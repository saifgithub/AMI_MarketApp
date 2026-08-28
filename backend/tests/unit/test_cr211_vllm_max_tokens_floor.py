"""CR211 — the on-prem vLLM decode-budget floor.

Alpha was repointed (2026-08-28) from the non-reasoning `ami-llm` to
`qwen3.8-flash-next`, a REASONING model. The Room's per-agent budgets in
`room_prompts.py` are derived from measured VISIBLE output and budget nothing
for chain-of-thought, so every one of the eight agents in the first live
convene came back `llm_call_length_stop` with `chars: 0` — the whole budget
spent thinking, nothing written.

`OpenAICompatibleProvider`'s `max_tokens_floor` already solved this for Kimi
(CR130) and is tested there. What these tests pin is the part CR211 adds and
the part that fails SILENTLY when it regresses: that `VLLMProvider` forwards
the setting at all, and that 0 means "no floor" rather than "a floor of 0".
A floor that is silently not wired looks exactly like a floor that is.
"""

from __future__ import annotations

import pytest

from app.services.llm_gateway import LLMGateway, VLLMProvider


def test_vllm_provider_forwards_the_floor_to_the_request():
    """The wiring CR211 adds. Without the constructor forwarding, this is the
    test that reds — the request goes out at the caller's starved 800."""
    p = VLLMProvider(
        base_url="http://lan:8048",
        model_name="qwen3.8-flash-next",
        max_tokens_floor=3600,
    )
    assert p._max_tokens_floor == 3600


def test_vllm_provider_without_a_floor_leaves_the_budget_alone():
    """The default. A non-reasoning server must carry no floor at all, so the
    room's tuned per-agent budgets reach the wire unmodified."""
    p = VLLMProvider(base_url="http://lan:8000", model_name="ami-llm")
    assert p._max_tokens_floor is None


def test_gateway_reads_the_floor_from_settings(monkeypatch):
    """End of the wire: SETTING -> provider. This is the join that broke twice
    before as a missing compose line (DEF038/DEF063) and would break here as a
    missing constructor kwarg."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "vllm_base_url", "http://lan:8048")
    monkeypatch.setattr(cfg.settings, "vllm_model", "qwen3.8-flash-next")
    monkeypatch.setattr(cfg.settings, "vllm_max_tokens_floor", 3600)

    g = LLMGateway()
    assert g._providers["vllm"]._max_tokens_floor == 3600


def test_a_zero_setting_registers_no_floor_not_a_floor_of_zero(monkeypatch):
    """0 is the off switch. `max(requested, 0)` is a no-op either way, so this
    cannot be caught by behaviour — only by the value the provider carries and
    the boot log therefore reports. A provider reporting `0` reads as
    'floor in force, set to zero', which is not a state that exists."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "vllm_base_url", "http://lan:8000")
    monkeypatch.setattr(cfg.settings, "vllm_model", "ami-llm")
    monkeypatch.setattr(cfg.settings, "vllm_max_tokens_floor", 0)

    g = LLMGateway()
    assert g._providers["vllm"]._max_tokens_floor is None


@pytest.mark.asyncio
async def test_the_floor_reaches_the_wire_on_a_starved_room_budget(monkeypatch):
    """The measured failure, in miniature: the Fundamentals Analyst asks for
    800 (its derived cap) and must go out at 3600, or it returns chars=0."""
    from tests.unit.test_llm_gateway import _FakeClient, _FakeSSEResponse
    from app.services.llm_gateway import ChatMessage

    captured: dict = {}
    p = VLLMProvider(
        base_url="http://lan:8048",
        model_name="qwen3.8-flash-next",
        max_tokens_floor=3600,
    )
    p._client = _FakeClient(_FakeSSEResponse(200, ["data: [DONE]"]), captured)  # type: ignore[assignment]

    async for _ in p.stream_chat(
        system_prompt="x",
        messages=[ChatMessage(role="user", content="ping")],
        max_tokens=800,
    ):
        pass

    assert captured["json"]["max_tokens"] == 3600
