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

vLLM arm (run 2026-10-04 09:50-10:08 UTC, resumed-skipped then gated
directly via scoring.gate_report — the resume path of room_benchmark does
not re-run the gate on skipped arms; see "Harness gaps"):

- AAPL tm-all: **gate OK** (no truncation, no missing envelope, PM JSON parsed)
- V tm-all: **gate OK**

### Verdict diff vs Phase-5 baseline (scoring.diff_batches)

| Ticker | Baseline (vLLM) | tm-all (vLLM) | Flag |
|---|---|---|---|
| AAPL | APPROVE 2.2%, horizon 90 | **PASS** | **FLIPPED** |
| V | APPROVE 2.5%, horizon 90 | APPROVE 2.0%, **horizon 180** | params shifted |

n=1 per arm (the D26 unit). The AAPL flip is one draw under CR197's ~12%
same-prompt flip noise; the stance-level chain below is the corroborating
evidence, not the verdict bit alone.

### Contract behavior (stance census, AAPL arm)

- **STANCE envelope survived wholesale:** all 11 non-PM agents in both
  arms produced parseable STANCE lines. The personas' "strict JSON" output
  demands did NOT break the envelope — the Room addition block's format
  instructions (appended after the persona) won. No SCS floats in any
  envelope (SCS schema mentions: 0).
- **TIER language is live but contained:** TIER_1 tokens appear in
  conservative/neutral debator responses; SIZE fields still emitted in %
  (envelope held). But tm-all aggressive_debator argued **SIZE 5.0%**
  vs baseline's 3.0% mandate cap — the TIER_2 band top (2.51-5.00%)
  displaced the computed cap in the argument (PM did not take it).
- **Hardcoded horizon leaked into trade params:** tm-all V verdict carries
  `time_horizon_days=180` vs baseline 90 — the constitution's 180-730d
  HORIZON_MANDATE overrode the R3 mandate's horizon in the emitted trade.
  This is the refused-hardcoded-horizon element measurably overriding
  mandate-driven behavior (D2's conflict, observed live).

### Why AAPL flipped (producer→consumer chain)

| Agent | Baseline stance | tm-all stance |
|---|---|---|
| fundamentals_analyst | for / high | for / high (unchanged) |
| market_analyst | for / medium | for / medium (unchanged) |
| bull_researcher | for / medium | for / **high** |
| bear_researcher | against / medium | against / medium (unchanged) |
| research_manager | for / medium | **neutral** / medium |
| trader | **for** / medium | **against / high** ("-1.7% asymmetry to target") |
| aggressive_debator | for / low, 3.0% | for / high, **5.0%** |
| conservative_debator | neutral / low, 1.5% | neutral / medium, 1.5% ("R:R 0.3:1 poor") |
| neutral_debator | for / medium, 2.2% | for / medium, 2.0% |

Mechanism: the tm-all Trader persona ("do not place tight, intraday stops
for a HORIZON_MANDATE trade" + Technical Strategist's structural floor)
placed a wide structural stop ($289.16, -13.3%) against a $345.34 target
(+3.5%) → R:R 0.3:1. The Trader itself turned **against**; the Research
Manager de-escalated to neutral; the PM (0/5 approve votes) passed on the
asymmetry. The flip is **internal to the teammate suite's own design
tension**: horizon-mandated wide stops vs the CIO's conviction-alignment
gate on R:R. It is not a contract failure and not noise in the usual sense
— it is the persona architecture working as written, and its output is a
worse trade decision on the gate's reference ticker (PASS on AAPL at R3
with ROIC 87.4% and 5/5 room agreement on quality).

### Harness gaps found by this run

1. room_benchmark resume-skip does not re-run gate_report on skipped arms
   (gate silently evaluates nothing; worked around by calling
   scoring.gate_report directly). Fix deferred — one line + JSONL reload.
2. audit_db hardcoded `ssh melehost` — fixed: AMI_AUDIT_SSH_HOST env
   override (6096e314); melehost-ts alias over Tailscale.

## Decision inputs

*pending — GO/NO-GO per element, referencing D2/D8/D15/D17 verdicts and
whether the measurement confirms or overturns each refusal. Awaiting the
DeepInfra arm before concluding (GLM behavior under the same variant).*
