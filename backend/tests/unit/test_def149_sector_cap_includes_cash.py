"""DEF149 — the sector-concentration cap counted only invested value, not the portfolio.

Reported by Saiful from the app: *"Sector allocation is not taking into account cash.
So when 1 buy for the 1st time, I am immediately violating the allocation."*

Two defects live in this one code path, and they point in opposite directions.

**A — the denominator excluded cash, so every new user was locked out.** `sector_cap_breach`
divided by `invested + proposed`, so a first buy was *always* exactly 100% of "the
portfolio" however small it was against the user's $10,000 of cash, and was always
blocked. The second buy — in a *different* sector — read 50% and was blocked too. You
needed three sectors before any one fell under the 40% cap. The breach copy said "of
your portfolio" while the arithmetic used invested value alone, so the words and the
maths disagreed (the CR046 shown-equals-enforced rule).

The correct denominator is total portfolio value, and it is the **pre-trade** total: a
BUY spends cash to acquire shares, moving value between two buckets and leaving the sum
unchanged. Adding `proposed_value` to it double-counted the purchase.

**B — the cap silently never fired on a market order.** `proposed_value` was priced off
`limit_price` alone, which is `None` for a MARKET order, so it computed 0 and the check
returned `None` before evaluating anything. A hole in the safety floor in the opposite
direction from A, in the same three lines.

This is all deterministic Python — `check_mandate_compliance` is documented "No LLM" —
so neither defect is model behaviour.
"""

from __future__ import annotations

from app.services.sector_allocation import (
    CASH,
    NON_SECTOR_BUCKETS,
    OTHER,
    allocate_by_sector,
    sector_cap_breach,
)

_SECTORS = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "JPM": "Financials",
    "XOM": "Energy",
}


class _Map:
    def sector(self, ticker: str) -> str:
        return _SECTORS.get(str(ticker).upper(), OTHER)


class _H:
    def __init__(self, ticker: str, quantity: float) -> None:
        self.ticker, self.quantity = ticker, quantity


def _breach(holdings, quotes, ticker, value, portfolio_value, cap=0.40):
    return sector_cap_breach(
        holdings=holdings, quotes=quotes, proposed_ticker=ticker,
        proposed_value=value, sector_map=_Map(), cap=cap,
        portfolio_value=portfolio_value,
    )


# ── A. the reported defect ────────────────────────────────────────────────────


def test_a_first_ever_buy_is_not_a_breach():
    """$200 of AAPL against $10,000 of cash is 2% of the portfolio, not 100%."""
    assert _breach([], {}, "AAPL", 200.0, portfolio_value=10_000.0) is None


def test_a_second_buy_in_a_different_sector_is_not_a_breach():
    """The follow-on case: pre-fix this read Financials 50% and blocked."""
    holdings, quotes = [_H("AAPL", 1)], {"AAPL": 200.0}
    assert _breach(holdings, quotes, "JPM", 200.0, portfolio_value=10_000.0) is None


def test_a_genuine_concentration_still_blocks():
    """The cap must still bite — this is not a licence to remove enforcement.

    $5,000 of Technology on top of $1,000 already held, in a $10,000 portfolio,
    is 60% and must be refused against a 40% cap.
    """
    holdings, quotes = [_H("AAPL", 10)], {"AAPL": 100.0}
    b = _breach(holdings, quotes, "MSFT", 5_000.0, portfolio_value=10_000.0)
    assert b is not None
    assert b.sector == "Technology"
    assert round(b.projected_weight, 4) == 0.60
    assert "60.0%" in b.message() and "40%" in b.message()


def test_a_denominator_is_the_pre_trade_total_not_total_plus_purchase():
    """A BUY converts cash into shares; the portfolio total does not grow.

    Exactly at the cap: $4,000 of Technology in a $10,000 portfolio is 40.0% and
    must pass. Had `proposed_value` been added to the denominator the weight would
    read 4000/14000 = 28.6% and the cap would sit in the wrong place entirely.
    """
    b = _breach([], {}, "AAPL", 4_000.0, portfolio_value=10_000.0)
    assert b is None
    over = _breach([], {}, "AAPL", 4_001.0, portfolio_value=10_000.0)
    assert over is not None, "one dollar past the cap must breach"


def test_a_short_portfolio_value_cannot_produce_a_weight_above_one():
    """Guard a stale/short portfolio_value rather than trusting it blindly."""
    holdings, quotes = [_H("AAPL", 10)], {"AAPL": 100.0}
    b = _breach(holdings, quotes, "MSFT", 1_000.0, portfolio_value=0.0)
    assert b is not None
    assert b.projected_weight <= 1.0 + 1e-9


def test_a_unknown_sector_still_never_breaches():
    """The DEF059 inversion guard is untouched by this fix."""
    assert _breach([], {}, "ZZZZ", 9_999.0, portfolio_value=10_000.0) is None


# ── B. the market-order hole ──────────────────────────────────────────────────


def test_b_a_market_order_is_priced_and_therefore_checked():
    """Pre-fix, a market buy priced at 0 and the cap never evaluated at all.

    Exercised through the floor, because the limit_price/quote fallback lives there.
    """
    from app.agents.safety_floor import check_mandate_compliance
    from app.schemas.trade import OrderType, ProposedTrade, Side
    from app.services.coach_engine import hydrate_coach_mandate

    proposed = ProposedTrade(
        ticker="AAPL", side=Side.BUY, quantity=90.0,
        order_type=OrderType.MARKET, limit_price=None,
    )
    result = check_mandate_compliance(
        proposed,
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        mandate=hydrate_coach_mandate({"plan": "trader"}),
        holdings=[],
        quotes={"AAPL": 100.0},   # $9,000 of a $10,000 portfolio = 90%
        sector_map=_Map(),
    )
    assert not result.passed, "a 90% market buy sailed past the sector cap"
    assert any("Technology" in v for v in result.violations)


def test_b_a_small_market_order_still_passes():
    from app.agents.safety_floor import check_mandate_compliance
    from app.schemas.trade import OrderType, ProposedTrade, Side
    from app.services.coach_engine import hydrate_coach_mandate

    proposed = ProposedTrade(
        ticker="AAPL", side=Side.BUY, quantity=2.0,
        order_type=OrderType.MARKET, limit_price=None,
    )
    result = check_mandate_compliance(
        proposed,
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        mandate=hydrate_coach_mandate({"plan": "trader"}),
        holdings=[], quotes={"AAPL": 100.0}, sector_map=_Map(),
    )
    assert result.passed, result.violations


# ── the display half — shown must equal enforced ──────────────────────────────


def test_allocation_includes_cash_as_its_own_bucket():
    """The donut re-normalises whatever it is given, so weights that merely summed
    to <1 would be silently redrawn as invested-only. Cash must be a real slice."""
    holdings, quotes = [_H("AAPL", 1)], {"AAPL": 200.0}
    w = allocate_by_sector(holdings, quotes, cash=9_800.0, sector_of=_Map().sector)
    assert round(w["Technology"], 4) == 0.02
    assert round(w[CASH], 4) == 0.98
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_allocation_matches_what_the_cap_enforces():
    """CR046: the number drawn and the number enforced come from one basis."""
    holdings, quotes = [_H("AAPL", 1)], {"AAPL": 200.0}
    w = allocate_by_sector(holdings, quotes, cash=9_800.0, sector_of=_Map().sector)
    assert w["Technology"] <= 0.40
    assert _breach(holdings, quotes, "MSFT", 0.01, portfolio_value=10_000.0) is None


def test_cash_is_never_a_concentration_breach():
    assert CASH in NON_SECTOR_BUCKETS and OTHER in NON_SECTOR_BUCKETS


def test_allocation_without_cash_is_unchanged():
    """The `cash=0.0` default keeps a genuinely cash-free caller on old behaviour."""
    holdings, quotes = [_H("AAPL", 1), _H("JPM", 1)], {"AAPL": 300.0, "JPM": 100.0}
    w = allocate_by_sector(holdings, quotes, sector_of=_Map().sector)
    assert round(w["Technology"], 4) == 0.75
    assert round(w["Financials"], 4) == 0.25
    assert CASH not in w
