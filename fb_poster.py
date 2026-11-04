#!/usr/bin/env python3
"""SUpload - đăng bài tự động lên Facebook Page qua Graph API chính thức.

Các lệnh:
  token   Đổi User Token ngắn hạn -> Page Access Token dài hạn
  post    Đăng 1 bài (chữ / link / ảnh / hẹn giờ)
  batch   Đăng hàng loạt từ file JSON, có giãn cách giữa các bài
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

GRAPH_VERSION = os.getenv("FB_GRAPH_VERSION", "v23.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
LOG_FILE = Path("post_log.jsonl")


class FBError(RuntimeError):
    pass


def _call(method: str, path: str, **kwargs) -> dict:
    resp = requests.request(method, f"{GRAPH}/{path.lstrip('/')}", timeout=120, **kwargs)
    try:
        data = resp.json()
    except ValueError:
        raise FBError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    if "error" in data:
        err = data["error"]
        raise FBError(f"[{err.get('code')}] {err.get('message')}")
    return data


# ---------------------------------------------------------------- token
def exchange_long_lived_user_token(app_id: str, app_secret: str, short_token: str) -> str:
    data = _call(
        "GET",
        "oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
    )
    return data["access_token"]


def list_pages(user_token: str) -> list[dict]:
    data = _call("GET", "me/accounts", params={"access_token": user_token, "fields": "id,name,access_token"})
    return data.get("data", [])


# ---------------------------------------------------------------- posting
class PagePoster:
    def __init__(self, page_id: str, page_token: str):
        if not page_id or not page_token:
            raise FBError("Thiếu FB_PAGE_ID hoặc FB_PAGE_TOKEN (xem .env.example)")
        self.page_id = page_id
        self.token = page_token

    def _upload_photo(self, photo: str, published: bool, caption: str | None = None) -> dict:
        data = {"access_token": self.token, "published": str(published).lower()}
        if caption:
            data["caption"] = caption
        if photo.startswith(("http://", "https://")):
            data["url"] = photo
            return _call("POST", f"{self.page_id}/photos", data=data)
        path = Path(photo).expanduser()
        if not path.is_file():
            raise FBError(f"Không tìm thấy ảnh: {photo}")
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        with path.open("rb") as fh:
            return _call("POST", f"{self.page_id}/photos", data=data, files={"source": (path.name, fh, mime)})

    def post(
        self,
        message: str = "",
        link: str | None = None,
        photos: list[str] | None = None,
        schedule: datetime | None = None,
    ) -> dict:
        photos = photos or []
        if not (message or link or photos):
            raise FBError("Bài viết trống: cần message, link hoặc photos")

        sched = {}
        if schedule:
            ts = int(schedule.timestamp())
            delta = ts - time.time()
            if not 600 <= delta <= 30 * 86400:
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
            media = self._upload_photo(photo, published=False)
            data[f"attached_media[{i}]"] = json.dumps({"media_fbid": media["id"]})
        return _call("POST", f"{self.page_id}/feed", data=data)


def parse_schedule(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)  # giờ địa phương của máy
        except ValueError:
            continue
    raise FBError(f"Sai định dạng thời gian '{value}', dùng 'YYYY-MM-DD HH:MM'")


def log_result(entry: dict) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), **entry}, ensure_ascii=False) + "\n")


def poster_from_env() -> PagePoster:
    return PagePoster(os.getenv("FB_PAGE_ID", ""), os.getenv("FB_PAGE_TOKEN", ""))


# ---------------------------------------------------------------- CLI
def cmd_token(args) -> None:
    app_id, secret = os.getenv("FB_APP_ID"), os.getenv("FB_APP_SECRET")
    if not app_id or not secret:
        raise FBError("Cần FB_APP_ID và FB_APP_SECRET trong .env")
    long_user = exchange_long_lived_user_token(app_id, secret, args.user_token)
    pages = list_pages(long_user)
    if not pages:
        print("Không thấy Page nào. Kiểm tra quyền pages_show_list / pages_manage_posts.")
        return
    print("Page Access Token (từ user token dài hạn -> không hết hạn):\n")
    for p in pages:
        print(f"# {p['name']}\nFB_PAGE_ID={p['id']}\nFB_PAGE_TOKEN={p['access_token']}\n")
    print("=> Copy cặp dòng của Page cần dùng vào file .env")


def cmd_post(args) -> None:
    res = poster_from_env().post(
        message=args.message or "",
        link=args.link,
        photos=args.photo,
        schedule=parse_schedule(args.schedule),
    )
    log_result({"ok": True, "message": args.message, "result": res})
    print("Đã đăng:", res)


def cmd_batch(args) -> None:
    posts = json.loads(Path(args.file).read_text(encoding="utf-8"))
    poster = poster_from_env()
    ok = 0
    for i, item in enumerate(posts, 1):
        try:
            res = poster.post(
                message=item.get("message", ""),
                link=item.get("link"),
                photos=item.get("photos"),
                schedule=parse_schedule(item.get("schedule")),
            )
            ok += 1
            log_result({"ok": True, "index": i, "result": res})
            print(f"[{i}/{len(posts)}] OK {res}")
        except FBError as e:
            log_result({"ok": False, "index": i, "error": str(e)})
            print(f"[{i}/{len(posts)}] LỖI {e}", file=sys.stderr)
        if i < len(posts) and args.delay:
            time.sleep(args.delay)
    print(f"Xong: {ok}/{len(posts)} bài thành công. Log: {LOG_FILE}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Đăng bài tự động lên Facebook Page (Graph API)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("token", help="Lấy Page Access Token dài hạn")
    t.add_argument("--user-token", required=True, help="User token từ Graph API Explorer")
    t.set_defaults(func=cmd_token)

    p = sub.add_parser("post", help="Đăng 1 bài")
    p.add_argument("-m", "--message")
    p.add_argument("-l", "--link")
    p.add_argument("-p", "--photo", action="append", help="URL hoặc đường dẫn ảnh (lặp lại để thêm nhiều ảnh)")
    p.add_argument("-s", "--schedule", help="Hẹn giờ 'YYYY-MM-DD HH:MM'")
    p.set_defaults(func=cmd_post)

    b = sub.add_parser("batch", help="Đăng hàng loạt từ file JSON")
    b.add_argument("file")
    b.add_argument("--delay", type=int, default=60, help="Số giây chờ giữa các bài (mặc định 60)")
    b.set_defaults(func=cmd_batch)

    args = ap.parse_args(argv)
    try:
        args.func(args)
    except FBError as e:
        print("Lỗi:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
