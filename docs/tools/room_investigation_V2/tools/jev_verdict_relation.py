#!/usr/bin/env python3
"""Jev-score <-> verdict relationship for a CR251 matrix arm.

Usage: jev_verdict_relation.py --base out/<arm> [--label NAME]

Joins r{1..5}/runs_*.jsonl verdicts to jev/r{1..5}.jsonl room evidence scores
on `arm_key` (both sides record it, e.g. "AAPL-rep2"), then reports:
  1. per-level APPROVE vs PASS mean room evidence score + delta
  2. score-decile distribution by verdict (where approvals actually sit)
  3. agreement if a single Jev threshold decided every verdict
  4. the two failure shapes: high-support PASS, low-support APPROVE
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

SUPPORT_NUM = {"well_supported": 1.0, "partially_supported": 0.5,
               "unsupported": 0.0, "no_clear_claim": None}
LEVELS = [1, 2, 3, 4, 5]


def load(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p)] if p.exists() else []


def room_score(turns: list[dict]) -> float | None:
    vals = []
    for t in turns:
        cc = (t.get("answers") or {}).get("core_claim_supported") or {}
        n = SUPPORT_NUM.get(cc.get("choice"))
        if n is not None:
            vals.append(n)
    return sum(vals) / len(vals) if vals else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--label", default="arm")
    args = ap.parse_args()
    base = Path(args.base)

    # verdicts by arm_key
    v_map: dict[tuple[str, int], str] = {}
    for lvl in LEVELS:
        runs = sorted((base / f"r{lvl}").glob("runs_*.jsonl"))
        if not runs:
            continue
        for rec in load(runs[0]):
            k = (rec.get("arm_key") or f"{rec['ticker']}-?", int(rec.get("risk_score") or lvl))
            v = rec.get("verdict")
            v_map[k] = v.get("action") if isinstance(v, dict) else v

    # room evidence scores by arm_key
    s_map: dict[tuple[str, int], float] = {}
    for lvl in LEVELS:
        jf = base / "jev" / f"r{lvl}.jsonl"
        if not jf.exists():
            continue
        by_room: dict[tuple[str, int], list[dict]] = defaultdict(list)
        for t in load(jf):
            by_room[(t.get("arm_key") or "?", int(t.get("risk_score") or lvl))].append(t)
        for k, turns in by_room.items():
            s = room_score(turns)
            if s is not None:
                s_map[k] = s

    joined = [(k[0], s_map[k], v_map[k], k[1])
              for k in s_map if k in v_map and v_map[k] in ("APPROVE", "PASS")]

    print(f"\n=== [{args.label}] APPROVE vs PASS mean room evidence score ===")
    per_level: dict[int, dict[str, list[float]]] = {l: {"APPROVE": [], "PASS": []} for l in LEVELS}
    for _, s, a, lvl in joined:
        per_level[lvl][a].append(s)
    for lvl in LEVELS:
        av, pv = per_level[lvl]["APPROVE"], per_level[lvl]["PASS"]
        if av and pv:
            print(f"  R{lvl}: APPROVE n={len(av):2d} mean={sum(av)/len(av):.3f} | "
                  f"PASS n={len(pv):2d} mean={sum(pv)/len(pv):.3f} | "
                  f"Δ={sum(av)/len(av)-sum(pv)/len(pv):+.3f}")

    pairs = sorted((s, a) for _, s, a, _ in joined)
    n = len(pairs)
    print(f"\n=== [{args.label}] score deciles by verdict (n={n} rooms) ===")
    dec = max(n // 10, 1)
    for d in range(10):
        chunk = pairs[d * dec:(d + 1) * dec] if d < 9 else pairs[9 * dec:]
        ap_ct = sum(1 for _, a in chunk if a == "APPROVE")
        print(f"  decile {d}: {chunk[0][0]:.2f}-{chunk[-1][0]:.2f}  APPROVE {ap_ct:2d}/{len(chunk)}")

    print(f"\n=== [{args.label}] if a single Jev threshold decided ===")
    best = max(
        ((thr, sum(1 for s, a in pairs if (s >= thr) == (a == "APPROVE")))
         for thr in (i / 40 for i in range(1, 40))),
        key=lambda x: x[1],
    )
    print(f"  best threshold {best[0]:.3f} → agrees with actual verdict "
          f"{best[1]}/{n} = {100*best[1]/n:.0f}% (50% = coin flip)")

    print(f"\n=== [{args.label}] failure shapes ===")
    fn = sorted(((k, s) for k, s, a, _ in joined if a == "PASS" and s >= 0.75),
                key=lambda x: -x[1])
    fp = sorted(((k, s) for k, s, a, _ in joined if a == "APPROVE" and s <= 0.55),
                key=lambda x: x[1])
    print(f"  high-support PASS (>=0.75): {len(fn)}")
    for k, s in fn[:10]:
        print(f"    {k:14s} {s:.2f}")
    print(f"  low-support APPROVE (<=0.55): {len(fp)}")
    for k, s in fp[:10]:
        print(f"    {k:14s} {s:.2f}")


if __name__ == "__main__":
    main()
