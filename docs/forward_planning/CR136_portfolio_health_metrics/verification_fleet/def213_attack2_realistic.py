"""Attack 2, reachability: ONE thinly-traded holding, the rest of the book clean.

Every-other-day is the clean boundary case; it is not what a real feed does. This
arm drops a fraction of ONE holding's days at random and leaves the other two and
the benchmark complete — which is what a thinly-traded name, a halted session, or
a feed with holes looks like.

The point is the amplification: `_join` intersects, so ONE gappy series thins the
grid every metric in the book is computed on. 12 seeds per gap fraction.
"""

from __future__ import annotations

import random
import statistics
import sys
from datetime import date, timedelta

sys.path.insert(0, "/Volumes/Extreme Pro/AMI_MarketApp/backend")

from app.services.portfolio_health import compute_health
from app.services.portfolio_health_constants import BENCHMARK_TICKER

N_DAYS = 420
TICKERS = ("AAA", "BBB", "CCC")
GAPS = (0.0, 0.05, 0.10, 0.20, 0.40)
SEEDS = range(12)


def weekdays(n: int, *, end: date = date(2026, 7, 31)) -> list[str]:
    out: list[date] = []
    cursor = end
    while len(out) < n:
        if cursor.weekday() < 5:
            out.append(cursor)
        cursor -= timedelta(days=1)
    return [d.isoformat() for d in reversed(out)]


def walk(seed: int, n: int, *, sigma: float, market: list[float] | None,
         beta: float) -> list[float]:
    rnd = random.Random(seed)
    closes = [100.0]
    for i in range(1, n):
        shock = rnd.gauss(0.0, sigma)
        if market is not None:
            shock += beta * (market[i] / market[i - 1] - 1.0)
        closes.append(closes[-1] * (1.0 + shock))
    return closes


def main() -> int:
    grid = weekdays(N_DAYS)
    print(f"{'gap':>6} {'n':>3} {'sigma%':>8} {'vs 0%':>7} {'n_obs':>6} "
          f"{'win_d':>6} {'w/n':>5} {'dropped':>8} {'partial':>8}")
    baseline: dict[int, float] = {}
    for gap in GAPS:
        sigmas, ratios, nobs, wins, dropped, partials = [], [], [], [], [], []
        for seed in SEEDS:
            market = walk(1000 + seed, N_DAYS, sigma=0.009, market=None, beta=0.0)
            closes = {BENCHMARK_TICKER: market}
            for k, t in enumerate(TICKERS):
                closes[t] = walk(seed * 10 + k, N_DAYS, sigma=0.012,
                                 market=market, beta=1.0 + 0.2 * k)

            rnd = random.Random(90000 + seed)
            thin = {i for i in range(1, N_DAYS - 1) if rnd.random() < gap}
            series = {}
            for name, vals in closes.items():
                idx = [i for i in range(N_DAYS)
                       if not (name == TICKERS[0] and i in thin)]
                series[name] = [(grid[i], vals[i]) for i in idx]

            blocks = compute_health(
                holdings=[(t, 10.0) for t in TICKERS],
                marks={t: 100.0 for t in TICKERS},
                cash=0.0,
                series=series,
                sector_of=lambda t: "Tech",
                etf_tickers=frozenset(),
                as_of=grid[-1],
            )["blocks"]
            v = blocks["portfolio_volatility"]
            if not v["sufficient"]:
                continue
            sigmas.append(v["value"])
            nobs.append(v["n_observations"])
            wins.append(v["window_days"])
            dropped.append(len(v["dropped_holdings"]))
            partials.append(1 if v["partial"] else 0)
            if gap == 0.0:
                baseline[seed] = v["value"]
            elif seed in baseline:
                ratios.append(v["value"] / baseline[seed])

        if not sigmas:
            print(f"{gap:>6.0%} — every seed came back insufficient")
            continue
        r = statistics.mean(ratios) if ratios else 1.0
        print(f"{gap:>6.0%} {len(sigmas):>3} {statistics.mean(sigmas) * 100:>8.2f} "
              f"{r:>7.3f} {statistics.mean(nobs):>6.0f} {statistics.mean(wins):>6.0f} "
              f"{statistics.mean(wins) / statistics.mean(nobs):>5.2f} "
              f"{statistics.mean(dropped):>8.2f} {statistics.mean(partials):>8.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
