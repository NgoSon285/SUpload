"""Luồng chạy nền: mỗi lượt làm tối đa MỘT việc, theo thứ tự ưu tiên:

1. Đối soát bài đã hẹn trên Facebook (đã lên chưa?)
2. Tự đăng bài đã đến giờ (việc gấp nhất về thời gian)
3. Giao bài sắp tới (trong 12 phút – 30 ngày) cho Facebook tự đăng   [cách API + bật hẹn giờ FB]
   Bài còn dưới 12 phút hoặc hơn 30 ngày nữa thì chờ, tới giờ tự đăng / tới lúc vào khung 30 ngày thì giao.
4. Hiện lại bình luận đã ẩn tạm; đồng bộ bình luận mới + quy tắc tự động, vài phút/lần (services/comments.py)
5. Kiểm tra kết nối từng Page qua API, mỗi 6 giờ (domain/health.py)
6. Lấy chỉ số tương tác của bài đã đăng trong 14 ngày, mỗi bài 6 giờ/lần (domain/insights.py)
7. Bảo trì hằng ngày: sao lưu, dọn dữ liệu cũ (services/maintenance.py)

Thời điểm đăng do domain.planner quyết định (giãn cách tối thiểu, số bài tối đa mỗi ngày).
"""
from __future__ import annotations

from datetime import datetime

from ..domain import health, insights, planner
from ..domain.pages import page_of
from ..integrations.facebook import FBError
from ..domain.posts import ERROR, PENDING, RUNNING, label
from ..storage import Store, add_log, find
from ..utils import now_iso
from . import comments as comment_sync
from .comments import CommentSync
from .maintenance import Maintenance
from .publisher import Publisher
from .runtime import Runtime


class Scheduler:
    def __init__(self, store: Store, publisher: Publisher, runtime: Runtime, idle_seconds: float = 10.0,
                 maintenance: Maintenance | None = None):
        self.store = store
        self.comments = CommentSync(store, publisher)
        self.publisher = publisher
        self.maintenance = maintenance
        self.runtime = runtime
        self.idle_seconds = idle_seconds

    # ---------------------------------------------------------------- vòng lặp
    def run_forever(self) -> None:
        while True:
            try:
                busy = self.process_one()
            except Exception as e:  # noqa: BLE001 - luồng nền không được chết
                self.store.log("error", f"Lỗi luồng nền: {e}")
                busy = False
            if not busy:
                self.runtime.worker = "Đang rảnh"
                self.runtime.wake.wait(self.idle_seconds)
                self.runtime.wake.clear()

    def recover_running(self) -> None:
        """Bài đang 'running' khi tắt app -> đánh dấu lỗi để người dùng tự quyết định đăng lại."""
        with self.store.transaction() as data:
            for p in data["posts"]:
                if p["status"] == RUNNING:
                    p.update(status=ERROR, error="Ứng dụng bị tắt khi đang đăng - kiểm tra Page trước khi đăng lại")

    # ---------------------------------------------------------------- một lượt
    def process_one(self, now: datetime | None = None) -> bool:
        """Làm việc ưu tiên nhất đang có. Trả về True nếu đã làm một việc."""
        now = now or datetime.now()
        with self.store.transaction() as data:
            settings = data["settings"]
            job = self._pick(data, settings, now)
            if job:
                kind, post, when = job
                page = page_of(data, post) if post and kind != "unhide" else None
                if kind == "unhide":
                    page = next((p for p in data["pages"] if p["id"] == post.get("page")), None)
                if kind == "check":
                    post["last_check_at"] = now.isoformat(timespec="seconds")
                elif kind == "stats":  # đánh dấu đã thử, lỗi thì 6 giờ sau thử lại
                    post["stats"] = {**(post.get("stats") or {}), "fetched_at": now.isoformat(timespec="seconds")}
                elif kind == "comments":  # giữ chỗ: lỗi giữa chừng cũng không hỏi lại liên tục
                    comment_sync.state(data, page["id"])["last_at"] = now.isoformat(timespec="seconds")
                elif kind == "unhide":
                    post["unhide_at"] = None
                elif kind in ("publish", "handoff"):
                    post["status"] = RUNNING  # giữ chỗ, tránh xử lý trùng
        if not job:
            return False
        kind, post, when = job
        try:
            {"check": self._do_check, "handoff": self._do_handoff, "publish": self._do_publish,
             "health": self._do_health, "stats": self._do_stats,
             "comments": self._do_comments, "unhide": self._do_unhide,
             "maintenance": self._do_maintenance}[kind](post, page, settings, now, when)
        finally:
            self.runtime.worker = "Đang rảnh"
        return True

    def _pick(self, data: dict, settings: dict, now: datetime):
        posts = data["posts"]
        for p in posts:
            if self.publisher.needs_check(p, now):
                return "check", p, None
        page_key = lambda p: (page_of(data, p) or {}).get("id")  # noqa: E731 - giới hạn tính riêng từng Page
        plan = planner.plan(posts, settings, now, key=page_key)
        # sắp xếp ổn định: cùng thời điểm thì giữ thứ tự ưu tiên mà planner đã quyết định
        order = [(slot.effective, pid) for pid, slot in sorted(plan.items(), key=lambda kv: kv[1].effective)]
        for when, pid in order:
            if when <= now:
                return "publish", find(posts, pid), when
        for when, pid in order:
            post = find(posts, pid)
            if self.publisher.can_hand_off(when, page_of(data, post), settings, now):
                return "handoff", post, when
        for c in comment_sync.unhide_due(data, now):
            return "unhide", c, None
        for pg in data["pages"]:
            if comment_sync.due(data, pg, now):
                return "comments", {"id": None, "page": pg["id"]}, None
        for pg in data["pages"]:
            if health.due(data, pg, now):
                return "health", {"id": None, "page": pg["id"]}, None
        for p in posts:
            if insights.needs_refresh(p, now) and (page_of(data, p) or {}).get("kind") == "api":
                return "stats", p, None
        if self.maintenance and self.maintenance.due(data, now):
            return "maintenance", None, None
        return None

    # ---------------------------------------------------------------- các việc
    def _finish(self, post_id: str, fields: dict, level: str | None, text: str | None,
                page: dict | None = None, error: Exception | None = None) -> None:
        with self.store.transaction() as data:
            p = find(data["posts"], post_id)
            if p:
                p.update(fields)
            if level:
                add_log(data, level, text)
            self._note_health(data, page, error)

    @staticmethod
    def _note_health(data: dict, page: dict | None, error: Exception | None) -> None:
        """Kết quả đăng qua API cũng cho biết tình trạng kết nối -> cập nhật ngay, không chờ lượt kiểm tra."""
        if not page or page.get("kind") != "api":
            return
        now = datetime.now()
        if error is None:
            health.record(data, page["id"], True, now)
        elif isinstance(error, FBError) and health.is_connection_error(error.code):
            health.record(data, page["id"], False, now, health.describe(error.code, str(error)), error.code)

    def _do_publish(self, post: dict, page, settings: dict, now: datetime, when) -> None:
        self.runtime.worker = "Đang đăng: " + label(post)[:40]
        try:
            info = self.publisher.publish_now(post, page, settings)
            fb_id = self.publisher.last_fb_id
            if page:
                info = f"{info} · {page['name']}"
            self._finish(post["id"], {"status": "done", "done_at": now_iso(), "result": info, "error": "",
                                      **({"page": page["id"]} if page else {}), **({"fb_id": fb_id} if fb_id else {})},
                         "ok", f"Đã đăng: {label(post)} ({info})", page)
        except Exception as e:  # noqa: BLE001
            msg = health.describe(e.code, str(e)) if isinstance(e, FBError) else str(e)
            self._finish(post["id"], {"status": ERROR, "done_at": now_iso(), "error": msg}, "error", f"Lỗi khi đăng: {msg}", page, e)

    def _do_handoff(self, post: dict, page, settings: dict, now: datetime, when: datetime) -> None:
        self.runtime.worker = "Đang hẹn giờ trên Facebook: " + label(post)[:30]
        try:
            fields = self.publisher.hand_off(post, page, when)
            self._finish(post["id"], fields, "ok", f"Đã hẹn trên Facebook lúc {when:%H:%M %d/%m}: {label(post)}", page)
        except Exception as e:  # noqa: BLE001
            msg = health.describe(e.code, str(e)) if isinstance(e, FBError) else str(e)
            self._finish(post["id"], {"status": ERROR, "done_at": now_iso(), "error": f"Không hẹn được trên Facebook: {msg}"},
                         "error", f"Lỗi khi hẹn giờ trên Facebook: {msg}", page, e)

    def _do_check(self, post: dict, page, settings: dict, now: datetime, when) -> None:
        fields = self.publisher.check(post, page, now)
        status = fields.get("status")
        if status == "done":
            self._finish(post["id"], fields, "ok", f"Facebook đã đăng bài hẹn giờ: {label(post)}")
        elif status == ERROR:
            self._finish(post["id"], fields, "error", f"Bài hẹn giờ có vấn đề: {fields['error']}")
        else:
            self._finish(post["id"], fields, None, None)

    def _do_health(self, post, page, settings: dict, now: datetime, when) -> None:
        self.runtime.worker = f"Đang kiểm tra kết nối Page {page['name']}…"
        ok, err, code, name = self.publisher.check_page(page)
        with self.store.transaction() as data:
            before = health.of(data, page["id"])
            health.record(data, page["id"], ok, now, err, code)
            if not ok and (before is None or before.get("ok")):
                add_log(data, "error", f"Page “{page['name']}” mất kết nối: {err}")
            elif ok and before is not None and not before.get("ok"):
                add_log(data, "ok", f"Page “{page['name']}” đã kết nối lại bình thường")

    def _do_stats(self, post, page, settings: dict, now: datetime, when) -> None:
        self.runtime.worker = "Đang cập nhật thống kê: " + label(post)[:30]
        try:
            stats = self.publisher.fetch_stats(post, page, now)
        except FBError as e:
            if e.code in (100, 803):  # bài đã bị xoá trên Facebook -> thôi theo dõi
                self._finish(post["id"], {"stats": {**(post.get("stats") or {}), "fetched_at": now.isoformat(timespec="seconds"),
                                                    "gone": True}, "fb_id": None}, None, None)
            return
        self._finish(post["id"], {"stats": stats}, None, None)

    def _do_comments(self, post, page, settings: dict, now: datetime, when) -> None:
        self.runtime.worker = f"Đang đọc bình luận Page {page['name']}…"
        self.comments.sync(page, now)

    def _do_unhide(self, comment, page, settings: dict, now: datetime, when) -> None:
        self.runtime.worker = "Đang hiện lại bình luận đã ẩn tạm…"
        self.comments.unhide(comment, page, now)

    def _do_maintenance(self, post, page, settings: dict, now: datetime, when) -> None:
        self.runtime.worker = "Đang sao lưu & dọn dữ liệu…"
        self.maintenance.run(now)


__all__ = ["Scheduler", "PENDING"]
