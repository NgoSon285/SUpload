"""Trợ lý AI: gợi ý nội dung bài đăng."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..domain import pages as pages_domain
from ..integrations import ai
from . import error, services

bp = Blueprint("ai", __name__, url_prefix="/api/ai")


@bp.get("/models")
def models():
    return jsonify(providers={k: {f: v[f] for f in ("label", "models", "key_url", "key_hint", "env")}
                              for k, v in ai.PROVIDERS.items()}, tones=ai.TONES)


@bp.post("/suggest")
def suggest():
    body = request.get_json(force=True)
    data = services().store.load()
    s = data["settings"]
    provider = ai.clean_provider(s.get("ai_provider"))
    if not ai.api_key(s):
        return error(f"Chưa có API key {ai.PROVIDERS[provider]['label']}: vào Cài đặt → Trợ lý AI để nhập", 400, need_key=True)
    page = pages_domain.find(data, body.get("page")) or pages_domain.default_page(data)
    try:
        items = ai.suggest_with(s, body.get("action", ""), body.get("text", ""),
                                page_name=(page or {}).get("name", ""), tone=body.get("tone", ""))
    except ai.AIError as e:
        return error(str(e))
    return jsonify(suggestions=items, provider=provider, model=ai.clean_model(s.get("ai_model"), provider))
