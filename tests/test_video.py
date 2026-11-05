"""Video thường & Reels: tải lên, đăng ngay, hẹn giờ trên Facebook, đối soát."""
import io
from datetime import datetime, timedelta

from supload.integrations import facebook

MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


def upload_video(client, name="clip.mp4"):
    r = client.post("/api/upload", data={"files": (io.BytesIO(MP4), name)}, content_type="multipart/form-data")
    assert r.status_code == 200, r.get_json()
    return r.get_json()["files"][0]


def state(client):
    return client.get("/api/state").get_json()


def test_video_upload_allowed_but_not_other_files(client):
    upload_video(client)
    r = client.post("/api/upload", data={"files": (io.BytesIO(b"x"), "a.exe")}, content_type="multipart/form-data")
    assert r.status_code == 400


def test_video_post_published_via_graph_host(connected, svc, graph):
    v = upload_video(connected)
    connected.post("/api/posts", json={"message": "Clip mới", "link": "https://x.vn", "video": v, "video_kind": "video"})
    svc.scheduler.process_one()
    call = graph.by("POST", "/videos")[0]
    assert call["base"] == facebook.GRAPH and "graph-video" not in call["base"] and call["files"] == ["source"]
    assert call["data"]["description"] == "Clip mới\nhttps://x.vn"  # link gộp vào mô tả
    p = state(connected)["posts"][0]
    assert p["status"] == "done" and p["video"] == v


def test_reel_three_phase_upload(connected, svc, graph):
    v = upload_video(connected, "reel.mp4")
    connected.post("/api/posts", json={"message": "Reel", "video": v, "video_kind": "reel"})
    svc.scheduler.process_one()
    start, upload, finish = graph.calls
    assert start["path"] == "111/video_reels" and start["data"]["upload_phase"] == "start"
    vid = finish["data"]["video_id"]
    assert upload["base"] == f"https://rupload.facebook.com/video-upload/v23.0/{vid}" and upload["path"] == "" and upload["data"]["_bytes"] == len(MP4)
    assert upload["headers"]["file_size"] == str(len(MP4)) and upload["headers"]["Authorization"].startswith("OAuth ")
    assert finish["data"] == {"upload_phase": "finish", "video_id": vid, "description": "Reel", "video_state": "PUBLISHED"}
    assert state(connected)["posts"][0]["result"].startswith(f"id={vid}")


def test_scheduled_reel_handed_to_facebook_and_reconciled(connected, svc, graph):
    v = upload_video(connected)
    when = (datetime.now() + timedelta(hours=3)).replace(second=0, microsecond=0)
    connected.post("/api/posts", json={"message": "R", "video": v, "video_kind": "reel", "scheduled_at": when.isoformat(timespec="minutes")})
    svc.scheduler.process_one()
    finish = graph.calls[-1]["data"]
    assert finish["video_state"] == "SCHEDULED" and int(finish["scheduled_publish_time"]) == int(when.timestamp())
    p = state(connected)["posts"][0]
    assert p["status"] == "scheduled"
    graph.published.add(p["fb_id"])
    svc.scheduler.process_one(now=when + timedelta(minutes=3))
    assert graph.calls[-1]["params"]["fields"] == "published"  # video dùng trường published
    assert state(connected)["posts"][0]["status"] == "done"


def test_scheduled_video_has_schedule_fields(connected, svc, graph):
    v = upload_video(connected)
    when = datetime.now() + timedelta(hours=5)
    connected.post("/api/posts", json={"message": "V", "video": v, "scheduled_at": when.isoformat(timespec="minutes")})
    svc.scheduler.process_one()
    d = graph.by("POST", "/videos")[0]["data"]
    assert d["published"] == "false" and d["scheduled_publish_time"]


def test_video_and_photos_together_rejected(connected):
    from conftest import upload
    v, img = upload_video(connected), upload(connected)
    r = connected.post("/api/posts", json={"message": "x", "video": v, "photos": [img]})
    assert r.status_code == 400 and "ảnh hoặc video" in r.get_json()["error"]


def test_unknown_video_rejected(connected):
    r = connected.post("/api/posts", json={"message": "x", "video": "khong-co.mp4"})
    assert r.status_code == 400


def test_reel_via_browser_page_gives_clear_error(client, svc, graph, monkeypatch):
    import sys
    import types
    import supload.integrations as integrations
    fake = types.ModuleType("supload.integrations.browser")
    fake.PostError = RuntimeError
    fake.configure = lambda *a: None
    fake.post_once = lambda *a: None
    monkeypatch.setitem(sys.modules, "supload.integrations.browser", fake)
    monkeypatch.setattr(integrations, "browser", fake, raising=False)
    from conftest import add_browser_page
    client.post("/api/settings", json={"min_gap": 0})
    add_browser_page(client)
    v = upload_video(client)
    client.post("/api/posts", json={"message": "x", "video": v, "video_kind": "reel"})
    svc.scheduler.process_one()
    assert "Reels chỉ đăng được qua Graph API" in state(client)["posts"][0]["error"]


def test_editing_video_post_to_text_drops_video(connected, svc):
    v = upload_video(connected)
    when = (datetime.now() + timedelta(days=2)).isoformat(timespec="minutes")
    pid = connected.post("/api/posts", json={"message": "x", "video": v, "scheduled_at": when}).get_json()["post"]["id"]
    connected.put(f"/api/posts/{pid}", json={"message": "chỉ chữ", "scheduled_at": when})
    p = state(connected)["posts"][0]
    assert "video" not in p and p["message"] == "chỉ chữ"
