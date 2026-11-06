"""Dòng lệnh: đăng bài qua Graph API (không cần giao diện).

  python fb_poster.py token --user-token <TOKEN>
  python fb_poster.py post -m "Xin chào" -p anh.jpg [-s "2026-12-01 09:00"]
  python fb_poster.py batch posts.json --delay 60
  python fb_poster.py kiemtra --video clip.mp4 [--reel] [--page "Tên Page"] [--xoa]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from ..config import ROOT  # noqa: F401  (nạp .env)
from ..integrations import facebook as fb
from ..integrations.facebook import (
    FBError, PagePoster, exchange_long_lived_user_token, list_pages, parse_schedule, poster_from_env,
)

LOG_FILE = Path("post_log.jsonl")


def log_result(entry: dict) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), **entry}, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- CLI
def cmd_token(args) -> None:
    app_id, secret = os.getenv("FB_APP_ID"), os.getenv("FB_APP_SECRET")
    if not app_id or not secret:
        raise FBError("Cần FB_APP_ID và FB_APP_SECRET trong .env")
    long_user = exchange_long_lived_user_token(app_id, secret, args.user_token)
    pages = list_pages(long_user)
    if not pages:
        print("Không thấy Page nào. Kiểm tra quyền pages_show_list / pages_manage_posts.")
        return
    print("Page Access Token (từ user token dài hạn -> không hết hạn):\n")
    for p in pages:
        print(f"# {p['name']}\nFB_PAGE_ID={p['id']}\nFB_PAGE_TOKEN={p['access_token']}\n")
    print("=> Copy cặp dòng của Page cần dùng vào file .env")


def cmd_post(args) -> None:
    res = poster_from_env().post(
        message=args.message or "",
        link=args.link,
        photos=args.photo,
        schedule=parse_schedule(args.schedule),
    )
    log_result({"ok": True, "message": args.message, "result": res})
    print("Đã đăng:", res)


def cmd_batch(args) -> None:
    posts = json.loads(Path(args.file).read_text(encoding="utf-8"))
    poster = poster_from_env()
    ok = 0
    for i, item in enumerate(posts, 1):
        try:
            res = poster.post(
                message=item.get("message", ""),
                link=item.get("link"),
                photos=item.get("photos"),
                schedule=parse_schedule(item.get("schedule")),
            )
            ok += 1
            log_result({"ok": True, "index": i, "result": res})
            print(f"[{i}/{len(posts)}] OK {res}")
        except FBError as e:
            log_result({"ok": False, "index": i, "error": str(e)})
            print(f"[{i}/{len(posts)}] LỖI {e}", file=sys.stderr)
        if i < len(posts) and args.delay:
            time.sleep(args.delay)
    print(f"Xong: {ok}/{len(posts)} bài thành công. Log: {LOG_FILE}")


# ---------------------------------------------------------------- kiểm tra thật trên Page
def _poster_for(page_ref: str | None) -> tuple[PagePoster, str]:
    """Page trong data.json (theo tên hoặc Page ID), hoặc FB_PAGE_ID/FB_PAGE_TOKEN trong .env."""
    if page_ref:
        from ..config import data_home
        data_file = data_home() / "data.json"
        pages = json.loads(data_file.read_text(encoding="utf-8")).get("pages", []) if data_file.exists() else []
        for pg in pages:
            if pg.get("kind") == "api" and page_ref in (pg.get("name"), pg.get("fb_page_id"), pg.get("id")):
                return PagePoster(pg["fb_page_id"], pg["token"]), pg.get("name") or pg["fb_page_id"]
        raise FBError(f"Không thấy Page qua API nào tên/ID '{page_ref}' trong {data_file}")
    return poster_from_env(), os.getenv("FB_PAGE_ID", "")


def cmd_check(args, sleep=time.sleep) -> bool:
    """Đăng thử 1 video/Reel lên Page rồi kiểm tra từng bước. Trả về True nếu các bước chính đều qua."""
    results: list[tuple[str, bool, str]] = []

    def step(name, fn):
        try:
            detail = fn()
            results.append((name, True, detail or ""))
            print(f"  [OK]   {name}{': ' + detail if detail else ''}")
            return True
        except FBError as e:
            results.append((name, False, str(e)))
            print(f"  [LỖI] {name}: {e}")
            return False

    poster, label = _poster_for(args.page)
    kind = "Reels" if args.reel else "video"
    print(f"Kiểm tra thật trên Page {label} ({kind}: {args.video})\n")
    st: dict = {}
    if not step("Token Page dùng được", lambda: fb.page_info(poster.page_id, poster.token).get("name", "")):
        return False

    def upload():
        msg = args.message or f"SUpload kiểm tra {kind} {datetime.now():%H:%M %d/%m}"
        res = (poster.post_reel if args.reel else poster.post_video)(args.video, msg)
        st["id"] = res["id"]
        return f"video id={res['id']}"
    if not step(f"Tải và đăng {kind}", upload):
        return False

    def wait_ready():
        deadline = time.time() + args.wait
        while True:
            d = fb.call("GET", st["id"], params={"access_token": poster.token, "fields": "status,published,permalink_url"})
            vs = (d.get("status") or {}).get("video_status")
            if vs == "error":
                raise FBError(f"Facebook xử lý video bị lỗi: {d.get('status')}")
            if vs == "ready" and d.get("published"):
                return f"đã lên, xem tại https://www.facebook.com{d.get('permalink_url') or ''}".rstrip("/")
            if time.time() > deadline:
                raise FBError(f"Sau {args.wait}s vẫn chưa xong (video_status={vs}, published={d.get('published')}). Xem lại trên Page sau ít phút.")
            sleep(10)
    step("Facebook xử lý xong và hiển thị", wait_ready)

    def video_stats():
        s = poster.engagement(st["id"], video=True)
        if s["reach_error"]:
            raise FBError(f"thích={s['reactions']}, bình luận={s['comments']} nhưng không lấy được lượt xem: {s['reach_error']}")
        return f"thích={s['reactions']}, bình luận={s['comments']}, lượt xem={s['reach']}"
    step("Số liệu video (likes, comments, total_video_views)", video_stats)

    def post_stats():
        posts = fb.call("GET", f"{poster.page_id}/posts", params={"access_token": poster.token, "limit": 1}).get("data") or []
        if not posts:
            return "Page chưa có bài viết nào để thử"
        s = poster.engagement(posts[0]["id"])
        if s["reach_error"]:
            raise FBError(f"cảm xúc={s['reactions']} nhưng không lấy được người xem: {s['reach_error']}")
        return f"bài {posts[0]['id']}: cảm xúc={s['reactions']}, bình luận={s['comments']}, chia sẻ={s['shares']}, người xem={s['reach']}"
    step("Số liệu bài mới nhất (post_total_media_view_unique)", post_stats)

    if args.instagram:
        def ig_post():
            info = fb.page_info(poster.page_id, poster.token).get("instagram_business_account")
            if not info:
                raise FBError("Page chưa liên kết tài khoản Instagram doanh nghiệp (hoặc token thiếu quyền instagram_basic)")
            ig = fb.InstagramPoster(info["id"], poster)
            res = ig.post_reel(args.video, args.message or f"SUpload kiểm tra Instagram {datetime.now():%H:%M %d/%m}")
            return f"@{info.get('username', '')}: {ig.permalink(res['id']) or res['id']} (xoá thủ công trên Instagram nếu không cần)"
        step("Đăng Reels lên Instagram liên kết (thử nghiệm)", ig_post)

    if args.xoa:
        step("Xoá video thử", lambda: poster.delete(st["id"]))

    failed = [r for r in results if not r[1]]
    print(f"\nKết quả: {len(results) - len(failed)}/{len(results)} bước qua.")
    log_result({"ok": not failed, "check": kind, "steps": [{"step": n, "ok": ok, "detail": d} for n, ok, d in results]})
    return not failed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Đăng bài tự động lên Facebook Page (Graph API)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("token", help="Lấy Page Access Token dài hạn")
    t.add_argument("--user-token", required=True, help="User token từ Graph API Explorer")
    t.set_defaults(func=cmd_token)

    p = sub.add_parser("post", help="Đăng 1 bài")
    p.add_argument("-m", "--message")
    p.add_argument("-l", "--link")
    p.add_argument("-p", "--photo", action="append", help="URL hoặc đường dẫn ảnh (lặp lại để thêm nhiều ảnh)")
    p.add_argument("-s", "--schedule", help="Hẹn giờ 'YYYY-MM-DD HH:MM'")
    p.set_defaults(func=cmd_post)

    b = sub.add_parser("batch", help="Đăng hàng loạt từ file JSON")
    b.add_argument("file")
    b.add_argument("--delay", type=int, default=60, help="Số giây chờ giữa các bài (mặc định 60)")
    b.set_defaults(func=cmd_batch)

    k = sub.add_parser("kiemtra", help="Đăng thử 1 video/Reel lên Page phụ và kiểm tra đăng + số liệu")
    k.add_argument("--video", required=True, help="Đường dẫn video ngắn (.mp4)")
    k.add_argument("--reel", action="store_true", help="Đăng dạng Reels (video dọc 9:16, 3-90 giây)")
    k.add_argument("--page", help="Tên hoặc Page ID đã thêm trong ứng dụng (mặc định: FB_PAGE_ID/FB_PAGE_TOKEN trong .env)")
    k.add_argument("-m", "--message", help="Chú thích (mặc định: 'SUpload kiểm tra …')")
    k.add_argument("--wait", type=int, default=300, help="Số giây chờ Facebook xử lý video (mặc định 300)")
    k.add_argument("--xoa", action="store_true", help="Xoá video thử sau khi kiểm tra")
    k.add_argument("--instagram", action="store_true", help="Đăng thử thêm video đó dạng Reels lên Instagram liên kết với Page")
    k.set_defaults(func=cmd_check)

    args = ap.parse_args(argv)
    try:
        if args.func(args) is False:
            return 1
    except FBError as e:
        print("Lỗi:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
