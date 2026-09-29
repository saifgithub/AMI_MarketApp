# CR247 — Phase 2 gate measurement

Gate: `benchmarks/room-gate.yaml`, harness 5K floor, backend at 6c6942f7
(2.1-2.3 scoreboard/conviction/horizon + ROOM_JSON_CONSTRAINTS_ENABLED
default-ON). Refs: `phase1cd_gate.md` (the JSON regression this gate
re-measures).

## Verdicts

| Ticker | Provider | 1C+1D gate | Phase 2 gate |
|---|---|---|---|
| AAPL | vLLM | PASS | PASS 2/5 |
| AAPL | DeepInfra | PASS | APPROVE 5/5 (cross-provider divergence; spot 329.4 near the support thesis — inputs moved) |
| V | vLLM | PASS | APPROVE 4/5 |
| V | DeepInfra | APPROVE | APPROVE 5/5 (consistent) |

## Gate status — ALL FOUR ARMS OK

| Ticker | Provider | Findings |
|---|---|---|
| AAPL | vLLM | none — PM 5/5 schema-enforced draws, zero non-JSON, zero recovery draws |
| AAPL | DeepInfra | none — 5/5 parseable via tolerant parser (constraint loudly unsupported on GLM, one warn per draw, as designed) |
| V | vLLM | none — 5/5 schema-enforced |
| V | DeepInfra | none — 5/5 parseable |

## The JSON regression is fixed on vLLM

Phase 1C+1D measured ~50% non-JSON PM draws on vLLM. This gate: **0/10
non-JSON across both vLLM convenes, 0 recovery draws.** Cause was
CR210's constraint machinery sitting behind a False code default in
harness runs (production had it env-on since 2026-09-03); the flip makes
harness = production. DeepInfra remains instructional (capability gate
drops the schema loudly; parser held 10/10). Residual risk: if GLM's
format adherence decays under longer prompts again, its only guard is
instructional — a DeepInfra-side decision for CR240, not CR247.

## Phase 2 items observed live

- Scoreboard renders AGENT|STANCE|SIZE|CONVICTION|HEADLINE with officer
  sizes in the SIZE column and `—` for the eight non-officer seats.
- Horizon discipline line present in Trader/debator/PM blocks (long
  mandate); analysts and the structured Risk Officer byte-identical.
- Conviction legend maps the three seat-specific names to one envelope.
- PM input +1.7K chars caused no truncation (5K floor; worst draw 1,037
  output chars) and no latency anomaly (convene ~6.5-7 min vLLM, ~8.4 min
  DeepInfra — in line with pre-Phase-2).

## Standing instability note

AAPL diverges across providers again (PASS 2/5 vs APPROVE 5/5) on the
same mandate and near-identical sheets — single-draw gates certify the
harness, not verdict stability. The resampling instrument (repeats ≥5 on
a fixed input snapshot) remains the open item for any verdict-level
claim; Phase 2.4's anchoring measurement should use it.
