"""Các Page được kết nối: liệt kê, thêm, sửa, xoá, đặt mặc định, kiểm tra."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from datetime import datetime

from ..domain import health
from ..domain import pages as pages_domain
from ..integrations import facebook
from ..storage import add_log
from . import error, services
from .settings import start_browser_job

bp = Blueprint("pages", __name__, url_prefix="/api/pages")


def _list(data: dict) -> list[dict]:
    default = pages_domain.default_page(data)
    return [{**pages_domain.public(p, default and default["id"]), "health": health.of(data, p["id"])} for p in data["pages"]]


@bp.get("")
def list_pages():
    return jsonify(pages=_list(services().store.load()))


@bp.post("")
def add_page():
    """Thêm Page thủ công: {kind:"api", fb_page_id, token, name?} hoặc {kind:"browser", url, name?}."""
    body = request.get_json(force=True)
    try:
        page = pages_domain.new_page(body.get("kind", ""), name=body.get("name", ""), fb_page_id=body.get("fb_page_id", ""),
                                     token=body.get("token", ""), url=body.get("url", ""))
    except ValueError as e:
        return error(str(e))
    with services().store.transaction() as data:
        if page["kind"] == "api" and any(p["kind"] == "api" and p["fb_page_id"] == page["fb_page_id"] for p in data["pages"]):
            return error("Page này đã được kết nối")
        data["pages"].append(page)
        if not data["settings"].get("default_page"):
            data["settings"]["default_page"] = page["id"]
        add_log(data, "ok", f"Đã thêm Page: {page['name']}")
        out = _list(data)
    services().runtime.notify()
    return jsonify(page=pages_domain.public(page, None), pages=out)


@bp.put("/<page_id>")
def edit_page(page_id):
    body = request.get_json(force=True)
    with services().store.transaction() as data:
        page = pages_domain.find(data, page_id)
        if not page:
            return error("Không tìm thấy Page", 404)
        try:
            pages_domain.update_page(page, {k: body.get(k) for k in ("name", "fb_page_id", "token", "url")})
        except ValueError as e:
            return error(str(e))
        if body.get("token") or body.get("fb_page_id"):
            health.reset(data, page_id)
        out = _list(data)
    return jsonify(pages=out)


@bp.delete("/<page_id>")
def delete_page(page_id):
    """Xoá Page. Không cho xoá khi Page còn bài chưa đăng (tránh bài mồ côi / bài hẹn còn trên Facebook)."""
    with services().store.transaction() as data:
        page = pages_domain.find(data, page_id)
        if not page:
            return error("Không tìm thấy Page", 404)
        waiting = pages_domain.active_posts(data, page_id)
        if waiting:
            return error(f"Page “{page['name']}” còn {len(waiting)} bài chưa đăng. Xoá hoặc chuyển các bài đó sang Page khác trước.", 409)
        data["pages"] = [p for p in data["pages"] if p["id"] != page_id]
        health.reset(data, page_id)
        if data["settings"].get("default_page") == page_id:
            data["settings"]["default_page"] = data["pages"][0]["id"] if data["pages"] else ""
        for f in data["flows"]:
            if f.get("page") == page_id:
                f["page"] = ""  # flow quay về dùng Page mặc định
        add_log(data, "info", f"Đã xoá Page: {page['name']}")
        out = _list(data)
    return jsonify(pages=out)


@bp.post("/<page_id>/default")
def set_default(page_id):
    with services().store.transaction() as data:
        page = pages_domain.find(data, page_id)
        if not page:
            return error("Không tìm thấy Page", 404)
        data["settings"]["default_page"] = page_id
        out = _list(data)
    return jsonify(pages=out)


@bp.post("/<page_id>/test")
def test_page(page_id):
    s = services()
    data = s.store.load()
    page = pages_domain.find(data, page_id)
    if not page:
        return error("Không tìm thấy Page", 404)
    if page["kind"] == "browser":
        start_browser_job("check")
        return jsonify(ok=True, pending=True, text="Đang kiểm tra đăng nhập trong trình duyệt...")
    ok, err, code, name = s.publisher.check_page(page)
    with s.store.transaction() as data:
        health.record(data, page_id, ok, datetime.now(), err, code)
        p = pages_domain.find(data, page_id)
        if ok and p and name:
            p["name"] = name
        if ok:
            add_log(data, "ok", f"Kết nối thành công tới Page: {name or page['name']}")
    if not ok:
        return error(err)
    return jsonify(ok=True, text=f"Kết nối tốt tới Page “{name or page['name']}”")
