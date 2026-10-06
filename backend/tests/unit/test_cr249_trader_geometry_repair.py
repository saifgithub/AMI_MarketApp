"""CR249 — Trader geometry repair gate.

Measured in the CR247 tm-all gate (2026-10-06): a Trader proposal with an
implausible level (GLM: stop $50 vs close $332.89) used to continue to the
transcript flag-only, so the debators and the PM reasoned from a level AMI
had already refused. CR249 gives the Trader's live turn ONE regeneration
with the violation named; a failed repair leaves exactly the pre-CR249
flag-only annotation in place (DEF059 — never a veto).

Coverage: the level-reparse helper, the repair helper's every outcome
branch against a fake gateway, and an end-to-end RoomRunner run proving
the repair fires exactly once and never touches the verdict.
"""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest

from app.schemas import AgentId
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import (
    LiveDataState,
    RoomRunner,
    _attempt_trader_geometry_repair,
    _implausible_trade_levels,
)

CLOSE = 332.89


def _msg_content(m) -> str:
    """ChatMessage dataclass or plain dict — both appear in tests."""
    if isinstance(m, dict):
        return str(m.get("content", ""))
    return str(getattr(m, "content", ""))


class TestImplausibleTradeLevels:
    def test_implausible_stop_is_flagged(self):
        text = "Entry $332.00, stop $50.00, target $360.00."
        assert _implausible_trade_levels(text, CLOSE) == {"stop": 50.0}

    def test_clean_triple_flags_nothing(self):
        text = "Entry $330.00, stop $310.00, target $370.00."
        assert _implausible_trade_levels(text, CLOSE) == {}

    def test_no_close_means_no_gate(self):
        """DEF237: without the run's own close there is no plausibility
        reference, so no repair can be attempted — degrade, don't guess."""
        text = "Entry $332.00, stop $50.00, target $360.00."
        assert _implausible_trade_levels(text, None) == {}

    def test_partial_triple_flags_only_the_bad_level(self):
        text = "Entry $330.00, stop $289.16, target $2000.00."
        assert _implausible_trade_levels(text, CLOSE) == {"target": 2000.0}

    @pytest.mark.parametrize("level,kind,expected", [
        (50.0, "stop", {"stop": 50.0}),
        (310.0, "stop", {}),
        (1664.45, "target", {}),   # exactly 5.0x the close — boundary is exclusive
        (1665.0, "target", {"target": 1665.0}),
    ])
    def test_plausibility_boundary(self, level, kind, expected):
        if kind == "stop":
            text = f"Entry $330.00, stop ${level:.2f}, target $370.00."
        else:
            text = f"Entry $330.00, stop $310.00, target ${level:.2f}."
        assert _implausible_trade_levels(text, CLOSE) == expected


class _RepairGateway:
    """Serves one scripted reply per call, recording every call's messages."""

    def __init__(self, replies: list[str]):
        self._replies = list(replies)
        self.calls: list[dict] = []

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, meta=None, **_audit):
        self.calls.append({"system_prompt": system_prompt, "messages": messages})
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


# Stated R:R deliberately disagrees with the implied 2.0:1 so the AMI
# verification note is guaranteed to render (a coherent narration gets the
# inline rewrite only, by design — `_annotate_rr_against_levels`).
_GOOD_PROPOSAL = (
    "[STANCE: for | CONVICTION: medium | HEADLINE: re-placed stop]\n"
    "Take it: entry $330.00, stop $310.00 (structural floor), "
    "target $370.00. R:R 5:1."
)

_BAD_PROPOSAL = (
    "[STANCE: for | CONVICTION: medium | HEADLINE: wide structural stop]\n"
    "Take it: entry $332.00, stop $50.00, target $360.00. R:R 0.1:1."
)


def _run_repair(gateway: _RepairGateway):
    return _attempt_trader_geometry_repair(
        gateway=gateway,  # type: ignore[arg-type]
        system_prompt="sys",
        messages=[{"role": "user", "content": "original turn"}],  # type: ignore[list-item]
        tier="cheap",
        locale="en",
        user_id=uuid4(),
        ticker="AAPL",
        max_tokens=1024,
        timeout_s=30.0,
        implausible={"stop": 50.0},
        reference_close=CLOSE,
        size_pct=3.0,
    )


class TestRepairHelper:
    def test_success_returns_verified_text(self):
        gw = _RepairGateway([_GOOD_PROPOSAL])
        out = asyncio.run(_run_repair(gw))
        assert out is not None
        text, sig, env = out
        assert "stop $310.00" in text
        assert "AMI verified the trade geometry" in text
        assert sig is not None and sig["implied_rr"] == pytest.approx(2.0)
        assert env.stance == "for"

    def test_repair_note_names_the_violation(self):
        gw = _RepairGateway([_GOOD_PROPOSAL])
        asyncio.run(_run_repair(gw))
        note = _msg_content(gw.calls[0]["messages"][-1])
        assert "[AMI fact-check]" in note
        assert "stop $50.00" in note
        assert f"${CLOSE:.2f}" in note

    def test_still_implausible_returns_none(self):
        gw = _RepairGateway([_BAD_PROPOSAL])
        assert asyncio.run(_run_repair(gw)) is None

    def test_call_error_returns_none(self):
        class _Exploding(_RepairGateway):
            async def stream_chat(self, **kwargs):
                self.calls.append({"messages": kwargs.get("messages")})
                raise RuntimeError("provider down")
                yield  # pragma: no cover - keeps this an async generator

        assert asyncio.run(_run_repair(_Exploding([]))) is None

    def test_stream_error_returns_none(self):
        gw = _RepairGateway(["__STREAM_ERROR__"])
        assert asyncio.run(_run_repair(gw)) is None

    def test_empty_reply_returns_none(self):
        gw = _RepairGateway(["   "])
        assert asyncio.run(_run_repair(gw)) is None


# ── end-to-end through RoomRunner ────────────────────────────────────────────

_PM_APPROVE = json.dumps({
    "action": "APPROVE",
    "size_pct": 2.0, "entry": 330.0, "stop": 310.0, "target": 370.0,
    "horizon_days": 90, "narration": "PM: take it.",
})


def _run_room(gateway) -> dict:
    captured: dict = {}

    async def _drain():
        async for ev in RoomRunner(llm=gateway).run(  # type: ignore[arg-type]
            user_id=uuid4(), ticker="AAPL",
            mandate=hydrate_coach_mandate({
                "plan": "trader", "risk_score": 3, "single_name_cap_pct": 3.0,
            }),
            char_delay_min=0.0, char_delay_max=0.0,
        ):
            if ev.kind == "verdict":
                captured["v"] = ev.verdict

    asyncio.run(_drain())
    return captured


def test_repair_gate_end_to_end(monkeypatch):
    """The implausible stop triggers exactly one repair call whose messages
    carry the fact-check note; DEF059 holds — the verdict is the PM's own."""
    monkeypatch.setattr(
        "app.services.room_runner._reference_close", lambda profile: CLOSE,
    )
    state = {"repaired": False}

    class _Gw:
        def __init__(self):
            self.calls: list[dict] = []

        def has_real_provider(self) -> bool:
            return True

        async def stream_chat(self, *, system_prompt, messages, model_tier,
                              locale="en", max_tokens=1024, **_audit):
            self.calls.append({"agent": _audit.get("audit_agent_id"),
                               "messages": messages})
            agent = _audit.get("audit_agent_id")
            if agent == "trader":
                if any("[AMI fact-check]" in _msg_content(m) for m in messages):
                    state["repaired"] = True
                    yield _GOOD_PROPOSAL
                else:
                    yield _BAD_PROPOSAL
            elif agent == "portfolio_manager":
                yield _PM_APPROVE
            else:
                yield "[STANCE: for | CONVICTION: high | HEADLINE: x]\nA reply."

    gw = _Gw()
    captured = _run_room(gw)

    trader_calls = [c for c in gw.calls if c["agent"] == "trader"]
    assert len(trader_calls) == 2, "exactly one repair attempt expected"
    assert state["repaired"], "the second trader call must carry the repair note"
    assert captured["v"] is not None


def test_no_repair_when_levels_are_sane(monkeypatch):
    monkeypatch.setattr(
        "app.services.room_runner._reference_close", lambda profile: CLOSE,
    )

    class _Gw:
        def __init__(self):
            self.trader_calls = 0

        def has_real_provider(self) -> bool:
            return True

        async def stream_chat(self, *, system_prompt, messages, model_tier,
                              locale="en", max_tokens=1024, **_audit):
            if _audit.get("audit_agent_id") == "trader":
                self.trader_calls += 1
                yield _GOOD_PROPOSAL
            elif _audit.get("audit_agent_id") == "portfolio_manager":
                yield _PM_APPROVE
            else:
                yield "[STANCE: for | CONVICTION: high | HEADLINE: x]\nA reply."

    gw = _Gw()
    captured = _run_room(gw)
    assert gw.trader_calls == 1, "a sane proposal must not be re-asked"
    assert captured["v"] is not None
