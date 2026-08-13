"""CR145 Tier D — the quarterly statements, and the TTL cache the tier was gated on.

Tier D's row makes the cache a precondition, not a nicety: *"a TTL fundamentals
cache ships in this tier or the tier does not ship."* These tests pin what that
cache must guarantee, and — more importantly — the three places where getting
it slightly wrong would produce a confident wrong number instead of an absence.

The measurements behind the fixtures, taken live before any of this was
written (2026-08-13, yfinance 1.3.0):

  - `.quarterly_income_stmt` returns 5–7 quarterly columns for NVDA, GRAB,
    KTOS, SNOA and NBIS; all five carry Gross Profit / Operating Income /
    Net Income / Total Revenue.
  - `.quarterly_cashflow` carries `Repurchase Of Capital Stock` for NVDA, GRAB
    and SNOA — and **NOT** for NBIS or KTOS. An absent row is the common case,
    not the edge case.
  - An unknown ticker yields an EMPTY frame rather than raising.
  - Each call costs 0.27–0.99s, which is what the cache is for.
"""

from __future__ import annotations

import sys
import types

import pytest

from app.services import fundamentals
from app.services.fundamentals import (
    _margin_bps,
    buyback_line,
    clear_statement_cache,
    fetch_statement_facts,
    margin_trend_line,
)

_PERIODS = ["2026-04-30", "2026-01-31", "2025-10-31", "2025-07-31", "2025-04-30"]


def _frame(rows: dict[str, list[float]], periods=None):
    import pandas as pd

    periods = periods or _PERIODS
    return pd.DataFrame(
        list(rows.values()), index=list(rows.keys()), columns=periods
    )


def _income(gross=None, operating=None, net=None, revenue=None, periods=None):
    rows = {"Total Revenue": revenue or [1000.0] * 5}
    if gross is not None:
        rows["Gross Profit"] = gross
    if operating is not None:
        rows["Operating Income"] = operating
    if net is not None:
        rows["Net Income"] = net
    return _frame(rows, periods)


def _install(monkeypatch, income, cashflow, *, calls=None):
    def _ticker(sym):
        if calls is not None:
            calls.append(sym)
        return types.SimpleNamespace(
            quarterly_income_stmt=income, quarterly_cashflow=cashflow
        )

    monkeypatch.setitem(
        sys.modules, "yfinance", types.SimpleNamespace(Ticker=_ticker, __version__="1.3.0")
    )


@pytest.fixture(autouse=True)
def _clean_cache():
    clear_statement_cache()
    yield
    clear_statement_cache()


# ── The cache ────────────────────────────────────────────────────────────


def test_a_second_fetch_of_the_same_ticker_does_not_hit_the_provider(monkeypatch):
    calls: list[str] = []
    _install(monkeypatch, _income(gross=[600.0] * 4 + [500.0]), _frame({}), calls=calls)

    first = fetch_statement_facts("NVDA")
    second = fetch_statement_facts("NVDA")

    assert first == second
    assert calls == ["NVDA"], f"expected one provider call, got {calls}"


def test_the_cache_is_keyed_per_ticker_and_normalises_the_symbol(monkeypatch):
    calls: list[str] = []
    _install(monkeypatch, _income(gross=[600.0] * 4 + [500.0]), _frame({}), calls=calls)

    fetch_statement_facts("nvda")
    fetch_statement_facts("  NVDA  ")
    fetch_statement_facts("GRAB")

    assert calls == ["NVDA", "GRAB"], (
        f"case and whitespace must not open a second cache slot: {calls}"
    )


def test_a_none_result_is_cached_too(monkeypatch):
    """A ticker with no parseable filings is a STABLE fact.

    Re-asking every convene would make the failure case the expensive one,
    which is how a degraded provider turns into a latency incident.
    """
    calls: list[str] = []
    _install(monkeypatch, _frame({}), _frame({}), calls=calls)

    assert fetch_statement_facts("ZZZZQ") is None
    assert fetch_statement_facts("ZZZZQ") is None
    assert calls == ["ZZZZQ"]


def test_a_provider_explosion_returns_none_rather_than_propagating(monkeypatch):
    """A statements outage must degrade the two new lines to CR104 UNAVAILABLE,
    never take the whole fact sheet down with it."""

    def _boom(sym):
        raise RuntimeError("yfinance is having a day")

    monkeypatch.setitem(
        sys.modules, "yfinance", types.SimpleNamespace(Ticker=_boom, __version__="1.3.0")
    )
    assert fetch_statement_facts("NVDA") is None


def test_clearing_the_cache_lets_a_new_filing_through(monkeypatch):
    _install(monkeypatch, _income(gross=[600.0] * 4 + [500.0]), _frame({}))
    before = fetch_statement_facts("NVDA")
    assert before["gross_margin_trend_bps"] == 1000

    _install(monkeypatch, _income(gross=[700.0] * 4 + [500.0]), _frame({}))
    assert fetch_statement_facts("NVDA") == before, "still inside the TTL"

    clear_statement_cache()
    assert fetch_statement_facts("NVDA")["gross_margin_trend_bps"] == 2000


# ── Margin trend ─────────────────────────────────────────────────────────


def test_the_trend_is_year_over_year_not_quarter_on_quarter(monkeypatch):
    """The prior quarter and the year-ago quarter carry different margins; the
    output must reflect the YEAR-ago one.

    Quarter-on-quarter would measure the season rather than the business for
    any seasonal name, and it would be indistinguishable in the rendered line.
    """
    _install(
        monkeypatch,
        _income(gross=[600.0, 590.0, 580.0, 570.0, 500.0]),
        _frame({}),
    )
    out = fetch_statement_facts("NVDA")
    assert out["gross_margin_trend_bps"] == 1000  # 60% vs 50%, not 60% vs 59%
    assert out["margin_trend_basis"] == "2026-04-30 vs 2025-04-30"


def test_fewer_than_five_quarters_yields_no_trend_at_all(monkeypatch):
    """A four-column frame has no year-ago quarter. Nothing is rendered rather
    than a quarter-on-quarter delta wearing a YoY label."""
    periods = _PERIODS[:4]
    _install(
        monkeypatch,
        _income(gross=[600.0, 590.0, 580.0, 500.0], revenue=[1000.0] * 4, periods=periods),
        _frame({}, periods=periods),
    )
    assert fetch_statement_facts("NVDA") is None


def test_a_missing_row_drops_only_its_own_margin(monkeypatch):
    _install(
        monkeypatch,
        _income(gross=[600.0] * 4 + [500.0], net=[300.0] * 4 + [250.0]),
        _frame({}),
    )
    out = fetch_statement_facts("NVDA")
    assert out["gross_margin_trend_bps"] == 1000
    assert out["net_margin_trend_bps"] == 500
    assert "operating_margin_trend_bps" not in out
    assert "margin_trend_basis" in out


def test_zero_revenue_is_not_divided_by(monkeypatch):
    _install(
        monkeypatch,
        _income(gross=[600.0] * 4 + [500.0], revenue=[1000.0, 1000.0, 1000.0, 1000.0, 0.0]),
        _frame({}),
    )
    assert fetch_statement_facts("NVDA") is None


def test_a_nan_in_either_quarter_drops_that_margin(monkeypatch):
    """yfinance's missing-value sentinel is NaN, not an absent cell — DEF052's
    F1 lesson, which `_num` already applies to `.info`."""
    _install(
        monkeypatch,
        _income(gross=[float("nan"), 600.0, 590.0, 580.0, 500.0]),
        _frame({}),
    )
    assert fetch_statement_facts("NVDA") is None


def test_a_contracting_margin_is_reported_as_negative(monkeypatch):
    _install(monkeypatch, _income(gross=[400.0] * 4 + [500.0]), _frame({}))
    assert fetch_statement_facts("NVDA")["gross_margin_trend_bps"] == -1000


def test_margin_bps_needs_both_quarters_present():
    assert _margin_bps([600.0, None, None, None, None], [1000.0] * 5, 0, 4) is None
    assert _margin_bps(None, [1000.0] * 5, 0, 4) is None
    assert _margin_bps([600.0] * 5, None, 0, 4) is None


# ── Buybacks ─────────────────────────────────────────────────────────────


def test_a_company_with_no_repurchase_row_reports_no_buyback_not_zero(monkeypatch):
    """Measured: NBIS and KTOS carry no `Repurchase Of Capital Stock` row while
    SNOA, a microcap, does.

    "Did not report a repurchase line" and "repurchased $0" are different
    claims and only the second is ours to make — DEF053's absent-beats-
    meaningless rule, and the one that matters most here, because a rendered
    `Buybacks: $0M` is an assertion about capital allocation that the filing
    does not support.
    """
    _install(monkeypatch, _income(gross=[600.0] * 4 + [500.0]), _frame({}))
    out = fetch_statement_facts("KTOS")
    assert "buyback_ttm" not in out


def test_a_reported_zero_repurchase_is_reported_as_zero(monkeypatch):
    """The other half of the same rule: GRAB reports 0.0 in its latest quarter,
    and that IS a fact about capital allocation."""
    _install(
        monkeypatch,
        _income(gross=[600.0] * 4 + [500.0]),
        _frame({"Repurchase Of Capital Stock": [0.0, 0.0, 0.0, 0.0, 0.0]}),
    )
    assert fetch_statement_facts("GRAB")["buyback_ttm"] == 0


def test_the_buyback_is_the_trailing_four_quarters_not_the_latest(monkeypatch):
    _install(
        monkeypatch,
        _income(gross=[600.0] * 4 + [500.0]),
        _frame({"Repurchase Of Capital Stock": [-1e9, -2e9, -3e9, -1.654e9, -9e9]}),
    )
    out = fetch_statement_facts("NVDA")
    assert out["buyback_ttm"] == 7654, "the fifth quarter must not be counted"


def test_a_short_repurchase_history_yields_no_ttm(monkeypatch):
    """Three quarters is not a trailing twelve months. Summing what exists
    would label a partial year as TTM."""
    _install(
        monkeypatch,
        _income(gross=[600.0] * 4 + [500.0]),
        _frame({"Repurchase Of Capital Stock": [-1e9, -2e9, -3e9, None, None]}),
    )
    assert "buyback_ttm" not in (fetch_statement_facts("NVDA") or {})


def test_the_buyback_yield_needs_a_live_market_cap(monkeypatch):
    """The percentage is computed in `fetch_live_fundamentals`, where market cap
    lives. Without a denominator there is no yield — computing one against a
    missing market cap is the fabrication the CR104 gating exists to stop."""
    info = {"currentPrice": 100.0, "trailingPE": 20.0}  # no marketCap
    _install(
        monkeypatch,
        _income(gross=[600.0] * 4 + [500.0]),
        _frame({"Repurchase Of Capital Stock": [-1e9] * 5}),
    )
    monkeypatch.setitem(
        sys.modules,
        "yfinance",
        types.SimpleNamespace(
            __version__="1.3.0",
            Ticker=lambda t: types.SimpleNamespace(
                info=info,
                quarterly_income_stmt=_income(gross=[600.0] * 4 + [500.0]),
                quarterly_cashflow=_frame(
                    {"Repurchase Of Capital Stock": [-1e9] * 5}
                ),
            ),
        ),
    )
    out = fundamentals.fetch_live_fundamentals("NVDA")
    assert out["buyback_ttm"] == 4000
    assert "buyback_yield" not in out


# ── The rendered lines ───────────────────────────────────────────────────


def test_the_trend_line_names_its_own_basis(monkeypatch):
    """The levels beside it are TTM and this delta is quarterly. Two bases for
    one word, silently adjacent, is the defect `_reference_price_line` had to
    reconcile for price — so the comparison states its own quarters."""
    line = margin_trend_line(1234, 2345, 3456, "2026-04-30 vs 2025-04-30")
    assert "quarter ending 2026-04-30" in line
    assert "against the quarter ending 2025-04-30" in line
    assert "YoY" in line


def test_the_trend_line_carries_no_thousands_separator():
    """DEF242: `Entry: $1,507.00` parsed as `1.0`. Every prose agent's output is
    walked by regexes that have been bitten by an in-number comma twice."""
    assert "1,234" not in margin_trend_line(1234, None, None, "a vs b")
    assert "+1234bps" in margin_trend_line(1234, None, None, "a vs b")


def test_the_trend_line_is_absent_without_a_basis():
    assert margin_trend_line(1234, 2345, 3456, None) is None
    assert margin_trend_line(None, None, None, "2026-04-30 vs 2025-04-30") is None


def test_the_buyback_line_carries_its_denominator():
    line = buyback_line(45303, 0.8)
    assert "$45,303M repurchased" in line
    assert "0.8% of market cap" in line


def test_the_buyback_line_survives_a_missing_yield():
    line = buyback_line(45303, None)
    assert "$45,303M repurchased" in line
    assert "market cap" not in line


def test_the_buyback_line_is_absent_with_no_figure():
    assert buyback_line(None, 0.8) is None
