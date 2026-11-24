"""CR282 Bursa batch step 2 — a seeded, stratified sample of the Bursa universe.

Reads `universe_<date>.csv` (from `scripts.bursa_universe`) and draws about N symbols:

1. Drop what cannot be Roomed or stratified: no price, zero or missing 3-month
   volume, missing market cap. Each drop is counted by reason and printed.
2. Market-cap terciles (large / mid / small) are cut over the eligible universe by
   rank, as equal thirds.
3. Sector quotas are proportional to the eligible universe's sector counts (largest
   remainder, capped at availability, shortfall re-spread).
4. Within a sector the quota is split as evenly as possible across the three
   terciles; a tercile with too few names hands its shortfall to the others.
5. Within a (sector, tercile) cell, picks are systematic over the cell ordered by
   `code_series` after a seeded shuffle, so the 0xxx / other mix follows the cell's
   own mix instead of luck. (`code_series` stands in for board: Yahoo does not say
   Main vs ACE, and the 0xxx series includes ACE graduates; see `bursa_universe`.)

Deterministic for a given seed and input file. Writes `sample_<seed>.csv` and
`sample_<seed>.meta.json` (seed, counts, drops, breakdowns).

Usage (from backend/):
    .venv/bin/python -m scripts.bursa_sample universe_2026-11-25.csv
    .venv/bin/python -m scripts.bursa_sample universe_2026-11-25.csv --seed 20261125 --n 200
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "docs/forward_planning/CR282_bursa_malaysia/bursa_batch"
DEFAULT_SEED = 20261125
DEFAULT_N = 200
TERCILES = ("large", "mid", "small")

SAMPLE_FIELDS = [
    "symbol", "short_name", "long_name", "sector", "industry", "market_cap",
    "tercile", "board", "code_series", "avg_daily_volume_3m", "price", "currency",
]


def _num(value: str | float | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_universe(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def eligible(rows: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """Rows that can be Roomed and stratified, plus the drop count per reason."""
    drops: Counter[str] = Counter()
    keep: list[dict] = []
    for r in rows:
        price, vol, cap = _num(r.get("price")), _num(r.get("avg_daily_volume_3m")), _num(r.get("market_cap"))
        if price is None or price <= 0:
            drops["no_price"] += 1
        elif vol is None or vol <= 0:
            drops["zero_or_missing_volume"] += 1
        elif cap is None or cap <= 0:
            drops["no_market_cap"] += 1
        else:
            keep.append(r)
    return keep, dict(drops)


def assign_terciles(rows: list[dict]) -> list[dict]:
    """Equal thirds by market-cap rank (symbol breaks ties, so it is deterministic)."""
    ranked = sorted(rows, key=lambda r: (-float(r["market_cap"]), r["symbol"]))
    n = len(ranked)
    out = []
    for i, r in enumerate(ranked):
        t = TERCILES[min(2, i * 3 // n)] if n else TERCILES[0]
        out.append({**r, "tercile": t})
    return out


def largest_remainder(weights: dict[str, int], total: int, caps: dict[str, int]) -> dict[str, int]:
    """Apportion `total` across keys proportionally to `weights`, never above `caps`.

    A key that hits its cap releases the rest to the others (re-run on the remainder).
    """
    quota = dict.fromkeys(weights, 0)
    live = {k for k in weights if caps[k] > 0}
    left = total
    while left > 0 and live:
        wsum = sum(weights[k] for k in live)
        raw = {k: left * weights[k] / wsum for k in live}
        floors = {k: min(int(raw[k]), caps[k] - quota[k]) for k in live}
        used = sum(floors.values())
        order = sorted(live, key=lambda k: (-(raw[k] - int(raw[k])), k))
        extra = left - used
        for k in order:
            if extra <= 0:
                break
            if quota[k] + floors[k] < caps[k]:
                floors[k] += 1
                extra -= 1
        gained = 0
        for k, v in floors.items():
            quota[k] += v
            gained += v
        left -= gained
        live = {k for k in live if quota[k] < caps[k]}
        if gained == 0:
            break
    return quota


def split_even(quota: int, caps: dict[str, int], rng: random.Random) -> dict[str, int]:
    """Spread `quota` as evenly as the caps allow; remainders go to a seeded order."""
    keys = list(caps)
    out = dict.fromkeys(keys, 0)
    live = [k for k in keys if caps[k] > 0]
    left = min(quota, sum(caps.values()))
    while left > 0 and live:
        share, rem = divmod(left, len(live))
        order = live[:]
        rng.shuffle(order)
        bonus = set(order[:rem])
        progressed = 0
        for k in live:
            want = share + (1 if k in bonus else 0)
            take = min(want, caps[k] - out[k])
            out[k] += take
            progressed += take
        left -= progressed
        live = [k for k in live if out[k] < caps[k]]
        if progressed == 0:
            break
    return out


def pick_systematic(cell: list[dict], k: int, rng: random.Random) -> list[dict]:
    """k evenly spaced picks from the cell, ordered by code_series after a shuffle."""
    if k <= 0:
        return []
    pool = cell[:]
    rng.shuffle(pool)
    pool.sort(key=lambda r: r["code_series"])
    if k >= len(pool):
        return pool
    step = len(pool) / k
    start = rng.random() * step
    return [pool[int(start + i * step)] for i in range(k)]


def draw_sample(rows: list[dict], n: int, seed: int) -> tuple[list[dict], dict]:
    keep, drops = eligible(rows)
    if not keep:
        raise ValueError("no eligible symbols to sample from")
    rows3 = assign_terciles(keep)
    rng = random.Random(seed)

    sectors: dict[str, list[dict]] = {}
    for r in rows3:
        sectors.setdefault(r["sector"] or "Unknown", []).append(r)
    total = min(n, len(rows3))
    sector_quota = largest_remainder(
        {s: len(v) for s, v in sectors.items()}, total, {s: len(v) for s, v in sectors.items()},
    )

    picked: list[dict] = []
    for sector in sorted(sectors):
        cells = {t: [r for r in sectors[sector] if r["tercile"] == t] for t in TERCILES}
        per_t = split_even(sector_quota[sector], {t: len(c) for t, c in cells.items()}, rng)
        for t in TERCILES:
            picked.extend(pick_systematic(cells[t], per_t[t], rng))

    picked.sort(key=lambda r: r["symbol"])
    meta = {
        "seed": seed,
        "requested_n": n,
        "universe_rows": len(rows),
        "dropped": drops,
        "dropped_total": sum(drops.values()),
        "eligible": len(keep),
        "sampled": len(picked),
        "tercile_cut_market_cap": {
            t: {
                "min": min(float(r["market_cap"]) for r in rows3 if r["tercile"] == t),
                "max": max(float(r["market_cap"]) for r in rows3 if r["tercile"] == t),
            }
            for t in TERCILES if any(r["tercile"] == t for r in rows3)
        },
        "by_tercile": dict(Counter(r["tercile"] for r in picked)),
        "by_code_series": dict(Counter(r["code_series"] for r in picked)),
        "universe_code_series": dict(Counter(r["code_series"] for r in keep)),
        "by_sector": dict(sorted(Counter(r["sector"] or "Unknown" for r in picked).items())),
        "universe_sector": dict(sorted(Counter(r["sector"] or "Unknown" for r in keep).items())),
        "board": "unknown for every symbol (Yahoo does not provide it); code_series is the proxy",
    }
    return picked, meta


def write_sample(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SAMPLE_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="CR282 Bursa batch: seeded stratified sample.")
    ap.add_argument("universe_csv", type=Path)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--n", type=int, default=DEFAULT_N)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = ap.parse_args()
    rows = load_universe(args.universe_csv)
    picked, meta = draw_sample(rows, args.n, args.seed)
    out = args.out_dir / f"sample_{args.seed}.csv"
    write_sample(picked, out)
    (args.out_dir / f"sample_{args.seed}.meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))
    print(f"wrote {len(picked)} symbols -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
