"""CR253 lane A — Bollinger bands + MACD on the Market Analyst's fact sheet.

The content/agents/market_analyst.md profile claims Bollinger bands and
MACD; the sheet never carried them (~140 measured GAPS turns reached for
training memory instead). Both are now computed in code from the same daily
bars as the range/trend block — Bollinger as the 20-period SMA ± 2
population σ, MACD as 12/26 EMAs with a 9-period EMA signal — and rendered
to every agent whose lane includes technicals. The firewalled News/Social
analysts stay untouched, and ATR's narrower Execution/Risk gate is not
widened by this change.

The rules pinned here:

**Computed in code (CR179 Leg 4).** The pure math lives in
`app/trading_math/indicators.py`; the model is never handed operands and an
instruction. Values below are hand-verified against the formulas.

**Absent stays absent.** A family that was not computed renders NO line —
never a $0 band or a 0.0 MACD wearing the (LIVE) label.

**The lane gate is the technicals domain, not a new allowlist.** Market
Analyst sees the lines; News/Social analysts do not; the default-open
full-sheet agents (Trader, PM, …) do.
"""

from __future__ import annotations

import pytest

from app.schemas.agents import AgentId
from app.services.market_data import Candle
from app.services.room_prompts import _format_profile
from app.services.technicals import compute_technicals
from app.trading_math import indicators

_BASE_T = 1_800_000_000


def _candles(closes, volumes=None) -> list[Candle]:
    n = len(closes)
    volumes = volumes if volumes is not None else [1_000_000] * n
    return [
        Candle(t=_BASE_T + i * 86400, o=closes[i], h=closes[i] + 1,
               low=closes[i] - 1, c=closes[i], v=volumes[i])
        for i in range(n)
    ]


class _FakeProvider:
    def __init__(self, candles):
        self._candles = candles

    def history(self, ticker, period):
        return self._candles


# ── The pure math (hand-verified against the formulas) ──────────────────────


class TestBollingerBands:
    def test_a_constant_window_has_zero_width(self):
        assert indicators.bollinger_bands([100.0] * 20) == (100.0, 100.0, 100.0)

    def test_the_last_window_is_what_gets_measured(self):
        """closes 1..20: mean 10.5, population σ = √33.25 ≈ 5.7663, so the
        bands sit at 10.5 ± 2σ — the 20-point window, not the whole series."""
        out = indicators.bollinger_bands([float(i) for i in range(1, 21)])
        assert out is not None
        middle, upper, lower = out
        assert middle == 10.5
        assert upper == pytest.approx(10.5 + 2 * 5.766281, abs=1e-4)
        assert lower == pytest.approx(10.5 - 2 * 5.766281, abs=1e-4)

    def test_fewer_than_window_closes_is_none(self):
        assert indicators.bollinger_bands([100.0] * 19) is None

    def test_population_not_sample_stddev(self):
        """Bollinger's own convention: the window is the whole population.
        Sample σ of 1..20 (√35) would put the bands at ±11.83, population
        (√33.25) at ±11.53 — the distinction is pinned so a library swap
        cannot silently change the number."""
        _middle, upper, _lower = indicators.bollinger_bands([float(i) for i in range(1, 21)])  # type: ignore[misc]
        assert upper == pytest.approx(22.0326, abs=1e-3)


class TestEma:
    def test_the_seed_is_the_first_window_sma(self):
        """SMA-of-first-window seeding (the TA-Lib/pandas convention), pinned:
        with no points past the window the EMA IS the seed, and a 2-point
        window over [1, 2, 3] seeds at 1.5 then smooths toward 3 with k=2/3."""
        assert indicators.ema([float(i) for i in range(1, 13)], 12) == 6.5
        series = indicators._ema_series([1.0, 2.0, 3.0], 2)
        assert series == [1.5, 2.5]

    def test_fewer_than_window_is_none(self):
        assert indicators.ema([1.0, 2.0], 3) is None
        assert indicators._ema_series([1.0, 2.0], 3) is None


class TestMacd:
    def test_minimum_bars_is_slow_plus_signal_minus_one(self):
        """The signal is an EMA over `signal` MACD-line values, and the MACD
        line starts at bar `slow` — so 33 bars cannot produce a signal and 34
        can. One bar short is None, never a partial (line-only) answer."""
        flat = [100.0] * 33
        assert indicators.macd(flat) is None
        out = indicators.macd([100.0] * 34)
        assert out is not None
        # Flat closes: both EMAs sit at 100 forever, so every leg is exactly 0.
        assert out == (0.0, 0.0, 0.0)

    def test_an_uptrend_reads_positive(self):
        closes = [100.0 + i * 0.5 for i in range(65)]
        macd_line, signal, histogram = indicators.macd(closes)
        assert macd_line > 0  # fast EMA above slow EMA on a steady rise
        assert histogram == pytest.approx(macd_line - signal)

    def test_the_histogram_never_disagrees_with_its_legs(self):
        closes = [200.0 - i for i in range(65)]
        macd_line, signal, histogram = indicators.macd(closes)
        assert histogram == pytest.approx(macd_line - signal)


# ── compute_technicals carries the families ─────────────────────────────────


def _compute(monkeypatch, closes):
    from app.services import technicals

    monkeypatch.setattr(
        technicals, "get_market_data_provider", lambda: _FakeProvider(_candles(closes)),
    )
    return compute_technicals("AAPL")


def test_the_families_ride_the_live_block(monkeypatch):
    t = _compute(monkeypatch, [100.0 + i * 0.5 for i in range(65)])
    assert t is not None
    assert t.bollinger_upper is not None and t.bollinger_upper > t.bollinger_lower  # type: ignore[operator]
    assert t.bollinger_width_pct is not None and t.bollinger_width_pct > 0
    assert t.macd_line is not None and t.macd_line > 0
    assert t.macd_histogram == pytest.approx(t.macd_line - t.macd_signal)  # type: ignore[operator]


def test_the_bands_measure_the_last_twenty_closes(monkeypatch):
    """The last 20 closes are 1..20 on top of a flat 45-candle base: the
    bands must read exactly the 1..20 window, not the base."""
    closes = [100.0] * 45 + [float(i) for i in range(1, 21)]
    t = _compute(monkeypatch, closes)
    assert t is not None
    assert t.bollinger_upper == pytest.approx(round(10.5 + 2 * 5.766281, 2))
    assert t.bollinger_lower == pytest.approx(round(10.5 - 2 * 5.766281, 2))


def test_the_whole_block_still_degrades_to_none_together(monkeypatch):
    """Bollinger/MACD ride the same all-or-nothing fetch as RSI/trend — a
    30-candle history is below the 50-bar minimum, so there is no partial
    result carrying bands with nothing else (the atr14 precedent)."""
    t = _compute(monkeypatch, [100.0] * 30)
    assert t is None


# ── The sheet ────────────────────────────────────────────────────────────────


def _live_profile(**over) -> dict:
    profile = {
        "ticker": "TEST",
        "field_state": {"technicals": "live"},
        "rsi": 50, "rsi_tone": "neutral", "trend": "uptrend",
        "support": 90.0, "breakout": 110.0, "last_close": 100.0,
        "sma_short": 99.0, "sma_long": 95.0, "volume_tone": "in-line",
        "volume_ratio": 1.0, "return_period_pct": 1.0, "period_candles": 63,
        "atr14": 4.21,
        "bollinger_upper": 108.5, "bollinger_lower": 91.5,
        "bollinger_width_pct": 17.0,
        "macd_line": 1.234, "macd_signal": 0.876, "macd_histogram": 0.358,
    }
    profile.update(over)
    return profile


class TestTheRenderedSheetPerAgent:
    def test_market_analyst_sees_both_lines(self):
        sheet = _format_profile(_live_profile(), AgentId.MARKET_ANALYST)
        assert "Bollinger bands (20-day, 2σ): upper $108.5, lower $91.5" in sheet
        assert "band width 17.0% of the 20-day average" in sheet
        assert "MACD (12/26/9): line 1.234, signal 0.876, histogram 0.358" in sheet
        # The rest of the technicals block rendered too, so an absent line
        # below would be the gate working, not a dead block.
        assert "RSI:" in sheet

    def test_news_and_social_analysts_do_not(self):
        """The lane firewall is untouched: technicals stay out of the
        News/Social sheets entirely — the new lines must not punch through
        the domain gate either."""
        for agent in (AgentId.NEWS_ANALYST, AgentId.SOCIAL_MEDIA_ANALYST):
            sheet = _format_profile(_live_profile(), agent)
            assert "Bollinger" not in sheet
            assert "MACD" not in sheet

    def test_full_sheet_agents_see_both_lines(self):
        """The lane matrix is default-open: the Trader and PM carry the
        technicals domain and get the breadth too (unlike ATR, which keeps
        its narrower Execution/Risk gate — pinned next)."""
        sheet = _format_profile(_live_profile(), AgentId.TRADER)
        assert "Bollinger bands" in sheet
        assert "MACD (12/26/9)" in sheet

    def test_atrs_narrow_gate_is_not_widened(self):
        """Regression: Bollinger/MACD render for the Market Analyst, but ATR
        must still be withheld from it — the two gates are independent."""
        sheet = _format_profile(_live_profile(), AgentId.MARKET_ANALYST)
        assert "ATR(14)" not in sheet
        sheet = _format_profile(_live_profile(), AgentId.TRADER)
        assert "ATR(14)" in sheet

    def test_absent_families_render_no_line_even_in_the_lane(self):
        sheet = _format_profile(
            _live_profile(bollinger_upper=None, bollinger_lower=None,
                          bollinger_width_pct=None, macd_line=None,
                          macd_signal=None, macd_histogram=None),
            AgentId.MARKET_ANALYST,
        )
        assert "Bollinger" not in sheet
        assert "MACD" not in sheet
        assert "RSI:" in sheet  # the block itself still rendered

    def test_a_partial_family_renders_nothing(self):
        """One leg of a family present without the other is not a family —
        no half-Bollinger or signal-less MACD line."""
        sheet = _format_profile(
            _live_profile(bollinger_lower=None, macd_signal=None),
            AgentId.MARKET_ANALYST,
        )
        assert "Bollinger" not in sheet
        assert "MACD" not in sheet

    def test_unavailable_technicals_render_no_fabricated_family(self):
        sheet = _format_profile(
            _live_profile(field_state={"technicals": "unavailable"}),
            AgentId.MARKET_ANALYST,
        )
        assert "Bollinger" not in sheet
        assert "MACD" not in sheet
        assert "not available this call" in sheet

    def test_the_unlaned_full_sheet_carries_the_lines(self):
        """agent_id=None is the union-of-lanes parity surface."""
        sheet = _format_profile(_live_profile())
        assert "Bollinger bands" in sheet
        assert "MACD (12/26/9)" in sheet
