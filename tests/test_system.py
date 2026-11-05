"""Tự khởi động cùng Windows (giả lập thư mục Startup), thông tin hệ thống, đường dẫn khi đóng gói."""
import importlib
import sys

from supload.services import autostart


def test_autostart_toggle_writes_hidden_startup_script(client, svc, tmp_path, monkeypatch):
    startup = tmp_path / "Startup"
    monkeypatch.setenv("SUPLOAD_FAKE_STARTUP_DIR", str(startup))
    info = client.get("/api/system").get_json()
    assert info["autostart"] == {"supported": True, "enabled": False} and info["data_dir"] == str(svc.config.base_dir)
    assert client.post("/api/system/autostart", json={"enabled": True}).get_json()["enabled"] is True
    text = (startup / "SUpload.vbs").read_text(encoding="utf-16")
    assert '--no-browser' in text and ", 0, False" in text            # chạy ẩn, không mở trình duyệt
    assert f'SUPLOAD_HOME") = "{svc.config.base_dir}"' in text       # đúng thư mục dữ liệu
    assert client.post("/api/system/autostart", json={"enabled": False}).get_json()["enabled"] is False
    assert not (startup / "SUpload.vbs").exists()


def test_autostart_unsupported_off_windows(client, monkeypatch):
    monkeypatch.delenv("SUPLOAD_FAKE_STARTUP_DIR", raising=False)
    monkeypatch.setattr(autostart.os, "name", "posix")
    r = client.post("/api/system/autostart", json={"enabled": True})
    assert r.status_code == 400 and "Windows" in r.get_json()["error"]


def test_shutdown_endpoint_is_safe_in_tests(client):
    assert client.post("/api/system/shutdown").get_json()["test"] is True


def test_no_browser_flag(monkeypatch):
    import supload.app as app_mod
    monkeypatch.delenv("NO_BROWSER", raising=False)
    monkeypatch.setattr(app_mod, "Config", lambda: (_ for _ in ()).throw(SystemExit(0)))  # dừng ngay sau khi đọc tham số
    try:
        app_mod.main(["--no-browser"])
    except SystemExit:
        pass
    import os
    assert os.environ["NO_BROWSER"] == "1"


def test_frozen_paths(monkeypatch, tmp_path):
    """Giả lập chạy từ file .exe đóng gói: giao diện trong gói, dữ liệu cạnh .exe."""
    import supload.config as cfg
    exe = tmp_path / "SUpload" / "SUpload.exe"
    exe.parent.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.delenv("SUPLOAD_HOME", raising=False)
    try:
        importlib.reload(cfg)
        c = cfg.Config()
        assert c.base_dir == exe.parent and c.data_file == exe.parent / "data.json"
        assert c.web_dir == tmp_path / "bundle" / "web"
    finally:
        monkeypatch.undo()
        importlib.reload(cfg)
