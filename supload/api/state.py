"""Trang giao diện, ảnh tải lên, trạng thái tổng hợp, xem trước lịch."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from ..config import ALLOWED_IMAGE_EXT, ALLOWED_VIDEO_EXT
from ..domain import health
from ..domain import pages as pages_domain
from ..domain import planner
from ..domain.posts import DONE, PENDING, SCHEDULED
from ..domain.settings import public_settings
from ..utils import new_id, parse_dt
from . import error, services

bp = Blueprint("state", __name__)


@bp.get("/")
def index():
    web = services().config.web_dir
    if not (web / "index.html").exists():
        return "Chưa có giao diện. Chạy: cd frontend && npm install && npm run build", 500
    return send_from_directory(web, "index.html")


@bp.get("/uploads/<path:name>")
def uploaded(name):
    return send_from_directory(services().config.upload_dir, name)


@bp.post("/api/upload")
def upload():
    names = []
    for f in request.files.getlist("files"):
        ext = Path(f.filename or "").suffix.lower()
        if ext not in ALLOWED_IMAGE_EXT | ALLOWED_VIDEO_EXT:
            return error(f"Định dạng không hỗ trợ: {f.filename}")
        name = f"{new_id(n=8)}_{secure_filename(f.filename) or 'img' + ext}"
        f.save(services().config.upload_dir / name)
        names.append(name)
    return jsonify(files=names)


def _used_today(posts: list[dict], now: datetime) -> int:
    today, used = now.date(), 0
    for p in posts:
        t = parse_dt(p.get("done_at")) if p["status"] == DONE else parse_dt(p.get("fb_scheduled_at")) if p["status"] == SCHEDULED else None
        used += bool(t and t.date() == today)
    return used


def _page_key(data: dict):
    return lambda p: (pages_domain.page_of(data, p) or {}).get("id")


@bp.get("/api/state")
def state():
    s = services()
    data = s.store.load()
    now = datetime.now()
    settings = data["settings"]
    key = _page_key(data)
    plan = planner.plan(data["posts"], settings, now, key=key)
    posts = []
    for p in sorted(data["posts"], key=lambda p: p["created_at"], reverse=True):
        slot = plan.get(p["id"]) if p["status"] == PENDING else None
        if slot:
            page = pages_domain.page_of(data, p)
            p = {**p, "effective_at": slot.effective.isoformat(timespec="seconds"),
                 "shift_reason": planner.describe(slot, settings) if slot.shifted else "",
                 "fb_handoff": s.publisher.fb_scheduling_enabled(page, settings) and slot.effective - now >= timedelta(minutes=12)}
        posts.append(p)
    default = pages_domain.default_page(data)
    per_page = {pg["id"]: _used_today([p for p in data["posts"] if key(p) == pg["id"]], now) for pg in data["pages"]}
    return jsonify(
        settings=public_settings(settings), posts=posts, log=data["log"][:100],
        pages=[{**pages_domain.public(pg, default and default["id"]), "health": health.of(data, pg["id"])} for pg in data["pages"]],
        worker=s.runtime.worker, login=s.runtime.login,
        limits={"daily_max": settings["daily_max"], "min_gap": settings["min_gap"],
                "today": per_page.get(default["id"], 0) if default else 0, "per_page": per_page},
        maintenance={**(data.get("maintenance") or {}), "backups": len(s.maintenance.backups())},
        comments_unseen=sum(1 for c in data.get("comments", []) if not c.get("seen")),
    )


@bp.post("/api/maintenance/run")
def run_maintenance():
    """Sao lưu & dọn dẹp ngay (thay vì chờ lượt hằng ngày)."""
    return jsonify(services().maintenance.run())


@bp.post("/api/plan/preview")
def plan_preview():
    """Xem trước: nếu thêm các bài này thì chúng sẽ thực sự được đăng lúc nào (sau giới hạn an toàn)."""
    body = request.get_json(force=True)
    items = body.get("posts", [])[:1000]
    data = services().store.load()
    now = datetime.now()
    default = pages_domain.default_page(data)
    temp = [{"id": f"tmp_{i}", "status": PENDING, "scheduled_at": it.get("scheduled_at"),
             "page": it.get("page") or body.get("page") or (default and default["id"]),
             "created_at": f"~{i:06d}"} for i, it in enumerate(items)]  # "~" xếp sau mọi bài thật cùng giờ
    plan = planner.plan(data["posts"] + temp, data["settings"], now, key=_page_key(data))
    out, by_cap, by_gap = [], 0, 0
    for t in temp:
        slot = plan[t["id"]]
        out.append({"effective_at": slot.effective.isoformat(timespec="seconds"), "shifted": slot.shifted,
                    "reason": planner.describe(slot, data["settings"]) if slot.shifted else ""})
        by_cap += slot.shifted and "cap" in slot.reasons
        by_gap += slot.shifted and "gap" in slot.reasons and "cap" not in slot.reasons
    return jsonify(items=out, shifted=by_cap + by_gap, by_cap=by_cap, by_gap=by_gap,
                   daily_max=data["settings"]["daily_max"], min_gap=data["settings"]["min_gap"])
