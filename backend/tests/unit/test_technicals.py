"""DEF052 — Market Analyst's RSI/trend/volume/support-breakout must be real,
computed from yfinance OHLCV, not fabricated (rng.randint / coin flip /
base_price * fixed_multiplier).
"""

from __future__ import annotations

from app.services import technicals
from app.services.market_data import Candle
from app.services.technicals import compute_technicals

_BASE_T = 1_800_000_000


def _candles(closes, highs=None, lows=None, volumes=None) -> list[Candle]:
    n = len(closes)
    highs = highs if highs is not None else [c + 1 for c in closes]
    lows = lows if lows is not None else [c - 1 for c in closes]
    volumes = volumes if volumes is not None else [1_000_000] * n
    return [
        Candle(t=_BASE_T + i * 86400, o=closes[i], h=highs[i], low=lows[i], c=closes[i], v=volumes[i])
        for i in range(n)
    ]


class _FakeProvider:
    def __init__(self, candles):
        self._candles = candles

    def history(self, ticker, period):
        return self._candles


class _RaisingProvider:
    def history(self, ticker, period):
        raise ConnectionError("boom")


def test_rsi_computed_from_real_price_deltas(monkeypatch):
    """14 deltas alternating +2/-1 → avg_gain=1.0, avg_loss=0.5, RS=2.0,
    RSI = 100 - 100/(1+2) = 66.66... -> rounds to 67. Hand-verified, not a
    coin flip or rng.randint(35, 75)."""
    closes = [100.0] * 51
    for d in [2, -1] * 7:
        closes.append(closes[-1] + d)
    assert len(closes) == 65
    monkeypatch.setattr(technicals, "get_market_data_provider", lambda: _FakeProvider(_candles(closes)))

    t = compute_technicals("AAPL")
    assert t is not None
    assert t.rsi == 67
    assert t.rsi_tone == "neither overbought nor oversold"


def test_rsi_pure_uptrend_is_overbought(monkeypatch):
    """All-gains, zero-loss window -> RS undefined -> RSI defined as 100."""
    closes = [100.0 + i for i in range(65)]
    monkeypatch.setattr(technicals, "get_market_data_provider", lambda: _FakeProvider(_candles(closes)))

    t = compute_technicals("AAPL")
    assert t is not None
    assert t.rsi == 100
    assert t.rsi_tone == "overbought"


def test_trend_directional_when_price_and_moving_averages_aligned(monkeypatch):
    """Strictly increasing closes -> price > SMA20 > SMA50 -> real directional
    bias, not a coin flip. DEF227 widened the reported value from the
    direction-blind "trading" to the direction that was already computed."""
    closes = [100.0 + i * 0.5 for i in range(65)]
    monkeypatch.setattr(technicals, "get_market_data_provider", lambda: _FakeProvider(_candles(closes)))

    t = compute_technicals("AAPL")
    assert t is not None
    assert t.trend == "uptrend"


def test_trend_consolidating_when_no_clear_alignment(monkeypatch):
    """Closes oscillating tightly around a flat mean -> no clean directional
    read -> consolidating, not a coin flip."""
    closes = [100.0 if i % 2 == 0 else 100.5 for i in range(65)]
    monkeypatch.setattr(technicals, "get_market_data_provider", lambda: _FakeProvider(_candles(closes)))

    t = compute_technicals("AAPL")
    assert t is not None
    assert t.trend == "consolidating"


def test_volume_tone_above_average_from_real_volume(monkeypatch):
    closes = [100.0] * 65
    volumes = [500_000] * 60 + [3_000_000] * 5
    monkeypatch.setattr(
        technicals, "get_market_data_provider",
        lambda: _FakeProvider(_candles(closes, volumes=volumes)),
    )
    t = compute_technicals("AAPL")
    assert t is not None
    assert t.volume_tone == "above 20-day average"


def test_volume_tone_below_average_from_real_volume(monkeypatch):
    closes = [100.0] * 65
    volumes = [500_000] * 60 + [100_000] * 5
    monkeypatch.setattr(
        technicals, "get_market_data_provider",
        lambda: _FakeProvider(_candles(closes, volumes=volumes)),
    )
    t = compute_technicals("AAPL")
    assert t is not None
    assert t.volume_tone == "below 20-day average"


def test_volume_tone_in_line_when_flat(monkeypatch):
    closes = [100.0] * 65
    volumes = [500_000] * 65
    monkeypatch.setattr(
        technicals, "get_market_data_provider",
        lambda: _FakeProvider(_candles(closes, volumes=volumes)),
    )
    t = compute_technicals("AAPL")
    assert t is not None
    assert t.volume_tone == "in-line with 20-day average"


def test_support_breakout_from_real_recent_range_not_base_price_multiplier(monkeypatch):
    """Support/breakout must come from the real recent (last 50-candle) price
    range, not `base_price * 0.9` / `* 1.03`. Extreme values outside the
    50-candle lookback must NOT leak in — proves the window is respected."""
    n = 65
    closes = [100.0] * n
    # First 15 candles (outside the last-50 window) carry absurd extremes.
    lows = [10.0] * 15 + [95.0] * 49 + [90.0]     # real min within window: 90.0 at the last candle
    highs = [500.0] * 15 + [105.0] * 49 + [110.0]  # real max within window: 110.0 at the last candle
    monkeypatch.setattr(
        technicals, "get_market_data_provider",
        lambda: _FakeProvider(_candles(closes, highs=highs, lows=lows)),
    )
    t = compute_technicals("AAPL")
    assert t is not None
    assert t.support == 90.0
    assert t.breakout == 110.0


def test_none_when_history_unavailable(monkeypatch):
    monkeypatch.setattr(technicals, "get_market_data_provider", lambda: _FakeProvider(None))
    assert compute_technicals("AAPL") is None


def test_none_when_history_too_short(monkeypatch):
    closes = [100.0] * 30  # below the 50-candle minimum
    monkeypatch.setattr(technicals, "get_market_data_provider", lambda: _FakeProvider(_candles(closes)))
    assert compute_technicals("AAPL") is None


def test_none_when_provider_raises(monkeypatch):
    monkeypatch.setattr(technicals, "get_market_data_provider", lambda: _RaisingProvider())
    assert compute_technicals("AAPL") is None


def test_none_when_a_close_is_nan(monkeypatch):
    """DEF052 round 2 (auditor F1, MAJOR): yfinance's own missing-value
    sentinel for thin/recently-IPO'd/halted tickers is NaN, not a missing
    candle — a type-valid Candle the 'never raises' contract must tolerate.
    Before the fix, round(rsi) raised ValueError on a NaN close, taking down
    the entire Room Convene, not just this agent's technicals."""
    closes = [100.0] * 64 + [float("nan")]
    monkeypatch.setattr(technicals, "get_market_data_provider", lambda: _FakeProvider(_candles(closes)))
    assert compute_technicals("AAPL") is None


def test_none_when_a_volume_is_nan(monkeypatch):
    closes = [100.0 + i * 0.5 for i in range(65)]
    volumes = [1_000_000.0] * 64 + [float("nan")]
    monkeypatch.setattr(
        technicals, "get_market_data_provider",
        lambda: _FakeProvider(_candles(closes, volumes=volumes)),
    )
    assert compute_technicals("AAPL") is None


def test_atr14_computed_alongside_the_rest_of_the_block(monkeypatch):
    """CR219 R36. `_candles()`'s default high/low spread (close ± 1) on flat
    closes gives a constant 2.0-wide True Range every session — hand-verified
    against `atr()`'s own formula before relying on it, matching
    `test_rsi_computed_from_real_price_deltas`'s own 'hand-verified, not
    fabricated' discipline above."""
    closes = [100.0] * 65
    monkeypatch.setattr(technicals, "get_market_data_provider", lambda: _FakeProvider(_candles(closes)))

    t = compute_technicals("AAPL")
    assert t is not None
    assert t.atr14 == 2.0


def test_atr14_none_when_the_whole_block_is_none(monkeypatch):
    """ATR rides the SAME all-or-nothing OHLCV fetch as RSI/trend/volume —
    when the block degrades to None (history too short), there is no
    partial result carrying an ATR value with nothing else."""
    closes = [100.0] * 30  # below the 50-candle minimum
    monkeypatch.setattr(technicals, "get_market_data_provider", lambda: _FakeProvider(_candles(closes)))
    assert compute_technicals("AAPL") is None


def test_none_when_a_low_is_nan(monkeypatch):
    """The auditor's own note: a NaN low alone doesn't reliably raise (min()
    skips it) but would silently yield a wrong support — the isfinite guard
    catches this case too, not just the raising ones."""
    closes = [100.0 + i * 0.5 for i in range(65)]
    lows = [c - 1 for c in closes]
    lows[-1] = float("nan")
    monkeypatch.setattr(
        technicals, "get_market_data_provider",
        lambda: _FakeProvider(_candles(closes, lows=lows)),
    )
    assert compute_technicals("AAPL") is None


def test_build_technicals_context_block_absent_when_disabled(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "use_real_market_data", False)
    closes = [100.0 + i * 0.5 for i in range(65)]
    monkeypatch.setattr(technicals, "get_market_data_provider", lambda: _FakeProvider(_candles(closes)))

    assert technicals.build_technicals_context_block("AAPL") is None


def test_build_technicals_context_block_present_when_enabled(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "use_real_market_data", True)
    closes = [100.0 + i * 0.5 for i in range(65)]
    monkeypatch.setattr(technicals, "get_market_data_provider", lambda: _FakeProvider(_candles(closes)))

    block = technicals.build_technicals_context_block("AAPL")
    assert block is not None
    assert "LIVE TECHNICALS — AAPL" in block
    assert "MACD" in block  # explicit "do NOT claim MACD" disclaimer present
