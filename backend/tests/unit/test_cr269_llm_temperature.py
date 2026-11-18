"""CR269 (CR267 WP-11) — the desk sampling temperature is pinned in config.

Until now no `temperature` was sent anywhere, so every Room, 1-on-1 and Brief
call sampled at whatever the serving stack defaulted to — and a measurement
could not say what it measured. What these tests pin is the part that fails
SILENTLY when it regresses: that an unset setting leaves the wire byte-identical
to before, that a set one reaches BOTH provider families, and that a blank
compose-forwarded env value reads as "unset" instead of crashing boot.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core import config as cfg
from app.core.config import Settings
from app.services.llm_gateway import (
    AnthropicProvider,
    ChatMessage,
    OpenAICompatibleProvider,
    VLLMProvider,
)
from tests.unit.test_llm_gateway import _FakeClient, _FakeSSEResponse


async def _body(provider) -> dict:
    captured: dict = {}
    provider._client = _FakeClient(  # type: ignore[assignment]
        _FakeSSEResponse(200, ["data: [DONE]"]), captured
    )
    async for _ in provider.stream_chat(
        system_prompt="x",
        messages=[ChatMessage(role="user", content="ping")],
        max_tokens=64,
    ):
        pass
    return captured["json"]


def _providers():
    return [
        OpenAICompatibleProvider(
            name="deepseek", base_url="http://x", model_name="m",
            extra_body={"enable_thinking": False},
        ),
        VLLMProvider(base_url="http://lan:8000", model_name="m"),
        AnthropicProvider(api_key="sk-ant-fake"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("idx", [0, 1, 2], ids=["openai_compat", "vllm", "anthropic"])
async def test_unset_setting_sends_no_temperature(monkeypatch, idx):
    monkeypatch.setattr(cfg.settings, "llm_desk_temperature", None)
    body = await _body(_providers()[idx])
    assert "temperature" not in body


@pytest.mark.asyncio
@pytest.mark.parametrize("idx", [0, 1, 2], ids=["openai_compat", "vllm", "anthropic"])
async def test_set_setting_reaches_the_wire(monkeypatch, idx):
    monkeypatch.setattr(cfg.settings, "llm_desk_temperature", 0.3)
    body = await _body(_providers()[idx])
    assert body["temperature"] == 0.3


@pytest.mark.asyncio
async def test_zero_is_sent_not_mistaken_for_unset(monkeypatch):
    monkeypatch.setattr(cfg.settings, "llm_desk_temperature", 0.0)
    body = await _body(_providers()[0])
    assert body["temperature"] == 0.0


@pytest.mark.asyncio
async def test_anthropic_clamps_above_its_ceiling_and_says_so(monkeypatch):
    from app.services import llm_gateway as gw

    warnings: list[str] = []
    monkeypatch.setattr(
        gw.logger, "warning", lambda event, **kw: warnings.append(event)
    )
    monkeypatch.setattr(cfg.settings, "llm_desk_temperature", 1.5)
    assert (await _body(AnthropicProvider(api_key="sk-ant-fake")))["temperature"] == 1.0
    assert "llm_temperature_clamped" in warnings
    assert (await _body(_providers()[0]))["temperature"] == 1.5


@pytest.mark.parametrize("bad", [-0.1, 2.01, 5])
@pytest.mark.parametrize("field", ["llm_desk_temperature", "llm_judge_temperature"])
def test_out_of_range_is_rejected(field, bad):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: bad})


@pytest.mark.parametrize("ok", [0.0, 0.3, 2.0])
def test_boundary_values_accepted(ok):
    assert Settings(_env_file=None, llm_desk_temperature=ok).llm_desk_temperature == ok


def test_defaults(monkeypatch):
    monkeypatch.delenv("LLM_DESK_TEMPERATURE", raising=False)
    monkeypatch.delenv("LLM_JUDGE_TEMPERATURE", raising=False)
    s = Settings(_env_file=None)
    assert s.llm_desk_temperature is None
    assert s.llm_judge_temperature == 0.0


@pytest.mark.parametrize("raw", ["", "   "])
def test_blank_env_reads_as_none(monkeypatch, raw):
    monkeypatch.setenv("LLM_DESK_TEMPERATURE", raw)
    assert Settings(_env_file=None).llm_desk_temperature is None


def test_env_values_parse(monkeypatch):
    monkeypatch.setenv("LLM_DESK_TEMPERATURE", "0.3")
    monkeypatch.setenv("LLM_JUDGE_TEMPERATURE", "0")
    s = Settings(_env_file=None)
    assert s.llm_desk_temperature == 0.3
    assert s.llm_judge_temperature == 0.0


def test_env_out_of_range_fails_boot(monkeypatch):
    monkeypatch.setenv("LLM_DESK_TEMPERATURE", "3")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
