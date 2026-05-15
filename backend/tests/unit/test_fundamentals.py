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
            "fcf_margin": 25,
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
    assert out["fcf_margin"] == 25
    assert out["net_cash"] == 65_100
    assert out["low"] == 164.0
    assert out["high"] == 260.0
