"""Technical indicators — RSI, SMA, and an RSI overbought/oversold tone.

Pure functions over a list of close prices. Ported verbatim from
app/services/technicals.py (DEF052) so the computation is reusable and testable
in isolation; technicals.py keeps the yfinance I/O and re-exports these names.

CR046 Decision D1 (see library_survey.md): `rsi` is **Cutler's RSI** — a *simple*
average of gains/losses over the period, NOT Wilder's smoothing. This is
deliberate and load-bearing: every mainstream TA library (ta, pandas-ta, TA-Lib)
defaults to Wilder's, which yields different numbers, so we hand-roll rather than
adopt a library for this family. Don't "upgrade" it to Wilder without re-baselining
test_technicals.py.
"""

from __future__ import annotations

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
