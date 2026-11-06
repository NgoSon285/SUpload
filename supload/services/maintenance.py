"""Bảo trì hằng ngày: sao lưu data.json, dọn bài đã đăng lâu ngày, xoá ảnh không còn dùng."""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from ..config import Config
from ..domain.posts import DONE
from ..storage import Store, add_log
from ..utils import parse_dt

KEEP_BACKUPS = 14
ORPHAN_AGE = timedelta(days=7)   # ảnh mới tải lên có thể đang nằm trong bản nháp chưa đăng -> chờ 7 ngày
RUN_EVERY = timedelta(hours=24)


def referenced_photos(data: dict) -> set[str]:
    """Mọi tên ảnh/video còn được bài viết hoặc flow dùng tới."""
    used = {p for post in data["posts"] for p in post.get("photos", [])}
    used.update(post["video"] for post in data["posts"] if isinstance(post.get("video"), str) and post["video"])
    for flow in data.get("flows", []):
        for node in flow.get("nodes", []):
            d = node.get("data") or {}
            used.update(x for x in d.get("photos", []) if isinstance(x, str))
            if isinstance(d.get("video"), str) and d["video"]:
                used.add(d["video"])
    return used


class Maintenance:
    def __init__(self, store: Store, config: Config):
        self.store = store
        self.config = config

    @property
    def backup_dir(self) -> Path:
        return self.config.base_dir / "backups"

    def backups(self) -> list[Path]:
        return sorted(self.backup_dir.glob("data-*.json"))

    def due(self, data: dict, now: datetime) -> bool:
        last = parse_dt((data.get("maintenance") or {}).get("last_run"))
        return last is None or now - last >= RUN_EVERY

    def backup(self, now: datetime) -> str | None:
        if not self.store.path.exists():
            return None
        self.backup_dir.mkdir(exist_ok=True)
        dest = self.backup_dir / f"data-{now:%Y%m%d-%H%M%S}.json"
        with self.store.lock:
            shutil.copy2(self.store.path, dest)
        for old in self.backups()[:-KEEP_BACKUPS]:
            old.unlink(missing_ok=True)
        return dest.name

    def run(self, now: datetime | None = None) -> dict:
        """Sao lưu (trước) rồi dọn dẹp. Trả về tóm tắt."""
        now = now or datetime.now()
        backup = self.backup(now)
        with self.store.transaction() as data:
            keep_days = int(data["settings"].get("keep_done_days") or 0)
            removed_posts = 0
            if keep_days:
                cutoff = now - timedelta(days=keep_days)
                before = len(data["posts"])
                data["posts"] = [p for p in data["posts"]
                                 if not (p["status"] == DONE and (parse_dt(p.get("done_at")) or now) < cutoff)]
                removed_posts = before - len(data["posts"])
            used = referenced_photos(data)
            removed_files = 0
            for f in self.config.upload_dir.iterdir():
                if f.is_file() and f.name not in used and now - datetime.fromtimestamp(f.stat().st_mtime) > ORPHAN_AGE:
                    f.unlink(missing_ok=True)
                    removed_files += 1
            summary = {"last_run": now.isoformat(timespec="seconds"), "last_backup": backup,
                       "removed_posts": removed_posts, "removed_files": removed_files}
            data["maintenance"] = summary
            if removed_posts or removed_files:
                add_log(data, "info", f"Bảo trì: đã sao lưu, dọn {removed_posts} bài cũ và {removed_files} ảnh không dùng")
        return {**summary, "backups": len(self.backups())}
