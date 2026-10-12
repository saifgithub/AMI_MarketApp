# CR256 — Evidence-gated verdicts (spec for review)

**Status:** proposed, awaiting review · **Spec:** AT:K3 · **Supersedes:** nothing;
consumes CR253 (disposition fold-in pending), CR255 (target curve + program frame)

---

## 0. Purpose and background — the week this CR comes from

**Where this started.** CR247 (2026-09) asked a quality question about the
Room: 12 agents, 6 stages — are the prompts feeding the LLMs right, and do the
agents' decisions hold together? The investigation that followed converged on
a product question Saiful posed for the risk-knob feature (CR228/CR251): *with
5 risk appetites and 30 benchmark tickers, approval rate should rise
monotonically from R1 to R5 — does it?* The frozen heuristics-off baseline
(Oct-07, ami-llm, 300 rooms) answered: **no** — approvals went
0/3/4/24/26, a switch between R3 and R4, not a slope; and Jev-scored evidence
showed **zero discrimination**: APPROVE rooms were no better-supported than
PASS rooms at every level. The risk knob moved sizes, not judgment.

**What the week established** (each step measured, all artifacts committed;
`docs/tools/room_investigation_V2/EXPERIMENT_LOG.md` is the canonical map):

1. **The stack shipped** (Oct-08/09: CR249 trader-geometry repair, CR252 CFA
   evaluation parameters folded into all 12 personas, CR253 data lanes, D28
   EDGAR ingest) and was re-measured as a full 300-room matrix on dsv4
   (ami-host had died — the first of three deaths; dsv4 on alpha-spark was the
   bridge). The new stack made dsv4 more willing but **inverted at R5**
   (5/11/22/27/17) — approving less at max aggression than at R4.
2. **The R5 inversion was dissected to a mechanism**: commitment size raises
   the evidence bar (pinning size to 1% removed the inversion; per-name size
   thresholds measured — DHR/MO approve ≤3%, refuse ≥4%). "Size ≠ worthiness"
   (CR253's thesis) got its quantitative proof.
3. **Every prompt-level fix was tried and measured dead.** Disposition table:
   fixed curve *shape* (first monotone curve, 1/7/13/15/19) but not
   discrimination or stability. Sub-cap conditional: inert — sizing below cap
   happens spontaneously (~13%) and narration cannot carry control ("cut
   2.0% to 3.5%"). tm-all suite: re-confirmed NO-GO at n=300 with the worst
   flip rate (27%). The rule the whole week converged on: **personas move
   priors; structure moves evidence and stability.**
4. **The disease was proven cross-model.** When the DGX returned, the clean
   ami-llm control arm showed the same failure (r=+0.03, Δ negative, lift 0)
   with a conservative-but-monotone curve (0/0/4/10/20). No model swap fixes
   this — it is structural.
5. **The target was set.** Saiful locked the policy the bar must implement:
   R1–R5 = 5/15/30/45/60 approvals per 60 rooms
   (`CR255_decision_consistency/target_curve.md`).

**Why this CR is the conclusion.** The week's experiments bracket the design
space: prose interventions are measured exhaustively (points 3–4), and the
single-metric evidence bar was tried and died of score-ties. What remains —
and all that remains — is to make evidence a computed, structured input to a
gated verdict. That is Layer 1–3 below. The acceptance criteria in §4 are the
program's original question restated as testable gates: monotone curve that
tracks the target, decisions that track evidence, holdouts that stay out.

---

## 1. Problem statement (measured — do not re-litigate without new data)

The Room's final verdict does not read the evidence the debate produces.
Measured on 1,350+ rooms across six arms (see `docs/tools/room_investigation_V2/
EXPERIMENT_LOG.md`; analysis `docs/forward_planning/CR251_risk_monotonicity_matrix/
analysis_r3.md`–`analysis_r6.md`):

| Symptom | dsv4 production | ami-llm clean | dsv4 disposition | tm-all |
|---|---|---|---|---|
| APPROVE vs PASS evidence Δ | −0.06…−0.13 | −0.05 / −0.11 | −0.03…−0.13 | −0.05…−0.13 |
| Net-support r (direction-corrected) | +0.19 | +0.03 | — | +0.07 |
| Threshold lift over always-PASS | 0 pts | 0 pts | +0–2 pts | +1 pt |
| Verdict flips (2 reps) | 17% | 14% | 21% | 27% |

**Failure mode A — attention:** the PM's verdict anti-tracks or ignores the
realized evidence score. Decomposition (analysis behind the numbers): part
late-desk prose artifact (trader r=−0.44, verdict-aware), part rational bear
weighting, part direction-agnostic metric conflation — but the
direction-corrected residual is still ~zero, so the PM is not conditioning on
evidence quality.

**Failure mode B — instability:** the evidence itself re-rolls every run.
12/26 flip-pairs flip their stated reason; researcher order logging shows
`seeded=False` in harness runs; free-form claim selection means each run
surfaces a different subset of the available evidence.

**Measured dead-ends (why this CR exists):** prompt prose moves the prior
(willingness/curve shape) and nothing else — disposition table (monotone curve,
discrimination unchanged), sub-cap conditional (inert; sizing is spontaneous at
~13% in every arm), tm-all suite (27% flips, r=+0.07, NO-GO re-confirmed at
n=300). **No persona-level mechanism remains untried; the fix must be
structural.**

## 2. Design

### Layer 1 — Claim cards: evidence as census, not sample

Every desk (4 analysts + bull + bear + RM) must file a **CLAIMS** block as part
of its existing stance envelope: one card per CFA evaluation-parameter item
(the CR252-folded checklist already defines the items), each card:

```
{ item: <checklist id>, direction: support|oppose|neutral,
  claim: <one sentence>, key_numbers: [...], data_present: yes|no,
  support_grade: well|partial|unsupported }
```

- `support_grade` is the desk's self-assessment against the Jev rubric
  (docs/tools/room_investigation_V2/tools/jev_score_runs.py writes that rubric;
  reuse its wording verbatim so self-grades and Jev-audit grades share a scale).
- `data_present: no` is a first-class signal — it distinguishes "checked,
  data absent" from "didn't check" (today both read as silence; this is the
  census property).
- Bear/debators additionally file **OBJECTIONS**: `{ objection, target_claim,
  severity }`. The PM's rebuttal must reference `objection.id` as resolved or
  leave it unresolved — the unresolved count is computed, not narrated.

Parsing reuses the CR143-tolerant parser family — the stance-envelope parser
(`parse_stance_envelope`, `backend/app/services/room_runner.py:4436`) is the
template; the card parser lives beside it with the same degrade-loudly
semantics (unparseable card → desk marked `card_malformed`, surfaced in the
run record, never silently dropped).

**What this kills:** failure mode B at the source — the evidence set becomes
the full checklist census, identical in structure every run.

### Layer 2 — Composite evidence score (code-computed)

`evidence_score(room) = w1·net_support + w2·(−unresolved_objections) +
w3·catalyst_proximity + w4·factor_coverage`, where:

- `net_support` = mean(support_grade of bull-side cards, Jev-audit corrected)
  − mean(bear-side cards) — the metric `tools/net_support.py` computes today,
  upgraded from turn-prose grades to card grades (fixes the resolution/tie
  problem: the single-metric bar died because ~40/60 rooms tied at net=+0.33;
  card-level grades + objection counts + coverage add the missing dimensions).
- `catalyst_proximity` = days to nearest filed catalyst (from claim cards'
  key_numbers; already in the data the desks cite).
- `factor_coverage` = fraction of checklist items with data_present=yes.
- Weights `w*` are fit, not hand-set (§4).

Self-grades are the runtime signal; **Jev audits a stratified sample per run**
(2 cards/desk) and systematic divergence between self-grade and Jev-grade
triggers a calibration review — this keeps the external judge in the loop
without the cost/scaling limits of scoring every turn (the 402-outage lesson).

### Layer 3 — The bar: per-level thresholds on the verdict action

Thresholds `T(level)` on evidence_score, fit so the calibration arm's curve
matches the **locked target** (`docs/forward_planning/CR255_decision_consistency/
target_curve.md`: R1=5/15/30/45/60 of 60). Fit procedure: per level, sort rooms
by evidence_score, T = the score at the target quantile, subject to the
holdout rules below. Fit ONCE per model on the calibration arm, frozen
thereafter, versioned with the prompts.

Enforcement semantics (DEF059-compatible — the gate steers, never silently
vetoes):

- `evidence_score ≥ T(level)` → PM may APPROVE; full-size or structurally
  sub-cap (below).
- `evidence_score < T(level)` → PM's available actions are PASS (or
  sub-cap APPROVE if within the sub-cap band); the verdict record carries
  `bar_blocked: true` and the computed score. The LLM narrates; the action
  set is code.
- **Holdout rules override thresholds both ways:** thesis-broken shapes
  (RIOT-pattern: high grounding, negative thesis) are barred at every level;
  grounded-bear cases (APD-pattern: negative SBC-adjusted FCF) pass at every
  level regardless of score. These are the two named patterns from
  analysis_r3; encoded as data checks, not vibes.

Sub-cap sizing (structural, replaces the dead prose route): on APPROVE,
`size = cap(level) · f(evidence_score, ATR)` — a monotone map from score to
size within the mandate cap (CR129 `single_name_cap_pct`,
`backend/app/schemas/mandate.py`; the map's parameters ship in the same fit).
The PM receives the computed size as context and narrates around it; it cannot
argue a different number past `check_mandate_compliance`
(`backend/app/agents/safety_floor.py:175`), which already runs.

### Determinism hardening (prerequisite)

- `_researchers_order(run_id)` (`backend/app/services/room_runner.py:249`,
  CR219 R58) is deterministic by run_id; **harness runs must stop disabling it**
  (log line `seeded=False` — find and remove the harness-side switch,
  `docs/tools/room_investigation_V2/library/runner.py`).
- Analyst temperature pinning per provider via
  `force_provider()` (`docs/tools/room_investigation_V2/library/provider_gateway.py:96`)
  — `supports_temperature` exists in the ProviderSpec; pin analysts to 0.2.

## 3. Code touchpoints (anchors as of bf0fa99f)

| Area | Location | Change |
|---|---|---|
| Verdict schema | `backend/app/schemas/room.py:123` class `Verdict` | + `decision_record` object (per `CR255_decision_consistency/decision_record_spec.md`), + `evidence_score`, `bar_blocked`, `sub_cap` fields |
| PM verdict parse | `backend/app/services/room_runner.py:3133` `_parse_pm_verdict` | parse cards; apply gate; stamp `bar_blocked` |
| Stance envelope | `backend/app/services/room_prompts.py:1018`, parser `room_runner.py:4436` | envelope extended with CLAIMS/OBJECTIONS blocks; same tolerant-parse contract |
| Evidence computation | NEW `backend/app/services/evidence_record.py` | card aggregation, composite score, holdout checks — pure functions, unit-tested |
| Gate application | `room_runner.py` verdict assembly (near `_parse_pm_verdict`) | action-set restriction per §2 Layer 3 |
| Trader geometry repair | `backend/app/services/room_runner.py:8387` `_attempt_trader_geometry_repair` | unchanged; sub-cap size feeds the same plausibility path |
| Safety floor | `backend/app/agents/safety_floor.py:175` `check_mandate_compliance` | unchanged; the existing backstop the gate sits above |
| Mandate caps | `backend/app/schemas/mandate.py` (CR129 fields), `brief_engine.py:578` `hydrate_brief_mandate` | unchanged |
| Review toggles | `room_runner.py:5548` | matrix containers keep `ROOM_*_REVIEW_ENABLED=false` (methodology) |
| Harness variant | `docs/tools/room_investigation_V2/benchmarks/cr256-evbar-*/`, prompt overrides via `library/prompt_lab.py:104` | measurement venue; production personas untouched |
| Fit/validation tooling | extend `tools/net_support.py`, `tools/decision_factors.py`; NEW `tools/evidence_bar.py` (fit + apply + report) | thresholds fit per model, committed under the CR folder |
| External judge | `tools/jev_score_runs.py` (systemone) | stratified audit mode; billing is a metered dependency (402 incident) |

## 4. Acceptance criteria (all four, fresh 30×5, per model)

1. Curve within tolerance of target (each level ±8 approvals).
2. Verdict flips < 10%.
3. Holdouts out at every level (RIOT/APD-shaped names 0 approvals).
4. Discrimination Δ positive at every level (APPROVE rooms score higher).

Validated first **retroactively on the 1,350 existing scored rooms** (cards
can be re-derived from the logged turns for a feasibility pass) before any new
run is spent. Then: fresh 30×5 on dsv4 → on ami-llm → production fold-in CR
(with the CR253 disposition table, which this gate subsumes at the action
level).

## 5. Boundaries

- DEF059 holds: the gate restricts the action set; the PM's narration is never
  rewritten post-hoc.
- No `content/agents/*.md` production change until measured GO; all
  experimentation in harness variant benchmarks.
- Per-model thresholds; never fit on one model and applied to another.
- `BASELINE.md` / `analysis_r1/r2` remain frozen references.
- llm_audit immutability: the evidence record is additive; no historical rows
  change.

## 6. Open questions for the reviewer

1. **Card grade trust:** self-graded support with Jev audit-sampling assumes
   desks grade themselves honestly. The review session (CR255 jev_review)
   partially covers the judge side; do we also need a self-grade bias
   measurement before fitting weights?
2. **Gate bypass surface:** an LLM that knows the gate can phrase narration to
   game `data_present` flags. Is the card schema's `key_numbers` requirement
   (must cite the datum) a sufficient structural defense, or do we need
   arithmetic verification of cited numbers against the data payload?
3. **Fit stability:** quantile-fit thresholds on n=60/level are themselves
   noisy (the R4/R5 10-room gaps in our own arms). Do we accept n=60 fit, or
   require the calibration arm at n=3 reps (90/level) for the fit run?
4. **Sub-cap map shape:** linear vs step function from score to size — any
   product preference (user-facing copy implications)?
