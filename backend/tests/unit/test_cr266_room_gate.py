"""CR266 — the evidence gate wired into the Room runner.

Covers, against `_run_cio_step` with a scripted gateway:

1. Gate OFF is byte-behaviour: the PM prompt gains no decision block, the
   verdict is the PM's own, and `decision_record` stays null.
2. The PM prompt's decision block carries score, threshold, allowed actions,
   computed size and unresolved objection ids — without changing the JSON
   grammar the verdict is parsed against.
3. Fail closed: an uncalibrated provider or missing typed evidence stops the
   convene BEFORE the PM call, with an explicit reason, and no record is
   fabricated.
4. Post-vote application: a disallowed APPROVE flips to an explicit PASS with
   no APPROVE narration; an allowed APPROVE ships the computed size, not the
   CIO's stated size, and the record says so.
5. The existing vote bar and safety floor stay final over a gate-allowed
   APPROVE; contestedness from split votes, blocked approvals and scripted
   desks lands on the persisted record; the record survives the JSONB
   round-trip.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.config import settings
from app.schemas import AgentId
from app.schemas.room import RoomRun, Verdict
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import (
    _build_pm_formatter,
    _compute_agent_text,
    _RoomContext,
    _run_cio_step,
    parse_claim_cards,
)

# ── fixtures ────────────────────────────────────────────────────────────────

_REGISTRY_FIELDS = (
    "free_cash_flow", "sbc", "net_cash", "roic", "wacc",
    "pe", "forward_pe", "ev_to_ebitda", "peg_ratio", "price_to_sales",
    "total_debt", "interest_coverage", "debt_maturity", "current_ratio",
    "quick_ratio", "debt_to_equity",
    "gross_margin", "operating_margin", "rev_growth", "profit_margin",
)

_THRESHOLDS_JSON = (
    '{"mock": {"R1": 0.6, "R2": 0.55, "R3": 0.5, "R4": 0.45, "R5": 0.4}}'
)


def _field_state(*, live: bool = True) -> dict[str, str]:
    return dict.fromkeys(_REGISTRY_FIELDS, "live" if live else "unavailable")


def _desk_cards(text: str):
    _, cards = parse_claim_cards(text)
    assert cards is not None
    return cards


def _cards_block(
    eq=("neutral", "unsupported"),
    vc=("neutral", "unsupported"),
    vh=("neutral", "unsupported"),
    bs=("neutral", "unsupported"),
    moat=("neutral", "unsupported"),
    objections: str = "",
) -> str:
    lines = ["[CLAIMS]"]
    for item, (direction, grade) in (
        ("eq", eq), ("vc", vc), ("vh", vh), ("bs", bs), ("moat", moat),
    ):
        lines.append(f"item={item} dir={direction} grade={grade} data=yes claim=c nums=1")
    lines.append("[/CLAIMS]")
    if objections:
        lines += ["[OBJECTIONS]", objections, "[/OBJECTIONS]"]
    return "\n".join(lines)


def _strong_room_cards() -> dict:
    """Score 4.0 (4 desks x support/well eq) — comfortably above the 0.5
    threshold."""
    block = _cards_block(eq=("support", "well"))
    return {
        desk: _desk_cards(block)
        for desk in ("fundamentals_analyst", "bull_researcher",
                     "bear_researcher", "research_manager")
    }


def _bare_room_cards() -> dict:
    """Every card neutral/unsupported: net support 0.0, below the threshold."""
    block = _cards_block()
    return {
        desk: _desk_cards(block)
        for desk in ("fundamentals_analyst", "bull_researcher",
                     "bear_researcher", "research_manager")
    }


def _ctx(*, cards_by_desk=None, risk_score=3, drawdown=0.0, scripted=()):
    mandate = hydrate_coach_mandate({
        "plan": "trader", "risk_score": risk_score, "single_name_cap_pct": 3.0,
    })
    profile = {"field_state": _field_state()}
    ctx = _RoomContext(
        ticker="AAPL",
        mandate=mandate,
        portfolio_value=100_000.0,
        current_drawdown_pct=drawdown,
        halal_universe=set(),
        classification_universe=None,
        locale_allowed_universe=None,
        user_id=uuid4(),
        sector_holdings=[],
        sector_marks={},
        risk_last_loss_closed_at=None,
        risk_trade_open_timestamps=[],
        risk_existing_open_risk_pct=0.0,
        profile=profile,
        scripted_turns=list(scripted),
    )
    if cards_by_desk:
        ctx.claim_cards = {AgentId(k): v for k, v in cards_by_desk.items()}
    return ctx, mandate, profile


class _GateGateway:
    """Scripted LLM gateway: one reply per PM call, plus provider identity."""

    def __init__(self, replies: list[str]):
        self._replies = list(replies)
        self.calls: list[dict] = []

    def has_real_provider(self) -> bool:
        return True

    def status(self) -> dict:
        return {"active_provider": "mock"}

    async def stream_chat(
        self, *, system_prompt, messages, model_tier, locale="en",
        max_tokens=1024, meta=None, **audit,
    ):
        self.calls.append({
            "agent": audit.get("audit_agent_id"),
            "flow": audit.get("audit_flow"),
            "system_prompt": system_prompt,
        })
        if self._replies:
            yield self._replies.pop(0)


_PM_APPROVE = json.dumps({
    "action": "APPROVE", "size_pct": 2.0, "entry": 150.0, "stop": 141.0,
    "target": 172.0, "horizon_days": 90, "narration": "PM: take it.",
})
_PM_PASS = json.dumps({"action": "PASS", "narration": "PM: wait."})


def _drain_cio(gateway, ctx, mandate, profile):
    run_id = uuid4()
    run = RoomRun(
        id=run_id, user_id=uuid4(), ticker=ctx.ticker,
        triggered_at=datetime.now(UTC),
        mandate_version=1, model_tier="mid", credit_cost=1,
    )
    captured: dict = {"pm_text": "", "verdict": None}

    async def _drain():
        async for ev in _run_cio_step(
            run_id=run_id, ctx=ctx, profile=profile,
            formatter=_build_pm_formatter(ctx, profile, mandate),
            run=run, mandate=mandate, gateway=gateway, live=True,
            char_delay_min=0.0, char_delay_max=0.0, agent_timeout_s=30.0,
        ):
            if ev.kind == "agent_token" and ev.agent_id == AgentId.PORTFOLIO_MANAGER:
                captured["pm_text"] += ev.text or ""
            if ev.kind == "verdict":
                captured["verdict"] = ev.verdict

    asyncio.run(_drain())
    return captured


@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setattr(settings, "room_evidence_gate_enabled", True)
    monkeypatch.setattr(
        settings, "room_evidence_gate_thresholds_json", _THRESHOLDS_JSON
    )
    monkeypatch.setattr(settings, "pm_self_consistency_samples", 1)
    # The CR247 reviews are a different WP's surface — keep them out of these
    # tests so a gated APPROVE is not double-checked by a scripted gateway.
    monkeypatch.setattr(settings, "room_veto_review_enabled", False)
    monkeypatch.setattr(settings, "room_resurrection_review_enabled", False)
    yield
    monkeypatch.undo()


@pytest.fixture
def cards_envelope_on(monkeypatch):
    monkeypatch.setattr(settings, "room_cards_envelope_enabled", True)
    yield
    monkeypatch.undo()


def _pm_calls(gateway) -> list[dict]:
    return [c for c in gateway.calls if c["agent"] == AgentId.PORTFOLIO_MANAGER.value]


# ── gate off: nothing changes ───────────────────────────────────────────────


def test_gate_off_keeps_the_verdict_the_pms_own_and_the_record_null():
    ctx, mandate, profile = _ctx(cards_by_desk=_strong_room_cards())
    gateway = _GateGateway([_PM_APPROVE])
    captured = _drain_cio(gateway, ctx, mandate, profile)

    verdict = captured["verdict"]
    assert verdict.action == "APPROVE"
    assert verdict.size_pct == 2.0  # the CIO's stated size, untouched
    assert verdict.decision_record is None
    assert ctx.evidence_gate is None
    assert "EVIDENCE GATE" not in _pm_calls(gateway)[0]["system_prompt"]


# ── the PM decision block ───────────────────────────────────────────────────


def test_the_pm_prompt_carries_the_decision_block_and_keeps_the_json_grammar(gate_on):
    # Only the bear files the objection (objections are bear/RM-only by the
    # CR256 contract): one unresolved challenge, score 4.0 - 0.1 = 3.90.
    desks = _strong_room_cards()
    desks["bear_researcher"] = _desk_cards(_cards_block(
        eq=("support", "well"),
        objections="target=eq severity=high objection=the accruals disagree",
    ))
    ctx, mandate, profile = _ctx(cards_by_desk=desks)
    gateway = _GateGateway([_PM_APPROVE])
    _drain_cio(gateway, ctx, mandate, profile)

    prompt = _pm_calls(gateway)[0]["system_prompt"]
    assert "EVIDENCE GATE" in prompt
    assert "Typed evidence score:" in prompt and "3.90" in prompt
    assert "0.50" in prompt  # the R3 threshold this mandate resolves to
    assert "APPROVE and PASS." in prompt
    assert "Computed position size: 3.00%" in prompt
    assert "bear_researcher:eq:0" in prompt  # the unresolved objection id
    # The JSON grammar the verdict is parsed against is untouched.
    assert '"action": "APPROVE" | "PASS"' in prompt
    assert "Your ENTIRE reply must be one single JSON object" in prompt


def test_the_block_is_absent_below_the_threshold_and_names_pass_only(gate_on):
    ctx, mandate, profile = _ctx(cards_by_desk=_bare_room_cards())
    gateway = _GateGateway([_PM_PASS])
    _drain_cio(gateway, ctx, mandate, profile)

    prompt = _pm_calls(gateway)[0]["system_prompt"]
    assert "EVIDENCE GATE" in prompt
    assert "Allowed actions this run: PASS only." in prompt
    assert "Computed position size:" not in prompt  # no size below the bar


# ── fail closed ─────────────────────────────────────────────────────────────


def test_uncalibrated_provider_fails_closed_before_the_pm_call():
    ctx, mandate, profile = _ctx(cards_by_desk=_strong_room_cards())
    gateway = _GateGateway([_PM_APPROVE])  # never consumed
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "room_evidence_gate_enabled", True)
        mp.setattr(settings, "room_evidence_gate_thresholds_json", "{}")
        mp.setattr(settings, "pm_self_consistency_samples", 1)
        mp.setattr(settings, "room_veto_review_enabled", False)
        mp.setattr(settings, "room_resurrection_review_enabled", False)
        captured = _drain_cio(gateway, ctx, mandate, profile)

    assert _pm_calls(gateway) == []  # the CIO was never asked
    verdict = captured["verdict"]
    assert verdict.action == "PASS"
    assert verdict.overridden_from_llm is True
    assert "no calibrated evidence thresholds" in verdict.reason
    assert "'mock'" in verdict.reason
    assert verdict.decision_record is None  # never fabricated


def test_missing_cards_fail_closed_before_the_pm_call(gate_on):
    ctx, mandate, profile = _ctx(cards_by_desk=None)  # no desk filed cards
    gateway = _GateGateway([_PM_APPROVE])
    captured = _drain_cio(gateway, ctx, mandate, profile)

    assert _pm_calls(gateway) == []
    verdict = captured["verdict"]
    assert verdict.action == "PASS"
    assert verdict.overridden_from_llm is True
    assert "missing" in verdict.reason
    assert "cards:fundamentals_analyst" in verdict.reason
    assert verdict.decision_record is None


# ── post-vote application ───────────────────────────────────────────────────


def test_disallowed_approve_flips_to_pass_with_no_approve_narration(gate_on):
    ctx, mandate, profile = _ctx(cards_by_desk=_bare_room_cards())
    gateway = _GateGateway([_PM_APPROVE])
    captured = _drain_cio(gateway, ctx, mandate, profile)

    verdict = captured["verdict"]
    assert verdict.action == "PASS"
    assert verdict.overridden_from_llm is True
    assert verdict.size_pct is None
    assert "0.00" in verdict.reason and "0.50" in verdict.reason
    assert "PM: take it." not in verdict.reason  # no APPROVE narration
    assert "PM: take it." not in captured["pm_text"]

    record = verdict.decision_record
    assert record is not None
    assert record.score == 0.0
    assert record.threshold == 0.5
    assert record.allowed_actions == ["PASS"]
    assert record.computed_size_pct is None
    assert record.evidence_available is True
    assert record.evidence_source == "claim_cards"
    # The PM wanted in; the gate blocked it — that is contested by definition.
    assert record.contested is True
    assert any("blocked" in r for r in record.reasons)


def test_computed_size_overrides_the_llm_size_and_the_record_says_so(gate_on):
    ctx, mandate, profile = _ctx(cards_by_desk=_strong_room_cards())
    gateway = _GateGateway([_PM_APPROVE])  # asks 2.0; gate computes 3.0 (cap)
    captured = _drain_cio(gateway, ctx, mandate, profile)

    verdict = captured["verdict"]
    assert verdict.action == "APPROVE"
    assert verdict.size_pct == 3.0  # the computed evidence size, not 2.0
    assert verdict.overridden_from_llm is True
    assert "evidence gate at 3.00%" in verdict.reason
    assert "CIO's stated 2.00%" in verdict.reason

    record = verdict.decision_record
    assert record.allowed_actions == ["APPROVE", "PASS"]
    assert record.computed_size_pct == 3.0
    assert record.contested is False
    assert any("computed size" in r for r in record.reasons)


def test_at_threshold_score_ships_25pct_of_cap(gate_on):
    desks = {
        "fundamentals_analyst": _desk_cards(
            _cards_block(eq=("support", "partial"))
        ),
        "bull_researcher": _desk_cards(_cards_block()),
        "bear_researcher": _desk_cards(_cards_block()),
        "research_manager": _desk_cards(_cards_block()),
    }
    ctx, mandate, profile = _ctx(cards_by_desk=desks)
    gateway = _GateGateway([_PM_APPROVE])
    captured = _drain_cio(gateway, ctx, mandate, profile)

    verdict = captured["verdict"]
    assert verdict.action == "APPROVE"
    assert verdict.size_pct == pytest.approx(0.75)  # 25% of the 3.0% cap
    assert verdict.decision_record.score == 0.5
    assert verdict.decision_record.contested is True  # on the bar


# ── the floor and the vote bar stay final ───────────────────────────────────


def test_the_safety_floor_stays_final_over_a_gate_allowed_approve(gate_on):
    # Evidence strongly approves, but the account is past its drawdown cap:
    # the floor's REJECT wins, and the record shows the blocked approval.
    ctx, mandate, profile = _ctx(
        cards_by_desk=_strong_room_cards(), drawdown=35.0,
    )
    gateway = _GateGateway([_PM_APPROVE])
    captured = _drain_cio(gateway, ctx, mandate, profile)

    verdict = captured["verdict"]
    assert verdict.action == "REJECT"
    assert verdict.violations
    assert "safety floor" in verdict.reason
    record = verdict.decision_record
    assert record is not None
    assert "APPROVE" in record.allowed_actions
    assert record.contested is True
    assert any("blocked" in r for r in record.reasons)


def test_a_split_vote_marks_the_record_contested():
    ctx, mandate, profile = _ctx(cards_by_desk=_strong_room_cards())
    gateway = _GateGateway([_PM_APPROVE, _PM_PASS, _PM_PASS])
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "room_evidence_gate_enabled", True)
        mp.setattr(
            settings, "room_evidence_gate_thresholds_json", _THRESHOLDS_JSON
        )
        mp.setattr(settings, "pm_self_consistency_samples", 3)
        mp.setattr(settings, "room_veto_review_enabled", False)
        mp.setattr(settings, "room_resurrection_review_enabled", False)
        captured = _drain_cio(gateway, ctx, mandate, profile)

    verdict = captured["verdict"]
    assert verdict.action == "PASS"  # 1 of 3 approves misses the bar
    assert verdict.samples == 3
    assert "split" in verdict.reason
    record = verdict.decision_record
    assert record.contested is True
    assert any("split" in r for r in record.reasons)
    assert len(_pm_calls(gateway)) == 3


def test_scripted_desks_mark_the_record_contested(gate_on):
    ctx, mandate, profile = _ctx(
        cards_by_desk=_strong_room_cards(), scripted=[AgentId.NEWS_ANALYST],
    )
    gateway = _GateGateway([_PM_APPROVE])
    captured = _drain_cio(gateway, ctx, mandate, profile)

    verdict = captured["verdict"]
    assert verdict.action == "APPROVE"  # 1 scripted desk is below the NO_VERDICT cap
    assert verdict.scripted_turns == 1
    record = verdict.decision_record
    assert record.contested is True
    assert any("scripted" in r for r in record.reasons)


# ── persistence + capture ───────────────────────────────────────────────────


def test_the_record_survives_the_json_round_trip(gate_on):
    ctx, mandate, profile = _ctx(cards_by_desk=_strong_room_cards())
    gateway = _GateGateway([_PM_APPROVE])
    captured = _drain_cio(gateway, ctx, mandate, profile)

    verdict = captured["verdict"]
    assert verdict.decision_record is not None
    payload = json.loads(json.dumps(verdict.model_dump(mode="json")))
    restored = Verdict.model_validate(payload)
    assert restored.decision_record == verdict.decision_record
    assert restored.decision_record.score == pytest.approx(verdict.decision_record.score)


def test_a_live_card_desk_turn_is_captured_on_ctx(cards_envelope_on):
    ctx, _, profile = _ctx()
    turn = (
        "[STANCE: for | CONVICTION: high | HEADLINE: eq holds]\n"
        "[CLAIMS]\n"
        + "\n".join(
            f"item={i} dir=support grade=well data=yes claim=c nums=1"
            for i in ("eq", "vc", "vh", "bs", "moat")
        )
        + "\n[/CLAIMS]\nThe desk's own analysis."
    )
    gateway = _GateGateway([turn])
    text, *_ = asyncio.run(_compute_agent_text(
        agent_id=AgentId.FUNDAMENTALS_ANALYST, ctx=ctx, profile=profile,
        formatter={}, transcript=[], gateway=gateway, live=True,
        agent_timeout_s=30.0,
    ))
    assert AgentId.FUNDAMENTALS_ANALYST in ctx.claim_cards
    assert len(ctx.claim_cards[AgentId.FUNDAMENTALS_ANALYST].cards) == 5
    assert "[CLAIMS]" not in text  # the machine channel stays off the transcript


def test_the_scripted_path_never_carries_a_record(gate_on):
    ctx, mandate, profile = _ctx(cards_by_desk=_strong_room_cards())
    run_id = uuid4()
    run = RoomRun(
        id=run_id, user_id=uuid4(), ticker=ctx.ticker,
        triggered_at=datetime.now(UTC),
        mandate_version=1, model_tier="mid", credit_cost=1,
    )

    async def _drain():
        async for ev in _run_cio_step(
            run_id=run_id, ctx=ctx, profile=profile,
            formatter=_build_pm_formatter(ctx, profile, mandate),
            run=run, mandate=mandate, gateway=_GateGateway([]), live=False,
            char_delay_min=0.0, char_delay_max=0.0, agent_timeout_s=30.0,
        ):
            if ev.kind == "verdict":
                return ev.verdict
        return None

    verdict = asyncio.run(_drain())
    assert verdict.decision_record is None
    assert ctx.evidence_gate is None
