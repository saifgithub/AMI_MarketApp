# CR266 — structural decision reliability

**Status:** in_progress · **Owner:** AT:K4 · **Opened:** 2026-10-29

## Purpose

Complete the general application improvements that prompt-only experiments did
not address: typed evidence as the PM's binding decision input, computed action
and size, contested/change presentation, independent outcome reporting and real
acceptance tests. Production rollout is per model and conditional on measured
acceptance; a failed gate remains OFF.

## Workstreams

1. Backend evidence record, context capture, PM gate, configuration and tests.
2. Mobile decision-record models, contested/change cards, localization and tests.
3. Calibration and independent outcome reporting.
4. Integration, V2 acceptance, governance, final verification and Alpha decision.

## Shared contract

`DecisionRecord` carries evidence score, threshold, allowed actions, computed
size, unresolved objection text and IDs, evidence availability/source,
contested flag and `contested_reasons`. The PM vote bar remains 4/4/3/2/2; the
deterministic safety floor remains the final veto. Uncalibrated model identities
and uncomputable evidence fail closed with an explicit reason, never a silent
bypass.

`net_support` is the sum of direction × grade contributions divided by the 20
required cards (four desks × five items); `score = net_support - 0.1 ×
unresolved_objections`. Thus complete support scores 1.0 and each unresolved
objection retains a material 0.1 penalty. Every desk must file exactly one card
per item: missing or duplicate cards fail closed rather than inflating the
score.

Sizing is continuous and monotone from 25% of mandate cap at the evidence
threshold to 100% at score 1.0. Thresholds are keyed by provider **and model**
(for example `vllm:ami-llm`, not the shared `vllm` provider), monotone
descending from R1 to R5, and fitted by the calibration tool rather than
hand-selected.

## Acceptance

The immediate objective is **`ami-llm` Alpha readiness**. Ling is a separate
per-model evaluation and neither blocks nor inherits an `ami-llm` decision; no
Ling configuration is enabled without Ling evidence.

1. Backend and mobile standard suites green; register parity clean. Any
   unrelated pre-existing failure is documented rather than misattributed.
2. R4 card pilot per model reaches ICC ≥0.85 with complete machine channels.
3. Full 30×5 per-model calibration reaches target curve within tolerance,
   flips <10% with 95% CI, positive discrimination, zero holdout approvals and
   no unlabelled fallbacks.
4. Contested/change cards work for new and old verdicts without fabricated state.
5. Only passing configurations are promoted to Alpha; all failures and limits
   are documented in `progress.md`.
