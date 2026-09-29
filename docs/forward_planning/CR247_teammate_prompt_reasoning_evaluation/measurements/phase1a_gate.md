# CR247 — Phase 1A gate measurement

Gate: `benchmarks/room-gate.yaml` (AAPL + V, repeats=1, risk_score 3,
backend-default prompts, harness 5K token floor). Before = 2026-09-29
morning runs (backend at 232a0623/c994ed5b, i.e. pre-1A). After = 2026-09-29
05:00 local, backend at a5ee49bc (Phase 1A: 6 CR221 fields graduated).

## Verdicts

| Ticker | Provider | Before (votes) | After (votes) | Δ |
|---|---|---|---|---|
| AAPL | vLLM | PASS 1/5 | PASS 1/5 | none |
| AAPL | DeepInfra | PASS 0/5 | PASS 0/5 | none |
| V | vLLM | PASS 2/5 | APPROVE 5/5 | flipped (unstable across runs; see below) |
| V | DeepInfra | APPROVE 5/5 | APPROVE 5/5 | none |

## Gate status

| Ticker | Provider | Before | After | After findings |
|---|---|---|---|---|
| AAPL | vLLM | FAIL (PM markdown draw 0) | FAIL (PM draw nth=0 non-JSON) | real model defect, retry path absorbed it (1 lost/1 recovered; verdict on 4/5) |
| AAPL | DeepInfra | FAIL (neutral_debator 429 → scripted fallback) | **OK** | — |
| V | vLLM | OK | FAIL (neutral_debator missing stance; PM draw nth=2 non-JSON) | 1 PM draw lost+recovered |
| V | DeepInfra | OK | **OK** | — |

## Observations

- **No truncation anywhere on either provider** — the D25 5000-token floor
  holds; the cheap-tier 1400 truncation from 2026-09-28 is gone.
- **AAPL is verdict-stable across providers and across the 1A change**
  (PASS everywhere, 0–1 approve votes). The new 1A lines (cash-flow bridge,
  FCF history/conversion, ROE history, debt maturity ladder) reached the
  fundamentals sheet live — DeepInfra AAPL cite the 151.9% ROE vs the 149%
  vendor TTM; `interest_cost_absent` fires correctly as designed degrade.
- **V is verdict-unstable** — APPROVE 5/5 and PASS 2/5 on the SAME day on
  the same model, differing inputs only by the live news/price refresh.
  This is a target for the Phase 2.4 anchoring measurement and the gate's
  resampling instrument; one-draw gates cannot size it.
- **vLLM PM non-JSON recurs** (1 draw per convene across 3 of 4 gate
  runs). The recovery draw keeps the run alive; if it grows, a tighter PM
  JSON-schema system prompt is a Phase 2/5 candidate — currently a known,
  absorbed defect at rate ~1/10 draws.
- **DeepInfra kill_criterion over-bound persists** (240-char bound; 1–3
  draws per convene) — field-length discipline item for GLM personas.
