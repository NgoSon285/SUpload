"""Tình trạng kết nối từng Page: kiểm tra định kỳ, cập nhật theo kết quả đăng, thông báo dễ hiểu."""
from datetime import datetime, timedelta

from supload.domain import health
from supload.integrations import facebook


def page_health(client):
    return {p["name"]: p["health"] for p in client.get("/api/state").get_json()["pages"]}


def add_page(client, fb_id="111", name="Tiệm Bánh"):
    return client.post("/api/pages", json={"kind": "api", "fb_page_id": fb_id, "token": "t", "name": name}).get_json()["page"]["id"]


def test_new_api_page_is_checked_by_worker(client, svc, graph):
    add_page(client)
    assert page_health(client)["Tiệm Bánh"] is None
    assert svc.scheduler.process_one() is True
    h = page_health(client)["Tiệm Bánh"]
    assert h["ok"] is True and graph.calls[-1]["path"] == "111"
    assert svc.scheduler.process_one() is False                                   # 6 giờ sau mới kiểm tra lại
    assert svc.scheduler.process_one(now=datetime.now() + timedelta(hours=7)) is True


def test_expired_token_is_reported_in_plain_words(client, svc, graph):
    add_page(client)

    def expired(method, path, **kw):
        raise facebook.FBError("[190] Error validating access token", 190)
    import pytest

    mp = pytest.MonkeyPatch()
    mp.setattr(facebook, "call", expired)
    try:
        svc.scheduler.process_one()
    finally:
        mp.undo()
    h = page_health(client)["Tiệm Bánh"]
    assert h["ok"] is False and h["code"] == 190 and "Token đã hết hạn" in h["error"]
    log = client.get("/api/state").get_json()["log"][0]
    assert log["level"] == "error" and "mất kết nối" in log["text"]


def test_browser_pages_are_not_checked_periodically(client, svc, graph):
    client.post("/api/pages", json={"kind": "browser", "url": "https://www.facebook.com/x"})
    assert svc.scheduler.process_one() is False
    assert graph.calls == []


def test_publish_failure_with_connection_error_marks_page_unhealthy(connected, svc, monkeypatch):
    def denied(method, path, **kw):
        raise facebook.FBError("[200] Permissions error", 200)
    monkeypatch.setattr(facebook, "call", denied)
    connected.post("/api/posts", json={"message": "x"})
    svc.scheduler.process_one()
    post = connected.get("/api/state").get_json()["posts"][0]
    assert "thiếu quyền đăng bài" in post["error"]
    h = list(page_health(connected).values())[0]
    assert h["ok"] is False and h["code"] == 200


def test_content_error_does_not_mark_page_unhealthy(connected, svc, graph):
    graph.fail_on = "LOI"
    connected.post("/api/posts", json={"message": "LOI"})
    svc.scheduler.process_one()
    assert list(page_health(connected).values())[0]["ok"] is True


def test_successful_post_restores_health(connected, svc, graph):
    with svc.store.transaction() as data:
        health.record(data, data["pages"][0]["id"], False, datetime.now(), "hỏng", 190)
    connected.post("/api/posts", json={"message": "x"})
    svc.scheduler.process_one()
    assert list(page_health(connected).values())[0]["ok"] is True


def test_manual_test_records_health_and_new_token_resets_it(connected, svc, graph):
    pid = connected.get("/api/state").get_json()["pages"][0]["id"]
    assert connected.post(f"/api/pages/{pid}/test").status_code == 200
    assert list(page_health(connected).values())[0]["ok"] is True
    connected.put(f"/api/pages/{pid}", json={"token": "TOKEN_MOI"})
    assert list(page_health(connected).values())[0] is None  # sẽ được kiểm tra lại


def test_friendly_messages():
    assert "Token đã hết hạn" in health.describe(190, "x")
    assert health.describe(9999, "nguyên văn") == "nguyên văn"
    assert health.is_connection_error(190) and not health.is_connection_error(1)
