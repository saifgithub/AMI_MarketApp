# CR247 — SPEC: Room reasoning-quality improvements

Execution spec distilled from `discussion_log.md` (D1–D14). The teammate's
prompt suite (`teammate_suite/`) is treated as *suggestions*; this spec is
organized around Saiful's four questions (D3):

1. Are we feeding the LLM the right information?
2. What additional information do we need to supply?
3. Are producer→consumer scores consistent and robust?
4. Does the LLM know what to do with the data?

Plus the decision layer (CIO review). **Every item that changes behaviour
ships behind a measurement** (CR247 scope item 7; CR197/CR228 methodology;
current serving model is `qwen3.8-flash-next-abliterated` — CR197's Qwen3.6
numbers do not transfer, only its methods).

Governance: CR247 is the umbrella for the reasoning-quality evaluation and the
prompt/decision-layer work. New **data pipelines** are separate CRs per the
CR247 non-goals ("flag it, don't fold it in") — they are listed here as
dependencies with their own minted IDs to be requested from the Architect.

---

## Phase 0 — Baselines and the census (no behaviour change)

Pure measurement. Everything downstream is sized by what this finds.

| # | Item | Method | Output |
|---|---|---|---|
| 0.1 | **Outcome census** | SQL + scoring over the verdict-outcome ledger (`verdict_outcomes`, `score_verdict_outcomes.py`): false-APPROVE rate (approved, then lost past stop / underperformed) vs false-PASS rate (passed, then rallied past would-be target), per horizon bucket | Decides veto-review vs resurrection-review vs both (D12/D13) |
| 0.2 | **Current-model Room baseline** | Re-run CR197-style convene corpus on `qwen3.8-flash-next-abliterated` (same tickers/epochs where possible): approval rate, stance distribution, truncation, envelope parse rate | The new baseline every later phase compares against |
| 0.3 | **Conviction-semantics audit** | Tabulate declared conviction × agent × outcome from the ledger/envelopes: does "high conviction" predict anything per role? | Sizes D4 — if conviction carries no signal per role, relabelling is cosmetic and a deeper fix is needed |

Acceptance: three numbers written into the CR247 folder
(`measurements/phase0.md`). No code change ships from this phase.

---

## Phase 1 — Feed the right information (Q1 + Q2)

### 1A. Graduate already-fetched fields (no new source)
Each flag flips independently, each with a before/after convene sample:

| Field | Flag (all default OFF) | Feeds |
|---|---|---|
| Working-capital bridge | `room_cashflow_bridge_enabled` | FA; the teammate's "trapped in working capital" ask becomes legal |
| Debt maturity schedule | `room_debt_maturity_enabled` | FA, Bear (debt-wall heuristic) |
| Cost of debt | `room_cost_of_debt_enabled` | FA, Bear |
| FCF history + conversion | `room_fcf_history_enabled`, `room_fcf_conversion_enabled` | FA (accrual-trap heuristic) |
| ROE history | `room_roe_history_enabled` | FA |
| Debt split (industrial vs captive) | `room_debt_split_enabled` | FA |

Each graduation: persona sentence added naming the field (the CR219 guard
pattern), before/after convene sample measured, GAPS telemetry checked for
the field disappearing from agents' want-lists.

### 1B. New computed fields (small CRs — mint IDs)
| Field | Source (D14, all free) | Notes |
|---|---|---|
| SBC + SBC-adjusted FCF | EDGAR `ShareBasedCompensation` (verified live) | AMI computes; labelled "SBC treated as a cash cost" |
| ROIC (+ WACC stance note) | XBRL tags already resolved | AMI computes; estimation-honesty label on WACC |
| Put/call ratio | Existing `option_chain.py` data | Arithmetic on data in hand; goes to Flow & Positioning's lane |

### 1C. Peer comparison (medium CR — mint ID)
SIC-basket build: SEC submissions JSON SIC + market-cap neighbours (verified
live). New table + refresh job, then a computed "vs N same-SIC peers" line
(median P/E, EV/EBITDA, margins). Removes the persona's two "no peer
comparison" disclaimers **only when the line is live**.

### 1D. Deliberately deferred (documented, not built)
Earnings-call transcripts (no free source), retail-flow (proprietary),
filing full-text pipeline (worth its own CR; largest honest upgrade).

---

## Phase 2 — Consistent scores and horizon discipline (Q3 + critique 1)

| # | Item | What changes | Measurement |
|---|---|---|---|
| 2.1 | **Scoreboard SIZE column** (D5) | Render parsed `argued_size_pct` into `_room_scoreboard` | PM size decisions vs declared sizes; CR197's deferred recommendation, baseline now recorded |
| 2.2 | **Conviction relabel** (D4) | Scoreboard column labelled per role family ("evidence strength" / "threat specificity" / "evidence clarity"), or one shared definition — decided by Phase 0.3 | Before/after: PM narration references to conviction; verdict stability |
| 2.3 | **Horizon-weighting instruction** (critique 1 fix) | Mandate-derived line to Trader + debators + PM: when `horizon` is long, short-term technicals tune entry, never validate the thesis (teammate RULE 1, de-hardcoded). FA/MA/News/Social overlays already branch on horizon/path — this closes the downstream half | Ablation on long-horizon mandates: verdict horizon_days distribution, citation mix (technicals vs fundamentals) in PM narrations |
| 2.4 | SCS 0–100 floats | **Rejected** (D8) — documented in the CR as evaluated-and-refused | — |

## Phase 3 — Teach interpretation (Q4)

Adopt `teammate_suite/01_institutional_heuristics.md` as reasoning frames —
**after** the fields they consume are live (D10 sequencing rule):

1. FA persona: SBC-as-cash-cost, accrual trap (NI vs OCF), EV-over-P/E
   hygiene, value-trap filter, debt wall, moat typology. Each sentence names
   a real sheet field; every ratio AMI-computed.
2. Echo the vocabulary into Bull ("re-rating catalyst over the horizon"),
   Bear ("terminal vulnerabilities"), RM, CIO — the shared glossary is what
   makes producer→consumer reasoning commensurate (Q3 applied to prose).
3. Deficit reporting: keep the shipped GAPS tail as the channel; fold the
   teammate's per-field `DEFICIT` idea into it rather than adding a second
   mechanism.
4. No JSON-everything, no tier sizing, no hardcoded horizon (D2 — refused
   with reasons recorded).

## Phase 4 — Decision layer: the second pass (D11–D13)

Shape decided by Phase 0.1's census:

- **Veto review** (on APPROVE): reviewer LLM, "kill this if Bear/Conservative
  terminal vulnerabilities were dismissed without numbers"; AND-combination
  in code; flips narrated + journaled.
- **Resurrection review** (on PASS): outputs *reconsider* only (a PASS has no
  size/entry/stop); CIO re-runs once with the audit note appended.
- LLMs judge; code routes, combines, vetoes (D13 rule).
- Metrics: approval-rate stability (CR197 resampling instrument) + verdict
  quality vs outcomes (outcome ledger). Both baselined in Phase 0.
- 5× same-model ensemble and 5-different-LLM variants: parked unless Phase 4
  measurements leave a large error budget.

## Phase 5 — Remaining personas

Evaluate/rewrite the other agents' prompts to the Phase-3 standard (each ask
maps to a live field; dual-surface Room + 1-on-1 holds; length-guide/token
budget pairing per DEF125/DEF236). Ordered by measured impact: FA → Bear →
Bull → RM → CIO → Trader → debators → analysts 2–4.

---

## Cross-cutting acceptance

- Every shipped item: before/after measurement on a real ticker sample,
  pre-registered metric, noise-floor arm where the CR197 pattern applies.
- Every new sheet field: `field_state` provenance, persona sentence, and the
  two anti-fabrication guards updated (`test_agent_prompts.py:61`,
  `test_cr219_availability_guard.py:528-537`).
- Every new env flag: forwarded in `docker-compose.yml`
  (`test_config_compose_parity.py`).
- `pytest backend/tests/unit/ -q` green; registers regenerated;
  pathspec-only commits `(AT:K3 CR247)` for this CR's items, new IDs for
  the data-pipeline CRs.

## Dependency order

```
Phase 0 (census + baselines)
   ├─► Phase 1A/1B (fields live) ─► Phase 3 (heuristics that consume them)
   ├─► Phase 1C (peers, independent)
   ├─► Phase 2 (scoreboard/conviction/horizon — independent of 1)
   └─► Phase 4 (shape decided by 0.1)
Phase 5 last, informed by everything measured above.
```
