"""Ảnh sản phẩm: thư mục lưu ảnh (đặt, chọn bằng hộp thoại hệ điều hành, mở). Phần lấy ảnh làm sau."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request

from ..storage import add_log
from . import error, services

bp = Blueprint("review", __name__, url_prefix="/api/review")


def _root() -> Path | None:
    d = services().store.load()["settings"].get("review_dir")
    return Path(d) if d and Path(d).is_dir() else None


@bp.put("/dir")
def set_dir():
    """Đặt thư mục lưu: phải là đường dẫn đầy đủ; chưa có thì tạo; phải ghi được."""
    raw = str(request.get_json(force=True).get("dir") or "").strip()
    p = Path(raw).expanduser()
    if not raw or not p.is_absolute():
        return error("Nhập đường dẫn đầy đủ, vd /Users/ten/Pictures/Review hoặc D:\\Review")
    try:
        p.mkdir(parents=True, exist_ok=True)
        tempfile.TemporaryFile(dir=p).close()  # thử ghi
    except OSError as e:
        return error(f"Không dùng được thư mục này: {e.strerror or e}")
    with services().store.transaction() as data:
        data["settings"]["review_dir"] = str(p)
        add_log(data, "info", f"Thư mục lưu ảnh sản phẩm: {p}")
    return jsonify(dir=str(p))


PICK_PROMPT = "Chọn thư mục lưu ảnh sản phẩm"
PICK_CMD = {
    # hiện hộp chọn trong ứng dụng đang ở trước (trình duyệt) để không bị che
    "darwin": ["osascript", "-e", f'tell application (path to frontmost application as text) to POSIX path of (choose folder with prompt "{PICK_PROMPT}")'],
    "win32": ["powershell", "-NoProfile", "-STA", "-Command",
              "Add-Type -AssemblyName System.Windows.Forms; [Console]::OutputEncoding=[Text.Encoding]::UTF8; "
              "$f=New-Object System.Windows.Forms.Form -Property @{TopMost=$true}; $d=New-Object System.Windows.Forms.FolderBrowserDialog; "
              f"$d.Description='{PICK_PROMPT}'; if($d.ShowDialog($f) -eq 'OK'){{$d.SelectedPath}}"],
    "linux": ["zenity", "--file-selection", "--directory", f"--title={PICK_PROMPT}"],
}


@bp.post("/pick")
def pick_dir():
    """Mở hộp chọn thư mục của hệ điều hành (ứng dụng chạy trên chính máy người dùng). Trả "" nếu bấm Huỷ."""
    cmd = PICK_CMD.get(sys.platform)
    if not cmd:
        return error("Máy này chưa hỗ trợ hộp chọn thư mục, hãy nhập đường dẫn")
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=600)  # noqa: S603 - lệnh cố định
    except (OSError, subprocess.TimeoutExpired):
        return error("Không mở được hộp chọn thư mục, hãy nhập đường dẫn")
    out = r.stdout.decode("utf-8", "replace").strip() if r.returncode == 0 else ""
    return jsonify(dir=str(Path(out)) if out else "")  # Path bỏ dấu / thừa ở cuối (giữ nguyên ổ D:\\)


@bp.post("/open")
def open_folder():
    """Mở thư mục lưu (hoặc thư mục của một sản phẩm) trong Finder / File Explorer."""
    root = _root()
    if not root:
        return error("Chưa chọn thư mục lưu ảnh", 400, need_dir=True)
    p = Path(request.get_json(force=True).get("path") or root).resolve()
    if not p.is_dir() or not p.is_relative_to(root.resolve()):  # chỉ mở trong thư mục lưu
        return error("Không tìm thấy thư mục", 404)
    if sys.platform == "win32":
        os.startfile(p)  # type: ignore[attr-defined]  # noqa: S606
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(p)])  # noqa: S603
    return jsonify(ok=True)
