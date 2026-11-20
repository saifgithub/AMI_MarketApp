#!/usr/bin/env python3
"""wp20_analyze — summarise a CR267 WP-20 baseline arm from its runs_*.jsonl (AT:B1 CR267).

Pure stdlib, post-hoc, no LLM and no network: reads the harness's run records and prints the
WP-20 acceptance tables as markdown — approvals per risk level, per-ticker curve, flip count across
the two reps, minutes per Room, n per cell, errors. Scores are computed in code, never by a model.

Usage:  python3 wp20_analyze.py RUNS.jsonl [RUNS2.jsonl ...]   # several files are pooled (arm + side set)
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

LEVELS = [1, 2, 3, 4, 5]


def load(paths: list[str]) -> list[dict]:
    latest: dict[tuple[str, str], dict] = {}
    for p in paths:
        for line in Path(p).read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                if "arm_key" in rec:
                    latest[(rec["batch_id"], rec["arm_key"])] = rec
    return list(latest.values())


def action(rec: dict) -> str:
    v = rec.get("verdict")
    if rec.get("status") != "completed" or not isinstance(v, dict):
        return "ERROR"
    return str(v.get("action") or "NONE").upper()


def main(paths: list[str]) -> None:
    recs = load(paths)
    print(f"records: {len(recs)}  statuses: {dict(sorted(defaultdict(int, {s: sum(1 for r in recs if r['status'] == s) for s in {r['status'] for r in recs}}).items()))}")
    cell: dict[tuple[str, int], list[str]] = defaultdict(list)
    for r in recs:
        cell[(r["ticker"], int(r["risk_score"]))].append(action(r))
    tickers = sorted({t for t, _ in cell})

    print("\n## Approvals per risk level (rooms with a verdict; ERROR excluded from n)\n")
    print("| Risk | n | APPROVE | rate | PASS | other | ERROR |")
    print("|---|---|---|---|---|---|---|")
    for lv in LEVELS:
        acts = [a for (t, l), v in cell.items() if l == lv for a in v]
        n = sum(1 for a in acts if a != "ERROR")
        ap = sum(1 for a in acts if a == "APPROVE")
        ps = sum(1 for a in acts if a == "PASS")
        er = sum(1 for a in acts if a == "ERROR")
        print(f"| R{lv} | {n} | {ap} | {ap / n:.0%} | {ps} | {n - ap - ps} | {er} |" if n else f"| R{lv} | 0 | - | - | - | - | {er} |")

    print("\n## Per-ticker APPROVE count by risk level (of the reps run)\n")
    print("| Ticker | " + " | ".join(f"R{l}" for l in LEVELS) + " |")
    print("|---|" + "---|" * len(LEVELS))
    for t in tickers:
        cells = []
        for lv in LEVELS:
            v = cell.get((t, lv), [])
            cells.append(f"{sum(1 for a in v if a == 'APPROVE')}/{len(v)}" if v else "-")
        print(f"| {t} | " + " | ".join(cells) + " |")

    comparable = flips = 0
    for v in cell.values():
        ok = [a for a in v if a != "ERROR"]
        if len(ok) >= 2:
            comparable += 1
            flips += len(set(ok)) > 1
    print(f"\n## Flips across reps\n\ncomparable cells (ticker x risk with 2 verdicts): {comparable}; flips (reps disagree): {flips}"
          + (f" ({flips / comparable:.0%})" if comparable else ""))

    durs = [r["duration_ms"] / 60000 for r in recs if r.get("duration_ms")]
    if durs:
        print(f"\n## Minutes per Room (wall clock per room as run, concurrency-dependent)\n\n"
              f"n={len(durs)} mean={st.mean(durs):.2f} median={st.median(durs):.2f} "
              f"p90={sorted(durs)[int(0.9 * (len(durs) - 1))]:.2f} max={max(durs):.2f}")
    bad = [r for r in recs if r["status"] != "completed"]
    if bad:
        print("\n## Non-completed arms\n")
        for r in bad:
            print(f"- {r['arm_key']} {r['status']} {r.get('error_message')}")


if __name__ == "__main__":
    main(sys.argv[1:])
