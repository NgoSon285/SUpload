"""Nhập bài từ CSV / Excel."""
import io
from datetime import datetime, timedelta

import pytest
from openpyxl import Workbook

from conftest import PNG, upload
from supload.domain import importer
from supload.services import media


def csv_file(text, name="bai.csv"):
    return {"file": (io.BytesIO(text.encode("utf-8")), name)}


def preview(client, files):
    return client.post("/api/import/preview", data=files, content_type="multipart/form-data")


FUTURE = (datetime.now() + timedelta(days=2)).replace(hour=20, minute=0, second=0, microsecond=0)


def test_template_downloads(client):
    r = client.get("/api/import/template")
    assert r.status_code == 200 and "Nội dung" in r.data.decode("utf-8-sig")
    r = client.get("/api/import/template?format=xlsx")
    assert r.status_code == 200 and r.data[:2] == b"PK"


def test_template_parses_cleanly():
    rows = importer.parse_rows(importer.read_table("m.xlsx", importer.template_xlsx()), [], datetime(2026, 1, 1))
    assert len(rows) == 4 and not any(r["errors"] for r in rows)
    assert rows[0]["scheduled_at"] == "2026-12-01T08:00" and rows[3]["scheduled_at"] is None
    assert rows[2]["video"].endswith(".mp4") and rows[2]["video_kind"] == "reel" and rows[0]["video"] == ""


def test_preview_accepts_vietnamese_headers_without_accents_and_semicolons(connected):
    text = f"noi dung;Link;Thoi gian\nXin chào;https://a.vn;{FUTURE:%d/%m/%Y %H:%M}\nBài 2;;\n"
    r = preview(connected, csv_file(text)).get_json()
    assert r["ok"] == 2 and r["bad"] == 0
    assert r["rows"][0]["scheduled_at"] == FUTURE.isoformat(timespec="minutes")
    assert r["rows"][1]["scheduled_at"] is None


@pytest.mark.parametrize("cell,err", [
    ("32/13/2026 25:00", "Không hiểu thời gian"),
])
def test_bad_time_is_reported_per_row(connected, cell, err):
    r = preview(connected, csv_file(f"Nội dung,Thời gian\nA,{cell}\nB,\n")).get_json()
    assert r["bad"] == 1 and err in r["rows"][0]["errors"][0] and r["rows"][0]["row"] == 2


def test_past_time_becomes_post_now_with_warning(connected):
    r = preview(connected, csv_file("Nội dung,Thời gian\nA,01/01/2020 08:00\n")).get_json()
    row = r["rows"][0]
    assert row["scheduled_at"] is None and "đăng ngay" in row["warnings"][0] and not row["errors"]


def test_missing_message_column(connected):
    r = preview(connected, csv_file("Tiêu đề,Link\nA,B\n"))
    assert r.status_code == 400 and "Nội dung" in r.get_json()["error"]


def test_empty_rows_skipped_and_empty_content_flagged(connected):
    r = preview(connected, csv_file("Nội dung,Link,Ảnh\n,,\nA,,\n,,\n,ftp://x,\n")).get_json()
    assert [x["row"] for x in r["rows"]] == [3, 5]
    assert "Link phải bắt đầu" in r["rows"][1]["errors"][0]


def test_unknown_page_and_page_by_name(connected, svc):
    r = preview(connected, csv_file("Nội dung,Page\nA,Không có\nB,Page 111\n")).get_json()
    assert "Không tìm thấy Page" in r["rows"][0]["errors"][0]
    assert r["rows"][1]["page"] == svc.store.load()["pages"][0]["id"]


def test_xlsx_with_real_datetime_cells(connected):
    wb = Workbook()
    ws = wb.active
    ws.append(["Nội dung", "Thời gian"])
    ws.append(["Excel", FUTURE])
    buf = io.BytesIO()
    wb.save(buf)
    r = preview(connected, {"file": (io.BytesIO(buf.getvalue()), "b.xlsx")}).get_json()
    assert r["rows"][0]["scheduled_at"] == FUTURE.isoformat(timespec="minutes")


def test_unsupported_file(connected):
    r = preview(connected, {"file": (io.BytesIO(b"x"), "a.pdf")})
    assert r.status_code == 400 and ".csv" in r.get_json()["error"]


def test_commit_downloads_image_urls_and_uses_library_names(connected, svc, monkeypatch):
    lib = upload(connected, "co-san.png")
    monkeypatch.setattr(media, "fetch", lambda url: (PNG, "image/png"))
    text = f"Nội dung,Ảnh,Thời gian\nCó ảnh link,https://cdn.vn/banh.png,{FUTURE:%Y-%m-%d %H:%M}\nẢnh thư viện,{lib},\n"
    rows = preview(connected, csv_file(text)).get_json()["rows"]
    r = connected.post("/api/import/commit", json={"rows": rows}).get_json()
    assert r["count"] == 2
    posts = {p["message"]: p for p in svc.store.load()["posts"]}
    assert posts["Ảnh thư viện"]["photos"] == [lib]
    downloaded = posts["Có ảnh link"]["photos"][0]
    assert downloaded.endswith("_banh.png") and (svc.config.upload_dir / downloaded).is_file()
    assert all(p["source"] == "import" for p in posts.values())


def test_commit_is_all_or_nothing_unless_skipping(connected, svc):
    rows = preview(connected, csv_file("Nội dung,Thời gian\nTốt,\nLỗi,không-phải-ngày\n")).get_json()["rows"]
    r = connected.post("/api/import/commit", json={"rows": rows})
    assert r.status_code == 400 and r.get_json()["failed"][0]["row"] == 3
    assert svc.store.load()["posts"] == []
    r = connected.post("/api/import/commit", json={"rows": rows, "skip_errors": True}).get_json()
    assert r["count"] == 1 and len(svc.store.load()["posts"]) == 1


def test_commit_rejects_non_image_url(connected, svc, monkeypatch):
    monkeypatch.setattr(media, "fetch", lambda url: (b"<html>", "text/html"))
    rows = preview(connected, csv_file("Nội dung,Ảnh\nA,https://x.vn/trang\n")).get_json()["rows"]
    r = connected.post("/api/import/commit", json={"rows": rows})
    assert r.status_code == 400 and "không phải ảnh" in r.get_json()["failed"][0]["errors"][0]


def test_library_photo_missing_is_flagged_in_preview(connected):
    r = preview(connected, csv_file("Nội dung,Ảnh\nA,khong-co.png\n")).get_json()
    assert "Không có ảnh" in r["rows"][0]["errors"][0]


MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


def test_import_reels_from_link_and_video_from_library(connected, svc, monkeypatch):
    r = connected.post("/api/upload", data={"files": (io.BytesIO(MP4), "co-san.mp4")}, content_type="multipart/form-data")
    lib = r.get_json()["files"][0]

    def fake_fetch(url, dest, max_bytes=0):
        dest.write_bytes(MP4)
        return "video/mp4"
    monkeypatch.setattr(media, "fetch_to_file", fake_fetch)
    text = (f"Nội dung,Video,Loại,Thời gian\nReel mới,https://cdn.vn/hau-truong.mp4,Reels,{FUTURE:%d/%m/%Y %H:%M}\n"
            f"Video thư viện,{lib},Video,\n")
    rows = preview(connected, csv_file(text)).get_json()["rows"]
    assert [x["errors"] for x in rows] == [[], []] and rows[0]["video_kind"] == "reel"
    assert connected.post("/api/import/commit", json={"rows": rows}).get_json()["count"] == 2
    posts = {p["message"]: p for p in svc.store.load()["posts"]}
    reel = posts["Reel mới"]
    assert reel["video_kind"] == "reel" and reel["video"].endswith("_hau-truong.mp4") and (svc.config.upload_dir / reel["video"]).is_file()
    assert posts["Video thư viện"]["video"] == lib and posts["Video thư viện"]["video_kind"] == "video"
    assert not list(svc.config.upload_dir.glob(".tai_*"))  # không để lại file tạm


@pytest.mark.parametrize("text,err", [
    ("Nội dung,Loại\nA,Reels\n", "cần cột Video"),
    ("Nội dung,Video,Loại\nA,x.mp4,Story\n", "không hợp lệ"),
    ("Nội dung,Video,Ảnh\nA,https://x.vn/a.mp4,https://x.vn/a.png\n", "ảnh hoặc video"),
    ("Nội dung,Video\nA,khong-co.mp4\n", "Không có video"),
])
def test_video_rows_are_validated(connected, text, err):
    r = preview(connected, csv_file(text)).get_json()
    assert any(err in e for e in r["rows"][0]["errors"]), r["rows"][0]["errors"]


def test_commit_rejects_non_video_link(connected, svc, monkeypatch):
    def fake_fetch(url, dest, max_bytes=0):
        dest.write_bytes(b"<html>")
        return "text/html"
    monkeypatch.setattr(media, "fetch_to_file", fake_fetch)
    rows = preview(connected, csv_file("Nội dung,Video,Loại\nA,https://x.vn/trang,Reels\n")).get_json()["rows"]
    r = connected.post("/api/import/commit", json={"rows": rows})
    assert r.status_code == 400 and "không phải video" in r.get_json()["failed"][0]["errors"][0]
    assert not list(svc.config.upload_dir.glob(".tai_*"))
