"""Attack 2, swept: 24 independent price paths, four arms each.

One seed is an anecdote — the two arms draw their EWMA window from the same path
over different calendar spans, so part of any single-seed gap is sampling noise.
This reports the distribution, and includes a phase-shifted thinning (odd days
instead of even) so a result cannot be an artefact of WHICH days were kept.

Arm D re-annualises the thinned grid by its true period length (126 two-day
periods per year instead of 252 daily ones) — not a proposed fix, just evidence
that the gap is the annualisation constant and not something about the path.
"""

from __future__ import annotations

import math
import random
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, "/Volumes/Extreme Pro/AMI_MarketApp/backend")

from app.services.portfolio_health import compute_health
from app.services.portfolio_health_constants import BENCHMARK_TICKER

SIGMA_DAILY = 0.012
N_DAYS = 320
TICKERS = ("AAA", "BBB")
SEEDS = range(24)


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


def run(grid: list[str], closes: dict[str, list[float]], keep: list[int]) -> dict:
    series = {n: [(grid[i], v[i]) for i in keep] for n, v in closes.items()}
    return compute_health(
        holdings=[(t, 10.0) for t in TICKERS],
        marks={t: 100.0 for t in TICKERS},
        cash=0.0,
        series=series,
        sector_of=lambda t: "Tech",
        etf_tickers=frozenset(),
        as_of=grid[keep[-1]],
    )["blocks"]["portfolio_volatility"]


def main() -> int:
    grid = weekdays(N_DAYS)
    rows = []
    for seed in SEEDS:
        market = walk(1000 + seed, N_DAYS, sigma=0.009, market=None, beta=0.0)
        closes = {BENCHMARK_TICKER: market}
        for k, t in enumerate(TICKERS):
            closes[t] = walk(seed * 10 + k, N_DAYS, sigma=SIGMA_DAILY,
                             market=market, beta=1.0 + 0.2 * k)

        daily = run(grid, closes, list(range(N_DAYS)))
        even = run(grid, closes, list(range(0, N_DAYS, 2)))
        odd = run(grid, closes, list(range(1, N_DAYS, 2)))
        if not (daily["sufficient"] and even["sufficient"] and odd["sufficient"]):
            print(f"seed {seed}: an arm came back insufficient — skipped")
            continue
        rows.append((
            seed,
            daily["value"],
            even["value"],
            odd["value"],
            even["value"] / daily["value"],
            odd["value"] / daily["value"],
            # arm D: the same thinned estimate re-annualised by its true period
            # count. sqrt(252) is baked into the engine, so undo and redo it.
            even["value"] / math.sqrt(252) * math.sqrt(126) / daily["value"],
        ))

    print(f"{'seed':>4} {'daily%':>8} {'even%':>8} {'odd%':>8} "
          f"{'even/d':>7} {'odd/d':>7} {'D re-ann':>9}")
    for r in rows:
        print(f"{r[0]:>4} {r[1] * 100:>8.2f} {r[2] * 100:>8.2f} {r[3] * 100:>8.2f} "
              f"{r[4]:>7.3f} {r[5]:>7.3f} {r[6]:>9.3f}")

    for name, idx in (("even/daily", 4), ("odd/daily", 5), ("D re-annualised", 6)):
        vals = [r[idx] for r in rows]
        print(f"\n{name}: n={len(vals)}  mean={statistics.mean(vals):.4f}  "
              f"median={statistics.median(vals):.4f}  "
              f"min={min(vals):.4f}  max={max(vals):.4f}  "
              f"sd={statistics.stdev(vals):.4f}")
        print(f"  arms above 1.0: {sum(1 for v in vals if v > 1.0)}/{len(vals)}")

    pp = [(r[2] - r[1]) * 100 for r in rows]
    print(f"\nabsolute overstatement, percentage points: mean={statistics.mean(pp):+.2f}pp  "
          f"min={min(pp):+.2f}pp  max={max(pp):+.2f}pp")
    print(f"sqrt(2) = {math.sqrt(2):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
