"""DEF213 guard — where to put the `window_days / n_observations` threshold.

The guard's whole job is to separate a book whose joined return grid is dense
enough for a √252 annualisation from one whose grid has holes. Both halves of
that separation have to be measured, and only one of them was measured when
DEF213 was filed:

- the GAPPY side is already in the defect row (`def213_attack2_realistic.py`:
  5% of one holding's days missing → ratio 1.47 and σ overstated 6.1%, rising to
  2.33 / +29.8% at 40%). Those runs use a synthetic weekday-only calendar, so
  their clean baseline is exactly 7/5 = 1.40.
- the CLEAN side is NOT 1.40 on a real calendar, because market holidays remove
  trading days without removing calendar days. This script measures it.

The number that matters is the MAXIMUM ratio a legitimate, hole-free book can
produce, over every window length the engine can actually consume (T_MIN=126
returns up to MAX_RETURNS=504) and over every position in the year — a window
straddling Thanksgiving→Christmas→New Year→MLK→Presidents' Day carries six
holidays and is the worst case, not the average one.

Threshold = that maximum, plus headroom. A false fire is not a cosmetic error:
it withholds every Σ-derived metric from a user whose data is fine.

Run:  .venv/bin/python ../docs/.../verification_fleet/def213_guard_threshold.py
"""

from __future__ import annotations

import statistics
import sys
import time
from datetime import datetime

sys.path.insert(0, "/Volumes/Extreme Pro/AMI_MarketApp/backend")

import yfinance as yf

from app.services.portfolio_health_constants import MAX_RETURNS, T_MIN

# The real US-equity trading calendar, taken from the instruments themselves.
# SPY is the benchmark leg every joined grid contains; the rest are a spread of
# venues and asset classes so a calendar difference would show up as a shrunken
# intersection rather than being assumed away.
TICKERS = ("SPY", "AAPL", "MSFT", "BND", "XLU", "GLD", "IWM", "TLT")
YEARS = "10y"

# Window lengths in DATES (returns = dates − 1). The engine consumes 126…504
# returns, so these are the endpoints plus a spread between them.
WINDOW_DATES = (T_MIN + 1, 200, 300, 400, MAX_RETURNS + 1)


def _closes(ticker: str) -> list[str]:
    # Yahoo throttles a burst of eight fetches and answers the throttled ones
    # with an EMPTY frame and a "possibly delisted" warning rather than an
    # error — an empty calendar would silently make the intersection tiny and
    # the measured ratio meaningless, so retry until bars actually arrive.
    for attempt in range(6):
        hist = yf.Ticker(ticker).history(period=YEARS, auto_adjust=True)
        if len(hist):
            return [d.date().isoformat() for d in hist.index]
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{ticker}: no bars after 6 attempts")


def _window_days(dates: list[str]) -> int:
    first = datetime.strptime(dates[0], "%Y-%m-%d").date()
    last = datetime.strptime(dates[-1], "%Y-%m-%d").date()
    return (last - first).days


def _sweep(dates: list[str], n_dates: int) -> tuple[float, float, str]:
    ratios: list[tuple[float, str]] = []
    for i in range(0, len(dates) - n_dates + 1):
        w = dates[i:i + n_dates]
        ratios.append((_window_days(w) / (n_dates - 1), f"{w[0]}→{w[-1]}"))
    worst = max(ratios)
    return statistics.mean(r for r, _ in ratios), worst[0], worst[1]


def main() -> int:
    print(f"fetching {len(TICKERS)} tickers, {YEARS}…")
    cal = {t: _closes(t) for t in TICKERS}
    for t, d in cal.items():
        print(f"  {t:>5} {len(d):>5} bars  {d[0]} → {d[-1]}")

    # A book joins on the intersection. If every US-equity instrument shares one
    # calendar, the intersection over the common span is lossless and the guard
    # can never fire on a clean book for calendar reasons alone.
    spans = [set(d) for d in cal.values()]
    common = set.intersection(*spans)
    lo = max(min(d) for d in cal.values())
    hi = min(max(d) for d in cal.values())
    in_span = {d for s in spans for d in s if lo <= d <= hi}
    print(f"\nintersection over the common span: {len(common)} of {len(in_span)} "
          f"distinct dates ({len(common) / len(in_span):.4%} lossless)")
    missing = sorted(in_span - common)
    if missing:
        print(f"  dates NOT shared by all {len(TICKERS)}: {missing[:10]}"
              f"{' …' if len(missing) > 10 else ''}")

    grid = sorted(common)
    print(f"\nclean-book ratio on {len(grid)} real trading days:")
    print(f"{'n_ret':>6} {'windows':>8} {'mean':>7} {'MAX':>7}  worst window")
    overall = 0.0
    for n_dates in WINDOW_DATES:
        if n_dates > len(grid):
            continue
        mean, mx, where = _sweep(grid, n_dates)
        overall = max(overall, mx)
        print(f"{n_dates - 1:>6} {len(grid) - n_dates + 1:>8} "
              f"{mean:>7.4f} {mx:>7.4f}  {where}")

    print(f"\nworst clean-book ratio anywhere: {overall:.4f}")

    # The 10-year sample above contains only SINGLE-day extraordinary closures
    # (Bush 2018-12-05, Carter 2025-01-09). The tail that actually threatens a
    # false fire is a MULTI-day closure — 9/11 shut the market for four
    # sessions, Sandy for two — because those remove trading days from a span
    # without removing calendar days, which is exactly the signal the guard
    # reads, and a book holding nothing but clean instruments would still see it.
    #
    # Those two events are outside the fetchable window: Yahoo's free endpoint
    # caps this ticker at ~10 years today (`period="20y"`, `period="30y"` and any
    # explicit pre-2016 `start` all answer with an EMPTY frame, not an error).
    # So the tail is CONSTRUCTED, not observed: take the real calendar above and
    # delete a block of L consecutive sessions at every position, which is
    # precisely the shape a closure has. Stated as a construction because it is
    # one — nothing below was measured on 2001 or 2012 data.
    print(f"\n{'─' * 60}")
    print("constructed extraordinary-closure tail (real calendar, sessions removed)")
    ords = [datetime.strptime(d, "%Y-%m-%d").date().toordinal() for d in grid]
    print(f"{'closure':>8} {'n_ret':>6} {'MAX':>7}  worst window")
    tail = overall
    for closure in (2, 4, 5):          # Sandy; 9/11; a week, longer than any US closure since 1933
        for n_dates in WINDOW_DATES:
            if n_dates + closure > len(ords):
                continue
            worst, at = 0.0, ""
            # A window still holding n_dates observations after L sessions are
            # deleted from inside it reaches L further along the ORIGINAL
            # calendar. Any start i admits such a cut (anywhere strictly inside
            # the window), so the maximum is a single pass, not a double sweep.
            for i in range(0, len(ords) - n_dates - closure + 1):
                span = ords[i + n_dates - 1 + closure] - ords[i]
                r = span / (n_dates - 1)
                if r > worst:
                    worst, at = r, f"{grid[i]}→{grid[i + n_dates - 1 + closure]}"
            tail = max(tail, worst)
            print(f"{closure:>8} {n_dates - 1:>6} {worst:>7.4f}  {at}")

    print(f"\nworst clean-book ratio incl. constructed closures: {tail:.4f}")
    for pad in (0.05, 0.10, 0.15):
        print(f"  +{pad:.0%} headroom → threshold {tail * (1 + pad):.4f}")

    # What the guard would then CATCH: one holding of a book missing a fraction
    # of its days thins the joined grid by that fraction (`_join` intersects),
    # so the ratio scales as clean/(1−gap). Solved against each candidate.
    clean = statistics.mean([_sweep(grid, n)[0] for n in WINDOW_DATES])
    print(f"\nmean clean ratio {clean:.4f} — smallest single-holding gap caught:")
    for pad in (0.05, 0.10, 0.15):
        thr = tail * (1 + pad)
        print(f"  threshold {thr:.4f} → fires above {1 - clean / thr:.1%} missing days")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
