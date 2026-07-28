"""DEF125 — per-agent decode budgets, and a length-stop that is never silent.

One flat `max_tokens=400` served all eleven streamed Room agents and cut the
Research Manager off mid-sentence in 66.1% of convenes (measured on melehost's
`llm_audit`, 30 days, ~884 calls/agent). Nothing logged it, nothing marked the
transcript, and the truncated synthesis is what the Trader, the three Risk
debators and the PM reason from — DEF095's contagion vector, feeding on a
fragment that reads as a finished thought.

Three things are pinned here, in the order they have to hold:

  1. **The budget table covers the roster.** An agent that gains a length guide
     without a budget silently inherits the flat legacy value — the exact drift
     this defect is. Vacuity-checked against `_LENGTH_GUIDE`'s own membership,
     so adding a thirteenth agent fails the build rather than defaulting.
  2. **The runner spends the budget it was given**, per agent, at every one of
     the three call sites (streamed agents, the PM, the PM reformatter).
  3. **A length stop is disclosed** — logged at the gateway for every flow, and
     marked in the transcript for the Room, so both the downstream agents and
     the user can see the turn is incomplete (CR040).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator
from uuid import uuid4

import pytest

from app.schemas import AgentId
from app.services import room_prompts
from app.services.coach_engine import hydrate_coach_mandate
from app.services.llm_gateway import (
    AnthropicProvider,
    ChatMessage,
    VLLMProvider,
)
from app.services.room_prompts import (
    _AGENT_MAX_TOKENS,
    _DEFAULT_AGENT_MAX_TOKENS,
    _LENGTH_GUIDE,
    max_tokens_for,
)
from app.services.room_runner import RoomRunner
from tests.unit.test_room_runner import _collect


# ── 1. the table covers the roster ───────────────────────────────────────


def test_every_agent_with_a_length_guide_has_a_decode_budget():
    """The ask and the budget that pays for it drifted apart because they lived
    in different files. They live in one file now; this keeps them in step."""
    assert len(_LENGTH_GUIDE) == 12, "vacuity guard — the roster is 12 agents"
    missing = sorted(
        a.value for a in _LENGTH_GUIDE if a not in _AGENT_MAX_TOKENS
    )
    assert missing == [], (
        f"agents asked for output with no decode budget: {missing} — they fall "
        f"back to the flat {_DEFAULT_AGENT_MAX_TOKENS}, which is the defect"
    )


def test_the_three_measured_truncated_agents_got_more_than_the_flat_cap():
    """RM 66.1%, Bull 60.6%, Bear 25.6% of turns ended mid-word at 400 tokens.
    Anything that walks those back to the old value re-opens the defect."""
    for agent in (
        AgentId.RESEARCH_MANAGER,
        AgentId.BULL_RESEARCHER,
        AgentId.BEAR_RESEARCHER,
    ):
        assert max_tokens_for(agent) > 400, (
            f"{agent.value} was measured truncating at 400 tokens"
        )
    # The RM is the worst case AND the most damaging (its synthesis is the only
    # input EXECUTION and RISK see), so it gets the most headroom of the three.
    assert max_tokens_for(AgentId.RESEARCH_MANAGER) >= max_tokens_for(
        AgentId.BULL_RESEARCHER
    )
    # Symmetric researchers: a Bear budgeted below the Bull would make the
    # bear case shorter for a reason no reader could see.
    assert max_tokens_for(AgentId.BULL_RESEARCHER) == max_tokens_for(
        AgentId.BEAR_RESEARCHER
    )


def test_agents_measured_inside_the_cap_were_not_inflated():
    """`max_tokens` is free in decode but not in scheduling — vLLM reserves KV
    blocks against it. The four agents measured at ≤0.1% keep the low budget."""
    for agent in (
        AgentId.MARKET_ANALYST,
        AgentId.NEWS_ANALYST,
        AgentId.SOCIAL_MEDIA_ANALYST,
        AgentId.AGGRESSIVE_DEBATOR,
        AgentId.CONSERVATIVE_DEBATOR,
    ):
        assert max_tokens_for(agent) == _DEFAULT_AGENT_MAX_TOKENS


def test_the_pm_reformatter_is_never_budgeted_below_the_pm():
    """The reformatter re-emits the SAME JSON envelope the PM was asked for. A
    smaller budget means the DEF058 recovery path is clipped exactly whenever
    the original was — the retry failing for the reason it was invoked. Both
    call sites read the PM's single entry, so this holds by construction; the
    test states the invariant so a future split notices it."""
    assert max_tokens_for(AgentId.PORTFOLIO_MANAGER) >= 600


def test_unknown_agent_falls_back_rather_than_raising():
    """A new agent should speak at the old budget, not fail to speak."""

    class _NotAnAgent:
        pass

    assert max_tokens_for(_NotAnAgent()) == _DEFAULT_AGENT_MAX_TOKENS  # type: ignore[arg-type]


# ── 2. the runner spends the per-agent budget ────────────────────────────


class _BudgetRecordingGateway:
    """Records the `max_tokens` each agent's turn was issued with."""

    def __init__(self) -> None:
        self.budgets: dict[str, int] = {}

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(
        self, *, system_prompt, messages, model_tier,
        locale="en", max_tokens=1024, audit_agent_id=None, meta=None, **_kw,
    ):
        if audit_agent_id:
            self.budgets[audit_agent_id] = max_tokens
        yield "AMI agent live reply."


def test_each_agent_is_issued_its_own_budget_not_a_flat_one():
    fake = _BudgetRecordingGateway()
    runner = RoomRunner(llm=fake)  # type: ignore[arg-type]
    _collect(runner.run(
        user_id=uuid4(),
        ticker="AAPL",
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        char_delay_min=0.0,
        char_delay_max=0.0,
    ))

    # Non-vacuity: the whole roster streamed.
    assert len(fake.budgets) == 12, fake.budgets
    for agent in _LENGTH_GUIDE:
        assert fake.budgets[agent.value] == max_tokens_for(agent), (
            f"{agent.value} was issued {fake.budgets[agent.value]}, "
            f"table says {max_tokens_for(agent)}"
        )
    # The defect itself: not one flat number across the roster.
    assert len(set(fake.budgets.values())) > 1


# ── 3. a length stop is disclosed ────────────────────────────────────────


class _TruncatingGateway:
    """Reports a `length` finish for one agent and a clean stop for the rest."""

    def __init__(self, truncated_agent: str) -> None:
        self._truncated = truncated_agent

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(
        self, *, system_prompt, messages, model_tier,
        locale="en", max_tokens=1024, audit_agent_id=None, meta=None, **_kw,
    ):
        if meta is not None:
            meta["finish_reason"] = (
                "length" if audit_agent_id == self._truncated else "stop"
            )
        if audit_agent_id == AgentId.PORTFOLIO_MANAGER.value:
            yield (
                '{"action": "PASS", "size_pct": null, "entry": null, '
                '"stop": null, "target": null, "horizon_days": null, '
                '"narration": "PM: sitting this one out."}'
            )
        else:
            yield "A sentence that the model was still in the middle of"


def _transcript_for(truncated_agent: str):
    runner = RoomRunner(llm=_TruncatingGateway(truncated_agent))  # type: ignore[arg-type]
    events = _collect(runner.run(
        user_id=uuid4(),
        ticker="AAPL",
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        char_delay_min=0.0,
        char_delay_max=0.0,
    ))
    return runner.get_run(events[0].run_id).transcript


def test_a_length_stopped_turn_is_marked_incomplete_in_the_transcript():
    """The mark travels into the transcript, so the Trader / Risk / PM read
    'this is incomplete' instead of inheriting a fragment as a conclusion."""
    transcript = _transcript_for(AgentId.RESEARCH_MANAGER.value)
    rm = next(
        m for m in transcript if m.agent_id == AgentId.RESEARCH_MANAGER.value
    )
    assert "[AMI:" in rm.content
    assert "incomplete" in rm.content.lower()
    # And it says so where the client already looks: CR106 §3.3 marks a
    # collapsed transcript row amber on `content.contains('[AMI')`.
    assert rm.content.strip().endswith("]")


def test_turns_that_ended_cleanly_are_left_untouched():
    """The mark asserts a fact reported by the provider — never inferred from
    the shape of the text. Every other agent in the same run is unmarked."""
    transcript = _transcript_for(AgentId.RESEARCH_MANAGER.value)
    others = [
        m for m in transcript
        if m.agent_id not in (
            AgentId.RESEARCH_MANAGER.value,
            AgentId.PORTFOLIO_MANAGER.value,
        )
    ]
    assert len(others) == 10, "vacuity guard — the rest of the roster spoke"
    for m in others:
        assert "hit its length limit" not in m.content


def test_a_provider_that_reports_no_finish_reason_never_gets_a_mark():
    """Silence is not evidence of truncation. A gateway that reports nothing
    (every fake in the suite, and the mock provider) marks nothing."""
    transcript = _transcript_for("no_such_agent")
    for m in transcript:
        assert "hit its length limit" not in m.content


def test_the_mark_is_not_appended_twice():
    from app.services.room_runner import _TRUNCATION_MARK, _mark_if_truncated

    once = _mark_if_truncated(
        "cut off here",
        agent_id=AgentId.RESEARCH_MANAGER,
        meta={"finish_reason": "length"},
    )
    twice = _mark_if_truncated(
        once, agent_id=AgentId.RESEARCH_MANAGER, meta={"finish_reason": "length"}
    )
    assert twice == once
    assert once.count(_TRUNCATION_MARK) == 1


# ── the providers actually report the stop reason ────────────────────────


class _FakeSSEResponse:
    def __init__(self, status_code: int, lines: list[str], body: bytes = b""):
        self.status_code = status_code
        self._lines = lines
        self._body = body

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line

    async def aread(self) -> bytes:
        return self._body


class _FakeClient:
    def __init__(self, resp: _FakeSSEResponse):
        self._resp = resp

    @asynccontextmanager
    async def stream(self, method: str, url: str, json: dict):
        yield self._resp

    async def aclose(self) -> None:
        pass


def _sse(payload: str) -> str:
    return f"data: {payload}"


@pytest.mark.asyncio
async def test_vllm_reports_a_length_stop_into_meta():
    """vLLM sends `finish_reason` on the FINAL chunk, whose delta is empty —
    the parser has to read it before the `content` guard skips the chunk."""
    lines = [
        _sse('{"choices":[{"index":0,"delta":{"content":"half a sen"}}]}'),
        _sse('{"choices":[{"index":0,"delta":{},"finish_reason":"length"}]}'),
        "data: [DONE]",
    ]
    p = VLLMProvider(base_url="http://lan:8000", model_name="ami-llm")
    p._client = _FakeClient(_FakeSSEResponse(200, lines))  # type: ignore[assignment]

    meta: dict = {}
    chunks = [
        c async for c in p.stream_chat(
            system_prompt="x",
            messages=[ChatMessage(role="user", content="ping")],
            max_tokens=8,
            meta=meta,
        )
    ]
    assert "".join(chunks) == "half a sen"
    assert meta["finish_reason"] == "length"


@pytest.mark.asyncio
async def test_vllm_reports_a_clean_stop_distinctly():
    lines = [
        _sse('{"choices":[{"index":0,"delta":{"content":"done."}}]}'),
        _sse('{"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}'),
        "data: [DONE]",
    ]
    p = VLLMProvider(base_url="http://lan:8000", model_name="ami-llm")
    p._client = _FakeClient(_FakeSSEResponse(200, lines))  # type: ignore[assignment]

    meta: dict = {}
    async for _ in p.stream_chat(
        system_prompt="x",
        messages=[ChatMessage(role="user", content="ping")],
        meta=meta,
    ):
        pass
    assert meta["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_anthropic_max_tokens_is_normalised_to_length():
    """Anthropic calls it `max_tokens` on `message_delta`; callers must not
    have to know which provider served them."""
    lines = [
        _sse('{"type":"content_block_delta","delta":{"type":"text_delta","text":"cut"}}'),
        _sse('{"type":"message_delta","delta":{"stop_reason":"max_tokens"}}'),
        "data: [DONE]",
    ]
    p = AnthropicProvider(api_key="sk-ant-fake")
    p._client = _FakeClient(_FakeSSEResponse(200, lines))  # type: ignore[assignment]

    meta: dict = {}
    chunks = [
        c async for c in p.stream_chat(
            system_prompt="x",
            messages=[ChatMessage(role="user", content="ping")],
            meta=meta,
        )
    ]
    assert "".join(chunks) == "cut"
    assert meta["finish_reason"] == "length"


@pytest.mark.asyncio
async def test_the_gateway_warns_on_a_length_stop_for_every_flow():
    """The room marks its own transcript, but one-on-one, Brief and Concierge
    have no such mark — the gateway warning is their only disclosure, so it
    fires whether or not the caller passed a `meta` dict of its own."""
    import structlog

    from app.services.llm_gateway import LLMGateway, LLMProvider

    class _LengthStopProvider(LLMProvider):
        name = "fake"

        async def stream_chat(
            self, *, system_prompt, messages, model_tier="cheap",
            max_tokens=1024, meta=None,
        ):
            yield "half a sen"
            if meta is not None:
                meta["finish_reason"] = "length"

    g = LLMGateway()
    g._providers = {"mock": _LengthStopProvider()}

    with structlog.testing.capture_logs() as captured:
        async for _ in g.stream_chat(
            system_prompt="x",
            messages=[ChatMessage(role="user", content="ping")],
            max_tokens=8,
            audit_flow="one_on_one",
            audit_agent_id="market_analyst",
        ):
            pass

    warned = [e for e in captured if e.get("event") == "llm_call_length_stop"]
    assert len(warned) == 1, captured
    assert warned[0]["flow"] == "one_on_one"
    assert warned[0]["agent_id"] == "market_analyst"
    assert warned[0]["max_tokens"] == 8


def test_room_prompts_module_exposes_the_budget_helper():
    """The runner imports `max_tokens_for` by name; keep the seam explicit."""
    assert callable(room_prompts.max_tokens_for)
