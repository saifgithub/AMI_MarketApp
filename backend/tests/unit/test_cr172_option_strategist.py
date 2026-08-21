"""CR172 §10 step 1 — what the candidate generator must and must not do.

The generator sits between a chain and a card the user says yes to, so the
tests that matter are the ones about what it REFUSES to put on that card:

  * `test_marked_not_hidden_*` — a candidate the mandate forbids is still
    generated, carrying the floor's own refusal text. §10 wants the PM able
    to say "the natural structure here is forbidden, so instead…"; filtering
    the violators out deletes the teaching moment AND leaves the user
    believing the menu was the whole menu.
  * `test_no_invented_strike_*` — with no target, the spread is not built.
    The rival behaviour (anchor the short leg somewhere reasonable) puts a
    strike on the card that no analysis produced.
  * `test_greeks_*` — one leg without greeks makes the NET greeks None. A
    partial sum reads as the position's exposure and is not (DEF169's shape,
    where 0.0 is a confident claim).
  * `test_size_*` — an unbounded or share-covered loss sizes to ONE contract
    with the reason recorded. Dividing a budget by a loss that has no
    ceiling invents the ceiling.

Every figure asserted here is recomputed from `strategy_metrics`/`bs_greeks`
in the test itself where it is cheap to do so, rather than pinned as a
literal: a literal drifts silently when the math module moves.
"""

from __future__ import annotations

import datetime

from app.services import option_strategist as st
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import OptionChain, OptionQuote
from app.services.option_chain import enrich_chain
from app.trading_math.option_strategy import strategy_metrics

_EXPIRY = datetime.date(2027, 3, 19)
_NOW = datetime.datetime(2027, 1, 15, 15, 0, tzinfo=datetime.UTC)
_SPOT = 100.0


def _mandate(*, long_only: bool = False, halal: bool = False):
    return hydrate_coach_mandate({
        "plan": "trader",
        "single_name_cap_pct": 100.0,
        "compliance": {"long_only": long_only, "halal": halal},
    })


def _q(strike, bid, ask, iv=0.30):
    return OptionQuote(
        strike=strike, bid=bid, ask=ask, last=None, volume=50,
        open_interest=500, implied_vol=iv,
    )


def _chain(calls=None, puts=None, *, rate: float | None = 0.04, spot=_SPOT):
    """A liquid, symmetric chain around $100 unless a test overrides a side."""
    if calls is None:
        calls = tuple(
            _q(k, round(max(0.5, 105 - k) + 4.0, 2), round(max(0.5, 105 - k) + 4.4, 2))
            for k in (90.0, 95.0, 100.0, 105.0, 110.0)
        )
    if puts is None:
        puts = tuple(
            _q(k, round(max(0.5, k - 95) + 4.0, 2), round(max(0.5, k - 95) + 4.4, 2))
            for k in (90.0, 95.0, 100.0, 105.0, 110.0)
        )
    raw = OptionChain(
        underlying="AAPL", expiry=_EXPIRY, calls=calls, puts=puts, source="yfinance",
    )
    return enrich_chain(raw, spot, rate, "test", 0.0, _NOW, "yfinance")


def _build(**over):
    kwargs = {
        "underlying": "AAPL",
        "direction": "bullish",
        "mandate": _mandate(),
        "risk_budget_usd": 2_000.0,
        "target": 110.0,
        "stop": 90.0,
        "now": _NOW,
    }
    chain = over.pop("chain", None) or _chain()
    kwargs.update(over)
    return st.build_candidates(chain, **kwargs)


def _named(result, name):
    return next((c for c in result.candidates if c.strategy_name == name), None)


# ── the menu is generated at all ────────────────────────────────────────────

def test_bullish_offers_the_three_bullish_structures():
    result = _build()
    names = {c.strategy_name for c in result.candidates}
    assert names == {"long_call", "bull_call_spread", "cash_secured_put"}
    assert result.underlying == "AAPL"
    assert result.expiry == _EXPIRY.isoformat()


def test_bearish_offers_the_bearish_structures_and_no_bullish_one():
    # A bearish target sits BELOW the money — the same 110 the bullish case
    # uses would be a target the view does not hold, and the module refuses
    # to build a spread onto it rather than flipping the strike itself.
    result = _build(direction="bearish", target=90.0)
    names = {c.strategy_name for c in result.candidates}
    assert names == {"long_put", "bear_put_spread"}
    assert "long_call" not in names


def test_every_candidate_carries_its_expiry_and_days_to_expiry():
    result = _build()
    for c in result.candidates:
        assert c.expiry == _EXPIRY.isoformat()
        assert c.days_to_expiry == (_EXPIRY - _NOW.date()).days
        assert all(leg.expiry == c.expiry for leg in c.legs)


def test_shares_held_unlocks_the_covered_structures():
    result = _build(shares_held=300.0)
    names = {c.strategy_name for c in result.candidates}
    assert "covered_call" in names
    assert "protective_put" in names


def test_no_shares_means_no_covered_call_offered():
    result = _build(shares_held=99.0)
    assert _named(result, "covered_call") is None
    assert _named(result, "protective_put") is None


# ── marked, never hidden ────────────────────────────────────────────────────

def test_marked_not_hidden_long_only_still_sees_the_short_put():
    """A long-only mandate forbids selling to open — and still gets the card."""
    result = _build(mandate=_mandate(long_only=True))
    csp = _named(result, "cash_secured_put")
    assert csp is not None, "the forbidden structure must still be offered, marked"
    assert csp.mandate_violations, "…and it must carry the floor's refusal"
    assert any("long-only" in v for v in csp.mandate_violations)


def test_marked_not_hidden_permitted_structures_carry_no_violation():
    result = _build(mandate=_mandate(long_only=True))
    call = _named(result, "long_call")
    assert call is not None and call.mandate_violations == ()


def test_the_violation_text_is_the_floors_own():
    """One renderer of each rule (DEF098) — not a second copy in this module."""
    from app.agents.safety_floor import check_option_open

    result = _build(mandate=_mandate(long_only=True))
    csp = _named(result, "cash_secured_put")
    floor = check_option_open(csp.legs, _mandate(long_only=True), shares_held=0.0)
    assert list(csp.mandate_violations) == list(floor.violations)


def test_halal_advisory_travels_on_the_candidate():
    result = _build(mandate=_mandate(halal=True))
    csp = _named(result, "cash_secured_put")
    assert csp is not None
    assert any("gharar" in a for a in csp.advisories)


# ── nothing is invented ─────────────────────────────────────────────────────

def test_no_invented_strike_without_a_target_there_is_no_spread():
    result = _build(target=None)
    assert _named(result, "bull_call_spread") is None
    assert any("target" in r for r in result.not_evaluated)


def test_no_invented_strike_without_a_stop_there_is_no_cash_secured_put():
    result = _build(stop=None)
    assert _named(result, "cash_secured_put") is None


def test_untradeable_strikes_are_never_used():
    """A zero-bid strike is a real quote meaning worthless — not a price."""
    calls = (
        _q(100.0, 0.0, 0.05),      # worthless
        _q(105.0, None, None),     # unusable
        _q(110.0, 6.0, 6.4),       # the only tradeable call
    )
    result = _build(chain=_chain(calls=calls))
    call = _named(result, "long_call")
    assert call is not None
    assert [leg.strike for leg in call.legs] == [110.0]


def test_a_chain_with_no_tradeable_strike_offers_nothing_and_says_why():
    dead = tuple(_q(k, 0.0, 0.05) for k in (95.0, 100.0, 105.0))
    result = _build(chain=_chain(calls=dead, puts=dead))
    assert result.candidates == ()
    assert any("transactable" in r for r in result.not_evaluated)


def test_an_unknown_direction_builds_nothing():
    result = _build(direction="sideways-ish")
    assert result.candidates == ()
    assert any("unknown direction" in r for r in result.not_evaluated)


# ── the figures ─────────────────────────────────────────────────────────────

def test_every_figure_matches_strategy_metrics_on_the_same_legs():
    result = _build(shares_held=300.0)
    for c in result.candidates:
        assert c.metrics == strategy_metrics(c.legs, shares_held=300.0)


def test_premium_is_the_mid_not_the_bid_or_the_ask():
    chain = _chain()
    result = _build(chain=chain)
    call = _named(result, "long_call")
    atm = next(q for q in chain.calls if q.quote.strike == 100.0)
    assert call.legs[0].premium == atm.mid


def test_the_spread_is_long_the_money_short_the_target():
    result = _build()
    spread = _named(result, "bull_call_spread")
    longs = [leg for leg in spread.legs if leg.quantity > 0]
    shorts = [leg for leg in spread.legs if leg.quantity < 0]
    assert len(longs) == len(shorts) == 1
    assert longs[0].strike == 100.0 and shorts[0].strike == 110.0


# ── sizing ──────────────────────────────────────────────────────────────────

def test_size_is_the_budget_divided_by_the_one_contract_loss():
    result = _build(risk_budget_usd=2_000.0)
    call = _named(result, "long_call")
    unit = strategy_metrics(
        tuple(leg._replace(quantity=leg.quantity / call.contracts) for leg in call.legs)
    )
    assert call.contracts == int(2_000.0 // unit.max_loss)
    assert call.contracts >= 1


def test_size_never_falls_below_one_contract():
    result = _build(risk_budget_usd=1.0)
    assert all(c.contracts == 1 for c in result.candidates)


def test_size_of_a_share_covered_structure_is_one_and_says_why():
    result = _build(shares_held=1_000.0, risk_budget_usd=100_000.0)
    cc = _named(result, "covered_call")
    assert cc is not None and cc.contracts == 1
    assert any("bounded by shares" in r for r in cc.not_evaluated)


def test_size_with_no_budget_is_one_and_says_why():
    result = _build(risk_budget_usd=0.0)
    call = _named(result, "long_call")
    assert call.contracts == 1
    assert any("risk budget" in r for r in call.not_evaluated)


# ── greeks ──────────────────────────────────────────────────────────────────

def test_greeks_are_the_net_across_legs_scaled_by_contracts():
    from app.trading_math.option_strategy import combine_greeks

    chain = _chain()
    result = _build(chain=chain)
    spread = _named(result, "bull_call_spread")
    by_strike = {q.quote.strike: q for q in chain.calls}
    expected = combine_greeks([
        (leg.quantity, 100.0, by_strike[leg.strike].greeks) for leg in spread.legs
    ])
    assert spread.net_greeks == expected


def test_greeks_are_none_when_one_leg_could_not_price_them():
    """A partial sum would read as the position's exposure. It is not."""
    result = _build(chain=_chain(rate=None))
    call = _named(result, "long_call")
    assert call.net_greeks is None
    assert call.greeks_not_evaluated, "and the reason travels"


# ── ordering + volatility awareness ─────────────────────────────────────────

def test_order_is_stable_so_structure_ids_are_stable():
    first = [c.strategy_name for c in _build().candidates]
    second = [c.strategy_name for c in _build().candidates]
    assert first == second


def test_without_a_realised_vol_the_order_is_structural_and_says_so():
    result = _build()
    assert result.volatility_aware is False
    assert any("volatility" in r for r in result.not_evaluated)


def test_rich_implied_vol_puts_the_income_structure_first():
    result = _build(realised_vol=0.10)   # chain solves to ~30% IV
    assert result.volatility_aware is True
    assert result.candidates[0].strategy_name == "cash_secured_put"


def test_cheap_implied_vol_puts_the_debit_structures_first():
    result = _build(realised_vol=0.90)
    assert result.volatility_aware is True
    assert result.candidates[0].strategy_name != "cash_secured_put"
