"""DEF153 — the single-name position-size cap was dark on every market order.

Found while writing DEF147's `failure_patterns` entry, not from a report: DEF149
had just taught the *sector* cap (step 6b of the safety floor) that a MARKET order
carries no `limit_price` and must be priced off the mark instead. The *single-name*
cap two lines above it, step 6, was left on the old formula —
`(proposed.limit_price or 0.0) * quantity` — which is 0 for a market order, and the
`proposed_value > 0` guard then skipped the check entirely.

Measured before the fix, with no sector context so only step 6 could fire:

    limit   $9,000 of a $10,000 book (90%) -> blocked, "exceeds single-name cap 50.0%"
    market  $9,000 of a $10,000 book (90%) -> PASSED, no violations

Identical economics, opposite ruling, decided by an order-type field the cap has no
business reading. The app's trade ticket submits market orders, so this is the path
a user actually takes.

**The class, and why the fix is structural rather than a second `or`.** Two renderers
of one rule with neither a superset — the DEF098 shape. Fixing 6b without 6 was
possible only because each priced the proposal for itself; the proposal is now priced
ONCE, at step 6, and both caps read that number. They can no longer disagree about
what the trade is worth, so the next pricing change cannot reach one and miss the other.

And per CR040 the unevaluated case is no longer silent: a buy that cannot be priced
at all still passes both size caps — there is nothing to compare — but it now says so
in the log, which is the thing that was missing while DEF149 sat undetected for the
whole life of CR026.
"""

from __future__ import annotations

from unittest.mock import patch

from app.agents.safety_floor import check_mandate_compliance
from app.schemas.trade import OrderType, ProposedTrade, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.sector_allocation import OTHER

_PORTFOLIO = 10_000.0
_PRICE = 100.0

# CR101-BE1 made the single-name cap per-mandate (settable) rather than the fixed
# 50% absolute backstop. This suite is about the DEF153 pricing mechanism (one
# price feeds both concentration caps), not about a specific cap value, so the
# fixture mandate pins an explicit `single_name_cap_pct` override to 50.0 —
# preserving every percentage threshold this file already asserts.
_CAP = 50.0

_SECTORS = {"AAPL": "Technology"}


class _Map:
    def sector(self, ticker: str) -> str:
        return _SECTORS.get(str(ticker).upper(), OTHER)


def _check(
    *,
    quantity: float,
    order_type: OrderType,
    side: Side = Side.BUY,
    quotes: dict[str, float] | None = None,
    sector_map: object | None = None,
    portfolio_value: float = _PORTFOLIO,
    holdings: list | None = None,
):
    proposed = ProposedTrade(
        ticker="AAPL",
        side=side,
        quantity=quantity,
        order_type=order_type,
        limit_price=_PRICE if order_type == OrderType.LIMIT else None,
    )
    return check_mandate_compliance(
        proposed,
        portfolio_value=portfolio_value,
        current_drawdown_pct=0.0,
        mandate=hydrate_coach_mandate({"plan": "trader"}).model_copy(
            update={"single_name_cap_pct": _CAP}
        ),
        holdings=[] if holdings is None else holdings,
        quotes={"AAPL": _PRICE} if quotes is None else quotes,
        sector_map=sector_map,
        # CR129: the five BE2 limits are always-active now; this file is
        # about single-name-cap pricing, not these — harmless real context.
        last_loss_closed_at=None, trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )


def _size_violations(result) -> list[str]:
    return [v for v in result.violations if "single-name cap" in v]


# ── the defect ───────────────────────────────────────────────────────────────


def test_a_market_buy_over_the_cap_is_blocked():
    """90% of the book in one name. Pre-fix this returned passed=True."""
    result = _check(quantity=90.0, order_type=OrderType.MARKET)
    assert not result.passed, "a 90% market buy sailed past a 50% single-name cap"
    assert _size_violations(result) == [
        f"position size 90.0% exceeds single-name cap {_CAP}%"
    ]
    assert result.blocked_by == "concentration"


def test_the_two_order_types_agree_on_identical_economics():
    """The invariant, stated directly: the cap is about how much of the book one
    name takes. `order_type` says how the trade is routed, not how big it is, so
    it must not change the ruling — which is the whole defect in one assertion."""
    for quantity in (90.0, 60.0, 50.0, 49.0, 10.0):
        market = _check(quantity=quantity, order_type=OrderType.MARKET)
        limit = _check(quantity=quantity, order_type=OrderType.LIMIT)
        assert _size_violations(market) == _size_violations(limit), quantity
        assert market.passed == limit.passed, quantity


def test_a_market_buy_under_the_cap_still_passes():
    """The fix must not read as licence to block trades that were always fine."""
    result = _check(quantity=10.0, order_type=OrderType.MARKET)
    assert result.passed, result.violations


def test_the_boundary_sits_where_it_did_before():
    """Exactly at the cap passes; a cent over does not. Pinned so a later change
    to the pricing expression cannot quietly move the line."""
    at_cap = _PORTFOLIO * _CAP / 100 / _PRICE
    assert _check(quantity=at_cap, order_type=OrderType.MARKET).passed
    assert not _check(quantity=at_cap + 0.01, order_type=OrderType.MARKET).passed


class _Held:
    """A holding, duck-typed the way the floor consumes them."""

    def __init__(self, ticker: str, quantity: float, avg_cost: float = _PRICE):
        self.ticker, self.quantity, self.avg_cost = ticker, quantity, avg_cost


def test_a_sell_to_CLOSE_is_never_size_capped():
    """The cap is on taking a position, not on leaving one.

    **Narrowed by CR171 §6, and the narrowing is the point.** This assertion
    used to read "a sell is NEVER size capped" and passed `holdings=[]` — which,
    once a sell against a flat position could OPEN a short, meant it was
    asserting the new rule away while looking like a regression guard for the
    old one. DEF153's actual invariant is about leaving a position, so the test
    now holds one. The sell-to-OPEN half is asserted directly below.
    """
    result = _check(
        quantity=90.0, order_type=OrderType.MARKET, side=Side.SELL,
        holdings=[_Held("AAPL", 90.0)],
    )
    assert _size_violations(result) == []


def test_a_sell_to_OPEN_is_size_capped_like_any_other_position():
    """CR171 §6. A sell against a flat position is a SHORT — it takes exposure,
    it does not leave it, and the `is_buy` gate that was correct for four
    months would let an unbounded one past a mandate reporting itself as
    enforced."""
    result = _check(
        quantity=90.0, order_type=OrderType.MARKET, side=Side.SELL, holdings=[],
    )
    assert _size_violations(result) == [
        "position size 90.0% exceeds single-name cap 50.0%"
    ]


# ── the structural half: one price, both caps ────────────────────────────────


def test_both_concentration_caps_price_the_same_proposal_the_same_way():
    """DEF149 fixed the sector cap and left the single-name cap on the old
    formula, so the same market buy was over one cap and invisible to the other.
    A trade that breaches both must now be named by both."""
    result = _check(quantity=90.0, order_type=OrderType.MARKET, sector_map=_Map())
    assert not result.passed
    assert any("single-name cap" in v for v in result.violations), result.violations
    assert any("Technology" in v for v in result.violations), result.violations


def test_the_sector_cap_did_not_regress_when_the_pricing_moved():
    """The `unit_price` fallback moved out of step 6b and up to step 6. 6b now
    reads the hoisted value, so DEF149's own case has to still hold: a market buy
    small enough for the single-name cap but over the sector cap is still caught."""
    result = _check(quantity=45.0, order_type=OrderType.MARKET, sector_map=_Map())
    assert _size_violations(result) == [], "45% is under the 50% single-name cap"
    assert any("Technology" in v for v in result.violations), result.violations


# ── CR040: unevaluated is not compliant ──────────────────────────────────────


def test_a_buy_that_cannot_be_priced_at_all_is_logged_not_silently_skipped():
    """No limit price and no quote. There is nothing to measure, so both size
    caps abstain and the trade passes — but it must not do so in silence. DEF149
    was invisible for the entire life of CR026 for exactly want of this line."""
    with patch("app.agents.safety_floor.logger") as log:
        result = _check(quantity=90.0, order_type=OrderType.MARKET, quotes={})
    assert result.passed, "nothing to compare against — abstain, do not invent"
    assert log.warning.call_count == 1
    event, kwargs = log.warning.call_args[0][0], log.warning.call_args[1]
    assert event == "safety_floor_proposal_unpriced"
    assert kwargs["ticker"] == "AAPL"
    assert kwargs["quoted"] is False


def test_a_priced_buy_logs_nothing():
    """Vacuity guard on the test above — the warning must mark the unevaluated
    case specifically, not fire on every buy."""
    with patch("app.agents.safety_floor.logger") as log:
        _check(quantity=10.0, order_type=OrderType.MARKET)
    assert log.warning.call_count == 0
