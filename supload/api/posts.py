"""Bài viết: thêm, sửa, xoá, đăng lại."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..domain.posts import DONE, EDITABLE, RUNNING, SCHEDULED, clean_body, label, new_post, reset_to_pending
from ..integrations.facebook import FBError
from ..storage import add_log, find
from . import error, services

bp = Blueprint("posts", __name__, url_prefix="/api")


@bp.post("/posts")
def add_post():
    s = services()
    try:
        fields = clean_body(request.get_json(force=True), s.config.upload_dir)
    except ValueError as e:
        return error(str(e))
    post = new_post(fields)
    with s.store.transaction() as data:
        data["posts"].append(post)
        sched = fields["scheduled_at"]
        add_log(data, "info", "Đã thêm bài " + (f"hẹn {sched.replace('T', ' ')}" if sched else "đăng ngay"))
    s.runtime.notify()
    return jsonify(post=post)


def _cancel_on_facebook(post: dict, settings: dict):
    """Huỷ bài đã hẹn trên Facebook. Trả về response lỗi nếu không huỷ được, None nếu ổn."""
    try:
        services().publisher.cancel(post, settings)
    except FBError as e:
        return error(f"Không huỷ được bài hẹn trên Facebook: {e}", 502, can_force=True)
    return None


@bp.put("/posts/<post_id>")
def edit_post(post_id):
    s = services()
    try:
        fields = clean_body(request.get_json(force=True), s.config.upload_dir)
    except ValueError as e:
        return error(str(e))
    data = s.store.load()
    post = find(data["posts"], post_id)
    if not post:
        return error("Không tìm thấy bài", 404)
    if post["status"] not in EDITABLE:
        return error("Chỉ sửa được bài đang chờ, đã hẹn hoặc bị lỗi")
    if post["status"] == SCHEDULED and (resp := _cancel_on_facebook(post, data["settings"])):
        return resp  # bài cũ vẫn còn trên Facebook -> không sửa, tránh đăng trùng
    with s.store.transaction() as data:
        post = find(data["posts"], post_id)
        reset_to_pending(post, **fields)
        add_log(data, "info", "Đã sửa bài: " + label(post)[:50])
    s.runtime.notify()
    return jsonify(post=post)


@bp.delete("/posts/<post_id>")
def delete_post(post_id):
    """Xoá bài khỏi lịch. Bài đã hẹn trên Facebook được huỷ trên Facebook trước. ?force=1 bỏ qua lỗi huỷ."""
    s = services()
    data = s.store.load()
    post = find(data["posts"], post_id)
    if not post:
        return jsonify(ok=True)
    if post["status"] == RUNNING:
        return error("Bài đang được đăng, thử lại sau ít giây")
    if post["status"] == SCHEDULED and request.args.get("force") != "1" and (resp := _cancel_on_facebook(post, data["settings"])):
        return resp
    with s.store.transaction() as data:
        data["posts"] = [p for p in data["posts"] if p["id"] != post_id]
        if post["status"] == SCHEDULED:
            add_log(data, "info", f"Đã huỷ bài hẹn trên Facebook: {label(post)}")
    return jsonify(ok=True)


@bp.post("/posts/<post_id>/retry")
def retry(post_id):
    s = services()
    with s.store.transaction() as data:
        post = find(data["posts"], post_id)
        if post and post["status"] not in (RUNNING, SCHEDULED):
            reset_to_pending(post, scheduled_at=None)
    s.runtime.notify()
    return jsonify(ok=True)


@bp.post("/clear-done")
def clear_done():
    with services().store.transaction() as data:
        data["posts"] = [p for p in data["posts"] if p["status"] != DONE]
    return jsonify(ok=True)
