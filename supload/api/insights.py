"""Thống kê tương tác."""
from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, Response, jsonify, request

from ..domain import insights, report
from ..domain import pages as pages_domain
from ..domain.posts import DONE
from ..utils import parse_dt
from . import services

bp = Blueprint("insights", __name__, url_prefix="/api/insights")


@bp.get("")
def summary():
    data = services().store.load()
    days = max(1, min(365, int(request.args.get("days", 30))))
    page = request.args.get("page") or ""
    page_of = lambda p: (pages_domain.page_of(data, p) or {}).get("id")  # noqa: E731
    posts = [p for p in data["posts"] if not page or page_of(p) == page]
    out = insights.summarize(posts, datetime.now() - timedelta(days=days), page_of)
    tracked = [p for p in posts if p.get("status") == DONE and p.get("fb_id")]
    out["waiting"] = sum(1 for p in tracked if "reactions" not in (p.get("stats") or {}))  # chưa lấy được lần nào
    return jsonify(out)


@bp.post("/refresh")
def refresh():
    """Lấy lại chỉ số ngay cho các bài đang theo dõi (luồng nền làm dần từng bài)."""
    now = datetime.now()
    n = 0
    with services().store.transaction() as data:
        for p in data["posts"]:
            if p.get("status") == DONE and p.get("fb_id") and p.get("stats"):
                done = datetime.fromisoformat(p["done_at"]) if p.get("done_at") else now
                if now - done <= timedelta(days=insights.TRACK_DAYS):
                    p["stats"]["fetched_at"] = None
                    n += 1
            elif p.get("status") == DONE and p.get("fb_id"):
                n += 1
    services().runtime.notify()
    return jsonify(queued=n)


@bp.get("/report.xlsx")
def report_xlsx():
    """Tải báo cáo Excel cho khoảng ngày / Page đang xem."""
    data = services().store.load()
    days = max(1, min(365, int(request.args.get("days", 30))))
    page = request.args.get("page") or ""
    now = datetime.now()
    since = now - timedelta(days=days)
    page_of = lambda p: (pages_domain.page_of(data, p) or {}).get("id")  # noqa: E731
    names = {pg["id"]: pg["name"] for pg in data["pages"]}
    posts = [p for p in data["posts"] if not page or page_of(p) == page]
    summary = insights.summarize(posts, since, page_of)
    rows = sorted([p for p in posts if p.get("status") == DONE and p.get("stats") and (parse_dt(p.get("done_at")) or since) >= since],
                  key=lambda p: p["done_at"], reverse=True)
    comments = [c for c in data.get("comments", []) if (not page or c["page"] == page)
                and (parse_dt((c.get("created_time") or "")[:19]) or now) >= since]
    title = f"Báo cáo Facebook · {names.get(page, 'Tất cả Page')}"
    body = report.build_xlsx(summary, rows, comments, lambda p: names.get(page_of(p), ""), title, since, now)
    fname = f"bao-cao-{now:%Y%m%d}-{days}ngay.xlsx"
    return Response(body, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename={fname}"})
