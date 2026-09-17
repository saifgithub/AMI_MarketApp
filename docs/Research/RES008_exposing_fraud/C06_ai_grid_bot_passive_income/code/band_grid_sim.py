"""
Band-grid ("blown account") simulator — Mechanism 2 of C06's PREREGISTRATION.md.

Bollinger(20,2) on close (SMA20 +/- 2*rolling-std20) and ATR(14) as the simple
(unweighted) rolling mean of True Range over 14 bars -- the spec names "ATR(14)"
without specifying Wilder vs. simple smoothing; the simple rolling mean is the
more literal reading of "ATR(14)" as a 14-bar average and is recorded in
../out/DEVIATIONS.md.

Signals are computed on a bar's close and fill at the next bar's open (the
house default execution timing, per PREREG_COMMON.md, applied here since the
mechanism's own description ties fills to closes without stating a timing --
also recorded in DEVIATIONS.md): a close beyond the band starts (or, if a
basket beyond that side is open and the new close is a FURTHER extension at
least one ATR(14) past the last add's own close) adds to a basket; a close
back at-or-past the 20-bar mean closes the whole basket at the next bar's
open. No stop.

Two sizings: constant-unit (every add is the same notional) and 1.5x
martingale (each add is 1.5x the previous add's notional), both applied to a
fixed unit-notional-per-add expressed as a fraction of STARTING equity (the
spec's own "our assumption, disclosed"). FX cost is 2 bps per side, charged
on the notional of each add and on the notional closed out.

Equity is marked at every bar's close for reporting, and additionally at the
bar's worst point (the price most adverse to the open basket within that
bar's assumed intrabar range) purely to check ruin -- equity <= 20% of
starting equity -- which ends the run at that bar without waiting for the
close.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

FX_COST_BPS = 2.0
RUIN_FRACTION = 0.20
BOLLINGER_WINDOW = 20
BOLLINGER_STD = 2.0
ATR_WINDOW = 14
MARTINGALE_MULT = 1.5


def bollinger_bands(close: pd.Series, window: int = BOLLINGER_WINDOW, n_std: float = BOLLINGER_STD):
    mid = close.rolling(window).mean()
    std = close.rolling(window).std(ddof=0)
    upper = mid + n_std * std
    lower = mid - n_std * std
    return mid, upper, lower


def average_true_range(bars: pd.DataFrame, window: int = ATR_WINDOW) -> pd.Series:
    high, low, close = bars["high"], bars["low"], bars["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(window).mean()


@dataclass
class Add:
    side: int
    qty: float
    price: float
    notional: float


@dataclass
class BandGridRunResult:
    basket_pnls: list[float] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series, repr=False)
    monthly_returns: list[float] = field(default_factory=list)
    ruined: bool = False
    ruin_bar: int | None = None
    ruin_date: pd.Timestamp | None = None
    n_baskets_closed: int = 0
    n_baskets_won: int = 0


def _unit_size(equity0: float, unit_frac: float, sizing: str, add_index: int) -> float:
    base = equity0 * unit_frac
    if sizing == "constant":
        return base
    if sizing == "martingale":
        return base * (MARTINGALE_MULT**add_index)
    raise ValueError(f"unknown sizing {sizing!r}")


def run_band_grid(
    bars: pd.DataFrame,
    equity0: float,
    unit_frac: float,
    sizing: str,
    fx_cost_bps: float = FX_COST_BPS,
    ruin_fraction: float = RUIN_FRACTION,
) -> BandGridRunResult:
    """Simulate one band-grid run starting at the first row of `bars`.

    `bars` must already include enough lead-in history before the run's
    official start for the Bollinger/ATR windows to be valid; the run itself
    is understood to begin at the first bar where a signal can act on it
    (callers slice `bars` so its first row is the run's start date, with
    prior bars included only for the indicator warm-up).
    """
    close = bars["close"]
    mid, upper, lower = bollinger_bands(close)
    atr = average_true_range(bars)
    fee_rate = fx_cost_bps / 10_000.0

    cash = equity0
    basket: list[Add] = []
    basket_side = 0
    result = BandGridRunResult()

    equity_curve = np.empty(len(bars))
    month_marks: dict[tuple[int, int], float] = {}

    def basket_notional_value(price: float) -> float:
        return sum(a.qty * price * basket_side for a in basket) if basket else 0.0

    def basket_cost_value() -> float:
        return sum(a.qty * a.price * basket_side for a in basket) if basket else 0.0

    def mark_equity(price: float) -> float:
        if not basket:
            return cash
        unrealized = basket_notional_value(price) - basket_cost_value()
        return cash + unrealized

    pending_add: tuple[int, int] | None = None
    pending_close = False

    for i in range(len(bars)):
        row = bars.iloc[i]
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]

        if pending_close and basket:
            fill_price = o
            gross_pnl = basket_notional_value(fill_price) - basket_cost_value()
            close_notional = sum(a.qty * fill_price for a in basket)
            fee = close_notional * fee_rate
            realized = gross_pnl - fee
            cash += realized
            result.basket_pnls.append(realized)
            result.n_baskets_closed += 1
            if realized > 0:
                result.n_baskets_won += 1
            basket = []
            basket_side = 0
        pending_close = False

        if pending_add is not None:
            side, add_index = pending_add
            fill_price = o
            unit_notional = _unit_size(equity0, unit_frac, sizing, add_index)
            qty = unit_notional / fill_price
            fee = unit_notional * fee_rate
            cash -= fee
            basket.append(Add(side=side, qty=qty, price=fill_price, notional=unit_notional))
            basket_side = side
        pending_add = None

        worst_price = l if basket_side >= 0 else h
        if basket:
            worst_equity = cash + (basket_notional_value(worst_price) - basket_cost_value())
        else:
            worst_equity = cash
        if worst_equity <= ruin_fraction * equity0 and not result.ruined:
            result.ruined = True
            result.ruin_bar = i
            result.ruin_date = bars.index[i]
            equity_curve[i] = worst_equity
            result.equity_curve = pd.Series(equity_curve[: i + 1], index=bars.index[: i + 1])
            _finalize_monthly(result, month_marks)
            return result

        if pd.notna(upper.iloc[i]) and pd.notna(lower.iloc[i]) and pd.notna(mid.iloc[i]):
            if basket:
                crossed_back = (
                    (basket_side == 1 and c >= mid.iloc[i])
                    or (basket_side == -1 and c <= mid.iloc[i])
                )
                if crossed_back:
                    pending_close = True
                elif pd.notna(atr.iloc[i]) and atr.iloc[i] > 0:
                    last_add_price = basket[-1].price
                    if basket_side == 1 and c < lower.iloc[i] and (last_add_price - c) >= atr.iloc[i]:
                        pending_add = (1, len(basket))
                    elif basket_side == -1 and c > upper.iloc[i] and (c - last_add_price) >= atr.iloc[i]:
                        pending_add = (-1, len(basket))
            else:
                if c > upper.iloc[i]:
                    pending_add = (-1, 0)
                elif c < lower.iloc[i]:
                    pending_add = (1, 0)

        equity = mark_equity(c)
        equity_curve[i] = equity

        key = (bars.index[i].year, bars.index[i].month)
        month_marks[key] = equity

    result.equity_curve = pd.Series(equity_curve, index=bars.index)
    _finalize_monthly(result, month_marks)
    return result


def _finalize_monthly(result: BandGridRunResult, month_marks: dict[tuple[int, int], float]) -> None:
    keys = sorted(month_marks.keys())
    if len(keys) < 2:
        return
    values = [month_marks[k] for k in keys]
    rets = [values[i] / values[i - 1] - 1.0 for i in range(1, len(values))]
    result.monthly_returns = rets
