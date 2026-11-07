"""Cài đặt & kết nối Page (Graph API hoặc trình duyệt)."""
from __future__ import annotations

import threading

from flask import Blueprint, jsonify, request

from ..config import SECRET_KEYS
from ..domain import health
from ..domain import pages as pages_domain
from ..domain.settings import apply_update
from ..integrations import facebook
from ..storage import add_log, find
from . import error, services

bp = Blueprint("settings", __name__, url_prefix="/api")


@bp.post("/settings")
def save_settings():
    with services().store.transaction() as data:
        apply_update(data["settings"], request.get_json(force=True))
        add_log(data, "info", "Đã lưu cài đặt")
    services().runtime.notify()
    return jsonify(ok=True)


@bp.post("/settings/reveal")
def reveal_key():
    """Trả key AI đã lưu khi người dùng bấm nút con mắt (chỉ key AI; không nằm trong /api/state)."""
    k = request.get_json(force=True).get("key")
    if k not in SECRET_KEYS or not k.endswith("_api_key"):
        return error("Không xem được khoá này", 400)
    return jsonify(value=services().store.load()["settings"].get(k, ""))


@bp.post("/test-connection")
def test_connection():
    """Kiểm tra Page mặc định (giữ cho tương thích; dùng /api/pages/<id>/test cho từng Page)."""
    from .pages import test_page

    page = pages_domain.default_page(services().store.load())
    if not page:
        return error("Chưa kết nối Page nào")
    return test_page(page["id"])


@bp.post("/fb/pages")
def fb_pages():
    """Đổi user token -> danh sách Page kèm Page token dài hạn (token giữ phía máy chủ)."""
    body = request.get_json(force=True)
    s = services()
    settings = s.store.load()["settings"]
    app_id = body.get("app_id") or settings["app_id"]
    secret = body.get("app_secret") or settings["app_secret"]
    if not (app_id and secret and body.get("user_token")):
        return error("Cần App ID, App Secret và User Token")
    try:
        long_token = facebook.exchange_long_lived_user_token(app_id, secret, body["user_token"])
        pages = facebook.list_pages(long_token)
    except facebook.FBError as e:
        return error(str(e))
    with s.store.transaction() as data:
        data["settings"]["app_id"], data["settings"]["app_secret"] = app_id, secret
        data["_pages"] = pages
    return jsonify(pages=[{"id": p["id"], "name": p["name"]} for p in pages])


@bp.post("/fb/select-page")
def select_page():
    """Thêm Page vừa chọn từ danh sách (hoặc cập nhật token nếu Page đã có)."""
    page_id = request.get_json(force=True).get("id")
    with services().store.transaction() as data:
        src = find(data.get("_pages", []), page_id)
        if not src:
            return error("Không tìm thấy Page", 404)
        page = next((p for p in data["pages"] if p["kind"] == "api" and p["fb_page_id"] == src["id"]), None)
        if page:
            page.update(token=src["access_token"], name=src["name"])
            health.reset(data, page["id"])  # token mới -> kiểm tra lại
        else:
            page = pages_domain.new_page("api", name=src["name"], fb_page_id=src["id"], token=src["access_token"])
            data["pages"].append(page)
        if not data["settings"].get("default_page"):
            data["settings"]["default_page"] = page["id"]
        add_log(data, "ok", f"Đã kết nối Page: {page['name']}")
    services().runtime.notify()
    return jsonify(ok=True, page_id=page["id"])


def _browser_job(rt, config, action: str) -> None:
    try:
        from ..integrations import browser
    except ImportError:
        rt.login = "error: chưa cài playwright (pip install playwright && playwright install chromium)"
        return
    if not rt.browser_lock.acquire(blocking=False):
        rt.login = "busy"
        return
    try:
        browser.configure(config.profile_dir, config.screenshot_dir)
        rt.login = "waiting" if action == "login" else "checking"
        ok = browser.login_wait() if action == "login" else browser.check_login()
        rt.login = "yes" if ok else "no"
    except Exception as e:  # noqa: BLE001
        msg = str(e).splitlines()[0] if str(e) else e.__class__.__name__
        if "Executable doesn't exist" in msg:  # playwright có nhưng chưa tải Chromium
            msg = "chưa cài Chromium (chạy: playwright install chromium)"
        rt.login = f"error: {msg}"
    finally:
        rt.browser_lock.release()


def start_browser_job(action: str) -> None:
    s = services()
    threading.Thread(target=_browser_job, args=(s.runtime, s.config, action), daemon=True).start()


@bp.post("/browser/<action>")
def browser_action(action):
    if action not in ("login", "check"):
        return error("unknown", 404)
    start_browser_job(action)
    return jsonify(ok=True)
