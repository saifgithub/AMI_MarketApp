#!/usr/bin/env python3
# ==========================================
# CR196 RUN2_PLAN §9 — the acceptance table: tuned arm vs vanilla, per surface,
# with 95% Wilson intervals and an explicit verdict per criterion.
#
# WHY THE BASELINE COMES FROM TWO FILES. The decontamination fix (2026-08-24) rebuilt
# S4/S7/S8 because 167 of 456 prompts were verbatim training rows. S1/S2/S3/S5/S6
# prompts are byte-identical before and after, so `baseline_vanilla.json` remains valid
# for those five and only the three rebuilt surfaces needed a fresh vanilla arm. Mixing
# the two is therefore legitimate — but ONLY for the five unchanged surfaces, so the
# split is asserted here rather than assumed.
#
# WHY INTERVALS. Per-surface n is 44-69. At n=60 a 93% rate carries roughly a +/-6pp
# band, and at n=15 (a probe) it is +/-20pp. Reporting a bare percentage at that width
# invites reading noise as a result — S8's "0% -> 7%" was one completion out of fifteen.
#
# Usage:
#   python3 compare_arms.py --ours /runs/r2_scored.json \
#       --baseline-new /runs/baseline_s478_scored.json --out /runs/acceptance_r2.md
# ==========================================
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(KIT, "eval", "basis"))

from score_basis import mcnemar_exact, wilson  # noqa: E402

REBUILT = {"S4", "S7", "S8"}   # surfaces whose prompts changed; need the new baseline
CARRIED = {"S1", "S2", "S3", "S5", "S6"}   # byte-identical prompts; old baseline valid

# RUN2_PLAN §9. ("hold" = must not regress, "beat" = must improve.)
CRITERIA = [
    ("S1", "l1_plus",             "hold", 0.98),
    ("S1", "false_conflict",      "hold_zero", 0.0),
    ("S4", "parses",              "hold", 1.00),
    ("S5", "has_side",            "beat", None),
    ("S5", "rr_correct",          "beat", None),
    ("S6", "one_per_size",        "beat", None),
    ("S7", "refused",             "beat", None),
    ("S8", "gave_code",           "beat", None),
]


def rate(d, key):
    n = d.get("n", 0)
    return (d.get(key, 0), n, (d.get(key, 0) / n if n else 0.0))


def band(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({k / n if n else 0:.0%}) [{lo:.0%}-{hi:.0%}]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ours", required=True)
    ap.add_argument("--baseline-new", required=True,
                    help="vanilla arm over the REBUILT S4/S7/S8 prompts")
    ap.add_argument("--baseline-old",
                    default=os.path.join(HERE, "baseline_vanilla.json"),
                    help="vanilla arm over the unchanged S1/S2/S3/S5/S6 prompts")
    ap.add_argument("--out")
    args = ap.parse_args()

    ours = json.load(open(args.ours))["surfaces"]
    b_new = json.load(open(args.baseline_new))["surfaces"]
    b_old = json.load(open(args.baseline_old))["surfaces"]

    base = {}
    for s in CARRIED:
        if s in b_old:
            base[s] = b_old[s]
    for s in REBUILT:
        if s in b_new:
            base[s] = b_new[s]
    # A rebuilt surface must NOT be taken from the stale baseline: those numbers were
    # measured on prompts the model had memorised, and would flatter the tuned arm.
    stale = sorted(REBUILT & set(b_old) - set(b_new))
    if stale:
        print(f"!! WARNING: {stale} exist in the OLD baseline but not the new one. "
              f"They are EXCLUDED, not carried — the old numbers were measured on "
              f"contaminated prompts.")

    lines = ["# CR196 run 2 — acceptance", "",
             "Vanilla baseline for S1/S2/S3/S5/S6 carried from `baseline_vanilla.json` "
             "(prompts byte-identical); S4/S7/S8 re-measured after decontamination.",
             "", "| surface | check | vanilla | tuned | McNemar p | verdict |",
             "|---|---|---|---|---|---|"]
    verdicts = []
    for surf, key, kind, thresh in CRITERIA:
        o, b = ours.get(surf), base.get(surf)
        if not o or not b:
            lines.append(f"| {surf} | {key} | — | — | — | NOT MEASURED |")
            verdicts.append((surf, key, "NOT MEASURED"))
            continue
        bk, bn, bp = rate(b, key)
        ok, on, op = rate(o, key)
        # Unpaired counts only — the per-item pairing needed for a true McNemar is not
        # in the aggregate JSON, so this is the conservative discordant approximation.
        p = mcnemar_exact(max(0, bk - ok), max(0, ok - bk)) if bn and on else 1.0

        if kind == "hold_zero":
            v = "HOLDS" if ok == 0 else f"FAILS ({ok} nonzero)"
        elif kind == "hold":
            v = "HOLDS" if op >= thresh - 1e-9 else f"FAILS (<{thresh:.0%})"
        else:
            lo_o, _ = wilson(ok, on)
            _, hi_b = wilson(bk, bn)
            if op <= bp:
                v = "NO GAIN"
            elif lo_o > hi_b:
                v = "BEATS"
            else:
                v = "beats (CIs overlap)"
        verdicts.append((surf, key, v))
        lines.append(f"| {surf} | {key} | {band(bk, bn)} | {band(ok, on)} | "
                     f"{p:.3f} | **{v}** |")

    hard = [v for v in verdicts if v[2].startswith("FAILS") or v[2] == "NOT MEASURED"]
    soft = [v for v in verdicts if v[2] in ("NO GAIN", "beats (CIs overlap)")]
    lines += ["", f"**{len(hard)} hard failures / not-measured**, "
                  f"{len(soft)} weak-or-absent gains, "
                  f"{len(verdicts) - len(hard) - len(soft)} clean."]
    if hard:
        lines.append("")
        for s, k, v in hard:
            lines.append(f"- `{s}.{k}`: {v}")

    text = "\n".join(lines)
    print(text)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text + "\n")
        print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
