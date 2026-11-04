"""Hẹn giờ trên Facebook + giới hạn an toàn trong luồng nền (supload/services)."""
from datetime import datetime, timedelta

import pytest


def iso(dt):
    return dt.isoformat(timespec="minutes")


def state(client):
    return client.get("/api/state").get_json()


def post(client, pid=None):
    posts = state(client)["posts"]
    return posts[0] if pid is None else next(p for p in posts if p["id"] == pid)


def add(client, **body):
    r = client.post("/api/posts", json={"message": "Bài thử", **body})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["post"]


def handed_off(client, svc, when):
    p = add(client, scheduled_at=iso(when))
    assert svc.scheduler.process_one() is True
    q = post(client, p["id"])
    assert q["status"] == "scheduled", q
    return q


# ---------------------------------------------------------------- giao cho Facebook
def test_hand_off_stores_facebook_id_and_time(connected, svc, graph):
    when = (datetime.now() + timedelta(hours=3)).replace(second=0, microsecond=0)
    q = handed_off(connected, svc, when)
    assert q["fb_id"] == "111_1" and q["fb_scheduled_at"] == when.isoformat()
    assert int(graph.by("POST", "/feed")[0]["data"]["scheduled_publish_time"]) == int(when.timestamp())
    assert "Đã hẹn trên Facebook" in state(connected)["log"][0]["text"]


def test_too_soon_is_published_locally_when_due(connected, svc, graph):
    now = datetime.now()
    p = add(connected, scheduled_at=iso(now + timedelta(minutes=5)))
    assert svc.scheduler.process_one() is False                       # < 12 phút: không giao cho Facebook
    assert svc.scheduler.process_one(now=now + timedelta(minutes=6)) is True
    assert post(connected, p["id"])["status"] == "done"
    assert "scheduled_publish_time" not in graph.calls[-1]["data"]


def test_beyond_30_days_waits_then_hands_off(connected, svc, graph, monkeypatch):
    from supload.integrations import facebook
    now = datetime.now()
    p = add(connected, scheduled_at=iso(now + timedelta(days=40)))
    assert svc.scheduler.process_one() is False
    later = now + timedelta(days=11)
    monkeypatch.setattr(facebook.time, "time", lambda: later.timestamp())  # đồng hồ của lớp Facebook cũng tiến 11 ngày
    assert svc.scheduler.process_one(now=later) is True  # đã vào khung 30 ngày
    assert post(connected, p["id"])["status"] == "scheduled"


def test_photos_for_scheduled_post_are_temporary(connected, svc, graph):
    from conftest import upload
    name = upload(connected)
    add(connected, message="có ảnh", photos=[name], scheduled_at=iso(datetime.now() + timedelta(hours=2)))
    svc.scheduler.process_one()
    photo = graph.by("POST", "/photos")[0]
    assert photo["data"]["temporary"] == "true" and photo["data"]["published"] == "false"


def test_hand_off_failure_marks_error(connected, svc, graph):
    graph.fail_on = "LOI"
    p = add(connected, message="LOI", scheduled_at=iso(datetime.now() + timedelta(hours=2)))
    svc.scheduler.process_one()
    q = post(connected, p["id"])
    assert q["status"] == "error" and "Không hẹn được trên Facebook" in q["error"]


# ---------------------------------------------------------------- đối soát
def test_reconcile_marks_done_when_facebook_published(connected, svc, graph):
    when = (datetime.now() + timedelta(hours=1)).replace(second=0, microsecond=0)
    q = handed_off(connected, svc, when)
    graph.published.add(q["fb_id"])
    assert svc.scheduler.process_one(now=when + timedelta(minutes=3)) is True
    r = post(connected, q["id"])
    assert r["status"] == "done" and r["done_at"] == when.isoformat()


def test_reconcile_waits_then_errors_if_never_published(connected, svc, graph):
    when = (datetime.now() + timedelta(hours=1)).replace(second=0, microsecond=0)
    q = handed_off(connected, svc, when)
    assert svc.scheduler.process_one(now=when + timedelta(minutes=3)) is True
    assert post(connected, q["id"])["status"] == "scheduled"           # chưa lên, chờ thêm
    assert svc.scheduler.process_one(now=when + timedelta(minutes=4)) is False  # chưa tới lượt kiểm tra lại
    assert svc.scheduler.process_one(now=when + timedelta(hours=2)) is True
    r = post(connected, q["id"])
    assert r["status"] == "error" and "quá giờ hẹn" in r["error"]


def test_reconcile_detects_post_deleted_on_facebook(connected, svc, graph):
    when = (datetime.now() + timedelta(hours=1)).replace(second=0, microsecond=0)
    q = handed_off(connected, svc, when)
    graph.missing.add(q["fb_id"])
    svc.scheduler.process_one(now=when + timedelta(minutes=3))
    assert "bị xoá trên Facebook" in post(connected, q["id"])["error"]


# ---------------------------------------------------------------- sửa / xoá bài đã hẹn
def test_edit_scheduled_cancels_on_facebook_and_reschedules(connected, svc, graph):
    q = handed_off(connected, svc, datetime.now() + timedelta(hours=2))
    r = connected.put(f"/api/posts/{q['id']}", json={"message": "Đã sửa", "scheduled_at": iso(datetime.now() + timedelta(hours=5))})
    assert r.status_code == 200
    assert graph.by("DELETE")[0]["path"] == q["fb_id"]
    p = post(connected, q["id"])
    assert p["status"] == "pending" and "fb_id" not in p
    svc.scheduler.process_one()
    p = post(connected, q["id"])
    assert p["status"] == "scheduled" and p["fb_id"] != q["fb_id"]
    assert graph.by("POST", "/feed")[-1]["data"]["message"] == "Đã sửa"


def test_edit_scheduled_refused_when_cancel_fails(connected, svc, graph):
    q = handed_off(connected, svc, datetime.now() + timedelta(hours=2))
    graph.fail_delete = True
    r = connected.put(f"/api/posts/{q['id']}", json={"message": "Đã sửa"})
    assert r.status_code == 502 and "Không huỷ được" in r.get_json()["error"]
    assert post(connected, q["id"])["status"] == "scheduled"  # không đổi -> tránh đăng trùng


def test_delete_scheduled_cancels_on_facebook(connected, svc, graph):
    q = handed_off(connected, svc, datetime.now() + timedelta(hours=2))
    assert connected.delete(f"/api/posts/{q['id']}").status_code == 200
    assert graph.by("DELETE")[0]["path"] == q["fb_id"] and state(connected)["posts"] == []


def test_delete_scheduled_cancel_failure_and_force(connected, svc, graph):
    q = handed_off(connected, svc, datetime.now() + timedelta(hours=2))
    graph.fail_delete = True
    r = connected.delete(f"/api/posts/{q['id']}")
    assert r.status_code == 502 and r.get_json()["can_force"] is True
    assert len(state(connected)["posts"]) == 1
    assert connected.delete(f"/api/posts/{q['id']}?force=1").status_code == 200
    assert state(connected)["posts"] == []


def test_delete_already_gone_on_facebook_is_ok(connected, svc, graph):
    q = handed_off(connected, svc, datetime.now() + timedelta(hours=2))
    graph.missing.add(q["fb_id"])
    assert connected.delete(f"/api/posts/{q['id']}").status_code == 200


def test_delete_flow_cancels_its_scheduled_posts(connected, svc, graph):
    connected.put("/api/flows/f_a", json={"name": "A", "nodes": [{"id": "s", "type": "start"}], "edges": []})
    connected.post("/api/flows/run", json={"flow_id": "f_a", "name": "A", "posts": [{"message": "x", "scheduled_at": iso(datetime.now() + timedelta(hours=2))}]})
    svc.scheduler.process_one()
    r = connected.delete("/api/flows/f_a?delete_posts=1").get_json()
    assert r["removed_posts"] == 1 and len(graph.by("DELETE")) == 1


def test_retry_does_not_touch_scheduled(connected, svc, graph):
    q = handed_off(connected, svc, datetime.now() + timedelta(hours=2))
    connected.post(f"/api/posts/{q['id']}/retry")
    assert post(connected, q["id"])["status"] == "scheduled"


# ---------------------------------------------------------------- giới hạn an toàn trong luồng nền
def test_daily_cap_pushes_extra_post_to_tomorrow_on_facebook(connected, svc, graph):
    connected.post("/api/settings", json={"daily_max": 1})
    a = add(connected, message="A")
    b = add(connected, message="B")
    svc.scheduler.process_one()                                  # A đăng ngay
    svc.scheduler.process_one()                                  # B: hôm nay đã đủ -> hẹn ngày mai trên Facebook
    pb = post(connected, b["id"])
    assert post(connected, a["id"])["status"] == "done"
    assert pb["status"] == "scheduled"
    assert datetime.fromisoformat(pb["fb_scheduled_at"]).date() == (datetime.now() + timedelta(days=1)).date()


def test_daily_cap_keeps_post_pending_with_reason(connected, svc, graph):
    connected.post("/api/settings", json={"daily_max": 1, "fb_schedule": False})
    add(connected, message="A")
    b = add(connected, message="B")
    svc.scheduler.process_one()
    assert svc.scheduler.process_one() is False
    pb = post(connected, b["id"])
    assert pb["status"] == "pending" and pb["shift_reason"] == "đã đủ 1 bài/ngày"
    assert state(connected)["limits"] == {"daily_max": 1, "min_gap": 0, "today": 1}


def test_min_gap_applies_to_api_mode(connected, svc, graph):
    connected.post("/api/settings", json={"min_gap": 600})
    add(connected, message="A")
    b = add(connected, message="B")
    now = datetime.now()
    svc.scheduler.process_one(now=now)
    assert svc.scheduler.process_one(now=now) is False        # còn 10 phút < 12 phút: chờ, không giao Facebook
    assert "giãn cách 10 phút" in post(connected, b["id"])["shift_reason"]
    assert svc.scheduler.process_one(now=now + timedelta(minutes=11)) is True
    assert post(connected, b["id"])["status"] == "done"


def test_plan_preview_reports_shifts(connected):
    connected.post("/api/settings", json={"daily_max": 2, "min_gap": 0})
    r = connected.post("/api/plan/preview", json={"posts": [{"scheduled_at": None}] * 3}).get_json()
    assert r["shifted"] == 1 and r["by_cap"] == 1 and r["items"][2]["reason"] == "đã đủ 2 bài/ngày"


@pytest.mark.parametrize("body,expect", [({"daily_max": -5}, 0), ({"daily_max": 9999}, 500), ({"daily_max": "abc"}, 0)])
def test_limit_settings_are_validated(client, svc, body, expect):
    client.post("/api/settings", json=body)
    assert svc.store.load()["settings"]["daily_max"] == expect
