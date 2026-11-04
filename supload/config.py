"""Cấu hình ứng dụng: đường dẫn & cài đặt mặc định. Không dùng biến toàn cục để test tách biệt được."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def default_settings() -> dict:
    """Cài đặt mặc định. Giá trị trong .env (FB_*) được dùng khi chưa cấu hình trên giao diện."""
    return {
        # kết nối (danh sách Page nằm ở data["pages"], xem domain/pages.py)
        "default_page": "",
        "app_id": os.getenv("FB_APP_ID", ""),  # dùng để lấy danh sách Page từ User Token
        "app_secret": os.getenv("FB_APP_SECRET", ""),
        "headless": False,  # cách Trình duyệt: chạy ẩn
        # hẹn giờ trên Facebook (chỉ cách API)
        "fb_schedule": True,
        # giới hạn an toàn (cả hai cách)
        "min_gap": 300,  # giây tối thiểu giữa 2 bài
        "daily_max": 20,  # số bài tối đa mỗi ngày, 0 = không giới hạn
        # dữ liệu
        "keep_done_days": 90,  # tự xoá bài đã đăng sau N ngày, 0 = giữ mãi
    }


SECRET_KEYS = ("app_secret",)


def data_home() -> Path:
    """Thư mục dữ liệu: biến môi trường SUPLOAD_HOME nếu có, mặc định là thư mục dự án."""
    return Path(os.getenv("SUPLOAD_HOME") or ROOT)


@dataclass
class Config:
    base_dir: Path = field(default_factory=data_home)
    data_file: Path = field(default=None)  # type: ignore[assignment]
    upload_dir: Path = field(default=None)  # type: ignore[assignment]
    web_dir: Path = field(default=None)  # type: ignore[assignment]
    profile_dir: Path = field(default=None)  # type: ignore[assignment]
    screenshot_dir: Path = field(default=None)  # type: ignore[assignment]
    worker_idle_seconds: float = 10.0
    start_worker: bool = True

    def __post_init__(self):
        b = Path(self.base_dir)
        self.base_dir = b
        self.data_file = Path(self.data_file or b / "data.json")
        self.upload_dir = Path(self.upload_dir or b / "uploads")
        self.web_dir = Path(self.web_dir or ROOT / "web")
        self.profile_dir = Path(self.profile_dir or b / "fb_profile")
        self.screenshot_dir = Path(self.screenshot_dir or b / "screenshots")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
