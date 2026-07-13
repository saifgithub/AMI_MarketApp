"""Real technical indicators for the Market Analyst — Room + 1-on-1 agent paths.

DEF052 (AT:R58): `room_runner.py::_profile_for_ticker()`'s `rsi`/`trend`/
`volume_tone`/`support`/`breakout` were 100% fabricated always (a coin flip
or `rng.randint`), and `content/agents/market_analyst.md` claimed MACD/
moving averages/Bollinger Bands that were never computed anywhere. This
module computes real RSI, a real moving-average trend read, real volume vs.
a real trailing average, and a real recent-range support/breakout from
yfinance OHLCV (`MarketDataProvider.history()`, already flowing for the
mobile Ticker Detail chart) — no new external API, just a computation layer
over data already being fetched.

MACD, moving-average-crossover signals, and Bollinger Bands are explicitly
NOT computed here (DEF052's scope decision, AT:R58) — the prompt no longer
claims them rather than half-implementing a third indicator family.

Never raises. Returns None when history is unavailable or too short for a
reliable read — callers fall back to the synthetic profile block, same
never-raises contract as fundamentals.py/news_context.py/social_context.py.
"""

from __future__ import annotations

from typing import NamedTuple

from app.core.config import settings
from app.core.logging import logger
from app.services.market_data import get_market_data_provider

_HISTORY_PERIOD = "3m"  # ~65 daily candles — enough for RSI-14 and a 50-day SMA
_RSI_PERIOD = 14
_SMA_SHORT = 20
_SMA_LONG = 50
_RECENT_VOLUME_WINDOW = 5
_VOLUME_BASELINE_WINDOW = 20


class Technicals(NamedTuple):
    """A real technical read for one ticker, derived from yfinance OHLCV."""

    rsi: int
    rsi_tone: str
    trend: str
    volume_tone: str
    support: float
    breakout: float


def _rsi(closes: list[float], period: int = _RSI_PERIOD) -> float | None:
    """Standard 14-period RSI (simple average of gains/losses)."""
    if len(closes) < period + 1:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _rsi_tone(rsi: float) -> str:
    if rsi >= 70:
        return "overbought"
    if rsi <= 30:
        return "oversold"
    return "neither overbought nor oversold"


def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def compute_technicals(ticker: str) -> Technicals | None:
    """Real RSI/trend/volume/support-resistance from yfinance OHLCV.

    Never raises. Returns None when history is unavailable or shorter than
    the 50-day lookback the trend/support/breakout reads need.
    """
    try:
        candles = get_market_data_provider().history(ticker.upper().strip(), _HISTORY_PERIOD)
    except Exception as exc:
        logger.warn("technicals_history_error", ticker=ticker, error=str(exc)[:200])
        return None
    if not candles or len(candles) < _SMA_LONG:
        return None

    closes = [c.c for c in candles]
    highs = [c.h for c in candles]
    lows = [c.low for c in candles]
    volumes = [c.v for c in candles]

    rsi = _rsi(closes)
    if rsi is None:
        return None

    sma_short = _sma(closes, _SMA_SHORT)
    sma_long = _sma(closes, _SMA_LONG)
    if sma_short is None or sma_long is None:
        return None
    price = closes[-1]
    # "Trading" = a clear directional bias (price + both moving averages
    # aligned the same way); "consolidating" = no clean read either way.
    aligned_up = price > sma_short > sma_long
    aligned_down = price < sma_short < sma_long
    trend = "trading" if (aligned_up or aligned_down) else "consolidating"

    recent_vol = sum(volumes[-_RECENT_VOLUME_WINDOW:]) / _RECENT_VOLUME_WINDOW
    baseline_vol = sum(volumes[-_VOLUME_BASELINE_WINDOW:]) / _VOLUME_BASELINE_WINDOW
    if baseline_vol <= 0:
        volume_tone = "in-line with 20-day average"
    elif recent_vol > baseline_vol * 1.1:
        volume_tone = "above 20-day average"
    elif recent_vol < baseline_vol * 0.9:
        volume_tone = "below 20-day average"
    else:
        volume_tone = "in-line with 20-day average"

    # Support/breakout: the real recent swing low/high over the same
    # lookback window as the trend read — not `base_price × fixed_multiplier`.
    support = min(lows[-_SMA_LONG:])
    breakout = max(highs[-_SMA_LONG:])

    return Technicals(
        rsi=round(rsi),
        rsi_tone=_rsi_tone(rsi),
        trend=trend,
        volume_tone=volume_tone,
        support=round(support, 2),
        breakout=round(breakout, 2),
    )


def build_technicals_context_block(ticker: str) -> str | None:
    """System-prompt-ready block of real technicals — 1-on-1 path, Market
    Analyst only. Mirrors news_context.build_news_context_block's contract.
    """
    if not settings.use_real_market_data:
        return None
    t = compute_technicals(ticker)
    if t is None:
        return None
    sym = ticker.upper()
    return (
        f"─── LIVE TECHNICALS — {sym} ───\n"
        f"RSI(14): {t.rsi} ({t.rsi_tone})\n"
        f"Trend: {t.trend} (price vs. 20/50-day moving averages)\n"
        f"Volume: {t.volume_tone}\n"
        f"Recent range — support: ${t.support}, breakout level: ${t.breakout}\n"
        f"(Real yfinance OHLCV for {sym}, computed this call. Use these "
        f"numbers when discussing {sym}'s technicals. Do NOT claim MACD, a "
        f"moving-average crossover signal, or Bollinger Bands — none of "
        f"those are computed.)"
    )
