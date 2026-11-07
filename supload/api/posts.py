"""Bài viết: thêm, sửa, xoá, đăng lại."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..domain import pages as pages_domain
from ..domain.posts import DONE, EDITABLE, RUNNING, SCHEDULED, clean_body, label, new_post, reset_to_pending
from ..integrations.facebook import FBError
from ..storage import add_log, find
from . import error, services

bp = Blueprint("posts", __name__, url_prefix="/api")


@bp.post("/posts")
def add_post():
    s = services()
    body = request.get_json(force=True)
    try:
        fields = clean_body(body, s.config.upload_dir)
        ig_fields = clean_body({**body, "channel": "instagram"}, s.config.upload_dir) if body.get("also_instagram") else None
        with s.store.transaction() as data:
            # "pages": đăng cùng nội dung lên nhiều Page (mỗi Page một bài); không có thì dùng "page" như cũ
            page_ids = list(dict.fromkeys(pages_domain.resolve(data, pid) for pid in (body.get("pages") or [body.get("page")])))
            created = []
            for page_id in page_ids:
                created.append(new_post(fields, page=page_id))
                if ig_fields:
                    if (pages_domain.find(data, page_id) or {}).get("instagram"):
                        created.append(new_post(ig_fields, page=page_id))
                    elif len(page_ids) == 1:  # nhiều Page: bỏ qua Page chưa liên kết Instagram
                        raise ValueError("Page này chưa liên kết tài khoản Instagram doanh nghiệp")
            data["posts"].extend(created)
            sched = fields["scheduled_at"]
            add_log(data, "info", "Đã thêm bài " + (f"hẹn {sched.replace('T', ' ')}" if sched else "đăng ngay")
                    + (f" cho {len(page_ids)} Page" if len(page_ids) > 1 else ""))
    except ValueError as e:
        return error(str(e))
    s.runtime.notify()
    return jsonify(post=created[0], posts=created)


def _cancel_on_facebook(post: dict, data: dict):
    """Huỷ bài đã hẹn trên Facebook. Trả về response lỗi nếu không huỷ được, None nếu ổn."""
    try:
        services().publisher.cancel(post, pages_domain.page_of(data, post))
    except FBError as e:
        return error(f"Không huỷ được bài hẹn trên Facebook: {e}", 502, can_force=True)
    return None


@bp.put("/posts/<post_id>")
def edit_post(post_id):
    s = services()
    body = request.get_json(force=True)
    data = s.store.load()
    try:
        existing = find(data["posts"], post_id) or {}
        fields = clean_body({**body, "channel": existing.get("channel") or "facebook"}, s.config.upload_dir)
        fields["page"] = pages_domain.resolve(data, body.get("page") or existing.get("page"))
    except ValueError as e:
        return error(str(e))
    post = find(data["posts"], post_id)
    if not post:
        return error("Không tìm thấy bài", 404)
    if post["status"] not in EDITABLE:
        return error("Chỉ sửa được bài đang chờ, đã hẹn hoặc bị lỗi")
    if post["status"] == SCHEDULED and (resp := _cancel_on_facebook(post, data)):
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
    if post["status"] == SCHEDULED and request.args.get("force") != "1" and (resp := _cancel_on_facebook(post, data)):
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
