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

# Facebook chỉ nhận hẹn giờ từ 10 phút tới 30 ngày
SCHEDULE_MIN_SECONDS = 600
SCHEDULE_MAX_SECONDS = 30 * 86400


class FBError(RuntimeError):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


def call(method: str, path: str, **kwargs) -> dict:
    """Gọi Graph API. Mọi lời gọi đi qua hàm này (test thay hàm này bằng bản giả)."""
    resp = requests.request(method, f"{GRAPH}/{path.lstrip('/')}", timeout=120, **kwargs)
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

    def delete(self, post_id: str) -> None:
        """Xoá bài (dùng để huỷ bài đã hẹn giờ)."""
        call("DELETE", post_id, params={"access_token": self.token})

    def is_published(self, post_id: str) -> bool:
        return bool(call("GET", post_id, params={"access_token": self.token, "fields": "is_published"}).get("is_published"))


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
