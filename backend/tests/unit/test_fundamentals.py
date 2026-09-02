"""Tests for the live-fundamentals helper (shared by Room + 1-on-1)."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.schemas import AgentId
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


def test_build_block_header_states_the_run_date_anchor(monkeypatch):
    """DEF124/D2/D3 — the 1-on-1 fundamentals block gets the same run-date
    anchor as the Room's fact sheet, not a strictly poorer surface."""
    from datetime import datetime, timezone

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(fundamentals, "fetch_live_fundamentals", lambda t: {"base_price": 100.0})
    monkeypatch.setattr(fundamentals, "fetch_next_earnings", lambda t: None)

    block = build_live_data_block("AAPL")
    today = datetime.now(timezone.utc).date().isoformat()
    assert f"as of {today} (UTC)" in block


def test_build_block_earnings_line_renders_interval_alongside_date(monkeypatch):
    """DEF124/D1/D3 — mirrors the Room's earnings line: the interval rides
    alongside the absolute date, computed in Python via the same shared
    `app.core.time.relative_day_phrase` helper."""
    from datetime import date, datetime, timezone
    from app.core.time import relative_day_phrase
    from app.services.market_data import EarningsInfo

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(fundamentals, "fetch_live_fundamentals", lambda t: {"base_price": 100.0})
    monkeypatch.setattr(
        fundamentals, "fetch_next_earnings",
        lambda t: EarningsInfo(earnings_date="2026-08-01", quarter="Q3", eps_estimate=2.1),
    )

    block = build_live_data_block("AAPL")
    today = datetime.now(timezone.utc).date()
    interval = relative_day_phrase(date(2026, 8, 1), today)
    assert f"Next earnings (LIVE): 2026-08-01 (Q3) — {interval}, consensus EPS est. $2.1" in block


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


# ── CR219 R24 — lane-gating (reuses room_prompts._AGENT_LANES) ──────────
#
# One payload carrying at least one field from every domain: fundamentals
# (pe, margin), technicals (CR179 Leg 3: day_change_pct/sma_200/beta/...),
# and the dual-lane fields (52-week range, next earnings). If a domain's
# gate is wrong, either an in-lane line goes missing or an out-of-lane line
# leaks — this payload is rich enough for both directions to be visible.
_LANED_PAYLOAD: dict = {
    "base_price": 271.83,
    "long_name": "LANESENT CORP",
    "exchange_name": "NASDAQ",
    # fundamentals-domain
    "pe": "48.77",
    "rev_growth": 23.61,
    "net_cash": 944,
    "gross_margin": 63.71,
    "operating_margin": 52.83,
    "profit_margin": 41.29,
    "price_to_sales": "7.31",
    "dividend_yield": 1.63,
    "sector": "ENERGYSENT",
    "industry": "DRILLSENT",
    "analyst_target_price": 488.12,
    "analyst_rating": "STRONGSENT",
    # technicals-domain (CR179 Leg 3 — fetched via the fundamentals endpoint,
    # classified as technicals by SUBJECT MATTER, same as the Room)
    "day_change_pct": -1.77,
    "market_state": "REGULAR",
    "sma_200": 188.44,
    "price_vs_sma_200_pct": 12.6,
    "volume_today": 44556677,
    "volume_avg_3m": 88776655,
    "change_52w_pct": 27.4,
    "change_52w_sp500_pct": 11.9,
    "relative_strength_52w_pct": 15.5,
    "beta": 1.93,
    "short_pct_float": 6.28,
    "short_days_to_cover": 4.7,
    "short_interest_date": "2026-07-15",
    # dual-lane
    "low": 155.4,
    "high": 402.9,
    "week52_range_live": True,
}


def test_build_block_fundamentals_analyst_gets_no_technicals_section(monkeypatch):
    """CR219 R24 — the same lane-gating the Room applies to `_format_profile`
    now applies here: a 1-on-1 Fundamentals Analyst does not receive the
    day-move/200-day-trend/relative-strength/volume/beta/short-interest
    block, matching the persona's own denial that this data is another
    desk's."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(
        fundamentals, "fetch_live_fundamentals", lambda t: dict(_LANED_PAYLOAD)
    )
    monkeypatch.setattr(fundamentals, "fetch_next_earnings", lambda t: None)

    block = build_live_data_block("AAPL", AgentId.FUNDAMENTALS_ANALYST)
    assert block is not None
    # In lane: fundamentals content survives.
    assert "P/E: 48.77" in block
    assert "gross 63.71%" in block
    assert "Sector/industry: ENERGYSENT / DRILLSENT" in block
    # Out of lane: no technicals-domain content leaks.
    for marker in (
        "-1.77% today", "200-day average", "S&P 500", "vs the market",
        "shares today", "3-month average", "days to cover",
    ):
        assert marker not in block, f"{marker!r} leaked into the fundamentals_analyst block"


def test_build_block_market_analyst_still_gets_technicals_section(monkeypatch):
    """The other half of the same check — a lane-gated Market Analyst must
    not lose the CR179 Leg 3 data it is entitled to; only the OTHER desk's
    data is withheld."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(
        fundamentals, "fetch_live_fundamentals", lambda t: dict(_LANED_PAYLOAD)
    )
    monkeypatch.setattr(fundamentals, "fetch_next_earnings", lambda t: None)

    block = build_live_data_block("AAPL", AgentId.MARKET_ANALYST)
    assert block is not None
    # In lane: technicals content survives.
    assert "-1.77% today" in block
    assert "200-day average" in block
    assert "vs the market" in block  # beta
    # Out of lane: no fundamentals-only content leaks (dividend/sector/
    # consensus/valuation are fundamentals-exclusive; margin/growth too).
    for marker in (
        "P/E: 48.77", "gross 63.71%", "Sector/industry:", "TTM revenue growth",
        "Valuation:", "STRONGSENT",
    ):
        assert marker not in block, f"{marker!r} leaked into the market_analyst block"


def test_build_block_dual_lane_range_survives_either_lane(monkeypatch):
    """52-week range is dual-lane (fundamentals OR technicals), same as the
    Room's `week52` line — both firewalled analysts should still see it."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(
        fundamentals, "fetch_live_fundamentals", lambda t: dict(_LANED_PAYLOAD)
    )
    monkeypatch.setattr(fundamentals, "fetch_next_earnings", lambda t: None)

    fund_block = build_live_data_block("AAPL", AgentId.FUNDAMENTALS_ANALYST)
    tech_block = build_live_data_block("AAPL", AgentId.MARKET_ANALYST)
    assert "52-week range: $155.4–$402.9" in fund_block
    assert "52-week range: $155.4–$402.9" in tech_block


def test_build_block_unlaned_agent_and_default_get_the_full_block(monkeypatch):
    """`agent_id=None` (the default, every pre-R24 call site) and an agent
    absent from `_AGENT_LANES` (e.g. the Trader — only the four analysts are
    gated, room_prompts.py `_AGENT_LANES`) both fail OPEN to the full block,
    matching `_format_profile`'s own fail-open contract. This is the parity
    guarantee `test_prompt_data_parity.py` depends on: it calls with no
    agent_id and must keep seeing every domain."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(
        fundamentals, "fetch_live_fundamentals", lambda t: dict(_LANED_PAYLOAD)
    )
    monkeypatch.setattr(fundamentals, "fetch_next_earnings", lambda t: None)

    default_block = build_live_data_block("AAPL")
    trader_block = build_live_data_block("AAPL", AgentId.TRADER)
    for block in (default_block, trader_block):
        assert block is not None
        assert "P/E: 48.77" in block
        assert "-1.77% today" in block
        assert "Sector/industry: ENERGYSENT / DRILLSENT" in block


def test_build_block_identity_and_price_survive_lane_gating(monkeypatch):
    """Identity and the reference quote are core, not a lane's data — every
    agent needs a price to reason about the portfolio block, same as the
    Room's unconditional `_reference_price_line`."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(
        fundamentals, "fetch_live_fundamentals", lambda t: dict(_LANED_PAYLOAD)
    )
    monkeypatch.setattr(fundamentals, "fetch_next_earnings", lambda t: None)

    block = build_live_data_block("AAPL", AgentId.FUNDAMENTALS_ANALYST)
    assert "LANESENT CORP" in block
    assert "Price: $271.83" in block


def test_build_block_withheld_lane_announces_itself(monkeypatch):
    """CR040 — a withheld lane must not silently vanish. The Room's
    `_out_of_lane_line` exists for exactly this; the 1-on-1 block gets an
    analogous notice, worded for a single-agent chat (no "another analyst
    holds it" claim — there is no other analyst in this conversation)."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(
        fundamentals, "fetch_live_fundamentals", lambda t: dict(_LANED_PAYLOAD)
    )
    monkeypatch.setattr(fundamentals, "fetch_next_earnings", lambda t: None)

    block = build_live_data_block("AAPL", AgentId.FUNDAMENTALS_ANALYST)
    assert "Not shown in this chat:" in block
    assert "market technicals (RSI, trend, ranges, volume)" in block
    assert "division of labour" in block
    assert "do not estimate or infer it" in block
    # The Room's exact wording would be false here — there is no other
    # analyst in a 1-on-1 conversation to hand withheld data to.
    assert "another analyst" not in block.lower()


def test_build_block_unlaned_and_default_carry_no_withheld_notice(monkeypatch):
    """The notice must not fire when nothing is withheld — otherwise every
    pre-R24 caller's output changes shape, which is exactly the parity
    break `test_prompt_data_parity.py` exists to catch."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(
        fundamentals, "fetch_live_fundamentals", lambda t: dict(_LANED_PAYLOAD)
    )
    monkeypatch.setattr(fundamentals, "fetch_next_earnings", lambda t: None)

    default_block = build_live_data_block("AAPL")
    trader_block = build_live_data_block("AAPL", AgentId.TRADER)
    for block in (default_block, trader_block):
        assert "Not shown in this chat:" not in block


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
    # CR166 Tier B — the yield keeps its basis label now that an indicated RATE
    # can sit beside it on the same line (DEF233's two-bases rule).
    assert "Dividend: yield 0.34% (trailing)" in block
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
