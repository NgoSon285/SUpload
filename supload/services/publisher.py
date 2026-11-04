"""Đăng bài thật lên một Page: qua Graph API hoặc trình duyệt; hẹn giờ / huỷ / đối soát trên Facebook."""
from __future__ import annotations

from datetime import datetime, timedelta

from ..config import Config
from ..domain.posts import DONE, ERROR, SCHEDULED
from ..domain.settings import has_api_credentials
from ..integrations import facebook
from ..utils import now_iso, parse_dt
from .runtime import Runtime

# Biên an toàn quanh giới hạn 10 phút – 30 ngày của Facebook
FB_MIN_LEAD = timedelta(minutes=12)
FB_MAX_LEAD = timedelta(days=29, hours=23)
CHECK_AFTER = timedelta(minutes=2)    # đối soát sau giờ hẹn bao lâu
CHECK_EVERY = timedelta(minutes=5)    # khoảng cách giữa 2 lần đối soát một bài
LATE_LIMIT = timedelta(hours=1)       # quá giờ hẹn bao lâu mà chưa lên thì báo lỗi
NOT_FOUND_CODES = {100, 803}          # bài không tồn tại / đã bị xoá
NO_PAGE = "Chưa kết nối Page nào: vào Cài đặt để thêm Page"


class Publisher:
    def __init__(self, config: Config, runtime: Runtime):
        self.config = config
        self.runtime = runtime

    # ---------------------------------------------------------------- helpers
    def _photos(self, post: dict) -> list[str]:
        return [str(self.config.upload_dir / f) for f in post.get("photos", [])]

    @staticmethod
    def poster(page: dict | None) -> facebook.PagePoster:
        if not page:
            raise facebook.FBError(NO_PAGE)
        return facebook.PagePoster(page.get("fb_page_id", ""), page.get("token", ""))

    # ---------------------------------------------------------------- đăng ngay
    def publish_now(self, post: dict, page: dict | None, settings: dict) -> str:
        if not page:
            raise ValueError(NO_PAGE)
        if page["kind"] == "api":
            res = self.poster(page).post(message=post.get("message", ""), link=post.get("link") or None, photos=self._photos(post))
            return f"id={res.get('post_id') or res.get('id')}"
        return self._publish_browser(post, page, settings)

    def _publish_browser(self, post: dict, page: dict, settings: dict) -> str:
        from ..integrations import browser  # chỉ cần playwright khi dùng cách này

        if not page.get("url"):
            raise browser.PostError("Page này chưa có địa chỉ facebook.com/…")
        browser.configure(self.config.profile_dir, self.config.screenshot_dir)
        message = post.get("message", "")
        if post.get("link"):
            message = f"{message}\n{post['link']}".strip()
        with self.runtime.browser_lock:
            self.runtime.worker = f"Đang đăng qua trình duyệt lên {page['name']}..."
            browser.post_once(page["url"], message, self._photos(post), settings.get("headless", False))
        return "đã đăng qua trình duyệt"

    # ---------------------------------------------------------------- hẹn giờ trên Facebook
    @staticmethod
    def fb_scheduling_enabled(page: dict | None, settings: dict) -> bool:
        return bool(settings.get("fb_schedule")) and has_api_credentials(page)

    @classmethod
    def can_hand_off(cls, when: datetime, page: dict | None, settings: dict, now: datetime) -> bool:
        """Bài đăng lúc `when` lên `page` có giao được cho Facebook tự đăng không."""
        return cls.fb_scheduling_enabled(page, settings) and FB_MIN_LEAD <= when - now <= FB_MAX_LEAD

    def hand_off(self, post: dict, page: dict, when: datetime) -> dict:
        """Gửi bài lên Facebook ở chế độ hẹn giờ. Trả về các trường cần cập nhật cho bài."""
        res = self.poster(page).post(message=post.get("message", ""), link=post.get("link") or None,
                                     photos=self._photos(post), schedule=when)
        fb_id = res.get("post_id") or res.get("id")
        return {"status": SCHEDULED, "fb_id": fb_id, "fb_scheduled_at": when.isoformat(timespec="seconds"),
                "page": page["id"], "result": f"đã hẹn trên Facebook (id={fb_id})", "error": ""}

    def cancel(self, post: dict, page: dict | None) -> None:
        """Huỷ bài đã hẹn trên Facebook. Bài đã không còn trên Facebook thì coi như đã huỷ."""
        if post.get("status") != SCHEDULED or not post.get("fb_id"):
            return
        try:
            self.poster(page).delete(post["fb_id"])
        except facebook.FBError as e:
            if e.code not in NOT_FOUND_CODES:
                raise

    # ---------------------------------------------------------------- tình trạng kết nối
    def check_page(self, page: dict) -> tuple[bool, str, int | None, str]:
        """Thử kết nối Page qua API. Trả về (ok, lỗi dễ hiểu, mã lỗi, tên Page lấy được)."""
        from ..domain.health import describe

        try:
            info = facebook.page_info(page["fb_page_id"], page["token"])
            return True, "", None, info.get("name", "")
        except facebook.FBError as e:
            return False, describe(e.code, str(e)), e.code, ""

    # ---------------------------------------------------------------- đối soát
    @staticmethod
    def needs_check(post: dict, now: datetime) -> bool:
        if post.get("status") != SCHEDULED or not post.get("fb_scheduled_at"):
            return False
        if now < parse_dt(post["fb_scheduled_at"]) + CHECK_AFTER:
            return False
        last = parse_dt(post.get("last_check_at"))
        return last is None or now - last >= CHECK_EVERY

    def check(self, post: dict, page: dict | None, now: datetime) -> dict:
        """Hỏi Facebook xem bài hẹn đã lên chưa. Trả về các trường cần cập nhật."""
        when = parse_dt(post["fb_scheduled_at"])
        try:
            published = self.poster(page).is_published(post["fb_id"])
        except facebook.FBError as e:
            if e.code in NOT_FOUND_CODES:
                return {"status": ERROR, "done_at": now_iso(),
                        "error": "Không còn thấy bài hẹn trên Facebook (có thể đã bị xoá trên Facebook)"}
            return {"last_check_at": now.isoformat(timespec="seconds"), "error": f"Chưa kiểm tra được: {e}"}
        if published:
            return {"status": DONE, "done_at": when.isoformat(timespec="seconds"), "error": "",
                    "result": f"Facebook đã đăng (id={post['fb_id']})"}
        if now - when > LATE_LIMIT:
            return {"status": ERROR, "done_at": now_iso(),
                    "error": "Đã quá giờ hẹn hơn 1 giờ nhưng Facebook vẫn chưa đăng bài. Kiểm tra mục Bài đã lên lịch trên Page."}
        return {"last_check_at": now.isoformat(timespec="seconds")}
