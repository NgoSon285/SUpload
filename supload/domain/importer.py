"""Đọc danh sách bài từ bảng tính (CSV / Excel).

Cột (tên tiếng Việt hoặc tiếng Anh, có dấu hay không đều được; chỉ cần cột Nội dung):
  Nội dung | Link | Ảnh (nhiều ảnh cách nhau bởi xuống dòng, dấu phẩy hoặc ;) | Thời gian | Page
  | Video (link .mp4 hoặc tên video trong thư viện) | Loại (Bài viết / Video / Reels)
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from datetime import datetime

MAX_ROWS = 500
COLUMNS = {
    "message": ("noi dung", "message", "content", "text", "bai viet", "caption"),
    "link": ("link", "url", "duong dan"),
    "photos": ("anh", "hinh", "hinh anh", "photos", "photo", "images", "image"),
    "scheduled_at": ("thoi gian", "gio dang", "lich", "ngay gio", "scheduled_at", "time", "schedule", "datetime"),
    "page": ("page", "trang", "fanpage"),
    "video": ("video", "clip", "file video"),
    "kind": ("loai", "loai bai", "kind", "type", "dang"),
}
KINDS = {"reels": "reel", "reel": "reel", "thuoc phim": "reel", "video": "video", "bai viet": "", "bai": "",
         "anh": "", "post": "", "photo": "", "": ""}
TIME_FORMATS = (
    "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
    "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%H:%M %d/%m/%Y", "%d/%m/%Y",
    "%Y-%m-%d",
)
TEMPLATE_ROWS = [
    ["Nội dung", "Link", "Ảnh", "Thời gian", "Page", "Video", "Loại"],
    ["Chào buổi sáng cả nhà ☀️ #tiembanh", "", "", "01/12/2026 08:00", "", "", "Bài viết"],
    ["Bánh mới ra lò, mời mọi người ghé thử!", "https://example.com/menu", "https://example.com/banh.jpg", "01/12/2026 20:00", "", "", "Bài viết"],
    ["Hậu trường làm bánh 🎬", "", "", "02/12/2026 19:00", "", "https://example.com/hau-truong.mp4", "Reels"],
    ["Bài đăng ngay khi nhập (để trống Thời gian)", "", "", "", "", "", ""],
]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9_ ]+", " ", s).strip()


def map_header(header: list) -> dict[int, str]:
    """{chỉ số cột: tên trường}. Bỏ qua cột lạ."""
    out = {}
    for i, h in enumerate(header):
        n = _norm(h)
        for field, names in COLUMNS.items():
            if n in names and field not in out.values():
                out[i] = field
    return out


def parse_time(value, now: datetime) -> tuple[str | None, str | None]:
    """(thời gian ISO hoặc None = đăng ngay, lỗi)."""
    if value in (None, ""):
        return None, None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None, None
        dt = None
        for fmt in TIME_FORMATS:
            try:
                dt = datetime.strptime(text, fmt)
                if fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                    dt = dt.replace(hour=9)  # chỉ có ngày -> 9:00 sáng
                break
            except ValueError:
                continue
        if dt is None:
            return None, f"Không hiểu thời gian “{text}” (dùng dạng 01/12/2026 08:00)"
    return dt.replace(second=0, microsecond=0).isoformat(timespec="minutes"), None


def split_photos(value) -> list[str]:
    return [x.strip() for x in re.split(r"[\n,;]+", str(value or "")) if x.strip()]


def read_table(filename: str, content: bytes) -> list[list]:
    """Đọc file thành danh sách dòng (dòng đầu là tiêu đề)."""
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        return [list(r) for r in ws.iter_rows(values_only=True)]
    if name.endswith((".csv", ".txt")):
        text = content.decode("utf-8-sig", errors="replace")
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        return [row for row in csv.reader(io.StringIO(text), dialect)]
    raise ValueError("Chỉ hỗ trợ file .csv hoặc .xlsx")


def parse_rows(table: list[list], pages: list[dict], now: datetime) -> list[dict]:
    """Kiểm tra từng dòng. Mỗi kết quả: {row, message, link, photos, scheduled_at, page, errors, warnings}."""
    if not table:
        raise ValueError("File trống")
    cols = map_header(table[0])
    if "message" not in cols.values():
        raise ValueError("Không thấy cột “Nội dung” ở dòng tiêu đề (xem file mẫu)")
    by_name = {_norm(p["name"]): p["id"] for p in pages} | {p["id"]: p["id"] for p in pages} | \
              {p.get("fb_page_id"): p["id"] for p in pages if p.get("fb_page_id")}
    out = []
    for i, raw in enumerate(table[1:], start=2):
        cells = {field: (raw[idx] if idx < len(raw) else None) for idx, field in cols.items()}
        if all(v in (None, "") or str(v).strip() == "" for v in cells.values()):
            continue  # bỏ dòng trống
        row = {"row": i, "errors": [], "warnings": [],
               "message": str(cells.get("message") or "").strip(),
               "link": str(cells.get("link") or "").strip(),
               "photos": split_photos(cells.get("photos")), "page": "",
               "video": str(cells.get("video") or "").strip(), "video_kind": "video"}
        kind_raw = _norm(cells.get("kind"))
        kind = KINDS.get(kind_raw)
        if kind is None:
            row["errors"].append(f"Loại “{cells.get('kind')}” không hợp lệ (dùng Bài viết, Video hoặc Reels)")
            kind = ""
        if kind and not row["video"]:
            row["errors"].append("Loại Video/Reels cần cột Video (link .mp4 hoặc tên video trong thư viện)")
        if row["video"]:
            row["video_kind"] = "reel" if kind == "reel" else "video"
            if row["photos"]:
                row["errors"].append("Một bài chỉ có ảnh hoặc video, không có cả hai")
            if not re.match(r"^https?://", row["video"]) and ("/" in row["video"] or "\\" in row["video"]):
                row["errors"].append(f"Video “{row['video']}”: dùng link video (https://…) hoặc tên video đã có trong thư viện")
        when, err = parse_time(cells.get("scheduled_at"), now)
        if err:
            row["errors"].append(err)
        elif when and datetime.fromisoformat(when) <= now:
            row["warnings"].append("Thời gian đã qua: bài sẽ được đăng ngay")
            when = None
        row["scheduled_at"] = when
        page_ref = str(cells.get("page") or "").strip()
        if page_ref:
            pid = by_name.get(_norm(page_ref)) or by_name.get(page_ref)
            if pid:
                row["page"] = pid
            else:
                row["errors"].append(f"Không tìm thấy Page “{page_ref}”")
        if not (row["message"] or row["photos"] or row["link"] or row["video"]):
            row["errors"].append("Dòng không có nội dung, ảnh, video hay link")
        if row["link"] and not re.match(r"^https?://", row["link"]):
            row["errors"].append("Link phải bắt đầu bằng http:// hoặc https://")
        for ph in row["photos"]:
            if not re.match(r"^https?://", ph) and ("/" in ph or "\\" in ph):
                row["errors"].append(f"Ảnh “{ph}”: dùng link ảnh (https://…) hoặc tên ảnh đã có trong thư viện")
        out.append(row)
        if len(out) > MAX_ROWS:
            raise ValueError(f"Tối đa {MAX_ROWS} bài mỗi lần nhập")
    if not out:
        raise ValueError("File không có dòng nào để nhập")
    return out


def template_csv() -> bytes:
    buf = io.StringIO()
    csv.writer(buf).writerows(TEMPLATE_ROWS)
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM để Excel mở đúng tiếng Việt


def template_xlsx() -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Bài viết"
    for r in TEMPLATE_ROWS:
        ws.append(r)
    for c in ws[1]:
        c.font = Font(bold=True)
    for col, width in zip("ABCDEFG", (60, 30, 40, 20, 20, 40, 12)):
        ws.column_dimensions[col].width = width
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
