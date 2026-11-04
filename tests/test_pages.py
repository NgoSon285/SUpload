"""Nhiều Page: chuyển dữ liệu cũ, quản lý Page, đăng đúng Page, giới hạn theo từng Page."""
import json
from datetime import datetime, timedelta

import pytest

from supload import Config, create_app


def state(client):
    return client.get("/api/state").get_json()


def add_api_page(client, fb_id, name):
    r = client.post("/api/pages", json={"kind": "api", "fb_page_id": fb_id, "token": f"TOK_{fb_id}", "name": name})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["page"]["id"]


@pytest.fixture
def two_pages(client):
    client.post("/api/settings", json={"min_gap": 0, "daily_max": 0})
    a = add_api_page(client, "111", "Tiệm Bánh")
    b = add_api_page(client, "222", "Quán Cà Phê")
    return a, b


# ---------------------------------------------------------------- chuyển dữ liệu cũ
def test_legacy_single_page_data_is_migrated(tmp_path, graph):
    legacy = {
        "settings": {"method": "api", "page_id": "111", "page_token": "OLD_TOKEN", "page_name": "Page cũ", "page_url": "", "min_gap": 0, "daily_max": 0},
        "posts": [
            {"id": "p1", "status": "pending", "message": "chờ", "photos": [], "created_at": "2026-01-01T00:00:00"},
            {"id": "p2", "status": "done", "message": "xong", "photos": [], "created_at": "2026-01-01T00:00:00", "done_at": "2026-01-01T00:00:00"},
        ],
    }
    (tmp_path / "data.json").write_text(json.dumps(legacy), encoding="utf-8")
    svc = create_app(Config(base_dir=tmp_path)).extensions["supload"]
    data = svc.store.load()
    (page,) = data["pages"]
    assert (page["kind"], page["fb_page_id"], page["token"], page["name"]) == ("api", "111", "OLD_TOKEN", "Page cũ")
    assert data["settings"]["default_page"] == page["id"]
    assert "page_token" not in data["settings"] and "method" not in data["settings"]
    assert data["posts"][0]["page"] == page["id"] and "page" not in data["posts"][1]
    svc.scheduler.process_one()  # bài cũ vẫn đăng được
    assert graph.by("POST")[0]["path"] == "111/feed"


def test_legacy_browser_method_becomes_default(tmp_path, graph):
    legacy = {"settings": {"method": "browser", "page_id": "111", "page_token": "T", "page_url": "https://www.facebook.com/tiembanh"}}
    (tmp_path / "data.json").write_text(json.dumps(legacy), encoding="utf-8")
    data = create_app(Config(base_dir=tmp_path)).extensions["supload"].store.load()
    kinds = {p["kind"]: p for p in data["pages"]}
    assert set(kinds) == {"api", "browser"}
    assert data["settings"]["default_page"] == kinds["browser"]["id"] and kinds["browser"]["name"] == "tiembanh"


def test_env_page_is_picked_up_on_first_run(tmp_path, graph, monkeypatch):
    monkeypatch.setenv("FB_PAGE_ID", "999")
    monkeypatch.setenv("FB_PAGE_TOKEN", "ENV_TOKEN")
    data = create_app(Config(base_dir=tmp_path)).extensions["supload"].store.load()
    assert data["pages"][0]["fb_page_id"] == "999" and data["pages"][0]["token"] == "ENV_TOKEN"


# ---------------------------------------------------------------- quản lý Page
def test_first_page_becomes_default_and_can_switch(client, two_pages):
    a, b = two_pages
    pages = {p["id"]: p for p in state(client)["pages"]}
    assert pages[a]["default"] and not pages[b]["default"]
    client.post(f"/api/pages/{b}/default")
    assert {p["id"]: p["default"] for p in state(client)["pages"]} == {a: False, b: True}


def test_duplicate_api_page_rejected(client, two_pages):
    r = client.post("/api/pages", json={"kind": "api", "fb_page_id": "111", "token": "x"})
    assert r.status_code == 400 and "đã được kết nối" in r.get_json()["error"]


@pytest.mark.parametrize("body", [{"kind": "api", "fb_page_id": "1"}, {"kind": "api", "token": "t"}, {"kind": "zzz"}, {"kind": "browser", "url": ""}])
def test_invalid_page_rejected(client, body):
    assert client.post("/api/pages", json=body).status_code == 400


def test_delete_page_blocked_while_it_has_waiting_posts(client, two_pages, svc):
    a, b = two_pages
    client.post("/api/posts", json={"message": "x", "page": b, "scheduled_at": (datetime.now() + timedelta(days=3)).isoformat(timespec="minutes")})
    r = client.delete(f"/api/pages/{b}")
    assert r.status_code == 409 and "còn 1 bài chưa đăng" in r.get_json()["error"]
    client.delete(f"/api/posts/{state(client)['posts'][0]['id']}")
    assert client.delete(f"/api/pages/{b}").status_code == 200
    assert [p["id"] for p in state(client)["pages"]] == [a]


def test_deleting_default_page_promotes_another(client, two_pages, svc):
    a, b = two_pages
    client.delete(f"/api/pages/{a}")
    assert svc.store.load()["settings"]["default_page"] == b


def test_test_page_uses_its_own_token(client, two_pages, graph):
    a, b = two_pages
    assert client.post(f"/api/pages/{b}/test").status_code == 200
    assert graph.calls[-1]["path"] == "222"


# ---------------------------------------------------------------- đăng đúng Page
def test_posts_go_to_their_page(client, two_pages, svc, graph):
    a, b = two_pages
    client.post("/api/posts", json={"message": "bánh", "page": a})
    client.post("/api/posts", json={"message": "cà phê", "page": b})
    client.post("/api/posts", json={"message": "mặc định"})
    while svc.scheduler.process_one():
        pass
    sent = {c["data"]["message"]: c["path"] for c in graph.by("POST", "/feed")}
    assert sent == {"bánh": "111/feed", "cà phê": "222/feed", "mặc định": "111/feed"}
    assert all(p["page"] in (a, b) for p in state(client)["posts"])


def test_unknown_page_rejected(client, two_pages):
    r = client.post("/api/posts", json={"message": "x", "page": "pg_khong_co"})
    assert r.status_code == 400 and "Không tìm thấy Page" in r.get_json()["error"]


def test_editing_scheduled_post_to_another_page_moves_it_on_facebook(client, two_pages, svc, graph):
    a, b = two_pages
    when = (datetime.now() + timedelta(hours=3)).isoformat(timespec="minutes")
    pid = client.post("/api/posts", json={"message": "x", "page": a, "scheduled_at": when}).get_json()["post"]["id"]
    svc.scheduler.process_one()
    fb_old = state(client)["posts"][0]["fb_id"]
    client.put(f"/api/posts/{pid}", json={"message": "x", "page": b, "scheduled_at": when})
    assert graph.by("DELETE")[0]["path"] == fb_old  # huỷ trên Page cũ
    svc.scheduler.process_one()
    assert graph.by("POST", "/feed")[-1]["path"] == "222/feed"


# ---------------------------------------------------------------- giới hạn theo từng Page
def test_daily_cap_is_per_page(client, two_pages, svc, graph):
    a, b = two_pages
    client.post("/api/settings", json={"daily_max": 1, "fb_schedule": False})
    for page in (a, b, a):
        client.post("/api/posts", json={"message": f"bài {page}", "page": page})
    while svc.scheduler.process_one():
        pass
    paths = [c["path"] for c in graph.by("POST", "/feed")]
    assert sorted(paths) == ["111/feed", "222/feed"]  # mỗi Page 1 bài hôm nay
    st = state(client)
    waiting = [p for p in st["posts"] if p["status"] == "pending"]
    assert len(waiting) == 1 and waiting[0]["page"] == a and "đã đủ 1 bài/ngày" in waiting[0]["shift_reason"]
    assert st["limits"]["per_page"] == {a: 1, b: 1}


def test_preview_respects_page(client, two_pages):
    a, b = two_pages
    client.post("/api/settings", json={"daily_max": 1})
    client.post("/api/posts", json={"message": "x", "page": a})
    r = client.post("/api/plan/preview", json={"page": b, "posts": [{"scheduled_at": None}]}).get_json()
    assert r["shifted"] == 0  # Page b còn trống
    r = client.post("/api/plan/preview", json={"page": a, "posts": [{"scheduled_at": None}]}).get_json()
    assert r["shifted"] == 1


# ---------------------------------------------------------------- flow gắn Page
def test_flow_targets_its_page(client, two_pages, svc, graph):
    a, b = two_pages
    client.put("/api/flows/f_x", json={"name": "CF", "page": b, "nodes": [{"id": "s", "type": "start"}], "edges": []})
    assert client.get("/api/flows").get_json()["flows"][0]["page"] == b
    client.post("/api/flows/run", json={"flow_id": "f_x", "name": "CF", "posts": [{"message": "m"}]})
    assert state(client)["posts"][0]["page"] == b


def test_flow_with_unknown_page_rejected(client, two_pages):
    r = client.put("/api/flows/f_x", json={"name": "CF", "page": "pg_nope", "nodes": [], "edges": []})
    assert r.status_code == 400


def test_deleting_page_resets_flows_to_default(client, two_pages, svc):
    a, b = two_pages
    client.put("/api/flows/f_x", json={"name": "CF", "page": b, "nodes": [], "edges": []})
    client.delete(f"/api/pages/{b}")
    assert svc.store.load()["flows"][0]["page"] == ""
