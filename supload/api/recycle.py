"""Tự đăng lại bài hiệu quả: cấu hình, xem trước, chạy ngay."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from ..domain import recycle
from ..domain.insights import engagement
from ..services import recycle as svc_recycle
from . import error, services

bp = Blueprint("recycle", __name__, url_prefix="/api/recycle")


def _recycler():
    return services().scheduler.recycler


@bp.get("")
def overview():
    data = services().store.load()
    now = datetime.now()
    out = []
    for pg in data["pages"]:
        c = _recycler().preview(data, pg["id"], now)
        out.append({"page": pg["id"], "name": pg["name"], "last_at": svc_recycle.state(data, pg["id"]).get("last_at"),
                    "next": c and {"id": c["id"], "message": c.get("message", ""), "photos": c.get("photos", []), "video": c.get("video"),
                                   "done_at": c.get("done_at"), "engagement": engagement(c["stats"]), "stats": c["stats"]}})
    return jsonify(config=svc_recycle.config(data), pages=out)


@bp.put("/config")
def save_config():
    cfg = recycle.clean_config(request.get_json(force=True))
    with services().store.transaction() as data:
        data["settings"]["recycle"] = cfg
    services().runtime.notify()
    return jsonify(config=cfg)


@bp.post("/run")
def run_now():
    page_id = (request.get_json(silent=True) or {}).get("page")
    data = services().store.load()
    page = next((p for p in data["pages"] if p["id"] == page_id), None)
    if not page:
        return error("Không tìm thấy Page", 404)
    post = _recycler().run(page, datetime.now(), force=True)
    if not post:
        return error("Page chưa có bài nào đủ điều kiện đăng lại (cần bài đã đăng lâu hơn số ngày đã chọn, tương tác từ mức trung bình)")
    services().runtime.notify()
    return jsonify(post=post)
