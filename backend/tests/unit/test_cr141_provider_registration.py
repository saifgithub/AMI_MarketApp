"""CR141 — DeepSeek / Qwen / Gemini registered from settings (CR017 §3/§5
step 2), mirroring the existing vLLM/Anthropic/Kimi "presence of key turns
the feature on, absence is a silent no-op (never an error)" pattern.
"""

from __future__ import annotations

from app.services.llm_gateway import LLMGateway, OpenAICompatibleProvider


def test_no_keys_registers_none_of_the_three():
    gw = LLMGateway()
    assert "deepseek" not in gw._providers
    assert "qwen" not in gw._providers
    assert "gemini" not in gw._providers


def test_deepseek_registers_when_key_present(monkeypatch):
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "deepseek_api_key", "sk-deepseek-fake")
    gw = LLMGateway()
    p = gw._providers["deepseek"]
    assert isinstance(p, OpenAICompatibleProvider)
    assert p.name == "deepseek"
    assert p._model_name == "deepseek-chat"
    assert str(p._client.base_url) == "https://api.deepseek.com"
    assert p._client.headers.get("Authorization") == "Bearer sk-deepseek-fake"


def test_qwen_registers_when_dashscope_key_present(monkeypatch):
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "dashscope_api_key", "sk-dashscope-fake")
    gw = LLMGateway()
    p = gw._providers["qwen"]
    assert isinstance(p, OpenAICompatibleProvider)
    assert p.name == "qwen"
    assert p._model_name == "qwen-flash"
    assert str(p._client.base_url) == "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/"
    # CR017 §3 quirk: forces the fast/non-thinking response mode.
    assert p._extra_body == {"enable_thinking": False}


def test_gemini_registers_when_google_ai_key_present(monkeypatch):
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "google_ai_api_key", "sk-google-fake")
    gw = LLMGateway()
    p = gw._providers["gemini"]
    assert isinstance(p, OpenAICompatibleProvider)
    assert p.name == "gemini"
    assert p._model_name == "gemini-2.5-flash"
    assert str(p._client.base_url) == "https://generativelanguage.googleapis.com/v1beta/openai/"


def test_new_providers_do_not_change_default_active_provider(monkeypatch):
    """None of the three joins `_PREFERENCE` — registering them must not
    steal traffic from vLLM/Anthropic/Kimi/mock (CR141 acceptance 4's
    'unkeyed deployment behaves exactly as it does now', extended to 'a
    deployment with ONLY the new keys set still falls back to mock')."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "deepseek_api_key", "sk-deepseek-fake")
    monkeypatch.setattr(cfg.settings, "dashscope_api_key", "sk-dashscope-fake")
    monkeypatch.setattr(cfg.settings, "google_ai_api_key", "sk-google-fake")
    gw = LLMGateway()
    assert gw.status()["active_provider"] == "mock"
    assert set(gw.status()["providers_registered"]) == {
        "deepseek", "qwen", "gemini", "mock",
    }
