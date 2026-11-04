from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta

_stamp_lock = threading.Lock()
_last_stamp = [datetime.min]


def now() -> datetime:
    return datetime.now()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def stamp() -> str:
    """Dấu thời gian tới mili giây, luôn tăng dần (sắp xếp "mới sửa" đúng thứ tự)."""
    with _stamp_lock:
        t = max(datetime.now(), _last_stamp[0] + timedelta(milliseconds=1))
        _last_stamp[0] = t
    return t.isoformat(timespec="milliseconds")


def parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def new_id(prefix: str = "", n: int = 10) -> str:
    return f"{prefix}{uuid.uuid4().hex[:n]}"
