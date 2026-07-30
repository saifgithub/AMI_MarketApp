"""CR056 — universal no-assumed-data directive is injected on the shared LLM path.

Defence-in-depth for the phantom-data class (SCHD incident, CR055): every call
routed through ``LLMGateway.stream_chat`` gets a grounding directive prepended to
its system prompt — both handed to the provider and recorded to ``llm_audit`` —
telling the model to use only explicitly-provided facts.

These tests guard the two site-specific caveats that would silently break the
suite if the wording or placement slipped:
  1. the preamble must contain NONE of the agent-id tokens the MockProvider
     routes on (or the mock mis-routes and every mock-dependent test breaks);
  2. the Portfolio Manager safety floor must remain the LAST instruction (the
     directive is prepended, never appended).
Plus idempotency (prepend-once) and a mock-routing no-regression check.

This is a SOFT control (CR038): asserting the directive is *present*, not that
the model obeys it — the structural fix for holdings is CR055.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.agents.safety_floor import render_safety_floor_block
from app.schemas import AgentId
from app.services.agent_prompts import build_agent_prompt
from app.services.llm_gateway import (
    GROUNDING_DIRECTIVE,
    GROUNDING_DIRECTIVE_SENTINEL,
    ChatMessage,
    LLMGateway,
    MockProvider,
    prepend_grounding_directive,
)


# ── helpers ───────────────────────────────────────────────────────────────


class _CapturingProvider(MockProvider):
    """Records the system_prompt it is handed, then yields a trivial chunk.

    Subclasses MockProvider so it registers cleanly under the ``mock`` key that
    the gateway's provider-preference fallback expects.
    """

    name = "mock"

    def __init__(self) -> None:
        self.seen_system_prompt: str | None = None

    async def stream_chat(  # type: ignore[override]
        self,
        *,
        system_prompt: str,
        messages,
        model_tier="cheap",
        max_tokens: int = 1024,
        meta: dict | None = None,  # DEF125 — the gateway's stop-reason channel
    ) -> AsyncIterator[str]:
        self.seen_system_prompt = system_prompt
        yield "ok"


def _gateway_with_capture() -> tuple[LLMGateway, _CapturingProvider]:
    g = LLMGateway()
    cap = _CapturingProvider()
    # Register under a key the preference order (vllm > anthropic > mock) reaches
    # and that the fallback (self._providers["mock"]) can resolve.
    g._providers = {"mock": cap}
    return g, cap


async def _drain(agen) -> str:
    return "".join([c async for c in agen])


# ── 1. directive present on the shared path (provider + audit) ─────────────


async def test_directive_reaches_provider_and_audit(monkeypatch):
    import app.services.audit as audit_mod

    recorded: dict = {}

    def _fake_record(**kwargs):
        recorded.update(kwargs)

    monkeypatch.setattr(audit_mod, "record_llm_call", _fake_record)

    g, cap = _gateway_with_capture()
    out = await _drain(
        g.stream_chat(
            system_prompt="You are the Market Analyst.",
            messages=[ChatMessage(role="user", content="Why is AAPL up?")],
            audit_agent_id="market_analyst",
            audit_flow="one_on_one",
        )
    )

    assert out == "ok"
    # Handed to the provider, at the very top.
    assert cap.seen_system_prompt is not None
    assert cap.seen_system_prompt.startswith(GROUNDING_DIRECTIVE_SENTINEL)
    assert "explicitly provided" in cap.seen_system_prompt
    # And recorded to llm_audit verbatim — how the auditor verifies "every flow".
    assert GROUNDING_DIRECTIVE_SENTINEL in recorded["system_prompt"]
    assert recorded["system_prompt"] == cap.seen_system_prompt


@pytest.mark.parametrize(
    "flow, agent_id, base_prompt_template",
    [
        ("one_on_one", "market_analyst", "You are the Market Analyst."),
        ("concierge_floor", "concierge", "You are the AMI Concierge."),
        ("pm_reformat", None, "Reformat the following verdict into strict JSON."),
        ("room", "portfolio_manager", "You are the Portfolio Manager.{floor}"),
    ],
)
async def test_directive_is_flow_agnostic(flow, agent_id, base_prompt_template, base_mandate):
    """Injected regardless of flow — Room agent, Concierge, and reformatter alike
    (build_agent_prompt would miss the latter two; the gateway does not).

    The "room" case's floor block is rendered through render_safety_floor_block
    (DEF188) rather than the raw SAFETY_FLOOR_BLOCK template, so this test never
    exercises the unsubstituted `[[CAP]]` placeholder.
    """
    floor = render_safety_floor_block(base_mandate) if flow == "room" else ""
    base_prompt = base_prompt_template.format(floor=floor)
    g, cap = _gateway_with_capture()
    await _drain(
        g.stream_chat(
            system_prompt=base_prompt,
            messages=[ChatMessage(role="user", content="hi")],
            audit_agent_id=agent_id,
            audit_flow=flow,
        )
    )
    assert cap.seen_system_prompt.startswith(GROUNDING_DIRECTIVE_SENTINEL)
    assert base_prompt in cap.seen_system_prompt


# ── 2. CAVEAT 1: no agent-id token leaks into the preamble ─────────────────


def test_preamble_contains_no_agent_id_token():
    """The MockProvider routes by matching agent-id substrings in the lowercased
    system prompt. The preamble must contain none of them (all 13 ids, in both
    the ``foo_bar`` and ``foo bar`` forms, and the ``agent_id: foo_bar`` form)."""
    lowered = GROUNDING_DIRECTIVE.lower()
    for aid in AgentId:
        token = aid.value  # e.g. "market_analyst"
        spaced = token.replace("_", " ")  # e.g. "market analyst"
        assert token not in lowered, f"underscore token {token!r} leaked into preamble"
        assert spaced not in lowered, f"spaced token {spaced!r} leaked into preamble"
        assert f"agent_id: {token}" not in lowered


# ── 2b. CAVEAT 1: mock routing still resolves the right agent ──────────────


@pytest.mark.parametrize(
    "agent_key, needle",
    [
        ("portfolio_manager", "gatekeep"),
        ("trader", "instrument"),
        ("concierge", "route"),
        ("market_analyst", "chart"),
    ],
)
async def test_mock_routing_survives_directive(monkeypatch, agent_key, needle):
    """After the directive is prepended, the real MockProvider must still route
    to the SAME canned reply (not _DEFAULT, not a neighbour). Sleep is patched
    out so the char-by-char stream is instant."""
    import app.services.llm_gateway as gw

    async def _no_sleep(*_a, **_k):
        return None

    monkeypatch.setattr(gw.asyncio, "sleep", _no_sleep)

    g = LLMGateway()  # no keys → real MockProvider under "mock"
    text = await _drain(
        g.stream_chat(
            system_prompt=f"agent_id: {agent_key}\nyou are the agent",
            messages=[ChatMessage(role="user", content="hi")],
        )
    )
    assert needle in text.lower(), f"{agent_key} mis-routed after directive injection"
    # And the directive itself rode along on the mock path too.
    # (MockProvider streams the canned reply, so assert routing via the needle;
    #  presence on the prompt is covered by the capturing-provider tests above.)


# ── 3. CAVEAT 2: PM safety floor stays last after prepend ──────────────────


def test_prepend_keeps_trailing_safety_floor_last(base_mandate):
    rendered_floor = render_safety_floor_block(base_mandate)
    pm_prompt = "You are the Portfolio Manager." + rendered_floor
    injected = prepend_grounding_directive(pm_prompt)
    assert injected.startswith(GROUNDING_DIRECTIVE_SENTINEL)
    assert injected.endswith(rendered_floor)  # floor untouched at the tail
    assert injected.index(GROUNDING_DIRECTIVE_SENTINEL) < injected.index("SAFETY FLOOR")


def test_pm_floor_last_through_build_agent_prompt(base_mandate):
    """Faithful check: a real PM prompt (build_agent_prompt appends the floor
    LAST) still ends with the floor after the directive is prepended."""
    rendered_floor = render_safety_floor_block(base_mandate)
    pm = build_agent_prompt(AgentId.PORTFOLIO_MANAGER, base_mandate)
    assert pm.endswith(rendered_floor)  # precondition: floor is last today
    injected = prepend_grounding_directive(pm)
    assert injected.startswith(GROUNDING_DIRECTIVE_SENTINEL)
    assert injected.endswith(rendered_floor)


# ── 4. idempotency: prepend once, never stacked ────────────────────────────


def test_prepend_is_idempotent():
    base = "You are the Market Analyst."
    once = prepend_grounding_directive(base)
    twice = prepend_grounding_directive(once)
    assert once == twice
    assert once.count(GROUNDING_DIRECTIVE_SENTINEL) == 1
    assert twice.count(GROUNDING_DIRECTIVE_SENTINEL) == 1


async def test_gateway_does_not_double_inject(monkeypatch):
    """A prompt that already carries the sentinel is not re-prefixed by the
    gateway (guards against stacking on re-entry)."""
    import app.services.audit as audit_mod

    monkeypatch.setattr(audit_mod, "record_llm_call", lambda **_k: None)

    g, cap = _gateway_with_capture()
    pre_injected = prepend_grounding_directive("You are the Market Analyst.")
    await _drain(
        g.stream_chat(
            system_prompt=pre_injected,
            messages=[ChatMessage(role="user", content="hi")],
        )
    )
    assert cap.seen_system_prompt == pre_injected
    assert cap.seen_system_prompt.count(GROUNDING_DIRECTIVE_SENTINEL) == 1
