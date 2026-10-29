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
size, unresolved objections, evidence availability/source, contested flag and
reasons. The PM vote bar remains 4/4/3/2/2; the deterministic safety floor
remains the final veto. Uncalibrated providers and uncomputable evidence fail
closed with an explicit reason, never a silent bypass.

Sizing is continuous and monotone from 25% of mandate cap at the evidence
threshold to 100% at score 1.0. Thresholds are per model, monotone descending
from R1 to R5, and fitted by the calibration tool rather than hand-selected.

## Acceptance

1. Backend and mobile standard suites green; register parity clean.
2. R4 card pilot per model reaches ICC ≥0.85 with complete machine channels.
3. Full 30×5 per-model calibration reaches target curve within tolerance,
   flips <10% with 95% CI, positive discrimination, zero holdout approvals and
   no unlabelled fallbacks.
4. Contested/change cards work for new and old verdicts without fabricated state.
5. Only passing configurations are promoted to Alpha; all failures and limits
   are documented in `progress.md`.
