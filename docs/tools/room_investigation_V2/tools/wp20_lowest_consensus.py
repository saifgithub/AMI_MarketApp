#!/usr/bin/env python3
"""wp20_lowest_consensus — rank CR035's 150-ticker universe by CURRENT Yahoo sell-side consensus (AT:B1 CR267).

WP-20 step 3: pick the lowest-consensus names outside the 30-ticker matrix as a side set. The CR035 screen
(2026-07-17) is four months stale, so this refreshes `recommendationMean` (1 = strong buy ... 5 = strong sell)
and `recommendationKey` via yfinance. Prints JSON lines worst-first; run inside any container with yfinance.

Usage: python3 wp20_lowest_consensus.py TICKERS_150.txt EXCLUDE_CSV
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import yfinance as yf


def main(tickers_file: str, exclude_csv: str) -> None:
    exclude = {t.strip().upper() for t in exclude_csv.split(",") if t.strip()}
    tickers = [
        ln.strip().upper() for ln in Path(tickers_file).read_text().splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    rows = []
    for t in tickers:
        if t in exclude:
            continue
        try:
            info = yf.Ticker(t).info
            rows.append({
                "ticker": t, "mean": info.get("recommendationMean"),
                "key": info.get("recommendationKey"), "n": info.get("numberOfAnalystOpinions"),
            })
        except Exception as exc:  # noqa: BLE001 — one bad ticker must not sink the ranking
            rows.append({"ticker": t, "mean": None, "key": None, "n": None, "error": repr(exc)[:120]})
        time.sleep(0.4)
    rows.sort(key=lambda r: -(r["mean"] if r["mean"] is not None else -1))
    for r in rows:
        print(json.dumps(r))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
