# Run report — CR237 round 1 (U69, 2026-09-25)

**Item:** CR237 — "Ask the CIO again" after a CIO-outage PASS. **Tier A.**
**SHA audited:** `dbf9632ccd19da64912dc16232ebfebb7369b399` (branch
`worktree-agent-a9118ad435e787cf1`, off `main`; detached worktree
`.claude/worktrees/audit-CR237/`).
**Verdict:** AWAITING_FIXES (round 1) — 3 MAJOR, 1 MINOR, 1 out-of-scope.

## Commands run (all from the worktree unless noted)

- `python -m pytest tests/unit/test_cr237_cio_retry.py tests/unit/test_def432_room_outage_refund.py
  tests/unit/test_def425_def432_respawn_keeps_charge.py tests/unit/test_cr236_room_done_credit_cost.py
  tests/unit/test_room_runner.py tests/unit/test_def200_ratchet.py
  tests/unit/test_no_blocking_io_in_async_routes.py tests/unit/test_config_compose_parity.py
  tests/unit/test_def278_migrations_are_immutable.py tests/unit/test_def406_single_migration_head.py
  tests/unit/test_registers_no_drift.py tests/unit/test_p30_registers_name_things_that_exist.py
  tests/unit/test_def295_seeded_translations_are_marked.py tests/unit/test_http_audit_scrub.py
  tests/unit/test_merge_service.py -q -p no:cacheprovider` (interpreter: the repo's absolute
  `.venv` path) → **259 passed, 1 skipped in 208.34s**. Matches the submission's combined figure.
- `python -m alembic heads` → `cr237a0cio0retry1 (head)` — single head, as claimed.
- Mobile (`worktree/mobile/`): `flutter pub get`, `flutter analyze --no-fatal-infos` →
  11 issues, all `info`, matching the submission's pre-existing 11; `flutter test` →
  **1816 passed** (1808 + 8 new, as claimed).
- Auditor's own blind probe — `cio_retry_eligible` edge matrix, 19 cases constructed
  directly against the schema (happy path, failed-refund no-suffix shape, legacy wording,
  R51 partial-outage, reasoned PASS, missing override flag, wrong user, missing/empty
  snapshot, stale mandate, four non-completed statuses, age boundary both sides, None and
  naive `finished_at`): **19/19 expected results**.
- Full unit suite at the SHA: kicked off; figure recorded in the ledger row when landed.

## Code read (file:line, worktree SHA)

`room_runner.py`: `cio_retry_eligible` :800-855; `retry_cio_step` :6916-7156 (no
`spend`/`refund` anywhere in the body); `_run_cio_step` :4466+ with the single shared
`enforce_safety_floor` call at :4755; refund ordering :6682-6745 (`refund_recorded=True`
only in the refund-success `else:`); snapshot write :6743 (outage-PASS-only, inside the
refund-success branch — verified coherent with the mobile third cost line's claim);
`run_was_refunded` :718-774; `_rebuild_ctx_from_snapshot` :4350-4405; in-memory
`_retrying_runs` guard :5280 with the single-process justification (Dockerfile CMD has no
`--workers` — verified). `api/room.py`: route :435-519 (plain `def`, 404/403 pre-stream,
in-band refusals), `_compute_cio_retry_available` :88-105. `journal_store.py`:
`update_by_reference` :318-363. Migration: additive, server defaults, single head.
Mobile: `room_providers.dart` retryCio + done/error handlers, `room.dart:195-221`,
`credits_line.dart` diff, `api_client.dart` retryCioStep SSE loop.

## Foreign pass (CR215, Tier A)

`dispatch_foreign_audit.sh CR237 dbf9632c… 1 …` → branch `foreign/CR237.r1`, commit
`bea87350`, model kimi-code/k3, FOREIGN-VERDICT: ADVISORY-CONCERNS, 5 findings.
Dispositions (each re-verified at file:line by this auditor): **3 real → MAJOR-1/2/3**
(verdict loses `sheet_state`/`reference_price`/`next_convene_delta` on retry persist —
`room_runner.py:6638-6643` vs `:7112`, consumer `:5787-5793`; soft-deleted journal entry
resurrected — `journal_store.py:339-341` vs `room_runner.py:7142-7148`; mobile GET path
never parses the cio flags — `room.dart:195-221`, `room_providers.dart:625-633`), **1 real
downgraded MINOR** (no `live` guard on retry — reachable only via mid-window config
removal; sanctioned mock-mode behaviour otherwise), **1 real but pre-existing** (sweep/
respawn refund paths never set `refund_recorded`; `status=="failed"` short-circuit masks
it — documented CR039 shape). Counts recorded in `foreign_trail.md`. All three MAJORs are
correlated-error catches: Claude built and self-audited the lane without flagging any of
them; this Kimi gate also missed them pre-foreign (F1/F2; F3's area I had noted but not
pursued).

## Findings

See `orchestration/audit/cr/CR237.auditor.md` — MAJOR-1/2/3, MINOR-1, one OUT-OF-SCOPE.
