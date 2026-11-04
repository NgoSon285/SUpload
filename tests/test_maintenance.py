"""Bảo trì hằng ngày: sao lưu, dọn bài cũ, xoá ảnh không dùng."""
import json
import os
import time
from datetime import datetime, timedelta

from conftest import upload


def age(path, days):
    t = time.time() - days * 86400
    os.utime(path, (t, t))


def test_backup_then_prune_old_done_posts(connected, svc):
    now = datetime.now()
    with svc.store.transaction() as data:
        data["posts"] += [
            {"id": "old", "status": "done", "done_at": (now - timedelta(days=100)).isoformat(), "photos": [], "created_at": "x"},
            {"id": "new", "status": "done", "done_at": (now - timedelta(days=5)).isoformat(), "photos": [], "created_at": "x"},
            {"id": "err", "status": "error", "done_at": (now - timedelta(days=100)).isoformat(), "photos": [], "created_at": "x"},
        ]
    r = svc.maintenance.run(now)
    assert r["removed_posts"] == 1 and r["backups"] == 1
    assert sorted(p["id"] for p in svc.store.load()["posts"]) == ["err", "new"]  # bài lỗi không bị dọn
    backup = json.loads(svc.maintenance.backups()[0].read_text(encoding="utf-8"))
    assert "old" in {p["id"] for p in backup["posts"]}  # bản sao lưu có dữ liệu TRƯỚC khi dọn


def test_keep_forever_when_zero(connected, svc):
    connected.post("/api/settings", json={"keep_done_days": 0})
    with svc.store.transaction() as data:
        data["posts"].append({"id": "old", "status": "done", "done_at": "2020-01-01T00:00:00", "photos": [], "created_at": "x"})
    assert svc.maintenance.run()["removed_posts"] == 0


def test_orphan_photos_removed_only_when_unused_and_old(connected, svc):
    used_by_post = upload(connected, "a.png")
    used_by_flow = upload(connected, "b.png")
    orphan_old = upload(connected, "c.png")
    orphan_new = upload(connected, "d.png")
    connected.post("/api/posts", json={"message": "x", "photos": [used_by_post], "scheduled_at": (datetime.now() + timedelta(days=3)).isoformat(timespec="minutes")})
    connected.put("/api/flows/f_a", json={"name": "A", "nodes": [{"id": "s", "type": "start"}, {"id": "b", "type": "batch", "data": {"photos": [used_by_flow]}}], "edges": []})
    for f in (used_by_post, used_by_flow, orphan_old):
        age(svc.config.upload_dir / f, 30)
    assert svc.maintenance.run()["removed_files"] == 1
    left = {f.name for f in svc.config.upload_dir.iterdir()}
    assert left == {used_by_post, used_by_flow, orphan_new}


def test_keeps_only_14_backups(connected, svc):
    base = datetime(2026, 1, 1)
    for i in range(20):
        svc.maintenance.run(base + timedelta(days=i))
    names = [p.name for p in svc.maintenance.backups()]
    assert len(names) == 14 and names[0] == "data-20260107-000000.json"


def test_scheduler_runs_maintenance_once_a_day(connected, svc):
    now = datetime.now()
    assert svc.scheduler.process_one(now=now) is False                      # fixture: vừa bảo trì
    later = now + timedelta(hours=25)
    assert svc.scheduler.process_one(now=later) is True  # tới hạn (kiểm tra kết nối đi trước, rồi bảo trì)
    while svc.scheduler.process_one(now=later):
        pass
    assert len(svc.maintenance.backups()) == 1
    assert svc.scheduler.process_one(now=now + timedelta(hours=26)) is False


def test_maintenance_api_and_state(connected, svc):
    r = connected.post("/api/maintenance/run").get_json()
    assert r["backups"] == 1 and r["last_backup"].startswith("data-")
    m = connected.get("/api/state").get_json()["maintenance"]
    assert m["backups"] == 1 and m["last_backup"] == r["last_backup"]
