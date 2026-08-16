#!/usr/bin/env python3
"""
Sector-stratified random ticker sampler.

Picks N tickers spread across GICS sectors so a batch run exercises genuinely
different accounting shapes -- banks (no gross margin, deposits as liabilities),
REITs (FFO, huge depreciation), utilities (regulated, heavy debt), energy
(cyclical, impairments) -- not just 100 flavours of large-cap tech. That is the
point of the exercise: data-layer bugs hide in the sectors you don't sample.

Two allocation modes:
  proportional  -- mirrors the index weight by count (default). Realistic mix.
  equal         -- same count per sector, remainder spread round-robin. Better
                   for BUG HUNTING, because it over-samples the small, weird
                   sectors (Energy, Materials, Real Estate) where the collector
                   is most likely to break.

Universe is cached at data/sp500_universe.csv so runs don't depend on Wikipedia
being reachable. --refresh re-fetches it.

Usage:
    python3 sample_universe.py -n 100                    # proportional, random seed
    python3 sample_universe.py -n 100 --mode equal --seed 42
    python3 sample_universe.py -n 100 --out data/batch1.csv
    python3 sample_universe.py -n 100 --plain            # bare tickers, pipeable
    python3 sample_universe.py --refresh -n 20
"""
import argparse
import io
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "data", "sp500_universe.csv")
WIKI = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def fetch_universe():
    """Scrape the S&P 500 constituent table. Needs a real UA -- Wikipedia
    returns 403 to pandas' default urllib user-agent."""
    import requests
    r = requests.get(WIKI, headers={"User-Agent": "Mozilla/5.0 (research)"},
                     timeout=30)
    r.raise_for_status()
    t = pd.read_html(io.StringIO(r.text))[0]
    t = t.rename(columns={"Symbol": "ticker", "Security": "name",
                          "GICS Sector": "sector",
                          "GICS Sub-Industry": "industry"})
    t = t[["ticker", "name", "sector", "industry"]]
    # BRK.B / BF.B use dots on Wikipedia but dashes on Yahoo.
    t["ticker"] = t["ticker"].str.replace(".", "-", regex=False)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    t.to_csv(CACHE, index=False)
    return t


def load_universe(refresh=False):
    if refresh or not os.path.exists(CACHE):
        return fetch_universe()
    return pd.read_csv(CACHE)


def allocate(sectors, n, mode):
    """Decide how many names to draw from each sector."""
    counts = sectors.value_counts()
    names = list(counts.index)
    if mode == "equal":
        base, rem = divmod(n, len(names))
        alloc = {s: min(base, counts[s]) for s in names}
        # Spread the remainder over the sectors that still have headroom,
        # smallest-first so thin sectors are not starved.
        for s in sorted(names, key=lambda x: counts[x]):
            if rem <= 0:
                break
            if alloc[s] < counts[s]:
                alloc[s] += 1
                rem -= 1
    else:
        # Largest-remainder apportionment: floor each share, then hand out the
        # leftovers to the biggest fractional parts. Keeps the total exactly n.
        exact = {s: n * counts[s] / counts.sum() for s in names}
        alloc = {s: int(exact[s]) for s in names}
        rem = n - sum(alloc.values())
        for s in sorted(names, key=lambda x: exact[x] - int(exact[x]),
                        reverse=True):
            if rem <= 0:
                break
            if alloc[s] < counts[s]:
                alloc[s] += 1
                rem -= 1
    # Every sector gets at least one name, so no sector is silently absent.
    for s in names:
        if alloc[s] == 0 and counts[s] > 0:
            alloc[s] = 1
    return alloc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", "--count", type=int, default=100)
    ap.add_argument("--mode", choices=["proportional", "equal"],
                    default="proportional")
    ap.add_argument("--seed", type=int, default=None,
                    help="fix for a reproducible sample")
    ap.add_argument("--refresh", action="store_true",
                    help="re-scrape the universe from Wikipedia")
    ap.add_argument("--out", default=None, help="write sample to CSV")
    ap.add_argument("--plain", action="store_true",
                    help="print bare tickers only (space-separated)")
    args = ap.parse_args()

    uni = load_universe(args.refresh)
    if args.count > len(uni):
        sys.exit(f"asked for {args.count} but universe has only {len(uni)}")

    alloc = allocate(uni["sector"], args.count, args.mode)
    picks = []
    for sector, k in alloc.items():
        pool = uni[uni["sector"] == sector]
        picks.append(pool.sample(n=min(k, len(pool)), random_state=args.seed))
    out = pd.concat(picks)

    # Allocation guarantees can overshoot n (the min-1-per-sector floor), so
    # trim back to exactly n without disturbing the sector spread more than
    # necessary -- drop from the largest sectors first.
    if len(out) > args.count:
        order = out["sector"].map(out["sector"].value_counts())
        out = out.assign(_o=order).sort_values("_o").head(args.count).drop(
            columns="_o")

    out = out.sort_values(["sector", "ticker"]).reset_index(drop=True)

    if args.plain:
        print(" ".join(out["ticker"]))
        return

    if args.out:
        out.to_csv(args.out, index=False)
        print(f"[written] {args.out}", file=sys.stderr)

    print(f"# {len(out)} tickers, {out['sector'].nunique()} sectors, "
          f"mode={args.mode}, seed={args.seed}")
    for sector, grp in out.groupby("sector"):
        print(f"\n{sector} ({len(grp)})")
        print("  " + " ".join(grp["ticker"]))
    print(f"\n# space-separated:\n{' '.join(out['ticker'])}")


if __name__ == "__main__":
    main()
