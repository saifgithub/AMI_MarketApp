<!--
Auditor run report — run-53 (2026-07-27, session auditor.core/track U). Round-1 audit
of DEF094. Audited SHA b02c5dc on lane/DEF094.coder.api. Verdict COMPLETE with one
MAJOR follow-up finding (a sibling defect, not a defect in DEF094 itself). Owner: AUDITOR.
-->

# run-53 (round 1) — DEF094 Sharia verdict on the wire → COMPLETE

- **Auditor session:** auditor.core (track U), 2026-07-27.
- **Audited SHA:** `b02c5dc`, tip of `lane/DEF094.coder.api` (base `main` @ `6b24833`).
  Audited in a fresh isolated worktree `.claude/worktrees/audit-DEF094/`, own `uv sync
  --frozen --extra dev` venv (the lane's own worktree had none).
- **The item:** `ComplianceResult.sharia_verdict` was computed and enforced but never
  serialized — `sim.py`'s hand-built response dicts dropped it, including the
  **accepted** trade path, which carried no compliance block at all. A PASS ticker
  and an UNKNOWN ticker returned byte-identical bodies on a successful trade — the
  exact silent-pass shape CR069/G3 exists to prevent.
- **Gate:** independent — D-5, an observance disclosure crossing the wire to two
  app stores.
- **Verdict:** COMPLETE (round 1) — delivered code is correct; one MAJOR finding
  about a **sibling** dark field, not a defect in DEF094's own delivered scope.

## Verification

### Reproduced independently

2 files, +305/−17, exact match (`sim.py` +75/−17 prod, new 247-line test file).
Targeted subset `-k "sim or sharia or compliance"` → **175 passed**, matching the
coder's claim exactly. Full suite → **1269 passed**, 4 pre-existing warnings, matching
both count and warning set exactly (145s vs. the coder's 144s — consistent).

Read `sim.py` in full: `ComplianceBlock`/`PreviewTradeResponse` are typed Pydantic
models (not hand-built dicts); `preview_trade` now declares
`response_model=PreviewTradeResponse`; `submit_trade`'s rejected path gained the
`sharia_verdict` key; the accepted path — previously **no compliance block at
all** — now returns `{ok: True, trade, compliance: {passed, violations, blocked_by,
sharia_verdict}}`. Confirmed the two-shape `submit_trade` dict return (no Union
response_model) was a deliberate, reasonable scope call for a ~2-line fix, not an
oversight.

**Contract check redone independently, not trusted from the hand-off** — read
`mobile/lib/models/sim.dart:227-249` and `mobile/lib/models/sharia.dart` directly.
`SimSubmitResult.fromJson` reads `compliance['sharia_verdict']` on **both** the
`ok:true` and `ok:false` branches, and `ShariaVerdict.fromJson`'s wire map
(`pass`/`screened_out`/`unknown`/`unavailable`) matches `ShariaStatus` byte-for-byte.
The claimed key names (`status`, `ticker`, `standard`, `source`, `as_of`) match
exactly — not assumed from the hand-off's description.

### Mutation-tested the delivered fix (3 probes)

1. **Dropped `sharia_verdict` from `submit_trade`'s accepted-path dict** (the
   defect's headline case) → exactly the 3 expected tests failed
   (`test_submit_accepted_carries_the_verdict`,
   `test_submit_accepted_unknown_ticker_is_permitted_and_discloses`,
   `test_pass_and_unknown_accepted_bodies_are_not_byte_identical`); 6 others
   unaffected.
2. **Dropped the explicit `response_model=` kwarg from `/preview` alone** — suite
   stayed green. Not a real gap: FastAPI still infers the response schema from the
   function's `-> PreviewTradeResponse` return-type annotation, so the explicit
   kwarg is redundant-but-harmless, not the load-bearing part of the OpenAPI claim.
3. **Dropped the `sharia_verdict` field from `ComplianceBlock` itself** (the actual
   load-bearing element) → 5 tests failed, including
   `test_shariaverdict_appears_in_the_openapi_schema` — confirms the OpenAPI claim
   is genuinely backed by the field's presence, not an artifact of route wiring.

All three reverted; suite re-confirmed 1269/1269 green before the next probe.

### A sibling defect found by asking what else lives on the same object

The hand-off itself flagged this for me to check: *"`classification_verdicts`
(DEF061's parallel field) was NOT touched — worth confirming it isn't a second dark
field the auditor expects fixed here versus tracked separately."* Confirmed by
grep: `classification_verdicts` is genuinely untouched by this diff (correct scope
call — DEF094's assign named `sharia_verdict` only).

But going one step further: `classification_verdicts` is populated in
`safety_floor.py` (lines 138-249) by the **exact same mechanism** as
`sharia_verdict` — one `ClassificationVerdict` per active `no_fossil_fuels` /
`no_tobacco_alcohol_gambling` / `esg_lite` flag, with an identical four-state
contract (PERMITTED / EXCLUDED / UNKNOWN-permitted-with-disclosure / UNAVAILABLE-
paused). Grepped `app/` for any place it reaches an API response: **zero hits**,
before or after this fix. `test_def061_compliance_enforcement.py`'s
`test_unknown_is_permitted_with_disclosure_not_blocked` proves the disclosure text
exists on the pure `ComplianceResult` — same "resolver correct, contract dark"
gap DEF094's own diagnosis named for `sharia_verdict` ("verifying the component is
not verifying the contract that reaches a client").

This is not hypothetical or dead code: `mobile/lib/models/mandate.dart:55-69`
already round-trips `esg_lite` and `no_fossil_fuels` as live, user-toggleable
mandate flags. A user who turns on `no_fossil_fuels` and trades an unclassified
ticker gets the exact silent-pass DEF094 was filed to close — just for a
different flag family, in the same file, on the same object.

### Findings

1. **MAJOR** (sibling defect, not present in DEF094's own delivered code) —
   `ComplianceResult.classification_verdicts` (DEF061's `no_fossil_fuels` /
   `no_tobacco_alcohol_gambling` / `esg_lite` verdicts) has the identical
   "computed, enforced, never serialized" shape this defect was filed to fix, for
   three live, user-toggleable mandate flags. Not present in any existing register
   entry (`def_list.md`/`cr_list.md` grepped — no hits). Recommend the Architect
   mint a new Defect immediately given the recurring observance/ethical-disclosure
   pattern and that the flags are already live on mobile.

## Verdict

**VERDICT: COMPLETE (round 1)**
