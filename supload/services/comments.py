"""Đồng bộ bình luận của các Page (qua API) và áp quy tắc tự động.

Ứng dụng chạy trên máy nên không nhận được webhook của Facebook: luồng nền hỏi định kỳ
(mặc định 3 phút/lần) bình luận mới của các bài trong vài ngày gần đây.
Lần đồng bộ đầu tiên chỉ ghi nhận bình luận cũ, KHÔNG tự trả lời/ẩn, để tránh trả lời hàng loạt bình luận cũ.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from ..domain import comments as cm
from ..integrations.facebook import FBError
from ..storage import Store, add_log
from ..utils import parse_dt
from .publisher import Publisher

PERMISSION_CODES = {10, 200, 190, 102}
RETRY_AFTER_ERROR = timedelta(hours=1)
PERMISSION_HELP = ("Token chưa có quyền đọc/quản lý bình luận. Tạo lại User Token với thêm quyền "
                   "pages_read_user_content, pages_manage_engagement và pages_messaging, rồi thêm lại Page.")


def config(data: dict) -> dict:
    return cm.clean_config(data["settings"].get("comments"))


def state(data: dict, page_id: str) -> dict:
    return data.setdefault("comment_sync", {}).setdefault(page_id, {})


def due(data: dict, page: dict, now: datetime) -> bool:
    cfg = config(data)
    if page.get("kind") != "api" or not (cfg["enabled"] or cfg.get("inbox", True)):
        return False
    st = state(data, page["id"])
    last = parse_dt(st.get("last_at"))
    wait = RETRY_AFTER_ERROR if st.get("error") else timedelta(minutes=cfg["poll_minutes"])
    return last is None or now - last >= wait


def unhide_due(data: dict, now: datetime) -> list[dict]:
    return [c for c in data.get("comments", []) if c.get("hidden") and c.get("unhide_at") and parse_dt(c["unhide_at"]) <= now]


class CommentSync:
    def __init__(self, store: Store, publisher: Publisher):
        self.store = store
        self.publisher = publisher

    # ------------------------------------------------------------ đồng bộ 1 Page
    def sync(self, page: dict, now: datetime) -> dict:
        """Lấy bình luận mới của Page, áp quy tắc. Trả về {"new": n, "actions": n, "error": str}."""
        data = self.store.load()
        cfg = config(data)
        st = dict(state(data, page["id"]))
        first = not st.get("started_at")
        started = parse_dt(st.get("started_at")) or now
        known = {c["id"] for c in data.get("comments", [])}
        poster = self.publisher.poster(page)
        fresh, updates, logs = [], {}, []
        try:
            for post in poster.recent_posts(now - timedelta(days=cfg["days"]), limit=10):
                for c in poster.comments(post["id"], limit=50):
                    if (c.get("from") or {}).get("id") == page.get("fb_page_id"):
                        continue  # bình luận của chính Page
                    if c["id"] in known:
                        updates[c["id"]] = bool(c.get("is_hidden"))
                        continue
                    rec = cm.record(c, page["id"], post)
                    created = parse_dt(c.get("created_time"))
                    if first or (created and created < started - timedelta(minutes=1)):
                        rec["seen"] = True  # bình luận có từ trước khi bật đồng bộ: chỉ lưu, không tự xử lý
                    else:
                        self._apply(poster, rec, c, cfg, now, logs)
                    fresh.append(rec)
                    known.add(c["id"])
            error = ""
        except FBError as e:
            error = PERMISSION_HELP if e.code in PERMISSION_CODES else str(e)
        with self.store.transaction() as data:
            items = data.setdefault("comments", [])
            for c in items:
                if c["id"] in updates and not c.get("unhide_at"):
                    c["hidden"] = updates[c["id"]]
            items.extend(fresh)
            data["comments"] = cm.trim(items)
            s = state(data, page["id"])
            s.update(last_at=now.isoformat(timespec="seconds"), error=error)
            s.setdefault("started_at", now.isoformat(timespec="seconds"))
            for level, text in logs:
                add_log(data, level, text)
            if error and error != st.get("error"):
                add_log(data, "error", f"Không đọc được bình luận của Page “{page['name']}”: {error}")
        return {"new": len(fresh), "actions": len(logs), "error": error}

    @staticmethod
    def _apply(poster, rec: dict, raw: dict, cfg: dict, now: datetime, logs: list) -> None:
        todo = cm.decide(raw, cfg, now)
        who = rec["from_name"]
        if todo["hide"] and rec["can_hide"] and not rec["hidden"]:
            try:
                poster.hide_comment(rec["id"], True)
                rec.update(hidden=True, hide_reason=todo["hide_reason"], unhide_at=todo["unhide_at"], auto_hidden=True)
                logs.append(("info", f"Đã ẩn bình luận của {who} ({todo['hide_reason'].lower()})"))
            except FBError as e:
                rec["errors"].append(f"Không ẩn được: {e}")
        if todo["reply"]:
            try:
                r = poster.reply_comment(rec["id"], todo["reply"])
                rec["replies"].append({"text": todo["reply"], "at": now.isoformat(timespec="seconds"), "auto": True, "id": r.get("id")})
                logs.append(("ok", f"Đã tự trả lời bình luận của {who}"))
            except FBError as e:
                rec["errors"].append(f"Không trả lời được: {e}")
        if todo["private"]:
            try:
                poster.private_reply(rec["id"], todo["private"])
                rec["private_sent"] = True
                rec["replies"].append({"text": todo["private"], "at": now.isoformat(timespec="seconds"), "auto": True, "private": True})
                logs.append(("ok", f"Đã nhắn riêng cho {who}"))
            except FBError as e:
                rec["errors"].append(f"Không nhắn riêng được: {e}")
        if rec["replies"] or rec["hidden"]:
            rec["seen"] = True if not todo["hide"] else rec["seen"]

    # ------------------------------------------------------------ hiện lại bình luận đã ẩn tạm
    def unhide(self, comment: dict, page: dict | None, now: datetime) -> None:
        err = ""
        try:
            self.publisher.poster(page).hide_comment(comment["id"], False)
        except FBError as e:
            err = str(e)
        with self.store.transaction() as data:
            for c in data.get("comments", []):
                if c["id"] == comment["id"]:
                    c["unhide_at"] = None
                    if err:
                        c["errors"].append(f"Không hiện lại được: {err}")
                    else:
                        c["hidden"] = False
