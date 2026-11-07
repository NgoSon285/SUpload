"""Việc nền: mỗi Page, đủ hạn thì chọn 1 bài hiệu quả và đưa lại vào lịch đăng."""
from __future__ import annotations

from datetime import datetime

from ..config import Config
from ..domain import pages as pages_domain
from ..domain import recycle
from ..domain.posts import new_post
from ..storage import Store, add_log, find
from ..utils import now_iso


def config(data: dict) -> dict:
    return recycle.clean_config(data["settings"].get("recycle"))


def state(data: dict, page_id: str) -> dict:
    return data.setdefault("recycle_state", {}).setdefault(page_id, {})


def page_key(data: dict):
    return lambda p: (pages_domain.page_of(data, p) or {}).get("id")


class Recycler:
    def __init__(self, store: Store, config_: Config):
        self.store = store
        self.config = config_

    def due_pages(self, data: dict, now: datetime) -> list[dict]:
        cfg = config(data)
        return [pg for pg in data["pages"] if recycle.due(state(data, pg["id"]), cfg, now)]

    def preview(self, data: dict, page_id: str, now: datetime) -> dict | None:
        c = recycle.candidates(data["posts"], page_id, page_key(data), config(data), now, self.config.upload_dir)
        return c[0] if c else None

    def run(self, page: dict, now: datetime, force: bool = False) -> dict | None:
        """Tạo bài đăng lại cho Page. Trả về bài mới (hoặc None nếu không có ứng viên)."""
        data = self.store.load()
        cfg = config(data)
        orig = self.preview(data, page["id"], now)
        message = None
        if orig and cfg["rewrite"] and orig.get("message"):
            message = self._rewrite(data, orig, page)
        with self.store.transaction() as data:
            state(data, page["id"])["last_at"] = now.isoformat(timespec="seconds")
            if not orig:
                return None
            o = find(data["posts"], orig["id"])
            if not o:
                return None
            when = recycle.slot(data["posts"], page["id"], page_key(data), now)
            post = new_post(recycle.make_post(o, when, message), page=page["id"], source="recycle", recycled_from=o["id"])
            data["posts"].append(post)
            o["recycled_at"] = now_iso()
            add_log(data, "info", f"Đã lên lịch đăng lại bài hiệu quả lúc {when:%H:%M %d/%m}"
                                  f"{' (AI viết lại)' if message else ''}: {(o.get('message') or 'bài có ảnh/video')[:50]}")
            return post

    @staticmethod
    def _rewrite(data: dict, orig: dict, page: dict) -> str | None:
        from ..integrations import ai

        s = data["settings"]
        if not ai.api_key(s):
            return None
        try:
            return ai.suggest_with(s, "variants", orig["message"], page_name=page.get("name", ""))[0]
        except ai.AIError:
            return None  # AI lỗi: đăng lại nguyên văn
