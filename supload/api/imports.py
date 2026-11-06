"""Nhập bài hàng loạt từ CSV / Excel: tải file mẫu, xem trước, nhập."""
from __future__ import annotations

import re
from datetime import datetime

from flask import Blueprint, Response, jsonify, request

from ..domain import importer
from ..domain import pages as pages_domain
from ..domain.posts import clean_body, new_post
from ..services import media
from ..storage import add_log
from . import error, services

bp = Blueprint("imports", __name__, url_prefix="/api/import")


@bp.get("/template")
def template():
    if request.args.get("format") == "xlsx":
        return Response(importer.template_xlsx(), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": "attachment; filename=supload-mau.xlsx"})
    return Response(importer.template_csv(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=supload-mau.csv"})


@bp.post("/preview")
def preview():
    f = request.files.get("file")
    if not f:
        return error("Chưa chọn file")
    data = services().store.load()
    try:
        rows = importer.parse_rows(importer.read_table(f.filename or "", f.read()), data["pages"], datetime.now())
    except ValueError as e:
        return error(str(e))
    except Exception as e:  # noqa: BLE001 - file hỏng / sai định dạng
        return error(f"Không đọc được file: {e}")
    # ảnh dạng tên file phải có sẵn trong thư viện
    upload_dir = services().config.upload_dir
    for r in rows:
        for ph in r["photos"]:
            if not re.match(r"^https?://", ph) and not (upload_dir / ph).is_file():
                r["errors"].append(f"Không có ảnh “{ph}” trong thư viện ảnh")
        v = r.get("video")
        if v and not re.match(r"^https?://", v) and not (upload_dir / v).is_file():
            r["errors"].append(f"Không có video “{v}” trong thư viện")
    bad = sum(bool(r["errors"]) for r in rows)
    return jsonify(rows=rows, ok=len(rows) - bad, bad=bad)


@bp.post("/commit")
def commit():
    """Nhập các dòng đã xem trước. Có dòng lỗi thì không nhập gì, trừ khi skip_errors=true."""
    s = services()
    body = request.get_json(force=True)
    rows = body.get("rows", [])[: importer.MAX_ROWS]
    skip = bool(body.get("skip_errors"))
    data = s.store.load()
    failed, ready = [], []
    for r in rows:
        if r.get("errors"):
            failed.append({"row": r.get("row"), "errors": r["errors"]})
            continue
        try:
            photos = [media.download_image(p, s.config.upload_dir) if re.match(r"^https?://", p) else p for p in r.get("photos", [])]
            video = r.get("video") or ""
            if re.match(r"^https?://", video):
                video = media.download_video(video, s.config.upload_dir)
            body_row = {**r, "photos": photos, "video": video or None}
            if not video:
                body_row.pop("video_kind", None)
            fields = clean_body(body_row, s.config.upload_dir)
            if len(fields["photos"]) != len(photos):
                raise ValueError("Có ảnh không còn trong thư viện")
            page = pages_domain.resolve(data, r.get("page") or body.get("page"))
            ready.append(new_post(fields, page=page, source="import"))
        except ValueError as e:
            failed.append({"row": r.get("row"), "errors": [str(e)]})
    if failed and not skip:
        return error(f"{len(failed)} dòng có lỗi, chưa nhập bài nào", 400, failed=failed)
    if not ready:
        return error("Không có dòng hợp lệ để nhập", 400, failed=failed)
    with s.store.transaction() as data:
        data["posts"].extend(ready)
        add_log(data, "info", f"Đã nhập {len(ready)} bài từ file" + (f" (bỏ qua {len(failed)} dòng lỗi)" if failed else ""))
    s.runtime.notify()
    return jsonify(count=len(ready), failed=failed)
