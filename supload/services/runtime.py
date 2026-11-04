"""Trạng thái trong bộ nhớ của tiến trình (không lưu xuống đĩa)."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class Runtime:
    worker: str = "Đang rảnh"
    login: str = "unknown"
    wake: threading.Event = field(default_factory=threading.Event)
    browser_lock: threading.Lock = field(default_factory=threading.Lock)  # 1 thao tác trình duyệt mỗi lúc

    def notify(self) -> None:
        """Đánh thức luồng nền (có bài mới / bài vừa sửa)."""
        self.wake.set()
