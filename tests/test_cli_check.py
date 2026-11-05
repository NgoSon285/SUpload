"""Lệnh `fb_poster.py kiemtra`: đăng thử video/Reel thật rồi kiểm tra từng bước (ở đây dùng Graph giả)."""
import json

import pytest

from supload.cli import facebook as cli

MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


@pytest.fixture
def clip(tmp_path, monkeypatch, graph):
    monkeypatch.chdir(tmp_path)  # post_log.jsonl ghi vào thư mục tạm
    monkeypatch.setenv("FB_PAGE_ID", "111")
    monkeypatch.setenv("FB_PAGE_TOKEN", "PAGE_TOKEN_1")
    f = tmp_path / "clip.mp4"
    f.write_bytes(MP4)
    return f


def test_reel_check_all_steps_pass_and_deletes(clip, graph, capsys):
    assert cli.main(["kiemtra", "--video", str(clip), "--reel", "--xoa"]) == 0
    out = capsys.readouterr().out
    assert "6/6 bước qua" in out and "lượt xem=120" in out and "người xem=120" in out
    assert graph.by("DELETE")
    metrics = [c["params"]["metric"] for c in graph.calls if c["path"].endswith("insights")]
    assert metrics == ["total_video_views", "post_total_media_view_unique"]
    log = json.loads((clip.parent / "post_log.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert log["ok"] is True and log["check"] == "Reels"


def test_check_reports_missing_permission_and_processing_error(clip, graph, capsys):
    graph.no_insights = True
    graph.video_status = "error"
    assert cli.main(["kiemtra", "--video", str(clip)]) == 1
    out = capsys.readouterr().out
    assert "Facebook xử lý video bị lỗi" in out and "read_insights" in out and "2/5 bước qua" in out


def test_check_uses_page_saved_in_app(tmp_path, clip, graph, monkeypatch, capsys):
    monkeypatch.setenv("SUPLOAD_HOME", str(tmp_path))
    (tmp_path / "data.json").write_text(json.dumps({"pages": [
        {"id": "pg_1", "kind": "api", "name": "Page Phụ", "fb_page_id": "222", "token": "T2"}]}), encoding="utf-8")
    assert cli.main(["kiemtra", "--video", str(clip), "--page", "Page Phụ"]) == 0
    assert graph.calls[0]["path"] == "222"
    assert cli.main(["kiemtra", "--video", str(clip), "--page", "Không có"]) == 1
