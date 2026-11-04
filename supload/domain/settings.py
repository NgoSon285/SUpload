from __future__ import annotations

from ..config import SECRET_KEYS, default_settings


def public_settings(s: dict) -> dict:
    """Bản cài đặt gửi cho trình duyệt: ẩn token/secret, chỉ cho biết đã lưu hay chưa."""
    out = dict(s)
    for k in SECRET_KEYS:
        out[k + "_set"] = bool(out.get(k))
        out[k] = ""
    return out


def _int(v, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return lo


def apply_update(s: dict, body: dict) -> dict:
    """Áp các trường hợp lệ từ body vào cài đặt s (sửa tại chỗ)."""
    if body.get("page_id") is not None and body["page_id"] != s.get("page_id"):
        s["page_name"] = ""  # Page khác -> tên cũ không còn đúng
    for k in default_settings():
        if k not in body:
            continue
        if k in SECRET_KEYS and not body[k]:
            continue  # để trống = giữ giá trị cũ
        s[k] = body[k]
    if s.get("method") not in ("api", "browser"):
        s["method"] = "api"
    s["min_gap"] = _int(s.get("min_gap"), 0, 86400)
    s["daily_max"] = _int(s.get("daily_max"), 0, 500)
    s["headless"] = bool(s.get("headless"))
    s["fb_schedule"] = bool(s.get("fb_schedule"))
    return s


def has_api_credentials(s: dict) -> bool:
    return bool(s.get("page_id") and s.get("page_token"))
