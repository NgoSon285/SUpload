from __future__ import annotations

from ..config import SECRET_KEYS, default_settings


def public_settings(s: dict) -> dict:
    """Bản cài đặt gửi cho trình duyệt: ẩn token/secret, chỉ cho biết đã lưu hay chưa."""
    import os

    out = dict(s)
    for k in SECRET_KEYS:
        v = str(out.get(k) or "")
        out[k + "_set"] = bool(v)
        out[k + "_tail"] = v[-4:] if len(v) >= 12 else ""  # 4 ký tự cuối để nhận ra key nào; key ngắn thì không lộ
        out[k] = ""
    from ..integrations.ai import PROVIDERS
    out["ai_env_keys"] = {p: bool(os.getenv(c["env"])) for p, c in PROVIDERS.items()}
    return out


def _int(v, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return lo


def apply_update(s: dict, body: dict) -> dict:
    """Áp các trường hợp lệ từ body vào cài đặt s (sửa tại chỗ)."""
    for k in default_settings():
        if k == "default_page":
            continue  # đổi Page mặc định qua /api/pages/<id>/default
        if k not in body:
            continue
        if k in SECRET_KEYS and not body[k]:
            continue  # để trống = giữ giá trị cũ
        s[k] = body[k]
    s["min_gap"] = _int(s.get("min_gap"), 0, 86400)
    s["daily_max"] = _int(s.get("daily_max"), 0, 500)
    s["keep_done_days"] = _int(s.get("keep_done_days"), 0, 3650)
    from ..integrations.ai import clean_base_url, clean_model, clean_provider
    s["ai_provider"] = clean_provider(s.get("ai_provider"))
    s["ai_model"] = clean_model(s.get("ai_model"), s["ai_provider"])
    s["ai_base_url"] = clean_base_url(s.get("ai_base_url"))
    from .comments import clean_config
    s["comments"] = clean_config(s.get("comments"))
    from .recycle import clean_config as clean_recycle
    s["recycle"] = clean_recycle(s.get("recycle"))
    s["headless"] = bool(s.get("headless"))
    s["fb_schedule"] = bool(s.get("fb_schedule"))
    return s


def has_api_credentials(page: dict | None) -> bool:
    return bool(page and page.get("kind") == "api" and page.get("fb_page_id") and page.get("token"))
