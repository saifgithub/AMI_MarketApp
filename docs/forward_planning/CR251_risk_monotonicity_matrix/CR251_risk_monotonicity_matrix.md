# CR251 — Risk-appetite monotonicity science matrix

**Status:** in_progress · **Owner:** AT:K3 · **Opened:** 2026-10-06

Saiful's vision: 5 risk values × the CR228 30-ticker universe — from lowest
to highest risk appetite, the number of approved convenes should increase.
Jev brings the science (measurement) and, in Phase 2, the stability (control).

## Phase 1 — measurement (this CR, zero Room behavior change)

300 convenes: 30 tickers × risk 1–5 × 2 repeats · vLLM production prompts ·
conc 4. Benchmarks: `docs/tools/room_investigation_V2/benchmarks/
cr251-risk-matrix-r{1..5}.yaml`. Runs: `out/cr251-risk-matrix/r{1..5}/`.

Every prose-agent turn Jev-scored (four V1 questions, full request/response
logging): `tools/jev_score_runs.py` → `out/cr251-risk-matrix/jev/r{1..5}.jsonl`.

Analysis: `tools/risk_matrix_analysis.py` → `out/cr251-risk-matrix/analysis.md`:

- **a. Monotonicity** — APPROVE-count curve per ticker + pooled (n=60/level).
- **b. Discrimination** — does room evidence score separate APPROVE from PASS
  at each level.
- **c. Risk-bar curve** — minimum evidence score among approving rooms per
  level: is the knob moving the evidence bar or only the position size.
- **d. Stability** — verdict flips vs Jev-score flips across the 2 repeats:
  is the Jev signal the low-noise anchor.
- **e. Violation decomposition** — every monotonicity break tagged
  evidence-limited (support low everywhere → ticker genuinely unsupported)
  vs decision-limited (support present, curve still breaks → mapping
  miscalibrated → fixable).

## Phase 2 — control (separate CR, gated on Phase 1)

Only if Phase 1 shows discrimination is real: V1-live — measured conviction
cap (Jev support < threshold ⇒ cap at medium pre-RM) + PM context anchoring
(support scores in the CIO block). Acceptance: monotonicity violations down,
same-input flip rate below CR197's ~12%, D26 gate green. Jev never vetoes
(DEF059).

## Boundaries

Jev fixes nothing about provider bias (CR240), data gaps (D28 — SBC/ROIC
absents cap fundamentals support scores), or genuinely weak tickers. It makes
the system measurable and anchorable.
