"""Thư viện: đoạn nội dung dùng lại và ảnh/video đã tải lên."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from ..domain import library
from ..services.maintenance import referenced_photos
from ..storage import find
from . import error, services

bp = Blueprint("library", __name__, url_prefix="/api")


@bp.get("/library")
def list_items():
    items = services().store.load().get("library", [])
    return jsonify(items=sorted(items, key=lambda x: (x["kind"], -x.get("used", 0), x["name"].lower())), kinds=library.KINDS)


@bp.post("/library")
def add_item():
    try:
        item = library.clean(request.get_json(force=True))
    except ValueError as e:
        return error(str(e))
    with services().store.transaction() as data:
        items = data.setdefault("library", [])
        if len(items) >= library.MAX_ITEMS:
            return error(f"Thư viện đã đủ {library.MAX_ITEMS} mục")
        items.append(item)
    return jsonify(item=item)


@bp.put("/library/<item_id>")
def edit_item(item_id):
    with services().store.transaction() as data:
        items = data.setdefault("library", [])
        old = find(items, item_id)
        if not old:
            return error("Không tìm thấy mục", 404)
        try:
            item = library.clean(request.get_json(force=True), old)
        except ValueError as e:
            return error(str(e))
        items[items.index(old)] = item
    return jsonify(item=item)


@bp.delete("/library/<item_id>")
def delete_item(item_id):
    with services().store.transaction() as data:
        data["library"] = [x for x in data.get("library", []) if x["id"] != item_id]
    return jsonify(ok=True)


@bp.post("/library/<item_id>/used")
def mark_used(item_id):
    """Đếm số lần dùng để mục hay dùng hiện lên đầu."""
    with services().store.transaction() as data:
        item = find(data.get("library", []), item_id)
        if item:
            item["used"] = item.get("used", 0) + 1
    return jsonify(ok=True)


@bp.get("/media")
def list_media():
    """Mọi file trong uploads/, kèm số bài/flow đang dùng."""
    s = services()
    data = s.store.load()
    used = referenced_photos(data)
    counts: dict[str, int] = {}
    for p in data["posts"]:
        for f in p.get("photos", []) + ([p["video"]] if p.get("video") else []):
            counts[f] = counts.get(f, 0) + 1
    out = []
    for f in s.config.upload_dir.iterdir():
        if not f.is_file():
            continue
        st = f.stat()
        out.append({"name": f.name, "size": st.st_size, "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                    "used": counts.get(f.name, 0) + (1 if f.name in used and f.name not in counts else 0),
                    "kind": "video" if f.suffix.lower() in (".mp4", ".mov", ".m4v", ".webm") else "image"})
    out.sort(key=lambda x: x["modified"], reverse=True)
    return jsonify(media=out)


@bp.delete("/media/<path:name>")
def delete_media(name):
    s = services()
    path = (s.config.upload_dir / name).resolve()
    if path.parent != s.config.upload_dir.resolve() or not path.is_file():
        return error("Không tìm thấy file", 404)
    data = s.store.load()
    in_use = name in referenced_photos(data) or any(p.get("video") == name for p in data["posts"])
    if in_use:
        return error("File đang được bài viết hoặc flow sử dụng")
    path.unlink()
    return jsonify(ok=True)
