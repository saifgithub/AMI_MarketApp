"""Measures CR136-M04 Attack 2: a non-contiguous joined grid annualised as if daily.

The claim under test is directional only ("an overstated sigma, silently"), and the
auditor declined to grade a severity off a direction. This produces the number.

Design: ONE underlying daily price process, measured twice.
  control    every holding observed on every trading day  -> joined grid is daily
  treatment  the SAME closes, with alternate trading days removed -> the joined
             grid is every other trading day, so each consecutive ratio spans two
             trading days while `annualize_vol` still multiplies by sqrt(252)

Nothing about the underlying volatility differs between the two arms; only the
observation grid does. Any gap between the two reported sigmas is the defect.
"""

from __future__ import annotations

import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve()))
sys.path.insert(0, "/Volumes/Extreme Pro/AMI_MarketApp/backend")

from app.services.portfolio_health import compute_health
from app.services.portfolio_health_constants import BENCHMARK_TICKER

SIGMA_DAILY = 0.012
N_DAYS = 320
TICKERS = ("AAA", "BBB")


def weekdays(n: int, *, end: date = date(2026, 7, 31)) -> list[str]:
    out: list[date] = []
    cursor = end
    while len(out) < n:
        if cursor.weekday() < 5:
            out.append(cursor)
        cursor -= timedelta(days=1)
    return [d.isoformat() for d in reversed(out)]


def walk(seed: int, grid: list[str], *, sigma: float, market: list[float] | None,
         beta: float) -> list[float]:
    rnd = random.Random(seed)
    closes = [100.0]
    for i in range(1, len(grid)):
        shock = rnd.gauss(0.0, sigma)
        if market is not None:
            shock += beta * (market[i] / market[i - 1] - 1.0)
        closes.append(closes[-1] * (1.0 + shock))
    return closes


def realised_daily_sigma(closes: list[float]) -> float:
    """The truth the engine is trying to estimate, on the FULL daily path."""
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var)


def book(grid: list[str], closes: dict[str, list[float]], *, stride: int) -> dict:
    """`stride=1` keeps every trading day; `stride=2` keeps every other one.

    The kept closes are the SAME numbers in both arms — this thins the
    observation grid, it does not regenerate the path."""
    keep = list(range(0, len(grid), stride))
    series = {
        name: [(grid[i], vals[i]) for i in keep]
        for name, vals in closes.items()
    }
    return {
        "holdings": [(t, 10.0) for t in TICKERS],
        "marks": {t: 100.0 for t in TICKERS},
        "cash": 0.0,
        "series": series,
        "sector_of": lambda t: "Tech",
        "etf_tickers": frozenset(),
        "as_of": grid[keep[-1]],
    }


def main() -> int:
    grid = weekdays(N_DAYS)
    market = walk(1, grid, sigma=0.009, market=None, beta=0.0)
    closes: dict[str, list[float]] = {BENCHMARK_TICKER: market}
    for k, t in enumerate(TICKERS):
        closes[t] = walk(11 + k, grid, sigma=SIGMA_DAILY, market=market, beta=1.0 + 0.2 * k)

    truth = {t: realised_daily_sigma(closes[t]) * math.sqrt(252) for t in TICKERS}
    print("underlying, annualised from the FULL daily path:")
    for t, s in truth.items():
        print(f"  {t}  {s * 100:.2f}%")

    out = {}
    for label, stride in (("control (every trading day)", 1),
                          ("treatment (every OTHER trading day)", 2)):
        payload = compute_health(**book(grid, closes, stride=stride))
        vol = payload["blocks"]["portfolio_volatility"]
        beta = payload["blocks"]["beta"]
        out[stride] = vol
        print(f"\n{label}")
        print(f"  status                {payload['status']}")
        print(f"  sufficient            {vol['sufficient']}  cause={vol['insufficient_cause']}")
        print(f"  n_observations        {vol['n_observations']}")
        print(f"  window_days           {vol['window_days']}")
        print(f"  reported sigma_ann    {None if vol['value'] is None else f'{vol['value'] * 100:.2f}%'}")
        print(f"  reported beta         {beta['value']}")
        print(f"  dropped_holdings      {vol['dropped_holdings']}")
        print(f"  partial               {vol['partial']}")

    a, b = out[1]["value"], out[2]["value"]
    if a and b:
        print(f"\noverstatement  {b / a:.4f}x   ({(b / a - 1) * 100:+.1f}%)")
        print(f"sqrt(2)        {math.sqrt(2):.4f}x   (the prediction if every joined "
              "return spans exactly two trading days)")
        print(f"absolute       {a * 100:.2f}%  ->  {b * 100:.2f}%   "
              f"({(b - a) * 100:+.2f} percentage points)")
    print("\ndiagnostic the engine ALREADY has and does not check:")
    for stride in (1, 2):
        v = out[stride]
        if v["n_observations"]:
            print(f"  stride {stride}: window_days/n_observations = "
                  f"{v['window_days'] / v['n_observations']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
