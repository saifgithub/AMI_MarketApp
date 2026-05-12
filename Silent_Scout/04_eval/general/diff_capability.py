"""Diff two lm-evaluation-harness result JSON files and gate on regression.

Fails (exit code 1) if any tracked task drops more than --gate-pp percentage
points from base to candidate.

Tracked tasks: mmlu, ifeval, gsm8k, hellaswag.
The metric we read is the primary "acc" / "exact_match" / "inst_level_strict_acc"
depending on the task — falls back to the first numeric metric found.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TRACKED = {
    "mmlu": "acc,none",
    "ifeval": "inst_level_strict_acc,none",
    "gsm8k": "exact_match,strict-match",
    "hellaswag": "acc,none",
}


def _read_results(path: Path) -> dict[str, float]:
    data = json.loads(path.read_text())
    results = data.get("results", data)
    out: dict[str, float] = {}
    for task, metric_key in TRACKED.items():
        if task not in results:
            continue
        block = results[task]
        if metric_key in block:
            out[task] = float(block[metric_key])
            continue
        for k, v in block.items():
            if isinstance(v, (int, float)):
                out[task] = float(v)
                break
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("base", type=Path)
    p.add_argument("candidate", type=Path)
    p.add_argument("--gate-pp", type=float, default=3.0)
    args = p.parse_args()

    base = _read_results(args.base)
    cand = _read_results(args.candidate)

    failed = False
    print(f"{'task':<12} {'base':>8} {'cand':>8} {'delta_pp':>10}  verdict")
    for task in TRACKED:
        b = base.get(task)
        c = cand.get(task)
        if b is None or c is None:
            print(f"{task:<12} {'-':>8} {'-':>8} {'-':>10}  MISSING")
            failed = True
            continue
        delta = (c - b) * 100.0
        ok = delta >= -args.gate_pp
        verdict = "OK" if ok else "FAIL"
        print(f"{task:<12} {b * 100:>8.2f} {c * 100:>8.2f} {delta:>+10.2f}  {verdict}")
        if not ok:
            failed = True

    if failed:
        print(f"\nGate FAILED — at least one task regressed > {args.gate_pp}pp.")
        return 1
    print(f"\nGate PASSED — no task regressed > {args.gate_pp}pp.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
