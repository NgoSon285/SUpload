"""Ghép các phần của ứng dụng (application factory + dependency injection)."""
from __future__ import annotations

import os
import threading
import webbrowser
from dataclasses import dataclass

from flask import Flask

from . import api
from .config import MAX_UPLOAD_BYTES, Config
from .instance import AlreadyRunning, SingleInstance
from .services.maintenance import Maintenance
from .services.publisher import Publisher
from .services.runtime import Runtime
from .services.scheduler import Scheduler
from .storage import Store


@dataclass
class Services:
    config: Config
    store: Store
    runtime: Runtime
    publisher: Publisher
    scheduler: Scheduler
    maintenance: Maintenance


def create_app(config: Config | None = None) -> Flask:
    config = config or Config()
    app = Flask(__name__, static_folder=str(config.web_dir / "assets"), static_url_path="/assets")
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    store = Store(config.data_file)
    runtime = Runtime()
    publisher = Publisher(config, runtime)
    maintenance = Maintenance(store, config)
    scheduler = Scheduler(store, publisher, runtime, config.worker_idle_seconds, maintenance)
    app.extensions["supload"] = Services(config, store, runtime, publisher, scheduler, maintenance)
    api.register(app)
    return app


def main(argv: list[str] | None = None) -> None:
    import sys

    args = sys.argv[1:] if argv is None else argv
    if "--no-browser" in args:  # chạy ẩn (tự khởi động cùng Windows)
        os.environ["NO_BROWSER"] = "1"
    config = Config()
    port = int(os.getenv("PORT", "5000"))
    try:
        instance = SingleInstance(config.base_dir / "supload.lock", port).acquire()
    except AlreadyRunning as e:
        print(f"{e}. Mở lại giao diện đang chạy thay vì chạy thêm (tránh đăng trùng bài).")
        if e.port and not os.getenv("NO_BROWSER"):
            webbrowser.open(f"http://127.0.0.1:{e.port}")
        raise SystemExit(1) from None

    app = create_app(config)
    s: Services = app.extensions["supload"]
    s.scheduler.recover_running()
    threading.Thread(target=s.scheduler.run_forever, daemon=True, name="supload-worker").start()
    if not os.getenv("NO_BROWSER"):
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    print(f"SUpload đang chạy tại http://127.0.0.1:{port}  (Ctrl+C để thoát)")
    try:
        app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
    finally:
        instance.release()
