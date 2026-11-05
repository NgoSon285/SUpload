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
GRAPH_VIDEO = f"https://graph-video.facebook.com/{GRAPH_VERSION}"      # tải video thường
RUPLOAD = f"https://rupload.facebook.com/video-upload/{GRAPH_VERSION}"  # tải video Reels

# Facebook chỉ nhận hẹn giờ từ 10 phút tới 30 ngày
SCHEDULE_MIN_SECONDS = 600
SCHEDULE_MAX_SECONDS = 30 * 86400


class FBError(RuntimeError):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


def call(method: str, path: str, base: str = GRAPH, **kwargs) -> dict:
    """Gọi Graph API. Mọi lời gọi đi qua hàm này (test thay hàm này bằng bản giả)."""
    resp = requests.request(method, f"{base}/{path.lstrip('/')}", timeout=600, **kwargs)
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
    return call("GET", page_id, params={"access_token": token, "fields": "name"})


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
        """Video thường (POST /{page}/videos trên graph-video). Trả về {'id': video_id}."""
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
        call("POST", video_id, base=RUPLOAD, data=p.read_bytes(),
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
        edge, metric = ("video_insights", "total_video_impressions_unique") if video else ("insights", "post_impressions_unique")
        try:
            ins = call("GET", f"{post_id}/{edge}", params={"access_token": self.token, "metric": metric})
            values = (ins.get("data") or [{}])[0].get("values") or [{}]
            out["reach"] = int(values[0].get("value") or 0)
        except FBError as e:
            out["reach_error"] = "Cần quyền read_insights để xem lượt tiếp cận" if e.code in (10, 200, 100) else str(e)
        return out

    def delete(self, post_id: str) -> None:
        """Xoá bài (dùng để huỷ bài đã hẹn giờ)."""
        call("DELETE", post_id, params={"access_token": self.token})

    def is_published(self, post_id: str, video: bool = False) -> bool:
        """Bài (hoặc video/Reels nếu video=True) đã lên chưa."""
        field = "published" if video else "is_published"
        return bool(call("GET", post_id, params={"access_token": self.token, "fields": field}).get(field))


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
