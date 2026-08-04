"""AUD probe: does the guard's ratio track the sigma bias for a CONTIGUOUS hole?

His `_book_thinned` spreads the missing days EVENLY. A real feed gap is
clustered: a trading halt, a delisting pause, an outage. Construction here is
deliberately different from his: the TRUE price path is generated once on the
full grid and then SUBSAMPLED, so the underlying asset is literally identical
between clean and gappy and the only thing that changes is which days the feed
reported. That is what makes the sigma comparison meaningful.
"""
import sys
sys.path.insert(0, ".")
sys.path.insert(0, "tests/unit")

import random
from datetime import date, timedelta
from app.services.portfolio_health import compute_health
from app.services.portfolio_health_constants import GRID_DENSITY_MAX

TICKERS = ("AAA", "BBB", "CCC")
BM = "SPY"


def dates(n, end=date(2026, 7, 31)):
    out, cur = [], end
    while len(out) < n:
        if cur.weekday() < 5:
            out.append(cur)
        cur -= timedelta(days=1)
    return [d.isoformat() for d in reversed(out)]


def true_series(seed, grid, sigma=0.010, market=None, beta=0.0):
    rnd = random.Random(seed)
    closes = [100.0]
    for i in range(1, len(grid)):
        shock = rnd.gauss(0.0, sigma)
        if market is not None:
            shock += beta * (market[i] / market[i - 1] - 1.0)
        closes.append(closes[-1] * (1.0 + shock))
    return dict(zip(grid, closes))


def book(total, keep_dates_for_aaa):
    """One TRUE path per name on the full grid; AAA's feed reports a subset."""
    grid = dates(total)
    mkt = true_series(1, grid, sigma=0.009)
    mkt_list = [mkt[d] for d in grid]
    truth = {t: true_series(11 + i, grid, sigma=0.010, market=mkt_list,
                            beta=1.0 + 0.2 * i) for i, t in enumerate(TICKERS)}
    series = {}
    for t in TICKERS:
        seen = keep_dates_for_aaa if t == TICKERS[0] else grid
        series[t] = [(d, truth[t][d]) for d in seen]
    series[BM] = [(d, mkt[d]) for d in grid]
    return {
        "holdings": [(t, 10.0) for t in TICKERS],
        "marks": {t: 100.0 for t in TICKERS},
        "cash": 0.0, "series": series,
        "sector_of": lambda t: "Tech", "etf_tickers": frozenset(),
        "as_of": grid[-1],
    }


def report(label, payload):
    v = payload["blocks"]["portfolio_volatility"]
    ratio = v["window_days"] / v["n_observations"] if v["n_observations"] else 0
    return (label, v["n_observations"], round(ratio, 4), v["sufficient"],
            v["insufficient_cause"], v["value"],
            payload["dropped_holdings"], v["partial"])


TOTAL = 500
grid = dates(TOTAL)

rows = [report("clean", compute_health(**book(TOTAL, grid)))]
clean_sigma = rows[0][5]

# One contiguous hole of L sessions in the middle of AAA's feed.
for L in (10, 20, 40, 60, 75, 90, 120):
    cut = set(grid[200:200 + L])
    rows.append(report(f"hole L={L}", compute_health(**book(TOTAL, [d for d in grid if d not in cut]))))

# Even thinning, same number of missing days, for the direct comparison.
for L in (40, 75, 120):
    step = TOTAL / L
    cut = {grid[min(TOTAL - 2, int(i * step) + 1)] for i in range(L)}
    rows.append(report(f"even  n={len(cut)}", compute_health(**book(TOTAL, [d for d in grid if d not in cut]))))

print(f"GRID_DENSITY_MAX = {GRID_DENSITY_MAX}")
print(f"{'case':<14}{'obs':>5}{'ratio':>8}{'suff':>7}{'cause':>14}{'sigma':>9}{'vs clean':>10}  dropped/partial")
for lbl, n, ratio, suff, cause, val, dropped, partial in rows:
    bias = f"{(val / clean_sigma - 1) * 100:+.1f}%" if (val and clean_sigma) else "-"
    print(f"{lbl:<14}{n:>5}{ratio:>8.4f}{str(suff):>7}{str(cause):>14}"
          f"{(f'{val:.4f}' if val else '-'):>9}{bias:>10}  {len(dropped)}/{partial}")
