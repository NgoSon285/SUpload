import io
import itertools
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from supload import Config, create_app  # noqa: E402
from supload.integrations import facebook  # noqa: E402

# PNG 1x1 hợp lệ
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
)


class FakeGraph:
    """Thay cho Graph API thật: ghi lại mọi lời gọi, trả id giả, giả lập lỗi / bài đã lên / bài bị xoá."""

    def __init__(self):
        self.calls = []
        self.fail_on = None       # chuỗi: nếu xuất hiện trong message -> ném FBError
        self.published = set()    # id bài hẹn mà Facebook "đã đăng"
        self.missing = set()      # id bài "đã bị xoá trên Facebook"
        self.fail_delete = False  # giả lập không huỷ được bài hẹn
        self.metrics = {"reactions": 5, "comments": 2, "shares": 1, "reach": 120}
        self.no_insights = False  # giả lập token thiếu quyền read_insights
        # chỉ số Meta đã khai tử từ 06/2026
        self.retired_metrics = {"post_impressions_unique", "post_impressions", "total_video_impressions", "total_video_impressions_unique"}
        self.video_status = "ready"
        self._ids = itertools.count(1)

    def __call__(self, method, path, base=None, **kwargs):
        raw = kwargs.get("data")
        if isinstance(raw, (bytes, bytearray)):  # tải file Reels lên rupload
            self.calls.append({"method": method, "path": path, "base": base, "data": {"_bytes": len(raw)}, "params": {}, "files": [],
                               "headers": kwargs.get("headers", {})})
            return {"success": True}
        data = dict(kwargs.get("data") or {})
        data.pop("access_token", None)
        params = dict(kwargs.get("params") or {})
        params.pop("access_token", None)
        self.calls.append({"method": method, "path": path, "base": base, "data": data, "params": params, "files": list((kwargs.get("files") or {}).keys())})
        if self.fail_on and self.fail_on in data.get("message", ""):
            raise facebook.FBError("[1] Lỗi giả lập", 1)
        if path == "oauth/access_token":
            return {"access_token": "LONG_USER_TOKEN"}
        if path == "me/accounts":
            return {"data": [{"id": "111", "name": "Page Một", "access_token": "PAGE_TOKEN_1"}]}
        if path in self.missing:
            raise facebook.FBError("[100] Unsupported request", 100)
        if method == "DELETE":
            if self.fail_delete:
                raise facebook.FBError("[2] Service temporarily unavailable", 2)
            return {"success": True}
        if method == "GET" and path.endswith(("/insights", "/video_insights")):
            if self.no_insights:
                raise facebook.FBError("[10] Requires read_insights permission", 10)
            if params.get("metric") in self.retired_metrics:  # Meta đã khai tử: báo lỗi cả yêu cầu
                raise facebook.FBError("[100] (#100) The value must be a valid insights metric", 100)
            return {"data": [{"name": params.get("metric"), "period": "day", "values": [{"value": 1}]},
                             {"name": params.get("metric"), "period": "lifetime", "values": [{"value": self.metrics["reach"]}]}]}
        if method == "GET" and str(params.get("fields", "")).startswith(("reactions.", "likes.")):
            m = self.metrics
            key = "likes" if params["fields"].startswith("likes") else "reactions"
            return {key: {"summary": {"total_count": m["reactions"]}}, "comments": {"summary": {"total_count": m["comments"]}},
                    "shares": {"count": m["shares"]}}
        if method == "GET" and str(params.get("fields", "")).startswith("status"):  # trạng thái xử lý video
            return {"id": path, "status": {"video_status": self.video_status}, "published": self.video_status == "ready",
                    "permalink_url": f"/reel/{path}"}
        if method == "GET" and path.endswith("/posts"):
            return {"data": [{"id": "111_latest"}]}
        if method == "GET" and params.get("fields") in ("is_published", "published"):
            return {"id": path, params["fields"]: path in self.published}
        if path.endswith("/video_reels") and data.get("upload_phase") == "start":
            vid = f"v_{next(self._ids)}"
            return {"video_id": vid, "upload_url": f"https://rupload.facebook.com/video-upload/v23.0/{vid}"}
        if path.endswith("/video_reels") and data.get("upload_phase") == "finish":
            return {"success": True}
        if method == "GET":
            return {"id": path, "name": "Page Một"}
        return {"id": f"111_{next(self._ids)}"}

    def by(self, method=None, path_end=None):
        return [c for c in self.calls if (not method or c["method"] == method) and (not path_end or c["path"].endswith(path_end))]


@pytest.fixture
def graph(monkeypatch):
    g = FakeGraph()
    monkeypatch.setattr(facebook, "call", g)
    for k in ("FB_PAGE_ID", "FB_PAGE_TOKEN", "FB_APP_ID", "FB_APP_SECRET"):
        monkeypatch.delenv(k, raising=False)
    return g


@pytest.fixture
def app(tmp_path, graph):
    """Ứng dụng với dữ liệu riêng cho từng test (không chạy luồng nền: test tự gọi process_one)."""
    a = create_app(Config(base_dir=tmp_path, start_worker=False))
    a.config["TESTING"] = True
    # coi như vừa bảo trì xong, để test chỉ thấy việc đăng bài (bảo trì có test riêng)
    from datetime import datetime
    with a.extensions["supload"].store.transaction() as data:
        data["maintenance"] = {"last_run": datetime.now().isoformat(timespec="seconds")}
    return a


@pytest.fixture
def svc(app):
    return app.extensions["supload"]


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def connected(client, svc):
    """Đã kết nối Page qua API; tắt giới hạn an toàn để test hành vi cơ bản (test riêng cho giới hạn)."""
    client.post("/api/settings", json={"min_gap": 0, "daily_max": 0})
    r = client.post("/api/pages", json={"kind": "api", "fb_page_id": "111", "token": "SECRET_PAGE_TOKEN"})
    assert r.status_code == 200, r.get_json()
    mark_healthy(svc)
    return client


def mark_healthy(svc):
    """Coi như mọi Page vừa được kiểm tra kết nối (kiểm tra định kỳ có test riêng)."""
    from datetime import datetime
    from supload.domain import health
    with svc.store.transaction() as data:
        for p in data["pages"]:
            health.record(data, p["id"], True, datetime.now())


def add_browser_page(client, url="https://www.facebook.com/p", name="Page trình duyệt"):
    r = client.post("/api/pages", json={"kind": "browser", "url": url, "name": name})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["page"]["id"]


def upload(client, name="a.png"):
    r = client.post("/api/upload", data={"files": (io.BytesIO(PNG), name)}, content_type="multipart/form-data")
    assert r.status_code == 200, r.get_json()
    return r.get_json()["files"][0]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Ghi kết quả từng giai đoạn để fixture biết test có lỗi không (dùng chụp màn hình khi lỗi)."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
