"""Thông tin hệ thống, tự khởi động cùng Windows, tắt ứng dụng."""
from __future__ import annotations

import os
import platform
import threading

from flask import Blueprint, jsonify, request

from .. import __version__
from ..config import FROZEN
from ..services import autostart
from . import error, services

bp = Blueprint("system", __name__, url_prefix="/api/system")


@bp.get("")
def info():
    return jsonify(version=__version__, platform=platform.system(), frozen=FROZEN,
                   data_dir=str(services().config.base_dir),
                   autostart={"supported": autostart.supported(), "enabled": autostart.enabled()})


@bp.post("/autostart")
def set_autostart():
    on = bool(request.get_json(force=True).get("enabled"))
    try:
        state = autostart.set_enabled(on, services().config.base_dir)
    except (RuntimeError, OSError) as e:
        return error(str(e))
    services().store.log("info", "Đã bật tự khởi động cùng Windows" if state else "Đã tắt tự khởi động cùng Windows")
    return jsonify(enabled=state)


def _exit() -> None:
    os._exit(0)  # dừng hẳn tiến trình (kể cả luồng nền); khoá chạy-1-lần tự nhả


@bp.post("/shutdown")
def shutdown():
    """Tắt ứng dụng (hữu ích khi chạy ẩn cùng Windows)."""
    services().store.log("info", "Đã tắt ứng dụng từ giao diện")
    if not services().config.start_worker:  # trong test: không tắt tiến trình test
        return jsonify(ok=True, test=True)
    threading.Timer(0.5, _exit).start()
    return jsonify(ok=True)
