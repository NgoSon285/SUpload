"""API (supload/api) và luồng đăng bài nền (supload/services), với Graph API giả lập."""
import json
from datetime import datetime, timedelta

import pytest

from conftest import upload
from supload.storage import add_log


def state(client):
    return client.get("/api/state").get_json()


def add(client, **body):
    r = client.post("/api/posts", json={"message": "Bài thử", **body})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["post"]


# ---------------------------------------------------------------- cài đặt
def test_secrets_never_returned_to_browser(connected, svc):
    connected.post("/api/settings", json={"app_secret": "SECRET_APP"})
    raw = connected.get("/api/state").get_data(as_text=True) + connected.get("/api/pages").get_data(as_text=True)
    assert "SECRET_PAGE_TOKEN" not in raw and "SECRET_APP" not in raw
    st = state(connected)
    assert st["settings"]["app_secret_set"] is True and st["pages"][0]["token_set"] is True
    # nhưng vẫn được lưu phía máy chủ
    saved = json.loads(svc.config.data_file.read_text(encoding="utf-8"))
    assert saved["pages"][0]["token"] == "SECRET_PAGE_TOKEN"


def test_blank_token_keeps_existing(connected, svc):
    pid = state(connected)["pages"][0]["id"]
    connected.put(f"/api/pages/{pid}", json={"token": "", "name": "Tên mới"})
    page = svc.store.load()["pages"][0]
    assert page["token"] == "SECRET_PAGE_TOKEN" and page["name"] == "Tên mới"


def test_connection_test_updates_page_name(connected, svc):
    connected.post("/api/test-connection")
    assert svc.store.load()["pages"][0]["name"] == "Page Một"


def test_min_gap_is_clamped(client, svc):
    client.post("/api/settings", json={"min_gap": -50})
    assert svc.store.load()["settings"]["min_gap"] == 0


def test_page_picker_adds_page_and_keeps_token_server_side(client, svc):
    r = client.post("/api/fb/pages", json={"app_id": "app", "app_secret": "sec", "user_token": "short"})
    assert r.get_json() == {"pages": [{"id": "111", "name": "Page Một"}]}  # không có access_token
    client.post("/api/fb/select-page", json={"id": "111"})
    client.post("/api/fb/select-page", json={"id": "111"})  # chọn lại -> cập nhật, không nhân đôi
    data = svc.store.load()
    assert len(data["pages"]) == 1
    p = data["pages"][0]
    assert (p["kind"], p["fb_page_id"], p["token"], p["name"]) == ("api", "111", "PAGE_TOKEN_1", "Page Một")
    assert data["settings"]["default_page"] == p["id"]


def test_page_picker_requires_credentials(client):
    assert client.post("/api/fb/pages", json={"user_token": "x"}).status_code == 400


def test_test_connection(connected, client):
    r = connected.post("/api/test-connection")
    assert r.status_code == 200 and "Page Một" in r.get_json()["text"]


def test_test_connection_without_page(client):
    assert client.post("/api/test-connection").status_code == 400


# ---------------------------------------------------------------- ảnh
def test_upload_accepts_images_only(client, svc):
    name = upload(client, "ảnh đẹp.png")
    assert (svc.config.upload_dir / name).is_file()
    assert client.get(f"/uploads/{name}").status_code == 200
    import io
    r = client.post("/api/upload", data={"files": (io.BytesIO(b"x"), "virus.exe")}, content_type="multipart/form-data")
    assert r.status_code == 400


def test_upload_filename_is_sanitized(client, svc):
    import io
    from conftest import PNG
    r = client.post("/api/upload", data={"files": (io.BytesIO(PNG), "../../evil.png")}, content_type="multipart/form-data")
    name = r.get_json()["files"][0]
    assert "/" not in name and ".." not in name
    assert (svc.config.upload_dir / name).is_file()


# ---------------------------------------------------------------- bài viết
def test_empty_post_rejected(connected):
    assert connected.post("/api/posts", json={"message": "  "}).status_code == 400


def test_bad_schedule_rejected(connected):
    assert connected.post("/api/posts", json={"message": "x", "scheduled_at": "không phải ngày"}).status_code == 400


def test_unknown_photos_are_dropped(connected):
    p = add(connected, photos=["khong_ton_tai.png"])
    assert p["photos"] == []


def test_edit_pending_post(connected):
    p = add(connected, scheduled_at=(datetime.now() + timedelta(days=1)).isoformat(timespec="minutes"))
    r = connected.put(f"/api/posts/{p['id']}", json={"message": "Đã sửa", "scheduled_at": None})
    assert r.status_code == 200
    q = state(connected)["posts"][0]
    assert q["message"] == "Đã sửa" and q["scheduled_at"] is None and q["status"] == "pending"


def test_cannot_edit_done_post(connected, svc):
    p = add(connected)
    svc.scheduler.process_one()
    r = connected.put(f"/api/posts/{p['id']}", json={"message": "x"})
    assert r.status_code == 400


def test_delete_and_clear_done(connected, svc):
    a = add(connected)
    b = add(connected, scheduled_at=(datetime.now() + timedelta(days=1)).isoformat(timespec="minutes"))
    svc.scheduler.process_one()
    connected.post("/api/clear-done")
    ids = [p["id"] for p in state(connected)["posts"]]
    assert ids == [b["id"]]
    connected.delete(f"/api/posts/{b['id']}")
    assert state(connected)["posts"] == []
    assert a  # bài a đã được dọn


# ---------------------------------------------------------------- luồng đăng nền
def test_worker_posts_due_post_via_api(connected, svc, graph):
    name = upload(connected)
    add(connected, message="Có ảnh", photos=[name])
    assert svc.scheduler.process_one() is True
    p = state(connected)["posts"][0]
    assert p["status"] == "done" and p["result"].startswith("id=")
    assert graph.calls[-1]["path"] == "111/photos"
    assert graph.calls[-1]["files"] == ["source"]
    assert svc.scheduler.process_one() is False  # không còn bài


def test_future_post_is_handed_off_to_facebook(connected, svc, graph):
    add(connected, scheduled_at=(datetime.now() + timedelta(hours=1)).isoformat(timespec="minutes"))
    assert svc.scheduler.process_one() is True
    feed = graph.by("POST", "/feed")[0]
    assert feed["data"]["published"] == "false" and feed["data"]["scheduled_publish_time"]
    p = state(connected)["posts"][0]
    assert p["status"] == "scheduled" and p["fb_id"] == "111_1"


def test_future_post_waits_locally_when_fb_scheduling_off(connected, svc, graph):
    connected.post("/api/settings", json={"fb_schedule": False})
    add(connected, scheduled_at=(datetime.now() + timedelta(hours=1)).isoformat(timespec="minutes"))
    assert svc.scheduler.process_one() is False
    assert graph.calls == []


def test_worker_order_scheduled_before_newer(connected, svc, graph):
    add(connected, message="mới", scheduled_at=None)
    add(connected, message="cũ hơn", scheduled_at=(datetime.now() - timedelta(minutes=5)).isoformat(timespec="minutes"))
    svc.scheduler.process_one()
    assert graph.calls[0]["data"]["message"] == "cũ hơn"


def test_worker_records_errors_and_retry(connected, svc, graph):
    graph.fail_on = "LOI"
    p = add(connected, message="LOI đăng")
    svc.scheduler.process_one()
    s = state(connected)
    assert s["posts"][0]["status"] == "error" and "Lỗi giả lập" in s["posts"][0]["error"]
    assert s["log"][0]["level"] == "error"
    graph.fail_on = None
    connected.post(f"/api/posts/{p['id']}/retry")
    svc.scheduler.process_one()
    assert state(connected)["posts"][0]["status"] == "done"


def test_cannot_queue_post_without_any_page(client, svc):
    r = client.post("/api/posts", json={"message": "x"})
    assert r.status_code == 400 and "Chưa kết nối Page" in r.get_json()["error"]
    assert svc.store.load()["posts"] == []


@pytest.fixture
def fake_browser(monkeypatch):
    """Thay module trình duyệt (Playwright) bằng bản giả ghi lại lời gọi."""
    import sys
    import types
    import supload.integrations as integrations

    seen = {}
    fake = types.ModuleType("supload.integrations.browser")

    class PostError(RuntimeError):
        pass

    fake.PostError = PostError
    fake.configure = lambda profile, shots: seen.update(profile=profile)
    fake.post_once = lambda url, msg, photos, headless: seen.update(url=url, msg=msg, headless=headless)
    monkeypatch.setitem(sys.modules, "supload.integrations.browser", fake)
    monkeypatch.setattr(integrations, "browser", fake, raising=False)
    return seen


def test_browser_page_requires_facebook_url(client):
    r = client.post("/api/pages", json={"kind": "browser", "url": "https://example.com/x"})
    assert r.status_code == 400 and "facebook.com" in r.get_json()["error"]


def test_browser_mode_posts_with_link_appended(client, svc, fake_browser):
    from conftest import add_browser_page
    client.post("/api/settings", json={"min_gap": 0, "headless": True})
    add_browser_page(client)
    add(client, message="Xem", link="https://ex.com")
    svc.scheduler.process_one()
    assert {k: fake_browser[k] for k in ("url", "msg", "headless")} == {"url": "https://www.facebook.com/p", "msg": "Xem\nhttps://ex.com", "headless": True}
    assert fake_browser["profile"] == svc.config.profile_dir  # dùng đúng thư mục phiên đăng nhập
    assert state(client)["posts"][0]["status"] == "done"


def test_browser_page_never_hands_off_to_facebook(client, svc, fake_browser, graph):
    from conftest import add_browser_page
    client.post("/api/settings", json={"min_gap": 0})
    add_browser_page(client)
    add(client, scheduled_at=(datetime.now() + timedelta(hours=1)).isoformat(timespec="minutes"))
    assert svc.scheduler.process_one() is False
    assert graph.calls == []


def test_recover_running_marks_error(connected, svc):
    p = add(connected)
    svc.store.update_post(p["id"], status="running")
    svc.scheduler.recover_running()
    assert state(connected)["posts"][0]["status"] == "error"


# ---------------------------------------------------------------- flow
def test_flow_crud(client):
    body = {"name": "Chiến dịch", "nodes": [{"id": "a", "type": "start"}], "edges": [], "seed": "s1"}
    assert client.put("/api/flows/f1", json=body).status_code == 200
    client.put("/api/flows/f1", json={**body, "name": "Đổi tên"})
    flows = client.get("/api/flows").get_json()["flows"]
    assert len(flows) == 1 and flows[0]["name"] == "Đổi tên" and flows[0]["seed"] == "s1"
    client.delete("/api/flows/f1")
    assert client.get("/api/flows").get_json()["flows"] == []


def test_flow_run_enqueues_posts(connected, svc):
    future = (datetime.now() + timedelta(days=1)).isoformat(timespec="minutes")
    past = (datetime.now() - timedelta(hours=1)).isoformat(timespec="minutes")
    r = connected.post("/api/flows/run", json={"name": "CD", "posts": [
        {"message": "1", "scheduled_at": past},
        {"message": "2", "scheduled_at": future},
    ]})
    assert r.get_json() == {"count": 2}
    posts = {p["message"]: p for p in state(connected)["posts"]}
    assert posts["1"]["scheduled_at"] is None  # giờ đã qua -> đăng ngay
    assert posts["2"]["scheduled_at"] == future and posts["2"]["flow"] == "CD"


@pytest.mark.parametrize("posts,msg", [([], "chưa có"), ([{"message": ""}], "Bài #1"), ([{"message": "x"}] * 501, "500")])
def test_flow_run_validation(connected, posts, msg):
    r = connected.post("/api/flows/run", json={"posts": posts})
    assert r.status_code == 400 and msg in r.get_json()["error"]


def test_flow_run_is_all_or_nothing(connected):
    connected.post("/api/flows/run", json={"posts": [{"message": "ok"}, {"message": ""}]})
    assert state(connected)["posts"] == []


def test_log_is_capped(client, svc):
    data = svc.store.load()
    for i in range(400):
        add_log(data, "info", str(i))
    assert len(data["log"]) == 300 and data["log"][0]["text"] == "399"


# ---------------------------------------------------------------- quản lý flow
START = [{"id": "s", "type": "start", "position": {"x": 0, "y": 0}, "data": {}}]


def make_flow(client, fid="f_a", name="Flow A", **extra):
    r = client.put(f"/api/flows/{fid}", json={"name": name, "nodes": START, "edges": [], **extra})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["flow"]


def flows(client):
    return client.get("/api/flows").get_json()["flows"]


def test_many_flows_sorted_by_last_update(client):
    make_flow(client, "f_1", "Một")
    make_flow(client, "f_2", "Hai")
    make_flow(client, "f_3", "Ba")
    client.put("/api/flows/f_1", json={"name": "Một (sửa)"})
    assert [f["name"] for f in flows(client)] == ["Một (sửa)", "Ba", "Hai"]


def test_partial_update_keeps_graph_and_metadata(client):
    f = make_flow(client, description="mô tả", seed="s1")
    client.put("/api/flows/f_a", json={"name": "Tên mới"})
    g = flows(client)[0]
    assert g["name"] == "Tên mới" and g["description"] == "mô tả" and g["seed"] == "s1"
    assert g["nodes"] == START and g["created_at"] == f["created_at"]


def test_blank_name_gets_default(client):
    make_flow(client, name="   ")
    assert flows(client)[0]["name"] == "Flow chưa đặt tên"


@pytest.mark.parametrize("fid,body", [
    ("../x", {"nodes": START}),
    ("f_ok", {"nodes": "không phải list"}),
    ("f_ok", {"nodes": [{"type": "post"}]}),
    ("f_ok", {"nodes": [{"id": str(i), "type": "post"} for i in range(301)]}),
])
def test_invalid_flows_rejected(client, fid, body):
    assert client.put(f"/api/flows/{fid}", json=body).status_code in (400, 404)


def test_duplicate_flow(client):
    make_flow(client, description="d")
    client.post("/api/flows/run", json={"flow_id": "f_a", "name": "Flow A", "posts": [{"message": "x"}]})
    r = client.post("/api/flows/f_a/duplicate").get_json()["flow"]
    assert r["id"] != "f_a" and r["name"] == "Flow A (bản sao)" and r["description"] == "d"
    assert r["nodes"] == START and r["last_run_at"] is None and r["last_run_count"] == 0
    assert len(flows(client)) == 2
    assert client.post("/api/flows/nope/duplicate").status_code == 404


def test_import_export_roundtrip(client):
    exported = {"format": "supload-flow", "version": 1, "name": "Nhập", "description": "x", "nodes": START, "edges": [], "seed": "z"}
    f = client.post("/api/flows/import", json={"flow": exported}).get_json()["flow"]
    assert f["id"].startswith("f_") and f["name"] == "Nhập" and f["nodes"] == START
    # nhập lại lần nữa -> flow riêng, không ghi đè
    client.post("/api/flows/import", json={"flow": exported})
    assert len(flows(client)) == 2


def test_import_requires_start_node(client):
    r = client.post("/api/flows/import", json={"flow": {"name": "x", "nodes": [{"id": "p", "type": "post"}], "edges": []}})
    assert r.status_code == 400 and "Bắt đầu" in r.get_json()["error"]


def test_run_tags_posts_and_updates_stats(connected, svc):
    make_flow(connected)
    connected.post("/api/flows/run", json={"flow_id": "f_a", "name": "Flow A", "posts": [
        {"message": "1"}, {"message": "2", "scheduled_at": (datetime.now() + timedelta(days=1)).isoformat(timespec="minutes")}]})
    svc.scheduler.process_one()
    f = flows(connected)[0]
    assert f["last_run_count"] == 2 and f["last_run_at"]
    assert f["stats"] == {"pending": 1, "done": 1, "error": 0}
    assert all(p["flow_id"] == "f_a" for p in state(connected)["posts"])


@pytest.mark.parametrize("delete_posts,left", [(False, ["chờ", "xong", "khác"]), (True, ["xong", "khác"])])
def test_delete_flow_optionally_removes_unposted(connected, svc, delete_posts, left):
    make_flow(connected)
    connected.post("/api/flows/run", json={"flow_id": "f_a", "name": "A", "posts": [{"message": "xong"}]})
    svc.scheduler.process_one()
    future = (datetime.now() + timedelta(days=1)).isoformat(timespec="minutes")
    connected.post("/api/flows/run", json={"flow_id": "f_a", "name": "A", "posts": [{"message": "chờ", "scheduled_at": future}]})
    add(connected, message="khác", scheduled_at=future)  # không thuộc flow
    r = connected.delete("/api/flows/f_a" + ("?delete_posts=1" if delete_posts else "")).get_json()
    assert r["removed_posts"] == (1 if delete_posts else 0)
    assert flows(connected) == []
    assert sorted(p["message"] for p in state(connected)["posts"]) == sorted(left)


def test_delete_missing_flow(client):
    assert client.delete("/api/flows/nope").status_code == 404
