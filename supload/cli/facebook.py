"""Dòng lệnh: đăng bài qua Graph API (không cần giao diện).

  python fb_poster.py token --user-token <TOKEN>
  python fb_poster.py post -m "Xin chào" -p anh.jpg [-s "2026-12-01 09:00"]
  python fb_poster.py batch posts.json --delay 60
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from ..config import ROOT  # noqa: F401  (nạp .env)
from ..integrations.facebook import (
    FBError, exchange_long_lived_user_token, list_pages, parse_schedule, poster_from_env,
)

LOG_FILE = Path("post_log.jsonl")


def log_result(entry: dict) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), **entry}, ensure_ascii=False) + "\n")


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
