"""Tải ảnh từ link về thư mục uploads/ (dùng khi nhập bài từ bảng tính)."""
from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import urlparse

import requests
from werkzeug.utils import secure_filename

from ..config import ALLOWED_IMAGE_EXT
from ..utils import new_id

MAX_BYTES = 15 * 1024 * 1024


def fetch(url: str) -> tuple[bytes, str]:
    """Tải nội dung (bytes, content-type). Tách riêng để test thay bằng bản giả."""
    with requests.get(url, timeout=30, stream=True) as r:
        r.raise_for_status()
        data = b""
        for chunk in r.iter_content(65536):
            data += chunk
            if len(data) > MAX_BYTES:
                raise ValueError("Ảnh lớn hơn 15 MB")
        return data, r.headers.get("Content-Type", "")


def download_image(url: str, upload_dir: Path) -> str:
    """Tải ảnh về uploads/, trả về tên file. Ném ValueError nếu không phải ảnh hợp lệ."""
    try:
        data, ctype = fetch(url)
    except requests.RequestException as e:
        raise ValueError(f"Không tải được ảnh {url}: {e}") from None
    ext = Path(urlparse(url).path).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXT:
        ext = mimetypes.guess_extension((ctype or "").split(";")[0].strip()) or ""
        ext = ".jpg" if ext == ".jpe" else ext
    if ext not in ALLOWED_IMAGE_EXT or not (ctype or "image/").startswith("image/"):
        raise ValueError(f"Link không phải ảnh JPG/PNG/GIF/WEBP: {url}")
    stem = secure_filename(Path(urlparse(url).path).stem) or "anh"
    name = f"{new_id(n=8)}_{stem[:40]}{ext}"
    (upload_dir / name).write_bytes(data)
    return name
