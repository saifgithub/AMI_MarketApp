# CR247 — Phase 1B gate measurement

Gate: `benchmarks/room-gate.yaml`, harness 5K floor. After = backend at
9d5a2384 (Phase 1B: SBC-adjusted FCF, ROIC, put/call). Baseline refs in
`phase1a_gate.md`.

## Verdicts

| Ticker | Provider | 1A gate | 1B gate | Note |
|---|---|---|---|---|
| AAPL | vLLM | PASS 1/5 | **APPROVE 3/5** | flipped; AAPL now unstable across runs on vLLM (PASS ×4 → APPROVE) |
| AAPL | DeepInfra | PASS 0/5 | PASS 0/5 | stable |
| V | vLLM | APPROVE 5/5 | PASS 0/5 | flipped again — V remains the unstable ticker |
| V | DeepInfra | APPROVE 5/5 | APPROVE | stable (4th consecutive APPROVE-family run on DeepInfra) |

## Gate status

| Ticker | Provider | 1B gate | Findings |
|---|---|---|---|
| AAPL | vLLM | OK | — |
| AAPL | DeepInfra | OK | — |
| V | vLLM | FAIL | neutral_debator missing stance (2nd occurrence of this exact defect on vLLM/V); PM draw 0 non-JSON (recurring vLLM PM pattern, retry absorbed) |
| V | DeepInfra | OK | — |

## Observations

- **Zero truncation on both providers again** (floor holds).
- **SBC/ROIC degrade-loudly fired in the harness** — the Mac-side EDGAR
  store lacked the new tags, so `sbc_absent` / `roic_absent` +
  `edgar_sbc_roic_tags_not_ingested` warned with the exact fix on both
  tickers. CR040 working as designed; one-time `ingest_edgar_facts.py`
  for AAPL/V ran 2026-09-29 so the next gate sees the lines live.
- **AAPL flipped to APPROVE 3/5 on vLLM while staying PASS 0/5 on
  DeepInfra** — cross-provider divergence on the same day. Combined with
  V's flips, single-draw gates can only certify the harness, not verdict
  quality; the resampling instrument (repeats≥5) is needed for any
  verdict-level claim. Recorded for Phase 2.4.
- **vLLM/V neutral_debator missing-stance recurred** (also seen in the
  pre-1A gate) — worth a targeted `room_replay.py` on that exact captured
  prompt before Phase 5 persona work touches the debators.
