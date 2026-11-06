"""Đăng chéo Instagram (Graph API giả lập)."""
from datetime import datetime, timedelta

import io

from conftest import mark_healthy, upload
from supload.integrations import facebook

MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


def link_instagram(connected, graph, svc):
    graph.instagram = {"id": "ig1", "username": "tiembanh"}
    pid = svc.store.load()["pages"][0]["id"]
    r = connected.post(f"/api/pages/{pid}/test").get_json()
    assert "@tiembanh" in r["text"]
    return pid


def test_check_detects_linked_instagram_and_health_job_too(connected, graph, svc):
    pid = link_instagram(connected, graph, svc)
    assert svc.store.load()["pages"][0]["instagram"] == {"id": "ig1", "username": "tiembanh"}
    graph.instagram = None
    with svc.store.transaction() as data:
        data["health"][pid]["checked_at"] = "2020-01-01T00:00:00"
    svc.scheduler.process_one()
    assert svc.store.load()["pages"][0]["instagram"] is None  # đã gỡ liên kết


def test_also_instagram_creates_second_post_with_own_limits(connected, graph, svc):
    link_instagram(connected, graph, svc)
    photo = upload(connected, "a.png")
    r = connected.post("/api/posts", json={"message": "Bánh mới #banh", "photos": [photo], "also_instagram": True})
    assert r.status_code == 200
    posts = svc.store.load()["posts"]
    assert sorted(p.get("channel", "facebook") for p in posts) == ["facebook", "instagram"]
    while svc.scheduler.process_one():
        pass
    paths = [c["path"] for c in graph.calls if c["method"] == "POST"]
    assert "ig1/media" in paths and "ig1/media_publish" in paths and "111/photos" in paths
    media = next(c for c in graph.calls if c["path"] == "ig1/media")
    assert media["data"]["image_url"].startswith("https://fbcdn.test/") and media["data"]["caption"] == "Bánh mới #banh"
    assert media["data"]["image_url"].endswith(".jpg") and "_s" not in media["data"]["image_url"]  # ảnh lớn nhất
    assert [c for c in graph.calls if c["method"] == "DELETE"]  # xoá ảnh tạm trên Facebook
    ig = next(p for p in svc.store.load()["posts"] if p.get("channel") == "instagram")
    assert ig["status"] == "done" and "instagram.com/p/" in ig["result"]


def test_instagram_carousel_and_reel(connected, graph, svc):
    link_instagram(connected, graph, svc)
    photos = [upload(connected, f"{i}.png") for i in range(3)]
    connected.post("/api/posts", json={"message": "Album", "photos": photos, "channel": "instagram"})
    svc.scheduler.process_one()
    media = [c["data"] for c in graph.calls if c["path"] == "ig1/media"]
    assert sum(1 for m in media if m.get("is_carousel_item") == "true") == 3
    parent = next(m for m in media if m.get("media_type") == "CAROUSEL")
    assert len(parent["children"].split(",")) == 3 and parent["caption"] == "Album"

    r = connected.post("/api/upload", data={"files": (io.BytesIO(MP4), "r.mp4")}, content_type="multipart/form-data")
    graph.calls.clear()
    connected.post("/api/posts", json={"message": "Reel", "video": r.get_json()["files"][0], "video_kind": "reel", "channel": "instagram"})
    svc.scheduler.process_one()
    start = next(c for c in graph.calls if c["path"] == "ig1/media")
    assert start["data"]["media_type"] == "REELS" and start["data"]["upload_type"] == "resumable"
    up = next(c for c in graph.calls if c["data"].get("_bytes"))
    assert up["base"].startswith("https://rupload.facebook.com/ig-api-upload/") and up["headers"]["file_size"] == str(len(MP4))


def test_instagram_rules_and_errors(connected, graph, svc):
    r = connected.post("/api/posts", json={"message": "chỉ chữ", "channel": "instagram"})
    assert r.status_code == 400 and "ít nhất một ảnh" in r.get_json()["error"]
    photo = upload(connected, "a.png")
    r = connected.post("/api/posts", json={"message": "x", "photos": [photo], "also_instagram": True})
    assert r.status_code == 400 and "chưa liên kết" in r.get_json()["error"]
    link_instagram(connected, graph, svc)
    graph.ig_status = "ERROR"
    connected.post("/api/posts", json={"message": "x", "photos": [photo], "channel": "instagram"})
    svc.scheduler.process_one()
    p = svc.store.load()["posts"][0]
    assert p["status"] == "error" and "Instagram xử lý media bị lỗi" in p["error"]


def test_scheduled_instagram_post_is_not_handed_to_facebook(connected, graph, svc):
    link_instagram(connected, graph, svc)
    photo = upload(connected, "a.png")
    when = (datetime.now() + timedelta(hours=3)).isoformat(timespec="minutes")
    connected.post("/api/posts", json={"message": "x", "photos": [photo], "scheduled_at": when, "also_instagram": True})
    while svc.scheduler.process_one():
        pass
    by = {p.get("channel", "facebook"): p for p in svc.store.load()["posts"]}
    assert by["facebook"]["status"] == "scheduled" and by["instagram"]["status"] == "pending"
    st = connected.get("/api/state").get_json()
    ig = next(p for p in st["posts"] if p.get("channel") == "instagram")
    assert ig["fb_handoff"] is False


def test_instagram_poster_waits_for_processing():
    calls, sleeps = [], []
    seq = iter(["IN_PROGRESS", "IN_PROGRESS", "FINISHED"])

    def fake(method, path, base=facebook.GRAPH, **kw):
        calls.append(path)
        if path == "c1":
            return {"status_code": next(seq)}
        return {"id": "m1"}
    orig, facebook.call = facebook.call, fake
    try:
        ig = facebook.InstagramPoster("ig1", facebook.PagePoster("1", "t"), sleep=sleeps.append)
        assert ig._publish("c1") == {"id": "m1"}
    finally:
        facebook.call = orig
    assert sleeps == [3, 3] and calls[-1] == "ig1/media_publish"
