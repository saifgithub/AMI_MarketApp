"""CR172 §9 (D5) — the four book-level option caps.

**The property the whole file turns on: these are caps on the BOOK, not on a
structure.** A cap applied one structure at a time is not a cap — a user
refused a single 5%-of-NAV position simply opens five of them, and every one
passes on its own. `test_five_structures_that_each_pass_alone_are_refused_together`
is that stated as a test, and it is the one that would catch a future
refactor quietly dropping `existing_structures`.

Two design choices are pinned here because both are the kind that look like
details and are not:

* **`premium_at_risk` nets WITHIN a structure and never across.** A credit
  spread already open must not bankroll a new long position — that would let a
  user defeat a theta cap by writing options, which is the opposite of what the
  cap is for. But a debit spread's premium at risk genuinely IS its net debit,
  not its long leg's gross premium, or the cap would refuse structures that
  reduce risk.
* **An unknown NAV does not pass.** `portfolio_value=None` sends the three
  percentage caps to `not_evaluated`, never to a silent pass: a cap measured
  against an unknown denominator is not a cap that passed — the rule
  `check_exercise_outcome` already states one function down. It does not BLOCK
  either, per DEF169; the DEF169 exception in this floor is the bounded-loss
  question, not these.

`min_days_to_expiry` reads the SOONEST-expiring leg, because that is the leg
that stops existing first. Judging a calendar spread by its far leg would wave
through a structure half of which expires tomorrow.
"""

from __future__ import annotations

import datetime

import pytest

from app.agents.safety_floor import check_option_open
from app.services.coach_engine import hydrate_coach_mandate
from app.trading_math.option_strategy import StrategyLeg, book_exposure

TODAY = datetime.date(2026, 8, 24)
FAR = "2027-03-19"
NAV = 10_000.0


def _mandate(**limits):
    """Derivatives ON and long_only OFF — otherwise the gate or D4 answers
    first and every cap test below would pass for the wrong reason."""
    return hydrate_coach_mandate({
        "plan": "trader",
        "single_name_cap_pct": 100.0,
        "compliance": {
            "long_only": False, "halal": False, "derivatives_allowed": True,
        },
        **limits,
    })


def _leg(right, strike, qty, premium, expiry=FAR):
    return StrategyLeg(
        right=right, strike=strike, quantity=qty, premium=premium,
        multiplier=100.0, expiry=expiry,
    )


def _check(legs, mandate, *, nav=NAV, existing=(), today=TODAY):
    return check_option_open(
        legs, mandate, portfolio_value=nav,
        existing_structures=existing, today=today,
    )


LONG_CALL = [_leg("call", 195.0, 1.0, 9.10)]          # 910 premium, 19_500 notional
SHORT_PUT = [_leg("put", 180.0, -1.0, 4.50)]          # 18_000 assignment
DEBIT_SPREAD = [_leg("call", 195.0, 1.0, 9.10), _leg("call", 205.0, -1.0, 4.20)]
CREDIT_SPREAD = [_leg("put", 180.0, -1.0, 3.00), _leg("put", 170.0, 1.0, 1.00)]


# ── premium at risk ─────────────────────────────────────────────────────────

def test_premium_cap_refuses_a_structure_over_the_line():
    r = _check(LONG_CALL, _mandate(max_option_premium_pct=5.0))
    assert not r.passed
    assert any("9.1%" in v and "5.0%" in v for v in r.violations), r.violations


def test_premium_cap_permits_one_under_the_line():
    assert _check(LONG_CALL, _mandate(max_option_premium_pct=15.0)).passed


def test_a_debit_spread_is_measured_by_its_NET_debit():
    """490, not the long leg's 910 — a spread reduces risk and the cap must
    see that, or it refuses the safer structure and permits the naked one."""
    r = _check(DEBIT_SPREAD, _mandate(max_option_premium_pct=6.0))
    assert r.passed, r.violations
    assert book_exposure(DEBIT_SPREAD).premium_at_risk == 490.0


def test_an_open_credit_spread_cannot_bankroll_a_new_long():
    """THE netting rule. Premium RECEIVED is not premium at risk, so an open
    credit structure must not offset a new debit.

    The numbers are chosen so the two models DISAGREE, which an earlier version
    of this test failed to do: with a $700 credit already on the book, a
    net-across-the-book model puts premium at risk at $210 (2.1% — under a 5%
    cap, permitted) while the correct per-structure model puts it at $910
    (9.1% — refused). A credit spread whose credit is too small to swing the
    verdict proves nothing about which model is running.
    """
    m = _mandate(max_option_premium_pct=5.0)
    big_credit = [_leg("put", 180.0, -1.0, 8.00), _leg("put", 170.0, 1.0, 1.00)]
    assert book_exposure(big_credit).premium_at_risk == 0.0
    # Netted across the book this would be 910 - 700 = 210, i.e. 2.1% — under
    # the cap. Per structure it is 910, i.e. 9.1% — over it.
    r = _check(LONG_CALL, m, existing=[big_credit])
    assert not r.passed, "a credit elsewhere must not fund a new long position"
    assert any("9.1%" in v for v in r.violations), r.violations


def test_five_structures_that_each_pass_alone_are_refused_together():
    """A cap applied one structure at a time is not a cap.

    Each long call is 9.1% of NAV against a 50% cap — every one passes alone.
    Five of them is 45.5%; a sixth is 54.6% and must be refused.
    """
    m = _mandate(max_option_premium_pct=50.0)
    assert _check(LONG_CALL, m).passed
    five = [list(LONG_CALL) for _ in range(5)]
    assert not _check(LONG_CALL, m, existing=five).passed


# ── gross notional ──────────────────────────────────────────────────────────

def test_notional_cap_sees_the_contract_not_the_premium():
    """$910 of premium controls $19,500 of stock. A cap that looked at premium
    would call this a 9% position; it is 195% of the account."""
    r = _check(LONG_CALL, _mandate(max_option_notional_pct=100.0))
    assert not r.passed
    assert any("195.0%" in v for v in r.violations), r.violations


def test_notional_is_GROSS_so_a_spreads_legs_do_not_cancel():
    """Both legs can be exercised or assigned; netting them would understate
    what the user is standing behind."""
    assert book_exposure(DEBIT_SPREAD).gross_notional == 195_00.0 + 205_00.0


# ── assignment exposure ─────────────────────────────────────────────────────

def test_assignment_cap_counts_a_short_put():
    r = _check(SHORT_PUT, _mandate(max_assignment_exposure_pct=25.0))
    assert not r.passed
    assert any("180.0%" in v for v in r.violations), r.violations


def test_a_LONG_put_creates_no_assignment_exposure():
    """The holder chooses. Only a short leg can be assigned."""
    assert book_exposure([_leg("put", 180.0, 1.0, 4.50)]).assignment_exposure == 0.0


def test_a_short_CALL_is_not_counted_as_cash_assignment():
    """Not an omission: an uncovered short call is refused outright by D3, and
    a covered one needs no cash because the shares are already posted."""
    assert book_exposure([_leg("call", 195.0, -1.0, 9.10)]).assignment_exposure == 0.0


# ── days to expiry ──────────────────────────────────────────────────────────

def test_zero_dte_is_refused_under_a_min_days_limit():
    r = _check(
        [_leg("call", 195.0, 1.0, 9.10, expiry=TODAY.isoformat())],
        _mandate(min_days_to_expiry=7),
    )
    assert not r.passed
    assert any("0 day(s)" in v for v in r.violations), r.violations


def test_the_soonest_leg_is_what_min_days_reads():
    """Tested on the pure function, not through the floor, and that is the
    honest place for it.

    A structure in this codebase carries ONE expiry — `StrategyLeg.expiry`
    says so and `strategy_metrics` refuses a mixed-expiry structure before any
    cap runs, so a calendar spread cannot reach `min_days_to_expiry` through
    `check_option_open` at all. The soonest-leg rule is therefore
    defence-in-depth rather than live behaviour, and asserting it through the
    floor would have been asserting on a path that cannot execute — a green
    test proving nothing, which is worse than no test.
    """
    from app.trading_math.option_strategy import min_days_to_expiry

    near = (TODAY + datetime.timedelta(days=2)).isoformat()
    legs = [_leg("call", 195.0, 1.0, 9.10, expiry=FAR),
            _leg("call", 195.0, -1.0, 4.20, expiry=near)]
    assert min_days_to_expiry(legs, TODAY) == 2


def test_an_unreadable_expiry_yields_None_not_zero():
    """None, so a caller cannot mistake "unknown" for "expires today" — the
    reading that would turn a missing date into an urgent refusal."""
    from app.trading_math.option_strategy import min_days_to_expiry

    assert min_days_to_expiry([_leg("call", 195.0, 1.0, 9.10, expiry="")], TODAY) is None
    assert min_days_to_expiry([_leg("call", 195.0, 1.0, 9.10, expiry="garbage")], TODAY) is None


def test_a_mixed_expiry_structure_is_refused_before_the_caps_run():
    """Pins the upstream behaviour the two tests above depend on, so a change
    to `strategy_metrics` that started permitting mixed expiries would surface
    here rather than silently making the soonest-leg rule live and untested."""
    near = (TODAY + datetime.timedelta(days=2)).isoformat()
    r = _check(
        [_leg("call", 195.0, 1.0, 9.10, expiry=FAR),
         _leg("call", 195.0, -1.0, 4.20, expiry=near)],
        _mandate(min_days_to_expiry=30),
    )
    assert not r.passed
    assert any("could not be costed" in n for n in r.not_evaluated), r.not_evaluated


# ── the denominator ─────────────────────────────────────────────────────────

def test_an_unknown_nav_is_not_evaluated_never_a_silent_pass():
    r = _check(LONG_CALL, _mandate(max_option_premium_pct=1.0), nav=None)
    assert any("portfolio value" in n for n in r.not_evaluated), r.not_evaluated
    # DEF169: unevaluable does not BLOCK — the exception in this floor is the
    # bounded-loss question, not a cap.
    assert not any("premium at risk" in v for v in r.violations)


def test_an_unknown_nav_is_silent_when_no_cap_is_set():
    """No cap, nothing to fail to measure — the note must not appear on every
    portfolio in the app."""
    r = _check(LONG_CALL, _mandate(), nav=None)
    assert not r.not_evaluated, r.not_evaluated


def test_no_caps_set_means_no_refusal():
    assert _check(LONG_CALL, _mandate()).passed
    assert _check(SHORT_PUT, _mandate()).passed


# ── ordering ────────────────────────────────────────────────────────────────

def test_the_derivatives_gate_still_answers_before_any_cap():
    """A mandate that permits no derivatives should be told that, not handed a
    lecture about a premium cap it was never going to reach."""
    m = hydrate_coach_mandate({
        "plan": "trader",
        "compliance": {"derivatives_allowed": False},
        "max_option_premium_pct": 0.1,
    })
    r = _check(LONG_CALL, m)
    assert not r.passed
    assert not any("premium at risk" in v for v in r.violations), r.violations
