"""Chặn chạy 2 SUpload cùng lúc trên một thư mục dữ liệu."""
import os
import subprocess
import sys
import time

import pytest

from conftest import ROOT
from supload.instance import AlreadyRunning, SingleInstance


def test_second_instance_is_refused_and_told_the_port(tmp_path):
    lock = tmp_path / "supload.lock"
    with SingleInstance(lock, 5000):
        with pytest.raises(AlreadyRunning) as e:
            SingleInstance(lock, 5001).acquire()
        assert e.value.port == 5000
    # nhả khoá -> chạy lại được
    with SingleInstance(lock, 5002):
        pass


def test_real_second_process_exits_without_starting(tmp_path):
    """Chạy thật 2 tiến trình `python app.py` trên cùng thư mục dữ liệu."""
    code = "import sys; sys.path.insert(0, %r); from supload import main; main()" % str(ROOT)
    env = {**os.environ, "NO_BROWSER": "1", "PORT": "5391", "SUPLOAD_HOME": str(tmp_path)}
    first = subprocess.Popen([sys.executable, "-c", code], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(50):
            if (tmp_path / "supload.lock").exists() and (tmp_path / "supload.lock").read_text().strip():
                break
            time.sleep(0.1)
        second = subprocess.run([sys.executable, "-c", code], env={**env, "PORT": "5392"}, capture_output=True, text=True, timeout=30)
        assert second.returncode == 1
        assert "đã chạy ở cửa sổ khác (cổng 5391)" in second.stdout
        assert first.poll() is None  # phiên đầu vẫn chạy bình thường
    finally:
        first.terminate()
        first.wait(timeout=10)
