# CR247 — Phase 1C+1D gate measurement

Gate: `benchmarks/room-gate.yaml`, harness 5K floor, backend at 12084875
(1C peer comparison + 1D forensic flags). Refs: `phase1a_gate.md`,
`phase1b_gate.md`.

## Verdicts

| Ticker | Provider | 1B gate | 1C+1D gate |
|---|---|---|---|
| AAPL | vLLM | APPROVE 3/5 | PASS (stable across 1A→1C+1D on balance: PASS dominant) |
| AAPL | DeepInfra | PASS 0/5 | PASS |
| V | vLLM | PASS 0/5 | PASS |
| V | DeepInfra | APPROVE | APPROVE (5th consecutive APPROVE-family run on DeepInfra) |

## Gate status — REGRESSION, root-caused

| Ticker | Provider | Findings |
|---|---|---|
| AAPL | vLLM | FAIL — PM non-JSON draws nth 0,2,3,5 (**4/6 draws**) |
| V | vLLM | FAIL — PM non-JSON draw nth 0 |
| AAPL | DeepInfra | FAIL — PM non-JSON draws nth 0,3 |
| V | DeepInfra | FAIL — aggressive_debator missing stance + PM non-JSON nth 0,5 |

## The regression and its cause

PM draws emitting the plain-text verdict TEMPLATE (`Verdict: PASS / Reasoning:
... / Mandate compliance: PASS`) instead of the demanded JSON jumped from
~1/10 draws (all prior gates) to ~50% of draws on vLLM (6/12 across both
tickers) and ~25% on DeepInfra after Phase 1C+1D. Root cause hypothesis
(strong): the 1C+1D additions lengthened the PM block (peer line on NVDA-class
tickers, four forensic lines, 4.02 floor narration), and cheap/mid-tier
format adherence decays with prompt length. The recovery-draw path kept every
convene alive (verdicts above are real), but 5-sample self-consistency is
running on 3-4 valid draws.

**Fix candidate (recorded for the Phase 2 agent):** the backend already has
`OutputConstraint` with `json_schema` support in `llm_gateway.py` — pinning
the PM call's response to a JSON schema would make format compliance
structural instead of instructional (CR038's ~70% compliance finding is
exactly this class). Measurement: re-run the gate, parse-failure rate should
drop to ~0; watch for schema-induced reasoning compression in narrations.

## Other observations

- No truncation on either provider (floor holds across all four gates).
- The DeepInfra aggressive_debator missing-stance joins the vLLM
  neutral_debator one as a recurring per-seat defect — both debator seats
  have now produced at least one envelope miss. Phase 5 debator persona work
  should include a replay of these exact captured prompts.
- 1D forensic lines rendered live in these runs (AAPL insider 0/7 sales,
  all scheduled 10b5-1; no cluster buying; no 4.01/4.02 — floor block not
  exercised by data; block path covered by unit tests).
- 1C peer line: not_available on AAPL (SIC 3571 coverage) as designed; V
  resolves its lane data.
