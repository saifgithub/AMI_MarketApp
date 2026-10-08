# CR251 — Frozen production baseline (heuristics-off)

**Status:** FROZEN reference. Do not edit; diff future changes against this.

This is the benchmark of the production Room (`prompt_variant:
backend-default`, vLLM `ami-llm` = qwen38-flash-next-abliterated-nvfp4)
before any prompt/consistency change ships (pre-CR250, pre-CR252, pre
Phase-2 control). Captured 2026-10-07 from the first full 300-room pass
(60 rooms × risk 1–5 × 30 CR228 tickers, n=2 reps; 57 rooms later
re-run after NO_VERDICT infrastructure casualties — see analysis_r2).

## The canonical numbers (first pass, committed as analysis_r1.md)

Pooled APPROVE counts, first pass: R1=0, R2=3, R3=4, R4=24, R5=13 (R5
maimed by 25 infrastructure NO_VERDICTs). **CORRECTED (analysis_r2, R5
re-run to full 60): R1=0, R2=3, R3=4, R4=24, R5=26 — MONOTONE: TRUE**
at the pooled level; per-ticker violations 15→10. The R4→R5 dip was a
denominator artifact, not system behavior. Key findings:

1. Risk knob moves approvals 0%→43% but as an R3→R4 cliff, not a ramp.
2. **Zero evidence discrimination** — mean Jev support of APPROVE rooms
   ≈ PASS rooms (Δ≈0.00 at every level). Verdicts do not track evidence.
3. Risk-bar curve flat — min support among approving rooms 0.55–0.64,
   no movement across levels.
4. Repeat stability: verdict flips 20%; Jev room-mean flips 32%.
5. Per-desk support: aggressive 0.49 / neutral 0.57 / bull 0.62
   (weakest) … trader 0.92 / market 0.90 / RM 0.90 (strongest).

## Where the raw data lives (immutable)

- Verdict-level: `docs/tools/room_investigation_V2/out/cr251-risk-matrix/
  r{1..5}/runs_*.jsonl` (gitignored; mutated by resume re-runs).
- **The immutable archive is Alpha's `llm_audit`** (every turn of every
  room, system prompt + messages + response, keyed by the arm user_ids in
  the JSONLs). Nothing here is lost when out/ changes.
- Jev turn scores: `out/cr251-risk-matrix/jev/r{1..5}.jsonl`.

## Diff protocol for any change

1. Make the change under its CR (production fold-in or variant).
2. Run AAPL+V R3 gate (D26) — quick directional read.
3. For adoption-grade evidence: full 30×5 matrix re-run; compare pooled
   curve, discrimination Δ, risk-bar, stability against the numbers
   above. Analysis outputs are versioned (analysis_r1, analysis_r2, …)
   and committed here.
