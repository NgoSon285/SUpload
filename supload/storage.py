"""Lưu trữ trong data.json, an toàn khi nhiều luồng cùng đọc/ghi."""
from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from pathlib import Path

from .config import default_settings
from .utils import now_iso

LOG_LIMIT = 300


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.RLock()

    # ---- đọc / ghi
    def load(self) -> dict:
        with self.lock:
            data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        data["settings"] = {**default_settings(), **data.get("settings", {})}
        data.setdefault("posts", [])
        data.setdefault("flows", [])
        data.setdefault("log", [])
        return data

    def save(self, data: dict) -> None:
        with self.lock:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)  # ghi nguyên tử: không bao giờ để file dở dang

    @contextmanager
    def transaction(self):
        """`with store.transaction() as data:` đọc, sửa, tự ghi khi thoát (không ghi nếu có lỗi)."""
        with self.lock:
            data = self.load()
            yield data
            self.save(data)

    # ---- tiện ích
    def update_post(self, post_id: str, **fields) -> dict | None:
        with self.transaction() as data:
            post = find(data["posts"], post_id)
            if post:
                post.update(fields)
            return post

    def log(self, level: str, text: str) -> None:
        with self.transaction() as data:
            add_log(data, level, text)


def add_log(data: dict, level: str, text: str) -> None:
    data["log"].insert(0, {"at": now_iso(), "level": level, "text": text})
    del data["log"][LOG_LIMIT:]


def find(items: list[dict], item_id: str) -> dict | None:
    return next((x for x in items if x.get("id") == item_id), None)
