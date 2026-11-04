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
def server(app):
    from werkzeug.serving import make_server

    srv = make_server("127.0.0.1", 0, app, threaded=True)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture
def page(browser, server, request):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and pg.errors.append(m.text))
    pg.base = server
    yield pg
    rep = getattr(request.node, "rep_call", None)
    if rep is not None and rep.failed:  # chụp màn hình khi lỗi để dễ tìm nguyên nhân
        out = ROOT / "test-results"
        out.mkdir(exist_ok=True)
        pg.screenshot(path=str(out / f"{request.node.name}.png"), full_page=True)
    ctx.close()


def api_state(page):
    return json.loads(page.evaluate("fetch('/api/state').then(r => r.text())"))


def nav(page, label):
    page.locator(".mantine-NavLink-root", has_text=label).click()
    page.wait_for_timeout(300)


def connect(page):
    page.request.post(page.base + "/api/settings", data={"method": "api", "page_id": "111", "page_token": "tok", "min_gap": 0, "daily_max": 0})


def test_first_run_opens_settings_and_connects(page):
    page.goto(page.base)
    page.get_by_text("Kết nối Page qua API").wait_for()
    page.get_by_text("Nhập Page ID / Page Token thủ công").click()
    page.get_by_role("textbox", name="Page ID").fill("111")
    page.get_by_role("textbox", name="Page Access Token").fill("SECRET")
    save = page.get_by_role("button", name="Lưu cài đặt")
    save.click()
    save.wait_for(state="detached")  # đã lưu -> thanh biến mất
    page.get_by_role("button", name="Kiểm tra kết nối").click()
    page.get_by_text("Kết nối tốt tới Page “Page Một”").wait_for()
    assert "SECRET" not in page.content()
    assert page.errors == []


def test_compose_schedule_and_post_now(page, svc, tmp_path):
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

    assert svc.scheduler.process_one() is True  # luồng nền đăng bài đến hạn
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
    page.get_by_text("Đã lưu thay đổi").wait_for()
    page.get_by_role("heading", name="Lịch đăng").wait_for()  # tự quay về Lịch đăng
    p = api_state(page)["posts"][0]
    assert p["message"] == "Đã chỉnh sửa" and p["scheduled_at"] == future
    assert page.errors == []


START = [{"id": "s", "type": "start", "position": {"x": 0, "y": 0}, "data": {}, "deletable": False}]


def put_flow(page, fid, name, description=""):
    r = page.request.put(f"{page.base}/api/flows/{fid}", data={"name": name, "description": description, "nodes": START, "edges": []})
    assert r.ok


def card_action(page, name, item):
    """Mở menu ⋯ của đúng thẻ flow, chọn mục, rồi chờ menu đóng hẳn."""
    trigger = page.get_by_role("button", name=f"Thao tác với {name}", exact=True)
    trigger.click()
    menu = page.locator(f'[role=menu][aria-labelledby="{trigger.get_attribute("id")}"]')
    menu.get_by_role("menuitem", name=item).click()
    menu.wait_for(state="detached")


def api_flows(page):
    return json.loads(page.evaluate("fetch('/api/flows').then(r => r.text())"))["flows"]


def test_create_flow_from_template_and_run(page):
    connect(page)
    page.goto(page.base)
    nav(page, "Flow chiến dịch")
    page.get_by_text("Chưa có flow nào").wait_for()
    page.get_by_role("button", name="Tạo flow đầu tiên").click()
    page.get_by_label("Tên flow").fill("Chiến dịch Tết")
    page.get_by_label("Mô tả").fill("Đăng mỗi sáng")
    page.get_by_role("button", name="Tạo và mở").click()

    page.locator(".react-flow__node").first.wait_for()
    assert page.locator(".react-flow__node").count() == 6  # mẫu chiến dịch
    page.locator(".palette-item", has_text="Lặp lại").click()
    page.get_by_text("Số lần").wait_for()
    assert page.locator(".react-flow__node").count() == 7
    n_posts = int(page.get_by_test_id("flow-count").inner_text().split()[0])
    assert n_posts == 4
    page.get_by_role("button", name="Chạy flow").click()
    page.get_by_role("button", name=f"Lên lịch {n_posts} bài").click()
    page.get_by_text(f"Đã lên lịch {n_posts} bài").wait_for()
    page.get_by_role("button", name="Ở lại").click()

    posts = api_state(page)["posts"]
    fid = api_flows(page)[0]["id"]
    assert len(posts) == n_posts and all(p["flow"] == "Chiến dịch Tết" and p["flow_id"] == fid for p in posts)
    assert any("#tiembanh" in p["message"] for p in posts)  # khối Định dạng được áp dụng

    # quay lại danh sách: thẻ flow hiển thị thống kê
    page.get_by_role("button", name="Tất cả flow").click()
    card = page.get_by_test_id("flow-card").first
    card.get_by_text("Đăng mỗi sáng").wait_for()
    assert f"{n_posts} bài" in card.inner_text() and "đang chờ" in card.inner_text()
    assert len(api_flows(page)[0]["nodes"]) == 7  # đã lưu
    assert page.errors == []


def test_manage_many_flows(page, tmp_path):
    for i, name in enumerate(["Khuyến mãi", "Tuyển dụng", "Sự kiện"]):
        put_flow(page, f"f_{i}", name, f"mô tả {name}")
    page.goto(page.base)
    nav(page, "Flow chiến dịch")
    cards = page.get_by_test_id("flow-card")
    cards.first.wait_for()
    assert cards.count() == 3

    # tìm kiếm
    page.get_by_label("Tìm flow").fill("tuyển")
    assert cards.count() == 1 and "Tuyển dụng" in cards.first.inner_text()
    page.get_by_label("Tìm flow").fill("")

    # đổi tên & mô tả
    card_action(page, "Sự kiện", "Đổi tên & mô tả")
    page.get_by_label("Tên flow").fill("Sự kiện cuối năm")
    page.get_by_role("button", name="Lưu", exact=True).click()
    page.get_by_text("Sự kiện cuối năm", exact=True).wait_for()

    # nhân bản
    card_action(page, "Khuyến mãi", "Nhân bản")
    page.get_by_text("Khuyến mãi (bản sao)", exact=True).wait_for()
    assert cards.count() == 4
    assert page.locator("[role=menu]").count() == 0  # menu tự đóng sau khi chọn

    # xuất file rồi nhập lại
    with page.expect_download() as dl:
        card_action(page, "Tuyển dụng", "Xuất file")
    path = tmp_path / "flow.json"
    dl.value.save_as(path)
    exported = json.loads(path.read_text(encoding="utf-8"))
    assert exported["format"] == "supload-flow" and exported["name"] == "Tuyển dụng"
    page.locator("input[type=file]").set_input_files(str(path))
    page.get_by_text("Đã nhập flow “Tuyển dụng”").wait_for()
    assert cards.count() == 5

    # xoá
    card_action(page, "Khuyến mãi (bản sao)", "Xoá")
    page.get_by_role("button", name="Xoá flow").click()
    page.get_by_text("Đã xoá flow").wait_for()
    assert cards.count() == 4
    names = sorted(f["name"] for f in api_flows(page))
    assert names == ["Khuyến mãi", "Sự kiện cuối năm", "Tuyển dụng", "Tuyển dụng"]
    assert page.errors == []


def test_delete_flow_with_waiting_posts(page):
    connect(page)
    put_flow(page, "f_x", "Có bài chờ")
    future = (datetime.now() + timedelta(days=1)).isoformat(timespec="minutes")
    page.request.post(page.base + "/api/flows/run", data={"flow_id": "f_x", "name": "Có bài chờ", "posts": [{"message": "a", "scheduled_at": future}, {"message": "b", "scheduled_at": future}]})
    page.goto(page.base)
    nav(page, "Flow chiến dịch")
    card_action(page, "Có bài chờ", "Xoá")
    page.get_by_label("Xoá luôn 2 bài chưa đăng do flow này tạo trong Lịch đăng").wait_for()
    page.get_by_role("button", name="Xoá flow").click()
    page.get_by_text("Đã xoá flow và 2 bài chưa đăng").wait_for()
    assert api_state(page)["posts"] == []
    assert page.errors == []


def test_flow_changes_saved_when_leaving_page_immediately(page):
    put_flow(page, "f_y", "Lưu nhanh")
    page.goto(page.base)
    nav(page, "Flow chiến dịch")
    page.get_by_test_id("flow-card").get_by_role("button", name="Mở").click()
    page.locator(".react-flow__node").first.wait_for()
    page.locator(".palette-item", has_text="Định dạng").click()
    nav(page, "Nhật ký")  # rời trang ngay, chưa tới 0,7 giây
    page.wait_for_timeout(500)
    assert len(api_flows(page)[0]["nodes"]) == 2
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


# ---------------------------------------------------------------- hẹn giờ Facebook & giới hạn an toàn
def settings(page, **body):
    assert page.request.post(page.base + "/api/settings", data=body).ok


def test_scheduled_post_is_handed_to_facebook_and_cancellable(page, svc, graph):
    connect(page)
    page.goto(page.base)
    nav(page, "Soạn bài")
    page.get_by_label("Nội dung").fill("Hẹn giờ trên Facebook")
    page.get_by_text("Hẹn giờ", exact=True).click()
    page.get_by_test_id("who-posts").get_by_text("Facebook tự đăng", exact=False).wait_for()
    page.get_by_role("button", name="Lên lịch").click()
    page.get_by_text("Đã lên lịch").wait_for()
    assert svc.scheduler.process_one() is True  # giao cho Facebook
    nav(page, "Lịch đăng")
    row = page.get_by_test_id("post-row").first
    row.get_by_text("Đã hẹn trên Facebook").wait_for()
    assert "Facebook sẽ tự đăng" in row.inner_text()
    row.get_by_role("button", name="Xoá").click()
    page.get_by_role("button", name="Huỷ & xoá").click()
    page.get_by_text("Đã huỷ bài hẹn trên Facebook").wait_for()
    assert graph.by("DELETE") and api_state(page)["posts"] == []
    assert page.errors == []


def test_safety_limits_settings_and_shift_reason(page, svc):
    connect(page)
    page.goto(page.base)
    nav(page, "Cài đặt")
    page.get_by_text("Giới hạn an toàn").wait_for()
    page.get_by_label("Số bài tối đa mỗi ngày").fill("1")
    save = page.get_by_role("button", name="Lưu cài đặt")
    save.click()
    save.wait_for(state="detached")
    assert svc.store.load()["settings"]["daily_max"] == 1
    settings(page, fb_schedule=False)
    for m in ("Bài 1", "Bài 2"):
        page.request.post(page.base + "/api/posts", data={"message": m})
    svc.scheduler.process_one()
    nav(page, "Lịch đăng")
    page.get_by_test_id("shift-reason").get_by_text("đã đủ 1 bài/ngày", exact=False).wait_for()
    page.get_by_text("1/1").wait_for()  # thẻ "Bài hôm nay / giới hạn"
    nav(page, "Cài đặt")
    assert "Hôm nay: 1 / 1 bài" in page.get_by_test_id("limits-today").inner_text()
    assert page.errors == []


def test_compose_warns_when_post_will_be_shifted(page, svc):
    connect(page)
    settings(page, daily_max=1, fb_schedule=False)
    page.request.post(page.base + "/api/posts", data={"message": "đã đăng"})
    svc.scheduler.process_one()
    page.goto(page.base)
    nav(page, "Soạn bài")
    page.get_by_label("Nội dung").fill("Bài thứ hai hôm nay")
    page.get_by_role("button", name="Đăng ngay").last.click()
    page.get_by_text("Bài sẽ được dời giờ").wait_for()
    assert "đã đủ 1 bài/ngày" in page.locator(".mantine-Modal-body").inner_text()
    page.get_by_role("button", name="Đồng ý").click()
    page.get_by_text("Đã lên lịch").wait_for()
    assert len(api_state(page)["posts"]) == 2
    assert page.errors == []


def test_flow_run_warns_about_shifted_posts(page):
    connect(page)
    settings(page, daily_max=2)
    page.goto(page.base)
    nav(page, "Flow chiến dịch")
    page.get_by_role("button", name="Tạo flow đầu tiên").click()
    page.get_by_label("Tên flow").fill("Nhiều bài")
    page.get_by_role("button", name="Tạo và mở").click()
    page.locator(".react-flow__node").first.wait_for()
    page.get_by_role("button", name="Chạy flow").click()
    warn = page.get_by_test_id("run-shift-warning")
    warn.wait_for()
    assert "tối đa 2 bài/ngày" in warn.inner_text()
    assert page.errors == []
