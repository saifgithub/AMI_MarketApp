"""Refresh sell-side consensus for the CR228 30-ticker benchmark universe.

Replays the CR035 consensus schema (ticker/source/asof/bucket/counts/mean_score/
mean_target/n_analysts) against Yahoo Finance via yfinance, and adds the spot
price so target upside can be computed. Primary source only: the stockanalysis
API shape used in 2026-07 is gone (404) and their pages are JS-rendered.

Usage (from repo root, backend venv has yfinance):
    backend/.venv/bin/python docs/forward_planning/CR251_risk_monotonicity_matrix/tools/fetch_market_consensus.py
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

REPO = Path(__file__).resolve().parents[4]
TICKERS = [
    line.strip()
    for line in (REPO / "docs/forward_planning/CR228_risk_appetite_differentiation/tickers_30.txt").read_text().splitlines()
    if line.strip() and not line.startswith("#")
]
OUT = Path(__file__).resolve().parent.parent / "results" / "consensus_refresh.jsonl"


def bucket_of(mean_score: float) -> str:
    if mean_score <= 1.5:
        return "strong_buy"
    if mean_score < 2.5:
        return "buy"
    if mean_score < 3.5:
        return "hold"
    if mean_score < 4.5:
        return "sell"
    return "strong_sell"


def fetch(ticker: str) -> dict | None:
    t = yf.Ticker(ticker)
    counts = None
    try:
        rec = t.recommendations
        if rec is not None and not rec.empty:
            row = rec[rec["period"] == "0m"].iloc[0]
            counts = {
                "strong_buy": int(row["strongBuy"]),
                "buy": int(row["buy"]),
                "hold": int(row["hold"]),
                "sell": int(row["sell"]),
                "strong_sell": int(row["strongSell"]),
            }
    except Exception as e:
        print(f"  {ticker}: recommendations failed: {e}", file=sys.stderr)
    pt = None
    spot = None
    try:
        pt = t.analyst_price_targets
    except Exception as e:
        print(f"  {ticker}: price targets failed: {e}", file=sys.stderr)
    try:
        spot = t.info.get("regularMarketPrice") or t.info.get("currentPrice")
    except Exception:
        pass
    if counts is None and not pt:
        return None
    n = sum(counts.values()) if counts else 0
    mean_score = (
        (counts["strong_buy"] * 1 + counts["buy"] * 2 + counts["hold"] * 3 + counts["sell"] * 4 + counts["strong_sell"] * 5) / n
        if n
        else None
    )
    return {
        "ticker": ticker,
        "source": "yahoo",
        "asof": datetime.now(timezone.utc).isoformat(),
        "bucket": bucket_of(mean_score) if mean_score else None,
        "counts": counts,
        "mean_score": round(mean_score, 5) if mean_score else None,
        "mean_target": pt.get("mean") if pt else None,
        "median_target": pt.get("median") if pt else None,
        "high_target": pt.get("high") if pt else None,
        "low_target": pt.get("low") if pt else None,
        "spot": spot,
        "n_analysts": n,
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, ticker in enumerate(TICKERS):
        row = fetch(ticker)
        if row:
            rows.append(row)
            print(f"[{i + 1}/{len(TICKERS)}] {ticker}: {row['bucket']} score={row['mean_score']} target={row['mean_target']} spot={row['spot']} n={row['n_analysts']}")
        else:
            print(f"[{i + 1}/{len(TICKERS)}] {ticker}: FAILED", file=sys.stderr)
        time.sleep(1.0)
    with OUT.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    print(f"wrote {len(rows)} rows -> {OUT}")


if __name__ == "__main__":
    main()
