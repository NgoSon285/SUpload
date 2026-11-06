"""Tự đăng lại bài hiệu quả: chọn bài tương tác cao đã đăng lâu, đưa lại vào lịch vào giờ tốt nhất.

- Ứng viên: bài đã đăng (có số liệu) trên Page, cũ hơn `after_days`, tương tác > 0 và >= trung bình của Page,
  chưa được đăng lại trong `after_days` ngày, file ảnh/video vẫn còn.
- Mỗi Page tối đa `per_week` bài đăng lại mỗi tuần. Giờ đăng: giờ hiệu quả nhất của Page (ngày mai), mặc định 9:00.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from ..utils import parse_dt
from .insights import engagement, summarize
from .posts import DONE


def default_config() -> dict:
    return {"enabled": False, "after_days": 30, "per_week": 1, "rewrite": False}


def clean_config(cfg) -> dict:
    base = default_config()
    cfg = cfg if isinstance(cfg, dict) else {}
    out = {**base, **{k: cfg[k] for k in base if k in cfg}}
    out["enabled"], out["rewrite"] = bool(out["enabled"]), bool(out["rewrite"])
    try:
        out["after_days"] = max(7, min(365, int(out["after_days"])))
        out["per_week"] = max(1, min(7, int(out["per_week"])))
    except (TypeError, ValueError):
        out["after_days"], out["per_week"] = base["after_days"], base["per_week"]
    return out


def _files_ok(post: dict, upload_dir: Path) -> bool:
    files = list(post.get("photos") or []) + ([post["video"]] if post.get("video") else [])
    return all((upload_dir / f).is_file() for f in files)


def candidates(posts: list[dict], page_id: str, page_of, cfg: dict, now: datetime, upload_dir: Path) -> list[dict]:
    """Bài có thể đăng lại của Page, tốt nhất trước."""
    mine = [p for p in posts if p.get("status") == DONE and p.get("stats") and page_of(p) == page_id]
    if not mine:
        return []
    avg = sum(engagement(p["stats"]) for p in mine) / len(mine)
    cutoff = now - timedelta(days=cfg["after_days"])
    out = []
    for p in mine:
        done, again = parse_dt(p.get("done_at")), parse_dt(p.get("recycled_at"))
        e = engagement(p["stats"])
        if not done or done > cutoff or e <= 0 or e < avg:
            continue
        if again and again > cutoff:
            continue
        if not (p.get("message") or p.get("photos") or p.get("video") or p.get("link")) or not _files_ok(p, upload_dir):
            continue
        out.append(p)
    return sorted(out, key=lambda p: engagement(p["stats"]), reverse=True)


def due(state: dict, cfg: dict, now: datetime) -> bool:
    last = parse_dt((state or {}).get("last_at"))
    return cfg["enabled"] and (last is None or now - last >= timedelta(days=7) / cfg["per_week"])


def slot(posts: list[dict], page_id: str, page_of, now: datetime) -> datetime:
    """Giờ hiệu quả nhất của Page (theo 90 ngày gần đây), vào ngày mai."""
    s = summarize([p for p in posts if page_of(p) == page_id], now - timedelta(days=90), page_of)
    hour = s["best_hours"][0] if s["best_hours"] else 9
    return (now + timedelta(days=1)).replace(hour=hour, minute=0, second=0, microsecond=0)


def make_post(orig: dict, when: datetime, message: str | None = None) -> dict:
    """Trường của bài đăng lại (dùng cho new_post)."""
    fields = {"message": message if message is not None else orig.get("message", ""), "link": orig.get("link", ""),
              "photos": list(orig.get("photos") or []), "scheduled_at": when.isoformat(timespec="minutes")}
    if orig.get("video"):
        fields.update(video=orig["video"], video_kind=orig.get("video_kind", "video"))
    return fields
