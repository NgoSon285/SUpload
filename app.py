#!/usr/bin/env python3
"""SUpload - giao diện trực quan để soạn, xếp lịch và đăng bài lên Facebook Page.

Chạy:  python app.py   ->  mở http://127.0.0.1:5000
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

import fb_poster

BASE = Path(__file__).resolve().parent
DATA_FILE = BASE / "data.json"
UPLOAD_DIR = BASE / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

DEFAULT_SETTINGS = {
    "method": "api",  # "api" | "browser"
    "page_id": os.getenv("FB_PAGE_ID", ""),
    "page_token": os.getenv("FB_PAGE_TOKEN", ""),
    "page_name": "",
    "app_id": os.getenv("FB_APP_ID", ""),
    "app_secret": os.getenv("FB_APP_SECRET", ""),
    "page_url": "",
    "headless": False,
    "min_gap": 300,  # giây tối thiểu giữa 2 bài (chế độ trình duyệt)
}

WEB_DIR = BASE / "web"  # bản build của frontend/ (npm run build)
app = Flask(__name__, static_folder=str(WEB_DIR / "assets"), static_url_path="/assets")
lock = threading.RLock()  # bảo vệ data.json
browser_lock = threading.Lock()  # chỉ 1 thao tác trình duyệt tại 1 thời điểm
wake = threading.Event()
state = {"worker": "Đang rảnh", "login": "unknown", "last_browser_post": 0.0}


# ---------------------------------------------------------------- storage
def load() -> dict:
    with lock:
        if DATA_FILE.exists():
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        else:
            data = {}
        data.setdefault("settings", {})
        data["settings"] = {**DEFAULT_SETTINGS, **data["settings"]}
        data.setdefault("posts", [])
        data.setdefault("log", [])
        return data


def save(data: dict) -> None:
    with lock:
        tmp = DATA_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(DATA_FILE)


def add_log(data: dict, level: str, text: str) -> None:
    data["log"].insert(0, {"at": now_iso(), "level": level, "text": text})
    del data["log"][300:]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def public_settings(s: dict) -> dict:
    out = dict(s)
    for k in ("page_token", "app_secret"):
        out[k + "_set"] = bool(out.get(k))
        out[k] = ""
    return out


def update_post(post_id: str, **fields) -> None:
    with lock:
        data = load()
        for p in data["posts"]:
            if p["id"] == post_id:
                p.update(fields)
        save(data)


# ---------------------------------------------------------------- worker
def publish(post: dict, settings: dict) -> str:
    photos = [str(UPLOAD_DIR / f) for f in post.get("photos", [])]
    if settings["method"] == "api":
        poster = fb_poster.PagePoster(settings["page_id"], settings["page_token"])
        res = poster.post(message=post.get("message", ""), link=post.get("link") or None, photos=photos)
        return f"id={res.get('post_id') or res.get('id')}"

    import browser_poster  # chỉ cần playwright khi dùng chế độ trình duyệt

    if not settings["page_url"]:
        raise browser_poster.PostError("Chưa nhập URL của Page trong Cài đặt")
    gap = settings["min_gap"] - (time.time() - state["last_browser_post"])
    if gap > 0:
        state["worker"] = f"Chờ {int(gap)}s giãn cách trước khi đăng"
        time.sleep(gap)
    message = post.get("message", "")
    if post.get("link"):
        message = f"{message}\n{post['link']}".strip()
    with browser_lock:
        state["worker"] = "Đang đăng qua trình duyệt..."
        browser_poster.post_once(settings["page_url"], message, photos, settings["headless"])
    state["last_browser_post"] = time.time()
    return "đã đăng qua trình duyệt"


def next_due(data: dict) -> dict | None:
    now = datetime.now()
    due = [
        p for p in data["posts"]
        if p["status"] == "pending" and (not p.get("scheduled_at") or datetime.fromisoformat(p["scheduled_at"]) <= now)
    ]
    due.sort(key=lambda p: p.get("scheduled_at") or p["created_at"])
    return due[0] if due else None


def worker() -> None:
    while True:
        with lock:
            data = load()
            post = next_due(data)
            if post:
                post["status"] = "running"
                save(data)
        if not post:
            state["worker"] = "Đang rảnh"
            wake.wait(10)
            wake.clear()
            continue
        state["worker"] = "Đang đăng: " + (post.get("message") or "(ảnh)")[:40]
        try:
            info = publish(post, data["settings"])
            update_post(post["id"], status="done", done_at=now_iso(), result=info, error="")
            level, text = "ok", f"Đã đăng: {(post.get('message') or '(ảnh)')[:60]} ({info})"
        except Exception as e:  # noqa: BLE001
            update_post(post["id"], status="error", done_at=now_iso(), error=str(e))
            level, text = "error", f"Lỗi khi đăng: {e}"
        with lock:
            data = load()
            add_log(data, level, text)
            save(data)


# ---------------------------------------------------------------- routes
@app.get("/")
def index():
    if not (WEB_DIR / "index.html").exists():
        return "Chưa có giao diện. Chạy: cd frontend && npm install && npm run build", 500
    return send_from_directory(WEB_DIR, "index.html")


@app.get("/uploads/<path:name>")
def uploaded(name):
    return send_from_directory(UPLOAD_DIR, name)


@app.get("/api/state")
def api_state():
    data = load()
    return jsonify(
        settings=public_settings(data["settings"]),
        posts=sorted(data["posts"], key=lambda p: p["created_at"], reverse=True),
        log=data["log"][:100],
        worker=state["worker"],
        login=state["login"],
    )


@app.post("/api/settings")
def api_settings():
    body = request.get_json(force=True)
    with lock:
        data = load()
        s = data["settings"]
        if body.get("page_id") is not None and body["page_id"] != s["page_id"]:
            s["page_name"] = ""  # Page khác -> tên cũ không còn đúng
        for k in DEFAULT_SETTINGS:
            if k not in body:
                continue
            if k in ("page_token", "app_secret") and not body[k]:
                continue  # để trống = giữ giá trị cũ
            s[k] = body[k]
        s["min_gap"] = max(0, int(s.get("min_gap") or 0))
        s["headless"] = bool(s.get("headless"))
        add_log(data, "info", "Đã lưu cài đặt")
        save(data)
    return jsonify(ok=True)


@app.post("/api/upload")
def api_upload():
    names = []
    for f in request.files.getlist("files"):
        ext = Path(f.filename or "").suffix.lower()
        if ext not in ALLOWED_EXT:
            return jsonify(error=f"Định dạng không hỗ trợ: {f.filename}"), 400
        name = f"{uuid.uuid4().hex[:8]}_{secure_filename(f.filename) or 'img' + ext}"
        f.save(UPLOAD_DIR / name)
        names.append(name)
    return jsonify(files=names)


@app.post("/api/posts")
def api_add_post():
    try:
        fields = _clean_post_body(request.get_json(force=True))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    sched = fields["scheduled_at"]
    post = {
        "id": uuid.uuid4().hex[:10],
        **fields,
        "status": "pending",
        "created_at": now_iso(),
        "done_at": None,
        "error": "",
        "result": "",
    }
    with lock:
        data = load()
        data["posts"].append(post)
        add_log(data, "info", "Đã thêm bài " + (f"hẹn {sched.replace('T', ' ')}" if sched else "đăng ngay"))
        save(data)
    wake.set()
    return jsonify(post=post)


def _clean_post_body(body: dict):
    message = (body.get("message") or "").strip()
    photos = [p for p in body.get("photos", []) if (UPLOAD_DIR / p).is_file()]
    link = (body.get("link") or "").strip()
    if not (message or photos or link):
        raise ValueError("Bài viết đang trống")
    sched = body.get("scheduled_at") or None
    if sched:
        try:
            sched = datetime.fromisoformat(sched).isoformat(timespec="minutes")
        except ValueError:
            raise ValueError("Thời gian hẹn không hợp lệ")
    return {"message": message, "photos": photos, "link": link, "scheduled_at": sched}


@app.put("/api/posts/<post_id>")
def api_edit_post(post_id):
    try:
        fields = _clean_post_body(request.get_json(force=True))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    with lock:
        data = load()
        post = next((p for p in data["posts"] if p["id"] == post_id), None)
        if not post:
            return jsonify(error="Không tìm thấy bài"), 404
        if post["status"] not in ("pending", "error"):
            return jsonify(error="Chỉ sửa được bài đang chờ hoặc bị lỗi"), 400
        post.update(fields, status="pending", error="")
        add_log(data, "info", "Đã sửa bài: " + (fields["message"] or "(ảnh)")[:50])
        save(data)
    wake.set()
    return jsonify(post=post)


@app.post("/api/test-connection")
def api_test_connection():
    s = load()["settings"]
    if s["method"] == "browser":
        threading.Thread(target=_browser_job, args=("check",), daemon=True).start()
        return jsonify(ok=True, pending=True, text="Đang kiểm tra đăng nhập trong trình duyệt...")
    if not (s["page_id"] and s["page_token"]):
        return jsonify(error="Chưa có Page ID / Page Token"), 400
    try:
        info = fb_poster._call("GET", s["page_id"], params={"access_token": s["page_token"], "fields": "name"})
    except fb_poster.FBError as e:
        return jsonify(error=str(e)), 400
    with lock:
        data = load()
        data["settings"]["page_name"] = info.get("name", "")
        add_log(data, "ok", f"Kết nối thành công tới Page: {info.get('name')}")
        save(data)
    return jsonify(ok=True, text=f"Kết nối tốt tới Page “{info.get('name')}”")


@app.get("/api/flows")
def api_flows():
    return jsonify(flows=load().get("flows", []))


@app.put("/api/flows/<flow_id>")
def api_save_flow(flow_id):
    body = request.get_json(force=True)
    flow = {
        "id": flow_id,
        "name": (body.get("name") or "Flow chưa đặt tên").strip()[:80],
        "nodes": body.get("nodes", []),
        "edges": body.get("edges", []),
        "seed": str(body.get("seed") or flow_id)[:40],
        "updated_at": now_iso(),
    }
    with lock:
        data = load()
        flows = data.setdefault("flows", [])
        idx = next((i for i, f in enumerate(flows) if f["id"] == flow_id), None)
        if idx is None:
            flows.append(flow)
        else:
            flows[idx] = flow
        save(data)
    return jsonify(flow=flow)


@app.delete("/api/flows/<flow_id>")
def api_delete_flow(flow_id):
    with lock:
        data = load()
        data["flows"] = [f for f in data.get("flows", []) if f["id"] != flow_id]
        save(data)
    return jsonify(ok=True)


@app.post("/api/flows/run")
def api_run_flow():
    """Nhận danh sách bài đã tính giờ từ flow -> thêm hàng loạt vào lịch đăng."""
    body = request.get_json(force=True)
    items = body.get("posts", [])
    if not items:
        return jsonify(error="Flow chưa có bài viết nào"), 400
    if len(items) > 500:
        return jsonify(error="Tối đa 500 bài mỗi lần chạy"), 400
    created, now = [], datetime.now()
    try:
        for it in items:
            fields = _clean_post_body(it)
            if fields["scheduled_at"] and datetime.fromisoformat(fields["scheduled_at"]) <= now:
                fields["scheduled_at"] = None  # giờ đã qua -> đăng ngay
            created.append({
                "id": uuid.uuid4().hex[:10], **fields, "status": "pending", "created_at": now_iso(),
                "done_at": None, "error": "", "result": "", "flow": (body.get("name") or "")[:80],
            })
    except ValueError as e:
        return jsonify(error=f"Bài #{len(created) + 1}: {e}"), 400
    with lock:
        data = load()
        data["posts"].extend(created)
        add_log(data, "info", f"Chạy flow “{body.get('name') or 'không tên'}”: thêm {len(created)} bài vào lịch")
        save(data)
    wake.set()
    return jsonify(count=len(created))


@app.delete("/api/posts/<post_id>")
def api_delete_post(post_id):
    with lock:
        data = load()
        data["posts"] = [p for p in data["posts"] if not (p["id"] == post_id and p["status"] != "running")]
        save(data)
    return jsonify(ok=True)


@app.post("/api/posts/<post_id>/retry")
def api_retry(post_id):
    update_post(post_id, status="pending", error="", scheduled_at=None)
    wake.set()
    return jsonify(ok=True)


@app.post("/api/clear-done")
def api_clear_done():
    with lock:
        data = load()
        data["posts"] = [p for p in data["posts"] if p["status"] != "done"]
        save(data)
    return jsonify(ok=True)


@app.post("/api/fb/pages")
def api_fb_pages():
    """Đổi user token -> danh sách Page kèm Page token dài hạn."""
    body = request.get_json(force=True)
    s = load()["settings"]
    app_id = body.get("app_id") or s["app_id"]
    secret = body.get("app_secret") or s["app_secret"]
    if not (app_id and secret and body.get("user_token")):
        return jsonify(error="Cần App ID, App Secret và User Token"), 400
    try:
        long_token = fb_poster.exchange_long_lived_user_token(app_id, secret, body["user_token"])
        pages = fb_poster.list_pages(long_token)
    except fb_poster.FBError as e:
        return jsonify(error=str(e)), 400
    with lock:
        data = load()
        data["settings"]["app_id"], data["settings"]["app_secret"] = app_id, secret
        data["_pages"] = pages  # giữ token phía máy chủ, không gửi về trình duyệt
        save(data)
    return jsonify(pages=[{"id": p["id"], "name": p["name"]} for p in pages])


@app.post("/api/fb/select-page")
def api_select_page():
    page_id = request.get_json(force=True).get("id")
    with lock:
        data = load()
        page = next((p for p in data.get("_pages", []) if p["id"] == page_id), None)
        if not page:
            return jsonify(error="Không tìm thấy Page"), 404
        data["settings"].update(page_id=page["id"], page_token=page["access_token"], page_name=page["name"])
        add_log(data, "ok", f"Đã chọn Page: {page['name']}")
        save(data)
    return jsonify(ok=True)


def _browser_job(fn_name: str) -> None:
    try:
        import browser_poster
    except ImportError:
        state["login"] = "error: chưa cài playwright (pip install playwright && playwright install chromium)"
        return
    if not browser_lock.acquire(blocking=False):
        state["login"] = "busy"
        return
    try:
        state["login"] = "waiting" if fn_name == "login" else "checking"
        ok = browser_poster.login_wait() if fn_name == "login" else browser_poster.check_login()
        state["login"] = "yes" if ok else "no"
    except Exception as e:  # noqa: BLE001
        state["login"] = f"error: {e}"
    finally:
        browser_lock.release()


@app.post("/api/browser/<action>")
def api_browser(action):
    if action not in ("login", "check"):
        return jsonify(error="unknown"), 404
    threading.Thread(target=_browser_job, args=(action,), daemon=True).start()
    return jsonify(ok=True)


def recover_running() -> None:
    """Bài đang 'running' khi tắt app -> đánh dấu lỗi để người dùng tự quyết định đăng lại."""
    with lock:
        data = load()
        for p in data["posts"]:
            if p["status"] == "running":
                p.update(status="error", error="Ứng dụng bị tắt khi đang đăng - kiểm tra Page trước khi đăng lại")
        save(data)


if __name__ == "__main__":
    recover_running()
    threading.Thread(target=worker, daemon=True).start()
    port = int(os.getenv("PORT", "5000"))
    if not os.getenv("NO_BROWSER"):
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    print(f"SUpload đang chạy tại http://127.0.0.1:{port}  (Ctrl+C để thoát)")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
