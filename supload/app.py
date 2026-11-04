"""Ghép các phần của ứng dụng (application factory + dependency injection)."""
from __future__ import annotations

import os
import threading
import webbrowser
from dataclasses import dataclass

from flask import Flask

from . import api
from .config import Config
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


def create_app(config: Config | None = None) -> Flask:
    config = config or Config()
    app = Flask(__name__, static_folder=str(config.web_dir / "assets"), static_url_path="/assets")
    store = Store(config.data_file)
    runtime = Runtime()
    publisher = Publisher(config, runtime)
    scheduler = Scheduler(store, publisher, runtime, config.worker_idle_seconds)
    app.extensions["supload"] = Services(config, store, runtime, publisher, scheduler)
    api.register(app)
    return app


def main() -> None:
    app = create_app()
    s: Services = app.extensions["supload"]
    s.scheduler.recover_running()
    threading.Thread(target=s.scheduler.run_forever, daemon=True, name="supload-worker").start()
    port = int(os.getenv("PORT", "5000"))
    if not os.getenv("NO_BROWSER"):
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    print(f"SUpload đang chạy tại http://127.0.0.1:{port}  (Ctrl+C để thoát)")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
