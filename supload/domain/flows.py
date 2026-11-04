from __future__ import annotations

import copy
import re

from ..utils import new_id, stamp
from .posts import ACTIVE, DONE, ERROR

FLOW_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_NODES = 300
EDITABLE_FIELDS = ("name", "description", "nodes", "edges", "seed", "page")


def validate_graph(src: dict) -> tuple[list, list]:
    nodes, edges = src.get("nodes", []), src.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("Flow không hợp lệ: nodes/edges phải là danh sách")
    if len(nodes) > MAX_NODES:
        raise ValueError(f"Flow quá lớn (tối đa {MAX_NODES} khối)")
    for n in nodes:
        if not isinstance(n, dict) or not n.get("id") or not n.get("type"):
            raise ValueError("Flow không hợp lệ: mỗi khối cần có id và type")
    return nodes, edges


def _base(name, description, nodes, edges, seed) -> dict:
    return {
        "name": (str(name or "").strip()[:80]) or "Flow chưa đặt tên",
        "description": str(description or "").strip()[:300],
        "nodes": nodes, "edges": edges, "seed": str(seed or new_id(n=12))[:40],
    }


def upsert(flow_id: str, old: dict | None, body: dict) -> dict:
    """Tạo/cập nhật flow; trường không gửi lên thì giữ nguyên (đổi tên không mất khối)."""
    old = old or {}
    merged = {**old, **{k: v for k, v in body.items() if k in EDITABLE_FIELDS}}
    nodes, edges = validate_graph(merged)
    return {
        "id": flow_id, **_base(merged.get("name"), merged.get("description"), nodes, edges, merged.get("seed") or flow_id),
        "page": str(merged.get("page") or ""),  # "" = Page mặc định
        "created_at": old.get("created_at") or stamp(), "updated_at": stamp(),
        "last_run_at": old.get("last_run_at"), "last_run_count": old.get("last_run_count", 0),
    }


def _fresh(src: dict, name: str, seed=None) -> dict:
    nodes, edges = validate_graph(src)
    return {
        "id": new_id("f_", 12), **_base(name, src.get("description"), copy.deepcopy(nodes), copy.deepcopy(edges), seed),
        "page": str(src.get("page") or ""), "created_at": stamp(), "updated_at": stamp(), "last_run_at": None, "last_run_count": 0,
    }


def duplicate(src: dict) -> dict:
    return _fresh(src, f"{src['name']} (bản sao)"[:80])


def imported(src: dict) -> dict:
    nodes, _ = validate_graph(src)
    if not any(n.get("type") == "start" for n in nodes):
        raise ValueError("Flow không hợp lệ: thiếu khối Bắt đầu")
    return _fresh(src, src.get("name") or "Flow nhập", seed=src.get("seed"))


def stats(posts: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in posts:
        fid = p.get("flow_id")
        if not fid:
            continue
        st = out.setdefault(fid, {"pending": 0, "done": 0, "error": 0})
        if p["status"] in ACTIVE:
            st["pending"] += 1
        elif p["status"] == DONE:
            st["done"] += 1
        elif p["status"] == ERROR:
            st["error"] += 1
    return out
