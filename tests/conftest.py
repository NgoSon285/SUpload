import io
import itertools
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app as app_module  # noqa: E402
import fb_poster  # noqa: E402

# PNG 1x1 hợp lệ
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
)


class FakeGraph:
    """Thay cho Graph API thật: ghi lại mọi lời gọi, trả id giả, có thể giả lập lỗi."""

    def __init__(self):
        self.calls = []
        self.fail_on = None  # chuỗi: nếu xuất hiện trong message -> ném FBError
        self._ids = itertools.count(1)

    def __call__(self, method, path, **kwargs):
        data = dict(kwargs.get("data") or {})
        data.pop("access_token", None)
        params = dict(kwargs.get("params") or {})
        params.pop("access_token", None)
        self.calls.append({"method": method, "path": path, "data": data, "params": params, "files": list((kwargs.get("files") or {}).keys())})
        if self.fail_on and self.fail_on in data.get("message", ""):
            raise fb_poster.FBError("[200] Lỗi giả lập")
        if path == "oauth/access_token":
            return {"access_token": "LONG_USER_TOKEN"}
        if path == "me/accounts":
            return {"data": [{"id": "111", "name": "Page Một", "access_token": "PAGE_TOKEN_1"}]}
        if method == "GET":
            return {"id": path, "name": "Page Một"}
        return {"id": f"111_{next(self._ids)}"}


@pytest.fixture
def graph(monkeypatch):
    g = FakeGraph()
    monkeypatch.setattr(fb_poster, "_call", g)
    return g


@pytest.fixture
def appmod(tmp_path, monkeypatch, graph):
    """app.py với dữ liệu & thư mục ảnh tách riêng cho từng test."""
    monkeypatch.setattr(app_module, "DATA_FILE", tmp_path / "data.json")
    up = tmp_path / "uploads"
    up.mkdir()
    monkeypatch.setattr(app_module, "UPLOAD_DIR", up)
    monkeypatch.setitem(app_module.state, "login", "unknown")
    monkeypatch.setitem(app_module.state, "worker", "Đang rảnh")
    for k in ("page_id", "page_token", "page_name", "app_id", "app_secret"):
        monkeypatch.setitem(app_module.DEFAULT_SETTINGS, k, "")
    app_module.app.config["TESTING"] = True
    return app_module


@pytest.fixture
def client(appmod):
    return appmod.app.test_client()


@pytest.fixture
def connected(client):
    client.post("/api/settings", json={"method": "api", "page_id": "111", "page_token": "SECRET_PAGE_TOKEN"})
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
