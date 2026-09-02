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

import math
from typing import NamedTuple

from app.core.config import settings
from app.core.logging import logger
from app.services.market_data import (
    SYNTHETIC_HISTORY_SOURCES,
    get_market_data_provider,
    history_with_source,
)

# RSI/SMA math now lives in the portable trading_math library (CR046 M01).
# Re-exported under the original private names so this module's internals and
# any importers are unchanged; the computation is identical (Cutler's RSI).
from app.trading_math.indicators import atr as _atr
from app.trading_math.indicators import rsi as _rsi
from app.trading_math.indicators import rsi_tone as _rsi_tone
from app.trading_math.indicators import sma as _sma

_HISTORY_PERIOD = "3m"  # ~65 daily candles — enough for RSI-14 and a 50-day SMA
_RSI_PERIOD = 14
_SMA_SHORT = 20
_SMA_LONG = 50
_RECENT_VOLUME_WINDOW = 5
_VOLUME_BASELINE_WINDOW = 20
_ATR_PERIOD = 14  # CR219 R36


class Technicals(NamedTuple):
    """A real technical read for one ticker, derived from yfinance OHLCV."""

    rsi: int
    rsi_tone: str
    trend: str
    volume_tone: str
    support: float
    breakout: float
    price: float
    # CR150 A2-family / CR145 Tier A — computed here since DEF227 and then
    # DISCARDED. `trend` is derived from the two moving averages and `volume_tone`
    # from the ratio, so every one of these numbers already exists at the moment
    # the label is chosen; only the label shipped. An agent told "uptrend" and
    # "above 20-day average" cannot say by how much, cannot see whether price is
    # 0.4% or 14% above the 50-day, and reaches for training memory to fill the
    # gap — which is the exact behaviour the grounding directive forbids.
    sma_short: float
    sma_long: float
    volume_ratio: float
    # CR146 Tier C / CR179 Leg 3 — the TREND the overlay asks 18/18 prompts to
    # "emphasise (monthly/quarterly)", finally derivable. The series was always
    # here; only the last candle and two averages were ever read from it, so an
    # agent told to speak to a quarterly trend had a single day's price and two
    # smoothed levels to do it with.
    #
    # Computed from the SAME 3-month fetch rather than the 2-year one CR146 Tier
    # C proposed. That tier's own cost note was a second `.history()` call per
    # ticker per convene, and it is no longer needed: the 200-day average, the
    # 52-week change and the relative strength versus the index all now arrive
    # from `.info` (CR179 Leg 3a) at zero additional cost, which was most of
    # what the longer window was wanted for. The quarter is what remained, and
    # the quarter is exactly what this series already spans.
    #
    # Defaulted, following CR030's `EarningsInfo` precedent, so every existing
    # fixture that builds a Technicals positionally is unaffected. The defaults
    # are also the honest degrade: `_period_trend_line` treats a zero candle
    # count as falsy and renders "not available" rather than claiming a flat
    # quarter across no data.
    return_period_pct: float = 0.0
    period_candles: int = 0
    # CR219 R36 — ATR(14), Execution/Risk lanes only (the volatility measure
    # the Execution Desk currently sets stops with none of). Appended at the
    # END with a default for the same positional-fixture-safety reason as the
    # two fields above it, not inserted where it would read more naturally
    # beside `support`/`breakout`. `None` (not `0.0`) is the honest default:
    # zero volatility is a real, if implausible, ATR value, so it cannot also
    # mean "not computed" the way `period_candles: int = 0` safely can for a
    # count.
    atr14: float | None = None


def window_trend_phrase(return_pct: float, candles: int) -> str:
    """The window-trend sentence, shared by both surfaces so they cannot word
    one measurement two ways.

    "flat" rather than "up 0.0%" when it rounds to zero: NVDA measured +0.03%
    across 64 candles on 2026-08-13, and "up 0.0%" is a sentence that argues
    with itself. That case is not a rounding curiosity either — it is the whole
    point of the line. NVDA's 20/50 alignment reads `uptrend` on the same sheet,
    so an agent had a bullish label for a name that had round-tripped the entire
    quarter, and no way to see it.
    """
    if abs(return_pct) < 0.05:
        move = "flat"
    else:
        move = f"{'up' if return_pct > 0 else 'down'} {abs(return_pct)}%"
    return (
        f"{move} across the {candles} trading days of the fetched history "
        f"(first close to last close — this is the quarter-scale move, not a day move)"
    )


def range_position_pct(price: float, support: float, breakout: float) -> int | None:
    """Where `price` sits between the 50-day low and high, 0–100.

    None when the range has no width (every candle at one price), which is
    the only case where the question has no answer. `price` is the last
    close and support/breakout are the min-low/max-high over the same
    window, so it is always within the range by construction.
    """
    if breakout <= support:
        return None
    return round(100 * (price - support) / (breakout - support))


def compute_technicals(ticker: str) -> Technicals | None:
    """Real RSI/trend/volume/support-resistance from yfinance OHLCV.

    Never raises. Returns None when history is unavailable, shorter than the
    50-day lookback the trend/support/breakout reads need, or contains a
    non-finite value (NaN/inf) — yfinance's own missing-value sentinel for
    thin/recently-IPO'd/halted tickers, which a type-valid `Candle` does not
    protect against upstream (DEF052 round 2: the computation below used to
    run unguarded and `round(nan)` raised `ValueError`, failing the entire
    Room Convene — not just this agent's technicals).
    """
    try:
        sym = ticker.upper().strip()
        candles, source = history_with_source(
            get_market_data_provider(), sym, _HISTORY_PERIOD
        )
        # DEF229: the provider chain ends in a synthetic random walk so a
        # quote never fails. A quote says which leg served it; history did
        # not, so a yfinance outage substituted a fabricated series into a
        # block that asserts "Real yfinance OHLCV". Refuse it — the callers
        # already render "not available this call" for None, which is the
        # honest answer, and never the fabricated one.
        if source in SYNTHETIC_HISTORY_SOURCES:
            logger.warn("technicals_synthetic_feed_rejected", ticker=sym, source=source)
            return None
        if not candles or len(candles) < _SMA_LONG:
            return None

        closes = [c.c for c in candles]
        highs = [c.h for c in candles]
        lows = [c.low for c in candles]
        volumes = [c.v for c in candles]
        if not all(math.isfinite(v) for v in (*closes, *highs, *lows, *volumes)):
            return None

        rsi = _rsi(closes)
        if rsi is None:
            return None

        sma_short = _sma(closes, _SMA_SHORT)
        sma_long = _sma(closes, _SMA_LONG)
        if sma_short is None or sma_long is None:
            return None
        price = closes[-1]
        # The direction is computed here, so it is what gets reported (DEF227).
        # This field used to collapse both alignments into one token,
        # "trading", on this very line — so a stock at its 50-day high and a
        # stock pinned to its 52-week low rendered byte-identically, and no
        # bullish technical read was reachable on any ticker, ever. DEF052
        # (AT:R58) was right to delete the *fabricated* direction claim that
        # preceded it; this one is measured, which is the difference.
        aligned_up = price > sma_short > sma_long
        aligned_down = price < sma_short < sma_long
        if aligned_up:
            trend = "uptrend"
        elif aligned_down:
            trend = "downtrend"
        else:
            trend = "consolidating"

        recent_vol = sum(volumes[-_RECENT_VOLUME_WINDOW:]) / _RECENT_VOLUME_WINDOW
        baseline_vol = sum(volumes[-_VOLUME_BASELINE_WINDOW:]) / _VOLUME_BASELINE_WINDOW
        # The ratio the tone is a bucketing of. 1.0 when the baseline is zero —
        # the same case the tone calls "in-line", kept consistent so the number
        # and the label can never disagree.
        volume_ratio = round(recent_vol / baseline_vol, 2) if baseline_vol > 0 else 1.0
        # First close to last close over the fetched window. The candle COUNT
        # rides beside it because the window is trading days, not calendar
        # months: a holiday-shortened quarter and a full one both render as "3
        # months" and are not the same measurement. `_HISTORY_PERIOD` is the
        # ask; the count is what arrived.
        first_close = closes[0]
        return_period_pct = (
            round((price - first_close) / first_close * 100, 1) if first_close else 0.0
        )
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

        # CR219 R36 — ATR(14). `_ATR_PERIOD + 1` bars are needed (`atr`'s own
        # `period + 1` gate); the `_SMA_LONG` (50-bar) minimum already
        # enforced above this point covers that with room to spare, so this
        # can never be the reason a real fetch degrades to None — confirmed
        # against `_HISTORY_PERIOD`'s own comment (~65 candles) before
        # relying on it, not assumed.
        atr14 = _atr(highs, lows, closes, period=_ATR_PERIOD)

        return Technicals(
            rsi=round(rsi),
            rsi_tone=_rsi_tone(rsi),
            trend=trend,
            volume_tone=volume_tone,
            support=round(support, 2),
            breakout=round(breakout, 2),
            return_period_pct=return_period_pct,
            period_candles=len(closes),
            price=round(price, 2),
            sma_short=round(sma_short, 2),
            sma_long=round(sma_long, 2),
            volume_ratio=volume_ratio,
            atr14=round(atr14, 2) if atr14 is not None else None,
        )
    except Exception as exc:
        logger.warn("technicals_compute_error", ticker=ticker, error=str(exc)[:200])
        return None


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
    # DEF228: position-in-range is the single most decision-relevant fact a
    # technical read produces, and it was the one thing this block made the
    # model derive rather than stating. On live Alpha an agent got that join
    # wrong and asserted a breakdown at $3.67 with the floor at $3.18; all
    # twelve agents adopted it. State it.
    # DEF229(b): "breakout level" named the 50-day high as a trade trigger,
    # which makes the only long entry the analyst will authorise sit above
    # the 50-day high by definition. It is a level; let the agent reason.
    pct = range_position_pct(t.price, t.support, t.breakout)
    position = f" — last close ${t.price} sits at {pct}% of that range" if pct is not None else ""
    return (
        f"─── LIVE TECHNICALS — {sym} ───\n"
        f"RSI(14): {t.rsi} ({t.rsi_tone})\n"
        f"Trend: {t.trend} (price vs. 20/50-day moving averages)\n"
        # CR146 Tier B — the numbers the two labels above are bucketings of.
        # Both surfaces render them, so the Room and 1-on-1 cannot disagree
        # about what "uptrend" or "above average" meant on the same day.
        f"20-day SMA: ${t.sma_short}, 50-day SMA: ${t.sma_long}"
        + (f" — last close is {(t.price - t.sma_long) / t.sma_long * 100:+.1f}% "
           "vs the 50-day\n" if t.sma_long > 0 else "\n")
        # CR146 Tier C — same line, same wording as the Room sheet. The window
        # is stated in TRADING DAYS because 3 calendar months is not a fixed
        # number of candles, and a holiday-shortened quarter is not the same
        # measurement as a full one.
        + f"Window trend: {window_trend_phrase(t.return_period_pct, t.period_candles)}\n"
        + f"Volume: {t.volume_tone} ({t.volume_ratio:.2f}× the 20-day average, "
        f"5-day mean)\n"
        f"50-day range — low: ${t.support}, high: ${t.breakout}{position}\n"
        f"(Real yfinance OHLCV for {sym}, computed this call. Use these "
        f"numbers when discussing {sym}'s technicals. Do NOT claim MACD, a "
        f"moving-average crossover signal, or Bollinger Bands — none of "
        f"those are computed.)"
    )
