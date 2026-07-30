"""DEF165 — DEF149's stale-`portfolio_value` guard silently re-adopts the exact
denominator DEF149 was filed to remove.

`sector_cap_breach` clamps `projected_total` to
`max(portfolio_value, sum(current.values()) + proposed_value)` so a stale/short
`portfolio_value` can never push the weight above 1.0. But taking that second branch
means the denominator is the pre-DEF149 invested-only total — on exactly the input
that made the original bug visible, the "fixed" code computes the old answer. The
existing DEF149 test (`test_a_short_portfolio_value_cannot_produce_a_weight_above_one`)
only pins `weight <= 1.0`, which the defective denominator also satisfies, so it
cannot tell the fallback from the fix.

Per CR040 (degrade loudly), taking the fallback branch must be visible: this file pins
a `logger.warning("sector_cap_stale_portfolio_value_fallback", ...)` call that fires
exactly when the fallback denominator is used, and stays silent when the supplied
`portfolio_value` is trusted as-is — the same pattern DEF153 established in
`safety_floor.py` for its own unpriced-proposal log line.
"""

from __future__ import annotations

from unittest.mock import patch

from app.services.sector_allocation import OTHER, sector_cap_breach

_SECTORS = {"AAPL": "Technology", "MSFT": "Technology", "JPM": "Financials"}


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


def test_stale_portfolio_value_below_holdings_logs_the_fallback():
    """portfolio_value=0.0 against $1,000 already held forces the fallback branch —
    this is the exact regime DEF149's clamp exists for."""
    holdings, quotes = [_H("AAPL", 10)], {"AAPL": 100.0}
    with patch("app.services.sector_allocation.logger") as log:
        b = _breach(holdings, quotes, "MSFT", 1_000.0, portfolio_value=0.0)
    assert b is not None
    assert b.projected_weight <= 1.0 + 1e-9
    assert log.warning.call_count == 1
    event, kwargs = log.warning.call_args[0][0], log.warning.call_args[1]
    assert event == "sector_cap_stale_portfolio_value_fallback"
    assert kwargs["ticker"] == "MSFT"
    assert kwargs["supplied_portfolio_value"] == 0.0
    assert kwargs["holdings_derived_total"] == 2_000.0  # $1,000 held + $1,000 proposed


def test_a_trustworthy_portfolio_value_never_logs_the_fallback():
    """Vacuity guard: a `portfolio_value` that already covers the post-trade holdings
    must not trip the warning — it fires on the stale case specifically."""
    with patch("app.services.sector_allocation.logger") as log:
        b = _breach([], {}, "AAPL", 200.0, portfolio_value=10_000.0)
    assert b is None
    assert log.warning.call_count == 0


def test_the_fallback_denominator_is_the_pre_def149_invested_only_total():
    """Pin the actual number, not just that a fallback occurred: with the fallback
    forced, the denominator is `sum(current holdings) + proposed_value` — the same
    invested-only quantity DEF149 removed — never the (stale) supplied total."""
    holdings, quotes = [_H("JPM", 10)], {"JPM": 100.0}  # $1,000 held, Financials
    with patch("app.services.sector_allocation.logger"):
        b = _breach(holdings, quotes, "MSFT", 1_000.0, portfolio_value=1.0)
    assert b is not None
    # weight = 1000 (Technology) / (1000 Financials + 1000 Technology) = 0.5, using
    # the holdings-derived total — NOT 1000 / 1.0, which the pre-fix clamp direction
    # would have produced instead.
    assert round(b.projected_weight, 4) == 0.5
