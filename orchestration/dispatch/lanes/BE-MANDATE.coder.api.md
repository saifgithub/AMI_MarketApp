<!-- lane hand-off — coder.api. CR052. -->
# BE-MANDATE — hand-off (round 1)

STATUS: READY_FOR_AUDIT (round 1)

Branch: `lane/BE-MANDATE.coder.api`, worktree `.claude/worktrees/coder.api-BE-MANDATE`.

## DEF179 — paywall bypass, entitlement fields client-writable

**Fix, three touch points:**

1. `backend/app/schemas/mandate.py` — new module-level constant
   `CLIENT_UNWRITABLE_MANDATE_FIELDS = frozenset({"plan", "credit_balance",
   "credit_allowance", "trial_expires_at", "trial_started_at"})`. Single source
   of truth for the field list both fixes below filter against.
2. `backend/app/services/mandate_store.py::MandateStore.patch()` — filters
   `updates` against that set before the deep-merge/re-validate, so none of
   those keys ever reach the persisted `Mandate`.
3. `backend/app/services/mandate_store.py::resolve_mandate()` — the SAME
   filter applied to `override` (the `mandate_override` request body) before
   it reaches `hydrate_brief_mandate(override)`. **Deliberately NOT inside
   `hydrate_brief_mandate` itself** — that function is a trusted constructor
   with legitimate direct callers (tests, `MandateStore.get_or_default`'s own
   `hydrate_brief_mandate({"user_id": ...})` call) that pass an explicit
   `plan` on purpose. Filtering inside it would have silently broken every
   such caller (it did, in round 1 of writing this — `test_brief_engine.py`'s
   `trader_mandate` fixture stopped actually being "trader"; caught because
   the mutation-test pass below re-derives every assumption). The untrusted
   boundary is specifically `resolve_mandate`'s `override` param, which is
   where `req.mandate_override` from `/v1/brief/start` and
   `/v1/agents/one_on_one/start` actually lands — that's where the filter
   belongs.

**Decision — silent drop, not reject (acceptance-3):** a PATCH carrying
`plan`/`credit_balance`/etc. returns **200** with those fields ignored, not
400. Reasoning: `GET /v1/mandate/{id}` always echoes `plan`/`credit_balance`
on every response (CR039 `_with_plan_state` stamps them from server truth
regardless of what's stored) — a client that reads a mandate and PATCHes it
straight back (a plausible pattern, not necessarily malicious) would 400 on
fields it never intentionally touched if we rejected. Pinned by
`test_patch_silently_drops_entitlement_fields_returns_200`.

**Consumers switched to `effective_plan_for_user(user_id)`:**
- `backend/app/api/one_on_one.py::start_one_on_one` — the 1-on-1 agent-lock
  gate.
- `backend/app/services/brief_engine.py::BriefEngine.accept` — the Brief
  edit-cap. Also deleted `_plan_from_mandate` (now dead — its one call site
  was this line) and the now-unused `mandate = Mandate.model_validate(...)`
  local in `accept()`.

**Grep for other readers of `mandate.plan` (acceptance-2), reported not
changed:**
- `backend/app/services/agent_runner.py:263-266` (`_stream_concierge`) — reads
  `mandate.plan` ONLY on the `user_id is None` branch (pre-claim anon user,
  no DB row to look up via `effective_plan_for_user`), and only feeds
  Concierge's lesson/journal context — Concierge is never plan-gated
  (`one_on_one.py`'s own check skips it). Not a bypass vector; left as-is.
- `backend/app/services/concierge_prompts.py:229`, `agents/overlay_generator.py:494`
  — narration/prompt text (what the agent is TOLD its plan is), not an
  enforcement gate. Out of scope.
- `backend/app/services/credit_service.py` / `app/api/admin.py` — these read
  `user.plan` (the ORM row), not `Mandate.plan`. Already correct.

**Bonus bug found + fixed in the same touch (not filed as a separate
DEF — same file, same block, blocking my own acceptance-1/2 tests
entirely):** `one_on_one.py`'s `OneOnOneStartRequest` has
`model_config = ConfigDict(use_enum_values=True)`, so `req.agent_id` is
already a plain `str` post-validation — `req.agent_id.value` raised
`AttributeError` (surfaced as a bare 500) on **every** locked-agent request,
for every Floor Pass user, unconditionally. This isn't something DEF179
introduced; it pre-dates this lane and would have crashed in production
today. Fixed both `.value` accesses (the `unlocked` membership check and the
`agent_id` field in the 403 detail body) to use `req.agent_id` directly.
Flagging in case Governance wants a DEF number retroactively — I'm not the
ID-minter.

## DEF193 — mandate GET now stamps the resolved (enforced) cap

- `backend/app/schemas/mandate.py` — new `ResolvedCaps` model
  (`sector_cap_pct: float`, `single_name_cap_pct: float`, both required/never
  null) + `Mandate.resolved: ResolvedCaps | None = None` (stamped by the API
  layer, same pattern as `plan`/`credit_balance` — never persisted on the
  row). Exported from `app/schemas/__init__.py`.
- `backend/app/api/mandate.py::_with_plan_state` — computes `resolved` via
  `app.trading_math.sizing.resolved_sector_cap_pct` /
  `resolved_single_name_cap_pct` — **the exact same functions**
  `sector_allocation.sector_concentration_cap` and
  `safety_floor.single_name_cap_pct` call underneath (verified by reading
  both; neither adds logic beyond a units conversion / a `None`-input
  defensive branch that mandate schema validation makes unreachable). Chose
  to import from `app.trading_math.sizing` rather than from
  `sector_allocation.py`/`safety_floor.py` directly — both of those are
  fenced to `BE-MINOR`, and the lower-level module is the one place CR046
  says the number is actually computed, so there's no coupling to the fenced
  files at all, not even a read-only import.
- Units: `resolved.*_cap_pct` are percentage points, matching
  `Mandate.sector_cap_pct`/`single_name_cap_pct`'s own units (not the 0-1
  fraction `portfolio.py`'s `max_allowed` uses) — "disclosed in its own
  units" per CR101's invariant. Tests assert the cross-endpoint number
  matches after the `* 100` conversion.
- No client-side computation (acceptance-5): the resolver functions run
  server-side inside the mandate API handler; nothing in mobile or this PATCH
  path replicates the preset tables.

## Tests

- `backend/tests/unit/test_def179_mandate_paywall_bypass.py` (9 tests) — both
  vectors (PATCH, `mandate_override`), the silent-drop decision, both
  consumers' downstream consequences (agent lock stays engaged / edit cap
  stays at 3), and that a **genuine** upgrade via `users.plan` (not the
  mandate) correctly unlocks both — proving the gate reads the *right*
  source, not just that it ignores the wrong one.
- `backend/tests/unit/test_def193_mandate_resolved_caps.py` (6 tests) —
  `resolved` never null, matches the default risk-tier preset, matches
  `GET /v1/portfolio/sector-allocation`'s `max_allowed` (the cross-endpoint
  assertion that IS the fix), still matches after an explicit override, the
  single-name figure pinned against the shared `trading_math.sizing`
  function, and a CR046 guard that the numbers move with the server-side
  preset table (not hard-coded).
- `backend/tests/unit/test_brief_engine.py::test_trader_plan_has_unlimited_edits`
  — updated to give the test user a real DB row with `plan="trader"`, since
  `accept()` no longer reads the mandate's own `plan` field. (The other
  `hydrate_brief_mandate`-only tests in that file didn't need changes —
  none of them assert on `accept()`'s plan-gated behavior for more than 1-2
  edits, so the pre-existing coincidence of a no-DB-row user resolving to
  `FLOOR_PASS` didn't matter to them.)

## Mutation testing (acceptance-6) — DONE, all as expected

Reverted each fix point in turn, ran the relevant new test file, confirmed
RED, then restored:
1. `MandateStore.patch()`'s field-strip → 2 tests red
   (`test_patch_plan_does_not_persist_into_the_stored_mandate_row`,
   `test_patch_plan_leaves_brief_edit_cap_at_three`).
2. `resolve_mandate()`'s override field-strip → 1 test red
   (`test_resolve_mandate_ignores_client_plan_override_for_new_user`).
   Note: `test_one_on_one_start_mandate_override_cannot_unlock_agent` did
   NOT go red on this mutation alone — it's still caught by fix #3 below
   (defense in depth: even with the override unstripped, the gate reads
   real `users.plan`, not the mandate). Reporting honestly per the assign.
3. `one_on_one.py`'s `effective_plan_for_user` switch → 2 tests red
   (`test_patch_plan_leaves_agent_lock_engaged`,
   `test_one_on_one_start_mandate_override_cannot_unlock_agent`).
4. `brief_engine.py::accept()`'s switch → 2 tests red
   (`test_patch_plan_leaves_brief_edit_cap_at_three`,
   `test_brief_accept_reads_effective_plan_not_stored_mandate`).
5. DEF193's `resolved` stamp in `mandate.py::_with_plan_state` → all 6 of
   `test_def193_mandate_resolved_caps.py` red (`TypeError` on `None`).

No mutation came back green — every fix point is covered by at least one
test, matching the acceptance-6 requirement.

## Full suite

`"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q` from repo
root (worktree): **1706 passed, 0 failed, 8 warnings** (336.94s). This
includes the 15 new tests across the two new files.

**Discrepancy to disclose (assign's own escape clause):** the assign states
baseline **1719**; this worktree (branched from `main` at `e4532c3a`) measures
**1706** total *including* my 15 new tests, i.e. **1691** pre-existing tests
in this branch point — 28 fewer than the stated 1719. Zero failures/errors
either way, and I did not delete or skip any test. Likely explanation: three
other backend lanes (BE-MINOR, SIM-DEF166, ROOM-MINOR per the dispatch memo)
are adding tests concurrently in their own worktrees off the same `main`, so
1719 may be a later/different snapshot than this branch's fork point, or
counted after some of those lanes' own additions land. Not something I can
resolve from inside this worktree — flagging per "if you can measure an
instruction is wrong, disclose with the measurement," not asserting it IS
wrong.

## Registers

`docs/defect/_registry/DEF179.row.md` and `DEF193.row.md` flipped to
`resolved` (the convention actually used across existing rows — the assign
said "fixed" but every existing row uses `resolved`/`open`, so matched the
real convention). Regenerated `docs/defect/def_list.md` via
`scripts/registers/gen_registers.py gen def`. All three land in the same
commit as the code, per DEF159.
