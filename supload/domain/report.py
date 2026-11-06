"""Báo cáo thống kê ra file Excel (.xlsx): Tổng quan, Bài viết, Theo giờ, Theo thứ, Bình luận."""
from __future__ import annotations

import io
from datetime import datetime

from .insights import engagement

KIND = {"reel": "Reels", "video": "Video"}


def build_xlsx(summary: dict, posts: list[dict], comments: list[dict], page_name, title: str, since: datetime, now: datetime) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    head_font, head_fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="4C6EF5")

    def sheet(ws, header, rows, widths):
        ws.append(header)
        first = ws.max_row + 1  # dòng dữ liệu đầu tiên
        for c in ws[ws.max_row]:
            c.font, c.fill = head_font, head_fill
        for r in rows:
            ws.append(r)
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = f"A{first}"  # giữ dòng tiêu đề khi cuộn

    wb = Workbook()
    ws = wb.active
    ws.title = "Tổng quan"
    ws.append([title])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([f"Từ {since:%d/%m/%Y} đến {now:%d/%m/%Y} · xuất lúc {now:%H:%M %d/%m/%Y}"])
    ws.append([])
    t = summary["totals"]
    hidden = sum(1 for c in comments if c.get("hidden"))
    replied = sum(1 for c in comments if c.get("replies"))
    rows = [
        ("Số bài có số liệu", summary["posts"]), ("Tổng tương tác", t["engagement"]), ("Cảm xúc", t["reactions"]),
        ("Bình luận", t["comments"]), ("Chia sẻ", t["shares"]), ("Tiếp cận / lượt xem", t["reach"] if t["reach"] is not None else "—"),
        ("Tương tác trung bình / bài", summary["avg_engagement"]),
        ("Giờ đăng hiệu quả nhất", ", ".join(f"{h}:00" for h in summary["best_hours"]) or "Chưa đủ dữ liệu"),
        ("Bình luận nhận được (trong ứng dụng)", len(comments)), ("Đã trả lời", replied), ("Đã ẩn", hidden),
    ]
    sheet(ws, ["Chỉ số", "Giá trị"], rows, [38, 24])

    def kind(p):
        return KIND.get(p.get("video_kind"), "Video") if p.get("video") else ("Ảnh" if p.get("photos") else "Chữ/Link")

    sheet(wb.create_sheet("Bài viết"),
          ["Đăng lúc", "Page", "Loại", "Nội dung", "Cảm xúc", "Bình luận", "Chia sẻ", "Tổng tương tác", "Tiếp cận / lượt xem", "Link"],
          [[datetime.fromisoformat(p["done_at"]).strftime("%d/%m/%Y %H:%M"), page_name(p), kind(p), (p.get("message") or "")[:500],
            p["stats"].get("reactions", 0), p["stats"].get("comments", 0), p["stats"].get("shares", 0), engagement(p["stats"]),
            p["stats"].get("reach") if p["stats"].get("reach") is not None else "",
            f"https://www.facebook.com/{p['fb_id']}" if p.get("fb_id") else ""] for p in posts],
          [17, 20, 10, 60, 10, 10, 10, 14, 18, 40])
    for row in wb["Bài viết"].iter_rows(min_row=2, min_col=4, max_col=4):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    sheet(wb.create_sheet("Theo giờ"), ["Giờ", "Số bài", "Tổng tương tác", "TB tương tác"],
          [[f"{b['key']}:00", b["posts"], b["engagement"], b["avg"] or 0] for b in summary["by_hour"]], [10, 10, 16, 14])
    sheet(wb.create_sheet("Theo thứ"), ["Thứ", "Số bài", "Tổng tương tác", "TB tương tác"],
          [[b["label"], b["posts"], b["engagement"], b["avg"] or 0] for b in summary["by_dow"]], [10, 10, 16, 14])
    sheet(wb.create_sheet("Bình luận"), ["Thời gian", "Người bình luận", "Bình luận", "Trên bài", "Đã trả lời", "Đã ẩn"],
          [[(c.get("created_time") or "")[:16].replace("T", " "), c["from_name"], c["message"][:500], (c.get("post_text") or "")[:120],
            "Có" if c.get("replies") else "", "Có" if c.get("hidden") else ""] for c in comments],
          [17, 22, 60, 40, 11, 9])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
