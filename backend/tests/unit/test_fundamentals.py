"""Tests for the live-fundamentals helper (shared by Room + 1-on-1)."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.services import fundamentals
from app.services.fundamentals import (
    build_live_data_block,
    extract_tickers,
    fetch_live_fundamentals,
)


# ── extract_tickers ──────────────────────────────────────────────────────


def test_extract_ticker_simple():
    assert extract_tickers("Should I buy AAPL?") == ["AAPL"]


def test_extract_ticker_with_dollar_prefix():
    assert extract_tickers("$NVDA is on fire") == ["NVDA"]


def test_extract_ticker_skips_common_english():
    # "I", "A", "THE" are blocklisted; only NVDA survives.
    assert extract_tickers("I think A buy on THE NVDA dip") == ["NVDA"]


def test_extract_ticker_dedupes_in_order():
    assert extract_tickers("AAPL vs MSFT — AAPL wins") == ["AAPL", "MSFT"]


def test_extract_ticker_caps_at_three():
    text = "AAPL MSFT NVDA AMZN GOOG META TSLA"
    assert len(extract_tickers(text)) == 3


def test_extract_ticker_empty():
    assert extract_tickers("") == []
    assert extract_tickers("no tickers here just lowercase words") == []


def test_extract_ticker_skips_acronyms():
    # CEO, IPO, ETF are blocklisted.
    assert extract_tickers("The CEO did an IPO via an ETF") == []


# ── build_live_data_block ───────────────────────────────────────────────


def test_build_block_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", False)
    assert build_live_data_block("AAPL") is None


def test_build_block_returns_none_when_yfinance_empty(monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(fundamentals, "fetch_live_fundamentals", lambda t: None)
    assert build_live_data_block("XYZQ") is None


def test_build_block_formats_full_data(monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(
        fundamentals, "fetch_live_fundamentals",
        lambda t: {
            "base_price": 250.50,
            "pe": "35.2",
            "rev_growth": 8,
            "profit_margin": 25,
            "net_cash": 65_000,
            "low": 165.0,
            "high": 260.0,
        },
    )
    block = build_live_data_block("AAPL")
    assert block is not None
    assert "AAPL" in block
    assert "$250.5" in block
    assert "P/E: 35.2" in block
    assert "8%" in block
    assert "$165.0–$260.0" in block
    assert "training memory" in block.lower()


def test_build_block_omits_missing_keys(monkeypatch):
    """yfinance often returns partial data — block should skip missing
    fields rather than render 'None'."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(
        fundamentals, "fetch_live_fundamentals",
        lambda t: {"base_price": 100.0, "pe": "20.0"},
    )
    block = build_live_data_block("X")
    assert "Price: $100.0" in block
    assert "P/E: 20.0" in block
    assert "None" not in block
    assert "Net cash" not in block
    assert "revenue growth" not in block


# ── fetch_live_fundamentals (yfinance) ──────────────────────────────────


def test_fetch_swallows_exceptions(monkeypatch):
    """yfinance import or network error must never bubble up."""
    class _Boom:
        def __init__(self, *_a, **_kw):
            raise RuntimeError("network is on fire")

    # Force the yf import inside fetch to blow up.
    import sys, types
    fake_yf = types.SimpleNamespace(Ticker=_Boom)
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)
    assert fetch_live_fundamentals("AAPL") is None


def test_fetch_returns_none_when_anchor_fields_missing(monkeypatch):
    """If yfinance has neither price nor PE, treat ticker as unknown."""
    import sys, types

    class _Ticker:
        def __init__(self, _sym):
            self.info = {"marketCap": 1_000_000}  # no price, no PE
    fake_yf = types.SimpleNamespace(Ticker=_Ticker)
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)
    assert fetch_live_fundamentals("XYZQ") is None


def test_fetch_normalizes_yfinance_shape(monkeypatch):
    """Decimal growth → integer percent; cash/debt → net cash in millions."""
    import sys, types

    class _Ticker:
        def __init__(self, _sym):
            self.info = {
                "currentPrice": 250.0,
                "trailingPE": 35.123,
                "revenueGrowth": 0.084,
                "profitMargins": 0.252,
                "totalCash": 73_100_000_000,
                "totalDebt": 8_000_000_000,
                "fiftyTwoWeekLow": 164.0,
                "fiftyTwoWeekHigh": 260.0,
            }
    fake_yf = types.SimpleNamespace(Ticker=_Ticker)
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)

    out = fetch_live_fundamentals("AAPL")
    assert out is not None
    assert out["base_price"] == 250.0
    assert out["pe"] == "35.1"
    assert out["rev_growth"] == 8
    assert out["profit_margin"] == 25
    assert out["net_cash"] == 65_100
    assert out["low"] == 164.0
    assert out["high"] == 260.0


# ── DEF053: real valuation multiples / sector / dividends / analyst consensus ──


def test_fetch_includes_real_valuation_multiples_sector_and_consensus(monkeypatch):
    """P/S, EV/EBITDA, PEG, FCF yield, sector/industry, dividend yield, and
    analyst consensus all come free from yfinance's own info dict — no
    Alpha Vantage key needed, confirmed live against real tickers pre-code."""
    import sys, types

    class _Ticker:
        def __init__(self, _sym):
            self.info = {
                "currentPrice": 250.0,
                "trailingPE": 35.0,
                "priceToSalesTrailing12Months": 10.291255,
                "enterpriseToEbitda": 29.051,
                "pegRatio": 2.55,
                "freeCashflow": 101_090_746_368,
                "marketCap": 4_645_544_525_824,
                "dividendYield": 0.34,
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "targetMeanPrice": 315.56668,
                "recommendationKey": "strong_buy",
            }
    fake_yf = types.SimpleNamespace(Ticker=_Ticker)
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)

    out = fetch_live_fundamentals("AAPL")
    assert out is not None
    assert out["price_to_sales"] == "10.3"
    assert out["ev_to_ebitda"] == "29.1"
    assert out["peg_ratio"] == "2.55"
    assert out["fcf_yield"] == round(101_090_746_368 / 4_645_544_525_824 * 100, 1)
    assert out["dividend_yield"] == 0.34
    assert out["sector"] == "Technology"
    assert out["industry"] == "Consumer Electronics"
    assert out["analyst_target_price"] == 315.57
    assert out["analyst_rating"] == "strong buy"


def test_fetch_omits_new_fields_when_absent(monkeypatch):
    """Fields yfinance doesn't have for a ticker are omitted, not rendered
    as a fabricated placeholder."""
    import sys, types

    class _Ticker:
        def __init__(self, _sym):
            self.info = {"currentPrice": 100.0, "trailingPE": 20.0}
    fake_yf = types.SimpleNamespace(Ticker=_Ticker)
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)

    out = fetch_live_fundamentals("X")
    for key in ("price_to_sales", "ev_to_ebitda", "peg_ratio", "fcf_yield",
                "dividend_yield", "sector", "industry", "analyst_target_price",
                "analyst_rating"):
        assert key not in out


def test_fetch_handles_no_dividend_negative_fcf_and_no_rating(monkeypatch):
    """A non-dividend-payer with negative FCF and no analyst coverage
    (e.g. GME) must degrade gracefully, not crash or fabricate."""
    import sys, types

    class _Ticker:
        def __init__(self, _sym):
            self.info = {
                "currentPrice": 25.0,
                "trailingPE": 40.0,
                "freeCashflow": -1_261_250_048,
                "marketCap": 9_902_615_552,
                "dividendYield": None,
                "targetMeanPrice": None,
                "recommendationKey": "none",
                "sector": "Consumer Cyclical",
                "industry": "Specialty Retail",
            }
    fake_yf = types.SimpleNamespace(Ticker=_Ticker)
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)

    out = fetch_live_fundamentals("GME")
    assert out is not None
    assert out["fcf_yield"] < 0  # real negative FCF yield, not hidden
    assert "dividend_yield" not in out
    assert "analyst_target_price" not in out
    assert "analyst_rating" not in out  # "none" must not render as a fake rating
    assert out["sector"] == "Consumer Cyclical"


def test_fetch_treats_nan_numeric_fields_as_absent(monkeypatch):
    """DEF052's F1 lesson applied here proactively: yfinance's own
    missing-value sentinel is NaN, not always a missing key. A NaN value
    must be treated as absent, not rendered as the literal string "nan"
    (peg_ratio) or silently misbehave in a comparison (fcf_yield's
    market_cap > 0 guard)."""
    import sys, types

    nan = float("nan")

    class _Ticker:
        def __init__(self, _sym):
            self.info = {
                "currentPrice": 250.0,
                "trailingPE": nan,
                "priceToSalesTrailing12Months": nan,
                "pegRatio": nan,
                "freeCashflow": nan,
                "marketCap": nan,
                "dividendYield": nan,
                "targetMeanPrice": nan,
            }
    fake_yf = types.SimpleNamespace(Ticker=_Ticker)
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)

    out = fetch_live_fundamentals("AAPL")
    assert out is not None
    for key in ("pe", "price_to_sales", "peg_ratio", "fcf_yield",
                "dividend_yield", "analyst_target_price"):
        assert key not in out


def test_fetch_treats_nan_in_preexisting_fields_as_absent_not_a_crash(monkeypatch):
    """Auditor OUT-OF-SCOPE observation #2 on DEF053: the pre-existing
    round(rev_growth*100)/round(profit_margin*100)/round((cash-debt)/1e6)
    calls use round() without ndigits -- round(nan) raises ValueError,
    same class as DEF052's F1, and predates this Defect. The centralized
    _num() isfinite guard closes it without touching these call sites."""
    import sys, types

    nan = float("nan")

    class _Ticker:
        def __init__(self, _sym):
            self.info = {
                "currentPrice": 250.0,
                "revenueGrowth": nan,
                "profitMargins": nan,
                "totalCash": nan,
                "totalDebt": 1_000.0,
            }
    fake_yf = types.SimpleNamespace(Ticker=_Ticker)
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)

    out = fetch_live_fundamentals("AAPL")  # must not raise
    assert out is not None
    assert "rev_growth" not in out
    assert "profit_margin" not in out
    assert "net_cash" not in out


def test_build_block_includes_valuation_sector_dividend_and_analyst_lines(monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(
        fundamentals, "fetch_live_fundamentals",
        lambda t: {
            "base_price": 250.50,
            "pe": "35.2",
            "price_to_sales": "10.3",
            "ev_to_ebitda": "29.1",
            "peg_ratio": "2.55",
            "fcf_yield": 2.2,
            "dividend_yield": 0.34,
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "analyst_target_price": 315.57,
            "analyst_rating": "strong buy",
        },
    )
    block = build_live_data_block("AAPL")
    assert block is not None
    assert "P/S 10.3x" in block
    assert "EV/EBITDA 29.1x" in block
    assert "PEG 2.55" in block
    assert "FCF yield 2.2%" in block
    assert "Dividend yield: 0.34%" in block
    assert "Technology / Consumer Electronics" in block
    assert "strong buy" in block
    assert "$315.57" in block
    assert "not company guidance" in block


# ── CR046 M04 yfinance convention floor (FIX 3) ──────────────────────────


class _CapLogger:
    """Minimal stand-in that records error() calls, so the degrade-loudly path
    is asserted without exercising structlog itself."""

    def __init__(self) -> None:
        self.errors: list[tuple[str, dict]] = []

    def error(self, event: str, **kw) -> None:
        self.errors.append((event, kw))


def test_yfinance_major_parses_the_convention_floor():
    """CR046 M04 pin guard: dividend_yield_pct is only correct on yfinance major
    >= 1. 0.2.x (fraction convention) must read as below the floor; the two
    versions actually installed today (Mac 1.3.0, Alpha 1.5.1) as above it."""
    assert fundamentals._yfinance_major("0.2.50") == 0
    assert fundamentals._yfinance_major("1.3.0") == 1
    assert fundamentals._yfinance_major("1.5.1") == 1
    assert fundamentals._yfinance_major("") == -1
    assert fundamentals._yfinance_major(None) == -1
    assert fundamentals._yfinance_major("garbage") == -1
    # the gate that decides whether to shout
    assert (fundamentals._yfinance_major("0.2.50") < 1) is True
    assert (fundamentals._yfinance_major("1.5.1") < 1) is False


def test_stale_yfinance_shouts_loudly_once(monkeypatch):
    """degrade-loudly (CR040): a <1.0 yfinance logs an error, because on 0.2.x
    dividendYield is a fraction and every payer's yield would be ~100x too low —
    silently. The check fires once per process, not per fetch."""
    cap = _CapLogger()
    monkeypatch.setattr(fundamentals, "logger", cap)
    monkeypatch.setattr(fundamentals, "_yf_convention_checked", False)

    class _Stale:
        __version__ = "0.2.50"

    class _Ok:
        __version__ = "1.5.1"

    fundamentals._warn_if_yfinance_convention_stale(_Stale())
    assert [e for e, _ in cap.errors] == ["yfinance_below_dividend_convention_floor"]
    assert cap.errors[0][1]["installed"] == "0.2.50"
    # once-guard: a later call (even a fine version) does not re-log.
    fundamentals._warn_if_yfinance_convention_stale(_Ok())
    assert len(cap.errors) == 1


def test_current_yfinance_convention_is_silent(monkeypatch):
    """A 1.x install (today's reality) must NOT shout — no false alarm."""
    cap = _CapLogger()
    monkeypatch.setattr(fundamentals, "logger", cap)
    monkeypatch.setattr(fundamentals, "_yf_convention_checked", False)

    class _Ok:
        __version__ = "1.5.1"

    fundamentals._warn_if_yfinance_convention_stale(_Ok())
    assert cap.errors == []
