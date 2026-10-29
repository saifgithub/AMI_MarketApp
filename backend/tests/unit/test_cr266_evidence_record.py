"""CR266 — the typed evidence record and the PM evidence gate (pure half).

Pinned here, against `evidence_record.py` only:

1. Direction x grade arithmetic: support +, oppose -, neutral 0; well 1,
   partial .5, unsupported 0 — and data presence decides from the fact-sheet
   `field_state` REGISTRY, never the card's own `data=` self-report. Missing
   data is neutral/unsupported, never silently bearish: an unevidenced
   "oppose" contributes 0, not -1.
2. Net support, unresolved objections (adequate severity, opposite-direction
   evidenced cards from ANOTHER desk), score = net - 0.1 per unresolved.
3. Threshold config: per provider, exactly R1..R5 in [0, 1], monotone
   R1>=R2>=R3>=R4>=R5 — validated loudly (boot fails, never clamps).
4. Allowed actions (PASS only below the bar), the continuous size (25% of cap
   at the threshold, 100% at score 1.0, monotone), contestedness, and the
   fail-closed gate decision shapes.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.evidence_record import (
    ADEQUATE_SEVERITIES,
    UNRESOLVED_PENALTY,
    EvidenceGateDecision,
    ThresholdConfigError,
    allowed_actions,
    build_evidence_record,
    build_gate_decision,
    computed_size_pct,
    gate_contested,
    parse_gate_thresholds,
    threshold_for_risk,
)
from app.services.room_runner import parse_claim_cards

# ── fixtures ────────────────────────────────────────────────────────────────

_REGISTRY_FIELDS = (
    "free_cash_flow", "sbc", "net_cash", "roic", "wacc",
    "pe", "forward_pe", "ev_to_ebitda", "peg_ratio", "price_to_sales",
    "total_debt", "interest_coverage", "debt_maturity", "current_ratio",
    "quick_ratio", "debt_to_equity",
    "gross_margin", "operating_margin", "rev_growth", "profit_margin",
)


def _field_state(*, live: bool = True) -> dict[str, str]:
    return dict.fromkeys(_REGISTRY_FIELDS, "live" if live else "unavailable")


def _cards_block(
    eq=("support", "well"),
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
        lines.append(
            f"item={item} dir={direction} grade={grade} data=yes "
            f"claim=c claim nums=1"
        )
    lines.append("[/CLAIMS]")
    if objections:
        lines.append("[OBJECTIONS]")
        lines.append(objections)
        lines.append("[/OBJECTIONS]")
    return "\n".join(lines)


def _desk_cards(text: str):
    _, cards = parse_claim_cards(text)
    assert cards is not None
    return cards


def _room_cards(
    desks: dict[str, str] | None = None,
    *,
    field_state: dict[str, str] | None = None,
):
    desks = desks or {
        "fundamentals_analyst": _cards_block(),
        "bull_researcher": _cards_block(),
        "bear_researcher": _cards_block(),
        "research_manager": _cards_block(),
    }
    return build_evidence_record(desks, field_state or _field_state())


# ── direction x grade arithmetic ────────────────────────────────────────────


def test_direction_weights_support_oppose_neutral():
    record = build_evidence_record(
        {
            "fundamentals_analyst": _desk_cards(
                _cards_block(eq=("support", "well"))
            ),
        },
        _field_state(),
    )
    by_item = {ev.item: ev for ev in record.items}
    assert by_item["eq"].contribution == 1.0
    assert by_item["vc"].contribution == 0.0


def test_grade_weights_well_partial_unsupported():
    record = build_evidence_record(
        {
            "fundamentals_analyst": _desk_cards(
                "[CLAIMS]\n"
                "item=eq dir=support grade=well data=yes claim=c nums=1\n"
                "item=vc dir=support grade=partial data=yes claim=c nums=1\n"
                "item=vh dir=support grade=unsupported data=yes claim=c nums=1\n"
                "[/CLAIMS]"
            ),
        },
        _field_state(),
    )
    by_item = {ev.item: ev for ev in record.items}
    assert by_item["eq"].contribution == 1.0
    assert by_item["vc"].contribution == 0.5
    assert by_item["vh"].contribution == 0.0


def test_oppose_is_negative_when_the_registry_has_the_data():
    record = build_evidence_record(
        {"bear_researcher": _desk_cards(
            "[CLAIMS]\nitem=bs dir=oppose grade=well data=yes claim=c nums=1\n[/CLAIMS]"
        )},
        _field_state(),
    )
    assert {ev.item: ev for ev in record.items}["bs"].contribution == -1.0
    assert record.net_support == -1.0


def test_data_present_comes_from_the_registry_not_the_self_report():
    # The card claims data=yes, but the registry says the bs fields were not
    # live: the oppose must not count. The card claiming data=no while the
    # registry IS live does count — self-report is not the control.
    record = build_evidence_record(
        {
            "bear_researcher": _desk_cards(
                "[CLAIMS]\n"
                "item=bs dir=oppose grade=well data=yes claim=c nums=1\n"
                "[/CLAIMS]"
            ),
        },
        _field_state(live=False),
    )
    assert record.data_present["bs"] is False
    assert record.items[0].contribution == 0.0
    assert record.net_support == 0.0

    record_live = build_evidence_record(
        {
            "bear_researcher": _desk_cards(
                "[CLAIMS]\n"
                "item=bs dir=oppose grade=well data=no claim=c nums=1\n"
                "[/CLAIMS]"
            ),
        },
        _field_state(live=True),
    )
    assert record_live.data_present["bs"] is True
    assert record_live.items[0].contribution == -1.0


def test_missing_data_is_neutral_never_silently_bearish():
    # A room full of unevidenced oppose cards scores 0 — not negative: missing
    # data can talk a run OUT of an approve only through the absence of
    # support, never by manufacturing bearishness.
    desks = {
        desk: _desk_cards(_cards_block(
            eq=("oppose", "well"), vc=("oppose", "well"), vh=("oppose", "well"),
            bs=("oppose", "well"), moat=("oppose", "well"),
        ))
        for desk in ("fundamentals_analyst", "bull_researcher",
                     "bear_researcher", "research_manager")
    }
    record = build_evidence_record(desks, _field_state(live=False))
    assert record.net_support == 0.0
    assert record.score == 0.0


def test_net_support_sums_across_desks():
    desks = {
        "fundamentals_analyst": _desk_cards(_cards_block(eq=("support", "well"))),
        "bull_researcher": _desk_cards(_cards_block(eq=("support", "partial"))),
        "bear_researcher": _desk_cards(_cards_block(eq=("oppose", "well"))),
        "research_manager": _desk_cards(_cards_block(eq=("neutral", "well"))),
    }
    record = build_evidence_record(desks, _field_state())
    assert record.net_support == pytest.approx(1.0 + 0.5 - 1.0 + 0.0)


# ── objections ──────────────────────────────────────────────────────────────


def test_an_objection_without_an_opposite_evidenced_card_is_unresolved():
    desks = {
        desk: _desk_cards(_cards_block(eq=("support", "well")))
        for desk in ("fundamentals_analyst", "bull_researcher",
                     "bear_researcher", "research_manager")
    }
    desks["bear_researcher"] = _desk_cards(_cards_block(
        eq=("support", "well"),
        objections="target=eq severity=high objection=the accruals disagree",
    ))
    record = build_evidence_record(desks, _field_state())
    assert record.unresolved_objection_count == 1
    assert record.unresolved_objections == ("bear_researcher:eq:0",)
    assert record.score == pytest.approx(record.net_support - UNRESOLVED_PENALTY)


def test_an_opposite_evidenced_card_from_another_desk_resolves_it():
    desks = {
        desk: _desk_cards(_cards_block(eq=("support", "well")))
        for desk in ("fundamentals_analyst", "bull_researcher",
                     "bear_researcher", "research_manager")
    }
    desks["bear_researcher"] = _desk_cards(_cards_block(
        eq=("support", "well"),
        objections="target=eq severity=high objection=the accruals disagree",
    ))
    desks["research_manager"] = _desk_cards(_cards_block(eq=("oppose", "well")))
    record = build_evidence_record(desks, _field_state())
    assert record.unresolved_objection_count == 0


def test_a_desks_own_card_does_not_resolve_its_own_objection():
    # Bear objects to eq and is the ONLY desk pointing anywhere (oppose); the
    # other three file neutral/unsupported eq cards — no other desk filed an
    # opposite-direction evidenced card, so the objection stands.
    neutral = _cards_block(eq=("neutral", "unsupported"))
    desks = {
        "fundamentals_analyst": _desk_cards(neutral),
        "bull_researcher": _desk_cards(neutral),
        "research_manager": _desk_cards(neutral),
        "bear_researcher": _desk_cards(_cards_block(
            eq=("oppose", "well"),
            objections="target=eq severity=high objection=the accruals disagree",
        )),
    }
    record = build_evidence_record(desks, _field_state())
    assert record.unresolved_objections == ("bear_researcher:eq:0",)


def test_an_objection_with_no_own_card_resolves_on_any_evidenced_card():
    # Bear files no eq card at all (only bs) and objects to eq; the room's
    # evidenced eq support cards ARE the answer on the record.
    desks = {
        desk: _desk_cards(_cards_block(eq=("support", "well")))
        for desk in ("fundamentals_analyst", "bull_researcher",
                     "research_manager")
    }
    desks["bear_researcher"] = _desk_cards(
        "[CLAIMS]\nitem=bs dir=oppose grade=well data=yes claim=c nums=1\n"
        "[/CLAIMS]"
        + "\n[OBJECTIONS]\ntarget=eq severity=high objection=where are the accruals\n[/OBJECTIONS]"
    )
    record = build_evidence_record(desks, _field_state())
    assert record.unresolved_objection_count == 0


def test_low_severity_never_binds():
    assert "low" not in ADEQUATE_SEVERITIES
    desks = {
        desk: _desk_cards(_cards_block(eq=("support", "well")))
        for desk in ("fundamentals_analyst", "bull_researcher",
                     "bear_researcher", "research_manager")
    }
    desks["bear_researcher"] = _desk_cards(_cards_block(
        eq=("support", "well"),
        objections="target=eq severity=low objection=a footnote at best",
    ))
    record = build_evidence_record(desks, _field_state())
    assert record.unresolved_objection_count == 0
    assert record.score == pytest.approx(record.net_support)


def test_an_unevidenced_opposite_card_does_not_resolve():
    desks = {
        desk: _desk_cards(_cards_block(eq=("support", "well")))
        for desk in ("fundamentals_analyst", "bull_researcher",
                     "bear_researcher")
    }
    desks["bear_researcher"] = _desk_cards(_cards_block(
        eq=("support", "well"),
        objections="target=eq severity=medium objection=groundless but loud",
    ))
    desks["research_manager"] = _desk_cards(_cards_block(eq=("oppose", "well")))
    # The registry has no live eq payload anywhere, so the research manager's
    # oppose card carries nothing and cannot answer the objection.
    state = _field_state()
    for field in ("free_cash_flow", "sbc", "net_cash"):
        state[field] = "unavailable"
    record = build_evidence_record(desks, state)
    assert record.data_present["eq"] is False
    assert record.unresolved_objections == ("bear_researcher:eq:0",)


# ── threshold config ────────────────────────────────────────────────────────


_GOOD = '{"vllm": {"R1": 0.6, "R2": 0.55, "R3": 0.5, "R4": 0.45, "R5": 0.4}}'


def test_threshold_config_parses_per_provider():
    parsed = parse_gate_thresholds(_GOOD)
    assert parsed["vllm"]["R3"] == 0.5
    assert parse_gate_thresholds("") == {}
    assert parse_gate_thresholds("{}") == {}


@pytest.mark.parametrize("raw", [
    "not json",
    "[1, 2]",
    '{"vllm": [0.5]}',
    '{"vllm": {"R1": 0.6, "R2": 0.5, "R3": 0.4, "R4": 0.3}}',        # missing R5
    '{"vllm": {"R1": 0.6, "R2": 0.5, "R3": 0.4, "R4": 0.3, "R5": 0.2, "R6": 0.1}}',
    '{"vllm": {"R1": 0.3, "R2": 0.4, "R3": 0.2, "R4": 0.1, "R5": 0.05}}',  # non-monotone
    '{"vllm": {"R1": 0.6, "R2": 0.6, "R3": 0.6, "R4": 1.2, "R5": 0.4}}',   # out of range
    '{"vllm": {"R1": true, "R2": 0.5, "R3": 0.4, "R4": 0.3, "R5": 0.2}}',  # bool
    '{"": {"R1": 0.6, "R2": 0.5, "R3": 0.4, "R4": 0.3, "R5": 0.2}}',
])
def test_threshold_config_rejects_miscalibration_loudly(raw):
    with pytest.raises(ThresholdConfigError):
        parse_gate_thresholds(raw)


def test_threshold_config_equality_is_allowed():
    # Flat runs are monotone (R1>=...>=R5 holds at equality) — one threshold
    # for every risk level is a legal calibration.
    parsed = parse_gate_thresholds(
        '{"mock": {"R1": 0.5, "R2": 0.5, "R3": 0.5, "R4": 0.5, "R5": 0.5}}'
    )
    assert parsed["mock"]["R5"] == 0.5


def test_settings_fails_boot_on_miscalibrated_thresholds():
    with pytest.raises(Exception, match="miscalibrated"):
        Settings(room_evidence_gate_thresholds_json=(
            '{"vllm": {"R1": 0.1, "R2": 0.2, "R3": 0.3, "R4": 0.4, "R5": 0.5}}'
        ))


def test_threshold_selection_is_per_provider_and_clamps_risk():
    thresholds = parse_gate_thresholds(_GOOD)
    assert threshold_for_risk(thresholds, "vllm", 3) == 0.5
    assert threshold_for_risk(thresholds, "vllm", 1) == 0.6
    assert threshold_for_risk(thresholds, "vllm", 5) == 0.4
    assert threshold_for_risk(thresholds, "kimi", 3) is None
    assert threshold_for_risk(thresholds, None, 3) is None


# ── allowed actions, size, contestedness ────────────────────────────────────


def test_allowed_actions_pass_only_below_threshold():
    assert allowed_actions(0.49, 0.5) == ("PASS",)
    assert allowed_actions(0.5, 0.5) == ("APPROVE", "PASS")
    assert allowed_actions(9.0, 0.5) == ("APPROVE", "PASS")


def test_size_is_none_below_the_threshold():
    assert computed_size_pct(0.49, 0.5, 3.0) is None


def test_size_is_25pct_of_cap_at_the_threshold_and_full_cap_at_one():
    assert computed_size_pct(0.5, 0.5, 3.0) == pytest.approx(0.75)
    assert computed_size_pct(1.0, 0.5, 3.0) == pytest.approx(3.0)


def test_size_interpolates_linearly_and_is_monotone():
    threshold = 0.4
    cap = 4.0
    at_60 = computed_size_pct(0.6, threshold, cap)
    assert at_60 == pytest.approx(cap * 0.25 + cap * 0.75 * (0.2 / 0.6))
    scores = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.5]
    sizes = [computed_size_pct(s, threshold, cap) for s in scores]
    assert all(a <= b for a, b in zip(sizes, sizes[1:], strict=False)), sizes
    assert sizes[-1] == cap  # clamped at the cap past 1.0


def test_contestedness_signals():
    base = {"score": 0.8, "threshold": 0.5, "margin": 0.10}
    assert gate_contested(split_vote=False, bar_blocked=False, scripted_turns=0, **base) is False
    assert gate_contested(split_vote=True, bar_blocked=False, scripted_turns=0, **base) is True
    assert gate_contested(split_vote=False, bar_blocked=True, scripted_turns=0, **base) is True
    assert gate_contested(split_vote=False, bar_blocked=False, scripted_turns=1, **base) is True
    # score inside the margin of the threshold is contested
    assert gate_contested(split_vote=False, bar_blocked=False, scripted_turns=0,
                          score=0.55, threshold=0.5, margin=0.10) is True
    # 0.6-0.5 lands inside the margin at float precision too — go clear of it
    assert gate_contested(split_vote=False, bar_blocked=False, scripted_turns=0,
                          score=0.65, threshold=0.5, margin=0.10) is False


# ── availability + the gate decision shapes ─────────────────────────────────


def test_a_missing_desk_makes_evidence_unavailable_and_names_it():
    record = _room_cards(desks={
        "fundamentals_analyst": _desk_cards(_cards_block()),
        "bull_researcher": _desk_cards(_cards_block()),
        "bear_researcher": _desk_cards(_cards_block()),
    })
    assert record.evidence_available is False
    assert "cards:research_manager" in record.missing


def test_an_uncovered_item_makes_evidence_unavailable():
    record = _room_cards(desks={
        desk: _desk_cards(
            "[CLAIMS]\nitem=eq dir=support grade=well data=yes claim=c nums=1\n[/CLAIMS]"
        )
        for desk in ("fundamentals_analyst", "bull_researcher",
                     "bear_researcher", "research_manager")
    })
    assert record.evidence_available is False
    assert "item:vc" in record.missing
    assert "item:moat" in record.missing


def _gate(**overrides) -> EvidenceGateDecision:
    params = {
        "cards_by_desk": {
            desk: _desk_cards(_cards_block(eq=("support", "well")))
            for desk in ("fundamentals_analyst", "bull_researcher",
                         "bear_researcher", "research_manager")
        },
        "field_state": _field_state(),
        "thresholds": parse_gate_thresholds(_GOOD),
        "provider": "vllm",
        "risk_score": 3,
        "cap_pct": 3.0,
    }
    params.update(overrides)
    return build_gate_decision(**params)


def test_gate_decision_happy_path():
    gate = _gate()
    assert gate.fail_closed_reason is None
    assert gate.threshold == 0.5
    assert gate.allowed_actions == ("APPROVE", "PASS")
    assert gate.computed_size_pct == 3.0  # score 20 (4 desks x 5) clamps to cap
    assert gate.record.evidence_available is True


def test_gate_fails_closed_on_uncalibrated_provider_with_reason():
    gate = _gate(provider="kimi")
    assert gate.fail_closed_reason is not None
    assert "kimi" in gate.fail_closed_reason
    assert gate.allowed_actions == ("PASS",)
    assert gate.computed_size_pct is None


def test_gate_fails_closed_on_missing_cards_with_reason():
    gate = _gate(cards_by_desk={})
    assert gate.fail_closed_reason is not None
    assert "missing" in gate.fail_closed_reason
    assert gate.record.evidence_available is False


def test_gate_pass_only_below_threshold():
    neutral = _cards_block(eq=("neutral", "unsupported"))
    gate = _gate(cards_by_desk={
        "fundamentals_analyst": _desk_cards(_cards_block(eq=("support", "partial"))),
        "bull_researcher": _desk_cards(neutral),
        "bear_researcher": _desk_cards(neutral),
        "research_manager": _desk_cards(neutral),
    })
    assert gate.record.score == 0.5  # one evidenced partial support
    assert gate.allowed_actions == ("APPROVE", "PASS")  # 0.5 >= 0.5
    assert gate.computed_size_pct == pytest.approx(0.75)  # 25% of cap at bar

    gate_below = _gate(cards_by_desk={
        "fundamentals_analyst": _desk_cards(
            "[CLAIMS]\nitem=eq dir=neutral grade=unsupported data=no claim=c\n[/CLAIMS]"
        ),
        "bull_researcher": _desk_cards(neutral),
        "bear_researcher": _desk_cards(neutral),
        "research_manager": _desk_cards(neutral),
    })
    assert gate_below.record.score == 0.0
    assert gate_below.allowed_actions == ("PASS",)
    assert gate_below.computed_size_pct is None
