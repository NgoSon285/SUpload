"""Dòng lệnh: đăng bài qua trình duyệt.

  python browser_poster.py login
  python browser_poster.py post --page https://www.facebook.com/TenPage -m "Xin chào" -p anh.jpg
  python browser_poster.py batch posts.json --page https://www.facebook.com/TenPage
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from ..integrations.browser import HOME, PostError, is_logged_in, open_context, run_posts

LOG_FILE = Path("browser_post_log.jsonl")


def _log(entry: dict) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), **entry}, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- CLI
def cmd_login(_args) -> None:
    with sync_playwright() as pw:
        ctx = open_context(pw, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(HOME)
        print("Hãy đăng nhập Facebook trong cửa sổ vừa mở (kể cả 2FA).")
        input("Đăng nhập xong thì nhấn Enter ở đây để lưu phiên... ")
        print("Đã lưu phiên." if is_logged_in(page) else "Có vẻ chưa đăng nhập, thử lại.")
        ctx.close()


def cmd_post(args) -> None:
    post = {"message": args.message or "", "photos": args.photo or []}
    ok = run_posts(args.page, [post], args.headless, (0, 0), log=_log)
    if not ok:
        raise PostError("Đăng thất bại, xem thư mục screenshots/")


def cmd_batch(args) -> None:
    posts = json.loads(Path(args.file).read_text(encoding="utf-8"))
    ok = run_posts(args.page, posts, args.headless, (args.min_delay, args.max_delay), log=_log)
    print(f"Xong: {ok}/{len(posts)} bài. Log: {LOG_FILE}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Đăng bài Facebook Page qua trình duyệt")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("login", help="Mở trình duyệt để bạn đăng nhập 1 lần").set_defaults(func=cmd_login)

    for name, fn in (("post", cmd_post), ("batch", cmd_batch)):
        s = sub.add_parser(name)
        s.add_argument("--page", required=True, help="URL của Page, vd https://www.facebook.com/TenPage")
        s.add_argument("--headless", action="store_true", help="Chạy ẩn trình duyệt")
        s.set_defaults(func=fn)
        if name == "post":
            s.add_argument("-m", "--message")
            s.add_argument("-p", "--photo", action="append", help="Đường dẫn ảnh (lặp lại để thêm nhiều ảnh)")
        else:
            s.add_argument("file")
            s.add_argument("--min-delay", type=int, default=300, help="Giây chờ tối thiểu giữa các bài")
            s.add_argument("--max-delay", type=int, default=900, help="Giây chờ tối đa giữa các bài")

    args = ap.parse_args(argv)
    try:
        args.func(args)
    except PostError as e:
        print("Lỗi:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
