# CR247 — SPEC: Room reasoning-quality improvements

Execution spec for the builder. Organized around four questions (discussion
log D3): (1) are agents fed the right information, (2) what information is
missing, (3) are agent-to-agent scores consistent, (4) do agents know what to
do with the data. External prompt suggestions received during preparation
were inputs to this analysis, not decisions; every item below is justified
against this codebase's own measurements.

Standing rules for every item:

- Behaviour changes ship behind a before/after measurement on a real ticker
  sample, pre-registered metric, noise-floor arm where the CR197 replay
  pattern applies (`backend/scripts/pm_debate_ablation.py`).
- Measurements run on the current serving model
  (`qwen3.8-flash-next-abliterated`). CR197's numbers were measured on
  Qwen3.6-35B and do not transfer; its methods do.
- New sheet fields carry `field_state` provenance, a persona sentence naming
  the field, and updates to the two anti-fabrication guards
  (`backend/tests/unit/test_agent_prompts.py:61`,
  `backend/tests/unit/test_cr219_availability_guard.py:528-537`).
- New env flags are forwarded in `docker-compose.yml`
  (`test_config_compose_parity.py`).
- LLMs never compute figures. Ratios and aggregates are computed in code and
  rendered as labelled lines (measured failure class DEF066→DEF241).
- Data-pipeline items are separate CRs (IDs minted by the Architect); CR247
  covers the prompt/decision-layer work and the measurements.

---

## Phase 0 — Baselines (no behaviour change)

**Status: CLOSED 2026-09-28 (Saiful, D25).** The 0.1 census and 0.3
conviction audit were waived as not necessary at the moment; their tooling
is built and verified in `docs/tools/room_investigation_V2/`
(`audit_db.fetch_verdict_outcomes`, `scoring.outcome_quality`,
`scoring.conviction_audit`) and can run on demand when a later phase needs
the numbers — note Phase 4's shape decision (veto vs resurrection, D12) is
therefore still formally open until the census runs. In place of the full
0.2 replay, the harness itself was proven live: AAPL on vLLM (PASS 1/5)
and AAPL+V concurrent on DeepInfra GLM-5.3-Flash (AAPL PASS 0/4 —
cross-provider agreement — V APPROVE 3/5). Findings logged in D25:
cheap-tier 1400-token truncation (→ harness floor now 5000), PM JSON-schema
miss absorbed by the retry path, 32-char headline-cap overruns, `[AMI
checked]` false positives, DeepInfra 429s under the PM fan-out,
`kill_criterion` over-bound on GLM.

Purpose: every later item is sized and judged against these numbers.

| # | Item | Method | Output |
|---|---|---|---|
| 0.1 | Outcome census | Query `verdict_outcomes` via `backend/scripts/score_verdict_outcomes.py`: false-APPROVE rate (approved, then stopped out / underperformed) vs false-PASS rate (passed, then rallied past the would-be target), per horizon bucket | Decides Phase 4 shape (D12) |
| 0.2 | Current-model Room baseline | Replay a convene corpus on `qwen3.8-flash-next-abliterated` per CR197's arm design: approval rate, stance distribution, envelope parse rate, truncation rate | Baseline for Phases 2–4 |
| 0.3 | Conviction-signal audit | From journaled envelopes: declared conviction × agent × outcome. Does conviction predict anything per role? | Sizes item 2.2 (relabel vs redefine) |

Acceptance: `measurements/phase0.md` in this folder with the three result sets.
*(Superseded by the D25 closure above — no phase0.md was produced; the
census/audit tooling stands by for any phase that needs its numbers.)*

---

## Phase 1 — Information supply (Q1, Q2)

### 1A. Enable already-fetched fields

These flags ARE CR221's open sourcing decisions (its census: 49 asks, 36
open, 35 with verified free sources) — this phase executes them, it does not
rediscover them. CR221's ruled-out items (company guidance, Level 2 depth,
dark-pool prints, sentiment history) stay ruled out.

The fields below are fetched, rendered, and tested today, each behind a
`False`-default flag in `backend/app/core/config.py`. Enabling one adds its
line to the fact sheet.

| Field | Flag | Consumer agents |
|---|---|---|
| Working-capital bridge (OCF→FCF walk, receivables/inventory/payables) | `room_cashflow_bridge_enabled` | Fundamentals Analyst |
| Debt maturity schedule | `room_debt_maturity_enabled` | Fundamentals, Bear |
| Cost of debt | `room_cost_of_debt_enabled` | Fundamentals, Bear |
| FCF history + FCF conversion | `room_fcf_history_enabled`, `room_fcf_conversion_enabled` | Fundamentals |
| ROE history | `room_roe_history_enabled` | Fundamentals |
| Debt split (industrial vs captive finance) | `room_debt_split_enabled` | Fundamentals |

Per flag, in order: enable in config; add the persona sentence naming the
field's sheet label; update the two guards; measure a before/after convene
sample (target metrics: citation accuracy on the new field, GAPS-telemetry
want-list movement, no truncation regression per `_AGENT_MAX_TOKENS`);
commit with the flag forwarded in `docker-compose.yml`.

### 1B. New computed fields (separate CRs)

| Field | Source | Change |
|---|---|---|
| SBC and SBC-adjusted FCF | EDGAR XBRL `ShareBasedCompensation` (endpoint verified 2026-09-28: AAPL returns 180 rows) | Add tag to `edgar_tags.py`, ingest, one computed line: TTM FCF, TTM SBC, FCF minus SBC, all labelled AMI-computed |
| ROIC | XBRL tags already resolved (operating income, tax, debt, equity) | Computed line with a stated tax-rate assumption and a WACC-comparison note labelled as an estimate |
| Put/call ratio | Existing `option_chain.py` fetch | Aggregated put/call volume and open-interest ratio, rendered in the Flow & Positioning lane |

### 1C. Peer comparison (separate CR)

SEC submissions JSON provides SIC code per company (verified 2026-09-28:
`data.sec.gov/submissions/CIK*.json` returns `sic`, `sicDescription`).
Build: peer-basket table (same 4-digit SIC, market-cap neighbours from data
already fetched, refreshed weekly), then one computed line: median trailing
P/E, EV/EBITDA, and net margin across the basket, with basket size stated.
On the same ship, remove the two "no peer comparison" disclaimers in
`content/agents/fundamentals_analyst.md` — only for the state where the line
is live.

### 1D. Forensic metadata flags (deterministic extraction; D16)

Computed in code, rendered as sheet lines in the News/Macro lane.

| Flag | Source | Change |
|---|---|---|
| Insider open-market buy/sell ratio (90d, transaction codes P/S only; M and F excluded) | `edgar_ownership.py` (CR244 dependency) | One computed line |
| 10b5-1 plan tag on insider sales | CR244 extraction layer | Already specified in CR244; consumed here as a sheet label |
| Cluster-buy flag (≥3 distinct insiders, code P, 14-day window) | Same source | Boolean line with the count and window dates |
| 8-K timing/item flags: filed Friday ≥16:00 ET; Item 4.01 (auditor change); Item 4.02 (non-reliance on prior financials) | `edgar_filings_feed.py` already fetches form type + filed date | Computed flags; Item 4.02 also extends the safety floor to hard-block BUY with the reason narrated (never a silent refusal) |

Deferred: Loughran-McDonald uncertainty/litigious scoring, Gunning Fog on
MD&A, YoY Risk-Factors word-count/similarity — all require filing text beyond
the one channel that exists today. **Correction (D22):** filing-text
ingestion is NOT greenfield — `edgar_8k.py` (CR221 I1) already fetches,
parses, hidden-text-filters, and sanitizes the 8-K Item 5.02 section in
production. The deferred CR is an *extension* of that proven machinery to
more item types (4.01, 4.02) and document sections (10-K/10-Q MD&A, Risk
Factors), with the standing requirement that all extracted text routes
through `prompt_safety.sanitize_for_prompt` (DEF370). GAAP/non-GAAP spread:
refused (no reliable free source for non-GAAP figures).

### 1E. Not sourced (recorded so they are not re-proposed)

Earnings-call transcripts (no free API), retail-flow data (proprietary).
The teammate's LLM-reads-the-filing linguistics approach: refused — measured
instruction compliance (~30%, CR038) and run-to-run variance make the model
the wrong instrument for detection; detection is code's job (1D), synthesis
is the model's job.

---

## Phase 2 — Score consistency and horizon discipline (Q3, critique 1)

| # | Item | Change | Measurement |
|---|---|---|---|
| 2.1 | Scoreboard SIZE column | Render the parsed `argued_size_pct` (already journaled, CR197) as a column in `_room_scoreboard` (`room_prompts.py:3592`) | PM approved sizes vs declared debator sizes; approval-rate delta vs Phase 0.2 |
| 2.2 | Conviction semantics | One word, three role-specific definitions today (D4). Relabel the scoreboard column per role family — "evidence strength" (Aggressive), "threat specificity" (Conservative), "evidence clarity" (Neutral) — or adopt one shared definition, per Phase 0.3's finding | PM narration references; verdict stability under resampling |
| 2.3 | Horizon weighting | Add one mandate-derived line to the Trader, debator, and PM room blocks: when `mandate.horizon` is LONG/VERY_LONG, short-term technical readings inform entry timing only and cannot validate or invalidate the thesis. The analyst overlays already branch on horizon/path; this closes the downstream half | Ablation on long-horizon mandates: `horizon_days` distribution, technicals-vs-fundamentals citation mix in PM narrations |
| 2.4 | Bull/Bear anchoring test (D19) | Step 1 is measurement only: CR219 R58 already randomises Bull/Bear order per run_id, so the existing corpus is a natural experiment — compare second-speaker citation overlap and stance Bull-first vs Bear-first. Step 2 (only if anchoring is measured): blind parallel core theses + sequential cross-rebuttals, RM adjudicates four documents; requires a deliberate CR077-guard extension and +2 LLM calls per convene | Step 1: overlap/stance deltas by order. Step 2: before/after on the same corpus, RM adjudication quality |

Explicitly refused: 0–100 numeric conviction scores (unverifiable precision;
the system quantizes on purpose, `room_prompts.py:742-744`), fixed sizing
tiers (sizing is per-mandate and code-computed), a hardcoded 180–730-day
horizon (horizon is per-user), all-JSON agent turns (the prose is the
product surface; CR106 B2), prompts that self-modify in production à la
DSPy, and temperature/persona rotation across parallel CIO runs (variance
without information; differentiate review lenses, not sampling, D19).

## Phase 3 — Interpretation guidance (Q4)

Reasoning frames adopted into `content/agents/fundamentals_analyst.md`, each
sentence naming a sheet field that is live when the sentence ships:

- SBC treated as a cash cost (consumes 1B SBC line)
- Accrual check: net income rising while operating cash flow is flat or
  falling (consumes 1A cashflow bridge)
- EV-based multiples primary over P/E when debt is material (consumes
  existing EV/EBITDA and net-debt lines)
- Low multiple as a decline signal, not a buy signal, unless a catalyst is
  named from sheet data
- Debt maturities within the thesis horizon (consumes 1A debt maturity)
- Moat classification (network effects / switching costs / intangibles /
  cost advantage) as the framework for judging margin durability

The same vocabulary is echoed in the Bull (re-rating catalyst over the
mandate horizon), Bear (terminal vulnerabilities), Research Manager, and CIO
personas so producer and consumer use one glossary. Deficit reporting stays
in the shipped GAPS tail (CR219 R53); no second channel.

Constraint: thresholds appear as guidance, never as rules; computed ratios
come from code (standing rule above); every addition respects
`_LENGTH_GUIDE` and `_AGENT_MAX_TOKENS` pairing (DEF125/DEF236).

## Phase 4 — Second-pass verdict review (D11–D13)

Shape fixed by Phase 0.1:

- **Veto review (on APPROVE):** one additional LLM call instructed to fail
  the approval if the Bear's or Conservative's specific, numbered objections
  were not addressed with numbers in the CIO's narration. Combination is
  code: final = APPROVE only if both passes approve. Flips are narrated and
  journaled with the original verdict preserved.
- **Resurrection review (on PASS):** one LLM call instructed to show the
  PASS rested on evidence the mandate makes inadmissible (e.g., short-term
  technicals under a long horizon). It cannot approve — a PASS carries no
  size/entry/stop — it returns *reconsider*, and the CIO re-runs once with
  the audit note appended.
- Routing, combination, and the veto are deterministic code; only the
  reviews are LLM calls (D13).
- The review pass runs on a **different model than the CIO** (gateway
  fallback provider, already wired) — tests whether CIO errors are
  model-correlated at one extra call on ~16% of convenes (D18).
- Metrics: approval-rate stability (resampling instrument from 0.2) and
  verdict quality vs outcomes (outcome ledger, baselined in 0.1).
- Parked: 5× same-model ensemble; 5-provider tribunal (D18: privacy egress,
  latency, verdict-aggregation problem, alignment-variance contamination).
  Revisit only if the measured error budget after Phase 4 justifies the cost.

Pre-experiment, independent of Phase 4 (D18): Bull and Bear on different
models for a sample of convenes. If the CR197 stance constants de-correlate,
model bias is load-bearing and tier-policy multi-provider routing earns
investment; if not, the constants are prompt-shaped and the model mix
question is closed.

## Phase 5 — Remaining personas

Rewrite evaluation per agent, in this order: Fundamentals, Bear, Bull,
Research Manager, CIO, Trader, debators, remaining analysts. Standard per
persona: every ask maps to a live sheet field; Room and 1-on-1 surfaces both
hold; length guide and token budget move together; measured before ship.

## Phase 6 — Standing prompt-evolution loop (D20)

A periodic prompt-performance digest, run on a schedule: per-agent envelope
parse rates, truncation vs `_AGENT_MAX_TOKENS`, GAPS want-list movement,
stance/conviction distributions, citation accuracy, and verdict outcomes,
aggregated against baselines **keyed to serving-model identity** (never the
`ami-llm` alias). The digest flags anomalies and drafts candidate prompt
changes as CRs with pre-registered measurement plans. Build on
`weekly_room_retro.py` / `score_verdict_outcomes.py` (CR157's loop); do not
build a second pipeline. The machine measures and proposes; governance
disposes; nothing auto-ships. Cadence flags weekly, concludes monthly or
per-N-convenes (statistical power constraint, CR197).

## Cross-CR dependencies and prior art (D23)

- **CR240 owns the production-provider decision** — D21's provider review is
  folded into it; this CR does not pick production providers.
- **CR130**: Kimi Coding Plan is already integrated (`LLM_FORCE_PROVIDER`,
  `kimi_max_tokens_floor`); the Open Platform vs Coding Plan key/host
  distinction is a documented trap.
- **CR217**: the GLM head-to-head harness exists — use it for the D18
  split-model experiment.
- **CR221**: Phase 1A executes its sourcing decisions; its ruled-out items
  stay ruled out.
- **CR211**: reasoning-model token floor — persona-length changes in Phase
  3/5 must respect reasoning-token headroom.
- **CR242/CR243**: persona rewrites interact with AR/MS prompt reliability.

---

## Dependency order

```
Phase 0 (baselines)
   ├─► Phase 1A/1B/1D (fields) ─► Phase 3 (guidance consuming those fields)
   ├─► Phase 1C (peers — independent)
   ├─► Phase 2 (independent of 1)
   └─► Phase 4 (shape fixed by 0.1)
Phase 5 last, informed by all prior measurements.
```
