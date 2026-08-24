"""CR204 — the two greek-level option caps of §9.

Deferred out of CR172 by D5 for a dependency, not a priority: both need
full-portfolio greek aggregation, and CR172 §11's marks feed *fetched an
enriched chain carrying greeks and threw them away*. Three pieces here — the
greeks survive the fetch, `aggregate_book_greeks` combines them with equity
into one share-equivalent number, and `check_option_open` enforces both caps.

The guard worth naming is `test_an_incomplete_book_is_not_enforced_against`.
A portfolio delta summed over only the legs that HAD greeks is a number that
reads as the whole book and is not — CR040's case, landing on the figure a
risk cap is compared to. Reporting a pass off that subset would tell a user
their book is inside a limit nobody measured.
"""

from __future__ import annotations

import math
from datetime import date

from app.trading_math.greeks import (
    BookGreeks,
    GreekLeg,
    Greeks,
    aggregate_book_greeks,
)


def _g(delta=0.0, vega=0.0):
    return Greeks(delta=delta, gamma=0.0, theta_per_day=0.0,
                  vega_per_point=vega, rho_per_point=0.0)


def _leg(sym="AAPL260918C00195000", delta=0.0, vega=0.0, contracts=1.0, mult=100.0):
    return GreekLeg(occ_symbol=sym, greeks=_g(delta, vega),
                    contracts=contracts, multiplier=mult)


# ── The unit question: what does "combined" mean ─────────────────────────


def test_an_options_delta_is_scaled_by_multiplier_and_contracts():
    """An option's delta is per SHARE. Adding 0.60 to a share count would be
    adding a per-share figure to a position count."""
    book = aggregate_book_greeks([_leg(delta=0.60)])
    assert book.share_equivalent_delta == 60.0


def test_equity_contributes_one_delta_per_share_and_no_vega():
    book = aggregate_book_greeks([], equity_shares=250.0)
    assert book.share_equivalent_delta == 250.0
    assert book.vega_per_point == 0.0


def test_a_covered_call_nets_against_the_shares_behind_it():
    """The whole reason the two are combined in one number: a short call's
    delta genuinely offsets the stock it is written against."""
    book = aggregate_book_greeks(
        [_leg(delta=0.60, contracts=-1.0)], equity_shares=100.0,
    )
    assert book.share_equivalent_delta == 40.0


def test_a_short_leg_carries_its_sign_from_the_position():
    book = aggregate_book_greeks([_leg(delta=0.50, vega=8.0, contracts=-2.0)])
    assert book.share_equivalent_delta == -100.0
    assert book.vega_per_point == -1600.0


def test_vega_is_summed_not_averaged():
    """Summed answers "how much money moves on a one-point vol shift", which
    is what a dollar cap compares against. An average answers a different
    question entirely."""
    book = aggregate_book_greeks([_leg(vega=10.0), _leg(vega=20.0, sym="B")])
    assert book.vega_per_point == 3000.0


# ── The CR040 fence: never a silent subset ───────────────────────────────


def test_a_leg_with_no_greeks_is_named_not_skipped():
    book = aggregate_book_greeks([
        _leg(delta=0.6),
        GreekLeg(occ_symbol="NOGREEK", greeks=None, contracts=1.0, multiplier=100.0),
    ])
    assert book.unevaluable == ("NOGREEK",)
    assert book.is_complete is False


def test_a_complete_book_says_so():
    assert aggregate_book_greeks([_leg(delta=0.6)]).is_complete is True
    assert aggregate_book_greeks([], equity_shares=10.0).is_complete is True


def test_a_non_finite_greek_is_unevaluable_rather_than_poisoning_the_total():
    """A NaN summed in makes the whole book NaN, which reads as a broken
    screen rather than as one leg we could not price."""
    bad = GreekLeg(occ_symbol="NAN", greeks=_g(delta=float("nan")),
                   contracts=1.0, multiplier=100.0)
    book = aggregate_book_greeks([_leg(delta=0.6), bad])
    assert book.unevaluable == ("NAN",)
    assert math.isfinite(book.share_equivalent_delta)
    assert book.share_equivalent_delta == 60.0


# ── Enforcement in the floor ─────────────────────────────────────────────


def _mandate(base_mandate, **limits):
    """Built off the shared `base_mandate` fixture — Mandate has ten required
    fields and constructing a bare one is not possible."""
    return base_mandate.model_copy(update={
        "compliance": base_mandate.compliance.model_copy(
            update={"derivatives_allowed": True, "long_only": False},
        ),
        **limits,
    })


def _structure():
    from app.trading_math.option_strategy import StrategyLeg

    return [StrategyLeg(right="call", strike=195.0, quantity=1.0, premium=9.10,
                        multiplier=100.0, expiry=date(2026, 12, 18))]


def _check(m, book):
    from app.agents.safety_floor import check_option_open

    return check_option_open(
        _structure(), m, portfolio_value=100_000.0,
        existing_structures=(), today=date(2026, 8, 25), book_greeks=book,
    )


def test_a_book_inside_both_caps_passes(base_mandate):
    r = _check(_mandate(base_mandate, max_portfolio_delta=500.0, max_portfolio_vega=5_000.0),
               aggregate_book_greeks([_leg(delta=0.6, vega=10.0)]))
    assert r.passed, r.violations


def test_delta_over_the_cap_is_refused_in_share_equivalents(base_mandate):
    r = _check(_mandate(base_mandate, max_portfolio_delta=50.0),
               aggregate_book_greeks([_leg(delta=0.6)]))
    assert not r.passed
    assert r.blocked_by == "concentration"
    assert any("60" in v for v in r.violations)


def test_the_cap_is_on_the_absolute_value_so_a_short_book_is_limited_too(base_mandate):
    """A -600 delta book is as directionally exposed as a +600 one. A signed
    comparison would let an unlimited short position through."""
    r = _check(_mandate(base_mandate, max_portfolio_delta=50.0),
               aggregate_book_greeks([_leg(delta=0.6, contracts=-10.0)]))
    assert not r.passed, "a large SHORT delta must breach the same cap"


def test_short_vega_is_capped_too(base_mandate):
    r = _check(_mandate(base_mandate, max_portfolio_vega=100.0),
               aggregate_book_greeks([_leg(vega=12.0, contracts=-1.0)]))
    assert not r.passed


def test_an_incomplete_book_is_not_enforced_against(base_mandate):
    """THE guard. A total over the legs that HAD greeks is not the book's
    delta, and comparing it to a cap reports a pass the book never earned."""
    book = aggregate_book_greeks([
        _leg(delta=0.6),
        GreekLeg(occ_symbol="NOGREEK", greeks=None, contracts=99.0, multiplier=100.0),
    ])
    r = _check(_mandate(base_mandate, max_portfolio_delta=50.0), book)
    assert r.passed is True, "not blocked — we did not measure it"
    assert any("NOGREEK" in n for n in r.not_evaluated)
    assert not r.violations, "must not claim a breach it could not compute"


def test_absent_greeks_are_not_evaluated_never_a_silent_pass(base_mandate):
    r = _check(_mandate(base_mandate, max_portfolio_delta=1.0), None)
    assert r.passed is True
    assert any("not supplied" in n for n in r.not_evaluated)
    assert not r.violations


def test_no_cap_set_means_no_not_evaluated_noise(base_mandate):
    """A mandate with neither cap must not accumulate an unevaluated notice
    for a limit it never set."""
    r = _check(_mandate(base_mandate), None)
    assert r.passed
    assert not any("delta" in n for n in r.not_evaluated)


# ── Slice 1: the greeks survive the fetch ────────────────────────────────
#
# CR204's first acceptance criterion, and the dependency the whole CR was
# blocked on: `option_marks_for` pulled an enriched chain carrying computed
# greeks and kept only `mid`. Nothing above proves it stopped doing that — a
# mutation that reverts the fetch to discarding them passes every test in the
# rest of this file, because they all construct `GreekLeg`s by hand.

import datetime as _dt
from uuid import uuid4 as _uuid4

import pytest as _pytest

from app.schemas.trade import OptionLeg as _OptionLeg
from app.services.market_data import OptionChain as _OptionChain
from app.services.market_data import OptionQuote as _OptionQuote
from app.services.option_chain import EnrichedChain as _EnrichedChain
from app.services.option_chain import EnrichedOptionQuote as _EnrichedQuote
from app.services.sim_options import option_marks_for as _marks_for

_EXP = _dt.date(2026, 10, 7)
_NOW = _dt.datetime(2026, 8, 24, tzinfo=_dt.timezone.utc)


def _oleg(strike=195.0, right="call", occ="AAPL-C-195"):
    return _OptionLeg(
        id=_uuid4(), occ_symbol=occ, underlying="AAPL", right=right,
        strike=strike, expiry=_EXP, quantity=1.0, avg_premium=9.1,
        multiplier=100.0, collateral_posted=0.0, strategy_id=_uuid4(),
        strategy_name="long_call", opened_at=_NOW, days_to_expiry=44,
    )


def _equote(strike, mid, right, greeks):
    return _EnrichedQuote(
        quote=_OptionQuote(strike=strike, bid=None, ask=None, last=None,
                           volume=None, open_interest=None, implied_vol=None),
        right=right, mid=mid, state="tradeable", state_reason="",
        iv_used=0.3, iv_source="provider", greeks=greeks,
        greeks_reason=None if greeks else "no usable IV",
    )


@_pytest.fixture()
def _served(monkeypatch):
    store: dict = {}

    def fake(underlying, expiry):
        return store.get((underlying, expiry))

    import app.services.option_chain as oc
    monkeypatch.setattr(oc, "get_enriched_chain", fake)
    return store


def _chain(calls):
    return _EnrichedChain(
        chain=_OptionChain(underlying="AAPL", expiry=_EXP, calls=(), puts=(),
                           source="yfinance"),
        spot=195.42, spot_source="yfinance", rate=0.04, rate_source="fred",
        dividend_yield=0.0, t_years=0.12, calls=tuple(calls), puts=(),
    )


def test_the_marks_fetch_keeps_the_greeks_it_used_to_discard(_served):
    """CR204 slice 1. `option_marks_for` had the greeks in hand on every
    enriched quote and returned only the mid, which is why the two greek caps
    could not be built at all."""
    _served[("AAPL", _EXP)] = _chain([_equote(195.0, 9.5, "call", _g(0.55, 11.0))])
    out = _marks_for([_oleg()])
    assert out.marks["AAPL-C-195"] == 9.5
    assert out.greeks["AAPL-C-195"].delta == 0.55
    assert out.greeks["AAPL-C-195"].vega_per_point == 11.0
    assert out.ungreeked == ()


def test_a_leg_without_greeks_is_listed_never_given_a_zero(_served):
    """`0.0 delta` is a confident claim that a position has no directional
    exposure. An unpriceable leg has no entry and is named instead."""
    _served[("AAPL", _EXP)] = _chain([_equote(195.0, 9.5, "call", None)])
    out = _marks_for([_oleg()])
    assert out.marks["AAPL-C-195"] == 9.5, "a good mid survives a missing greek"
    assert "AAPL-C-195" not in out.greeks
    assert out.ungreeked == ("AAPL-C-195",)


def test_marks_and_greeks_fail_independently(_served):
    """A strike can carry usable greeks with no two-sided quote and vice
    versa; tying them together would drop one on the other's failure."""
    _served[("AAPL", _EXP)] = _chain([_equote(195.0, None, "call", _g(0.55, 11.0))])
    out = _marks_for([_oleg()])
    assert out.unmarked == ("AAPL-C-195",)
    assert out.greeks["AAPL-C-195"].delta == 0.55
    assert out.ungreeked == ()


def test_an_unavailable_chain_leaves_the_leg_both_unmarked_and_ungreeked(_served):
    out = _marks_for([_oleg()])
    assert out.unmarked == ("AAPL-C-195",)
    assert out.ungreeked == ("AAPL-C-195",)
