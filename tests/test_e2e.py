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
    page.request.post(page.base + "/api/settings", data={"min_gap": 0, "daily_max": 0})
    page.request.post(page.base + "/api/pages", data={"kind": "api", "fb_page_id": "111", "token": "tok", "name": "Tiệm Bánh"})


def test_first_run_opens_settings_and_adds_page(page):
    page.goto(page.base)
    page.get_by_text("Chưa kết nối Page nào").wait_for()
    page.get_by_text("Nhập Page ID / Page Token thủ công").click()
    page.get_by_role("textbox", name="Page ID").fill("111")
    page.get_by_role("textbox", name="Page Access Token").fill("SECRET")
    page.get_by_role("button", name="Thêm Page").first.click()
    row = page.get_by_test_id("page-row")
    row.wait_for()
    assert "mặc định" in row.inner_text().lower()
    row.get_by_role("button", name="Kiểm tra").click()
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
    assert "1 / 1 bài" in page.get_by_test_id("limits-today").inner_text()
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


def test_backup_now_from_settings(page, svc):
    connect(page)
    page.goto(page.base)
    nav(page, "Cài đặt")
    page.get_by_text("Dữ liệu & sao lưu").wait_for()
    page.get_by_role("button", name="Sao lưu & dọn dẹp ngay").click()
    page.get_by_text("Đã sao lưu (data-").wait_for()
    assert len(svc.maintenance.backups()) == 1
    page.get_by_test_id("backup-info").get_by_text("1 bản sao lưu", exact=False).wait_for()
    assert page.errors == []


# ---------------------------------------------------------------- nhiều Page
def two_pages(page):
    connect(page)  # Page "Tiệm Bánh" (111) là mặc định
    r = page.request.post(page.base + "/api/pages", data={"kind": "api", "fb_page_id": "222", "token": "t2", "name": "Quán Cà Phê"})
    return r.json()["page"]["id"]


def pick(page, testid, option):
    page.get_by_test_id(testid).click()
    page.get_by_role("option", name=option).click()


def test_compose_to_chosen_page_and_filter_queue(page, svc, graph):
    cafe = two_pages(page)
    page.goto(page.base)
    nav(page, "Soạn bài")
    pick(page, "page-select", "Quán Cà Phê")
    page.get_by_label("Nội dung").fill("Cà phê sáng")
    page.get_by_role("button", name="Đăng ngay").last.click()
    page.get_by_text("Đang đăng bài").wait_for()
    assert api_state(page)["posts"][0]["page"] == cafe
    page.request.post(page.base + "/api/posts", data={"message": "Bánh ngọt"})  # Page mặc định
    while svc.scheduler.process_one():
        pass
    assert sorted(c["path"] for c in graph.by("POST", "/feed")) == ["111/feed", "222/feed"]
    nav(page, "Lịch đăng")
    page.get_by_text("Đã đăng (2)").click()
    rows = page.get_by_test_id("post-row")
    rows.first.wait_for()
    assert rows.count() == 2
    pick(page, "queue-page-filter", "Quán Cà Phê")
    page.wait_for_timeout(200)
    assert rows.count() == 1 and "Cà phê sáng" in rows.first.inner_text() and "Quán Cà Phê" in rows.first.inner_text()
    assert page.errors == []


def test_manage_pages_in_settings(page, svc):
    two_pages(page)
    page.goto(page.base)
    nav(page, "Cài đặt")
    rows = page.get_by_test_id("page-row")
    rows.nth(1).wait_for()
    card_action(page, "Page Quán Cà Phê", "Đặt làm mặc định")
    page.get_by_text("“Quán Cà Phê” là Page mặc định").wait_for()
    assert svc.store.load()["settings"]["default_page"] == svc.store.load()["pages"][1]["id"]
    card_action(page, "Page Tiệm Bánh", "Xoá Page")
    page.get_by_role("dialog").get_by_role("button", name="Xoá Page").click()
    page.get_by_text("Đã xoá Page").wait_for()
    assert [p["name"] for p in svc.store.load()["pages"]] == ["Quán Cà Phê"]
    assert page.errors == []


def test_flow_targets_selected_page(page, svc):
    cafe = two_pages(page)
    page.goto(page.base)
    nav(page, "Flow chiến dịch")
    page.get_by_role("button", name="Tạo flow đầu tiên").click()
    page.get_by_label("Tên flow").fill("Cà phê")
    page.get_by_role("button", name="Tạo và mở").click()
    page.locator(".react-flow__node").first.wait_for()
    pick(page, "flow-page", "Quán Cà Phê")
    page.get_by_role("button", name="Chạy flow").click()
    page.get_by_text("lên Page Quán Cà Phê", exact=False).wait_for()
    page.get_by_role("button", name="Lên lịch").last.click()
    page.get_by_text("Đã lên lịch").wait_for()
    assert {p["page"] for p in api_state(page)["posts"]} == {cafe}
    assert api_flows(page)[0]["page"] == cafe
    assert page.errors == []


def test_health_banner_when_page_loses_connection(page, svc):
    connect(page)
    from datetime import datetime
    from supload.domain import health
    with svc.store.transaction() as data:
        health.record(data, data["pages"][0]["id"], False, datetime.now(), health.describe(190, "x"), 190)
    page.goto(page.base)
    nav(page, "Lịch đăng")
    banner = page.get_by_test_id("health-banner")
    banner.wait_for()
    assert "Tiệm Bánh" in banner.inner_text() and "Token đã hết hạn" in banner.inner_text()
    banner.get_by_role("button", name="Mở Cài đặt").click()
    page.get_by_test_id("health-bad").wait_for()
    page.get_by_test_id("page-row").get_by_role("button", name="Kiểm tra").click()  # Facebook giả lập trả OK
    page.get_by_test_id("health-ok").wait_for()
    nav(page, "Lịch đăng")
    page.wait_for_timeout(300)
    assert page.get_by_test_id("health-banner").count() == 0
    assert page.errors == []


# ---------------------------------------------------------------- lịch tháng/tuần
def at_day(days, hour=10, minute=0):
    d = datetime.now() + timedelta(days=days)
    return d.replace(hour=hour, minute=minute, second=0, microsecond=0)


def open_calendar(page):
    nav(page, "Lịch đăng")
    page.get_by_test_id("queue-layout").locator(".mantine-SegmentedControl-label", has_text="Lịch").click()
    page.get_by_test_id("cal-title").wait_for()


def test_calendar_shows_posts_and_drag_reschedules(page, svc, graph):
    connect(page)
    settings(page, fb_schedule=False)
    d1, d3 = at_day(1), at_day(3)
    page.request.post(page.base + "/api/posts", data={"message": "Bài ngày mai", "scheduled_at": d1.isoformat(timespec="minutes")})
    page.goto(page.base)
    open_calendar(page)
    cell1 = page.locator(f'[data-testid="cal-day"][data-date="{d1:%Y-%m-%d}"]')
    chip = cell1.get_by_test_id("cal-chip")
    chip.wait_for()
    assert "10:00" in chip.inner_text() and "Bài ngày mai" in chip.inner_text()
    target = page.locator(f'[data-testid="cal-day"][data-date="{d3:%Y-%m-%d}"]')
    chip.drag_to(target)
    page.get_by_text("Đã dời sang", exact=False).wait_for()
    p = api_state(page)["posts"][0]
    assert p["scheduled_at"] == d3.isoformat(timespec="minutes")  # đổi ngày, giữ giờ
    target.get_by_test_id("cal-chip").wait_for()
    assert page.errors == []


def test_calendar_drag_of_facebook_scheduled_post_reschedules_on_facebook(page, svc, graph):
    connect(page)
    d1, d2 = at_day(1, 11), at_day(2, 11)
    page.request.post(page.base + "/api/posts", data={"message": "Đã hẹn FB", "scheduled_at": d1.isoformat(timespec="minutes")})
    svc.scheduler.process_one()
    page.goto(page.base)
    assert api_state(page)["posts"][0]["status"] == "scheduled"
    open_calendar(page)
    chip = page.locator(f'[data-testid="cal-day"][data-date="{d1:%Y-%m-%d}"]').get_by_test_id("cal-chip")
    chip.drag_to(page.locator(f'[data-testid="cal-day"][data-date="{d2:%Y-%m-%d}"]'))
    page.get_by_text("đã huỷ và hẹn lại trên Facebook", exact=False).wait_for()
    assert graph.by("DELETE")
    svc.scheduler.process_one()
    p = api_state(page)["posts"][0]
    assert p["status"] == "scheduled" and p["fb_scheduled_at"].startswith(f"{d2:%Y-%m-%dT11:00}")
    assert page.errors == []


def test_calendar_past_days_do_not_accept_drops(page, svc):
    connect(page)
    settings(page, fb_schedule=False)
    d1 = at_day(1)
    page.request.post(page.base + "/api/posts", data={"message": "x", "scheduled_at": d1.isoformat(timespec="minutes")})
    page.goto(page.base)
    open_calendar(page)
    yesterday = page.locator(f'[data-testid="cal-day"][data-date="{datetime.now() - timedelta(days=1):%Y-%m-%d}"]')
    if yesterday.count():  # có thể nằm ngoài lưới vào ngày đầu tháng
        assert yesterday.get_attribute("data-past") == "true"
        page.locator(f'[data-testid="cal-day"][data-date="{d1:%Y-%m-%d}"]').get_by_test_id("cal-chip").drag_to(yesterday)
        page.wait_for_timeout(400)
        assert api_state(page)["posts"][0]["scheduled_at"] == d1.isoformat(timespec="minutes")
    assert page.errors == []


def test_calendar_plus_opens_compose_for_that_day(page):
    connect(page)
    page.goto(page.base)
    open_calendar(page)
    d2 = at_day(2)
    page.get_by_role("button", name=f"Soạn bài ngày {d2.day}/{d2.month}").click()
    page.get_by_text("Sẽ đăng lúc 09:00", exact=False).wait_for()
    assert page.errors == []


# ---------------------------------------------------------------- nhập từ file
def test_import_from_csv_with_preview_and_errors(page, svc, tmp_path):
    connect(page)
    future = (datetime.now() + timedelta(days=3)).replace(hour=19, minute=0)
    f = tmp_path / "bai.csv"
    f.write_text(f"Nội dung,Thời gian\nBài tốt,{future:%d/%m/%Y %H:%M}\nBài lỗi,sai-ngày\nĐăng ngay,\n", encoding="utf-8")
    page.goto(page.base)
    nav(page, "Lịch đăng")
    page.get_by_role("button", name="Nhập từ file").click()
    page.get_by_test_id("import-drop").locator("input[type=file]").set_input_files(str(f))
    table = page.get_by_test_id("import-table")
    table.wait_for()
    assert "Không hiểu thời gian" in table.inner_text()
    assert page.get_by_role("button", name="Nhập 2 bài", exact=True).is_disabled()
    page.get_by_role("button", name="Nhập 2 bài hợp lệ, bỏ qua 1 dòng lỗi").click()
    page.get_by_text("Đã nhập 2 bài vào Lịch đăng").wait_for()
    msgs = sorted(p["message"] for p in api_state(page)["posts"])
    assert msgs == ["Bài tốt", "Đăng ngay"]
    assert page.errors == []


def test_import_template_download(page):
    connect(page)
    page.goto(page.base)
    nav(page, "Lịch đăng")
    page.get_by_role("button", name="Nhập từ file").click()
    with page.expect_download() as dl:
        page.get_by_role("link", name="File mẫu Excel").click()
    assert dl.value.suggested_filename == "supload-mau.xlsx"


# ---------------------------------------------------------------- thư viện
def test_library_snippet_insert_and_reuse_photo(page, svc, tmp_path):
    connect(page)
    img = tmp_path / "logo.png"
    img.write_bytes(PNG)
    page.request.post(page.base + "/api/upload", multipart={"files": {"name": "logo.png", "mimeType": "image/png", "buffer": PNG}})
    page.goto(page.base)
    nav(page, "Thư viện")
    page.get_by_role("button", name="Thêm").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("textbox", name="Nội dung").fill("#tiembanh #banhngon")
    dialog.get_by_role("button", name="Lưu").click()
    page.get_by_test_id("lib-item").wait_for()
    page.get_by_role("tab", name="Ảnh & video").click()
    page.get_by_test_id("media-item").wait_for()

    nav(page, "Soạn bài")
    page.get_by_label("Nội dung").fill("Bánh mới")
    page.get_by_role("button", name="Chèn từ thư viện").click()
    page.get_by_role("menuitem", name="#tiembanh #banhngon").first.click()
    assert page.get_by_label("Nội dung").input_value() == "Bánh mới\n\n#tiembanh #banhngon"
    page.get_by_role("button", name="Chọn ảnh đã tải").click()
    page.get_by_test_id("media-picker").locator("button").first.click()
    page.get_by_role("button", name="Thêm 1 ảnh").click()
    page.locator(".thumb").first.wait_for()
    page.get_by_role("button", name="Đăng ngay").last.click()
    page.get_by_text("Đang đăng bài").wait_for()
    p = api_state(page)["posts"][0]
    assert p["message"].endswith("#tiembanh #banhngon") and len(p["photos"]) == 1
    assert svc.store.load()["library"][0]["used"] == 1
    assert page.errors == []


# ---------------------------------------------------------------- video / reels
def test_compose_reel_and_queue_badge(page, svc, graph, tmp_path):
    connect(page)
    clip = tmp_path / "reel.mp4"
    clip.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    page.goto(page.base)
    nav(page, "Soạn bài")
    page.get_by_test_id("media-type").locator(".mantine-SegmentedControl-label", has_text="Reels").click()
    page.get_by_text("video dọc 9:16", exact=False).wait_for()
    page.get_by_test_id("video-drop").locator("input[type=file]").set_input_files(str(clip))
    page.get_by_test_id("video-preview").wait_for()
    page.get_by_label("Nội dung").fill("Reel đầu tiên")
    page.get_by_role("button", name="Đăng ngay").last.click()
    page.get_by_text("Đang đăng bài").wait_for()
    p = api_state(page)["posts"][0]
    assert p["video"].endswith("reel.mp4") and p["video_kind"] == "reel" and p["photos"] == []
    svc.scheduler.process_one()
    assert [c["path"] for c in graph.calls][0] == "111/video_reels"
    nav(page, "Lịch đăng")
    page.get_by_text("Đã đăng (1)").click()
    page.get_by_test_id("post-row").get_by_text("Reels", exact=True).wait_for()
    assert page.errors == []


# ---------------------------------------------------------------- thống kê
def seed_stats(svc):
    now = datetime.now()
    with svc.store.transaction() as data:
        pid = data["pages"][0]["id"]
        for i, (hour, r) in enumerate([(20, 40), (20, 30), (8, 3), (8, 5), (12, 10), (21, 22)]):
            t = (now - timedelta(days=i + 1)).replace(hour=hour, minute=0, second=0, microsecond=0)
            data["posts"].append({"id": f"s{i}", "status": "done", "message": f"Bài {i} lúc {hour}h", "photos": [], "page": pid,
                                  "created_at": t.isoformat(), "done_at": t.isoformat(), "fb_id": f"111_s{i}",
                                  "stats": {"reactions": r, "comments": 2, "shares": 1, "reach": r * 10, "fetched_at": now.isoformat()}})


def test_insights_page(page, svc):
    connect(page)
    seed_stats(svc)
    page.goto(page.base)
    nav(page, "Thống kê")
    page.get_by_test_id("best-hours").wait_for()
    assert "20:00" in page.get_by_test_id("best-hours").inner_text()
    assert page.get_by_test_id("chart-hour").locator(".bar").count() == 4  # 4 khung giờ có bài
    page.get_by_test_id("chart-hour").get_by_label("20:00–20:59", exact=False).hover()
    page.get_by_text("TB 38 tương tác · 2 bài", exact=False).wait_for()
    assert "Bài 0 lúc 20h" in page.get_by_test_id("top-posts").locator("tbody tr").first.inner_text()
    page.get_by_text("Xem dạng bảng số liệu").click()
    page.get_by_role("columnheader", name="TB tương tác").first.wait_for()
    nav(page, "Lịch đăng")
    page.get_by_text("Đã đăng (6)").click()
    page.get_by_test_id("post-stats").first.wait_for()
    assert page.errors == []


# ---------------------------------------------------------------- trợ lý AI
def test_ai_assistant_rewrites_and_adds_hashtags(page, svc, monkeypatch):
    import json as _json
    from types import SimpleNamespace
    from supload.integrations import ai

    def fake(client, **kw):
        prompt = kw["messages"][-1]["content"]
        out = ["#banhngon", "#tiembanh"] if "hashtag" in prompt else ["Bản viết lại A 🎂", "Bản viết lại B"]
        msg = SimpleNamespace(content=_json.dumps({"suggestions": out}), refusal=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")])
    monkeypatch.setattr(ai, "create", fake)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    connect(page)
    page.goto(page.base)
    nav(page, "Soạn bài")
    page.get_by_label("Nội dung").fill("bánh kem mới")
    page.get_by_role("button", name="Trợ lý AI").click()
    page.get_by_role("menuitem", name="Viết lại hay hơn").click()
    page.get_by_text("Chưa có API key OpenAI", exact=False).wait_for()   # chưa cấu hình key
    page.get_by_role("dialog").get_by_role("button", name="Mở Cài đặt").click()
    page.get_by_label("API key OpenAI").fill("sk-test")
    page.get_by_role("button", name="Lưu cài đặt").click()
    page.get_by_text("Đã lưu cài đặt").wait_for()
    assert "sk-test" not in page.content()

    nav(page, "Soạn bài")
    page.get_by_role("button", name="Trợ lý AI").click()
    page.get_by_role("menuitem", name="Viết lại hay hơn").click()
    page.get_by_test_id("ai-suggestion").first.wait_for()
    page.get_by_role("button", name="Dùng bản này").first.click()
    assert page.get_by_label("Nội dung").input_value() == "Bản viết lại A 🎂"
    page.get_by_role("button", name="Trợ lý AI").click()
    page.get_by_role("menuitem", name="Gợi ý hashtag").click()
    page.get_by_role("button", name="Thêm 2 hashtag vào bài").click()
    assert page.get_by_label("Nội dung").input_value() == "Bản viết lại A 🎂\n\n#banhngon #tiembanh"
    # lỗi 400 duy nhất là câu trả lời "chưa có API key" có chủ đích ở đầu bài test
    assert [e for e in page.errors if "status of 400" not in e] == []
    assert len(page.errors) <= 1


# ---------------------------------------------------------------- ứng dụng / tự khởi động
def test_autostart_switch_in_settings(page, tmp_path, monkeypatch):
    startup = tmp_path / "Startup"
    monkeypatch.setenv("SUPLOAD_FAKE_STARTUP_DIR", str(startup))  # giả lập thư mục Startup của Windows
    connect(page)
    page.goto(page.base)
    nav(page, "Cài đặt")
    page.get_by_text("Khởi động cùng Windows", exact=True).click()
    page.get_by_text("tự chạy ẩn mỗi khi bạn đăng nhập Windows", exact=False).wait_for()
    assert (startup / "SUpload.vbs").exists()
    page.get_by_text("Khởi động cùng Windows", exact=True).click()
    page.get_by_text("Đã tắt tự khởi động").wait_for()
    assert not (startup / "SUpload.vbs").exists()
    assert page.errors == []
