"""Kiểm thử đầu-cuối: chạy Flask + giao diện React đã build, điều khiển bằng Playwright.

Bỏ qua nếu chưa cài playwright/chromium hoặc chưa build giao diện (web/index.html).
"""
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from conftest import PNG, ROOT

pw_api = pytest.importorskip("playwright.sync_api")
if not (ROOT / "web" / "index.html").exists():
    pytest.skip("Chưa build giao diện (cd frontend && npm run build)", allow_module_level=True)


@pytest.fixture(scope="module")
def browser():
    with pw_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"Không mở được Chromium: {e}")
        yield b
        b.close()


@pytest.fixture
def server(appmod):
    from werkzeug.serving import make_server

    srv = make_server("127.0.0.1", 0, appmod.app, threaded=True)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture
def page(browser, server):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and pg.errors.append(m.text))
    pg.base = server
    yield pg
    ctx.close()


def api_state(page):
    return json.loads(page.evaluate("fetch('/api/state').then(r => r.text())"))


def nav(page, label):
    page.locator(".mantine-NavLink-root", has_text=label).click()
    page.wait_for_timeout(300)


def connect(page):
    page.request.post(page.base + "/api/settings", data={"method": "api", "page_id": "111", "page_token": "tok"})


def test_first_run_opens_settings_and_connects(page):
    page.goto(page.base)
    page.get_by_text("Kết nối Page qua API").wait_for()
    page.get_by_text("Nhập Page ID / Page Token thủ công").click()
    page.get_by_role("textbox", name="Page ID").fill("111")
    page.get_by_role("textbox", name="Page Access Token").fill("SECRET")
    page.get_by_role("button", name="Lưu cài đặt").click()
    page.get_by_role("button", name="Kiểm tra kết nối").click()
    page.get_by_text("Kết nối tốt tới Page “Page Một”").wait_for()
    assert "SECRET" not in page.content()
    assert page.errors == []


def test_compose_schedule_and_post_now(page, appmod, tmp_path):
    connect(page)
    page.goto(page.base)
    nav(page, "Soạn bài")
    img = tmp_path / "anh.png"
    img.write_bytes(PNG)

    # bài hẹn giờ có ảnh
    page.get_by_label("Nội dung").fill("Khuyến mãi cuối tuần 🎉")
    page.locator("input[type=file]").first.set_input_files(str(img))
    page.locator(".thumb").first.wait_for()
    page.get_by_text("Hẹn giờ", exact=True).click()
    page.get_by_text("Sẽ đăng lúc").wait_for()
    page.get_by_role("button", name="Lên lịch").click()
    page.get_by_text("Đã lên lịch").wait_for()

    # bài đăng ngay
    page.get_by_text("Đăng ngay", exact=True).first.click()
    page.get_by_label("Nội dung").fill("Đăng liền")
    page.keyboard.press("Control+Enter")
    page.get_by_text("Đang đăng bài").wait_for()

    posts = {p["message"]: p for p in api_state(page)["posts"]}
    assert posts["Khuyến mãi cuối tuần 🎉"]["scheduled_at"] and len(posts["Khuyến mãi cuối tuần 🎉"]["photos"]) == 1
    assert posts["Đăng liền"]["scheduled_at"] is None

    assert appmod.process_one() is True  # luồng nền đăng bài đến hạn
    nav(page, "Lịch đăng")
    page.get_by_text("Đã đăng (1)").wait_for(timeout=5000)
    assert page.errors == []


def test_edit_post_from_queue(page):
    connect(page)
    future = (datetime.now() + timedelta(days=2)).isoformat(timespec="minutes")
    page.request.post(page.base + "/api/posts", data={"message": "Bản gốc", "scheduled_at": future})
    page.goto(page.base)
    nav(page, "Lịch đăng")
    page.get_by_role("button", name="Sửa").first.click()
    page.get_by_text("Đang sửa một bài trong lịch đăng").wait_for()
    page.get_by_label("Nội dung").fill("Đã chỉnh sửa")
    page.get_by_role("button", name="Lưu thay đổi").click()
    page.get_by_text("Đã chỉnh sửa").wait_for()
    p = api_state(page)["posts"][0]
    assert p["message"] == "Đã chỉnh sửa" and p["scheduled_at"] == future
    assert page.errors == []


def test_flow_builder_runs_sample(page):
    connect(page)
    page.goto(page.base)
    nav(page, "Flow chiến dịch")
    page.locator(".react-flow__node").first.wait_for()
    assert page.locator(".react-flow__node").count() == 6  # flow mẫu
    # thêm khối Lặp lại vào sau khối đang chọn (khối cuối)
    page.locator(".palette-item", has_text="Lặp lại").click()
    page.get_by_text("Số lần").wait_for()
    assert page.locator(".react-flow__node").count() == 7
    badge = page.get_by_test_id("flow-count").inner_text()
    n_posts = int(badge.split()[0])
    assert n_posts == 4
    page.get_by_role("button", name="Chạy flow").click()
    page.get_by_role("button", name=f"Lên lịch {n_posts} bài").click()
    page.get_by_text(f"Đã lên lịch {n_posts} bài").wait_for()
    posts = api_state(page)["posts"]
    assert len(posts) == n_posts and all(p["flow"] == "Chiến dịch mẫu" for p in posts)
    assert any("#tiembanh" in p["message"] for p in posts)  # khối Định dạng được áp dụng
    page.wait_for_timeout(1500)  # tự lưu sau 0,7 giây không thay đổi
    flows = json.loads(page.evaluate("fetch('/api/flows').then(r => r.text())"))["flows"]
    assert len(flows) == 1 and len(flows[0]["nodes"]) == 7  # tự lưu
    assert page.errors == []


def test_flow_changes_saved_when_leaving_page_immediately(page):
    page.goto(page.base)
    nav(page, "Flow chiến dịch")
    page.locator(".react-flow__node").first.wait_for()
    page.locator(".palette-item", has_text="Định dạng").click()
    nav(page, "Nhật ký")  # rời trang ngay, chưa tới 0,7 giây
    page.wait_for_timeout(500)
    flows = json.loads(page.evaluate("fetch('/api/flows').then(r => r.text())"))["flows"]
    assert len(flows[0]["nodes"]) == 7
    assert page.errors == []


@pytest.mark.parametrize("view", ["compose", "queue", "flow", "log", "settings"])
def test_mobile_layout_has_no_horizontal_scroll(browser, server, view):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, color_scheme="dark")
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(server)
    pg.evaluate(f"localStorage.setItem('view', JSON.stringify('{view}'))")
    pg.reload()
    pg.wait_for_timeout(1000)
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert errors == []
    ctx.close()
