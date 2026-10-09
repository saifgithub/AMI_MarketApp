#!/usr/bin/env python3
"""Net directional desk support per room for a CR251 matrix arm (CR255).

Usage: net_support.py --base out/<arm> [--out rooms.csv]

Joins r{1..5}/runs_*.jsonl verdicts to jev/r{1..5}.jsonl room evidence scores
on (arm_key, risk_score) — arm_key alone is not unique across levels (the
same "AAPL-rep1" key exists at every risk level). Per room:

    net_support = bull-side mean support - bear-side mean support

Bull desk: bull_researcher, fundamentals_analyst, trader.
Bear desk: bear_researcher, aggressive_debator, conservative_debator.
Debator turns are absent from the dsv4/cap1 Jev logs — bear-side means are
then driven by bear_researcher alone (reported, not an error).

Prints Pearson r (net_support vs approve indicator) and, per level and
pooled, the best single-threshold agreement vs the always-PASS base rate.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

SUPPORT_NUM = {"well_supported": 1.0, "partially_supported": 0.5,
               "unsupported": 0.0, "no_clear_claim": None}
BULL_DESK = {"bull_researcher", "fundamentals_analyst", "trader"}
BEAR_DESK = {"bear_researcher", "aggressive_debator", "conservative_debator"}
LEVELS = [1, 2, 3, 4, 5]


def load(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p)] if p.exists() else []


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    return cov / math.sqrt(vx * vy)


def best_threshold(pairs: list[tuple[float, float]]) -> tuple[float, int]:
    """(threshold, agreements) maximizing agreement with actual verdicts."""
    return max(
        ((thr, sum(1 for s, a in pairs if (s >= thr) == (a == 1.0)))
         for thr in (i / 40 for i in range(-39, 40))),
        key=lambda x: x[1],
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", default=None, help="CSV of per-room rows")
    args = ap.parse_args()
    base = Path(args.base)

    # verdicts keyed by (arm_key, risk_score)
    v_map: dict[tuple[str, int], dict] = {}
    for lvl in LEVELS:
        runs = sorted((base / f"r{lvl}").glob("runs_*.jsonl"))
        if not runs:
            continue
        for rec in load(runs[0]):
            k = (rec.get("arm_key") or f"{rec['ticker']}-?", int(rec.get("risk_score") or lvl))
            v_map[k] = rec

    # per-desk support values keyed by (arm_key, risk_score)
    desk_map: dict[tuple[str, int], dict[str, list[float]]] = {}
    bear_agents: set[str] = set()
    for lvl in LEVELS:
        jf = base / "jev" / f"r{lvl}.jsonl"
        if not jf.exists():
            continue
        for t in load(jf):
            k = (t.get("arm_key") or "?", int(t.get("risk_score") or lvl))
            cc = (t.get("answers") or {}).get("core_claim_supported") or {}
            n = SUPPORT_NUM.get(cc.get("choice"))
            if n is None:
                continue
            desks = desk_map.setdefault(k, {"bull": [], "bear": [], "neutral": []})
            a = t.get("agent_id") or "?"
            side = ("bull" if a in BULL_DESK else
                    "bear" if a in BEAR_DESK else "neutral")
            desks[side].append(n)
            if side == "bear":
                bear_agents.add(a)

    rows = []
    for k in sorted(v_map):
        if k not in desk_map:
            continue
        rec, d = v_map[k], desk_map[k]
        v = rec.get("verdict")
        action = v.get("action") if isinstance(v, dict) else v
        size = v.get("size_pct") if isinstance(v, dict) else None
        bull = sum(d["bull"]) / len(d["bull"]) if d["bull"] else None
        bear = sum(d["bear"]) / len(d["bear"]) if d["bear"] else None
        net = bull - bear if bull is not None and bear is not None else None
        rows.append({
            "arm_key": k[0], "ticker": rec.get("ticker"), "risk_score": k[1],
            "verdict": action, "size_pct": size,
            "bull_mean": bull, "bear_mean": bear, "net_support": net,
        })

    def fmt(x: float | None) -> str:
        return f"{x:.3f}" if x is not None else ""

    if args.out:
        with open(args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["arm_key", "ticker", "risk_score",
                                              "verdict", "size_pct",
                                              "bull_mean", "bear_mean", "net_support"])
            w.writeheader()
            for r in rows:
                w.writerow({kk: (fmt(r[kk]) if isinstance(r[kk], float) else
                                 "" if r[kk] is None else r[kk]) for kk in r})
        print(f"wrote {len(rows)} rooms -> {args.out}")

    missing_bear = BEAR_DESK - bear_agents
    note = (f" (absent: {sorted(missing_bear)} — bear mean driven by "
            f"{sorted(bear_agents)})" if missing_bear else "")
    print(f"\n=== [{base.name}] net thesis support (bull mean - bear mean) ===")
    print(f"rooms joined: {len(rows)}; bear-desk agents seen: "
          f"{sorted(bear_agents) or 'NONE'}{note}")

    print("\n-- Pearson r (net_support vs approve indicator) --")
    pooled = [(r["net_support"], 1.0 if r["verdict"] == "APPROVE" else 0.0)
              for r in rows if r["net_support"] is not None]
    for lvl in LEVELS:
        lp = [(r["net_support"], 1.0 if r["verdict"] == "APPROVE" else 0.0)
              for r in rows if r["risk_score"] == lvl and r["net_support"] is not None]
        r_val = pearson([p[0] for p in lp], [p[1] for p in lp])
        print(f"  R{lvl}: n={len(lp):3d} r={r_val if r_val is not None else float('nan'):+.3f}")
    pr = pearson([p[0] for p in pooled], [p[1] for p in pooled])
    print(f"  pooled: n={len(pooled)} r={pr:+.3f}")

    print("\n-- best net-support threshold vs always-PASS base rate --")
    for lvl in [None] + LEVELS:
        lp = pooled if lvl is None else [
            (r["net_support"], 1.0 if r["verdict"] == "APPROVE" else 0.0)
            for r in rows if r["risk_score"] == lvl and r["net_support"] is not None]
        if not lp:
            continue
        thr, agree = best_threshold(lp)
        n = len(lp)
        base_rate = max(sum(1 for _, a in lp if a == 0.0), sum(1 for _, a in lp if a == 1.0)) / n
        lift = agree / n - base_rate
        tag = "pooled" if lvl is None else f"R{lvl} "
        print(f"  {tag}: best thr {thr:+.3f} agrees {agree}/{n} = {100*agree/n:.0f}% "
              f"| always-PASS base {100*base_rate:.0f}% | lift {100*lift:+.0f} pts")


if __name__ == "__main__":
    main()
