"""Trợ lý AI (Claude API được giả lập - không gọi mạng, không tốn tiền)."""
import json
from types import SimpleNamespace

import anthropic
import httpx2 as httpx
import pytest

from supload.integrations import ai


class FakeClaude:
    def __init__(self, suggestions=None, stop_reason="end_turn", raise_exc=None, raw=None):
        self.calls = []
        self.suggestions = suggestions or ["Phương án 1", "Phương án 2", "Phương án 3"]
        self.stop_reason, self.raise_exc, self.raw = stop_reason, raise_exc, raw

    def __call__(self, client, **kw):
        self.calls.append({"api_key": client.api_key, **kw})
        if self.raise_exc:
            raise self.raise_exc
        text = self.raw if self.raw is not None else json.dumps({"suggestions": self.suggestions}, ensure_ascii=False)
        return SimpleNamespace(stop_reason=self.stop_reason, content=[SimpleNamespace(type="text", text=text)])


@pytest.fixture
def claude(monkeypatch):
    f = FakeClaude()
    monkeypatch.setattr(ai, "create", f)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return f


def test_needs_key(connected, claude):
    r = connected.post("/api/ai/suggest", json={"action": "improve", "text": "x"})
    assert r.status_code == 400 and r.get_json()["need_key"] is True and claude.calls == []


def test_key_is_secret_and_request_shape(connected, claude):
    connected.post("/api/settings", json={"anthropic_api_key": "sk-ant-SECRET"})
    raw = connected.get("/api/state").get_data(as_text=True)
    assert "sk-ant-SECRET" not in raw and '"anthropic_api_key_set": true' in raw.replace(":true", ": true")
    r = connected.post("/api/ai/suggest", json={"action": "improve", "text": "Bánh ngon", "tone": "fun"}).get_json()
    assert r["suggestions"] == ["Phương án 1", "Phương án 2", "Phương án 3"]
    c = claude.calls[0]
    assert c["api_key"] == "sk-ant-SECRET" and c["model"] == "claude-opus-5-5"
    assert c["fallbacks"] == "default" and c["betas"] == ["server-side-fallback-2026-07-01"]
    assert c["output_config"]["format"]["type"] == "json_schema" and c["output_config"]["effort"] == "low"
    prompt = c["messages"][0]["content"]
    assert "<noi_dung>\nBánh ngon\n</noi_dung>" in prompt and "vui nhộn" in prompt and "Page 111" in prompt
    assert "temperature" not in c and "thinking" not in c


def test_env_key_used_when_not_saved(connected, claude, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-ENV")
    assert connected.post("/api/ai/suggest", json={"action": "idea", "text": "khai trương"}).status_code == 200
    assert claude.calls[0]["api_key"] == "sk-ant-ENV"
    assert connected.get("/api/state").get_json()["settings"]["ai_env_key"] is True


def test_haiku_has_no_server_fallback(connected, claude):
    connected.post("/api/settings", json={"anthropic_api_key": "k", "ai_model": "claude-haiku-5-5"})
    connected.post("/api/ai/suggest", json={"action": "variants", "text": "x"})
    assert claude.calls[0]["model"] == "claude-haiku-5-5" and "fallbacks" not in claude.calls[0]


def test_unknown_model_setting_falls_back_to_default(connected, svc, claude):
    connected.post("/api/settings", json={"ai_model": "gpt-5"})
    assert svc.store.load()["settings"]["ai_model"] == "claude-opus-5-5"


def test_hashtags_are_normalised(connected, claude):
    connected.post("/api/settings", json={"anthropic_api_key": "k"})
    claude.suggestions = ["#banhngon", "tiem banh", "#banhngon", "  "]
    r = connected.post("/api/ai/suggest", json={"action": "hashtags", "text": "x"}).get_json()
    assert r["suggestions"] == ["#banhngon", "#tiembanh"]


@pytest.mark.parametrize("kwargs,msg", [
    ({"stop_reason": "refusal"}, "từ chối"),
    ({"stop_reason": "max_tokens"}, "quá dài"),
    ({"raw": "không phải json"}, "không đọc được"),
    ({"suggestions": ["", " "]}, "không đưa ra gợi ý"),
])
def test_bad_responses(connected, claude, kwargs, msg):
    connected.post("/api/settings", json={"anthropic_api_key": "k"})
    for k, v in kwargs.items():
        setattr(claude, k, v)
    r = connected.post("/api/ai/suggest", json={"action": "improve", "text": "x"})
    assert r.status_code == 400 and msg in r.get_json()["error"]


def _api_error(cls, status):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("lỗi", response=httpx.Response(status, request=req), body=None)


@pytest.mark.parametrize("exc,msg", [
    (lambda: _api_error(anthropic.AuthenticationError, 401), "không hợp lệ"),
    (lambda: _api_error(anthropic.RateLimitError, 429), "giới hạn tốc độ"),
    (lambda: anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com")), "Không kết nối"),
])
def test_api_errors_are_explained(connected, claude, exc, msg):
    connected.post("/api/settings", json={"anthropic_api_key": "k"})
    claude.raise_exc = exc()
    r = connected.post("/api/ai/suggest", json={"action": "improve", "text": "x"})
    assert r.status_code == 400 and msg in r.get_json()["error"]


@pytest.mark.parametrize("body,msg", [({"action": "zzz", "text": "x"}, "không hợp lệ"), ({"action": "improve", "text": " "}, "viết nội dung"),
                                      ({"action": "improve", "text": "x" * 7000}, "quá dài")])
def test_input_validation(connected, claude, body, msg):
    connected.post("/api/settings", json={"anthropic_api_key": "k"})
    r = connected.post("/api/ai/suggest", json=body)
    assert r.status_code == 400 and msg in r.get_json()["error"] and claude.calls == []
