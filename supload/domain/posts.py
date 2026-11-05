from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..config import ALLOWED_VIDEO_EXT
from ..utils import new_id, now_iso

VIDEO_KINDS = ("video", "reel")

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
    video = body.get("video") or None
    video_kind = body.get("video_kind") or "video"
    if video:
        if not isinstance(video, str) or "/" in video or Path(video).suffix.lower() not in ALLOWED_VIDEO_EXT or not (upload_dir / video).is_file():
            raise ValueError("Video không hợp lệ hoặc chưa được tải lên")
        if video_kind not in VIDEO_KINDS:
            raise ValueError("Loại video không hợp lệ")
        if photos:
            raise ValueError("Một bài chỉ có ảnh hoặc video, không có cả hai")
    if not (message or photos or link or video):
        raise ValueError("Bài viết đang trống")
    sched = body.get("scheduled_at") or None
    if sched:
        try:
            sched = datetime.fromisoformat(sched).isoformat(timespec="minutes")
        except (TypeError, ValueError):
            raise ValueError("Thời gian hẹn không hợp lệ") from None
    out = {"message": message, "photos": photos, "link": link, "scheduled_at": sched}
    if video:
        out.update(video=video, video_kind=video_kind)
    return out


def new_post(fields: dict, **extra) -> dict:
    return {
        "id": new_id(), **fields, "status": PENDING, "created_at": now_iso(),
        "done_at": None, "error": "", "result": "", **extra,
    }


def reset_to_pending(post: dict, **fields) -> None:
    """Đưa bài về trạng thái chờ, xoá dấu vết lần hẹn/đăng trước."""
    if "video" not in fields:  # bài sửa thành không còn video
        post.pop("video", None)
        post.pop("video_kind", None)
    post.update(fields, status=PENDING, error="")
    for k in ("fb_id", "fb_scheduled_at", "last_check_at"):
        post.pop(k, None)


def label(post: dict) -> str:
    return (post.get("message") or post.get("link") or "(ảnh)")[:60]
