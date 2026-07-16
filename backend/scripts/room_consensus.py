"""Analyst-consensus fetchers for the Room-vs-Street benchmark (CR035).

For each ticker, collects buy/sell/hold consensus from two programmatic
sources and normalises both to one JSONL record per (ticker, source):

  {ticker, source, asof, bucket, counts, mean_score, mean_target, n_analysts}

Sources:
  yahoo          yfinance .info (recommendationKey/Mean, targetMeanPrice,
                 numberOfAnalystOpinions) + recommendations_summary counts.
                 NOTE: this is the same feed the Room's Fundamentals agent
                 sees — the circularity the CR035 ablation batch isolates.
  stockanalysis  stockanalysis.com/stocks/{t}/forecast/__data.json — an
                 undocumented SvelteKit "devalue" payload (values are indexes
                 into a flat array). Best-effort; raw payloads cached under
                 results/raw/ for debuggability.

Usage (from backend/):
    .venv/bin/python -m scripts.room_consensus path/to/tickers.txt
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "docs/forward_planning/CR035_room_benchmark/results"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

BUCKETS = ("strong_buy", "buy", "hold", "sell", "strong_sell")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bucket_from_label(label: str | None) -> str | None:
    if not label:
        return None
    key = label.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "underperform": "sell",
        "outperform": "buy",
        "overweight": "buy",
        "underweight": "sell",
        "moderate_buy": "buy",
        "moderate_sell": "sell",
    }
    key = aliases.get(key, key)
    return key if key in BUCKETS else None


def _bucket_from_yahoo_mean(mean: float | None) -> str | None:
    """Yahoo scale: 1 = strong buy … 5 = strong sell."""
    if mean is None:
        return None
    if mean <= 1.5:
        return "strong_buy"
    if mean <= 2.5:
        return "buy"
    if mean <= 3.5:
        return "hold"
    if mean <= 4.5:
        return "sell"
    return "strong_sell"


def fetch_yahoo(ticker: str) -> dict | None:
    import yfinance as yf

    t = yf.Ticker(ticker)
    info = t.info or {}
    counts = None
    try:
        summary = t.recommendations_summary
        if summary is not None and len(summary):
            row = summary[summary["period"] == "0m"]
            if len(row):
                r = row.iloc[0]
                counts = {
                    "strong_buy": int(r["strongBuy"]),
                    "buy": int(r["buy"]),
                    "hold": int(r["hold"]),
                    "sell": int(r["sell"]),
                    "strong_sell": int(r["strongSell"]),
                }
    except Exception:
        pass
    mean = info.get("recommendationMean")
    bucket = _bucket_from_label(info.get("recommendationKey")) or _bucket_from_yahoo_mean(mean)
    if bucket is None and counts is None:
        return None
    return {
        "ticker": ticker,
        "source": "yahoo",
        "asof": _now_iso(),
        "bucket": bucket,
        "counts": counts,
        "mean_score": mean,
        "mean_target": info.get("targetMeanPrice"),
        "n_analysts": info.get("numberOfAnalystOpinions"),
    }


def _devalue_resolve(data: list, value, depth: int = 0):
    """Resolve a SvelteKit devalue container: ints in container positions are
    indexes into the flat array (negatives are sentinels → None); the pointed-to
    array entry is the literal value and is never re-dereferenced unless it is
    itself a container."""
    if depth > 8:
        return None
    if isinstance(value, dict):
        return {k: _devalue_deref(data, v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [_devalue_deref(data, v, depth + 1) for v in value]
    return value


def _devalue_deref(data: list, ref, depth: int):
    if isinstance(ref, int) and not isinstance(ref, bool):
        if ref < 0 or ref >= len(data):
            return None
        target = data[ref]
        if isinstance(target, (dict, list)):
            return _devalue_resolve(data, target, depth)
        return target
    if isinstance(ref, (dict, list)):
        return _devalue_resolve(data, ref, depth)
    return ref


def fetch_stockanalysis(ticker: str, raw_dir: Path, client: httpx.Client) -> dict | None:
    url = f"https://stockanalysis.com/stocks/{ticker}/forecast/__data.json"
    resp = client.get(url, headers={"User-Agent": _UA}, follow_redirects=True)
    if resp.status_code != 200:
        return None
    payload = resp.json()
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / f"{ticker}_stockanalysis.json").write_text(json.dumps(payload))

    data_nodes = [
        n["data"] for n in payload.get("nodes", [])
        if isinstance(n, dict) and n.get("type") == "data" and isinstance(n.get("data"), list)
    ]
    if not data_nodes:
        return None
    data = max(data_nodes, key=len)
    if not data or not isinstance(data[0], dict):
        return None

    # Root-level index refs proved unreliable; instead locate the current-
    # ratings summary dict (has counts + consensus, unlike the monthly-history
    # entries which carry a "month" key) and the price-target dict directly,
    # resolving their leaf refs one level.
    ratings: dict = {}
    targets: dict = {}
    for v in data:
        if not isinstance(v, dict):
            continue
        keys = set(v.keys())
        if {"consensus", "strongBuy", "buy", "hold"} <= keys and "month" not in keys:
            ratings = _devalue_resolve(data, v) or {}
        elif {"average", "median", "low", "high", "count", "filtered"} <= keys:
            # the "filtered" key marks the main price-target dict; per-rating
            # sub-dicts share the other keys and must not shadow it
            targets = _devalue_resolve(data, v) or {}
    counts_raw = {k: ratings.get(k) for k in ("strongBuy", "buy", "hold", "sell", "strongSell")}
    counts = (
        {
            "strong_buy": counts_raw["strongBuy"],
            "buy": counts_raw["buy"],
            "hold": counts_raw["hold"],
            "sell": counts_raw["sell"],
            "strong_sell": counts_raw["strongSell"],
        }
        if all(isinstance(v, (int, float)) for v in counts_raw.values())
        else None
    )
    bucket = _bucket_from_label(ratings.get("consensus"))
    if bucket is None and counts is None:
        return None
    return {
        "ticker": ticker,
        "source": "stockanalysis",
        "asof": _now_iso(),
        "bucket": bucket,
        "counts": counts,
        # stockanalysis score is higher-is-better (≈5 = strong buy) — opposite
        # of Yahoo's scale; recorded verbatim, never compared cross-source.
        "mean_score": ratings.get("score"),
        "mean_target": targets.get("average"),
        "n_analysts": ratings.get("count"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="CR035 consensus fetcher.")
    parser.add_argument("tickers_file", type=Path)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    tickers = [
        t.strip().upper()
        for t in args.tickers_file.read_text().splitlines()
        if t.strip() and not t.strip().startswith("#")
    ]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / "consensus.jsonl"
    raw_dir = args.out_dir / "raw"
    client = httpx.Client(timeout=30.0)

    records: list[dict] = []
    misses: list[str] = []
    for i, ticker in enumerate(tickers):
        got = []
        for name, fn in (
            ("yahoo", lambda t=ticker: fetch_yahoo(t)),
            ("stockanalysis", lambda t=ticker: fetch_stockanalysis(t, raw_dir, client)),
        ):
            try:
                rec = fn()
            except Exception as exc:  # noqa: BLE001 — best-effort per source
                print(f"  {ticker} {name}: error {exc!r}")
                rec = None
            if rec:
                records.append(rec)
                got.append(name)
            time.sleep(1.0)
        print(f"[{i + 1}/{len(tickers)}] {ticker}: {', '.join(got) or 'NO DATA'}")
        if not got:
            misses.append(ticker)

    with out_path.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    print(f"\nwrote {len(records)} records → {out_path}")
    if misses:
        print(f"no data for: {', '.join(misses)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
