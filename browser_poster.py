#!/usr/bin/env python3
"""SUpload (browser) - đăng bài lên Facebook Page bằng cách điều khiển trình duyệt.

Bạn tự đăng nhập 1 lần (lệnh `login`), phiên được lưu trong thư mục profile.
Công cụ KHÔNG lưu mật khẩu.

  python browser_poster.py login
  python browser_poster.py post --page https://www.facebook.com/TenPage -m "Xin chào" -p anh.jpg
  python browser_poster.py batch posts.json --page https://www.facebook.com/TenPage
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, TimeoutError as PWTimeout, sync_playwright

PROFILE_DIR = Path("fb_profile")
SHOT_DIR = Path("screenshots")
LOG_FILE = Path("browser_post_log.jsonl")
HOME = "https://www.facebook.com/"

# Nhãn giao diện tiếng Việt + tiếng Anh
RE_COMPOSER = re.compile(r"(Bạn đang nghĩ gì|What's on your mind|Tạo bài viết|Create post)", re.I)
RE_SWITCH = re.compile(r"^(Chuyển ngay|Switch now|Chuyển|Switch)$", re.I)
RE_PHOTO = re.compile(r"^(Ảnh/video|Photo/video)$", re.I)
RE_NEXT = re.compile(r"^(Tiếp|Next)$", re.I)
RE_POST = re.compile(r"^(Đăng|Post)$", re.I)


class PostError(RuntimeError):
    pass


def pause(a: float = 0.8, b: float = 2.0) -> None:
    time.sleep(random.uniform(a, b))


def open_context(pw, headless: bool) -> BrowserContext:
    return pw.chromium.launch_persistent_context(
        str(PROFILE_DIR),
        headless=headless,
        locale="vi-VN",
        viewport={"width": 1280, "height": 900},
    )


def is_logged_in(page: Page) -> bool:
    return not page.locator('input[name="email"], input[name="pass"]').first.is_visible()


# ---------------------------------------------------------------- actions
def switch_to_page_profile(page: Page, page_url: str) -> None:
    page.goto(page_url, wait_until="domcontentloaded")
    pause(2, 3)
    btn = page.get_by_role("button", name=RE_SWITCH).first
    try:
        if btn.is_visible(timeout=3000):
            btn.click()
            pause(1, 2)
            dlg_btn = page.get_by_role("dialog").get_by_role("button", name=RE_SWITCH).first
            if dlg_btn.is_visible(timeout=3000):
                dlg_btn.click()
            page.wait_for_load_state("domcontentloaded")
            pause(3, 5)
            page.goto(page_url, wait_until="domcontentloaded")
            pause(2, 3)
    except PWTimeout:
        pass  # đã đang ở vai trò Page


def create_post(page: Page, message: str, photos: list[str]) -> None:
    opener = page.get_by_role("button", name=RE_COMPOSER).first
    opener.wait_for(timeout=15000)
    opener.click()

    dialog = page.get_by_role("dialog").filter(has=page.locator('[contenteditable="true"]')).last
    box = dialog.locator('[contenteditable="true"][role="textbox"]').first
    box.wait_for(timeout=15000)
    pause()
    box.click()
    if message:
        for line_no, line in enumerate(message.split("\n")):
            if line_no:
                page.keyboard.press("Shift+Enter")
            page.keyboard.type(line, delay=random.randint(40, 110))
        pause()

    if photos:
        files = [str(Path(p).expanduser().resolve()) for p in photos]
        for f in files:
            if not Path(f).is_file():
                raise PostError(f"Không tìm thấy ảnh: {f}")
        file_input = dialog.locator('input[type="file"]').first
        if file_input.count() == 0:
            dialog.get_by_role("button", name=RE_PHOTO).first.click()
            pause()
            file_input = dialog.locator('input[type="file"]').first
        file_input.set_input_files(files)
        pause(3, 3 + len(files))  # chờ ảnh tải lên

    nxt = dialog.get_by_role("button", name=RE_NEXT).first
    if nxt.count() and nxt.is_visible():
        nxt.click()
        pause()

    post_btn = dialog.get_by_role("button", name=RE_POST).last
    post_btn.wait_for(timeout=10000)
    pause()
    post_btn.click()
    dialog.wait_for(state="detached", timeout=90000)
    pause(2, 4)


def run_posts(page_url: str, posts: list[dict], headless: bool, delay: tuple[int, int]) -> int:
    SHOT_DIR.mkdir(exist_ok=True)
    ok = 0
    with sync_playwright() as pw:
        ctx = open_context(pw, headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(HOME, wait_until="domcontentloaded")
        pause(2, 3)
        if not is_logged_in(page):
            ctx.close()
            raise PostError("Chưa đăng nhập. Chạy: python browser_poster.py login")
        switch_to_page_profile(page, page_url)

        for i, item in enumerate(posts, 1):
            try:
                create_post(page, item.get("message", ""), item.get("photos") or [])
                ok += 1
                _log({"ok": True, "index": i, "message": item.get("message", "")[:80]})
                print(f"[{i}/{len(posts)}] Đã đăng")
            except Exception as e:  # noqa: BLE001
                shot = SHOT_DIR / f"error_{datetime.now():%Y%m%d_%H%M%S}.png"
                page.screenshot(path=str(shot))
                _log({"ok": False, "index": i, "error": str(e), "screenshot": str(shot)})
                print(f"[{i}/{len(posts)}] LỖI: {e} (ảnh chụp: {shot})", file=sys.stderr)
                page.goto(page_url, wait_until="domcontentloaded")
            if i < len(posts):
                wait = random.randint(*delay)
                print(f"   chờ {wait}s ...")
                time.sleep(wait)
                page.reload(wait_until="domcontentloaded")
                pause(2, 3)
        ctx.close()
    return ok


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
    ok = run_posts(args.page, [post], args.headless, (0, 0))
    if not ok:
        raise PostError("Đăng thất bại, xem thư mục screenshots/")


def cmd_batch(args) -> None:
    posts = json.loads(Path(args.file).read_text(encoding="utf-8"))
    ok = run_posts(args.page, posts, args.headless, (args.min_delay, args.max_delay))
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
