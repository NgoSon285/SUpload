"""Hộp bình luận: xem, trả lời (công khai / nhắn riêng), ẩn / hiện, đồng bộ ngay."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from ..domain import comments as cm
from ..integrations.facebook import FBError
from ..services import comments as comment_sync
from ..storage import add_log
from . import error, services

bp = Blueprint("comments", __name__, url_prefix="/api/comments")
FILTERS = {
    "all": lambda c: True,
    "unreplied": lambda c: not c.get("replies") and not c.get("hidden"),
    "hidden": lambda c: c.get("hidden"),
    "auto": lambda c: any(r.get("auto") for r in c.get("replies", [])) or c.get("auto_hidden"),
}


def _find(data, cid):
    c = next((x for x in data.get("comments", []) if x["id"] == cid), None)
    page = next((p for p in data["pages"] if c and p["id"] == c["page"]), None)
    return c, page


@bp.get("")
def list_comments():
    data = services().store.load()
    page = request.args.get("page") or ""
    flt = FILTERS.get(request.args.get("filter", "all"), FILTERS["all"])
    q = cm.norm(request.args.get("q", ""))
    items = [c for c in data.get("comments", []) if (not page or c["page"] == page)]
    counts = {k: sum(1 for c in items if f(c)) for k, f in FILTERS.items()}
    items = [c for c in items if flt(c) and (not q or q in cm.norm(c["message"] + " " + c["from_name"]))]
    sync = {p["id"]: comment_sync.state(data, p["id"]) for p in data["pages"] if p.get("kind") == "api"}
    return jsonify(items=items[:300], total=len(items), counts=counts, sync=sync,
                   unseen=sum(1 for c in data.get("comments", []) if not c.get("seen")),
                   config=comment_sync.config(data))


@bp.post("/sync")
def sync_now():
    with services().store.transaction() as data:
        for st in data.get("comment_sync", {}).values():
            st["last_at"] = None
            st["error"] = ""
    services().runtime.notify()
    return jsonify(ok=True)


@bp.post("/seen")
def mark_seen():
    ids = set((request.get_json(silent=True) or {}).get("ids") or [])
    with services().store.transaction() as data:
        for c in data.get("comments", []):
            if not ids or c["id"] in ids:
                c["seen"] = True
    return jsonify(ok=True)


@bp.post("/<cid>/reply")
def reply(cid):
    body = request.get_json(force=True)
    text = str(body.get("message") or "").strip()
    private = bool(body.get("private"))
    if not text:
        return error("Câu trả lời đang trống")
    data = services().store.load()
    c, page = _find(data, cid)
    if not c or not page:
        return error("Không tìm thấy bình luận", 404)
    if private and (c.get("private_sent") or not c.get("can_reply_privately", True)):
        return error("Facebook chỉ cho nhắn riêng 1 lần cho mỗi bình luận (trong 7 ngày)")
    poster = services().publisher.poster(page)
    try:
        r = poster.private_reply(cid, text) if private else poster.reply_comment(cid, text)
    except FBError as e:
        msg = comment_sync.PERMISSION_HELP if e.code in comment_sync.PERMISSION_CODES else str(e)
        return error(f"Facebook từ chối: {msg}")
    now = datetime.now().isoformat(timespec="seconds")
    with services().store.transaction() as data:
        c, _ = _find(data, cid)
        if c:
            c["replies"].append({"text": text, "at": now, "auto": False, "private": private, "id": r.get("id")})
            c["seen"] = True
            if private:
                c["private_sent"] = True
        add_log(data, "ok", f"Đã {'nhắn riêng cho' if private else 'trả lời bình luận của'} {c['from_name'] if c else ''}")
    return jsonify(comment=c)


@bp.post("/<cid>/hide")
def hide(cid):
    hidden = bool((request.get_json(silent=True) or {}).get("hidden", True))
    data = services().store.load()
    c, page = _find(data, cid)
    if not c or not page:
        return error("Không tìm thấy bình luận", 404)
    try:
        services().publisher.poster(page).hide_comment(cid, hidden)
    except FBError as e:
        msg = comment_sync.PERMISSION_HELP if e.code in comment_sync.PERMISSION_CODES else str(e)
        return error(f"Facebook từ chối: {msg}")
    with services().store.transaction() as data:
        c, _ = _find(data, cid)
        if c:
            c.update(hidden=hidden, unhide_at=None, seen=True, hide_reason="" if not hidden else c.get("hide_reason") or "Ẩn thủ công")
    return jsonify(comment=c)


@bp.put("/config")
def save_config():
    cfg = cm.clean_config(request.get_json(force=True))
    with services().store.transaction() as data:
        old = comment_sync.config(data)
        data["settings"]["comments"] = cfg
        if cfg["enabled"] and not old["enabled"]:
            add_log(data, "info", "Đã bật tự động xử lý bình luận")
    services().runtime.notify()
    return jsonify(config=cfg)
