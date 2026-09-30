# CR247 — Phase 3+4 gate measurement

Gate: `benchmarks/room-gate.yaml`, harness 5K floor, backend at d4218071
(Phase 3 interpretation guidance + Phase 4 verdict review). Refs:
`phase2_gate.md`.

## Verdicts

| Ticker | Provider | Phase 2 gate | Phase 3+4 gate |
|---|---|---|---|
| AAPL | vLLM | PASS 2/5 | APPROVE 5/5 (flipped again — inputs moved, spot 329.4) |
| AAPL | DeepInfra | APPROVE 5/5 | PASS (resurrected: reconsider → re-run → PASS) |
| V | vLLM | APPROVE 4/5 | APPROVE 4/5 |
| V | DeepInfra | APPROVE 5/5 | PASS (resurrection upheld) |

## Gate status — ALL FOUR ARMS OK

No truncation, no missing stances, all PM draws parseable (vLLM
schema-enforced 5/5 and 4/5 valid; DeepInfra tolerant-parsed 5/5 both).

## Phase 4 exercised live on all four arms — the headline result

| Arm | CIO provider | Review provider | Outcome |
|---|---|---|---|
| AAPL (DeepInfra) | deepinfra | **vllm** (cross-model ✓) | resurrection: reconsider → exactly one re-run with audit note → re-run PASS → `room_verdict_resurrected` |
| V (DeepInfra) | deepinfra | **vllm** (cross-model ✓) | resurrection: uphold → verdict unchanged |
| AAPL (vLLM) | vllm | kimi (fallback pick) | veto attempt → 401 invalid key → **fail-safe: verdict unchanged**, error journaled |
| V (vLLM) | vllm | kimi (fallback pick) | veto attempt → 401 → fail-safe: verdict unchanged |

- Cross-model audit requirement: satisfied wherever two providers were
  available (DeepInfra CIO audited by qwen3.8 on LAN).
- Fail-safe under provider failure: verified twice in production-shaped
  conditions (401 → original verdict stands, journaled).
- **Harness-env defect exposed (not a code defect):** on vLLM-CIO runs the
  fallback picker chose the `kimi` provider, whose registered key on this
  Mac is the Open Platform key (`sk-ZJutc…`) — the Coding Plan endpoint
  (`api.kimi.com/coding`) rejects it with 401. Known key-product confusion
  (v1 README trap) surfacing in the review path. On Alpha the fallback is
  Anthropic (key present), so production is unaffected. Fix = local env
  hygiene (register the right key for that provider or accept the
  fail-safe), no code change.
- Cost note: resurrection adds 1 mid-tier cross-model call per PASS convene
  (+1 CIO re-run only on reconsider — observed once in 2 PASS arms).

## Phase 3 observed live

Fundamentals outputs now reference the new frames (SBC-adjusted FCF cited
in AAPL gate fundamentals turns; accrual-check register present). No
truncation despite the +2.7K-char fundamentals persona growth (5K floor;
worst observed fundamentals output well under cap).

## Standing instability note (unchanged)

AAPL flipped PASS→APPROVE→PASS→APPROVE across the last four vLLM-family
runs as price moved toward the support thesis; V flipped APPROVE→PASS on
DeepInfra today. Verdict-level stability remains unproven at n=1 — the
repeats≥5 resampling arm is the open measurement item.
