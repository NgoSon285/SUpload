"""Tổng hợp chỉ số tương tác: tổng quan, bài nổi bật, khung giờ hiệu quả."""
from __future__ import annotations

from datetime import datetime, timedelta

from ..utils import parse_dt
from .posts import DONE

TRACK_DAYS = 14                     # theo dõi chỉ số của bài trong 14 ngày sau khi đăng
REFRESH_EVERY = timedelta(hours=6)
FIRST_AFTER = timedelta(minutes=10)  # chờ bài có tương tác rồi mới lấy lần đầu
DOW = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]


def engagement(stats: dict | None) -> int:
    if not stats:
        return 0
    return int(stats.get("reactions", 0)) + int(stats.get("comments", 0)) + int(stats.get("shares", 0))


def needs_refresh(post: dict, now: datetime) -> bool:
    if post.get("status") != DONE or not post.get("fb_id"):
        return False
    done = parse_dt(post.get("done_at"))
    if not done or now - done > timedelta(days=TRACK_DAYS) or now - done < FIRST_AFTER:
        return False
    fetched = parse_dt((post.get("stats") or {}).get("fetched_at"))
    return fetched is None or now - fetched >= REFRESH_EVERY


def summarize(posts: list[dict], since: datetime, page_of=lambda p: p.get("page")) -> dict:
    """Số liệu cho trang Thống kê (chỉ bài đã đăng có chỉ số, từ `since`)."""
    rows = []
    for p in posts:
        t = parse_dt(p.get("done_at"))
        if p.get("status") == DONE and p.get("stats") and t and t >= since:
            rows.append((p, t))
    n = len(rows)
    tot = {k: sum(int((p["stats"] or {}).get(k) or 0) for p, _ in rows) for k in ("reactions", "comments", "shares")}
    reach_rows = [p["stats"]["reach"] for p, _ in rows if p["stats"].get("reach") is not None]
    by_hour = [{"key": h, "label": f"{h}h", "posts": 0, "engagement": 0} for h in range(24)]
    by_dow = [{"key": i, "label": DOW[i], "posts": 0, "engagement": 0} for i in range(7)]
    for p, t in rows:
        e = engagement(p["stats"])
        for bucket in (by_hour[t.hour], by_dow[t.weekday()]):
            bucket["posts"] += 1
            bucket["engagement"] += e
    for b in by_hour + by_dow:
        b["avg"] = round(b["engagement"] / b["posts"], 1) if b["posts"] else None
    overall = sum(engagement(p["stats"]) for p, _ in rows) / n if n else 0
    # chỉ gợi ý khung giờ đủ dữ liệu (>= 2 bài) VÀ tốt hơn mức trung bình chung
    best = sorted([b for b in by_hour if b["posts"] >= 2 and b["avg"] >= overall], key=lambda b: b["avg"], reverse=True)[:3]
    top = sorted(rows, key=lambda r: engagement(r[0]["stats"]), reverse=True)[:10]
    return {
        "posts": n,
        "totals": {**tot, "engagement": sum(tot.values()), "reach": sum(reach_rows) if reach_rows else None},
        "avg_engagement": round(overall, 1),
        "reach_missing": n > 0 and not reach_rows,
        "by_hour": by_hour, "by_dow": by_dow,
        "best_hours": [b["key"] for b in best],
        "top": [{"id": p["id"], "message": p.get("message", ""), "photos": p.get("photos", []), "video": p.get("video"),
                 "done_at": p["done_at"], "page": page_of(p), "stats": p["stats"], "engagement": engagement(p["stats"])} for p, _ in top],
        "updated_at": max((p["stats"].get("fetched_at") or "" for p, _ in rows), default=None),
    }
