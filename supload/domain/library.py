"""Thư viện nội dung: đoạn văn dùng lại (bộ hashtag, chữ ký, mẫu bài)."""
from __future__ import annotations

from ..utils import new_id, now_iso

KINDS = {"hashtag": "Bộ hashtag", "signature": "Chữ ký", "template": "Mẫu bài"}
MAX_ITEMS = 500


def clean(body: dict, old: dict | None = None) -> dict:
    """Kiểm tra & tạo/cập nhật một mục. Ném ValueError nếu không hợp lệ."""
    item = dict(old or {"id": new_id("lib_", 8), "created_at": now_iso(), "used": 0})
    kind = body.get("kind", item.get("kind"))
    if kind not in KINDS:
        raise ValueError("Loại không hợp lệ")
    name = str(body.get("name", item.get("name", ""))).strip()[:80]
    content = str(body.get("content", item.get("content", ""))).strip()
    if not content:
        raise ValueError("Nội dung đang trống")
    if len(content) > 5000:
        raise ValueError("Nội dung quá dài (tối đa 5.000 ký tự)")
    item.update(kind=kind, name=name or content.splitlines()[0][:40], content=content, updated_at=now_iso())
    return item
