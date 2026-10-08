# CR253 — Risk-disposition communication fix ("size ≠ worthiness")

**Status:** proposed · **Owner:** harness V2 builder (track R) · **Spec:** AT:K3 · **Opened:** 2026-10-08

## Problem (measured, CR251 frozen baseline)

The risk knob is a switch, not a curve: approvals 0/3/9/26/26 across R1–R5,
transition between R3 and R4. Jev evidence scores are flat per ticker across
levels (±0.05) while verdicts step — e.g. LEVI support 0.89 at R1 with zero
approvals; FCEL approves at R5 on weaker support than it passed at R1; RIOT
0.76–0.80 support, 0/10 approvals (the must-stay-out thesis case). Cause:
the PM is never told that **position size ≠ trade worthiness**, so it
derives willingness-to-act from size headroom.

## What to build (measurement variant first — D32, NO production changes)

### 1. Variant `cr253-disposition` — two additions to the CIO brief

**Decoupling line (verbatim):**

> Position size is set by the mandate cap. Size is not a reason to pass on
> a strong thesis — a great case at risk 1 still approves, at 1% of
> portfolio.

**Per-level disposition table (verbatim):**

> Your approval disposition by the user's risk score:
> - Risk 1 — approve only exceptional evidence: the strongest case you
>   have seen this quarter. A merely correct thesis passes.
> - Risk 2 — approve strong evidence; one unresolved objection is a pass.
> - Risk 3 — approve solid, well-evidenced cases; marginal theses pass.
> - Risk 4 — approve any defensible thesis; reserve passes for flawed cases.
> - Risk 5 — the bar is thesis coherence, not evidence abundance; pass
>   only broken cases.

The exact level wording is the starting hypothesis; the builder may tighten
it but must not weaken the decoupling line. All other agents stay on
production personas (the disposition is a CIO-level instruction; measuring
it at the PM is the cleanest signal).

### 2. Benchmark `cr253-calibration`

75 rooms: tickers LEVI, DHR, APD, PYPL (size-gated movers — Jev support
≥0.77, baseline approvals only at R4+), RIOT (holdout — 0/10 at every
level, must stay out) × risk 1–5 × **3 reps** (n=3 — n=2 cannot separate a
real shift from the 19–20% flip noise) · vLLM · `prompt_variant:
cr253-disposition` · out-dir `out/cr253-calibration/`.

### 3. Analysis vs the frozen baseline

Compare against `CR251_risk_monotonicity_matrix/BASELINE.md` +
`analysis_r2.md` (heuristics-off). Deliverables: per-ticker
support-vs-verdict table (Jev-score the new turns with
`tools/jev_score_runs.py`), pooled curve, sub-cap usage rate
(`size_pct` < level cap on APPROVEs — if zero, ALSO run the sub-cap variant:
same disposition plus "when conviction is moderate, approve at reduced size
rather than passing" — the verdict schema already carries size_pct).

## Acceptance

- **GO:** ≥2 of the 4 movers approve at levels below R4 at ≥2× their
  baseline rate, AND RIOT ≤1/15 approvals. → fold-in CR (production prompt
  change, own gate) + full 30×5 re-baseline.
- **NO-GO:** curve unchanged → prose dispositions can't beat the size
  anchor; the result itself justifies escalation to the measured evidence
  bar (Phase 2 — separate CR, pending Saiful's target-curve policy).

## Boundaries

DEF059 holds (disposition steers, never vetoes). No production prompt
files touched — variant lives under
`docs/tools/room_investigation_V2/benchmarks/cr253-disposition/prompts/`
(assembled: `content/agents/portfolio_manager.md` + the two additions; the
other 11 agents need no override files — pass-through keeps them on
production).
