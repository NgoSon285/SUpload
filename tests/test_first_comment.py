"""Bình luận đầu tiên sau khi bài lên: câu do AI viết và/hoặc link sản phẩm affiliate (Graph API & AI giả lập)."""
from datetime import datetime, timedelta

import pytest

from supload.integrations import ai

LINK = "https://s.shopee.vn/abc123"


def publish(connected, svc, **body):
    pid = connected.post("/api/posts", json={"message": "Áo thun cotton mới về", **body}).get_json()["post"]["id"]
    assert svc.scheduler.process_one()  # đăng
    return pid


def post_of(svc, pid):
    return next(p for p in svc.store.load()["posts"] if p["id"] == pid)


def comments(graph):
    return [c for c in graph.by("POST", "/comments")]


def test_affiliate_link_commented_under_post(connected, svc, graph):
    pid = publish(connected, svc, affiliate_link=LINK)
    fb_id = post_of(svc, pid)["fb_id"]
    assert svc.scheduler.process_one()  # bình luận đầu tiên
    (c,) = comments(graph)
    assert c["path"] == f"{fb_id}/comments" and c["data"]["message"] == f"👉 Link sản phẩm: {LINK}"
    fc = post_of(svc, pid)["first_comment"]
    assert fc["id"] and fc["tries"] == 1 and fc["error"] == ""
    assert not svc.scheduler.process_one()  # chỉ bình luận một lần


def test_ai_comment_with_affiliate_link(connected, svc, graph, monkeypatch):
    calls = []
    monkeypatch.setattr(ai, "suggest", lambda key, model, action, text, **kw: calls.append((key, action, text)) or ["Bấm link bên dưới nha cả nhà!"])
    connected.post("/api/settings", json={"openai_api_key": "sk-x"})
    publish(connected, svc, ai_comment=True, affiliate_link=LINK)
    svc.scheduler.process_one()
    assert calls == [("sk-x", "first_comment_link", "Áo thun cotton mới về")]
    assert comments(graph)[0]["data"]["message"] == f"Bấm link bên dưới nha cả nhà!\n👉 {LINK}"


def test_ai_failure_still_posts_link(connected, svc, graph, monkeypatch):
    def boom(*a, **k):
        raise ai.AIError("AI lỗi")
    monkeypatch.setattr(ai, "suggest", boom)
    connected.post("/api/settings", json={"openai_api_key": "sk-x"})
    publish(connected, svc, ai_comment=True, affiliate_link=LINK)
    svc.scheduler.process_one()
    assert comments(graph)[0]["data"]["message"] == f"👉 Link sản phẩm: {LINK}"


def test_ai_only_without_key_retries_then_gives_up(connected, svc, graph, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    pid = publish(connected, svc, ai_comment=True)
    now = datetime.now()
    assert svc.scheduler.process_one(now)
    fc = post_of(svc, pid)["first_comment"]
    assert fc["tries"] == 1 and "API key" in fc["error"] and comments(graph) == []
    assert not svc.scheduler.process_one(now + timedelta(minutes=5))  # chưa đủ 10 phút
    for i in (1, 2):
        assert svc.scheduler.process_one(now + timedelta(minutes=11 * i))
    assert post_of(svc, pid)["first_comment"]["tries"] == 3
    assert "đã thử 3 lần" in svc.store.load()["log"][0]["text"]
    svc.scheduler.process_one(now + timedelta(hours=1))  # có thể là việc định kỳ khác, nhưng không thử bình luận nữa
    assert post_of(svc, pid)["first_comment"]["tries"] == 3 and comments(graph) == []


def test_reel_comment_goes_to_video(connected, svc, graph):
    with svc.store.transaction() as data:  # reel đã lên (id là id video)
        data["posts"].append({"id": "r1", "message": "", "photos": [], "link": "", "video": "a.mp4", "video_kind": "reel",
                              "status": "done", "fb_id": "v_99", "page": data["pages"][0]["id"], "affiliate_link": LINK,
                              "created_at": datetime.now().isoformat()})
    assert svc.scheduler.process_one()
    assert comments(graph)[0]["path"] == "v_99/comments"


@pytest.mark.parametrize("link", ["shopee.vn/khong-co-http", "https://x/" + "a" * 600])
def test_invalid_affiliate_link_rejected(connected, link):
    r = connected.post("/api/posts", json={"message": "x", "affiliate_link": link})
    assert r.status_code == 400 and "affiliate" in r.get_json()["error"]


def test_nothing_requested_no_comment(connected, svc, graph):
    publish(connected, svc)
    assert not svc.scheduler.process_one() and comments(graph) == []


def test_comment_permission_error_is_explained_and_page_stays_healthy(connected, svc, graph):
    from supload.integrations.facebook import FBError
    graph.fail_reply = FBError("[200] (#200) Requires pages_manage_engagement permission", 200)
    pid = publish(connected, svc, affiliate_link=LINK)
    svc.scheduler.process_one()
    err = post_of(svc, pid)["first_comment"]["error"]
    assert "pages_manage_engagement" in err and "đăng bài" not in err
    health = connected.get("/api/pages").get_json()["pages"][0]["health"]
    assert health is None or health["ok"] is True  # đăng bài vẫn được: không báo Page mất kết nối

    # đổi token (đã thêm quyền) -> bài được thử bình luận lại từ đầu
    graph.fail_reply = None
    page = connected.get("/api/pages").get_json()["pages"][0]["id"]
    assert connected.post(f"/api/pages/{page}/token", json={"token": "USER_NEW"}).status_code == 200
    assert "tries" not in post_of(svc, pid)["first_comment"]
    assert "thử lại bình luận đầu tiên cho 1 bài" in " ".join(l["text"] for l in svc.store.load()["log"][:3])
    while svc.scheduler.process_one():
        pass
    assert post_of(svc, pid)["first_comment"]["id"] and len(comments(graph)) == 2
