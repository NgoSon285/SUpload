"""Trang giao diện, ảnh tải lên, trạng thái tổng hợp, xem trước lịch."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from ..config import ALLOWED_IMAGE_EXT
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
        if ext not in ALLOWED_IMAGE_EXT:
            return error(f"Định dạng không hỗ trợ: {f.filename}")
        name = f"{new_id(n=8)}_{secure_filename(f.filename) or 'img' + ext}"
        f.save(services().config.upload_dir / name)
        names.append(name)
    return jsonify(files=names)


def _limits_summary(posts: list[dict], settings: dict, now: datetime) -> dict:
    today = now.date()
    used = 0
    for p in posts:
        t = parse_dt(p.get("done_at")) if p["status"] == DONE else parse_dt(p.get("fb_scheduled_at")) if p["status"] == SCHEDULED else None
        used += bool(t and t.date() == today)
    return {"daily_max": settings["daily_max"], "min_gap": settings["min_gap"], "today": used}


@bp.get("/api/state")
def state():
    s = services()
    data = s.store.load()
    now = datetime.now()
    plan = planner.plan(data["posts"], data["settings"], now)
    posts = []
    for p in sorted(data["posts"], key=lambda p: p["created_at"], reverse=True):
        slot = plan.get(p["id"]) if p["status"] == PENDING else None
        if slot:
            p = {**p, "effective_at": slot.effective.isoformat(timespec="seconds"),
                 "shift_reason": planner.describe(slot, data["settings"]) if slot.shifted else "",
                 "fb_handoff": s.publisher.fb_scheduling_enabled(data["settings"]) and slot.effective - now >= timedelta(minutes=12)}
        posts.append(p)
    return jsonify(
        settings=public_settings(data["settings"]), posts=posts, log=data["log"][:100],
        worker=s.runtime.worker, login=s.runtime.login, limits=_limits_summary(data["posts"], data["settings"], now),
        maintenance={**(data.get("maintenance") or {}), "backups": len(s.maintenance.backups())},
    )


@bp.post("/api/maintenance/run")
def run_maintenance():
    """Sao lưu & dọn dẹp ngay (thay vì chờ lượt hằng ngày)."""
    return jsonify(services().maintenance.run())


@bp.post("/api/plan/preview")
def plan_preview():
    """Xem trước: nếu thêm các bài này thì chúng sẽ thực sự được đăng lúc nào (sau giới hạn an toàn)."""
    items = request.get_json(force=True).get("posts", [])[:1000]
    data = services().store.load()
    now = datetime.now()
    temp = [{"id": f"tmp_{i}", "status": PENDING, "scheduled_at": it.get("scheduled_at"),
             "created_at": f"~{i:06d}"} for i, it in enumerate(items)]  # "~" xếp sau mọi bài thật cùng giờ
    plan = planner.plan(data["posts"] + temp, data["settings"], now)
    out, by_cap, by_gap = [], 0, 0
    for t in temp:
        slot = plan[t["id"]]
        out.append({"effective_at": slot.effective.isoformat(timespec="seconds"), "shifted": slot.shifted,
                    "reason": planner.describe(slot, data["settings"]) if slot.shifted else ""})
        by_cap += slot.shifted and "cap" in slot.reasons
        by_gap += slot.shifted and "gap" in slot.reasons and "cap" not in slot.reasons
    return jsonify(items=out, shifted=by_cap + by_gap, by_cap=by_cap, by_gap=by_gap,
                   daily_max=data["settings"]["daily_max"], min_gap=data["settings"]["min_gap"])
