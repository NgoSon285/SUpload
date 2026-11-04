"""Logic đăng bài qua Graph API (fb_poster.py), với Graph API giả lập."""
import json
from datetime import datetime, timedelta

import pytest

import fb_poster
from conftest import PNG


@pytest.fixture
def poster():
    return fb_poster.PagePoster("111", "tok")


def test_requires_page_id_and_token():
    with pytest.raises(fb_poster.FBError):
        fb_poster.PagePoster("", "tok")
    with pytest.raises(fb_poster.FBError):
        fb_poster.PagePoster("111", "")


def test_text_post_goes_to_feed(poster, graph):
    poster.post(message="Xin chào")
    assert graph.calls == [{"method": "POST", "path": "111/feed", "data": {"message": "Xin chào"}, "params": {}, "files": []}]


def test_link_post(poster, graph):
    poster.post(message="Xem", link="https://example.com")
    assert graph.calls[0]["data"] == {"message": "Xem", "link": "https://example.com"}


def test_single_photo_url_posts_directly_to_photos(poster, graph):
    poster.post(message="cap", photos=["https://x/1.jpg"])
    assert len(graph.calls) == 1
    c = graph.calls[0]
    assert c["path"] == "111/photos"
    assert c["data"] == {"published": "true", "caption": "cap", "url": "https://x/1.jpg"}


def test_multi_photo_uploads_unpublished_then_attaches(poster, graph, tmp_path):
    f = tmp_path / "local.png"
    f.write_bytes(PNG)
    poster.post(message="album", photos=["https://x/1.jpg", str(f)])
    paths = [c["path"] for c in graph.calls]
    assert paths == ["111/photos", "111/photos", "111/feed"]
    assert graph.calls[0]["data"]["published"] == "false"
    assert graph.calls[1]["files"] == ["source"]  # file trên máy được upload dạng multipart
    feed = graph.calls[2]["data"]
    assert json.loads(feed["attached_media[0]"]) == {"media_fbid": "111_1"}
    assert json.loads(feed["attached_media[1]"]) == {"media_fbid": "111_2"}


def test_missing_local_photo_raises(poster, graph):
    with pytest.raises(fb_poster.FBError, match="Không tìm thấy ảnh"):
        poster.post(message="x", photos=["/khong/ton/tai.jpg"])


def test_empty_post_rejected(poster, graph):
    with pytest.raises(fb_poster.FBError, match="trống"):
        poster.post()
    assert graph.calls == []


def test_scheduled_post(poster, graph):
    when = datetime.now() + timedelta(hours=2)
    poster.post(message="hẹn", schedule=when)
    d = graph.calls[0]["data"]
    assert d["published"] == "false"
    assert int(d["scheduled_publish_time"]) == int(when.timestamp())


@pytest.mark.parametrize("delta", [timedelta(minutes=5), timedelta(days=31), timedelta(hours=-1)])
def test_schedule_out_of_range_rejected(poster, graph, delta):
    with pytest.raises(fb_poster.FBError, match="10 phút"):
        poster.post(message="x", schedule=datetime.now() + delta)
    assert graph.calls == []


def test_parse_schedule_formats():
    assert fb_poster.parse_schedule("2026-12-01 09:00") == datetime(2026, 12, 1, 9, 0)
    assert fb_poster.parse_schedule("2026-12-01T09:00") == datetime(2026, 12, 1, 9, 0)
    assert fb_poster.parse_schedule(None) is None
    with pytest.raises(fb_poster.FBError):
        fb_poster.parse_schedule("01/12/2026")


def test_token_exchange_and_pages(graph):
    long_token = fb_poster.exchange_long_lived_user_token("app", "secret", "short")
    assert long_token == "LONG_USER_TOKEN"
    assert graph.calls[0]["params"]["grant_type"] == "fb_exchange_token"
    pages = fb_poster.list_pages(long_token)
    assert pages[0]["access_token"] == "PAGE_TOKEN_1"


def test_call_surfaces_graph_errors(monkeypatch):
    class Resp:
        status_code = 400
        text = ""
        def json(self):
            return {"error": {"code": 190, "message": "Invalid OAuth access token"}}
    monkeypatch.setattr(fb_poster.requests, "request", lambda *a, **k: Resp())
    with pytest.raises(fb_poster.FBError, match=r"\[190\] Invalid OAuth"):
        fb_poster._call("GET", "me")
