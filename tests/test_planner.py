"""Giới hạn an toàn (supload/domain/planner.py): logic thuần, không cần Flask hay mạng."""
import time
from datetime import datetime, timedelta

from supload.domain import planner

NOW = datetime(2026, 11, 6, 10, 0, 0)
MIN = timedelta(minutes=1)


def pend(pid, at=None, created="2026-11-06T09:00:00"):
    return {"id": pid, "status": "pending", "scheduled_at": at.isoformat(timespec="minutes") if at else None, "created_at": created}


def eff(plan, pid):
    return plan[pid].effective


def test_no_limits_keeps_desired_time():
    s = {"min_gap": 0, "daily_max": 0}
    p = planner.plan([pend("a"), pend("b", NOW + 30 * MIN)], s, NOW)
    assert eff(p, "a") == NOW and eff(p, "b") == NOW + 30 * MIN
    assert not p["a"].shifted and p["a"].reasons == ()


def test_min_gap_spaces_posts():
    s = {"min_gap": 300, "daily_max": 0}
    p = planner.plan([pend("a"), pend("b"), pend("c", NOW + 7 * MIN)], s, NOW)
    assert [eff(p, x) for x in "abc"] == [NOW, NOW + 5 * MIN, NOW + 10 * MIN]
    assert p["b"].reasons == ("gap",) and p["c"].shifted


def test_gap_respects_already_posted_and_facebook_scheduled():
    s = {"min_gap": 600, "daily_max": 0}
    posts = [
        {"id": "d", "status": "done", "done_at": (NOW - 3 * MIN).isoformat()},
        {"id": "f", "status": "scheduled", "fb_scheduled_at": (NOW + 20 * MIN).isoformat()},
        pend("a"), pend("b", NOW + 15 * MIN),
    ]
    p = planner.plan(posts, s, NOW)
    assert eff(p, "a") == NOW + 7 * MIN          # 10 phút sau bài vừa đăng
    assert eff(p, "b") == NOW + 30 * MIN         # không chen sát bài đã hẹn trên Facebook lúc +20


def test_daily_cap_moves_to_next_day_same_time():
    s = {"min_gap": 0, "daily_max": 2}
    posts = [{"id": "d", "status": "done", "done_at": (NOW - 60 * MIN).isoformat()}, pend("a"), pend("b")]
    p = planner.plan(posts, s, NOW)
    assert eff(p, "a") == NOW
    assert eff(p, "b") == NOW + timedelta(days=1)  # hôm nay đã đủ 2 bài
    assert p["b"].reasons == ("cap",)
    assert planner.describe(p["b"], s) == "đã đủ 2 bài/ngày"


def test_cap_counts_facebook_scheduled_posts_on_that_day():
    s = {"min_gap": 0, "daily_max": 1}
    tomorrow9 = datetime(2026, 11, 7, 9, 0)
    posts = [{"id": "f", "status": "scheduled", "fb_scheduled_at": tomorrow9.isoformat()}, pend("a", datetime(2026, 11, 7, 20, 0))]
    p = planner.plan(posts, s, NOW)
    assert eff(p, "a") == datetime(2026, 11, 8, 20, 0)


def test_overdue_posts_go_first():
    s = {"min_gap": 300, "daily_max": 0}
    posts = [pend("now", None, created="2026-11-06T09:59:00"), pend("late", NOW - 30 * MIN, created="2026-11-06T09:59:30")]
    p = planner.plan(posts, s, NOW)
    assert eff(p, "late") == NOW and eff(p, "now") == NOW + 5 * MIN


def test_both_limits_describe():
    s = {"min_gap": 600, "daily_max": 1}
    p = planner.plan([pend("a"), pend("b")], s, NOW)
    assert planner.describe(p["b"], s) in ("đã đủ 1 bài/ngày", "đã đủ 1 bài/ngày và giãn cách 10 phút")


def test_large_plan_is_fast():
    s = {"min_gap": 300, "daily_max": 30}
    posts = [pend(f"p{i}", NOW + i * MIN) for i in range(1500)]
    t = time.perf_counter()
    p = planner.plan(posts, s, NOW)
    assert time.perf_counter() - t < 2
    days = {}
    for slot in p.values():
        days[slot.effective.date()] = days.get(slot.effective.date(), 0) + 1
    assert max(days.values()) <= 30
    times = sorted(slot.effective for slot in p.values())
    assert all(b - a >= timedelta(seconds=300) for a, b in zip(times, times[1:]))
