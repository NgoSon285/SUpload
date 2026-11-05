"""Điểm vào của bản đóng gói (SUpload.exe)."""
import sys
import traceback


def run() -> None:
    try:
        from supload import main

        main()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 - hiện lỗi thay vì cửa sổ tắt ngay
        traceback.print_exc()
        if sys.stdin and sys.stdin.isatty():
            input("\nSUpload gặp lỗi khi khởi động (xem ở trên). Nhấn Enter để đóng...")
        raise SystemExit(1) from None


if __name__ == "__main__":
    run()
