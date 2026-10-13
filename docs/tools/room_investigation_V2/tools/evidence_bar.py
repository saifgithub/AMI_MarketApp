#!/usr/bin/env python3
"""CR256 Step 0 — evidence-bar proxy-gate simulation over existing matrix arms.

Validates the Layer-3 quantile gate (per-level thresholds fit to the locked
target curve, with the 7-name holdout exclusions) on PROXY evidence scores
computed from Jev-scored turns of the four committed 300-room arms — zero new
rooms, CPU only, stdlib only. The real composite (claim cards + objections)
needs prompt/room changes and debator turns in Jev (spec prerequisite M7);
this is the feasibility gate for the bar mechanics themselves.

Scores compared (all direction-aware where applicable):
  desk_net_cont — desk-membership sign, Jev probability-weighted (legacy net_support.py)
  stance_signed — STANCE sign x E[Jev support], per card's own direction (spec proxy)
  stance_only   — STANCE sign only (the baseline the composite must beat)
  early_signed  — stance_signed over analysts + researchers only (pre-synthesis)

Method (review M5 honest validation — in-sample quantile fit reproduces any
curve trivially, so the headline is SPLIT-FIT): fit T(level) on rep-1 rooms,
apply to rep-2. Holdouts (APD, BA, FCEL, RIOT, RIVN, SNAP, SPCE) are excluded
from the approval set at every level BEFORE ranking; R5 target is 46/60
(amended 2026-10-13). Holdout leakage is reported as the RIOT-shaped
falsifier check: a fitted bar that lets a holdout through fails validation.

Run: python3 evidence_bar.py [--out-dir ../out/evidence_bar_step0]
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import math
import re
import statistics as st
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "docs/tools/room_investigation_V2/out"

ARMS = {
    "dsv4-prod (arm 1)": ["cr251-v2-dsv4"],
    "dsv4-disp (arm 9)": ["cr253-disp-matrix"],
    "ami-clean (arm 10+fix)": ["cr251-v2-ami", "cr251-v2-ami-fix"],
    "dsv4-tmall (arm 11)": ["cr254-tmall-matrix"],
}
# Amended 2026-10-13: R5 re-anchored 60 -> 46 (investable universe, 7 holdouts).
TARGET = {1: 5, 2: 15, 3: 30, 4: 45, 5: 46}
HOLDOUTS = ("APD", "BA", "FCEL", "RIOT", "RIVN", "SNAP", "SPCE")

BULL = {"bull_researcher", "fundamentals_analyst", "trader"}
BEAR = {"bear_researcher", "aggressive_debator", "conservative_debator"}
EARLY = {"market_analyst", "news_analyst", "social_media_analyst",
         "fundamentals_analyst", "bull_researcher", "bear_researcher"}
SUP = {"well_supported": 1.0, "partially_supported": 0.5, "unsupported": 0.0}
STANCE = re.compile(r"\[STANCE:\s*(for|against|neutral)\s*\|\s*CONVICTION:\s*(low|medium|high)", re.I)
SIGN = {"for": 1, "against": -1, "neutral": 0}

SCORES = ("desk_net_cont", "stance_signed", "stance_only", "early_signed")


def pearson(x, y):
    n = len(x)
    if n < 3:
        return float("nan")
    mx, my = sum(x) / n, sum(y) / n
    c = sum((a - mx) * (b - my) for a, b in zip(x, y))
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    return c / math.sqrt(vx * vy) if vx and vy else float("nan")


def load(arm):
    """Rooms + Jev turns; later dirs (the ami fix re-run) override earlier ones."""
    rooms, turns = {}, {}
    for d in ARMS[arm]:
        for lvl in range(1, 6):
            for f in glob.glob(str(OUT / d / f"r{lvl}" / "runs_*.jsonl")):
                for line in open(f):
                    r = json.loads(line)
                    rooms[(r["arm_key"], int(r["risk_score"]))] = r
            jf = OUT / d / "jev" / f"r{lvl}.jsonl"
            if not jf.exists():
                continue
            fresh = collections.defaultdict(list)
            for line in open(jf):
                t = json.loads(line)
                fresh[(t["arm_key"], int(t["risk_score"]))].append(t)
            turns.update(fresh)
    return rooms, turns


def split_key(k):
    t, rep = k[0].rsplit("-rep", 1)
    return t, k[1], rep


def room_features(ts):
    bullc, bearc, signed, stance_only, early = [], [], [], [], []
    for t in ts:
        a = t.get("agent_id")
        cc = (t.get("answers") or {}).get("core_claim_supported") or {}
        ch, p = cc.get("choice"), cc.get("probabilities") or {}
        if ch not in SUP:
            continue
        tot = p.get("well_supported", 0) + p.get("partially_supported", 0) + p.get("unsupported", 0)
        e = ((p.get("well_supported", 0) + 0.5 * p.get("partially_supported", 0)) / tot
             if tot else SUP[ch])
        if a in BULL:
            bullc.append(e)
        if a in BEAR:
            bearc.append(e)
        m = STANCE.search((((t.get("request") or {}).get("state") or {}).get("output") or "")[:400])
        if m and a != "trader":
            s = SIGN[m.group(1).lower()]
            signed.append(s * e)
            stance_only.append(s)
            if a in EARLY:
                early.append(s * e)
    f = {}
    if bullc and bearc:
        f["desk_net_cont"] = st.mean(bullc) - st.mean(bearc)
    if signed:
        f["stance_signed"] = st.mean(signed)
        f["stance_only"] = st.mean(stance_only)
    if early:
        f["early_signed"] = st.mean(early)
    return f


def fit_threshold(rows, lvl, key):
    """T(level) on rep-1 eligible rooms: the score at rank target_l."""
    fit = sorted((x[key] for x in rows
                  if x["lvl"] == lvl and x["rep"] == "1" and key in x and not x["holdout"]),
                 reverse=True)
    if not fit:
        return None
    k = max(1, min(TARGET[lvl], len(fit)))
    return fit[k - 1]


def gate_decisions(rows, key):
    """Split-fit gate: T fit on rep-1, applied to ALL rooms at the level.

    Holdouts are forced to False (excluded from the approval set) before
    ranking; everyone else approves iff score >= T(level).
    """
    T = {l: fit_threshold(rows, l, key) for l in range(1, 6)}
    dec = {}
    for x in rows:
        if key not in x:
            continue
        t = T.get(x["lvl"])
        dec[(x["t"], x["lvl"], x["rep"])] = (
            False if x["holdout"] else (t is not None and x[key] >= t))
    return dec, T


def nonmonotone(dec):
    n = tot = 0
    for t in {k[0] for k in dec}:
        for rep in "12":
            seq = [dec.get((t, l, rep)) for l in range(1, 6)]
            if None in seq:
                continue
            tot += 1
            n += any(seq[i] and not seq[i + 1] for i in range(4))
    return n, tot


def simulate_arm(arm):
    rooms, turns = load(arm)
    rows = []
    for k, r in rooms.items():
        if k not in turns:
            continue
        t, lvl, rep = split_key(k)
        rows.append(dict(t=t, lvl=lvl, rep=rep, holdout=t in HOLDOUTS,
                         appr=(r["verdict"] or {}).get("action") == "APPROVE",
                         **room_features(turns[k])))
    out = {"arm": arm, "rooms": len(rows), "scores": {}}
    for key in SCORES:
        R = [x for x in rows if key in x]
        rs = [pearson([x[key] for x in R if x["lvl"] == l],
                      [float(x["appr"]) for x in R if x["lvl"] == l]) for l in range(1, 6)]
        by = {(x["t"], x["lvl"], x["rep"]): x[key] for x in R}
        pr = [(v, by[(t, l, "2")]) for (t, l, rp), v in by.items()
              if rp == "1" and (t, l, "2") in by]
        trt = pearson([a for a, _ in pr], [b for _, b in pr])
        dec, T = gate_decisions(R, key)
        got = [sum(1 for (t, l, rp), v in dec.items() if l == lvl and v)
               for lvl in range(1, 6)]
        np_ = fl = 0
        for (t, l, rp), v in dec.items():
            if rp == "1" and (t, l, "2") in dec:
                np_ += 1
                fl += v != dec[(t, l, "2")]
        nm, nmt = nonmonotone(dec)
        # Holdout falsifier check: score rank of holdouts vs the fitted bar.
        hold = {h: {f"R{l}": (next((x for x in R if x["t"] == h and x["lvl"] == l), None) or {}
                              ).get(key) for l in range(1, 6)} for h in HOLDOUTS}
        hold_above = {h: sum(1 for l in range(1, 6)
                             if hold[h][f"R{l}"] is not None
                             and T.get(l) is not None
                             and hold[h][f"R{l}"] >= T[l])
                      for h in HOLDOUTS}
        out["scores"][key] = {
            "r_per_level": [round(v, 3) for v in rs],
            "test_retest_r": round(trt, 3),
            "gate_approvals_rep2_fit": got,
            "gate_flips": f"{fl}/{np_}",
            "gate_flip_rate": round(fl / max(np_, 1), 3),
            "non_monotone_paths": f"{nm}/{nmt}",
            "thresholds_rep1_fit": {f"R{l}": T[l] for l in range(1, 6)},
            "holdout_scores": hold,
            "holdout_levels_at_or_above_bar": hold_above,
        }
    return out


def render_md(results):
    L = ["# CR256 Step 0 — evidence-bar proxy-gate simulation", "",
         "Split-fit validation: T(level) fit on rep-1 rooms, applied to all rooms.",
         f"Targets per 60 rooms: {TARGET}. Holdouts excluded from the approval set "
         "before ranking (R5 = 46/60 investable universe).",
         "Scores are PROXIES over Jev-scored turns — the real composite (claim cards + "
         "objections) is gated on spec prerequisite M7 (debator turns missing from Jev).", ""]
    for res in results:
        L.append(f"## {res['arm']} (rooms with Jev: {res['rooms']})")
        L.append("")
        L.append("| score | r/level R1..R5 | test-retest r | rep1-fit approvals R1..R5 "
                 "| flips | non-monotone |")
        L.append("|---|---|---|---|---|---|")
        for key, s in res["scores"].items():
            L.append(f"| {key} | {' '.join(f'{v:+.2f}' for v in s['r_per_level'])} "
                     f"| {s['test_retest_r']:+.2f} | {s['gate_approvals_rep2_fit']} "
                     f"| {s['gate_flips']} ({s['gate_flip_rate']:.0%}) "
                     f"| {s['non_monotone_paths']} |")
        L.append("")
        for key, s in res["scores"].items():
            leaks = {h: n for h, n in s["holdout_levels_at_or_above_bar"].items() if n}
            L.append(f"- **{key}** thresholds (rep1-fit): "
                     + ", ".join(f"R{l}={s['thresholds_rep1_fit'][f'R{l}']:.3f}" for l in range(1, 6))
                     + f" — holdout at/above bar: {leaks or 'none'}")
        L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(OUT / "evidence_bar_step0"))
    args = ap.parse_args()
    od = Path(args.out_dir)
    od.mkdir(parents=True, exist_ok=True)

    results = [simulate_arm(arm) for arm in ARMS]
    (od / "report.json").write_text(json.dumps(
        {"target": TARGET, "holdouts": list(HOLDOUTS), "arms": results}, indent=2))
    md = render_md(results)
    (od / "report.md").write_text(md)
    print(md)
    print(f"\nwritten: {od / 'report.md'} + report.json")


if __name__ == "__main__":
    main()
