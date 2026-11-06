"""Các Page được kết nối. Mỗi Page có cách đăng riêng:

  kind="api"     -> fb_page_id + token (Graph API)
  kind="browser" -> url (điều khiển trình duyệt, dùng chung phiên đăng nhập fb_profile/)
"""
from __future__ import annotations

import re

from ..utils import new_id, now_iso
from .posts import ACTIVE

KINDS = ("api", "browser")
LEGACY_KEYS = ("method", "page_id", "page_token", "page_name", "page_url")
FB_URL_RE = re.compile(r"^https?://(www\.|m\.|web\.)?facebook\.com/.+", re.I)


def new_page(kind: str, *, name: str = "", fb_page_id: str = "", token: str = "", url: str = "") -> dict:
    """Tạo Page mới (đã kiểm tra). Ném ValueError nếu thiếu thông tin."""
    if kind not in KINDS:
        raise ValueError("Cách đăng không hợp lệ")
    page = {"id": new_id("pg_", 8), "kind": kind, "name": "", "fb_page_id": "", "token": "", "url": "", "created_at": now_iso()}
    return update_page(page, {"name": name, "fb_page_id": fb_page_id, "token": token, "url": url})


def update_page(page: dict, body: dict) -> dict:
    """Áp thay đổi (sửa tại chỗ) rồi kiểm tra. Token để trống = giữ token cũ."""
    for k in ("name", "fb_page_id", "url"):
        if k in body and body[k] is not None:
            page[k] = str(body[k]).strip()
    if body.get("token"):
        page["token"] = str(body["token"]).strip()
    if page["kind"] == "api":
        if not page["fb_page_id"] or not page["token"]:
            raise ValueError("Page qua API cần Page ID và Page Token")
        page["name"] = page["name"] or f"Page {page['fb_page_id']}"
    else:
        if not FB_URL_RE.match(page["url"]):
            raise ValueError("Địa chỉ Page phải là link facebook.com/…")
        page["name"] = page["name"] or page["url"].rstrip("/").rsplit("/", 1)[-1]
    page["name"] = page["name"][:80]
    return page


def public(page: dict, default_id: str | None) -> dict:
    """Bản gửi cho trình duyệt: ẩn token."""
    out = {k: v for k, v in page.items() if k != "token"}
    out["token_set"] = bool(page.get("token"))
    out["default"] = page["id"] == default_id
    return out


def find(data: dict, page_id: str | None) -> dict | None:
    return next((p for p in data.get("pages", []) if p["id"] == page_id), None)


def default_page(data: dict) -> dict | None:
    pages = data.get("pages", [])
    return find(data, data["settings"].get("default_page")) or (pages[0] if pages else None)


def page_of(data: dict, post: dict) -> dict | None:
    """Page mà bài sẽ đăng lên (bài cũ chưa gắn Page -> Page mặc định)."""
    return find(data, post.get("page")) or default_page(data)


def resolve(data: dict, page_id: str | None) -> str:
    """Kiểm tra page_id do người dùng chọn; để trống = Page mặc định. Ném ValueError nếu không hợp lệ."""
    if page_id:
        if not find(data, page_id):
            raise ValueError("Không tìm thấy Page đã chọn")
        return page_id
    d = default_page(data)
    if not d:
        raise ValueError("Chưa kết nối Page nào: vào Cài đặt để thêm Page")
    return d["id"]


def active_posts(data: dict, page_id: str) -> list[dict]:
    d = default_page(data)
    return [p for p in data["posts"] if p["status"] in ACTIVE and (p.get("page") or (d and d["id"])) == page_id]


def migrate(data: dict) -> dict:
    """Chuyển dữ liệu kiểu cũ (một Page trong settings) sang danh sách pages. Chạy nhiều lần vẫn an toàn."""
    s = data["settings"]
    if "pages" not in data:
        pages = []
        if s.get("page_id") and s.get("page_token"):
            pages.append({"id": new_id("pg_", 8), "kind": "api", "name": s.get("page_name") or f"Page {s['page_id']}",
                          "fb_page_id": s["page_id"], "token": s["page_token"], "url": "", "created_at": now_iso()})
        if s.get("page_url"):
            pages.append({"id": new_id("pg_", 8), "kind": "browser", "name": s["page_url"].rstrip("/").rsplit("/", 1)[-1],
                          "fb_page_id": "", "token": "", "url": s["page_url"], "created_at": now_iso()})
        data["pages"] = pages
        if pages:
            preferred = next((p for p in pages if p["kind"] == s.get("method")), pages[0])
            s["default_page"] = preferred["id"]
            for post in data["posts"]:
                if post.get("status") in ACTIVE and not post.get("page"):
                    post["page"] = preferred["id"]
    for k in LEGACY_KEYS:
        s.pop(k, None)
    if s.get("default_page") and not find(data, s["default_page"]):
        s["default_page"] = data["pages"][0]["id"] if data["pages"] else ""
    return data


def limit_key(data: dict, post: dict) -> str | None:
    """Khoá tính giới hạn an toàn: mỗi Page, mỗi kênh (Facebook / Instagram) tính riêng."""
    pid = (page_of(data, post) or {}).get("id")
    return f"{pid}:ig" if pid and post.get("channel") == "instagram" else pid


def set_instagram(data: dict, page_id: str, info: dict) -> None:
    """Lưu tài khoản Instagram doanh nghiệp liên kết với Page (từ page_info)."""
    page = find(data, page_id)
    if page is None or not isinstance(info, dict):
        return
    ig = info.get("instagram_business_account") or None
    page["instagram"] = {"id": ig["id"], "username": ig.get("username", "")} if ig and ig.get("id") else None
