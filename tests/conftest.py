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
        self._ids = itertools.count(1)

    def __call__(self, method, path, **kwargs):
        data = dict(kwargs.get("data") or {})
        data.pop("access_token", None)
        params = dict(kwargs.get("params") or {})
        params.pop("access_token", None)
        self.calls.append({"method": method, "path": path, "data": data, "params": params, "files": list((kwargs.get("files") or {}).keys())})
        if self.fail_on and self.fail_on in data.get("message", ""):
            raise facebook.FBError("[200] Lỗi giả lập", 200)
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
        if method == "GET" and params.get("fields") == "is_published":
            return {"id": path, "is_published": path in self.published}
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
    return a


@pytest.fixture
def svc(app):
    return app.extensions["supload"]


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def connected(client):
    """Đã kết nối Page qua API; tắt giới hạn an toàn để test hành vi cơ bản (test riêng cho giới hạn)."""
    client.post("/api/settings", json={"method": "api", "page_id": "111", "page_token": "SECRET_PAGE_TOKEN", "min_gap": 0, "daily_max": 0})
    return client


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
