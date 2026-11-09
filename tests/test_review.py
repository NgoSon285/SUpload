"""Ảnh sản phẩm: thư mục lưu ảnh (đặt, chọn bằng hộp thoại hệ điều hành, mở)."""
from types import SimpleNamespace

import pytest

from supload.api import review as review_api


def test_dir_must_be_absolute_and_is_created(client, svc, tmp_path):
    assert client.put("/api/review/dir", json={"dir": "tuong/doi"}).status_code == 400
    target = tmp_path / "anh" / "review"
    r = client.put("/api/review/dir", json={"dir": str(target)})
    assert r.status_code == 200 and target.is_dir() and svc.store.load()["settings"]["review_dir"] == str(target)


def test_open_only_inside_review_dir(client, tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(review_api.subprocess, "Popen", lambda args: opened.append(args))
    monkeypatch.setattr(review_api.os, "startfile", lambda p: opened.append(p), raising=False)
    assert client.post("/api/review/open", json={}).status_code == 400  # chưa chọn thư mục
    client.put("/api/review/dir", json={"dir": str(tmp_path / "r")})
    assert client.post("/api/review/open", json={"path": str(tmp_path)}).status_code == 404  # ngoài thư mục lưu
    assert client.post("/api/review/open", json={}).status_code == 200 and len(opened) == 1


@pytest.mark.parametrize("rc,out,expected", [(0, "/Users/a/Ảnh review/\n".encode(), "/Users/a/Ảnh review"), (1, b"", "")])
def test_pick_dir_uses_os_dialog(client, monkeypatch, rc, out, expected):
    calls = []
    monkeypatch.setattr(review_api.sys, "platform", "darwin")
    monkeypatch.setattr(review_api.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or SimpleNamespace(returncode=rc, stdout=out))
    assert client.post("/api/review/pick").get_json()["dir"] == expected  # rc 1 = bấm Huỷ
    assert calls[0][0] == "osascript"
