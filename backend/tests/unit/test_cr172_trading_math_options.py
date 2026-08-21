"""CR172 slice 1 — the options pricing family (M14–M17), pinned.

Three disciplines run through these tests:

* **Reference-free self-consistency where possible.** Greeks are checked
  against central finite differences of `bs_price` itself, and IV against a
  price→sigma→price round trip — a transcription error in a hand-copied
  reference number cannot green a broken formula that way.
* **The M14 parity self-guard** (C − P = S·e^(−qT) − K·e^(−rT)) is pinned
  across a grid: it is sigma-free, so it catches sign/discounting mistakes
  independently of any curve.
* **§6's collateral table is pinned row by row** — CSP posts the FULL
  strike (premium not netted, per the table), credit spreads post
  width − credit, the iron condor the wider wing, the naked call has NO
  number at all (None + flag, per the D3 ruling), and the share-cover
  allocation covers the HIGHEST-strike short call so the paired remainder
  can only over-secure.
"""

from __future__ import annotations

import math

from app.trading_math import (
    Greeks,
    StrategyLeg,
    bs_greeks,
    bs_price,
    combine_greeks,
    implied_vol,
    net_cost,
    payoff_at_expiry,
    per_contract,
    put_call_parity_gap,
    strategy_metrics,
)

_EXP = "2026-09-18"


def _leg(right, strike, qty, premium, mult=100.0, expiry=_EXP):
    return StrategyLeg(right, strike, qty, premium, mult, expiry)


# ── M14: Black-Scholes price ─────────────────────────────────────────────


def test_m14_classic_reference_values():
    # The textbook S=100, K=100, T=1, r=5%, sigma=20% pair.
    assert abs(bs_price("call", 100, 100, 1.0, 0.05, 0.2) - 10.4506) < 1e-3
    assert abs(bs_price("put", 100, 100, 1.0, 0.05, 0.2) - 5.5735) < 1e-3


def test_m14_put_call_parity_holds_across_a_grid():
    for spot in (60.0, 100.0, 155.0):
        for sigma in (0.1, 0.35, 0.9):
            for q in (0.0, 0.03):
                c = bs_price("call", spot, 100, 0.4, 0.04, sigma, q)
                p = bs_price("put", spot, 100, 0.4, 0.04, sigma, q)
                gap = put_call_parity_gap(c, p, spot, 100, 0.4, 0.04, q)
                assert gap is not None and abs(gap) < 1e-9


def test_m14_dividend_yield_lowers_the_call_and_raises_the_put():
    c0 = bs_price("call", 100, 100, 1.0, 0.05, 0.2, 0.0)
    c3 = bs_price("call", 100, 100, 1.0, 0.05, 0.2, 0.03)
    p0 = bs_price("put", 100, 100, 1.0, 0.05, 0.2, 0.0)
    p3 = bs_price("put", 100, 100, 1.0, 0.05, 0.2, 0.03)
    assert c3 < c0 and p3 > p0


def test_m14_invalid_inputs_are_none_never_a_guess():
    assert bs_price("call", 100, 100, 0.0, 0.05, 0.2) is None   # at expiry: M10's job
    assert bs_price("call", 100, 100, 1.0, 0.05, 0.0) is None   # sigma=0: a forward
    assert bs_price("call", -1, 100, 1.0, 0.05, 0.2) is None
    assert bs_price("call", 100, 0, 1.0, 0.05, 0.2) is None
    assert bs_price("straddle", 100, 100, 1.0, 0.05, 0.2) is None
    assert bs_price("call", float("nan"), 100, 1.0, 0.05, 0.2) is None


# ── M15: greeks vs finite differences of the pricer itself ───────────────


def _fd(kind, spot, strike, t, r, sigma, q, bump_arg, h):
    """Central finite difference of bs_price along one argument."""
    args = {"spot": spot, "strike": strike, "t": t, "r": r, "sigma": sigma, "q": q}
    up, dn = dict(args), dict(args)
    up[bump_arg] += h
    dn[bump_arg] -= h
    f_up = bs_price(kind, up["spot"], strike, up["t"], up["r"], up["sigma"], up["q"])
    f_dn = bs_price(kind, dn["spot"], strike, dn["t"], dn["r"], dn["sigma"], dn["q"])
    return (f_up - f_dn) / (2 * h)


def test_m15_greeks_match_finite_differences():
    for kind in ("call", "put"):
        spot, strike, t, r, sigma, q = 105.0, 100.0, 0.6, 0.04, 0.3, 0.02
        g = bs_greeks(kind, spot, strike, t, r, sigma, q)
        assert abs(g.delta - _fd(kind, spot, strike, t, r, sigma, q, "spot", 0.001)) < 1e-5
        d_up = bs_greeks(kind, spot + 0.001, strike, t, r, sigma, q).delta
        d_dn = bs_greeks(kind, spot - 0.001, strike, t, r, sigma, q).delta
        assert abs(g.gamma - (d_up - d_dn) / 0.002) < 1e-5
        assert abs(g.vega_per_point * 100 - _fd(kind, spot, strike, t, r, sigma, q, "sigma", 1e-5)) < 1e-4
        assert abs(g.rho_per_point * 100 - _fd(kind, spot, strike, t, r, sigma, q, "r", 1e-5)) < 1e-4
        # Theta: -dPrice/dT annualised, then per CALENDAR day.
        annual = -_fd(kind, spot, strike, t, r, sigma, q, "t", 1e-5)
        assert abs(g.theta_per_day - annual / 365.0) < 1e-6


def test_m15_theta_is_per_calendar_day_not_per_trading_day():
    # The /252 convention would be ~45% larger in magnitude; pin the ratio.
    g = bs_greeks("call", 100, 100, 1.0, 0.05, 0.2)
    annual = -_fd("call", 100.0, 100.0, 1.0, 0.05, 0.2, 0.0, "t", 1e-5)
    assert abs(g.theta_per_day * 365.0 - annual) < 1e-4
    assert abs(g.theta_per_day * 252.0 - annual) > 1e-2


def test_m15_put_delta_is_negative_and_call_positive():
    assert bs_greeks("put", 100, 100, 0.5, 0.03, 0.25).delta < 0
    assert bs_greeks("call", 100, 100, 0.5, 0.03, 0.25).delta > 0


def test_m15_per_contract_scales_by_the_multiplier():
    g = bs_greeks("call", 100, 100, 0.5, 0.03, 0.25)
    scaled = per_contract(g, 100.0)
    assert scaled.delta == g.delta * 100.0
    assert scaled.vega_per_point == g.vega_per_point * 100.0
    assert per_contract(g, 0.0) is None


# ── M16: implied vol ─────────────────────────────────────────────────────


def test_m16_round_trips_sigma_through_price():
    for kind in ("call", "put"):
        for sigma in (0.08, 0.2, 0.55, 1.4):
            for strike in (80.0, 100.0, 120.0):
                price = bs_price(kind, 100, strike, 0.35, 0.04, sigma)
                solved = implied_vol(kind, price, 100, strike, 0.35, 0.04)
                assert solved is not None, (kind, sigma, strike)
                # The contract: the solved sigma REPRICES to the input.
                repriced = bs_price(kind, 100, strike, 0.35, 0.04, solved)
                assert abs(repriced - price) < 1e-6, (kind, sigma, strike)
                # Sigma itself is recovered wherever the quote carries vol
                # information. Deep ITM at low vol the time value collapses
                # below any real tick (2e-7 here) and NO solver can pin
                # sigma from such a price — pseudo-precision would be the
                # bug, so the sigma assertion applies above one cent.
                disc_strike = strike * math.exp(-0.04 * 0.35)
                lower_bound = max(
                    0.0,
                    (100 - disc_strike) if kind == "call" else (disc_strike - 100),
                )
                if price - lower_bound > 0.01:
                    assert abs(solved - sigma) < 1e-4, (kind, sigma, strike)


def test_m16_price_outside_no_arb_band_is_none():
    # Above the spot no call price can exist; below intrinsic none either.
    assert implied_vol("call", 101.0, 100, 100, 0.5, 0.05) is None
    deep_itm_floor = 100 - 60 * math.exp(-0.05 * 0.5)
    assert implied_vol("call", deep_itm_floor - 0.01, 100, 60, 0.5, 0.05) is None


def test_m16_invalid_inputs_are_none():
    assert implied_vol("call", 0.0, 100, 100, 0.5, 0.05) is None
    assert implied_vol("call", -3.0, 100, 100, 0.5, 0.05) is None
    assert implied_vol("call", 5.0, 100, 100, 0.0, 0.05) is None
    assert implied_vol("banana", 5.0, 100, 100, 0.5, 0.05) is None


# ── M17: strategy metrics, §6 pinned row by row ──────────────────────────


def test_m17_bull_call_spread():
    m = strategy_metrics([
        _leg("call", 100, 1, 5.0), _leg("call", 105, -1, 3.0),
    ])
    assert m.net_cost == 200.0
    assert m.max_loss == 200.0 and not m.unbounded_loss
    assert m.max_gain == 300.0 and not m.unbounded_gain
    assert m.break_evens == (102.0,)
    assert m.collateral_required == 0.0  # §6: the debit already paid IS the risk


def test_m17_credit_call_spread_posts_width_minus_credit():
    m = strategy_metrics([
        _leg("call", 100, -1, 5.0), _leg("call", 105, 1, 3.0),
    ])
    assert m.net_cost == -200.0
    assert m.collateral_required == 300.0  # 5 wide x100 − 200 credit
    assert m.max_loss == 300.0


def test_m17_cash_secured_put_posts_the_full_strike():
    m = strategy_metrics([_leg("put", 95, -1, 2.0)])
    assert m.net_cost == -200.0
    assert m.collateral_required == 9500.0  # §6 literal: premium NOT netted
    assert m.max_loss == 9300.0             # loss at S=0 nets the premium
    assert m.break_evens == (93.0,)


def test_m17_naked_call_is_flagged_with_no_collateral_number():
    m = strategy_metrics([_leg("call", 105, -1, 3.0)])
    assert m.has_uncovered_short_call is True
    assert m.collateral_required is None  # no cash number contains unbounded
    assert m.unbounded_loss is True and m.max_loss is None
    assert m.max_gain == 300.0


def test_m17_covered_call_locks_shares_not_cash():
    m = strategy_metrics([_leg("call", 105, -1, 3.0)], shares_held=100)
    assert m.has_uncovered_short_call is False
    assert m.covered_by_shares is True and m.shares_locked == 100
    assert m.collateral_required == 0.0
    assert m.unbounded_loss is False
    assert m.max_loss is None  # stock-basis dependent: explicit, never a guess


def test_m17_partial_share_cover_is_still_uncovered():
    m = strategy_metrics([_leg("call", 105, -2, 3.0)], shares_held=100)
    assert m.has_uncovered_short_call is True
    assert m.collateral_required is None


def test_m17_iron_condor_posts_the_wider_wing_less_credit():
    m = strategy_metrics([
        _leg("put", 85, 1, 0.7), _leg("put", 95, -1, 2.0),
        _leg("call", 105, -1, 1.0), _leg("call", 110, 1, 0.4),
    ])
    assert m.net_cost == -190.0
    assert m.collateral_required == 810.0  # wider wing 10 x100 − 190 credit
    assert m.max_loss == 810.0
    assert m.break_evens == (93.1, 106.9)


def test_m17_share_cover_goes_to_the_highest_strike_short_call():
    # Two short calls at different strikes, one long call, 100 shares: the
    # shares cover the 110 (least liable), leaving the 100/105 credit pair
    # to post against — the conservative allocation, pinned.
    m = strategy_metrics([
        _leg("call", 100, -1, 5.0),
        _leg("call", 110, -1, 2.0),
        _leg("call", 105, 1, 3.0),
    ], shares_held=100)
    assert m.covered_by_shares is True and m.shares_locked == 100
    # Paired remainder: short 100 / long 105 → liability 500; credit 400.
    assert m.collateral_required == 100.0


def test_m17_long_straddle_has_two_break_evens_and_unbounded_gain():
    m = strategy_metrics([
        _leg("call", 100, 1, 4.0), _leg("put", 100, 1, 3.5),
    ])
    assert m.net_cost == 750.0
    assert m.max_loss == 750.0
    assert m.unbounded_gain is True and m.max_gain is None
    assert m.break_evens == (92.5, 107.5)
    assert m.collateral_required == 0.0


def test_m17_mixed_expiries_refuse_rather_than_pretend():
    m = strategy_metrics([
        _leg("call", 100, 1, 5.0, expiry="2026-09-18"),
        _leg("call", 100, -1, 3.0, expiry="2026-10-16"),
    ])
    assert m is None


def test_m17_invalid_legs_are_none():
    assert strategy_metrics([]) is None
    assert strategy_metrics([_leg("call", 0, 1, 5.0)]) is None
    assert strategy_metrics([_leg("call", 100, 0, 5.0)]) is None
    assert strategy_metrics([_leg("swap", 100, 1, 5.0)]) is None
    assert strategy_metrics([_leg("call", 100, 1, -1.0)]) is None
    assert strategy_metrics([StrategyLeg("call", 100, 1, 5.0, 100.0, "")]) is None


def test_m17_payoff_and_net_cost_basics():
    legs = [_leg("call", 100, 1, 5.0)]
    assert payoff_at_expiry(legs, 100.0) == -500.0
    assert payoff_at_expiry(legs, 120.0) == 1500.0
    assert net_cost(legs) == 500.0
    assert payoff_at_expiry(legs, -1.0) is None


def test_m17_multiplier_is_honoured_not_assumed_100():
    # An adjusted contract (deliverable 150) — the §3 reason it is a column.
    m = strategy_metrics([_leg("put", 95, -1, 2.0, mult=150.0)])
    assert m.collateral_required == 95 * 150.0
    assert m.net_cost == -300.0


def test_m17_combine_greeks_sums_signed_exposure():
    g = Greeks(delta=0.5, gamma=0.02, theta_per_day=-0.01,
               vega_per_point=0.3, rho_per_point=0.4)
    net = combine_greeks([(1, 100.0, g), (-2, 100.0, g)])
    assert abs(net.delta - (-50.0)) < 1e-12
    assert abs(net.vega_per_point - (-30.0)) < 1e-12
    assert combine_greeks([]) is None
