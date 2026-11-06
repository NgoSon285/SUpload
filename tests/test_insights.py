"""Thống kê tương tác: lấy chỉ số định kỳ, tổng hợp, khung giờ hiệu quả."""
from datetime import datetime, timedelta

from supload.domain import insights


def done_post(pid, when, stats=None, **extra):
    return {"id": pid, "status": "done", "done_at": when.isoformat(timespec="seconds"), "fb_id": f"111_{pid}",
            "photos": [], "message": pid, "created_at": "x", **({"stats": stats} if stats else {}), **extra}


def test_publish_stores_facebook_id(connected, svc, graph):
    connected.post("/api/posts", json={"message": "x"})
    svc.scheduler.process_one()
    assert svc.store.load()["posts"][0]["fb_id"] == "111_1"


def test_worker_fetches_stats_after_10_minutes_then_every_6_hours(connected, svc, graph):
    connected.post("/api/posts", json={"message": "x"})
    now = datetime.now()
    svc.scheduler.process_one(now=now)
    assert svc.scheduler.process_one(now=now + timedelta(minutes=5)) is False       # còn quá sớm
    assert svc.scheduler.process_one(now=now + timedelta(minutes=11)) is True
    s = svc.store.load()["posts"][0]["stats"]
    assert (s["reactions"], s["comments"], s["shares"], s["reach"]) == (5, 2, 1, 120)
    assert svc.scheduler.process_one(now=now + timedelta(hours=1)) is False
    graph.metrics["reactions"] = 50
    later = now + timedelta(hours=7)
    while svc.scheduler.process_one(now=later):  # kiểm tra kết nối (6 giờ) chạy trước, rồi tới thống kê
        pass
    assert svc.store.load()["posts"][0]["stats"]["reactions"] == 50


def test_stops_tracking_after_14_days(connected, svc):
    old = datetime.now() - timedelta(days=20)
    with svc.store.transaction() as data:
        data["posts"].append(done_post("old", old, page=data["pages"][0]["id"]))
    assert svc.scheduler.process_one() is False


def test_missing_read_insights_permission_keeps_other_metrics(connected, svc, graph):
    graph.no_insights = True
    connected.post("/api/posts", json={"message": "x"})
    now = datetime.now()
    svc.scheduler.process_one(now=now)
    svc.scheduler.process_one(now=now + timedelta(minutes=11))
    s = svc.store.load()["posts"][0]["stats"]
    assert s["reactions"] == 5 and s["reach"] is None and "read_insights" in s["reach_error"]


def test_video_uses_likes_and_video_insights(connected, svc, graph):
    with svc.store.transaction() as data:
        data["posts"].append(done_post("v", datetime.now() - timedelta(hours=1), video="a.mp4", page=data["pages"][0]["id"]))
    svc.scheduler.process_one()
    paths = [c["path"] for c in graph.calls]
    assert paths == ["111_v", "111_v/video_insights"]
    assert graph.calls[0]["params"]["fields"].startswith("likes.")
    assert graph.calls[1]["params"]["metric"] == "total_video_views"
    assert svc.store.load()["posts"][0]["stats"]["reach"] == 120


def test_post_reach_uses_media_view_metric_and_lifetime_row(connected, svc, graph):
    connected.post("/api/posts", json={"message": "x"})
    now = datetime.now()
    svc.scheduler.process_one(now=now)
    svc.scheduler.process_one(now=now + timedelta(minutes=11))
    ins = graph.by("GET", "/insights")[0]
    assert ins["params"]["metric"] == "post_total_media_view_unique" and ins["params"]["period"] == "lifetime"
    s = svc.store.load()["posts"][0]["stats"]
    assert s["reach"] == 120 and s["reach_error"] is None  # lấy dòng lifetime, bỏ dòng theo ngày


def test_retired_metric_error_is_not_reported_as_missing_permission():
    from supload.integrations import facebook as fb
    calls = []

    def fake(method, path, base=fb.GRAPH, **kw):
        calls.append(path)
        if path.endswith("/insights"):
            raise fb.FBError("[100] (#100) The value must be a valid insights metric", 100)
        return {"reactions": {"summary": {"total_count": 3}}}

    orig, fb.call = fb.call, fake
    try:
        s = fb.PagePoster("1", "t").engagement("1_2")
    finally:
        fb.call = orig
    assert s["reactions"] == 3 and s["reach"] is None
    assert "read_insights" not in s["reach_error"] and "không còn hỗ trợ" in s["reach_error"]


def test_lifetime_value_sums_breakdowns():
    from supload.integrations.facebook import _lifetime_value
    assert _lifetime_value({"data": [{"period": "lifetime", "values": [{"value": {"a": 2, "b": 3}}]}]}) == 5
    assert _lifetime_value({"data": []}) == 0


def test_deleted_on_facebook_stops_tracking(connected, svc, graph):
    with svc.store.transaction() as data:
        data["posts"].append(done_post("gone", datetime.now() - timedelta(hours=1), page=data["pages"][0]["id"]))
    graph.missing.add("111_gone")
    svc.scheduler.process_one()
    p = svc.store.load()["posts"][0]
    assert p["fb_id"] is None and p["stats"]["gone"] is True
    before = len([c for c in graph.calls if c["path"].startswith("111_gone")])
    while svc.scheduler.process_one(now=datetime.now() + timedelta(hours=7)):
        pass
    assert len([c for c in graph.calls if c["path"].startswith("111_gone")]) == before  # không hỏi lại bài đã xoá


def test_summarize_totals_best_hours_and_top():
    base = datetime(2026, 11, 2)  # Thứ Hai
    st = lambda r, c=0, s=0, reach=None: {"reactions": r, "comments": c, "shares": s, "reach": reach}  # noqa: E731
    posts = [
        done_post("a", base.replace(hour=20), st(30, 5, 5, 1000)),
        done_post("b", base.replace(hour=20) + timedelta(days=1), st(20, 0, 0, 800)),
        done_post("c", base.replace(hour=8), st(2, 0, 0, 100)),
        done_post("d", base.replace(hour=8) + timedelta(days=1), st(4, 0, 0, 100)),
        done_post("old", base - timedelta(days=60), st(999)),
        {"id": "p", "status": "pending", "stats": st(1)},
    ]
    r = insights.summarize(posts, base - timedelta(days=1))
    assert r["posts"] == 4 and r["totals"]["engagement"] == 66 and r["totals"]["reach"] == 2000
    assert r["avg_engagement"] == 16.5
    assert r["best_hours"] == [20]                    # ≥ 2 bài và trên mức TB chung (8h có 2 bài nhưng kém -> không gợi ý)
    assert r["by_hour"][20]["avg"] == 30.0 and r["by_hour"][3]["avg"] is None
    assert r["by_dow"][0]["posts"] == 2               # Thứ Hai
    assert [t["id"] for t in r["top"]][:2] == ["a", "b"]


def test_insights_api_filters_by_page_and_refresh(connected, svc, graph):
    with svc.store.transaction() as data:
        pid = data["pages"][0]["id"]
        data["posts"].append(done_post("a", datetime.now() - timedelta(hours=2), {"reactions": 3, "comments": 1, "shares": 0,
                                                                                  "reach": None, "fetched_at": datetime.now().isoformat()}, page=pid))
    r = connected.get("/api/insights?days=7").get_json()
    assert r["posts"] == 1 and r["totals"]["engagement"] == 4 and r["reach_missing"] is True
    assert connected.get("/api/insights?days=7&page=pg_khac").get_json()["posts"] == 0
    assert connected.post("/api/insights/refresh").get_json()["queued"] == 1
    assert svc.scheduler.process_one() is True  # lấy lại ngay


def test_report_xlsx_has_all_sheets_and_filters_by_page(connected, svc):
    import io
    from openpyxl import load_workbook
    with svc.store.transaction() as data:
        pid = data["pages"][0]["id"]
        now = datetime.now()
        st = {"reactions": 3, "comments": 1, "shares": 0, "reach": 50}
        data["posts"] += [done_post("a", now - timedelta(days=2), st, page=pid, fb_id="111_a"),
                          done_post("b", now - timedelta(days=60), st, page=pid)]
        data["comments"] = [{"id": "c1", "page": pid, "from_name": "An", "message": "Giá?", "created_time": now.isoformat(),
                             "replies": [{"text": "ib"}], "hidden": True, "post_text": "Bài a"}]
    r = connected.get("/api/insights/report.xlsx?days=30")
    assert r.status_code == 200 and "attachment" in r.headers["Content-Disposition"]
    wb = load_workbook(io.BytesIO(r.data))
    assert wb.sheetnames == ["Tổng quan", "Bài viết", "Theo giờ", "Theo thứ", "Bình luận"]
    posts = list(wb["Bài viết"].iter_rows(min_row=2, values_only=True))
    assert len(posts) == 1 and posts[0][9] == "https://www.facebook.com/111_a"  # bài 60 ngày trước nằm ngoài khoảng
    overview = {r[0]: r[1] for r in wb["Tổng quan"].iter_rows(min_row=4, values_only=True) if r[0]}
    assert overview["Số bài có số liệu"] == 1 and overview["Đã trả lời"] == 1 and overview["Đã ẩn"] == 1
    assert list(wb["Bình luận"].iter_rows(min_row=2, values_only=True))[0][1] == "An"
    r = connected.get("/api/insights/report.xlsx?days=30&page=khac")
    assert len(list(load_workbook(io.BytesIO(r.data))["Bài viết"].iter_rows(min_row=2))) == 0
