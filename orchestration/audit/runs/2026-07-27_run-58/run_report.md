<!--
Auditor run report — run-58 (2026-07-27, session auditor.core/track U). Round-1
audit of DEF112. Audited SHA e2d9e4b on lane/DEF112.coder.api. Verdict COMPLETE.
Owner: AUDITOR.
-->

# run-58 (round 1) — DEF112 classification_verdicts on the wire → COMPLETE

- **Auditor session:** auditor.core (track U), 2026-07-27.
- **Audited SHA:** `e2d9e4b`, tip of `lane/DEF112.coder.api` (base `main` @ `43ef4f3`).
  Audited in a fresh isolated worktree `.claude/worktrees/audit-DEF112/`, own
  `uv sync --frozen --extra dev` venv.
- **The item:** `ComplianceResult.classification_verdicts` (DEF061's `no_fossil_fuels` /
  `no_tobacco_alcohol_gambling` / `esg_lite` verdicts) — the sibling gap I flagged in my own
  DEF094 round-1 verdict — was computed and enforced but never serialized. Same shape as
  DEF094, one field over: `sim.py`'s response dicts dropped it on every trade, including the
  accepted path.
- **Gate:** independent — D-5, identical risk class to DEF094.

## Verification

### Reproduced independently

2 files, +315/−5 exact (`sim.py` +21/−5 prod, new 299-line test file). Targeted subset
`-k "sim or classification or compliance"` → **123 passed**, matching the coder's claim
exactly. Full suite → **1310 passed**, 4 pre-existing warnings, matching exactly (152s).

Read the full `sim.py` diff: mirrors DEF094's structure exactly — `ComplianceBlock` gained a
typed `classification_verdicts: list[ClassificationVerdict] = Field(default_factory=list)`
field (a list, correctly never `None`/optional unlike the scalar `sharia_verdict`); both
`submit_trade` branches (rejected and the previously-dark accepted path) gained the
list-comprehension serialization; `preview_trade`'s existing response model picks it up
automatically. `safety_floor.py` correctly untouched (frozen HOT-FILE, out of scope — DEF061
already covers its enforcement correctness).

### Mutation-tested the delivered fix (2 probes)

1. **Dropped `classification_verdicts` from `submit_trade`'s accepted-path dict** (the
   defect's headline case) → exactly the 4 expected tests failed
   (`test_submit_accepted_carries_the_verdict`,
   `test_submit_accepted_unknown_ticker_is_permitted_and_discloses_esg_lite`,
   `test_submit_accepted_empty_when_no_classification_flags_active`,
   `test_permitted_and_unknown_accepted_bodies_are_not_byte_identical`); 6 others unaffected.
2. **Dropped the `classification_verdicts` field from `ComplianceBlock` itself** (the actual
   load-bearing element for the OpenAPI claim) → 5 tests failed, including
   `test_classificationverdict_appears_in_the_openapi_schema` — confirms the OpenAPI claim is
   genuinely backed by the field's presence.

Both reverted; suite re-confirmed 1310/1310 clean before the next probe.

### Closed a gap the hand-off itself flagged as untested

The hand-off explicitly disclosed: *"Multiple active flags in one trade were NOT tested
together... worth confirming whether the acceptance bar expects a multi-flag response to carry
two list entries."* Wrote an independent ad-hoc check (not part of the shipped test suite):
submitted a trade on XOM with **both** `no_fossil_fuels` and `esg_lite` active simultaneously
against the real API. Result: `classification_verdicts` correctly carried **2 independent
entries** (`fossil_fuels: excluded`, `esg_lite: excluded`), matching `check_mandate_compliance`'s
per-active-flag loop (`safety_floor.py`) — not deduped, not truncated to one. Closes the one
adversarial angle the coder left open.

### Mobile contract — confirmed genuinely untouched, not just claimed

Grepped `mobile/lib/` for `classification_verdict`: zero hits, confirming the hand-off's claim
that this is a new response-side surface with no existing mobile consumer to cross-check against
(unlike DEF094, where `sim.dart`/`sharia.dart` already read `sharia_verdict` and needed direct
verification). Nothing to regress on the mobile side for this lane.

## Findings

None.

## Verdict

**VERDICT: COMPLETE (round 1)**
