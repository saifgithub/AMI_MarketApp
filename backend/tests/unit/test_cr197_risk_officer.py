"""CR197 — the single structured Risk Officer that replaces three arguing ones.

Measured over 136 replayed convenes, this design reproduces the three-officer debate's
decision behaviour exactly: 22 approvals against the debate's 22 (16.4% vs 16.3%), net
0 verdicts changed, 9 flips up and 9 down — the same symmetric shape as replaying the
identical prompt twice (8/8). It does that on ONE LLM call instead of three, one serial
round-trip instead of three, and with output a parser can read.

The two arms that bracket it say why it works. Strip the debate and add nothing: 7.4%.
Strip it and add the deterministic ladder alone: 11.8%. The gap between the ladder and
the full debate was never arithmetic — it was ticker-specific REASONS attached to each
size, which is precisely what this officer supplies and what the ladder cannot.

The property these tests exist to hold is the structural one: the model may not emit a
computed number. Sizes come from the ladder and the renderer reads them from the ladder,
never from the payload, so a model that echoes back a size nobody offered cannot smuggle
an unpriced option onto the CIO's menu.
"""

from __future__ import annotations

import pytest

from app.services.risk_officer import (
    RISK_OFFICER_PERSONA,
    _rung_head,
    build_risk_officer_instruction,
    render_risk_assessment,
)
from app.trading_math.option_ladder import build_option_ladder

_CAP = 30.0


@pytest.fixture
def rows():
    return build_option_ladder(
        reference_size_pct=3.0, entry=100.0, stop=94.0, target=113.0,
        cap_pts=_CAP, current_drawdown_pct=0.0,
    )


def _payload(sizes=(1.5, 3.0, 5.0), **kw):
    p = {
        "options": [
            {
                "size_pct": s,
                "case_for": f"for-{s}",
                "case_against": f"against-{s}",
                "key_number": f"kn-{s}",
            }
            for s in sizes
        ],
        "recommended": 3.0,
        "confidence": "medium",
        # CR219 R59-F2: a genuine quotation, not a placeholder. `render_risk_
        # assessment` now checks `key_number`/`decisive_number` against the
        # sheet/ladder before rendering them — "0.18" is the reference rung's
        # OWN `contribution_pts` for this fixture's ladder (reference_size_pct
        # 3.0, entry 100/stop 94/target 113, cap_pts 30.0), so it is a figure
        # the officer is actually entitled to cite, not an unquotable one that
        # would now render struck.
        "decisive_number": "0.18",
    }
    p.update(kw)
    return p


# ── the officer is not an advocate ───────────────────────────────────────────


def test_the_persona_refuses_a_house_view():
    """The three-officer design assigned positions, and the positions never moved —
    'for' in 117 of 118 convenes, 'against' in 117 of 118. One officer making both
    cases is the fix, so the prompt must say so."""
    assert "You are one officer, not an advocate for a position" in RISK_OFFICER_PERSONA
    assert "Do not argue a house view" in RISK_OFFICER_PERSONA


def test_the_officer_does_not_decide():
    assert "You do not decide whether the trade happens" in RISK_OFFICER_PERSONA


# ── the model may not emit a computed number ─────────────────────────────────


def test_the_instruction_fixes_the_sizes(rows):
    """Sizes are `risk_debator_sizes`, not the model's to choose. Fixing them is what
    makes the arithmetic unfalsifiable: there is no size in the output the model
    invented, so no drawdown figure it can get wrong."""
    text = build_risk_officer_instruction(rows)
    assert "1.5, 3.0, 5.0" in text
    assert "Do not invent a size" in text


def test_the_instruction_forbids_recomputing_risk_figures(rows):
    text = build_risk_officer_instruction(rows)
    assert "do not restate a drawdown or cap figure of your own" in text


def test_key_number_is_a_quotation_not_a_calculation(rows):
    assert "quote it, do not compute anything new" in build_risk_officer_instruction(rows)


def test_confidence_must_distinguish_a_close_call(rows):
    """The debate's conviction channel was near-constant too (the Aggressive never
    once said 'low' in 118 turns). If this one collapses the same way it carries no
    more information than the thing it replaced."""
    text = build_risk_officer_instruction(rows)
    assert "low when the data genuinely does not adjudicate" in text


# ── rendering: figures come from the ladder, never the payload ───────────────


def test_figures_are_the_ladders_not_the_models(rows):
    """The payload here claims a wrong contribution. It must not reach the CIO."""
    payload = _payload()
    payload["options"][1]["contribution_pts"] = 99.9
    text = render_risk_assessment(payload, rows)
    assert "99.9" not in text
    assert "0.18 pt of drawdown" in text


def test_a_size_nobody_offered_is_dropped(rows):
    """A model echoing back an unpriced size would put an option on the menu that no
    ladder rung priced and no cap check bounded."""
    text = render_risk_assessment(_payload(sizes=(1.5, 3.0, 5.0, 12.0)), rows)
    assert "12.0%" not in text
    assert text.count("- **") == 3


def test_every_ladder_rung_appears_even_when_unassessed(rows):
    """Silence about a rung must read as silence, not as absence of the option."""
    text = render_risk_assessment(_payload(sizes=(1.5, 3.0)), rows)
    assert "5.0%" in text
    assert "did not assess this size" in text


def test_both_cases_are_rendered(rows):
    text = render_risk_assessment(_payload(), rows)
    assert "For: for-3.0" in text
    assert "Against: against-3.0" in text
    assert "Key figure: kn-3.0" in text


def test_the_call_and_its_confidence_are_carried(rows):
    text = render_risk_assessment(_payload(), rows)
    assert "Risk Officer's call:" in text
    assert "3.0%" in text and "confidence medium" in text
    assert "decided by 0.18" in text


def test_it_is_offered_as_options_not_instructions(rows):
    """Same requirement as the ladder: 26% of baseline approvals land between rungs,
    so a menu presented as closed would narrow the decision rather than inform it."""
    text = render_risk_assessment(_payload(), rows)
    assert "These are options, not instructions" in text
    assert "land between them" in text
    assert "safety floor" in text


# ── degradation ──────────────────────────────────────────────────────────────


def test_an_empty_payload_still_lists_the_priced_options(rows):
    text = render_risk_assessment({}, rows)
    assert text.count("- **") == 3
    assert "did not assess this size" in text


def test_a_garbled_size_is_skipped_not_crashed(rows):
    payload = _payload()
    payload["options"].append({"size_pct": "not-a-number", "case_for": "x"})
    text = render_risk_assessment(payload, rows)
    assert "not-a-number" not in text


def test_missing_fields_shrink_the_row_rather_than_inventing_one(rows):
    payload = {"options": [{"size_pct": 3.0, "case_for": "only-for"}]}
    text = render_risk_assessment(payload, rows)
    assert "For: only-for" in text
    assert "Against:" not in text
    assert "Key figure:" not in text


# ── §13(a): `_rung_head` renders the per-rung dollar risk ────────────────────


def _rung(size_pct, *, portfolio_value=None):
    """One reference-ladder rung, by size, with an optional portfolio value —
    same fixture inputs `rows` above uses (entry 100/stop 94/target 113, cap
    30), so the pt figures below match the module's other tests exactly."""
    rows = build_option_ladder(
        reference_size_pct=3.0, entry=100.0, stop=94.0, target=113.0,
        cap_pts=_CAP, current_drawdown_pct=0.0, portfolio_value=portfolio_value,
    )
    return next(r for r in rows if r.size_pct == size_pct)


def test_rung_head_carries_the_dollar_risk_when_portfolio_value_is_known():
    """The exact rendered shape: dollar risk sits between the pt-of-drawdown
    clause and the pt-of-cap-left clause, formatted by the module's existing
    money formatter (DEF234/242-safe thousands separator, no decimals)."""
    r = _rung(3.0, portfolio_value=100_000.0)
    assert r.dollar_risk_usd == pytest.approx(180.0)
    assert _rung_head(r) == (
        "**3.0%** of portfolio (≈ 0.18 pt of drawdown, $180 at risk, "
        "29.82 pt of cap left)"
    )


def test_rung_head_is_byte_identical_with_no_portfolio_value():
    """The load-bearing caution (audit §4): a missing portfolio value must
    render NOTHING for the dollar figure, not `$0` — and the rest of the line
    must be untouched by the new clause's absence."""
    with_value = _rung(3.0, portfolio_value=None)
    assert with_value.dollar_risk_usd is None
    assert _rung_head(with_value) == (
        "**3.0%** of portfolio (≈ 0.18 pt of drawdown, 29.82 pt of cap left)"
    )
    assert "$" not in _rung_head(with_value)
    assert "at risk" not in _rung_head(with_value)


def test_rung_head_renders_nothing_for_a_zero_portfolio_value_never_a_dollar_zero():
    """Zero is exactly the case the audit called out by name: '$0' would read
    as a measured fact ('this rung risks nothing'), not as 'unknown'."""
    r = _rung(3.0, portfolio_value=0.0)
    assert r.dollar_risk_usd is None
    text = _rung_head(r)
    assert "$0" not in text
    assert "at risk" not in text


def test_rung_head_dollar_figures_differ_per_rung():
    """Each rung prices its OWN risk — the whole point of threading
    `portfolio_value` into the ladder instead of leaving one figure for the
    CIO/officer to scale by hand."""
    trim = _rung(1.5, portfolio_value=100_000.0)
    press = _rung(5.0, portfolio_value=100_000.0)
    assert "$90 at risk" in _rung_head(trim)
    assert "$300 at risk" in _rung_head(press)


def test_rung_head_omits_the_dollar_clause_when_drawdown_itself_is_none():
    """`dollar_risk_usd` is only ever meaningful nested inside the drawdown
    clause (it IS a scaling of `contribution_pts`) — an incoherent proposal
    that leaves `contribution_pts` None must leave the whole parenthetical,
    dollar clause included, unrendered."""
    rows = build_option_ladder(
        reference_size_pct=3.0, entry=100.0, stop=0.0, cap_pts=_CAP,
        portfolio_value=100_000.0,
    )
    r = next(r for r in rows if r.size_pct == 3.0)
    assert r.contribution_pts is None and r.dollar_risk_usd is None
    text = _rung_head(r)
    assert text == "**3.0%** of portfolio"
    assert "$" not in text
