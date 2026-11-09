from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from ..config import ALLOWED_VIDEO_EXT
from ..utils import new_id, now_iso

VIDEO_KINDS = ("video", "reel")
CHANNELS = ("facebook", "instagram")

# Vòng đời bài viết:
#   pending -> running -> done | error
#   pending -> scheduled (đã hẹn trên Facebook) -> done | error
PENDING, RUNNING, SCHEDULED, DONE, ERROR = "pending", "running", "scheduled", "done", "error"
ACTIVE = (PENDING, RUNNING, SCHEDULED)  # chưa kết thúc
EDITABLE = (PENDING, ERROR, SCHEDULED)
# bình luận đầu tiên sau khi bài lên (AI và/hoặc link affiliate): thử tối đa 3 lần, cách nhau 10 phút
FIRST_COMMENT_TRIES, FIRST_COMMENT_RETRY = 3, timedelta(minutes=10)
MAX_AFFILIATE_LINK = 500


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
    channel = body.get("channel") or "facebook"
    if channel not in CHANNELS:
        raise ValueError("Kênh đăng không hợp lệ")
    if channel == "instagram":
        if not (photos or video):
            raise ValueError("Instagram cần ít nhất một ảnh hoặc video")
        out["channel"] = channel
    if video:
        out.update(video=video, video_kind=video_kind)
    affiliate = (body.get("affiliate_link") or "").strip()
    if affiliate and (not affiliate.startswith(("http://", "https://")) or len(affiliate) > MAX_AFFILIATE_LINK):
        raise ValueError("Link sản phẩm affiliate không hợp lệ")
    if channel == "facebook":  # Instagram không bình luận tự động
        if body.get("ai_comment"):
            out["ai_comment"] = True
        if affiliate:
            out["affiliate_link"] = affiliate
    return out


def first_comment_due(post: dict, now: datetime) -> bool:
    """Bài đã lên Facebook, có yêu cầu bình luận đầu tiên, chưa bình luận được và còn lượt thử."""
    if post.get("status") != DONE or not post.get("fb_id") or post.get("channel") == "instagram":
        return False
    if not (post.get("ai_comment") or post.get("affiliate_link")):
        return False
    fc = post.get("first_comment") or {}
    if fc.get("id") or fc.get("tries", 0) >= FIRST_COMMENT_TRIES:
        return False
    return not fc.get("tried_at") or now - datetime.fromisoformat(fc["tried_at"]) >= FIRST_COMMENT_RETRY


def retry_first_comments(posts: list[dict], page_id: str) -> int:
    """Token của Page vừa đổi: cho các bài chưa bình luận đầu tiên được của Page đó thử lại từ đầu."""
    n = 0
    for p in posts:
        fc = p.get("first_comment") or {}
        if p.get("page") == page_id and fc.get("error") and not fc.get("id"):
            p["first_comment"] = {"error": fc["error"]}  # bỏ số lượt thử + giờ thử, giữ lỗi cũ để hiển thị tới khi thử lại
            n += 1
    return n


def first_comment_text(ai_text: str, link: str) -> str:
    """Câu AI viết (nếu có) rồi đến link affiliate ở dòng dưới."""
    if link:
        return f"{ai_text}\n👉 {link}" if ai_text else f"👉 Link sản phẩm: {link}"
    return ai_text


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
    for k in ("fb_id", "fb_scheduled_at", "last_check_at", "first_comment"):
        post.pop(k, None)


def label(post: dict) -> str:
    return (post.get("message") or post.get("link") or "(ảnh)")[:60]
