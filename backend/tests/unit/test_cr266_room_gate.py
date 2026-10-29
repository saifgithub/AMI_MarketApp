"""CR266 — the evidence gate wired into the Room runner.

Covers, against `_run_cio_step` with a scripted gateway:

1. Gate OFF is byte-behaviour: the PM prompt gains no decision block, the
   verdict is the PM's own, and `decision_record` stays null.
2. The PM prompt's decision block carries score, threshold, allowed actions,
   computed size and unresolved objection ids/texts — without changing the
   JSON grammar the verdict is parsed against.
3. Fail closed: an uncalibrated model identity or incomplete typed evidence
   stops the convene BEFORE the PM call, with an explicit reason, and no
   record is fabricated.
4. Post-vote application: a disallowed APPROVE flips to an explicit PASS with
   no APPROVE narration; an allowed APPROVE ships the computed size, not the
   CIO's stated size, and the record says so.
5. Threshold ladders are keyed provider+MODEL (`vllm:ami-llm`), never the
   shared provider; two models on one provider select different ladders.
6. The DecisionRecord emits the mobile wire contract's exact keys:
   `unresolved_objections` (texts) + `unresolved_objection_ids` +
   `contested_reasons`.
7. Review-bypass closures: a gate-blocked APPROVE->PASS never enters
   resurrection; an allowed resurrection re-run meets the same evidence action
   and computed-size rules before the floor; a review that changes the
   decision leaves a FINAL record describing the final verdict, marked
   contested with the change named.
8. The safety floor stays final over a gate-allowed APPROVE; the record
   survives the JSONB round-trip; gate OFF and CR247 behaviour (organic PASS
   resurrection routing) are unchanged.
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

# The default gateway double reports NO tier_to_model, so its identity stays
# the bare "mock" test identity — keyed as "mock" here, never "vllm".
_THRESHOLDS_JSON = (
    '{"mock": {"R1": 0.30, "R2": 0.25, "R3": 0.20, "R4": 0.15, "R5": 0.10}}'
)


def _field_state(*, live: bool = True) -> dict[str, str]:
    return dict.fromkeys(_REGISTRY_FIELDS, "live" if live else "unavailable")


def _desk_cards(text: str):
    _, cards = parse_claim_cards(text)
    assert cards is not None
    return cards


def _all_strong_block() -> str:
    return (
        "[CLAIMS]\n"
        + "\n".join(
            f"item={i} dir=support grade=well data=yes claim=c nums=1"
            for i in ("eq", "vc", "vh", "bs", "moat")
        )
        + "\n[/CLAIMS]"
    )


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
    """Every desk supports/well on eq only: 4 x 1.0 / 20 = 0.2 — exactly the
    R3 threshold, so APPROVE is allowed and size is 25% of the 3.0% cap."""
    block = _cards_block(eq=("support", "well"))
    return {
        desk: _desk_cards(block)
        for desk in ("fundamentals_analyst", "bull_researcher",
                     "bear_researcher", "research_manager")
    }


def _very_strong_room_cards() -> dict:
    """Every desk supports/well on eq AND vc: 8 x 1.0 / 20 = 0.4 — clear of
    the 0.20 threshold and its 0.10 contested margin, so a clean gated
    APPROVE is genuinely uncontested."""
    block = _cards_block(eq=("support", "well"), vc=("support", "well"))
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
    """Scripted LLM gateway: one reply per stream_chat call, plus provider
    identity. `status()` carries no tier_to_model, so the model identity is
    the bare `mock` test identity — exactly the shape the contract preserves
    for existing test doubles."""

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


class _ModelGateway(_GateGateway):
    """A double whose status names ONE model — the identity must become
    `mock:<model>`."""

    def __init__(self, replies: list[str], model: str = "ami-llm"):
        super().__init__(replies)
        self._model = model

    def status(self) -> dict:
        return {
            "active_provider": "mock",
            "tier_to_model": {"cheap": self._model, "mid": self._model,
                              "premium": self._model},
        }


class _MultiModelGateway(_GateGateway):
    """A double advertising several DISTINCT models: the PM's model cannot be
    identified from the snapshot, so the gate must fail closed rather than
    silently collapse to the bare provider."""

    def status(self) -> dict:
        return {
            "active_provider": "vllm",
            "tier_to_model": {"cheap": "claude-haiku-4-5",
                              "mid": "claude-sonnet-4-6",
                              "premium": "claude-opus-4-7"},
        }


class _ReviewGateway(_GateGateway):
    """Adds the fallback-provider picker the verdict review requires."""

    def pick_review_provider(self) -> str:
        return "anthropic"


_PM_APPROVE = json.dumps({
    "action": "APPROVE", "size_pct": 2.0, "entry": 150.0, "stop": 141.0,
    "target": 172.0, "horizon_days": 90, "narration": "PM: take it.",
})
_PM_PASS = json.dumps({"action": "PASS", "narration": "PM: wait."})
_RECONSIDER = json.dumps({
    "decision": "reconsider",
    "reasons": ["the PASS rested on inadmissible evidence"],
})
_VETO = json.dumps({
    "decision": "veto", "reasons": ["numbered objections went unanswered"],
})
_UPHOLD = json.dumps({"decision": "uphold", "reasons": ["the call stands"]})


def _drain_cio(gateway, ctx, mandate, profile, transcript=()):
    run_id = uuid4()
    run = RoomRun(
        id=run_id, user_id=uuid4(), ticker=ctx.ticker,
        triggered_at=datetime.now(UTC),
        mandate_version=1, model_tier="mid", credit_cost=1,
        transcript=list(transcript),
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


def _review_flags_off(mp):
    mp.setattr(settings, "room_veto_review_enabled", False)
    mp.setattr(settings, "room_resurrection_review_enabled", False)


@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setattr(settings, "room_evidence_gate_enabled", True)
    monkeypatch.setattr(
        settings, "room_evidence_gate_thresholds_json", _THRESHOLDS_JSON
    )
    monkeypatch.setattr(settings, "pm_self_consistency_samples", 1)
    # The CR247 reviews are exercised by their own tests below — keep them
    # out of the rest so a gated verdict is not double-checked.
    _review_flags_off(monkeypatch)
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
    # CR256 contract): 0.2 net support - 0.1 = 0.10 score.
    desks = _very_strong_room_cards()
    desks["bear_researcher"] = _desk_cards(_cards_block(
        eq=("support", "well"), vc=("support", "well"),
        objections="target=eq severity=high objection=the accruals disagree",
    ))
    ctx, mandate, profile = _ctx(cards_by_desk=desks)
    gateway = _GateGateway([_PM_APPROVE])
    _drain_cio(gateway, ctx, mandate, profile)

    prompt = _pm_calls(gateway)[0]["system_prompt"]
    assert "EVIDENCE GATE" in prompt
    assert "Typed evidence score:" in prompt and "0.30" in prompt
    assert "0.20" in prompt  # the R3 threshold this mandate resolves to
    assert "APPROVE and PASS." in prompt
    assert "Computed position size: 1.03%" in prompt
    assert "the accruals disagree" in prompt  # the unresolved objection text
    assert "bear_researcher:eq:0" in prompt  # and its id
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


def test_uncalibrated_model_identity_fails_closed_before_the_pm_call():
    ctx, mandate, profile = _ctx(cards_by_desk=_strong_room_cards())
    gateway = _GateGateway([_PM_APPROVE])  # never consumed
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "room_evidence_gate_enabled", True)
        mp.setattr(settings, "room_evidence_gate_thresholds_json", "{}")
        mp.setattr(settings, "pm_self_consistency_samples", 1)
        _review_flags_off(mp)
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


def test_duplicate_cards_fail_closed_with_the_duplicate_marker(gate_on):
    block = _cards_block(eq=("support", "well"))
    dup_eq = (
        "[CLAIMS]\n"
        "item=eq dir=support grade=well data=yes claim=c nums=1\n"
        "item=eq dir=support grade=well data=yes claim=c nums=1\n"
        "item=vc dir=support grade=well data=yes claim=c nums=1\n"
        "item=vh dir=support grade=well data=yes claim=c nums=1\n"
        "item=bs dir=support grade=well data=yes claim=c nums=1\n"
        "item=moat dir=support grade=well data=yes claim=c nums=1\n"
        "[/CLAIMS]"
    )
    desks = {
        "fundamentals_analyst": _desk_cards(block),
        "bear_researcher": _desk_cards(block),
        "research_manager": _desk_cards(block),
        "bull_researcher": _desk_cards(dup_eq),
    }
    ctx, mandate, profile = _ctx(cards_by_desk=desks)
    gateway = _GateGateway([_PM_APPROVE])
    captured = _drain_cio(gateway, ctx, mandate, profile)

    assert _pm_calls(gateway) == []
    verdict = captured["verdict"]
    assert verdict.action == "PASS"
    assert "duplicate:bull_researcher:eq" in verdict.reason
    assert verdict.decision_record is None


# ── provider+model identity ─────────────────────────────────────────────────


def test_a_named_model_selects_its_own_ladder():
    # Two ladders on the same provider: only the identity that matches the
    # gateway's model may be used — a shared-provider ladder must not apply
    # to every model on that provider.
    thresholds = json.dumps({
        "mock:ami-llm": {"R1": 0.30, "R2": 0.25, "R3": 0.20, "R4": 0.15, "R5": 0.10},
        "mock:ling": {"R1": 0.90, "R2": 0.85, "R3": 0.80, "R4": 0.75, "R5": 0.70},
    })
    # Strong room = 0.2 score: APPROVE under the ami-llm ladder, PASS only
    # under the (deliberately unreachable) ling ladder.
    ctx, mandate, profile = _ctx(cards_by_desk=_strong_room_cards())
    ami = _ModelGateway([_PM_APPROVE], model="ami-llm")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "room_evidence_gate_enabled", True)
        mp.setattr(settings, "room_evidence_gate_thresholds_json", thresholds)
        mp.setattr(settings, "pm_self_consistency_samples", 1)
        _review_flags_off(mp)
        captured = _drain_cio(ami, ctx, mandate, profile)
    assert captured["verdict"].action == "APPROVE"
    assert captured["verdict"].decision_record.threshold == 0.20

    ctx2, mandate2, profile2 = _ctx(cards_by_desk=_strong_room_cards())
    ling = _ModelGateway([_PM_APPROVE], model="ling")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "room_evidence_gate_enabled", True)
        mp.setattr(settings, "room_evidence_gate_thresholds_json", thresholds)
        mp.setattr(settings, "pm_self_consistency_samples", 1)
        _review_flags_off(mp)
        captured2 = _drain_cio(ling, ctx2, mandate2, profile2)
    verdict = captured2["verdict"]
    assert verdict.action == "PASS"  # 0.2 < 0.80: the ling ladder governs
    assert "0.80" in verdict.reason
    assert len(_pm_calls(ling)) == 1  # the CIO was asked; the bar blocked it


def test_several_distinct_models_fail_closed_instead_of_collapsing():
    ctx, mandate, profile = _ctx(cards_by_desk=_strong_room_cards())
    gateway = _MultiModelGateway([_PM_APPROVE])
    thresholds = json.dumps({
        "vllm": {"R1": 0.30, "R2": 0.25, "R3": 0.20, "R4": 0.15, "R5": 0.10},
    })
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "room_evidence_gate_enabled", True)
        mp.setattr(settings, "room_evidence_gate_thresholds_json", thresholds)
        mp.setattr(settings, "pm_self_consistency_samples", 1)
        _review_flags_off(mp)
        captured = _drain_cio(gateway, ctx, mandate, profile)

    # A bare-"vllm" ladder EXISTS but must not match: the identity could not
    # be resolved to one model, so the gate fails closed instead of silently
    # collapsing to the provider.
    assert _pm_calls(gateway) == []
    verdict = captured["verdict"]
    assert verdict.action == "PASS"
    assert "no calibrated evidence thresholds" in verdict.reason


def test_a_gateway_without_status_is_uncalibrated():
    class _NoStatus:
        def has_real_provider(self) -> bool:
            return True

        async def stream_chat(self, **kwargs):
            yield _PM_APPROVE

    ctx, mandate, profile = _ctx(cards_by_desk=_strong_room_cards())
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "room_evidence_gate_enabled", True)
        mp.setattr(
            settings, "room_evidence_gate_thresholds_json", _THRESHOLDS_JSON
        )
        mp.setattr(settings, "pm_self_consistency_samples", 1)
        _review_flags_off(mp)
        captured = _drain_cio(_NoStatus(), ctx, mandate, profile)

    assert captured["verdict"].action == "PASS"
    assert "no calibrated evidence thresholds" in captured["verdict"].reason


# ── post-vote application ───────────────────────────────────────────────────


def test_disallowed_approve_flips_to_pass_with_no_approve_narration(gate_on):
    ctx, mandate, profile = _ctx(cards_by_desk=_bare_room_cards())
    gateway = _GateGateway([_PM_APPROVE])
    captured = _drain_cio(gateway, ctx, mandate, profile)

    verdict = captured["verdict"]
    assert verdict.action == "PASS"
    assert verdict.overridden_from_llm is True
    assert verdict.size_pct is None
    assert "0.00" in verdict.reason and "0.20" in verdict.reason
    assert "PM: take it." not in verdict.reason  # no APPROVE narration
    assert "PM: take it." not in captured["pm_text"]

    record = verdict.decision_record
    assert record is not None
    assert record.score == 0.0
    assert record.threshold == 0.2
    assert record.allowed_actions == ["PASS"]
    assert record.computed_size_pct is None
    assert record.evidence_available is True
    assert record.evidence_source == "claim_cards"
    # The PM wanted in; the gate blocked it — that is contested by definition.
    assert record.contested is True
    assert any("blocked" in r for r in record.contested_reasons)


def test_computed_size_overrides_the_llm_size_and_the_record_says_so(gate_on):
    ctx, mandate, profile = _ctx(cards_by_desk=_very_strong_room_cards())
    gateway = _GateGateway([_PM_APPROVE])  # asks 2.0; gate computes 1.3125
    captured = _drain_cio(gateway, ctx, mandate, profile)

    verdict = captured["verdict"]
    assert verdict.action == "APPROVE"
    assert verdict.size_pct == 1.3125  # the computed evidence size, not 2.0
    assert verdict.overridden_from_llm is True
    assert "evidence gate at 1.31%" in verdict.reason
    assert "CIO's stated 2.00%" in verdict.reason

    record = verdict.decision_record
    assert record.allowed_actions == ["APPROVE", "PASS"]
    assert record.computed_size_pct == 1.3125
    assert record.contested is False
    assert any("computed size" in r for r in record.contested_reasons)


def test_unresolved_objections_mark_the_record_contested_with_their_text(gate_on):
    desks = _strong_room_cards()
    desks["bear_researcher"] = _desk_cards(_cards_block(
        eq=("support", "well"),
        objections="target=eq severity=high objection=the accruals disagree",
    ))
    ctx, mandate, profile = _ctx(cards_by_desk=desks)
    gateway = _GateGateway([_PM_APPROVE])
    captured = _drain_cio(gateway, ctx, mandate, profile)

    record = captured["verdict"].decision_record
    assert record is not None
    assert record.contested is True
    assert "the accruals disagree" in record.unresolved_objections
    assert record.unresolved_objection_ids == ["bear_researcher:eq:0"]
    assert any("the accruals disagree" in r for r in record.contested_reasons)


def test_the_record_emits_the_mobile_wire_contract_keys(gate_on):
    desks = _strong_room_cards()
    desks["bear_researcher"] = _desk_cards(_cards_block(
        eq=("support", "well"),
        objections="target=eq severity=high objection=the accruals disagree",
    ))
    ctx, mandate, profile = _ctx(cards_by_desk=desks)
    gateway = _GateGateway([_PM_APPROVE])
    captured = _drain_cio(gateway, ctx, mandate, profile)

    payload = captured["verdict"].decision_record.model_dump(mode="json")
    assert set(payload.keys()) == {
        "score", "threshold", "allowed_actions", "computed_size_pct",
        "unresolved_objections", "unresolved_objection_ids",
        "evidence_available", "evidence_source", "contested",
        "contested_reasons",
    }
    assert payload["unresolved_objections"] == ["the accruals disagree"]
    assert payload["unresolved_objection_ids"] == ["bear_researcher:eq:0"]
    assert "reasons" not in payload
    assert "unresolved_objection_count" not in payload


def test_at_threshold_score_ships_25pct_of_cap(gate_on):
    # The strong room scores exactly the 0.20 threshold: 25% of the 3.0% cap.
    ctx, mandate, profile = _ctx(cards_by_desk=_strong_room_cards())
    gateway = _GateGateway([_PM_APPROVE])
    captured = _drain_cio(gateway, ctx, mandate, profile)

    verdict = captured["verdict"]
    assert verdict.action == "APPROVE"
    assert verdict.size_pct == 0.75
    assert verdict.decision_record.score == 0.2
    assert verdict.decision_record.contested is True  # on the bar


# ── the floor stays final ───────────────────────────────────────────────────


def test_the_safety_floor_stays_final_over_a_gate_allowed_approve(gate_on):
    # Evidence clears the bar, but the account is past its drawdown cap:
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
    assert any("blocked" in r for r in record.contested_reasons)


def test_a_split_vote_marks_the_record_contested():
    ctx, mandate, profile = _ctx(cards_by_desk=_strong_room_cards())
    gateway = _GateGateway([_PM_APPROVE, _PM_PASS, _PM_PASS])
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "room_evidence_gate_enabled", True)
        mp.setattr(
            settings, "room_evidence_gate_thresholds_json", _THRESHOLDS_JSON
        )
        mp.setattr(settings, "pm_self_consistency_samples", 3)
        _review_flags_off(mp)
        captured = _drain_cio(gateway, ctx, mandate, profile)

    verdict = captured["verdict"]
    assert verdict.action == "PASS"  # 1 of 3 approves misses the bar
    assert verdict.samples == 3
    assert "split" in verdict.reason
    record = verdict.decision_record
    assert record.contested is True
    assert any("split" in r for r in record.contested_reasons)
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
    assert any("scripted" in r for r in record.contested_reasons)


# ── review bypass closures (CR247 interaction) ──────────────────────────────


def _dissent_transcript() -> list:
    from app.schemas import AgentMessage

    return [
        AgentMessage(
            agent_id=AgentId.BEAR_RESEARCHER, role="agent",
            content="The bear case, argued in full.",
            timestamp=datetime.now(UTC),
        ),
        AgentMessage(
            agent_id=AgentId.CONSERVATIVE_DEBATOR, role="agent",
            content="The conservative objections, argued in full.",
            timestamp=datetime.now(UTC),
        ),
    ]


def test_a_gate_blocked_approve_pass_never_enters_resurrection():
    ctx, mandate, profile = _ctx(cards_by_desk=_bare_room_cards())
    gateway = _ReviewGateway([_PM_APPROVE, _RECONSIDER, _PM_APPROVE])
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "room_evidence_gate_enabled", True)
        mp.setattr(
            settings, "room_evidence_gate_thresholds_json", _THRESHOLDS_JSON
        )
        mp.setattr(settings, "pm_self_consistency_samples", 1)
        mp.setattr(settings, "room_veto_review_enabled", False)
        mp.setattr(settings, "room_resurrection_review_enabled", True)
        captured = _drain_cio(gateway, ctx, mandate, profile)

    verdict = captured["verdict"]
    assert verdict.action == "PASS"
    # The resurrection review was never routed: no audit call consumed, no
    # review record, and the trailing APPROVE reply is still unconsumed.
    assert verdict.verdict_review is None
    review_calls = [c for c in gateway.calls if c["flow"] == "room_resurrection_review"]
    assert review_calls == []
    assert len(_pm_calls(gateway)) == 1  # only the original draw


def test_an_organic_pass_under_the_gate_still_routes_to_resurrection():
    """CR247 behaviour is unchanged when the gate did not force the PASS."""
    ctx, mandate, profile = _ctx(cards_by_desk=_very_strong_room_cards())
    gateway = _ReviewGateway([_PM_PASS, _UPHOLD])
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "room_evidence_gate_enabled", True)
        mp.setattr(
            settings, "room_evidence_gate_thresholds_json", _THRESHOLDS_JSON
        )
        mp.setattr(settings, "pm_self_consistency_samples", 1)
        mp.setattr(settings, "room_veto_review_enabled", False)
        mp.setattr(settings, "room_resurrection_review_enabled", True)
        captured = _drain_cio(gateway, ctx, mandate, profile)

    verdict = captured["verdict"]
    assert verdict.action == "PASS"
    assert verdict.verdict_review is not None
    assert verdict.verdict_review.kind == "resurrection"
    assert verdict.verdict_review.decision == "uphold"
    # Unchanged decision -> the record is not rebuilt with review state.
    assert verdict.decision_record.contested is False
    assert not any("review" in r for r in verdict.decision_record.contested_reasons)


def test_a_resurrection_rerun_meets_the_gate_size_before_the_floor():
    ctx, mandate, profile = _ctx(cards_by_desk=_strong_room_cards())
    gateway = _ReviewGateway([_PM_PASS, _RECONSIDER, _PM_APPROVE])
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "room_evidence_gate_enabled", True)
        mp.setattr(
            settings, "room_evidence_gate_thresholds_json", _THRESHOLDS_JSON
        )
        mp.setattr(settings, "pm_self_consistency_samples", 1)
        mp.setattr(settings, "room_veto_review_enabled", False)
        mp.setattr(settings, "room_resurrection_review_enabled", True)
        captured = _drain_cio(gateway, ctx, mandate, profile)

    verdict = captured["verdict"]
    assert verdict.action == "APPROVE"  # resurrected by the re-run
    assert verdict.verdict_review.rerun is True
    # The re-run asked 2.0%; the gate's computed size binds it before the floor.
    assert verdict.size_pct == 0.75
    # The FINAL record describes the FINAL verdict and names the review change.
    record = verdict.decision_record
    assert record is not None
    assert record.contested is True
    assert any("review" in r and "PASS -> APPROVE" in r
               for r in record.contested_reasons)


def test_a_veto_flip_leaves_a_final_record_describing_the_final_verdict():
    ctx, mandate, profile = _ctx(cards_by_desk=_strong_room_cards())
    gateway = _ReviewGateway([_PM_APPROVE, _VETO])
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "room_evidence_gate_enabled", True)
        mp.setattr(
            settings, "room_evidence_gate_thresholds_json", _THRESHOLDS_JSON
        )
        mp.setattr(settings, "pm_self_consistency_samples", 1)
        mp.setattr(settings, "room_veto_review_enabled", True)
        mp.setattr(settings, "room_resurrection_review_enabled", False)
        captured = _drain_cio(
            gateway, ctx, mandate, profile, transcript=_dissent_transcript(),
        )

    verdict = captured["verdict"]
    assert verdict.action == "PASS"  # veto flipped the gate-allowed APPROVE
    assert verdict.verdict_review.kind == "veto"
    assert verdict.verdict_review.original["action"] == "APPROVE"
    record = verdict.decision_record
    assert record is not None
    assert record.contested is True
    assert any("review" in r and "APPROVE -> PASS" in r
               for r in record.contested_reasons)
    assert any("blocked" in r for r in record.contested_reasons)


# ── persistence + capture ───────────────────────────────────────────────────


def test_the_record_survives_the_json_round_trip(gate_on):
    desks = _strong_room_cards()
    desks["bear_researcher"] = _desk_cards(_cards_block(
        eq=("support", "well"),
        objections="target=eq severity=high objection=the accruals disagree",
    ))
    ctx, mandate, profile = _ctx(cards_by_desk=desks)
    gateway = _GateGateway([_PM_APPROVE])
    captured = _drain_cio(gateway, ctx, mandate, profile)

    verdict = captured["verdict"]
    assert verdict.decision_record is not None
    payload = json.loads(json.dumps(verdict.model_dump(mode="json")))
    restored = Verdict.model_validate(payload)
    assert restored.decision_record == verdict.decision_record
    assert restored.decision_record.unresolved_objections == [
        "the accruals disagree"
    ]


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


def test_a_missing_registry_fails_closed_before_the_pm_call(gate_on):
    # Complete supportive cards but no fact-sheet registry: data presence is
    # registry-backed, so the evidence is uncomputable and the convene fails
    # closed BEFORE the CIO is asked — never an ordinary neutral room.
    ctx, mandate, profile = _ctx(cards_by_desk=_strong_room_cards())
    profile = dict(profile)
    profile.pop("field_state")
    gateway = _GateGateway([_PM_APPROVE])  # never consumed
    captured = _drain_cio(gateway, ctx, mandate, profile)

    assert _pm_calls(gateway) == []
    verdict = captured["verdict"]
    assert verdict.action == "PASS"
    assert verdict.overridden_from_llm is True
    assert "registry:field_state" in verdict.reason
    assert verdict.decision_record is None  # never fabricated
