"""Trợ lý AI: gợi ý nội dung bài đăng."""
from __future__ import annotations

import os

from flask import Blueprint, jsonify, request

from ..domain import pages as pages_domain
from ..integrations import ai
from . import error, services

bp = Blueprint("ai", __name__, url_prefix="/api/ai")


@bp.get("/models")
def models():
    return jsonify(models=ai.MODELS, tones=ai.TONES, default=ai.DEFAULT_MODEL)


@bp.post("/suggest")
def suggest():
    body = request.get_json(force=True)
    data = services().store.load()
    s = data["settings"]
    key = s.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
    if not key:
        return error("Chưa có API key OpenAI: vào Cài đặt → Trợ lý AI để nhập", 400, need_key=True)
    page = pages_domain.find(data, body.get("page")) or pages_domain.default_page(data)
    try:
        items = ai.suggest(key, s.get("ai_model"), body.get("action", ""), body.get("text", ""),
                           page_name=(page or {}).get("name", ""), tone=body.get("tone", ""), base_url=s.get("ai_base_url", ""))
    except ai.AIError as e:
        return error(str(e))
    return jsonify(suggestions=items, model=ai.clean_model(s.get("ai_model")))
