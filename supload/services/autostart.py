"""Tự khởi động cùng Windows: đặt một script nhỏ vào thư mục Startup của người dùng.

Script chạy SUpload ẩn (không cửa sổ, không mở trình duyệt). Mở giao diện bằng http://127.0.0.1:5000,
tắt bằng nút "Tắt ứng dụng" trong Cài đặt.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from ..config import FROZEN, ROOT

SCRIPT_NAME = "SUpload.vbs"


def supported() -> bool:
    return os.name == "nt" or bool(os.getenv("SUPLOAD_FAKE_STARTUP_DIR"))  # biến thứ hai: chỉ để test


def startup_dir() -> Path:
    fake = os.getenv("SUPLOAD_FAKE_STARTUP_DIR")
    if fake:
        return Path(fake)
    return Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def command() -> list[str]:
    """Lệnh chạy SUpload ẩn: file .exe khi đã đóng gói, hoặc pythonw app.py khi chạy từ mã nguồn."""
    if FROZEN:
        return [sys.executable, "--no-browser"]
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    return [str(pyw if pyw.exists() else py), str(ROOT / "app.py"), "--no-browser"]


def script_text(data_dir: Path) -> str:
    quoted = " ".join(f'""{c}""' for c in command())
    return (
        "' Tạo bởi SUpload: chạy ẩn khi đăng nhập Windows. Xoá file này hoặc tắt trong Cài đặt để bỏ.\r\n"
        'Set sh = CreateObject("WScript.Shell")\r\n'
        f'sh.CurrentDirectory = "{data_dir}"\r\n'
        f'sh.Environment("PROCESS")("SUPLOAD_HOME") = "{data_dir}"\r\n'
        f'sh.Run "{quoted}", 0, False\r\n'
    )


def enabled() -> bool:
    return supported() and (startup_dir() / SCRIPT_NAME).is_file()


def set_enabled(on: bool, data_dir: Path) -> bool:
    if not supported():
        raise RuntimeError("Tự khởi động chỉ hỗ trợ trên Windows")
    path = startup_dir() / SCRIPT_NAME
    if on:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(script_text(data_dir), encoding="utf-16")  # VBScript đọc được tiếng Việt khi lưu UTF-16
    else:
        path.unlink(missing_ok=True)
    return enabled()
