"""API của ứng dụng (app.py) và luồng đăng bài nền, với Graph API giả lập."""
import json
from datetime import datetime, timedelta

import pytest

from conftest import upload


def state(client):
    return client.get("/api/state").get_json()


def add(client, **body):
    r = client.post("/api/posts", json={"message": "Bài thử", **body})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["post"]


# ---------------------------------------------------------------- cài đặt
def test_secrets_never_returned_to_browser(connected, appmod):
    connected.post("/api/settings", json={"app_secret": "SECRET_APP"})
    raw = connected.get("/api/state").get_data(as_text=True)
    assert "SECRET_PAGE_TOKEN" not in raw and "SECRET_APP" not in raw
    s = state(connected)["settings"]
    assert s["page_token_set"] is True and s["app_secret_set"] is True
    # nhưng vẫn được lưu phía máy chủ
    saved = json.loads(appmod.DATA_FILE.read_text(encoding="utf-8"))["settings"]
    assert saved["page_token"] == "SECRET_PAGE_TOKEN"


def test_blank_secret_keeps_existing(connected, appmod):
    connected.post("/api/settings", json={"page_token": "", "page_id": "111"})
    assert appmod.load()["settings"]["page_token"] == "SECRET_PAGE_TOKEN"


def test_changing_page_id_clears_stale_name(connected, appmod):
    connected.post("/api/test-connection")
    assert appmod.load()["settings"]["page_name"] == "Page Một"
    connected.post("/api/settings", json={"page_id": "222"})
    assert appmod.load()["settings"]["page_name"] == ""


def test_min_gap_is_clamped(client, appmod):
    client.post("/api/settings", json={"min_gap": -50})
    assert appmod.load()["settings"]["min_gap"] == 0


def test_page_picker_keeps_page_tokens_server_side(client, appmod):
    r = client.post("/api/fb/pages", json={"app_id": "app", "app_secret": "sec", "user_token": "short"})
    body = r.get_json()
    assert body == {"pages": [{"id": "111", "name": "Page Một"}]}  # không có access_token
    client.post("/api/fb/select-page", json={"id": "111"})
    s = appmod.load()["settings"]
    assert (s["page_id"], s["page_token"], s["page_name"]) == ("111", "PAGE_TOKEN_1", "Page Một")


def test_page_picker_requires_credentials(client):
    assert client.post("/api/fb/pages", json={"user_token": "x"}).status_code == 400


def test_test_connection(connected, client):
    r = connected.post("/api/test-connection")
    assert r.status_code == 200 and "Page Một" in r.get_json()["text"]


def test_test_connection_without_page(client):
    assert client.post("/api/test-connection").status_code == 400


# ---------------------------------------------------------------- ảnh
def test_upload_accepts_images_only(client, appmod):
    name = upload(client, "ảnh đẹp.png")
    assert (appmod.UPLOAD_DIR / name).is_file()
    assert client.get(f"/uploads/{name}").status_code == 200
    import io
    r = client.post("/api/upload", data={"files": (io.BytesIO(b"x"), "virus.exe")}, content_type="multipart/form-data")
    assert r.status_code == 400


def test_upload_filename_is_sanitized(client, appmod):
    import io
    from conftest import PNG
    r = client.post("/api/upload", data={"files": (io.BytesIO(PNG), "../../evil.png")}, content_type="multipart/form-data")
    name = r.get_json()["files"][0]
    assert "/" not in name and ".." not in name
    assert (appmod.UPLOAD_DIR / name).is_file()


# ---------------------------------------------------------------- bài viết
def test_empty_post_rejected(client):
    assert client.post("/api/posts", json={"message": "  "}).status_code == 400


def test_bad_schedule_rejected(client):
    assert client.post("/api/posts", json={"message": "x", "scheduled_at": "không phải ngày"}).status_code == 400


def test_unknown_photos_are_dropped(client):
    p = add(client, photos=["khong_ton_tai.png"])
    assert p["photos"] == []


def test_edit_pending_post(client):
    p = add(client, scheduled_at=(datetime.now() + timedelta(days=1)).isoformat(timespec="minutes"))
    r = client.put(f"/api/posts/{p['id']}", json={"message": "Đã sửa", "scheduled_at": None})
    assert r.status_code == 200
    q = state(client)["posts"][0]
    assert q["message"] == "Đã sửa" and q["scheduled_at"] is None and q["status"] == "pending"


def test_cannot_edit_done_post(connected, appmod):
    p = add(connected)
    appmod.process_one()
    r = connected.put(f"/api/posts/{p['id']}", json={"message": "x"})
    assert r.status_code == 400


def test_delete_and_clear_done(connected, appmod):
    a = add(connected)
    b = add(connected, scheduled_at=(datetime.now() + timedelta(days=1)).isoformat(timespec="minutes"))
    appmod.process_one()
    connected.post("/api/clear-done")
    ids = [p["id"] for p in state(connected)["posts"]]
    assert ids == [b["id"]]
    connected.delete(f"/api/posts/{b['id']}")
    assert state(connected)["posts"] == []
    assert a  # bài a đã được dọn


# ---------------------------------------------------------------- luồng đăng nền
def test_worker_posts_due_post_via_api(connected, appmod, graph):
    name = upload(connected)
    add(connected, message="Có ảnh", photos=[name])
    assert appmod.process_one() is True
    p = state(connected)["posts"][0]
    assert p["status"] == "done" and p["result"].startswith("id=")
    assert graph.calls[-1]["path"] == "111/photos"
    assert graph.calls[-1]["files"] == ["source"]
    assert appmod.process_one() is False  # không còn bài


def test_worker_skips_future_posts(connected, appmod, graph):
    add(connected, scheduled_at=(datetime.now() + timedelta(hours=1)).isoformat(timespec="minutes"))
    assert appmod.process_one() is False
    assert graph.calls == []


def test_worker_order_scheduled_before_newer(connected, appmod, graph):
    add(connected, message="mới", scheduled_at=None)
    add(connected, message="cũ hơn", scheduled_at=(datetime.now() - timedelta(minutes=5)).isoformat(timespec="minutes"))
    appmod.process_one()
    assert graph.calls[0]["data"]["message"] == "cũ hơn"


def test_worker_records_errors_and_retry(connected, appmod, graph):
    graph.fail_on = "LOI"
    p = add(connected, message="LOI đăng")
    appmod.process_one()
    s = state(connected)
    assert s["posts"][0]["status"] == "error" and "Lỗi giả lập" in s["posts"][0]["error"]
    assert s["log"][0]["level"] == "error"
    graph.fail_on = None
    connected.post(f"/api/posts/{p['id']}/retry")
    appmod.process_one()
    assert state(connected)["posts"][0]["status"] == "done"


def test_worker_without_connection_marks_error(client, appmod):
    add(client)
    appmod.process_one()
    p = state(client)["posts"][0]
    assert p["status"] == "error" and "FB_PAGE_ID" in p["error"]


def test_browser_mode_requires_page_url(client, appmod, monkeypatch):
    import sys, types
    fake = types.ModuleType("browser_poster")

    class PostError(RuntimeError):
        pass

    fake.PostError = PostError
    fake.post_once = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "browser_poster", fake)
    client.post("/api/settings", json={"method": "browser", "page_url": "", "min_gap": 0})
    add(client)
    appmod.process_one()
    assert "URL của Page" in state(client)["posts"][0]["error"]


def test_browser_mode_posts_with_link_appended(client, appmod, monkeypatch):
    import sys, types
    seen = {}
    fake = types.ModuleType("browser_poster")
    fake.PostError = RuntimeError
    fake.post_once = lambda url, msg, photos, headless: seen.update(url=url, msg=msg, headless=headless)
    monkeypatch.setitem(sys.modules, "browser_poster", fake)
    client.post("/api/settings", json={"method": "browser", "page_url": "https://www.facebook.com/p", "min_gap": 0, "headless": True})
    add(client, message="Xem", link="https://ex.com")
    appmod.process_one()
    assert seen == {"url": "https://www.facebook.com/p", "msg": "Xem\nhttps://ex.com", "headless": True}
    assert state(client)["posts"][0]["status"] == "done"


def test_recover_running_marks_error(client, appmod):
    p = add(client)
    appmod.update_post(p["id"], status="running")
    appmod.recover_running()
    assert state(client)["posts"][0]["status"] == "error"


# ---------------------------------------------------------------- flow
def test_flow_crud(client):
    body = {"name": "Chiến dịch", "nodes": [{"id": "a", "type": "start"}], "edges": [], "seed": "s1"}
    assert client.put("/api/flows/f1", json=body).status_code == 200
    client.put("/api/flows/f1", json={**body, "name": "Đổi tên"})
    flows = client.get("/api/flows").get_json()["flows"]
    assert len(flows) == 1 and flows[0]["name"] == "Đổi tên" and flows[0]["seed"] == "s1"
    client.delete("/api/flows/f1")
    assert client.get("/api/flows").get_json()["flows"] == []


def test_flow_run_enqueues_posts(connected, appmod):
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
def test_flow_run_validation(client, posts, msg):
    r = client.post("/api/flows/run", json={"posts": posts})
    assert r.status_code == 400 and msg in r.get_json()["error"]


def test_flow_run_is_all_or_nothing(client):
    client.post("/api/flows/run", json={"posts": [{"message": "ok"}, {"message": ""}]})
    assert state(client)["posts"] == []


def test_log_is_capped(client, appmod):
    data = appmod.load()
    for i in range(400):
        appmod.add_log(data, "info", str(i))
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


def test_run_tags_posts_and_updates_stats(connected, appmod):
    make_flow(connected)
    connected.post("/api/flows/run", json={"flow_id": "f_a", "name": "Flow A", "posts": [
        {"message": "1"}, {"message": "2", "scheduled_at": (datetime.now() + timedelta(days=1)).isoformat(timespec="minutes")}]})
    appmod.process_one()
    f = flows(connected)[0]
    assert f["last_run_count"] == 2 and f["last_run_at"]
    assert f["stats"] == {"pending": 1, "done": 1, "error": 0}
    assert all(p["flow_id"] == "f_a" for p in state(connected)["posts"])


@pytest.mark.parametrize("delete_posts,left", [(False, ["chờ", "xong", "khác"]), (True, ["xong", "khác"])])
def test_delete_flow_optionally_removes_unposted(connected, appmod, delete_posts, left):
    make_flow(connected)
    connected.post("/api/flows/run", json={"flow_id": "f_a", "name": "A", "posts": [{"message": "xong"}]})
    appmod.process_one()
    future = (datetime.now() + timedelta(days=1)).isoformat(timespec="minutes")
    connected.post("/api/flows/run", json={"flow_id": "f_a", "name": "A", "posts": [{"message": "chờ", "scheduled_at": future}]})
    add(connected, message="khác", scheduled_at=future)  # không thuộc flow
    r = connected.delete("/api/flows/f_a" + ("?delete_posts=1" if delete_posts else "")).get_json()
    assert r["removed_posts"] == (1 if delete_posts else 0)
    assert flows(connected) == []
    assert sorted(p["message"] for p in state(connected)["posts"]) == sorted(left)


def test_delete_missing_flow(client):
    assert client.delete("/api/flows/nope").status_code == 404
