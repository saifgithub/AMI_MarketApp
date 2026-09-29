"""CR247 Phase 2 — the PM's JSON-schema decoding constraint, ON.

The phase1cd gate (`docs/forward_planning/CR247_teammate_prompt_reasoning_
evaluation/measurements/phase1cd_gate.md`) measured the regression this file
pins the fix for: after 1C/1D lengthened the PM prompt block (+~1.7K chars),
plain-text-verdict-template draws rose from ~1/10 to ~50% on vLLM (6/12 across
two convenes) and ~25% on DeepInfra. Instructional JSON demands hold ~70%
(CR038), so the fix is structural: CR210's `OutputConstraint` machinery already
existed behind `room_json_constraints_enabled` (default off, "flip after the
held-out before/after has run" — phase1cd IS that before). This CR flips the
default ON and pins what the flip must mean:

1. The default is ON in Settings (compose's inline default is pinned by the
   config/compose parity suite).
2. Every PM LLM call carries the `pm_verdict` grammar with the flag at its
   shipped default. There are exactly two PM call sites — `_stream_pm_response`
   (the live draw, which also serves the CR197 self-consistency fan-out AND the
   CR237 CIO-retry route, since all three funnel through it) and
   `_reformat_pm_response` (the DEF058 recovery retry).
3. The parser is the untouched consumer: a schema-honoring reply parses to
   exactly the Verdict it always did, and the old plain-text template still
   fails exactly as today (recovery path intact, fail-safe PASS preserved).
4. The provider matrix at the PM call site: a vLLM-shaped provider gets
   `response_format: json_schema` on the wire; a provider that cannot enforce
   (the DeepInfra-inject shape) drops the grammar with
   `llm_constraint_unsupported` and `constraint_status='unsupported'` and the
   tolerant parser still decides — degrade loudly, never silently.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import pytest
import structlog

from app.core.config import Settings, settings
from app.schemas.agents import AgentId
from app.schemas.room import VerdictAction
from app.services.coach_engine import hydrate_coach_mandate
from app.services.llm_gateway import (
    ChatMessage,
    LLMGateway,
    OpenAICompatibleProvider,
    OutputConstraint,
)
from app.services.room_prompts import pm_verdict_schema
from app.services.room_runner import (
    RoomRunner,
    _collect_agent_stream,
    _parse_pm_verdict,
    _pm_verdict_constraint,
    _RoomContext,
)
from tests.unit.test_room_runner import _collect, _FakeGateway

PM_REPLY = json.dumps(
    {
        "action": "APPROVE",
        "size_pct": 3.0,
        "entry": 150.0,
        "stop": 141.0,
        "target": 172.0,
        "horizon_days": 42,
        "narration": "PM: APPROVE; synthesis defended; mandate clears.",
        "kill_criterion": "A close below the 200-day SMA at $141.00 would reverse this call.",
    }
)

# The exact template the phase1cd gate measured the PM emitting ~50% of the
# time on vLLM — the regression this CR fixes structurally.
PM_PLAIN_TEXT_TEMPLATE = (
    "Verdict: PASS\n"
    "Reasoning: the setup fails the mandate's clean-case bar; waiting costs "
    "little and the next print settles the open question.\n"
    "Mandate compliance: PASS"
)


def _ctx() -> _RoomContext:
    return _RoomContext(
        ticker="AAPL",
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        halal_universe=None,
        classification_universe=None,
        locale_allowed_universe=None,
    )


class _ConstraintRecordingGateway(_FakeGateway):
    """Records the grammar each call carried, so wiring is asserted on the
    wire arguments rather than inferred from the verdict that came back."""

    def __init__(self, replies: dict[str, str] | None = None):
        super().__init__(replies=replies)
        self.constraints: list[tuple[str | None, object]] = []

    async def stream_chat(
        self, *, system_prompt, messages, model_tier, locale="en", max_tokens=1024, **kw
    ):
        self.constraints.append((kw.get("audit_agent_id"), kw.get("constraint")))
        async for chunk in super().stream_chat(
            system_prompt=system_prompt,
            messages=messages,
            model_tier=model_tier,
            locale=locale,
            max_tokens=max_tokens,
        ):
            yield chunk


def _run(gateway, monkeypatch, *, samples: int = 1):
    monkeypatch.setattr(settings, "pm_self_consistency_samples", samples)
    runner = RoomRunner(llm=gateway)  # type: ignore[arg-type]
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    return _collect(
        runner.run(
            user_id=uuid4(),
            ticker="AAPL",
            mandate=mandate,
            char_delay_min=0.0,
            char_delay_max=0.0,
        )
    )


def _pm_constraints(gateway: _ConstraintRecordingGateway) -> list[OutputConstraint]:
    return [
        c
        for agent, c in gateway.constraints
        if agent == AgentId.PORTFOLIO_MANAGER.value and c is not None
    ]


# ── 1. the default ──────────────────────────────────────────────────────────


def test_the_constraint_flag_defaults_on():
    """The flip IS the fix. Read from the model field rather than the live
    singleton so a test that monkeypatched it earlier in the process cannot
    mask a reverted default."""
    assert Settings.model_fields["room_json_constraints_enabled"].default is True
    assert settings.room_json_constraints_enabled is True


# ── 2. call-site wiring, flag at its shipped default ────────────────────────


def test_the_live_pm_draw_carries_the_verdict_schema(monkeypatch):
    """No flag monkeypatch — this is the shipped default's wire shape. The
    CR237 CIO-retry route funnels through the same `_stream_pm_response`, so
    this single assertion covers the live draw, the retry route, and (with
    samples>1, below) the fan-out."""
    gw = _ConstraintRecordingGateway(replies={"portfolio_manager": PM_REPLY})
    _run(gw, monkeypatch)

    pm = _pm_constraints(gw)
    assert len(pm) == 1
    assert pm[0].name == "pm_verdict"
    assert pm[0].json_schema == pm_verdict_schema()
    # and nothing else on the prose path picked a grammar up: the Trader regex
    # is a separate flag that stays OFF, every prose agent carries None.
    for agent, c in gw.constraints:
        if agent != AgentId.PORTFOLIO_MANAGER.value:
            assert c is None, agent


def test_the_self_consistency_fanout_constrains_every_draw(monkeypatch):
    gw = _ConstraintRecordingGateway(replies={"portfolio_manager": PM_REPLY})
    events = _run(gw, monkeypatch, samples=3)

    pm = _pm_constraints(gw)
    assert len(pm) == 3, "every independent read must be schema-pinned"
    assert all(c.name == "pm_verdict" for c in pm)
    v = next(e.verdict for e in events if e.kind == "verdict")
    assert v.action == VerdictAction.APPROVE.value
    assert v.samples == 3


def test_the_reformat_retry_carries_the_schema_too(monkeypatch):
    """The DEF058 recovery path must be at least as strong as the draw it
    recovers: PM emits the plain-text template (unparseable), the reformatter
    gets the SAME grammar and recovers the APPROVE."""

    class _RecoveringGateway(_ConstraintRecordingGateway):
        # The reformatter's system prompt names no agent, so the fake's
        # "Speak as the X" routing never matches it — serve the recovery
        # reply off the reformatter's own self-description instead.
        async def stream_chat(
            self, *, system_prompt, messages, model_tier, locale="en", max_tokens=1024, **kw
        ):
            if "strict formatter" in system_prompt:
                self.constraints.append((kw.get("audit_agent_id"), kw.get("constraint")))
                text = PM_REPLY
                mid = len(text) // 2
                yield text[:mid]
                yield text[mid:]
                return
            async for chunk in super().stream_chat(
                system_prompt=system_prompt,
                messages=messages,
                model_tier=model_tier,
                locale=locale,
                max_tokens=max_tokens,
                **kw,
            ):
                yield chunk

    gw = _RecoveringGateway(
        replies={
            "portfolio_manager": PM_PLAIN_TEXT_TEMPLATE,
        }
    )
    monkeypatch.setattr(settings, "pm_self_consistency_samples", 1)
    events = _collect(
        RoomRunner(llm=gw).run(  # type: ignore[arg-type]
            user_id=uuid4(),
            ticker="AAPL",
            mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
            char_delay_min=0.0,
            char_delay_max=0.0,
        )
    )

    constraints = [c for _, c in gw.constraints if c is not None]
    assert len(constraints) == 2, "PM draw + reformat retry"
    reformat = next(c for c in constraints if c.name == "pm_verdict_reformat")
    assert reformat.kind == "json_schema"
    assert reformat.json_schema == pm_verdict_schema()
    v = next(e.verdict for e in events if e.kind == "verdict")
    assert v.action == VerdictAction.APPROVE.value
    assert v.overridden_from_llm is False


# ── 3. parser compatibility — the consumer is untouched ─────────────────────


def test_a_schema_honoring_reply_parses_to_the_same_verdict_as_before():
    """Pin the demand/consumer seam: the schema is new, the parser is not.
    A grammar-conforming reply must yield exactly the Verdict the same payload
    yielded before the constraint existed."""
    display, verdict = _parse_pm_verdict(PM_REPLY, _ctx())

    assert verdict is not None
    assert verdict.action == VerdictAction.APPROVE
    assert verdict.size_pct == 3.0
    assert verdict.entry == 150.0
    assert verdict.stop == 141.0
    assert verdict.target == 172.0
    assert verdict.time_horizon_days == 42
    assert verdict.kill_criterion == (
        "A close below the 200-day SMA at $141.00 would reverse this call."
    )
    # no annotation fired: size under the risk-tier ceiling and the
    # concentration threshold, horizon inside [1, 365] and coherent with the
    # stop, stop/target stated — so the reason the user reads IS the narration.
    assert verdict.reason == "PM: APPROVE; synthesis defended; mandate clears."
    assert display == verdict.reason
    assert verdict.overridden_from_llm is False


def test_the_plain_text_template_still_fails_exactly_as_today():
    """Anti-regression on the consumer: the schema is a DEMAND, and any path
    where the demand is not honored (unsupported provider, killed switch) must
    behave byte-for-byte as it does today — the template does not parse."""
    text, verdict = _parse_pm_verdict(PM_PLAIN_TEXT_TEMPLATE, _ctx())
    assert verdict is None
    assert text == PM_PLAIN_TEXT_TEMPLATE.strip()


def test_a_plain_text_draw_still_fails_safe_to_pass(monkeypatch):
    """End-to-end: template draw, reformat cannot recover either (its reply is
    also prose) — the run must land on the same DEF059 fail-safe PASS it lands
    on today, with the schema demand having changed nothing downstream."""
    gw = _ConstraintRecordingGateway(
        replies={
            "portfolio_manager": PM_PLAIN_TEXT_TEMPLATE,
        }
    )
    events = _run(gw, monkeypatch)

    v = next(e.verdict for e in events if e.kind == "verdict")
    assert v.action == VerdictAction.PASS.value
    assert v.overridden_from_llm is True
    assert "machine-readable verdict" in v.reason
    # the schema demand went out on the wire regardless — and the reformat
    # retry carried it too, then failed like it always did.
    names = [c.name for c in (c for _, c in gw.constraints if c is not None)]
    assert names == ["pm_verdict", "pm_verdict_reformat"]


# ── 4. the provider matrix at the PM call site ──────────────────────────────


class _FakeSSEResponse:
    def __init__(self, status_code: int, lines: list[str]):
        self.status_code = status_code
        self._lines = lines

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line

    async def aread(self) -> bytes:
        return b""


class _RecordingClient:
    """Captures the request body so the test asserts what actually went on the
    wire — the property the whole CR210 design rests on (a grammar that is
    dropped silently is worse than none)."""

    def __init__(self, bodies: list[dict], resp: _FakeSSEResponse):
        self.bodies = bodies
        self._resp = resp

    @asynccontextmanager
    async def stream(self, method: str, url: str, json: dict):
        self.bodies.append(json)
        yield self._resp

    async def aclose(self) -> None:
        pass


def _sse(payload: str) -> str:
    return f"data: {payload}"


def _pm_stream_lines() -> list[str]:
    mid = len(PM_REPLY) // 2
    return [
        _sse(json.dumps({"choices": [{"index": 0, "delta": {"content": PM_REPLY[:mid]}}]})),
        _sse(json.dumps({"choices": [{"index": 0, "delta": {"content": PM_REPLY[mid:]}}]})),
        _sse(json.dumps({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})),
        _sse(json.dumps({"choices": [], "usage": {"prompt_tokens": 9, "completion_tokens": 2}})),
        "data: [DONE]",
    ]


async def _pm_call_through(gateway: LLMGateway, constraint: OutputConstraint):
    meta: dict[str, Any] = {}
    chunks = await _collect_agent_stream(
        gateway.stream_chat(
            system_prompt="sys",
            messages=[ChatMessage(role="user", content="hi")],
            model_tier="cheap",
            locale="en",
            audit_agent_id=AgentId.PORTFOLIO_MANAGER.value,
            audit_flow="room_pm",
            meta=meta,
            constraint=constraint,
        )
    )
    return "".join(chunks), meta


def _gateway_with(provider: OpenAICompatibleProvider, name: str) -> LLMGateway:
    gateway = LLMGateway()
    gateway._providers[name] = provider  # noqa: SLF001 — test inject, same idiom as test_def376
    return gateway


@pytest.mark.asyncio
async def test_a_vllm_shaped_provider_gets_the_schema_on_the_wire(monkeypatch):
    """The gateway's actual emission for a json_schema constraint, pinned at
    the PM call site: the OpenAI-standard `response_format` spelling the
    served vLLM (0.23.x) enforces under stream: true (verified live
    2026-08-25; re-verified against the qwen3.8 serve by CR247's probe)."""
    bodies: list[dict] = []
    provider = OpenAICompatibleProvider(
        name="vllm",
        base_url="http://lan:8000",
        model_name="ami-llm",
        supported_constraints=frozenset({"json_schema", "regex"}),
    )
    provider._client = _RecordingClient(bodies, _FakeSSEResponse(200, _pm_stream_lines()))  # type: ignore[assignment]
    gateway = _gateway_with(provider, "vllm")
    monkeypatch.setattr(settings, "llm_force_provider", "vllm")

    text, meta = await _pm_call_through(gateway, _pm_verdict_constraint(_ctx()))

    assert bodies[0]["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "pm_verdict",
            "schema": pm_verdict_schema(),
            "strict": True,
        },
    }
    assert meta["constraint"] == {
        "name": "pm_verdict",
        "kind": "json_schema",
        "provider": "vllm",
        "status": "enforced",
    }
    # and the constrained reply is exactly what the room's parser consumes
    _, verdict = _parse_pm_verdict(text, _ctx())
    assert verdict is not None and verdict.action == VerdictAction.APPROVE


@pytest.mark.asyncio
async def test_a_deepinfra_shaped_provider_drops_the_schema_loudly(monkeypatch):
    """force_deepinfra_gateway() registers a plain OpenAICompatibleProvider
    with NO supported_constraints — this builds exactly that shape. The
    capability gate must drop the grammar, warn, record 'unsupported', and the
    PM's tolerant parser path must still decide. Never silent."""
    bodies: list[dict] = []
    provider = OpenAICompatibleProvider(
        name="deepinfra",
        base_url="https://api.deepinfra.com",
        model_name="zai-org/GLM-5.3-Flash",
    )
    provider._client = _RecordingClient(bodies, _FakeSSEResponse(200, _pm_stream_lines()))  # type: ignore[assignment]
    gateway = _gateway_with(provider, "deepinfra")
    monkeypatch.setattr(settings, "llm_force_provider", "deepinfra")

    with structlog.testing.capture_logs() as logs:
        text, meta = await _pm_call_through(gateway, _pm_verdict_constraint(_ctx()))

    # 1. the grammar never reached the wire
    assert "response_format" not in bodies[0]
    assert "structured_outputs" not in bodies[0]
    # 2. the drop is recorded in the machine channel, per-call
    assert meta["constraint"]["status"] == "unsupported"
    assert meta["constraint"]["provider"] == "deepinfra"
    # 3. it is said out loud, at warning level
    warns = [r for r in logs if r["event"] == "llm_constraint_unsupported"]
    assert len(warns) == 1
    assert warns[0]["provider"] == "deepinfra"
    assert warns[0]["constraint"] == "pm_verdict"
    # 4. the call itself is unaffected: same body shape as today minus the
    #    grammar, and the reply still parses through the tolerant parser.
    _, verdict = _parse_pm_verdict(text, _ctx())
    assert verdict is not None and verdict.action == VerdictAction.APPROVE
