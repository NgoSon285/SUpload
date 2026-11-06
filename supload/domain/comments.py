"""Bình luận trên Page: quy tắc tự động (ẩn SĐT, ẩn từ cấm, trả lời theo từ khoá) và lưu trữ.

Luồng nền định kỳ hỏi Facebook bình luận mới của các bài gần đây (services/comments.py),
mỗi bình luận mới được `decide()` xem cần ẩn / trả lời công khai / nhắn riêng hay không.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta

from ..utils import parse_dt

MAX_KEEP = 3000                  # số bình luận lưu tối đa
MAX_RULES = 30
PRIVATE_REPLY_WINDOW = timedelta(days=7)  # Facebook chỉ cho nhắn riêng trong 7 ngày sau bình luận

# SĐT Việt Nam: 0xxxxxxxxx / +84xxxxxxxxx / 84xxxxxxxxx, cho phép dấu cách . - giữa các số
PHONE_RE = re.compile(r"(?<![\d])(?:\+?84|0)(?:[\s.\-]?\d){9}(?![\d])")
UNHIDE_CHOICES = (0, 1, 6, 24, 72, 168)   # giờ; 0 = ẩn vĩnh viễn


def default_config() -> dict:
    return {"enabled": False, "inbox": True, "hide_phone": True, "unhide_after_h": 0, "hide_words": "", "rules": [],
            "poll_minutes": 3, "days": 7}


def norm(text: str) -> str:
    """Chữ thường, bỏ dấu tiếng Việt, gộp khoảng trắng: so khớp từ khoá không phân biệt dấu."""
    text = unicodedata.normalize("NFD", str(text or "").replace("đ", "d").replace("Đ", "D"))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"\s+", " ", text).strip()


def split_words(value) -> list[str]:
    items = value if isinstance(value, list) else re.split(r"[,\n;]+", str(value or ""))
    return [w.strip() for w in items if isinstance(w, str) and w.strip()][:100]


def has_phone(text: str) -> bool:
    return bool(PHONE_RE.search(str(text or "")))


def contains_any(text: str, words: list[str]) -> str | None:
    """Từ khoá đầu tiên xuất hiện trong text (khớp nguyên từ, không phân biệt dấu/hoa thường)."""
    t = f" {re.sub(r'[^a-z0-9 ]+', ' ', norm(text))} "
    for w in words:
        k = re.sub(r"[^a-z0-9 ]+", " ", norm(w)).strip()
        if k and f" {k} " in re.sub(r"\s+", " ", t):
            return w
    return None


def clean_config(cfg) -> dict:
    """Kiểm tra cấu hình người dùng gửi lên."""
    base = default_config()
    cfg = cfg if isinstance(cfg, dict) else {}
    out = {**base, **{k: cfg[k] for k in base if k in cfg}}
    out["enabled"] = bool(out["enabled"])
    out["inbox"] = bool(out["inbox"])
    out["hide_phone"] = bool(out["hide_phone"])
    try:
        out["unhide_after_h"] = int(out["unhide_after_h"])
    except (TypeError, ValueError):
        out["unhide_after_h"] = 0
    if out["unhide_after_h"] not in UNHIDE_CHOICES:
        out["unhide_after_h"] = 0
    out["hide_words"] = ", ".join(split_words(out["hide_words"]))
    try:
        out["poll_minutes"] = max(1, min(60, int(out["poll_minutes"])))
        out["days"] = max(1, min(30, int(out["days"])))
    except (TypeError, ValueError):
        out["poll_minutes"], out["days"] = base["poll_minutes"], base["days"]
    rules = []
    for r in (out["rules"] if isinstance(out["rules"], list) else [])[:MAX_RULES]:
        if not isinstance(r, dict):
            continue
        words = split_words(r.get("keywords"))
        reply = str(r.get("reply") or "").strip()[:2000]
        private = str(r.get("private") or "").strip()[:2000]
        if words and (reply or private):
            rules.append({"keywords": ", ".join(words), "reply": reply, "private": private,
                          "enabled": r.get("enabled", True) is not False})
    out["rules"] = rules
    return out


def fill(template: str, name: str) -> str:
    """{ten} -> tên người bình luận; {a|b|c} -> chọn ngẫu nhiên."""
    import random

    text = template.replace("{ten}", name or "bạn").replace("{name}", name or "bạn")
    return re.sub(r"\{([^{}]*\|[^{}]*)\}", lambda m: random.choice(m.group(1).split("|")), text)


def decide(comment: dict, cfg: dict, now: datetime) -> dict:
    """Việc cần làm với MỘT bình luận mới: {hide, hide_reason, unhide_at, reply, private, rule}."""
    out = {"hide": False, "hide_reason": "", "unhide_at": None, "reply": "", "private": "", "rule": None}
    text = comment.get("message") or ""
    if not cfg.get("enabled") or not text.strip():
        return out
    if cfg.get("hide_phone") and has_phone(text):
        out.update(hide=True, hide_reason="Có số điện thoại")
    else:
        bad = contains_any(text, split_words(cfg.get("hide_words")))
        if bad:
            out.update(hide=True, hide_reason=f"Chứa từ “{bad}”")
    if out["hide"] and cfg.get("unhide_after_h"):
        out["unhide_at"] = (now + timedelta(hours=cfg["unhide_after_h"])).isoformat(timespec="seconds")
    name = ((comment.get("from") or {}).get("name") or "").split(" ")[-1]
    for i, r in enumerate(cfg.get("rules") or []):
        if r.get("enabled", True) and contains_any(text, split_words(r["keywords"])):
            out["rule"] = i
            out["reply"] = fill(r.get("reply", ""), name).strip()
            created = parse_dt(comment.get("created_time"))
            if r.get("private") and comment.get("can_reply_privately", True) is not False and \
                    (created is None or now - created <= PRIVATE_REPLY_WINDOW):
                out["private"] = fill(r["private"], name).strip()
            break
    return out


def record(c: dict, page_id: str, post: dict) -> dict:
    """Bản lưu của một bình luận lấy từ Graph API."""
    frm = c.get("from") or {}
    return {
        "id": c["id"], "page": page_id, "post_id": post.get("id"), "post_text": (post.get("message") or "")[:200],
        "post_url": post.get("permalink_url") or "", "url": c.get("permalink_url") or "",
        "from_id": frm.get("id", ""), "from_name": frm.get("name") or "Người dùng Facebook",
        "message": c.get("message") or "", "created_time": c.get("created_time") or "",
        "hidden": bool(c.get("is_hidden")), "can_hide": c.get("can_hide", True) is not False,
        "can_reply_privately": c.get("can_reply_privately", True) is not False,
        "hide_reason": "", "unhide_at": None, "replies": [], "private_sent": False, "seen": False, "errors": [],
    }


def trim(items: list[dict]) -> list[dict]:
    items.sort(key=lambda c: c.get("created_time") or "", reverse=True)
    return items[:MAX_KEEP]
