"""Facebook Graph API: đăng bài, hẹn giờ, huỷ hẹn, kiểm tra trạng thái, đổi token."""
from __future__ import annotations

import json
import mimetypes
import os
import time
from datetime import datetime
from pathlib import Path

import requests

GRAPH_VERSION = os.getenv("FB_GRAPH_VERSION", "v23.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
# Meta đã ngừng host graph-video.facebook.com cho việc tải video: tải video thường qua graph.facebook.com
GRAPH_VIDEO = GRAPH
RUPLOAD = f"https://rupload.facebook.com/video-upload/{GRAPH_VERSION}"  # tải video Reels (dự phòng nếu start không trả upload_url)

# Chỉ số tiếp cận. Meta khai tử post_impressions_unique và total_video_impressions(_unique) từ 06/2026
# (một tên chỉ số không hợp lệ làm hỏng cả yêu cầu), thay bằng nhóm "Media views/viewers".
POST_REACH_METRIC = "post_total_media_view_unique"   # số người xem bài (thay post_impressions_unique)
VIDEO_VIEWS_METRIC = "total_video_views"             # lượt xem video/Reels

# Facebook chỉ nhận hẹn giờ từ 10 phút tới 30 ngày
SCHEDULE_MIN_SECONDS = 600
SCHEDULE_MAX_SECONDS = 30 * 86400


class FBError(RuntimeError):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


def call(method: str, path: str, base: str = GRAPH, **kwargs) -> dict:
    """Gọi Graph API. Mọi lời gọi đi qua hàm này (test thay hàm này bằng bản giả)."""
    url = f"{base}/{path.lstrip('/')}" if path else base
    resp = requests.request(method, url, timeout=600, **kwargs)
    try:
        data = resp.json()
    except ValueError:
        raise FBError(f"HTTP {resp.status_code}: {resp.text[:300]}") from None
    if isinstance(data, dict) and "error" in data:
        err = data["error"]
        raise FBError(f"[{err.get('code')}] {err.get('message')}", err.get("code"))
    return data


# ---------------------------------------------------------------- token
def exchange_long_lived_user_token(app_id: str, app_secret: str, short_token: str) -> str:
    data = call("GET", "oauth/access_token", params={
        "grant_type": "fb_exchange_token", "client_id": app_id,
        "client_secret": app_secret, "fb_exchange_token": short_token,
    })
    return data["access_token"]


def list_pages(user_token: str) -> list[dict]:
    return call("GET", "me/accounts", params={"access_token": user_token, "fields": "id,name,access_token"}).get("data", [])


def page_info(page_id: str, token: str) -> dict:
    """Tên Page và tài khoản Instagram doanh nghiệp liên kết (nếu có)."""
    return call("GET", page_id, params={"access_token": token, "fields": "name,instagram_business_account{id,username}"})


# ---------------------------------------------------------------- posting
class PagePoster:
    def __init__(self, page_id: str, page_token: str):
        if not page_id or not page_token:
            raise FBError("Thiếu Page ID hoặc Page Token: hãy kết nối Page trong Cài đặt (hoặc FB_PAGE_ID/FB_PAGE_TOKEN trong .env)")
        self.page_id = page_id
        self.token = page_token

    def _upload_photo(self, photo: str, published: bool, caption: str | None = None, temporary: bool = False) -> dict:
        data = {"access_token": self.token, "published": str(published).lower()}
        if temporary:
            data["temporary"] = "true"  # bắt buộc với ảnh dùng cho bài hẹn giờ
        if caption:
            data["caption"] = caption
        if photo.startswith(("http://", "https://")):
            data["url"] = photo
            return call("POST", f"{self.page_id}/photos", data=data)
        path = Path(photo).expanduser()
        if not path.is_file():
            raise FBError(f"Không tìm thấy ảnh: {photo}")
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        with path.open("rb") as fh:
            return call("POST", f"{self.page_id}/photos", data=data, files={"source": (path.name, fh, mime)})

    def post(self, message: str = "", link: str | None = None, photos: list[str] | None = None,
             schedule: datetime | None = None) -> dict:
        """Đăng ngay, hoặc hẹn giờ trên Facebook nếu có `schedule`. Trả về {'id': ...}."""
        photos = photos or []
        if not (message or link or photos):
            raise FBError("Bài viết trống: cần message, link hoặc photos")

        sched = {}
        if schedule:
            ts = int(schedule.timestamp())
            delta = ts - time.time()
            if not SCHEDULE_MIN_SECONDS <= delta <= SCHEDULE_MAX_SECONDS:
                raise FBError("Thời gian hẹn phải cách hiện tại từ 10 phút đến 30 ngày")
            sched = {"published": "false", "scheduled_publish_time": str(ts)}

        # 1 ảnh, không hẹn giờ -> đăng thẳng qua /photos
        if len(photos) == 1 and not sched and not link:
            return self._upload_photo(photos[0], published=True, caption=message)

        data = {"access_token": self.token, **sched}
        if message:
            data["message"] = message
        if link:
            data["link"] = link
        # nhiều ảnh (hoặc ảnh + hẹn giờ): upload ẩn rồi gắn vào bài /feed
        for i, photo in enumerate(photos):
            media = self._upload_photo(photo, published=False, temporary=bool(sched))
            data[f"attached_media[{i}]"] = json.dumps({"media_fbid": media["id"]})
        return call("POST", f"{self.page_id}/feed", data=data)

    # ------------------------------------------------------------ video
    @staticmethod
    def _schedule_fields(schedule: datetime | None) -> dict:
        if not schedule:
            return {}
        ts = int(schedule.timestamp())
        if not SCHEDULE_MIN_SECONDS <= ts - time.time() <= SCHEDULE_MAX_SECONDS:
            raise FBError("Thời gian hẹn phải cách hiện tại từ 10 phút đến 30 ngày")
        return {"published": "false", "scheduled_publish_time": str(ts)}

    def post_video(self, path: str, message: str = "", schedule: datetime | None = None) -> dict:
        """Video thường (POST /{page}/videos, gửi file qua trường source). Trả về {'id': video_id}."""
        p = Path(path)
        if not p.is_file():
            raise FBError(f"Không tìm thấy video: {path}")
        data = {"access_token": self.token, "description": message, **self._schedule_fields(schedule)}
        mime = mimetypes.guess_type(p.name)[0] or "video/mp4"
        with p.open("rb") as fh:
            return call("POST", f"{self.page_id}/videos", base=GRAPH_VIDEO, data=data, files={"source": (p.name, fh, mime)})

    def post_reel(self, path: str, message: str = "", schedule: datetime | None = None) -> dict:
        """Reels: 3 bước start -> tải file lên rupload -> finish. Trả về {'id': video_id}."""
        p = Path(path)
        if not p.is_file():
            raise FBError(f"Không tìm thấy video: {path}")
        sched = self._schedule_fields(schedule)
        start = call("POST", f"{self.page_id}/video_reels", data={"access_token": self.token, "upload_phase": "start"})
        video_id = start["video_id"]
        upload_url = start.get("upload_url") or f"{RUPLOAD}/{video_id}"
        call("POST", "", base=upload_url, data=p.read_bytes(),
             headers={"Authorization": f"OAuth {self.token}", "offset": "0", "file_size": str(p.stat().st_size)})
        finish = {"access_token": self.token, "upload_phase": "finish", "video_id": video_id, "description": message,
                  "video_state": "SCHEDULED" if sched else "PUBLISHED"}
        if sched:
            finish["scheduled_publish_time"] = sched["scheduled_publish_time"]
        call("POST", f"{self.page_id}/video_reels", data=finish)
        return {"id": video_id}

    # ------------------------------------------------------------ chỉ số tương tác
    def engagement(self, post_id: str, video: bool = False) -> dict:
        """Cảm xúc, bình luận, chia sẻ (cần pages_read_engagement) và tiếp cận (cần read_insights).

        Trả về {"reactions", "comments", "shares", "reach", "reach_error"}; thiếu quyền tiếp cận thì reach=None.
        """
        if video:
            fields = "likes.summary(total_count).limit(0),comments.summary(total_count).limit(0)"
        else:
            fields = "reactions.summary(total_count).limit(0),comments.summary(total_count).limit(0),shares"
        d = call("GET", post_id, params={"access_token": self.token, "fields": fields})
        total = lambda k: int(((d.get(k) or {}).get("summary") or {}).get("total_count") or 0)  # noqa: E731
        out = {"reactions": total("likes" if video else "reactions"), "comments": total("comments"),
               "shares": int((d.get("shares") or {}).get("count") or 0), "reach": None, "reach_error": None}
        edge, metric = ("video_insights", VIDEO_VIEWS_METRIC) if video else ("insights", POST_REACH_METRIC)
        try:
            ins = call("GET", f"{post_id}/{edge}", params={"access_token": self.token, "metric": metric, "period": "lifetime"})
            out["reach"] = _lifetime_value(ins)
        except FBError as e:
            if e.code in (10, 200):
                out["reach_error"] = "Cần quyền read_insights để xem lượt tiếp cận"
            elif e.code == 100 and "metric" in str(e).lower():
                out["reach_error"] = "Facebook không còn hỗ trợ chỉ số tiếp cận này (cần cập nhật ứng dụng)"
            else:
                out["reach_error"] = str(e)
        return out

    # ------------------------------------------------------------ bình luận
    COMMENT_FIELDS = "id,message,from{id,name},created_time,is_hidden,can_hide,can_reply_privately,permalink_url"

    def recent_posts(self, since: datetime, limit: int = 25) -> list[dict]:
        """Bài trên Page từ `since` (cần để đọc bình luận)."""
        d = call("GET", f"{self.page_id}/posts", params={
            "access_token": self.token, "fields": "id,message,created_time,permalink_url",
            "since": str(int(since.timestamp())), "limit": str(limit)})
        return d.get("data") or []

    def comments(self, post_id: str, limit: int = 100) -> list[dict]:
        """Bình luận mới nhất của một bài (cả trả lời lồng nhau)."""
        d = call("GET", f"{post_id}/comments", params={
            "access_token": self.token, "fields": self.COMMENT_FIELDS, "filter": "stream",
            "order": "reverse_chronological", "limit": str(limit)})
        return d.get("data") or []

    def hide_comment(self, comment_id: str, hidden: bool = True) -> None:
        call("POST", comment_id, data={"access_token": self.token, "is_hidden": str(hidden).lower()})

    def reply_comment(self, comment_id: str, message: str) -> dict:
        """Trả lời công khai dưới bình luận."""
        return call("POST", f"{comment_id}/comments", data={"access_token": self.token, "message": message})

    def private_reply(self, comment_id: str, message: str) -> dict:
        """Nhắn riêng (Messenger) cho người bình luận. Facebook chỉ cho 1 tin mỗi bình luận, trong 7 ngày."""
        return call("POST", f"{self.page_id}/messages", data={
            "access_token": self.token, "recipient": json.dumps({"comment_id": comment_id}),
            "message": json.dumps({"text": message}, ensure_ascii=False), "messaging_type": "RESPONSE"})

    def delete(self, post_id: str) -> None:
        """Xoá bài (dùng để huỷ bài đã hẹn giờ)."""
        call("DELETE", post_id, params={"access_token": self.token})

    def is_published(self, post_id: str, video: bool = False) -> bool:
        """Bài (hoặc video/Reels nếu video=True) đã lên chưa."""
        field = "published" if video else "is_published"
        return bool(call("GET", post_id, params={"access_token": self.token, "fields": field}).get(field))


def _lifetime_value(ins: dict) -> int:
    """Lấy giá trị trọn đời từ kết quả insights; bỏ qua các dòng theo ngày nếu Facebook trả kèm."""
    rows = ins.get("data") or []
    row = next((r for r in rows if r.get("period") == "lifetime"), rows[0] if rows else {})
    values = row.get("values") or [{}]
    v = values[-1].get("value") or 0
    return int(sum(v.values()) if isinstance(v, dict) else v)


# ---------------------------------------------------------------- Instagram (thử nghiệm)
IG_RUPLOAD = f"https://rupload.facebook.com/ig-api-upload/{GRAPH_VERSION}"
IG_CAPTION_MAX = 2200
IG_CAROUSEL_MAX = 10


class InstagramPoster:
    """Đăng lên tài khoản Instagram doanh nghiệp liên kết với Page (Graph API, đăng nhập bằng Facebook).

    API Instagram chỉ nhận ảnh qua link public, nên ảnh được tải lên Facebook ở chế độ ẩn để lấy link,
    đăng xong thì xoá. Video/Reels được tải thẳng lên (resumable upload).
    """

    def __init__(self, ig_user_id: str, page: PagePoster, sleep=time.sleep, wait_seconds: int = 300):
        if not ig_user_id:
            raise FBError("Page chưa liên kết tài khoản Instagram doanh nghiệp (bấm Kiểm tra ở Cài đặt để tìm lại)")
        self.ig = ig_user_id
        self.page = page
        self.token = page.token
        self.sleep = sleep
        self.wait_seconds = wait_seconds

    def _photo_url(self, path: str) -> tuple[str, str]:
        """Tải ảnh lên Facebook (ẩn) rồi lấy link ảnh public. Trả về (link, id ảnh tạm)."""
        photo_id = self.page._upload_photo(path, published=False)["id"]
        d = call("GET", photo_id, params={"access_token": self.token, "fields": "images"})
        images = sorted(d.get("images") or [], key=lambda i: i.get("width", 0), reverse=True)
        if not images:
            raise FBError("Không lấy được link ảnh để gửi Instagram")
        return images[0]["source"], photo_id

    def _container(self, **params) -> str:
        return call("POST", f"{self.ig}/media", data={"access_token": self.token, **params})["id"]

    def _wait(self, container_id: str) -> None:
        waited = 0
        while True:
            st = call("GET", container_id, params={"access_token": self.token, "fields": "status_code,status"})
            code = st.get("status_code")
            if code == "FINISHED":
                return
            if code in ("ERROR", "EXPIRED"):
                raise FBError(f"Instagram xử lý media bị lỗi ({code}): {st.get('status') or ''}".strip())
            if waited >= self.wait_seconds:
                raise FBError("Instagram xử lý media quá lâu, thử lại sau")
            self.sleep(3)
            waited += 3

    def _publish(self, container_id: str) -> dict:
        self._wait(container_id)
        return call("POST", f"{self.ig}/media_publish", data={"access_token": self.token, "creation_id": container_id})

    def post_photos(self, paths: list[str], caption: str = "") -> dict:
        if not paths:
            raise FBError("Instagram cần ít nhất một ảnh hoặc video")
        caption = caption[:IG_CAPTION_MAX]
        temp = []
        try:
            urls = []
            for p in paths[:IG_CAROUSEL_MAX]:
                url, pid = self._photo_url(p)
                urls.append(url)
                temp.append(pid)
            if len(urls) == 1:
                return self._publish(self._container(image_url=urls[0], caption=caption))
            children = [self._container(image_url=u, is_carousel_item="true") for u in urls]
            return self._publish(self._container(media_type="CAROUSEL", children=",".join(children), caption=caption))
        finally:
            for pid in temp:  # dọn ảnh tạm trên Facebook
                try:
                    self.page.delete(pid)
                except FBError:
                    pass

    def post_reel(self, path: str, caption: str = "") -> dict:
        p = Path(path)
        if not p.is_file():
            raise FBError(f"Không tìm thấy video: {path}")
        start = call("POST", f"{self.ig}/media", data={
            "access_token": self.token, "media_type": "REELS", "upload_type": "resumable",
            "caption": caption[:IG_CAPTION_MAX], "share_to_feed": "true"})
        cid = start["id"]
        call("POST", "", base=start.get("uri") or f"{IG_RUPLOAD}/{cid}", data=p.read_bytes(),
             headers={"Authorization": f"OAuth {self.token}", "offset": "0", "file_size": str(p.stat().st_size)})
        return self._publish(cid)

    def permalink(self, media_id: str) -> str:
        try:
            return call("GET", media_id, params={"access_token": self.token, "fields": "permalink"}).get("permalink", "")
        except FBError:
            return ""


def parse_schedule(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)  # giờ địa phương của máy
        except ValueError:
            continue
    raise FBError(f"Sai định dạng thời gian '{value}', dùng 'YYYY-MM-DD HH:MM'")


def poster_from_env() -> PagePoster:
    return PagePoster(os.getenv("FB_PAGE_ID", ""), os.getenv("FB_PAGE_TOKEN", ""))
