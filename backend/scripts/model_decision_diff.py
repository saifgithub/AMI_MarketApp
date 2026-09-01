"""CR217 — compare two models' Room DECISIONS on the same (ticker, as_of) pairs.

This is deliberately not an outcome scorer. `backtest_report.py` grades whether a
verdict made money; this grades whether two models decide the same way given the
same inputs, and whether the challenger's verdicts are real decisions at all.

Why that separation matters here. The CR217 head-to-head cannot resolve an outcome
difference: the banked baseline's own 62-day paired spread is +5.09% with a
date-clustered CI of −1.41…+12.88 over 18 dates, so a challenger arm carries a
similar band and the DIFFERENCE of the two spans roughly ±20 points. No realistic
model gap is that large. Running longer does not fix it — the binding constraint is
the number of as-of dates, and the as-of window is hard-capped by the model cutoff.
So the honest deliverable is the part that IS measurable at n=54: does the
challenger produce valid, parseable, non-fail-safe verdicts, and where does it
disagree?

The one number that must never be read as judgement is the fail-safe count. A
DEF059 outage PASS is a COMPLETED run carrying a PASS verdict, indistinguishable
from a decision except via `is_llm_outage_verdict`. Count those separately or a
starved model reads as a conservative one — which, for a model whose decode budget
was mis-sized (CR130, CR211, and GLM here), is exactly the wrong conclusion.

Usage:
    python scripts/model_decision_diff.py \
        --baseline backtest_results/runs_r70-outcome-2.jsonl \
        --challenger backtest_results/runs_cr217-glm-1.jsonl \
        --baseline-label "ami-llm (pre-CR211)" --challenger-label "GLM-5.3-Flash" \
        --out backtest_results/decision_diff_cr217.md
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.room_runner import is_llm_outage_verdict  # noqa: E402

ACTIONS = ("APPROVE", "MODIFY", "PASS", "REJECT")


def load(path: Path) -> dict[tuple[str, str], dict]:
    """Completed runs keyed by (ticker, as_of).

    Only `completed` rows: a pair that errored or was never reached is not part of
    the set being paired against, and including it would make the two arms
    different sizes while still looking paired.
    """
    out: dict[tuple[str, str], dict] = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("status") != "completed":
                continue
            out[(rec["ticker"], rec["as_of"])] = rec
    return out


def classify(rec: dict) -> tuple[str, bool]:
    """(action, is_failsafe) for one run."""
    verdict = rec.get("verdict") or {}
    failsafe = bool(is_llm_outage_verdict(verdict))
    return verdict.get("action") or "MISSING", failsafe


def pct(n: int, d: int) -> str:
    return f"{100.0 * n / d:.1f}%" if d else "—"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True, type=Path)
    ap.add_argument("--challenger", required=True, type=Path)
    ap.add_argument("--baseline-label", default="baseline")
    ap.add_argument("--challenger-label", default="challenger")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    base_all, chal_all = load(args.baseline), load(args.challenger)
    shared = sorted(set(base_all) & set(chal_all))
    if not shared:
        raise SystemExit(
            "no (ticker, as_of) pair completed in BOTH arms — nothing is paired here"
        )

    L: list[str] = []
    add = L.append
    add(f"# CR217 — decision diff: {args.challenger_label} vs {args.baseline_label}")
    add("")
    add(
        f"Paired on **{len(shared)}** (ticker, as_of) pairs completed in both arms "
        f"(baseline file has {len(base_all)} completed, challenger {len(chal_all)}). "
        f"Distinct as-of dates: **{len({d for _, d in shared})}**."
    )
    add("")
    add(
        "**This is a decision comparison, not an outcome comparison.** It says nothing "
        "about which model made money. See the CR doc for why an outcome read is not "
        "resolvable at this sample size."
    )
    add("")

    # ── Fail-safes first: they are not decisions and must leave the population ──
    base_fs = [p for p in shared if classify(base_all[p])[1]]
    chal_fs = [p for p in shared if classify(chal_all[p])[1]]
    add("## Fail-safe accounting (DEF059) — read this before any rate below")
    add("")
    add(
        "An LLM-outage fail-safe is a *completed* run carrying a PASS verdict. Counted "
        "as a decision it makes a starved or unreachable model look like a cautious "
        "one. These are excluded from everything that follows."
    )
    add("")
    add("| arm | fail-safe runs | of paired |")
    add("|---|---|---|")
    add(f"| {args.baseline_label} | {len(base_fs)} | {pct(len(base_fs), len(shared))} |")
    add(f"| {args.challenger_label} | {len(chal_fs)} | {pct(len(chal_fs), len(shared))} |")
    add("")

    clean = [p for p in shared if p not in set(base_fs) | set(chal_fs)]
    if not clean:
        add("**No pair is clean in both arms — no decision comparison is possible.**")
        _emit(L, args.out)
        return
    add(f"Clean, comparable pairs: **{len(clean)}**.")
    add("")

    # ── Action mix ──────────────────────────────────────────────────────────
    bc = collections.Counter(classify(base_all[p])[0] for p in clean)
    cc = collections.Counter(classify(chal_all[p])[0] for p in clean)
    add("## Action mix on the clean paired set")
    add("")
    add(f"| action | {args.baseline_label} | {args.challenger_label} |")
    add("|---|---|---|")
    for a in ACTIONS:
        add(f"| {a} | {bc.get(a, 0)} ({pct(bc.get(a, 0), len(clean))}) | "
            f"{cc.get(a, 0)} ({pct(cc.get(a, 0), len(clean))}) |")
    missing_b, missing_c = bc.get("MISSING", 0), cc.get("MISSING", 0)
    if missing_b or missing_c:
        add(f"| MISSING (unparseable) | {missing_b} | {missing_c} |")
    add("")

    # ── Agreement, and its direction ────────────────────────────────────────
    SIGNAL = {"APPROVE", "MODIFY"}
    both_sig = sum(
        1 for p in clean
        if classify(base_all[p])[0] in SIGNAL and classify(chal_all[p])[0] in SIGNAL
    )
    both_no = sum(
        1 for p in clean
        if classify(base_all[p])[0] not in SIGNAL and classify(chal_all[p])[0] not in SIGNAL
    )
    only_base = sum(
        1 for p in clean
        if classify(base_all[p])[0] in SIGNAL and classify(chal_all[p])[0] not in SIGNAL
    )
    only_chal = sum(
        1 for p in clean
        if classify(base_all[p])[0] not in SIGNAL and classify(chal_all[p])[0] in SIGNAL
    )
    add("## Agreement (signal = APPROVE or MODIFY)")
    add("")
    add(f"| | {args.challenger_label} signal | {args.challenger_label} no-signal |")
    add("|---|---|---|")
    add(f"| **{args.baseline_label} signal** | {both_sig} | {only_base} |")
    add(f"| **{args.baseline_label} no-signal** | {only_chal} | {both_no} |")
    add("")
    add(f"- Raw agreement: **{pct(both_sig + both_no, len(clean))}** "
        f"({both_sig + both_no}/{len(clean)})")
    add(f"- Discordant pairs: **{only_base + only_chal}** "
        f"({only_base} baseline-only, {only_chal} challenger-only)")
    add("")
    add(
        "Raw agreement is inflated by the shared no-signal majority: at a ~9% approve "
        "rate two models that never agree on a single name still agree on ~82% of pairs. "
        "The discordant split is the informative cell."
    )
    add("")
    # McNemar's exact test on the discordant pairs — the paired-design test.
    n_disc = only_base + only_chal
    if n_disc:
        from math import comb

        k = min(only_base, only_chal)
        p_two = min(1.0, 2 * sum(comb(n_disc, i) for i in range(k + 1)) / (2 ** n_disc))
        add(f"- McNemar exact (discordant only, n={n_disc}): **p = {p_two:.4f}** "
            f"for a difference in signal rate.")
    else:
        add("- McNemar: no discordant pairs, so the two arms' signal rates are identical.")
    add("")

    # ── Wall clock ──────────────────────────────────────────────────────────
    add("## Convene wall clock")
    add("")
    add("| arm | n | mean | median | p90 | max |")
    add("|---|---|---|---|---|---|")
    for label, src in ((args.baseline_label, base_all), (args.challenger_label, chal_all)):
        d = sorted(src[p]["duration_ms"] / 1000 for p in clean if src[p].get("duration_ms"))
        if not d:
            add(f"| {label} | 0 | — | — | — | — |")
            continue
        add(f"| {label} | {len(d)} | {statistics.mean(d):.0f}s | "
            f"{statistics.median(d):.0f}s | {d[int(0.9 * len(d)) - 1]:.0f}s | {max(d):.0f}s |")
    add("")

    # ── The names they disagreed on, so the disagreement is inspectable ─────
    if only_base or only_chal:
        add("## Discordant names")
        add("")
        add("| ticker | as_of | " + f"{args.baseline_label} | {args.challenger_label} |")
        add("|---|---|---|---|")
        for p in clean:
            ba, ca = classify(base_all[p])[0], classify(chal_all[p])[0]
            if (ba in SIGNAL) != (ca in SIGNAL):
                add(f"| {p[0]} | {p[1]} | {ba} | {ca} |")
        add("")

    _emit(L, args.out)


def _emit(lines: list[str], out: Path | None) -> None:
    text = "\n".join(lines) + "\n"
    if out:
        out.write_text(text)
        print(f"wrote {out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
