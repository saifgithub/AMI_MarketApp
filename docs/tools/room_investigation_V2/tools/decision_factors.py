#!/usr/bin/env python3
"""Primary decision factor per room, from verdict.reason text (CR255).

Usage: decision_factors.py --base out/<arm> [--out rooms.csv]

Classifies each room verdict's reason into one primary factor by keyword
class, first match wins, case-insensitive (substring, not regex):

    catalyst_wait   wait|earnings|fomc|catalyst|confirm|print|binary
    technical_setup technical|trend|sma|rsi|macd|entry|bollinger|setup
    valuation       valuat|premium|multiple|p/e|priced|expensive|peg
    insider         insider|buyback|cluster|form 4
    balance_sheet   debt|leverage|interest coverage|maturity|sbc|fcf
    risk_language   risk|mandate|cap|exposure|drawdown
    other           everything else

Emits per-room rows, a factor x level summary (approval count / room
count / approval rate), and a flip-pair view: rooms where rep1 != rep2
verdict on the same (ticker, risk_score) — and whether the primary
factor flipped with the verdict.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

LEVELS = [1, 2, 3, 4, 5]
FACTORS: list[tuple[str, tuple[str, ...]]] = [
    ("catalyst_wait",   ("wait", "earnings", "fomc", "catalyst", "confirm", "print", "binary")),
    ("technical_setup", ("technical", "trend", "sma", "rsi", "macd", "entry", "bollinger", "setup")),
    ("valuation",       ("valuat", "premium", "multiple", "p/e", "priced", "expensive", "peg")),
    ("insider",         ("insider", "buyback", "cluster", "form 4")),
    ("balance_sheet",   ("debt", "leverage", "interest coverage", "maturity", "sbc", "fcf")),
    ("risk_language",   ("risk", "mandate", "cap", "exposure", "drawdown")),
]
REP_RE = re.compile(r"^(?P<ticker>.+)-rep(?P<rep>\d+)$")


def load(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p)] if p.exists() else []


def primary_factor(reason: str | None) -> str:
    text = (reason or "").lower()
    for name, kws in FACTORS:
        if any(kw in text for kw in kws):
            return name
    return "other"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", default=None, help="CSV of per-room rows")
    args = ap.parse_args()
    base = Path(args.base)

    rows = []
    for lvl in LEVELS:
        runs = sorted((base / f"r{lvl}").glob("runs_*.jsonl"))
        if not runs:
            continue
        for rec in load(runs[0]):
            v = rec.get("verdict")
            action = v.get("action") if isinstance(v, dict) else v
            reason = v.get("reason") if isinstance(v, dict) else None
            size = v.get("size_pct") if isinstance(v, dict) else None
            rows.append({
                "arm_key": rec.get("arm_key") or f"{rec['ticker']}-?",
                "ticker": rec.get("ticker"),
                "risk_score": int(rec.get("risk_score") or lvl),
                "verdict": action, "size_pct": size,
                "primary_factor": primary_factor(reason),
            })

    if args.out:
        with open(args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["arm_key", "ticker", "risk_score",
                                              "verdict", "size_pct", "primary_factor"])
            w.writeheader()
            for r in rows:
                w.writerow({k: ("" if r[k] is None else r[k]) for k in r})
        print(f"wrote {len(rows)} rooms -> {args.out}")

    print(f"\n=== [{base.name}] primary factor x risk level (APPROVE count / rooms / rate) ===")
    names = [n for n, _ in FACTORS] + ["other"]
    header = f"  {'factor':16s}" + "".join(f"  R{l:d} {'':14s}" for l in LEVELS) + "   TOTAL"
    print(header)
    for name in names:
        cells, tot_ap, tot_n = [], 0, 0
        for lvl in LEVELS:
            sel = [r for r in rows if r["risk_score"] == lvl and r["primary_factor"] == name]
            ap_ct = sum(1 for r in sel if r["verdict"] == "APPROVE")
            cells.append(f"{ap_ct:3d}/{len(sel):2d} = {100*ap_ct/len(sel) if sel else 0:4.0f}%")
            tot_ap += ap_ct
            tot_n += len(sel)
        print(f"  {name:16s}" + "  ".join(f"{c:18s}" for c in cells) +
              f"  {tot_ap:3d}/{tot_n:3d} = {100*tot_ap/tot_n if tot_n else 0:4.0f}%")

    # flip pairs: rep1 vs rep2 on the same (ticker, risk_score)
    by_pair: dict[tuple[str, int], dict[str, dict]] = defaultdict(dict)
    for r in rows:
        m = REP_RE.match(r["arm_key"])
        if not m:
            continue
        by_pair[(m.group("ticker"), r["risk_score"])][m.group("rep")] = r
    flips, factor_flips, both = 0, 0, 0
    for (ticker, lvl), reps in sorted(by_pair.items()):
        if "1" not in reps or "2" not in reps:
            continue
        a, b = reps["1"], reps["2"]
        if a["verdict"] == b["verdict"]:
            continue
        flips += 1
        ff = a["primary_factor"] != b["primary_factor"]
        factor_flips += ff
        both += a["verdict"] == "APPROVE" and b["verdict"] == "APPROVE"
    pairs_n = sum(1 for reps in by_pair.values() if "1" in reps and "2" in reps)
    print(f"\n=== [{base.name}] flip pairs (rep1 vs rep2, same ticker+level) ===")
    print(f"  complete pairs: {pairs_n}; verdict flips: {flips} "
          f"({100*flips/pairs_n:.0f}% if pairs_n else 0)")
    print(f"  flips where primary factor ALSO differs: {factor_flips}/{flips}")


if __name__ == "__main__":
    main()
