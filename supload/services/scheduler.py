"""Luồng chạy nền: mỗi lượt làm tối đa MỘT việc, theo thứ tự ưu tiên:

1. Đối soát bài đã hẹn trên Facebook (đã lên chưa?)
2. Tự đăng bài đã đến giờ (việc gấp nhất về thời gian)
3. Giao bài sắp tới (trong 12 phút – 30 ngày) cho Facebook tự đăng   [cách API + bật hẹn giờ FB]
   Bài còn dưới 12 phút hoặc hơn 30 ngày nữa thì chờ, tới giờ tự đăng / tới lúc vào khung 30 ngày thì giao.
4. Bảo trì hằng ngày: sao lưu, dọn dữ liệu cũ (services/maintenance.py)

Thời điểm đăng do domain.planner quyết định (giãn cách tối thiểu, số bài tối đa mỗi ngày).
"""
from __future__ import annotations

from datetime import datetime

from ..domain import planner
from ..domain.posts import ERROR, PENDING, RUNNING, label
from ..storage import Store, add_log, find
from ..utils import now_iso
from .maintenance import Maintenance
from .publisher import Publisher
from .runtime import Runtime


class Scheduler:
    def __init__(self, store: Store, publisher: Publisher, runtime: Runtime, idle_seconds: float = 10.0,
                 maintenance: Maintenance | None = None):
        self.store = store
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
                if kind == "check":
                    post["last_check_at"] = now.isoformat(timespec="seconds")
                elif kind in ("publish", "handoff"):
                    post["status"] = RUNNING  # giữ chỗ, tránh xử lý trùng
        if not job:
            return False
        kind, post, when = job
        try:
            {"check": self._do_check, "handoff": self._do_handoff, "publish": self._do_publish,
             "maintenance": self._do_maintenance}[kind](post, settings, now, when)
        finally:
            self.runtime.worker = "Đang rảnh"
        return True

    def _pick(self, data: dict, settings: dict, now: datetime):
        posts = data["posts"]
        for p in posts:
            if self.publisher.needs_check(p, now):
                return "check", p, None
        plan = planner.plan(posts, settings, now)
        # sắp xếp ổn định: cùng thời điểm thì giữ thứ tự ưu tiên mà planner đã quyết định
        order = [(slot.effective, pid) for pid, slot in sorted(plan.items(), key=lambda kv: kv[1].effective)]
        for when, pid in order:
            if when <= now:
                return "publish", find(posts, pid), when
        for when, pid in order:
            if self.publisher.can_hand_off(when, settings, now):
                return "handoff", find(posts, pid), when
        if self.maintenance and self.maintenance.due(data, now):
            return "maintenance", None, None
        return None

    # ---------------------------------------------------------------- các việc
    def _finish(self, post_id: str, fields: dict, level: str | None, text: str | None) -> None:
        with self.store.transaction() as data:
            p = find(data["posts"], post_id)
            if p:
                p.update(fields)
            if level:
                add_log(data, level, text)

    def _do_publish(self, post: dict, settings: dict, now: datetime, when) -> None:
        self.runtime.worker = "Đang đăng: " + label(post)[:40]
        try:
            info = self.publisher.publish_now(post, settings)
            self._finish(post["id"], {"status": "done", "done_at": now_iso(), "result": info, "error": ""},
                         "ok", f"Đã đăng: {label(post)} ({info})")
        except Exception as e:  # noqa: BLE001
            self._finish(post["id"], {"status": ERROR, "done_at": now_iso(), "error": str(e)}, "error", f"Lỗi khi đăng: {e}")

    def _do_handoff(self, post: dict, settings: dict, now: datetime, when: datetime) -> None:
        self.runtime.worker = "Đang hẹn giờ trên Facebook: " + label(post)[:30]
        try:
            fields = self.publisher.hand_off(post, settings, when)
            self._finish(post["id"], fields, "ok", f"Đã hẹn trên Facebook lúc {when:%H:%M %d/%m}: {label(post)}")
        except Exception as e:  # noqa: BLE001
            self._finish(post["id"], {"status": ERROR, "done_at": now_iso(), "error": f"Không hẹn được trên Facebook: {e}"},
                         "error", f"Lỗi khi hẹn giờ trên Facebook: {e}")

    def _do_check(self, post: dict, settings: dict, now: datetime, when) -> None:
        fields = self.publisher.check(post, settings, now)
        status = fields.get("status")
        if status == "done":
            self._finish(post["id"], fields, "ok", f"Facebook đã đăng bài hẹn giờ: {label(post)}")
        elif status == ERROR:
            self._finish(post["id"], fields, "error", f"Bài hẹn giờ có vấn đề: {fields['error']}")
        else:
            self._finish(post["id"], fields, None, None)

    def _do_maintenance(self, post, settings: dict, now: datetime, when) -> None:
        self.runtime.worker = "Đang sao lưu & dọn dữ liệu…"
        self.maintenance.run(now)


__all__ = ["Scheduler", "PENDING"]
