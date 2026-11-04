"""Đảm bảo chỉ một SUpload chạy trên cùng thư mục dữ liệu.

Hai phiên cùng đọc/ghi data.json sẽ cùng đăng một bài (khoá trong bộ nhớ không thấy được nhau),
nên khi khởi động ta giữ một khoá file của hệ điều hành. Khoá tự nhả khi tiến trình kết thúc,
kể cả khi bị tắt đột ngột.
"""
from __future__ import annotations

import os
from pathlib import Path

if os.name == "nt":  # Windows
    import msvcrt

    def _lock(fh) -> bool:
        try:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    def _unlock(fh) -> None:
        try:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:  # macOS / Linux
    import fcntl

    def _lock(fh) -> bool:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _unlock(fh) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


class AlreadyRunning(RuntimeError):
    def __init__(self, port: int | None):
        super().__init__(f"SUpload đã chạy ở cửa sổ khác (cổng {port})" if port else "SUpload đã chạy ở cửa sổ khác")
        self.port = port


class SingleInstance:
    """`with SingleInstance(path, port):` giữ khoá trong suốt thời gian chạy; ném AlreadyRunning nếu bị giữ."""

    def __init__(self, path: Path, port: int):
        self.path = Path(path)
        self.port = port
        self._fh = None

    def acquire(self) -> "SingleInstance":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+", encoding="utf-8")
        if not _lock(fh):
            fh.seek(0)
            other = fh.read().strip()
            fh.close()
            raise AlreadyRunning(int(other) if other.isdigit() else None)
        # ghi cổng đang chạy để lần mở sau biết đường chỉ tới
        fh.seek(0)
        fh.truncate()
        fh.write(" " + str(self.port))  # byte 0 là vùng bị khoá trên Windows
        fh.flush()
        self._fh = fh
        return self

    def release(self) -> None:
        if self._fh:
            _unlock(self._fh)
            self._fh.close()
            self._fh = None

    __enter__ = acquire

    def __exit__(self, *exc) -> None:
        self.release()
