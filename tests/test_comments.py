"""Bình luận: đồng bộ, quy tắc tự động (ẩn SĐT / từ cấm, trả lời, nhắn riêng), hộp bình luận."""
from datetime import datetime, timedelta

import pytest

from supload.domain import comments as cm
from supload.integrations import facebook


# ---------------------------------------------------------------- quy tắc
@pytest.mark.parametrize("text,ok", [("0912 345 678", True), ("gọi 0912.345.678 nhé", True), ("+84912345678", True),
                                     ("84 912 345 678", True), ("mã 12345", False), ("09123456789", False), ("giá?", False)])
def test_phone_detection(text, ok):
    assert cm.has_phone(text) is ok


def test_keyword_match_ignores_accents_case_and_whole_words():
    assert cm.contains_any("Giá BAO NHIÊU shop ơi", ["gia"]) == "gia"
    assert cm.contains_any("inbox giúp mình", ["ib"]) is None  # không khớp một phần chữ
    assert cm.contains_any("ib mình nhé", ["ib", "gia"]) == "ib"
    assert cm.contains_any("Đặt hàng", ["dat hang"]) == "dat hang"


def cfg(**kw):
    return cm.clean_config({"enabled": True, **kw})


def test_decide_hide_phone_and_reply_with_name_and_private():
    c = {"message": "Giá bao nhiêu, sđt 0912345678", "from": {"name": "Nguyễn Văn An"}, "created_time": datetime.now().isoformat()}
    rules = [{"keywords": "giá, ib", "reply": "Chào {ten}, shop đã nhắn riêng ạ", "private": "Gửi {ten} bảng giá"}]
    d = cm.decide(c, cfg(rules=rules, unhide_after_h=24), datetime.now())
    assert d["hide"] and d["hide_reason"] == "Có số điện thoại" and d["unhide_at"]
    assert d["reply"] == "Chào An, shop đã nhắn riêng ạ" and d["private"] == "Gửi An bảng giá"


def test_decide_respects_disabled_and_private_window():
    old = {"message": "giá", "from": {"name": "B"}, "created_time": (datetime.now() - timedelta(days=8)).isoformat()}
    rules = [{"keywords": "giá", "reply": "R", "private": "P"}]
    d = cm.decide(old, cfg(rules=rules), datetime.now())
    assert d["reply"] == "R" and d["private"] == ""  # quá 7 ngày: không nhắn riêng được
    assert cm.decide(old, cm.clean_config({"enabled": False, "rules": rules}), datetime.now())["reply"] == ""


def test_clean_config_drops_bad_rules_and_values():
    c = cm.clean_config({"rules": [{"keywords": "", "reply": "x"}, {"keywords": "a", "reply": "", "private": ""}, "rác",
                                   {"keywords": "a\nb", "reply": "ok"}], "unhide_after_h": 5, "poll_minutes": 0, "hide_words": "x;y"})
    assert c["rules"] == [{"keywords": "a, b", "reply": "ok", "private": "", "enabled": True}]
    assert c["unhide_after_h"] == 0 and c["poll_minutes"] == 1 and c["hide_words"] == "x, y"


# ---------------------------------------------------------------- đồng bộ qua Graph (giả)
def comment(cid, msg, minutes_ago=0, name="Khách Hàng", hidden=False):
    return {"id": cid, "message": msg, "from": {"id": "u" + cid, "name": name},
            "created_time": (datetime.now() - timedelta(minutes=minutes_ago)).isoformat(timespec="seconds"),
            "is_hidden": hidden, "can_hide": True, "can_reply_privately": True, "permalink_url": f"https://fb.com/{cid}"}


@pytest.fixture
def fb(connected, svc, graph):
    with svc.store.transaction() as data:
        data["settings"]["comments"]["inbox"] = True
    graph.page_posts = [{"id": "111_p1", "message": "Bánh kem mới", "permalink_url": "https://fb.com/p1"}]
    graph.post_comments = {"111_p1": [comment("c_old", "đẹp quá", 600)]}
    return graph


def sync(svc, minutes=0):
    return svc.scheduler.process_one(now=datetime.now() + timedelta(minutes=minutes))


def test_first_sync_only_records_then_rules_apply_to_new_comments(connected, svc, fb):
    connected.put("/api/comments/config", json={"enabled": True, "inbox": True, "hide_phone": True,
                                                "rules": [{"keywords": "giá", "reply": "Dạ {ten} ơi shop ib ạ", "private": "Bảng giá: ..."}]})
    fb.post_comments["111_p1"].append(comment("c_old2", "giá bao nhiêu 0912345678", 300))
    assert sync(svc)  # lần đầu: chỉ lưu
    assert not fb.by("POST") and len(svc.store.load()["comments"]) == 2

    fb.post_comments["111_p1"] += [comment("c1", "Giá bao nhiêu ạ", -5, "Trần Bình"), comment("c2", "sđt mình 0912 345 678", -5),
                                   comment("c3", "ok", -5, hidden=False) | {"from": {"id": "111", "name": "Page"}}]
    assert sync(svc, 4)
    posts = {(c["path"], tuple(sorted(c["data"]))) for c in fb.by("POST")}
    assert ("c1/comments", ("message",)) in posts  # trả lời công khai
    assert any(p == "111/messages" for p, _ in posts)  # nhắn riêng
    assert ("c2", ("is_hidden",)) in posts  # ẩn SĐT
    reply = next(c for c in fb.by("POST") if c["path"] == "c1/comments")
    assert reply["data"]["message"] == "Dạ Bình ơi shop ib ạ"
    msg = next(c for c in fb.by("POST") if c["path"] == "111/messages")
    assert '"comment_id": "c1"' in msg["data"]["recipient"]
    items = {c["id"]: c for c in svc.store.load()["comments"]}
    assert "c3" not in items  # bình luận của chính Page bị bỏ qua
    assert items["c1"]["private_sent"] and len(items["c1"]["replies"]) == 2
    assert items["c2"]["hidden"] and items["c2"]["hide_reason"] == "Có số điện thoại"
    assert not items["c_old2"]["hidden"]  # bình luận cũ không bị xử lý

    n_calls = len(fb.calls)
    assert sync(svc, 8) and not [c for c in fb.calls[n_calls:] if c["method"] == "POST"]  # không xử lý lại


def test_temporary_hide_is_undone_later(connected, svc, fb):
    connected.put("/api/comments/config", json={"enabled": True, "inbox": True, "hide_phone": True, "unhide_after_h": 1})
    sync(svc)
    fb.post_comments["111_p1"].append(comment("c9", "0987654321", -5))
    sync(svc, 4)
    c = next(x for x in svc.store.load()["comments"] if x["id"] == "c9")
    assert c["hidden"] and c["unhide_at"]
    sync(svc, 70)
    unhide = [x for x in fb.by("POST") if x["path"] == "c9" and x["data"]["is_hidden"] == "false"]
    assert unhide and not next(x for x in svc.store.load()["comments"] if x["id"] == "c9")["hidden"]


def test_permission_error_backs_off_and_is_reported(connected, svc, fb):
    fb.comments_error = facebook.FBError("[10] Requires pages_read_user_content", 10)
    sync(svc)
    data = svc.store.load()
    st = data["comment_sync"][data["pages"][0]["id"]]
    assert "pages_read_user_content" in st["error"]
    assert svc.scheduler.process_one(now=datetime.now() + timedelta(minutes=10)) is False  # chờ 1 giờ mới thử lại
    r = connected.get("/api/comments").get_json()
    assert "pages_manage_engagement" in list(r["sync"].values())[0]["error"]


def test_inbox_api_reply_private_hide_and_filters(connected, svc, fb):
    sync(svc)
    r = connected.get("/api/comments").get_json()
    assert r["total"] == 1 and r["counts"]["unreplied"] == 1 and r["unseen"] == 0  # lần đầu coi như đã xem
    assert connected.get("/api/state").get_json()["comments_unseen"] == 0
    assert connected.post("/api/comments/c_old/reply", json={"message": "Cảm ơn bạn!"}).status_code == 200
    assert connected.post("/api/comments/c_old/reply", json={"message": "Ưu đãi", "private": True}).status_code == 200
    r = connected.post("/api/comments/c_old/reply", json={"message": "lần 2", "private": True})
    assert r.status_code == 400 and "1 lần" in r.get_json()["error"]
    assert connected.post("/api/comments/c_old/hide", json={"hidden": True}).get_json()["comment"]["hidden"]
    r = connected.get("/api/comments?filter=hidden").get_json()
    assert r["total"] == 1 and r["counts"]["unreplied"] == 0
    assert connected.get("/api/comments?q=khong-co").get_json()["total"] == 0
    assert connected.post("/api/comments/zzz/reply", json={"message": "x"}).status_code == 404


def test_reply_error_from_facebook_is_explained(connected, svc, fb):
    sync(svc)
    fb.fail_reply = facebook.FBError("[200] Permissions error", 200)
    r = connected.post("/api/comments/c_old/reply", json={"message": "x"})
    assert r.status_code == 400 and "pages_manage_engagement" in r.get_json()["error"]


def test_sync_now_resets_timer(connected, svc, fb):
    sync(svc)
    assert svc.scheduler.process_one() is False
    connected.post("/api/comments/sync")
    assert svc.scheduler.process_one() is True
