"""Giới hạn an toàn: tính thời điểm đăng THỰC TẾ của từng bài đang chờ.

Quy tắc (áp cho cả cách API và Trình duyệt):
  - Giãn cách tối thiểu `min_gap` giây giữa 2 bài bất kỳ.
  - Tối đa `daily_max` bài mỗi ngày (theo ngày lịch của máy).
Bài vi phạm được dời sang thời điểm hợp lệ kế tiếp; bài đã đăng / đã hẹn trên Facebook / đang đăng
được coi là cố định và tính vào giới hạn.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..utils import parse_dt
from .posts import DONE, PENDING, RUNNING, SCHEDULED

MAX_STEPS = 5000


@dataclass
class Slot:
    effective: datetime
    desired: datetime
    reasons: tuple[str, ...]

    @property
    def shifted(self) -> bool:
        return self.effective - self.desired > timedelta(seconds=1)


def limits(settings: dict) -> tuple[timedelta, int]:
    return timedelta(seconds=max(0, int(settings.get("min_gap") or 0))), max(0, int(settings.get("daily_max") or 0))


def occupied(posts: list[dict], now: datetime) -> list[datetime]:
    """Các thời điểm đã chiếm chỗ (không dời được)."""
    out = []
    for p in posts:
        st = p.get("status")
        if st == DONE and p.get("done_at"):
            out.append(parse_dt(p["done_at"]))
        elif st == SCHEDULED and p.get("fb_scheduled_at"):
            out.append(parse_dt(p["fb_scheduled_at"]))
        elif st == RUNNING:
            out.append(now)
    return sorted(out)


def desired_time(post: dict, now: datetime) -> datetime:
    d = parse_dt(post.get("scheduled_at"))
    return max(d, now) if d else now


def plan(posts: list[dict], settings: dict, now: datetime | None = None) -> dict[str, Slot]:
    """Trả về {post_id: Slot} cho mọi bài đang chờ."""
    now = (now or datetime.now()).replace(microsecond=0)
    gap, cap = limits(settings)
    taken = occupied(posts, now)
    per_day: dict = {}
    for t in taken:
        per_day[t.date()] = per_day.get(t.date(), 0) + 1

    pending = [p for p in posts if p.get("status") == PENDING]
    # cùng thời điểm mong muốn -> bài có giờ hẹn gốc sớm hơn (đã quá hạn lâu hơn) đi trước
    pending.sort(key=lambda p: (desired_time(p, now), p.get("scheduled_at") or p.get("created_at") or "", p.get("created_at") or ""))
    result: dict[str, Slot] = {}
    for p in pending:
        want = desired_time(p, now)
        t, reasons = want, set()
        for _ in range(MAX_STEPS):
            moved = False
            if gap:
                i = bisect.bisect_left(taken, t - gap + timedelta(microseconds=1))
                clash = [s for s in taken[i:i + 50] if abs(s - t) < gap]
                if clash:
                    t, moved = max(clash) + gap, True
                    reasons.add("gap")
            if cap and per_day.get(t.date(), 0) >= cap:
                nxt = datetime.combine(t.date() + timedelta(days=1), want.time())
                t, moved = max(nxt, datetime.combine(t.date() + timedelta(days=1), datetime.min.time())), True
                reasons.add("cap")
            if not moved:
                break
        bisect.insort(taken, t)
        per_day[t.date()] = per_day.get(t.date(), 0) + 1
        slot = Slot(effective=t, desired=want, reasons=tuple(sorted(reasons)))
        if not slot.shifted:
            slot.reasons = ()
        result[p["id"]] = slot
    return result


def describe(slot: Slot, settings: dict) -> str:
    gap, cap = limits(settings)
    parts = []
    if "cap" in slot.reasons:
        parts.append(f"đã đủ {cap} bài/ngày")
    if "gap" in slot.reasons:
        parts.append(f"giãn cách {int(gap.total_seconds() // 60)} phút")
    return " và ".join(parts)
