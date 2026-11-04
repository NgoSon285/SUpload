"""Flow chiến dịch: quản lý và chạy."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from ..domain import flows as flow_domain
from ..domain.posts import ERROR, PENDING, SCHEDULED, clean_body, new_post
from ..integrations.facebook import FBError
from ..storage import add_log, find
from ..utils import now_iso
from . import error, services

bp = Blueprint("flows", __name__, url_prefix="/api/flows")
MAX_RUN = 500
EMPTY_STATS = {"pending": 0, "done": 0, "error": 0}


@bp.get("")
def list_flows():
    data = services().store.load()
    stats = flow_domain.stats(data["posts"])
    items = sorted(data["flows"], key=lambda f: f.get("updated_at") or "", reverse=True)
    return jsonify(flows=[{**f, "stats": stats.get(f["id"], EMPTY_STATS)} for f in items])


@bp.put("/<flow_id>")
def save_flow(flow_id):
    if not flow_domain.FLOW_ID_RE.match(flow_id):
        return error("Mã flow không hợp lệ")
    body = request.get_json(force=True)
    with services().store.lock:
        data = services().store.load()
        old = find(data["flows"], flow_id)
        try:
            flow = flow_domain.upsert(flow_id, old, body)
        except ValueError as e:
            return error(str(e))
        if old:
            data["flows"][data["flows"].index(old)] = flow
        else:
            data["flows"].append(flow)
        services().store.save(data)
    return jsonify(flow=flow)


@bp.post("/<flow_id>/duplicate")
def duplicate_flow(flow_id):
    with services().store.transaction() as data:
        src = find(data["flows"], flow_id)
        if not src:
            return error("Không tìm thấy flow", 404)
        copy = flow_domain.duplicate(src)
        data["flows"].append(copy)
    return jsonify(flow=copy)


@bp.post("/import")
def import_flow():
    body = request.get_json(force=True)
    try:
        flow = flow_domain.imported(body.get("flow", body))
    except ValueError as e:
        return error(str(e))
    with services().store.transaction() as data:
        data["flows"].append(flow)
        add_log(data, "info", f"Đã nhập flow “{flow['name']}”")
    return jsonify(flow=flow)


@bp.delete("/<flow_id>")
def delete_flow(flow_id):
    """Xoá flow. ?delete_posts=1 -> xoá luôn bài chưa đăng của flow (bài đã hẹn trên Facebook được huỷ)."""
    s = services()
    data = s.store.load()
    flow = find(data["flows"], flow_id)
    if not flow:
        return error("Không tìm thấy flow", 404)
    remove_ids, kept = set(), 0
    if request.args.get("delete_posts") == "1":
        for p in data["posts"]:
            if p.get("flow_id") != flow_id or p["status"] not in (PENDING, ERROR, SCHEDULED):
                continue
            try:
                s.publisher.cancel(p, data["settings"])
                remove_ids.add(p["id"])
            except FBError:
                kept += 1  # không huỷ được trên Facebook -> giữ lại để người dùng xử lý
    with s.store.transaction() as data:
        data["flows"] = [f for f in data["flows"] if f["id"] != flow_id]
        data["posts"] = [p for p in data["posts"] if p["id"] not in remove_ids]
        add_log(data, "info", f"Đã xoá flow “{flow['name']}”" + (f" và {len(remove_ids)} bài chưa đăng" if remove_ids else ""))
    return jsonify(ok=True, removed_posts=len(remove_ids), kept_posts=kept)


@bp.post("/run")
def run_flow():
    """Nhận danh sách bài đã tính giờ từ flow -> thêm hàng loạt vào lịch đăng."""
    s = services()
    body = request.get_json(force=True)
    items = body.get("posts", [])
    flow_id = body.get("flow_id") or None
    if not items:
        return error("Flow chưa có bài viết nào")
    if len(items) > MAX_RUN:
        return error(f"Tối đa {MAX_RUN} bài mỗi lần chạy")
    created, now = [], datetime.now()
    try:
        for it in items:
            fields = clean_body(it, s.config.upload_dir)
            if fields["scheduled_at"] and datetime.fromisoformat(fields["scheduled_at"]) <= now:
                fields["scheduled_at"] = None  # giờ đã qua -> đăng ngay (vẫn theo giới hạn an toàn)
            created.append(new_post(fields, flow=(body.get("name") or "")[:80], flow_id=flow_id))
    except ValueError as e:
        return error(f"Bài #{len(created) + 1}: {e}")
    with s.store.transaction() as data:
        data["posts"].extend(created)
        f = find(data["flows"], flow_id) if flow_id else None
        if f:
            f.update(last_run_at=now_iso(), last_run_count=len(created))
        add_log(data, "info", f"Chạy flow “{body.get('name') or 'không tên'}”: thêm {len(created)} bài vào lịch")
    s.runtime.notify()
    return jsonify(count=len(created))
