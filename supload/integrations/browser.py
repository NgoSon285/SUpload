"""Đăng bài lên Facebook Page bằng cách điều khiển trình duyệt (Playwright).

Người dùng tự đăng nhập 1 lần; phiên được lưu trong thư mục profile. Không lưu mật khẩu.
Nếu Facebook đổi chữ trên nút, sửa các biểu thức RE_* bên dưới.
"""
from __future__ import annotations

import random
import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, TimeoutError as PWTimeout, sync_playwright

PROFILE_DIR = Path("fb_profile")
SHOT_DIR = Path("screenshots")


def configure(profile_dir: Path, shot_dir: Path) -> None:
    """Đặt thư mục lưu phiên đăng nhập và ảnh chụp lỗi (ứng dụng gọi khi khởi động)."""
    global PROFILE_DIR, SHOT_DIR
    PROFILE_DIR, SHOT_DIR = Path(profile_dir), Path(shot_dir)
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


def run_posts(page_url: str, posts: list[dict], headless: bool, delay: tuple[int, int], log=lambda entry: None) -> int:
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
                log({"ok": True, "index": i, "message": item.get("message", "")[:80]})
                print(f"[{i}/{len(posts)}] Đã đăng")
            except Exception as e:  # noqa: BLE001
                shot = SHOT_DIR / f"error_{datetime.now():%Y%m%d_%H%M%S}.png"
                page.screenshot(path=str(shot))
                log({"ok": False, "index": i, "error": str(e), "screenshot": str(shot)})
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


def login_wait(timeout: int = 600) -> bool:
    """Mở trình duyệt, chờ người dùng tự đăng nhập (dùng cho giao diện, không cần nhấn Enter)."""
    with sync_playwright() as pw:
        ctx = open_context(pw, headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(HOME)
        end = time.time() + timeout
        ok = False
        while time.time() < end:
            try:
                page.wait_for_timeout(2000)
                if "facebook.com" in page.url and "login" not in page.url and is_logged_in(page) \
                        and page.locator('[role="navigation"], [aria-label="Facebook"]').count():
                    ok = True
                    page.wait_for_timeout(3000)  # cho cookie ghi xong
                    break
            except Exception:  # noqa: BLE001 - người dùng đóng cửa sổ
                break
        try:
            ctx.close()
        except Exception:  # noqa: BLE001
            pass
        return ok


def check_login(headless: bool = True) -> bool:
    with sync_playwright() as pw:
        ctx = open_context(pw, headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(HOME, wait_until="domcontentloaded")
        pause(2, 3)
        ok = is_logged_in(page)
        ctx.close()
        return ok


def post_once(page_url: str, message: str, photos: list[str], headless: bool) -> None:
    """Đăng 1 bài; ném PostError (kèm đường dẫn ảnh chụp lỗi) nếu thất bại."""
    SHOT_DIR.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        ctx = open_context(pw, headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(HOME, wait_until="domcontentloaded")
            pause(2, 3)
            if not is_logged_in(page):
                raise PostError("Chưa đăng nhập Facebook trên trình duyệt")
            switch_to_page_profile(page, page_url)
            create_post(page, message, photos)
        except PostError:
            raise
        except Exception as e:  # noqa: BLE001
            shot = SHOT_DIR / f"error_{datetime.now():%Y%m%d_%H%M%S}.png"
            try:
                page.screenshot(path=str(shot))
            except Exception:  # noqa: BLE001
                pass
            raise PostError(f"{e.__class__.__name__}: {str(e).splitlines()[0]} (ảnh chụp: {shot})") from e
        finally:
            ctx.close()
