# CR247 — Phase 5 gate measurement

Gate: `benchmarks/room-gate.yaml`, harness 5K floor, backend at af8dbd86
(Phase 5 remaining personas). Refs: `phase34_gate.md`.

## Verdicts

| Ticker | Provider | Phase 3+4 gate | Phase 5 gate |
|---|---|---|---|
| AAPL | vLLM | APPROVE 5/5 | APPROVE 4/5 (veto attempted; see below) |
| AAPL | DeepInfra | PASS (resurrected) | PASS 0/5 (resurrection upheld) |
| V | vLLM | APPROVE 4/5 | APPROVE 5/5 (veto attempted) |
| V | DeepInfra | PASS (resurrection upheld) | PASS 0/5 (resurrection upheld) |

Cross-provider divergence on AAPL is now a stable, repeated pattern at the
same spot price (vLLM-family approves the pullback-entry thesis, GLM-family
passes) — provider-shaped verdicts on identical mandates, which is itself
data for CR240 (D18's model-bias question).

## Gate status — ALL FOUR ARMS OK

- Zero truncation; all stances present; PM draws parseable everywhere
  (vLLM schema-enforced; DeepInfra tolerant-parsed 5/5 and 5/5).
- Phase 5 persona changes (Trader float/volume context, MA put/call
  attribution, News 4.02 stop-press) shipped without envelope or
  format drift.

## Review machinery — third live exercise

- DeepInfra CIO (both PASS arms): resurrection review on vLLM, both
  upheld — two more clean cross-model audits.
- vLLM CIO (both APPROVE arms): veto review routed to `kimi` → 401
  (Mac env key-product mismatch, documented in phase34_gate.md) →
  fail-safe, verdict unchanged, journaled. The fail-safe has now held
  four times in production-shaped conditions.

## Phase 5 observed live

- Trader outputs reference float/volume fill context (AAPL gate turns
  cite the float line).
- No persona-length regressions: fundamentals +2.7K and trader +0.9K
  input-side growth caused zero truncation at the 5K floor.

## Build state at this gate

Phases 0–5 all shipped and gated. Remaining: Phase 6 digest (build in
progress), then the full-build final gate + SPEC status sweep.
