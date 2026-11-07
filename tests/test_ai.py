"""Trợ lý AI (OpenAI API được giả lập - không gọi mạng, không tốn tiền)."""
import json
from types import SimpleNamespace

import httpx
import openai
import pytest

from supload.integrations import ai


def reply(text, finish_reason="stop", refusal=None):
    msg = SimpleNamespace(content=text, refusal=refusal)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason=finish_reason)])


class FakeOpenAI:
    def __init__(self):
        self.calls = []
        self.suggestions = ["Phương án 1", "Phương án 2", "Phương án 3"]
        self.finish_reason, self.refusal, self.raise_exc, self.raw = "stop", None, None, None

    def __call__(self, client, **kw):
        self.calls.append({"api_key": client.api_key, "base_url": str(client.base_url), **kw})
        if self.raise_exc:
            raise self.raise_exc
        text = self.raw if self.raw is not None else json.dumps({"suggestions": self.suggestions}, ensure_ascii=False)
        return reply(text, self.finish_reason, self.refusal)


@pytest.fixture
def gpt(monkeypatch):
    f = FakeOpenAI()
    monkeypatch.setattr(ai, "create", f)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return f


def test_needs_key(connected, gpt):
    r = connected.post("/api/ai/suggest", json={"action": "improve", "text": "x"})
    assert r.status_code == 400 and r.get_json()["need_key"] is True and gpt.calls == []


def test_key_is_secret_and_request_shape(connected, gpt):
    connected.post("/api/settings", json={"openai_api_key": "sk-SECRET"})
    raw = connected.get("/api/state").get_data(as_text=True)
    assert "sk-SECRET" not in raw and '"openai_api_key_set": true' in raw.replace(":true", ": true")
    connected.post("/api/settings", json={"deepseek_api_key": "sk-1234567890abcd"})
    st = connected.get("/api/state").get_json()["settings"]
    assert st["deepseek_api_key_tail"] == "abcd" and st["openai_api_key_tail"] == ""  # key ngắn: không lộ ký tự nào
    assert "sk-1234567890abcd" not in connected.get("/api/state").get_data(as_text=True)
    assert connected.post("/api/settings/reveal", json={"key": "deepseek_api_key"}).get_json()["value"] == "sk-1234567890abcd"
    assert connected.post("/api/settings/reveal", json={"key": "app_secret"}).status_code == 400  # chỉ key AI
    r = connected.post("/api/ai/suggest", json={"action": "improve", "text": "Bánh ngon", "tone": "fun"}).get_json()
    assert r["suggestions"] == ["Phương án 1", "Phương án 2", "Phương án 3"] and r["model"] == "gpt-5.4-mini"
    c = gpt.calls[0]
    assert c["api_key"] == "sk-SECRET" and c["model"] == "gpt-5.4-mini" and c["base_url"].startswith("https://api.openai.com")
    fmt = c["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert c["max_completion_tokens"] == 8000 and "max_tokens" not in c and "temperature" not in c
    system, user = c["messages"]
    assert system["role"] == "system" and "không bịa giá" in system["content"]
    assert "<noi_dung>\nBánh ngon\n</noi_dung>" in user["content"] and "vui nhộn" in user["content"] and "Page 111" in user["content"]


def test_env_key_used_when_not_saved(connected, gpt, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-ENV")
    assert connected.post("/api/ai/suggest", json={"action": "idea", "text": "khai trương"}).status_code == 200
    assert gpt.calls[0]["api_key"] == "sk-ENV"
    assert connected.get("/api/state").get_json()["settings"]["ai_env_keys"] == {"openai": True, "deepseek": False, "gemini": False}


def test_custom_model_and_compatible_base_url(connected, svc, gpt):
    connected.post("/api/settings", json={"openai_api_key": "k", "ai_model": " llama3.1 ", "ai_base_url": "http://localhost:11434/v1/"})
    s = svc.store.load()["settings"]
    assert s["ai_model"] == "llama3.1" and s["ai_base_url"] == "http://localhost:11434/v1"
    connected.post("/api/ai/suggest", json={"action": "variants", "text": "x"})
    assert gpt.calls[0]["model"] == "llama3.1" and gpt.calls[0]["base_url"].startswith("http://localhost:11434/v1")


@pytest.mark.parametrize("model,base", [("", "ftp://x"), ("x" * 101, "không phải url"), ("x" * 200, "")])
def test_invalid_model_or_url_falls_back(connected, svc, gpt, model, base):
    connected.post("/api/settings", json={"ai_model": model, "ai_base_url": base})
    s = svc.store.load()["settings"]
    assert s["ai_model"] == "gpt-5.4-mini" and s["ai_base_url"] == ""


def test_old_settings_are_cleaned_on_load(tmp_path):
    from supload.storage import Store
    old = {"settings": {"old_ai_key": "sk-OLD", "ai_model": "old-model", "min_gap": 60}, "posts": [], "flows": [], "pages": []}
    (tmp_path / "data.json").write_text(json.dumps(old), encoding="utf-8")
    s = Store(tmp_path / "data.json").load()["settings"]
    assert "old_ai_key" not in s and s["min_gap"] == 60  # khoá lạ bị bỏ, cài đặt hợp lệ giữ nguyên
    assert s["ai_model"] == "gpt-5.4-mini" and s["openai_api_key"] == ""  # dữ liệu trước bản OpenAI: về model mặc định


def test_model_kept_once_saved_with_openai_version(tmp_path):
    from supload.storage import Store
    new = {"settings": {"ai_model": "gpt-5.4", "ai_base_url": ""}, "posts": [], "flows": [], "pages": []}
    (tmp_path / "data.json").write_text(json.dumps(new), encoding="utf-8")
    assert Store(tmp_path / "data.json").load()["settings"]["ai_model"] == "gpt-5.4"


def test_hashtags_are_normalised(connected, gpt):
    connected.post("/api/settings", json={"openai_api_key": "k"})
    gpt.suggestions = ["#banhngon", "tiem banh", "#banhngon", "  "]
    r = connected.post("/api/ai/suggest", json={"action": "hashtags", "text": "x"}).get_json()
    assert r["suggestions"] == ["#banhngon", "#tiembanh"]


@pytest.mark.parametrize("attrs,msg", [
    ({"refusal": "Tôi không thể giúp"}, "từ chối"),
    ({"finish_reason": "content_filter"}, "từ chối"),
    ({"finish_reason": "length"}, "quá dài"),
    ({"raw": "không phải json"}, "không đọc được"),
    ({"raw": None, "suggestions": ["", " "]}, "không đưa ra gợi ý"),
])
def test_bad_responses(connected, gpt, attrs, msg):
    connected.post("/api/settings", json={"openai_api_key": "k"})
    for k, v in attrs.items():
        setattr(gpt, k, v)
    r = connected.post("/api/ai/suggest", json={"action": "improve", "text": "x"})
    assert r.status_code == 400 and msg in r.get_json()["error"]


def _api_error(cls, status):
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return cls("lỗi", response=httpx.Response(status, request=req), body=None)


@pytest.mark.parametrize("exc,msg", [
    (lambda: _api_error(openai.AuthenticationError, 401), "không hợp lệ"),
    (lambda: _api_error(openai.NotFoundError, 404), "Không tìm thấy model"),
    (lambda: _api_error(openai.RateLimitError, 429), "giới hạn tốc độ"),
    (lambda: _api_error(openai.InternalServerError, 500), "OpenAI (GPT) báo lỗi (500)"),
    (lambda: openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com")), "Không kết nối"),
])
def test_api_errors_are_explained(connected, gpt, exc, msg):
    connected.post("/api/settings", json={"openai_api_key": "k"})
    gpt.raise_exc = exc()
    r = connected.post("/api/ai/suggest", json={"action": "improve", "text": "x"})
    assert r.status_code == 400 and msg in r.get_json()["error"]


@pytest.mark.parametrize("body,msg", [({"action": "zzz", "text": "x"}, "không hợp lệ"), ({"action": "improve", "text": " "}, "viết nội dung"),
                                      ({"action": "improve", "text": "x" * 7000}, "quá dài")])
def test_input_validation(connected, gpt, body, msg):
    connected.post("/api/settings", json={"openai_api_key": "k"})
    r = connected.post("/api/ai/suggest", json=body)
    assert r.status_code == 400 and msg in r.get_json()["error"] and gpt.calls == []


def test_reply_suggestions_for_comment(connected, gpt):
    connected.post("/api/settings", json={"openai_api_key": "k"})
    r = connected.post("/api/ai/suggest", json={"action": "reply", "text": "Bình luận của An: giá sao ạ"})
    assert r.status_code == 200 and "Viết 3 câu trả lời" in gpt.calls[0]["messages"][1]["content"]


def test_deepseek_uses_own_key_url_and_json_object(connected, svc, gpt):
    connected.post("/api/settings", json={"openai_api_key": "sk-OPENAI", "ai_provider": "deepseek", "ai_model": "",
                                          "deepseek_api_key": "sk-DS"})
    assert svc.store.load()["settings"]["ai_model"] == "deepseek-flash"  # model trống -> mặc định của DeepSeek
    raw = connected.get("/api/state").get_data(as_text=True)
    assert "sk-DS" not in raw and "sk-OPENAI" not in raw
    r = connected.post("/api/ai/suggest", json={"action": "improve", "text": "x"}).get_json()
    assert r["provider"] == "deepseek" and r["model"] == "deepseek-flash"
    c = gpt.calls[0]
    assert c["api_key"] == "sk-DS" and c["base_url"].startswith("https://api.deepseek.com")
    assert c["response_format"] == {"type": "json_object"} and "JSON" in c["messages"][0]["content"]
    assert c["max_tokens"] == 8000 and "max_completion_tokens" not in c


def test_gemini_env_key_and_schema(connected, gpt, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-ENV")
    connected.post("/api/settings", json={"ai_provider": "gemini", "ai_model": "gemini-3.6-flash"})
    assert connected.post("/api/ai/suggest", json={"action": "idea", "text": "x"}).status_code == 200
    c = gpt.calls[0]
    assert c["api_key"] == "AIza-ENV" and c["base_url"].startswith("https://generativelanguage.googleapis.com/v1beta/openai")
    assert c["response_format"]["type"] == "json_schema" and c["model"] == "gemini-3.6-flash"


def test_needs_key_of_selected_provider(connected, gpt):
    connected.post("/api/settings", json={"openai_api_key": "k", "ai_provider": "gemini"})
    r = connected.post("/api/ai/suggest", json={"action": "improve", "text": "x"})
    assert r.status_code == 400 and r.get_json()["need_key"] is True and "Gemini" in r.get_json()["error"]


def test_unknown_provider_falls_back(connected, svc, gpt):
    connected.post("/api/settings", json={"ai_provider": "zzz"})
    assert svc.store.load()["settings"]["ai_provider"] == "openai"


def test_models_endpoint_lists_providers(connected):
    p = connected.get("/api/ai/models").get_json()["providers"]
    assert set(p) == {"openai", "deepseek", "gemini"} and "gpt-5.4-mini" in p["openai"]["models"]
