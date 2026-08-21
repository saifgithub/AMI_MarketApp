"""CR172 §8 / §14 D3-D4 acceptance — the options half of the safety floor.

The two that matter most:

  * `test_d3_*` — **the naked call is refused, and the refusal explains
    itself.** D3 was a genuine fork (Reg-T margin at ~5:1 against forbidding
    the structure outright) and Saiful ruled on 2026-08-20 that the "no
    leverage, ever" lock stands. A refusal that only says "not permitted"
    teaches nothing, so the sentence is asserted, not just the boolean.
  * `test_exercise_outcome_*` — **allow and flag never becomes block.** The
    one way this control can fail dangerously is by growing a refusal: the
    contract was already exercised, so a block here would leave a position
    the user cannot see and the floor thinks it stopped.

`check_option_open` is the floor for the OPEN path that lands in slice 3 —
the floor ships first, deliberately, so the path is built against a control
that already exists rather than the other way round.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.agents.safety_floor import (
    DERIVATIVES_NOT_PERMITTED,
    NAKED_CALL_REFUSAL,
    check_exercise_outcome,
    check_option_open,
)
from app.schemas.trade import Holding
from app.services.coach_engine import hydrate_coach_mandate
from app.trading_math.option_strategy import StrategyLeg

EXPIRY = "2026-01-16"
FAR_EXPIRY = "2026-03-20"


def _mandate(
    *,
    long_only: bool = False,
    halal: bool = False,
    derivatives_allowed: bool = True,
    **over,
):
    """Derivatives ON by default here, and that is deliberate.

    Every test in this file asks about the STRUCTURE rules — D3's uncovered
    call, D4's long-only reading, the halal advisory — and each of those
    questions only exists downstream of the §9 gate. A fixture that left the
    gate shut would make all of them pass for the wrong reason: refused, but
    never by the rule under test. The gate has its own tests below, which are
    the ones that assert the default is OFF.
    """
    base = {
        "plan": "trader",
        "single_name_cap_pct": 100.0,
        "compliance": {
            "long_only": long_only,
            "halal": halal,
            "derivatives_allowed": derivatives_allowed,
        },
    }
    base.update(over)
    return hydrate_coach_mandate(base)


def _leg(right, strike, quantity, premium=3.0, expiry=EXPIRY):
    return StrategyLeg(
        right=right, strike=strike, quantity=quantity,
        premium=premium, multiplier=100.0, expiry=expiry,
    )


def _holding(ticker="AAPL", quantity=100.0, avg_cost=100.0):
    return Holding(
        ticker=ticker, quantity=quantity, avg_cost=avg_cost,
        opened_at=datetime.now(timezone.utc),
    )


# ── D3: naked calls are forbidden ────────────────────────────────────────────


def test_d3_a_naked_short_call_is_refused_with_the_reason_spelled_out():
    result = check_option_open([_leg("call", 100.0, -1)], _mandate())

    assert not result.passed
    assert result.blocked_by == "compliance"
    assert NAKED_CALL_REFUSAL in result.violations
    assert "no ceiling" in NAKED_CALL_REFUSAL
    assert "leverage" in NAKED_CALL_REFUSAL


def test_d3_the_same_short_call_is_permitted_once_the_shares_cover_it():
    result = check_option_open(
        [_leg("call", 100.0, -1)], _mandate(), shares_held=100.0,
    )

    assert result.passed
    assert result.violations == []


def test_d3_a_short_call_covered_by_a_long_call_is_a_spread_not_a_naked_call():
    """The refusal is a verdict on the STRUCTURE, not on any leg's sign. A
    bear call spread has a bounded loss (the width) and must not be caught by
    a rule aimed at the unbounded one."""
    result = check_option_open(
        [_leg("call", 100.0, -1), _leg("call", 110.0, 1, premium=1.0)], _mandate(),
    )

    assert result.passed


def test_d3_forbids_the_call_and_not_the_put():
    """A naked put's loss is bounded at the strike and it is collateralised in
    full. Forbidding it too would have deleted cash-secured puts, which are
    half the assignment curriculum."""
    result = check_option_open([_leg("put", 100.0, -1)], _mandate())

    assert result.passed


# ── D4: long_only means "no sell-to-open", not "no bearish position" ─────────


def test_d4_long_only_permits_a_long_put():
    result = check_option_open([_leg("put", 100.0, 1)], _mandate(long_only=True))

    assert result.passed, (
        "a long put is bounded-loss bearish exposure with no borrow and no "
        "assignment risk — refusing it while permitting a short is backwards"
    )


def test_d4_long_only_refuses_a_sell_to_open():
    result = check_option_open([_leg("put", 100.0, -1)], _mandate(long_only=True))

    assert not result.passed
    assert result.blocked_by == "long_only"
    assert any("long-only" in v for v in result.violations)


def test_d4_long_only_permits_a_debit_spread():
    result = check_option_open(
        [_leg("call", 100.0, 1), _leg("call", 110.0, -1, premium=1.0)],
        _mandate(long_only=True),
    )

    assert not result.passed, (
        "the short leg of a debit spread is still a sell-to-open; D4 draws the "
        "line at the leg, not at the net cost"
    )
    assert result.blocked_by == "long_only"


# ── Halal: inform, never block (CR171's ruling, extended 2026-08-20) ─────────


def test_halal_informs_on_sell_to_open_and_lets_the_trade_through():
    result = check_option_open([_leg("put", 100.0, -1)], _mandate(halal=True))

    assert result.passed
    assert result.violations == []
    assert len(result.advisories) == 1
    assert "gharar" in result.advisories[0]
    assert "not blocking" in result.advisories[0]


def test_halal_says_nothing_about_a_long_structure():
    result = check_option_open([_leg("call", 100.0, 1)], _mandate(halal=True))

    assert result.passed
    assert result.advisories == []


def test_halal_and_long_only_are_independent():
    """One refuses, the other informs, and both can be true at once — the
    CR171 shape exactly."""
    result = check_option_open(
        [_leg("put", 100.0, -1)], _mandate(halal=True, long_only=True),
    )

    assert not result.passed
    assert result.blocked_by == "long_only"
    assert result.advisories != []


# ── A structure we cannot cost is refused, not permitted ────────────────────


def test_a_structure_that_cannot_be_costed_is_refused_and_says_which_check_died():
    result = check_option_open(
        [_leg("call", 100.0, -1, expiry=EXPIRY), _leg("call", 110.0, 1, expiry=FAR_EXPIRY)],
        _mandate(),
    )

    assert not result.passed
    assert result.not_evaluated != [], (
        "the failed check must be named — a refusal with no `not_evaluated` "
        "entry is indistinguishable from a refusal on the merits"
    )
    assert "uncovered-call check" in result.not_evaluated[0]


def test_an_empty_structure_is_refused():
    assert not check_option_open([], _mandate()).passed


# ── Allow and flag ───────────────────────────────────────────────────────────


def test_exercise_outcome_flags_a_breach_and_still_passes():
    result = check_exercise_outcome(
        "AAPL",
        [_holding(quantity=100.0, avg_cost=100.0)],
        {"AAPL": 130.0},
        20_000.0,
        0.0,
        _mandate(single_name_cap_pct=10.0),
    )

    assert result.passed is True
    assert result.blocked_by is None
    assert result.violations == []
    assert any("single-name cap" in a for a in result.advisories)
    assert any("did not block it" in a for a in result.advisories)


def test_exercise_outcome_is_silent_when_the_position_is_within_the_mandate():
    result = check_exercise_outcome(
        "AAPL",
        [_holding(quantity=10.0, avg_cost=100.0)],
        {"AAPL": 130.0},
        100_000.0,
        0.0,
        _mandate(),
    )

    assert result.passed is True
    assert result.advisories == []


def test_exercise_outcome_only_reports_the_ticker_that_settled():
    result = check_exercise_outcome(
        "AAPL",
        [_holding("AAPL", 500.0), _holding("MSFT", 500.0, 100.0)],
        {"AAPL": 100.0, "MSFT": 100.0},
        60_000.0,
        0.0,
        _mandate(single_name_cap_pct=10.0),
    )

    assert result.advisories != []
    assert all("MSFT" not in a for a in result.advisories)


def test_exercise_outcome_records_not_evaluated_rather_than_a_clean_bill():
    result = check_exercise_outcome(
        "AAPL", [_holding()], {}, 0.0, 0.0, _mandate(),
    )

    assert result.passed is True
    assert result.advisories == []
    assert result.not_evaluated != [], (
        "a cap measured against a zero denominator is not a cap that passed"
    )


# ── §9 — the gate itself (CR172, AT:R73) ────────────────────────────────────


def test_derivatives_are_refused_unless_the_mandate_permits_them():
    """The default is OFF, so a mandate written before the field refuses."""
    result = check_option_open(
        [_leg("call", 100.0, 1.0)], _mandate(derivatives_allowed=False),
    )
    assert result.passed is False
    assert DERIVATIVES_NOT_PERMITTED in result.violations
    assert result.blocked_by == "compliance"


def test_a_mandate_that_never_heard_of_the_field_refuses():
    """A stored snapshot predating CR172 has no such key — it must not open."""
    stored = hydrate_coach_mandate({
        "plan": "trader",
        "single_name_cap_pct": 100.0,
        "compliance": {"long_only": False, "halal": False},
    })
    assert stored.compliance.derivatives_allowed is False
    assert check_option_open([_leg("call", 100.0, 1.0)], stored).passed is False


def test_the_gate_speaks_before_the_structure_rules_do():
    """A naked call under a no-derivatives mandate is refused for the mandate.

    Ordering is what the user reads. Leading with the uncovered-call lecture
    would tell someone who cannot open ANY option to go find a covered
    structure instead — advice that cannot be acted on.
    """
    result = check_option_open(
        [_leg("call", 100.0, -1.0)], _mandate(derivatives_allowed=False),
    )
    assert result.violations == [DERIVATIVES_NOT_PERMITTED]
    assert NAKED_CALL_REFUSAL not in result.violations


def test_permitting_derivatives_does_not_permit_a_naked_call():
    """The gate opens the door; D3 still stands behind it."""
    result = check_option_open(
        [_leg("call", 100.0, -1.0)], _mandate(derivatives_allowed=True),
    )
    assert result.passed is False
    assert NAKED_CALL_REFUSAL in result.violations


def test_the_refusal_tells_the_user_what_to_change():
    assert "mandate" in DERIVATIVES_NOT_PERMITTED
    assert "AMI" in DERIVATIVES_NOT_PERMITTED


def test_the_overlay_states_the_gate_in_both_directions():
    """An agent never told about options proposes one the floor then refuses.

    That is CR150 Tier C's failure a different instrument along: advice AMI
    gave, refused by AMI, read by the user as a malfunction. So the overlay
    says it either way and never by omission.
    """
    from app.agents.overlay_generator import _compliance_block

    off = _compliance_block(_mandate(derivatives_allowed=False).compliance)
    on = _compliance_block(_mandate(derivatives_allowed=True).compliance)
    assert "NO DERIVATIVES" in off
    assert "shares only" in off
    assert "Derivatives permitted" in on
    assert "NO DERIVATIVES" not in on
