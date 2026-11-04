from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..utils import new_id, now_iso

# Vòng đời bài viết:
#   pending -> running -> done | error
#   pending -> scheduled (đã hẹn trên Facebook) -> done | error
PENDING, RUNNING, SCHEDULED, DONE, ERROR = "pending", "running", "scheduled", "done", "error"
ACTIVE = (PENDING, RUNNING, SCHEDULED)  # chưa kết thúc
EDITABLE = (PENDING, ERROR, SCHEDULED)


def clean_body(body: dict, upload_dir: Path) -> dict:
    """Kiểm tra & chuẩn hoá nội dung bài. Ném ValueError nếu không hợp lệ."""
    message = (body.get("message") or "").strip()
    photos = [p for p in body.get("photos", []) if isinstance(p, str) and "/" not in p and (upload_dir / p).is_file()]
    link = (body.get("link") or "").strip()
    if not (message or photos or link):
        raise ValueError("Bài viết đang trống")
    sched = body.get("scheduled_at") or None
    if sched:
        try:
            sched = datetime.fromisoformat(sched).isoformat(timespec="minutes")
        except (TypeError, ValueError):
            raise ValueError("Thời gian hẹn không hợp lệ") from None
    return {"message": message, "photos": photos, "link": link, "scheduled_at": sched}


def new_post(fields: dict, **extra) -> dict:
    return {
        "id": new_id(), **fields, "status": PENDING, "created_at": now_iso(),
        "done_at": None, "error": "", "result": "", **extra,
    }


def reset_to_pending(post: dict, **fields) -> None:
    """Đưa bài về trạng thái chờ, xoá dấu vết lần hẹn/đăng trước."""
    post.update(fields, status=PENDING, error="")
    for k in ("fb_id", "fb_scheduled_at", "last_check_at"):
        post.pop(k, None)


def label(post: dict) -> str:
    return (post.get("message") or post.get("link") or "(ảnh)")[:60]
