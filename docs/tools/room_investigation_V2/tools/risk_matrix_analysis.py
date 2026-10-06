"""CR251 — risk-matrix analysis: monotonicity, discrimination, stability.

Reads the five risk-level run JSONLs (verdicts) and the five Jev scoring
JSONLs (turn quality), then produces the science report Saiful asked for:

  a. APPROVE-count-by-risk curve per ticker + pooled — monotonicity test
  b. Discrimination — does room evidence score separate APPROVE from PASS
     at each risk level
  c. The risk-bar curve — evidence score at which each tier approves
  d. Stability — verdict flips vs Jev-score flips across the 2 repeats
  e. Violation decomposition — every monotonicity break tagged
     evidence-limited vs decision-limited

Writes analysis.md next to the inputs and prints the pooled summary.

Usage (from anywhere):
  python3 docs/tools/room_investigation_V2/tools/risk_matrix_analysis.py \
      --base docs/tools/room_investigation_V2/out/cr251-risk-matrix
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
    """Mean evidence-support score of a room's scored turns (0..1)."""
    vals = []
    for t in turns:
        a = t.get("answers") or {}
        cc = a.get("core_claim_supported") or {}
        n = SUPPORT_NUM.get(cc.get("choice"))
        if n is not None:
            vals.append(n)
    return sum(vals) / len(vals) if vals else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    args = ap.parse_args()
    base = Path(args.base)

    # ── verdicts: {(ticker, level): [action, ...]} ──────────────────────────
    verdicts: dict[tuple[str, int], list[str]] = defaultdict(list)
    for r in LEVELS:
        for rec in load(base / f"r{r}" / f"runs_cr251-risk-matrix-r{r}.jsonl"):
            v = rec.get("verdict")
            action = v.get("action") if isinstance(v, dict) else v
            verdicts[(rec["ticker"], r)].append(str(action))

    # ── Jev room scores: {(ticker, level): [score, ...]} ────────────────────
    jev_rooms: dict[tuple[str, int], list[float]] = defaultdict(list)
    turn_detail: dict[tuple[str, int, str], list[dict]] = defaultdict(list)
    for r in LEVELS:
        for rec in load(base / "jev" / f"r{r}.jsonl"):
            if "answers" not in rec:
                continue
            turn_detail[(rec["ticker"], r, rec["agent_id"])].append(rec)
        # group scored turns into rooms by arm_key
        by_arm: dict[str, list[dict]] = defaultdict(list)
        for rec in load(base / "jev" / f"r{r}.jsonl"):
            if "answers" in rec and rec.get("arm_key"):
                by_arm[rec["arm_key"]].append(rec)
        for arm_key, turns in by_arm.items():
            ticker = turns[0].get("ticker")
            s = room_score(turns)
            if ticker and s is not None:
                jev_rooms[(ticker, r)].append(s)

    # ── a. monotonicity per ticker ──────────────────────────────────────────
    tickers = sorted({t for t, _ in verdicts})
    lines = ["# CR251 risk-matrix analysis\n",
             "APPROVE counts per ticker across risk levels 1–5 (n=2 reps each):\n",
             "| Ticker | R1 | R2 | R3 | R4 | R5 | Monotone | Avg Jev score |",
             "|---|---|---|---|---|---|---|---|"]
    pooled = defaultdict(int)
    violations = []
    for t in tickers:
        counts = [sum(1 for v in verdicts.get((t, r), []) if v == "APPROVE")
                  for r in LEVELS]
        for r, c in zip(LEVELS, counts):
            pooled[r] += c
        mono = all(counts[i + 1] >= counts[i] for i in range(4))
        if not mono:
            violations.append((t, counts))
        js = jev_rooms.get((t, 1), []) + jev_rooms.get((t, 5), [])
        avg_j = f"{sum(js) / len(js):.2f}" if js else "?"
        lines.append(f"| {t} | {counts[0]} | {counts[1]} | {counts[2]} | "
                     f"{counts[3]} | {counts[4]} | {'✓' if mono else '✗'} | {avg_j} |")

    # ── pooled curve + b. discrimination + c. risk-bar ─────────────────────
    lines += ["", "## Pooled APPROVE counts (of 60 convenes per level)", "",
              "| Risk | APPROVE |", "|---|---|"]
    for r in LEVELS:
        lines.append(f"| R{r} | {pooled[r]} |")
    mono_pooled = all(pooled[l + 1] >= pooled[l] for l in LEVELS[:-1])
    lines.append(f"\nPooled monotonic: {'YES' if mono_pooled else 'NO'}")

    lines += ["", "## Discrimination — room evidence score, APPROVE vs PASS", "",
              "| Risk | APPROVE rooms (n, mean) | PASS rooms (n, mean) | Δ |", "|---|---|---|---|"]
    bar = {}
    for r in LEVELS:
        ap_s, pa_s = [], []
        for t in tickers:
            for s in jev_rooms.get((t, r), []):
                acts = verdicts.get((t, r), [])
                (ap_s if "APPROVE" in acts else pa_s).append(s)
        if ap_s and pa_s:
            d = sum(ap_s) / len(ap_s) - sum(pa_s) / len(pa_s)
            lines.append(f"| R{r} | {len(ap_s)}, {sum(ap_s)/len(ap_s):.2f} | "
                         f"{len(pa_s)}, {sum(pa_s)/len(pa_s):.2f} | {d:+.2f} |")
            bar[r] = min(ap_s)
    lines += ["", "## Risk-bar curve (min evidence score among APPROVEs)", "",
              "| Risk | min support of an approving room |", "|---|---|"]
    for r in LEVELS:
        lines.append(f"| R{r} | {bar.get(r, '—')} |")

    # ── d. stability ────────────────────────────────────────────────────────
    vflip = jflip = pairs = 0
    for t in tickers:
        for r in LEVELS:
            acts = verdicts.get((t, r), [])
            scores = jev_rooms.get((t, r), [])
            if len(acts) == 2 and len(scores) == 2:
                pairs += 1
                vflip += acts[0] != acts[1]
                jflip += abs(scores[0] - scores[1]) > 0.10
    lines += ["", "## Stability across the 2 repeats", "",
              f"- comparable cells: {pairs}",
              f"- verdict flips: {vflip} ({vflip/max(pairs,1)*100:.0f}%)",
              f"- Jev room-score flips (>0.10): {jflip} ({jflip/max(pairs,1)*100:.0f}%)",
              ""]

    # ── e. violation decomposition ──────────────────────────────────────────
    lines += ["## Monotonicity violations — decomposition", ""]
    if not violations:
        lines.append("None — every ticker monotone.")
    for t, counts in violations:
        allscores = [s for s in jev_rooms.get((t, 1), [])] + \
                    [s for s in jev_rooms.get((t, 5), [])]
        mean_low = allscores and (sum(allscores) / len(allscores)) < 0.5
        kind = "evidence-limited (low support at extremes)" if mean_low \
            else "decision-limited (support present, verdict curve still breaks)"
        lines.append(f"- **{t}** counts {counts} → **{kind}**")

    # per-agent mean support (the desk-level quality view)
    lines += ["", "## Per-desk mean support score (all levels)", "",
              "| Agent | mean support | n |", "|---|---|---|"]
    agg: dict[str, list[float]] = defaultdict(list)
    for (_, _, agent), recs in turn_detail.items():
        for rec in recs:
            cc = (rec.get("answers") or {}).get("core_claim_supported") or {}
            n = SUPPORT_NUM.get(cc.get("choice"))
            if n is not None:
                agg[agent].append(n)
    for agent in sorted(agg, key=lambda a: sum(agg[a]) / len(agg[a])):
        lines.append(f"| {agent} | {sum(agg[agent])/len(agg[agent]):.2f} | {len(agg[agent])} |")

    out = base / "analysis.md"
    out.write_text("\n".join(lines) + "\n")
    print(f"report → {out}")
    print("\n".join(lines[1:12]))
    print(f"...\npooled: " + " ".join(f"R{r}={pooled[r]}" for r in LEVELS)
          + f" monotone={mono_pooled} violations={len(violations)}")


if __name__ == "__main__":
    main()
