"""Technical indicators — RSI, SMA, ATR, EMA, Bollinger bands, MACD, and an
RSI overbought/oversold tone.

Pure functions over a list of close (and, for ATR, high/low) prices. Ported
verbatim from app/services/technicals.py (DEF052) so the computation is
reusable and testable in isolation; technicals.py keeps the yfinance I/O and
re-exports these names.

CR046 Decision D1 (see library_survey.md): `rsi` is **Cutler's RSI** — a *simple*
average of gains/losses over the period, NOT Wilder's smoothing. This is
deliberate and load-bearing: every mainstream TA library (ta, pandas-ta, TA-Lib)
defaults to Wilder's, which yields different numbers, so we hand-roll rather than
adopt a library for this family. Don't "upgrade" it to Wilder without re-baselining
test_technicals.py.

CR219 R36: `atr` follows the same simple-average convention for the same
reason, deliberately — see its own docstring.
"""

from __future__ import annotations

import math

DEFAULT_RSI_PERIOD = 14


def rsi(closes: list[float], period: int = DEFAULT_RSI_PERIOD) -> float | None:
    """Cutler's RSI — simple average of gains/losses over `period`.

    Returns None when fewer than `period + 1` closes are available to diff, and
    100.0 when the window has no losses (RSI's defined ceiling).
    """
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


def rsi_tone(value: float) -> str:
    if value >= 70:
        return "overbought"
    if value <= 30:
        return "oversold"
    return "neither overbought nor oversold"


def sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def atr(
    highs: list[float], lows: list[float], closes: list[float],
    period: int = 14,
) -> float | None:
    """Average True Range — a **simple** mean of True Range over `period`,
    not Wilder's smoothing (CR219 R36).

    True Range for session i is `max(high[i]-low[i], |high[i]-close[i-1]|,
    |low[i]-close[i-1]|)` — the widest of today's own range and either gap
    against yesterday's close, so a gap-open session reads as volatile even
    when its own high-low range is narrow.

    Simple average, matching this module's OWN CR046 Decision D1 for `rsi`
    above (Cutler's, deliberately not Wilder's): the two indicators sitting
    on one sheet should not silently use two different smoothing
    conventions without a stated reason, and nothing about ATR's use here
    (stop-sizing context for the Execution/Risk lanes) argues for one. A
    future ATR consumer that specifically needs Wilder's should say so and
    add a second function, the same way `rsi`/Wilder's would be a second
    function rather than a silent change to this one.

    Requires `period + 1` bars (the extra bar supplies the first
    previous-close) — the same `period + 1` gate `rsi` uses, for the same
    reason: `period` deltas need `period + 1` points. Returns None when the
    three lists disagree in length (a caller error, not a data gap) or don't
    reach that minimum.
    """
    if not (len(highs) == len(lows) == len(closes)):
        return None
    if len(closes) < period + 1:
        return None
    true_ranges: list[float] = []
    for i in range(1, len(closes)):
        true_ranges.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        ))
    return sum(true_ranges[-period:]) / period


def _ema_series(values: list[float], window: int) -> list[float] | None:
    """The full EMA series, seeded with the SMA of the first `window` points.

    None when fewer than `window` points exist. The SMA seed is the
    mainstream convention (TA-Lib, pandas) and, unlike a first-point seed, it
    does not bake one arbitrary close into every later value — a difference
    that is largest exactly where our history is shortest. Documented rather
    than chosen silently because CR046 D1 already pins this module's
    simple-average RSI/ATR convention: EMA is a different family with its own
    standard, and MACD's signal line is only coherent as an EMA.
    """
    if len(values) < window:
        return None
    k = 2.0 / (window + 1)
    seed = sum(values[:window]) / window
    out = [seed]
    for v in values[window:]:
        out.append((v - out[-1]) * k + out[-1])
    return out


def ema(values: list[float], window: int) -> float | None:
    """The last EMA value, or None when `window` points do not exist."""
    series = _ema_series(values, window)
    return series[-1] if series else None


def bollinger_bands(
    closes: list[float], window: int = 20, num_std: float = 2.0,
) -> tuple[float, float, float] | None:
    """Bollinger bands over the last `window` closes: (middle, upper, lower).

    The middle is the same simple average `sma` returns; the bands are the
    middle ± `num_std` POPULATION standard deviations of that same window —
    the conventional Bollinger calculation (population, not sample: the
    window is the whole population being described, not a draw from it).
    None when fewer than `window` closes exist.
    """
    if len(closes) < window:
        return None
    window_closes = closes[-window:]
    middle = sum(window_closes) / window
    variance = sum((c - middle) ** 2 for c in window_closes) / window
    half_width = num_std * math.sqrt(variance)
    return middle, middle + half_width, middle - half_width


def macd(
    closes: list[float],
    fast: int = 12, slow: int = 26, signal: int = 9,
) -> tuple[float, float, float] | None:
    """MACD (fast/slow EMAs, EMA signal line): (macd line, signal, histogram).

    None when the series is too short for a signal value: the MACD line
    exists once the slow EMA seeds (`slow` bars), and the signal is an EMA
    over `signal` MACD values, so the minimum is `slow + signal - 1` bars.
    The histogram is the MACD line minus the signal — the two never get out
    of step, because both are read off the same final bar.
    """
    if len(closes) < slow + signal - 1:
        return None
    fast_series = _ema_series(closes, fast)
    slow_series = _ema_series(closes, slow)
    assert fast_series is not None and slow_series is not None
    macd_series = [f - s for f, s in zip(fast_series[-len(slow_series):], slow_series, strict=True)]
    signal_series = _ema_series(macd_series, signal)
    assert signal_series is not None
    macd_line = macd_series[-1]
    signal_line = signal_series[-1]
    return macd_line, signal_line, macd_line - signal_line
