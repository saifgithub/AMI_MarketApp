"""CR253 — the envelope-presence re-ask guard.

A live prose turn that produced NO parseable stance envelope used to keep
its prose with an empty envelope: the machine channel the prompt names went
unanswered, and the comb's gutter rendered a null stance that WAS asked for.
CR253 gives such a turn ONE regeneration naming the omission — same gateway,
tier, timeout and constraint as the original call (the CR249 trader-repair /
room_pm_reformat precedent), audited under its own `room_envelope_repair`
flow so the scoring gate's once-per-agent base-flow count is untouched.

The rules pinned here:

**Exactly one bounded retry, failure changes nothing.** A call error, a
stream error, an empty reply, or a retry that STILL has no envelope all
leave the original prose and the empty envelope in place — the scripted
fallback machinery is not involved on the success path and untouched on
every failure path.

**Provider failures are not retried.** A turn that already fell back to the
scripted template (empty stream, stream error) never gets the re-ask —
re-asking a provider that just failed is a retry of a failed call, not a
content repair.

**The PM path is out of scope.** The PM speaks JSON, not the envelope; its
path never reaches the parse site and never earns a repair call.
"""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest

from app.schemas import AgentId
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import (
    RoomRunner,
    _attempt_envelope_repair,
)

_NO_ENVELOPE = "The multiple is defensible on the cash flows alone."
_WITH_ENVELOPE = (
    "[STANCE: for | CONVICTION: medium | HEADLINE: cash flows carry it]\n"
    "The multiple is defensible on the cash flows alone."
)

_PM_JSON = json.dumps({
    "action": "APPROVE",
    "size_pct": 2.0, "entry": 150.0, "stop": 141.0, "target": 172.0,
    "horizon_days": 90, "narration": "PM: take it.",
})


def _msg_content(m) -> str:
    if isinstance(m, dict):
        return str(m.get("content", ""))
    return str(getattr(m, "content", ""))


class _RepairGateway:
    """Serves one scripted reply per call, recording every call's audit kwargs
    and messages."""

    def __init__(self, replies: list[str]):
        self._replies = list(replies)
        self.calls: list[dict] = []

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, meta=None, **audit):
        self.calls.append({"messages": messages, "audit": audit})
        if meta is not None and self._replies and self._replies[0] == "__STREAM_ERROR__":
            self._replies.pop(0)
            meta["stream_error"] = True
            return
        if self._replies:
            yield self._replies.pop(0)
        else:
            yield "unexpected extra call"

    @property
    def call_count(self) -> int:
        return len(self.calls)


def _run_repair(gateway: _RepairGateway):
    return _attempt_envelope_repair(
        gateway=gateway,  # type: ignore[arg-type]
        system_prompt="sys",
        messages=[{"role": "user", "content": "original turn"}],  # type: ignore[list-item]
        tier="cheap",
        locale="en",
        user_id=uuid4(),
        agent_id=AgentId.FUNDAMENTALS_ANALYST,
        ticker="AAPL",
        max_tokens=1024,
        timeout_s=30.0,
        profile={},
    )


class TestTheRepairHelper:
    def test_a_parsed_retry_is_kept(self):
        gw = _RepairGateway([_WITH_ENVELOPE])
        out = asyncio.run(_run_repair(gw))
        assert out is not None
        text, env = out
        assert "cash flows alone" in text
        assert "[STANCE:" not in text, "the envelope comes off before the transcript"
        assert env.stance == "for" and env.conviction == "medium"
        assert env.headline == "cash flows carry it"

    def test_the_note_names_the_envelope_requirement(self):
        gw = _RepairGateway([_WITH_ENVELOPE])
        asyncio.run(_run_repair(gw))
        note = _msg_content(gw.calls[0]["messages"][-1])
        assert "[AMI fact-check]" in note
        assert "did not open with the required stance envelope" in note
        assert "[STANCE: for|against|neutral | CONVICTION: low|medium|high | HEADLINE:" in note

    def test_the_retry_is_audited_under_its_own_flow(self):
        gw = _RepairGateway([_WITH_ENVELOPE])
        asyncio.run(_run_repair(gw))
        assert gw.calls[0]["audit"].get("audit_flow") == "room_envelope_repair"
        assert gw.calls[0]["audit"].get("audit_agent_id") == AgentId.FUNDAMENTALS_ANALYST.value

    def test_a_retry_still_without_an_envelope_is_none(self):
        gw = _RepairGateway([_NO_ENVELOPE])
        assert asyncio.run(_run_repair(gw)) is None

    def test_a_call_error_is_none(self):
        class _Exploding(_RepairGateway):
            async def stream_chat(self, **kwargs):
                self.calls.append({"messages": kwargs.get("messages"), "audit": kwargs})
                raise RuntimeError("provider down")
                yield  # pragma: no cover - keeps this an async generator

        assert asyncio.run(_run_repair(_Exploding([]))) is None

    def test_a_stream_error_is_none(self):
        gw = _RepairGateway(["__STREAM_ERROR__"])
        assert asyncio.run(_run_repair(gw)) is None

    def test_an_empty_retry_is_none(self):
        gw = _RepairGateway(["   "])
        assert asyncio.run(_run_repair(gw)) is None

    def test_an_envelope_only_retry_keeps_the_stance_for_the_main_flow(self):
        """A retry that stops right after the envelope leaves no prose; the
        helper keeps the parsed stance and lets `_compute_agent_text`'s own
        envelope_only_no_prose fallback supply the prose (DEF147's rule)."""
        gw = _RepairGateway(["[STANCE: against | CONVICTION: low | HEADLINE: x]"])
        out = asyncio.run(_run_repair(gw))
        assert out is not None
        text, env = out
        assert text == ""
        assert env.stance == "against"


# ── End-to-end through RoomRunner ────────────────────────────────────────────


def _run_room(gateway) -> dict:
    captured: dict = {"texts": {}}

    async def _drain():
        async for ev in RoomRunner(llm=gateway).run(  # type: ignore[arg-type]
            user_id=uuid4(), ticker="AAPL",
            mandate=hydrate_coach_mandate({
                "plan": "trader", "risk_score": 3, "single_name_cap_pct": 3.0,
            }),
            char_delay_min=0.0, char_delay_max=0.0,
        ):
            if ev.kind == "agent_token":
                captured["texts"][ev.agent_id.value] = (
                    captured["texts"].get(ev.agent_id.value, "") + (ev.text or "")
                )
            if ev.kind == "verdict":
                captured["v"] = ev.verdict

    asyncio.run(_drain())
    return captured


class _RoomGateway:
    """Every prose agent answers WITH an envelope except `bare_agent`, whose
    first turn has none; its repair turn (the [AMI fact-check] note) yields
    the envelope answer. The PM answers JSON."""

    def __init__(self, bare_agent: str, repaired: str | None = None):
        self._bare = bare_agent
        self._repaired = repaired or (
            "[STANCE: for | CONVICTION: high | HEADLINE: repaired view]\n"
            "The repaired analysis with the envelope leading."
        )
        self.calls: list[dict] = []

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, meta=None, **audit):
        agent = audit.get("audit_agent_id")
        self.calls.append({"agent": agent, "flow": audit.get("audit_flow"),
                           "messages": messages})
        if agent == AgentId.PORTFOLIO_MANAGER.value:
            yield _PM_JSON
            return
        if agent == self._bare and not any(
            "[AMI fact-check]" in _msg_content(m) for m in messages
        ):
            yield _NO_ENVELOPE
            return
        if agent == self._bare:
            yield self._repaired
            return
        yield (
            f"[STANCE: for | CONVICTION: high | HEADLINE: {agent} view]\n"
            "A considered view with the envelope leading."
        )


def _calls_for(gw: _RoomGateway, agent: str) -> list[dict]:
    return [c for c in gw.calls if c["agent"] == agent]


def test_the_bare_turn_gets_exactly_one_repair_and_keeps_the_retry():
    gw = _RoomGateway(bare_agent=AgentId.NEWS_ANALYST.value)
    captured = _run_room(gw)

    news_calls = _calls_for(gw, AgentId.NEWS_ANALYST.value)
    assert len(news_calls) == 2, "exactly one repair attempt"
    assert news_calls[0]["flow"] == "room"
    assert news_calls[1]["flow"] == "room_envelope_repair"
    note = _msg_content(news_calls[1]["messages"][-1])
    assert "did not open with the required stance envelope" in note

    done = captured["texts"]
    # The retry's prose is what the Room hears — not the bare original's —
    # and the retried envelope went to the comb, not the transcript.
    assert "The repaired analysis with the envelope leading." in done[AgentId.NEWS_ANALYST.value]
    assert "[STANCE:" not in done[AgentId.NEWS_ANALYST.value]
    assert captured["v"] is not None


def test_a_failed_repair_leaves_the_original_prose_and_verdict():
    """Retry also envelope-less → the original text is what the Room hears;
    DEF059 holds — the verdict is the PM's own either way."""
    gw = _RoomGateway(bare_agent=AgentId.NEWS_ANALYST.value, repaired=_NO_ENVELOPE)
    captured = _run_room(gw)

    news_calls = _calls_for(gw, AgentId.NEWS_ANALYST.value)
    assert len(news_calls) == 2, "one repair attempt, not a loop"
    done = captured["texts"]
    assert done[AgentId.NEWS_ANALYST.value] == _NO_ENVELOPE
    assert captured["v"] is not None


def test_envelope_bearing_turns_are_never_re_asked():
    gw = _RoomGateway(bare_agent="nobody")  # every prose turn carries an envelope
    _run_room(gw)
    repairs = [c for c in gw.calls if c["flow"] == "room_envelope_repair"]
    assert repairs == []
    # Eleven prose agents, each exactly one base "room" call; the PM speaks
    # under its own "room_pm" flow and is counted separately.
    prose_calls = [c for c in gw.calls if c["flow"] == "room"]
    assert len(prose_calls) == 11


def test_the_pm_never_earns_an_envelope_repair():
    gw = _RoomGateway(bare_agent=AgentId.NEWS_ANALYST.value)
    _run_room(gw)
    pm_calls = _calls_for(gw, AgentId.PORTFOLIO_MANAGER.value)
    assert pm_calls, "the PM must have spoken"
    assert all(c["flow"] == "room_pm" for c in pm_calls)
    assert not any(c["flow"] == "room_envelope_repair" for c in pm_calls)
