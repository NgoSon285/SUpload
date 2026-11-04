"""Tình trạng kết nối của từng Page: lưu ở data["health"][page_id]."""
from __future__ import annotations

from datetime import datetime, timedelta

from ..utils import parse_dt

CHECK_EVERY = timedelta(hours=6)

# Mã lỗi Graph API hay gặp -> lời giải thích + cách xử lý
FRIENDLY = {
    190: "Token đã hết hạn hoặc bị thu hồi (đổi mật khẩu Facebook, gỡ quyền App…). Lấy User Token mới và thêm lại Page trong Cài đặt.",
    102: "Phiên đăng nhập Facebook đã hết hạn. Lấy User Token mới và thêm lại Page trong Cài đặt.",
    10: "Token thiếu quyền đăng bài. Tạo lại token với quyền pages_manage_posts và chọn đúng Page.",
    200: "Token thiếu quyền đăng bài. Tạo lại token với quyền pages_manage_posts và chọn đúng Page.",
    100: "Không tìm thấy Page hoặc Page ID sai.",
    368: "Facebook đang tạm chặn Page vì đăng quá dày hoặc nội dung giống spam. Giãn lịch đăng ra.",
}
CONNECTION_CODES = set(FRIENDLY)  # lỗi do kết nối/quyền, không phải do nội dung một bài


def describe(code: int | None, message: str) -> str:
    return FRIENDLY.get(code, message)


def is_connection_error(code: int | None) -> bool:
    return code in CONNECTION_CODES


def record(data: dict, page_id: str, ok: bool, now: datetime, error: str = "", code: int | None = None) -> None:
    data.setdefault("health", {})[page_id] = {
        "ok": ok, "checked_at": now.isoformat(timespec="seconds"), "error": "" if ok else error, "code": code,
    }


def reset(data: dict, page_id: str) -> None:
    """Thông tin kết nối vừa đổi (token mới…) -> kiểm tra lại sớm."""
    data.get("health", {}).pop(page_id, None)


def due(data: dict, page: dict, now: datetime) -> bool:
    if page.get("kind") != "api":
        return False  # Page qua trình duyệt: kiểm tra phải mở trình duyệt -> chỉ kiểm tra khi người dùng bấm
    h = data.get("health", {}).get(page["id"])
    last = parse_dt(h.get("checked_at")) if h else None
    return last is None or now - last >= CHECK_EVERY


def of(data: dict, page_id: str) -> dict | None:
    return data.get("health", {}).get(page_id)
