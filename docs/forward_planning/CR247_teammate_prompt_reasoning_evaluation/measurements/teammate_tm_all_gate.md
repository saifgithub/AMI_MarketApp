# Teammate tm-all wholesale gate — measurement

**CR247 · D32/D32a · 2026-10-04 · AT:K3**

*Status: RUNS COMPLETE (vLLM 2026-10-04, DeepInfra 2026-10-06). Verdict
numbers below are final for this gate.*

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

DeepInfra arm (run 2026-10-06 07:38-09:31 UTC, GLM-5.3-Flash, conc 2):

- AAPL tm-all: **gate FAIL (1 finding)** — PM_JSON_UNPARSEABLE, PM
  self-consistency draw 4 of 5: no parseable JSON object with an 'action'
  key. CR143's tolerant parser could not recover it. 1 of 10 PM draws
  across both GLM arms. Envelope and truncation otherwise clean.
- V tm-all: **gate OK**

### Verdict diff vs Phase-5 baseline (scoring.diff_batches)

| Ticker | Base (vLLM) | tm-all (vLLM) | Base (GLM) | tm-all (GLM) |
|---|---|---|---|---|
| AAPL | APPROVE 2.2%, h90 | **PASS** | PASS | PASS (gate FAIL: PM draw 4 unparseable) |
| V | APPROVE 2.5%, h90 | APPROVE 2.0%, **h180** | PASS | PASS |

n=1 per arm (the D26 unit). The AAPL flip exists only on vLLM; GLM is
insensitive (its baseline is already PASS — GLM's conservatism swamps
persona-level drift at n=1). The vLLM stance chain below remains the
corroborating evidence for the flip.

### DeepInfra-arm contract behavior

- **Trader structural-stop failure reproduces cross-provider.** AAPL
  tm-all GLM emitted **stop=50.0 vs close 332.89**
  (`room_geometry_implausible_level`, stop/close ratio beyond 5.0) and
  aggressive_debator implied **R:R 0.3:1** — the same 0.3 tension as the
  vLLM AAPL flip. On vLLM the wide stop killed the trade by arithmetic;
  on GLM it produced geometric nonsense. The teammate Trader's stop
  logic is the dominant failure mode of the suite on both models.
- **PM verbosity:** `room_pm_kill_criterion_over_bound` (240-char bound)
  fired on every PM draw, both GLM arms. Warning-level, not a gate
  failure — the tm-all PM persona writes longer kill criteria than the
  production PM.
- **Verdict reviews exercised live:** VLLM_BASE_URL was set for this run,
  so veto/resurrection reviews ran on ami-llm (previously 401-routed to
  kimi on this Mac). JPM veto review upheld (2 reasons), T upheld,
  WU resurrection review upheld (3 reasons), AAPL/V tm-all resurrection
  upheld. Fail-safe path works end-to-end when vLLM is reachable.
- **Production-prompt noise on GLM:** WU arm logged
  `room_stance_envelope_displaced` (GLM chatter before the STANCE line;
  envelope recovered downstream), and T's neutral_debator hit the
  scripted-fallback path (`room_partial_outage`, scripted=1 < threshold
  4, room still completed). Both production-suite, not tm-all.

### Three-way same-family model matrix (approved-14, R5, production prompts)

| Model | Provider | APPROVE |
|---|---|---|
| qwen38-flash-next-abliterated-nvfp4 | vLLM (ami-host) | **14/14** |
| zai-org/GLM-5.3-Flash | DeepInfra | 4/11 on this subset (4/26 on the 30-ticker universe) |
| Qwen/Qwen3.8-Flash (hosted) | DeepInfra | **6/14** — DHR, JPM, PLD, SLB, T, V |

Hosted Qwen3.8-Flash sits between the two: stricter than the local
abliterated serve, looser than GLM. JPM completed APPROVE 2/3 after PM
draw losses + upheld veto review (its first attempt was a 429-storm
NO_VERDICT; record deleted and re-run). BAC — approved by both vLLM and
GLM — flips to PASS on hosted Qwen3.8-Flash; the abstention cluster
(APD, BA, MA, PYPL, RIVN, WU) holds across all three models.

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

Per-element GO/NO-GO for wholesale teammate-suite adoption, measured
cross-provider (vLLM ami-llm + GLM-5.3-Flash). Confirms or overturns the
D2/D8/D15/D17 refusals.

| Element | D-ref | Measurement | Verdict |
|---|---|---|---|
| STANCE envelope vs "strict JSON" demands | D8 | Survived on vLLM (11/11 both arms). Broken 1/10 PM draws on GLM (AAPL draw 4 unparseable → gate FAIL) | **NO-GO as-is** — envelope survives abliterated-serve, not GLM |
| SCS 0-100 floats | D15 | Zero SCS floats in any envelope, both providers | confirmed refusal (harmless dead weight) |
| TIER sizing ontology | D15 | Contaminates arguments on both providers (vLLM 5.0% vs 3.0% cap; GLM R:R 0.3 advocacy); envelope sizing stayed % in all observed cases — contained, not adopted | confirmed refusal |
| Hardcoded 180-730d horizon | D2 | Leaked into trade params on vLLM V (h90→h180). GLM PASS arms carry no params, so unobservable there | confirmed refusal |
| Trader wide-stop / "no tight stops on horizon mandate" | — (new) | Dominant failure mode, BOTH providers: vLLM AAPL −13.3% stop → R:R 0.3:1 → flip to PASS; GLM AAPL stop=$50 (implausible geometry) | **NO-GO** — this instruction alone kills the suite |
| PM kill_criterion verbosity | — (new) | Over 240-char bound on 10/10 GLM draws, 0 gate failures | trim, not blocking |
| CIO/PM output discipline overall | — | vLLM gate clean; GLM 1 PM draw lost | needs per-provider output-contract work before any GLM prod use |

**Bottom line:** wholesale adoption (D17's original question) is measured
NO. The suite's value is the per-agent salvage map already extracted
(D17); the two elements that would change Room behavior if adopted —
hardcoded horizon and TIER sizing — are exactly the two the measurement
shows overriding mandate-driven and computed outputs. The new finding
this gate adds: the teammate Trader's stop placement is a
cross-provider failure and must not be ported in any form. AAPL's flip
is real (stance-chain corroborated) but vLLM-specific at n=1; GLM's
baseline conservatism masks persona drift, so GLM is not a useful drift
detector at gate scale.

Non-blocking harness gaps carried forward: resume-skip gate re-run (one
line), kill_criterion bound sizing vs persona verbosity.

*Measurement is not adoption (D32). Adoption decisions stay with
Saiful.*
