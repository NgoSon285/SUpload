"""Page bình luận vào bài đã đăng (Graph API giả lập)."""
from conftest import add_browser_page
from supload.integrations.facebook import FBError


def done_post(connected, svc, **body):
    pid = connected.post("/api/posts", json={"message": "Áo thun", **body}).get_json()["post"]["id"]
    svc.scheduler.process_one()
    return pid


def test_comment_on_published_post(connected, svc, graph):
    pid = done_post(connected, svc)
    fb_id = next(p for p in svc.store.load()["posts"] if p["id"] == pid)["fb_id"]
    r = connected.post(f"/api/posts/{pid}/comment", json={"message": "  Link nè: https://s.shopee.vn/x  "})
    assert r.status_code == 200 and r.get_json()["comment"]["id"]
    c = graph.by("POST", "/comments")[0]
    assert c["path"] == f"{fb_id}/comments" and c["data"]["message"] == "Link nè: https://s.shopee.vn/x"
    connected.post(f"/api/posts/{pid}/comment", json={"message": "Cảm ơn cả nhà"})
    post = next(p for p in connected.get("/api/state").get_json()["posts"] if p["id"] == pid)
    assert [c["text"] for c in post["page_comments"]] == ["Link nè: https://s.shopee.vn/x", "Cảm ơn cả nhà"]


def test_only_published_facebook_posts(connected, svc, graph):
    pending = connected.post("/api/posts", json={"message": "x", "scheduled_at": "2099-01-01T08:00"}).get_json()["post"]["id"]
    r = connected.post(f"/api/posts/{pending}/comment", json={"message": "hi"})
    assert r.status_code == 400 and "đã lên Facebook" in r.get_json()["error"]
    pid = done_post(connected, svc)
    assert connected.post(f"/api/posts/{pid}/comment", json={"message": " "}).status_code == 400
    assert connected.post("/api/posts/khong-co/comment", json={"message": "hi"}).status_code == 404
    assert graph.by("POST", "/comments") == []


def test_browser_page_cannot_comment(client, svc):
    add_browser_page(client)
    with svc.store.transaction() as data:
        data["posts"].append({"id": "b1", "message": "x", "photos": [], "link": "", "status": "done", "fb_id": "1_2",
                              "page": data["pages"][0]["id"], "created_at": "2026-01-01T00:00:00"})
    r = client.post("/api/posts/b1/comment", json={"message": "hi"})
    assert r.status_code == 400 and "Graph API" in r.get_json()["error"]


def test_permission_error_names_engagement_permission(connected, svc, graph):
    pid = done_post(connected, svc)
    graph.fail_reply = FBError("[200] (#200) Requires pages_manage_engagement permission", 200)
    r = connected.post(f"/api/posts/{pid}/comment", json={"message": "hi"})
    assert r.status_code == 400 and "pages_manage_engagement" in r.get_json()["error"]
