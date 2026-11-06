"""Tự đăng lại bài hiệu quả."""
from datetime import datetime, timedelta

from conftest import upload


def done_post(pid, page, days_ago, reactions, hour=20, **kw):
    t = (datetime.now() - timedelta(days=days_ago)).replace(hour=hour, minute=0, second=0, microsecond=0)
    return {"id": pid, "status": "done", "message": f"Bài {pid}", "photos": [], "link": "", "page": page,
            "done_at": t.isoformat(timespec="seconds"), "created_at": t.isoformat(timespec="seconds"),
            "stats": {"reactions": reactions, "comments": 0, "shares": 0, "fetched_at": t.isoformat()}, **kw}


def seed(svc):
    with svc.store.transaction() as data:
        pid = data["pages"][0]["id"]
        data["posts"] += [done_post("top", pid, 40, 50), done_post("low", pid, 40, 2), done_post("new", pid, 3, 99),
                          done_post("top2", pid, 45, 45), done_post("h1", pid, 50, 30, hour=20), done_post("zero", pid, 60, 0)]
    return pid


def test_overview_previews_best_old_post(connected, svc):
    seed(svc)
    r = connected.get("/api/recycle").get_json()
    assert r["config"]["enabled"] is False and r["pages"][0]["next"]["id"] == "top"  # "new" quá mới, "low" dưới trung bình


def test_job_runs_weekly_when_enabled_and_schedules_at_best_hour(connected, svc):
    pid = seed(svc)
    assert svc.scheduler.process_one() is False  # chưa bật
    connected.put("/api/recycle/config", json={"enabled": True, "after_days": 30, "per_week": 2})
    assert svc.scheduler.process_one() is True
    data = svc.store.load()
    new = [p for p in data["posts"] if p.get("source") == "recycle"]
    assert len(new) == 1 and new[0]["recycled_from"] == "top" and new[0]["message"] == "Bài top" and new[0]["page"] == pid
    when = datetime.fromisoformat(new[0]["scheduled_at"])
    assert when.hour == 20 and when.date() == (datetime.now() + timedelta(days=1)).date()  # giờ hiệu quả nhất
    assert next(p for p in data["posts"] if p["id"] == "top")["recycled_at"]
    while svc.scheduler.process_one():  # (bài mới được giao cho Facebook hẹn giờ)
        pass
    assert len([p for p in svc.store.load()["posts"] if p.get("source") == "recycle"]) == 1  # chưa tới lượt kế (3,5 ngày)
    later = datetime.now() + timedelta(days=4)
    while svc.scheduler.process_one(now=later):  # (bài đăng lại đầu tiên cũng tới giờ đăng)
        pass
    data = svc.store.load()
    assert [p["recycled_from"] for p in data["posts"] if p.get("source") == "recycle"][:2] == ["top", "top2"]


def test_run_now_and_nothing_eligible(connected, svc):
    pid = seed(svc)
    r = connected.post("/api/recycle/run", json={"page": pid}).get_json()
    assert r["post"]["recycled_from"] == "top"
    with svc.store.transaction() as data:
        data["posts"] = [p for p in data["posts"] if p.get("source") != "recycle" and p["id"] in ("new", "zero")]
    r = connected.post("/api/recycle/run", json={"page": pid})
    assert r.status_code == 400 and "đủ điều kiện" in r.get_json()["error"]
    assert connected.post("/api/recycle/run", json={"page": "x"}).status_code == 404


def test_missing_media_is_skipped_and_ai_rewrite_used(connected, svc, monkeypatch):
    from supload.integrations import ai
    pid = seed(svc)
    photo = upload(connected, "a.png")
    with svc.store.transaction() as data:
        for p in data["posts"]:
            if p["id"] == "top":
                p["photos"] = ["da-xoa.png"]
            if p["id"] == "top2":
                p["photos"] = [photo]
    connected.post("/api/settings", json={"openai_api_key": "k"})
    monkeypatch.setattr(ai, "suggest", lambda *a, **k: ["Bản viết lại ✨"])
    connected.put("/api/recycle/config", json={"enabled": True, "rewrite": True})
    svc.scheduler.process_one()
    new = next(p for p in svc.store.load()["posts"] if p.get("source") == "recycle")
    assert new["recycled_from"] == "top2" and new["photos"] == [photo] and new["message"] == "Bản viết lại ✨"


def test_config_is_validated(connected, svc):
    r = connected.put("/api/recycle/config", json={"enabled": 1, "after_days": 1, "per_week": 99}).get_json()
    assert r["config"] == {"enabled": True, "after_days": 7, "per_week": 7, "rewrite": False}
