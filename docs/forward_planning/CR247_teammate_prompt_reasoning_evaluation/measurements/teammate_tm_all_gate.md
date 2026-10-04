# Teammate tm-all wholesale gate — measurement

**CR247 · D32/D32a · 2026-10-04 · AT:K3**

*Status: RUNS IN FLIGHT — this doc is the skeleton; results sections are
filled when the batches land. Do not cite verdict numbers until the
"Results" section is complete.*

## What is being measured

The teammate_suite installed WHOLESALE (global constitution + all twelve
personas as whole-persona overrides, risk officers split into three resolved
postures — variant `tm-all`, commit e3b6d398) against the D26 standard gate
(AAPL + V, R3, repeats=1), diffed against the Phase-5 baseline gate
(`out/gate-5/*/runs_room-gate-v1.jsonl`, commit af8dbd86 era).

This measures what wholesale adoption would do to the Room contract:
STANCE envelope survival under all-JSON output demands, sizing behavior
under the TIER ontology vs computed mandate caps, horizon behavior under
the hardcoded 180–730d mandate vs the user's R3 mandate, and verdict
drift. Measurement is not adoption (D32); refused elements (SCS floats,
TIER sizing, hardcoded horizon) are deliberately left in the variant so
the gate sees the teammate's design as written.

## Serving identity (D20)

- vLLM path: `http://100.79.86.15:8000` (ami-host, Tailscale)
- ami-llm root: `/models/qwen38-flash-next-abliterated-nvfp4`
- **Identical to the Phase-5 baseline gate's serving model** — diff
  comparability holds.
- Harness floor: 5000 tokens (HARNESS_MAX_TOKENS_FLOOR).
- Network: Mac off the 192.168.20 LAN; melehost reached via Tailscale
  100.110.14.31 (pg tunnel 5434); full working config in D32a.

## Runs

| Arm | Batch | Provider/Model | Concurrency | Out |
|---|---|---|---|---|
| tm-all gate | cr247-tm-all-gate | vllm / ami-llm (root above) | 1 | out/gate-tm-all/vllm/ |
| Qwen3.8-Flash resume | cr247-approved14-qwen38flash | deepinfra / Qwen/Qwen3.8-Flash | 1 | out/cr247-approved14-qwen38flash/ |
| tm-all gate | cr247-tm-all-gate | deepinfra / GLM-5.3-Flash (registered default) | 2 | out/gate-tm-all/deepinfra/ |

Startup verified: `prompt_variant=tm-all` installed in-process; gateway
forced as expected; 5K floor active.

Ambient caveat (D32a): 1B XBRL tags (SBC/ROIC) are absent for non-AAPL
tickers until the one-time Alpha `ingest_edgar_facts.py --force` (D28
open item). These absents are ambient, not variant effects.

## Results

### Gate reports (truncation / STANCE envelope / PM JSON)

*pending — filled from scoring.gate_report output at run completion*

### Verdict diff vs Phase-5 baseline (scoring.diff_batches)

*pending*

| Ticker | Baseline verdict (vLLM) | tm-all verdict (vLLM) | Baseline (DeepInfra) | tm-all (DeepInfra) |
|---|---|---|---|---|
| AAPL | APPROVE 2.2% | ? | ? | ? |
| V | ? | ? | ? | ? |

### Contract-breakage findings

*pending — e.g. SCS floats in envelopes, TIER_0–3 language vs computed
sizes, hardcoded-horizon overrides, JSON-instead-of-STANCE failures*

## Decision inputs

*pending — GO/NO-GO per element, referencing D2/D8/D15/D17 verdicts and
whether the measurement confirms or overturns each refusal*
