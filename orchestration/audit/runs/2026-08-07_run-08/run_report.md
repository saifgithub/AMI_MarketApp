# Run report — 2026-08-07_run-08

Item: CR121, round 2 addendum. SHA: `c6cca556` (lane at `110c3a16` /
`921783db`). Verdict: **AWAITING_FIXES (round 2)** — updates the prior
`COMPLETE (round 2)` on this lane. 1 MAJOR (new), 0 BLOCKER, 1 MINOR (new).
Full findings in `orchestration/audit/cr/CR121.auditor.md`'s ADDENDUM
section.

## Collision with a concurrent auditor pass — twice

Started this session dispatched to audit **round 1** at `04be4b91`
(`ddacd608`). Independently ran the full adversarial brief (fail-open
matrix, footgun guard mutation, middleware ordering, cannot-5xx, mobile
fail-open path) against a fresh detached worktree. Partway through,
`git fetch origin main` showed a DIFFERENT track-U instance (`AT:U66`) had
already pushed round 1 (`aae675af`, AWAITING_FIXES: 1 MAJOR untested-log-fix,
1 MINOR test-count misattribution), the architect had already fixed and
resubmitted round 2 (`c6cca556` / `110c3a16`), and the coordinator then
redirected this session explicitly to round 2. Confirmed via
`git log --oneline origin/main`.

Redid the round-2-specific attack list the coordinator gave (mutation-delete
the log block against the FULL suite in isolation, not just the targeted
file; field-swap `client_build`/`min_build`/`path` one at a time; check the
"no event on an allowed request" test isn't vacuous; diff collected test IDs
`04be4b91`→`c6cca556`). All four confirmed exactly as the architect and
`AT:U66` both claimed.

While finishing the writeup, `git fetch` again showed `AT:U66` had ALSO
already completed and pushed a **round-2 COMPLETE** (`921783db`) — zero
BLOCKER/MAJOR/MINOR, "everything from round 1... not re-litigated." Read
that verdict in full: it correctly re-verified the round-2 diff, but
explicitly deferred to its own round-1 pass for the fail-open/footgun/mobile
areas — which is exactly where the two findings below came from, since
neither round-1 pass on this lane (this session's own independent one, nor
`AT:U66`'s) had traced `_VersionGateInterceptor`'s annotated exception
forward to where the app actually turns it into user-facing text, and
neither had mutated `highest_observed_build`'s two-column scan specifically
(only the surrounding footgun-check-as-a-whole).

Folded as an addendum into the same lane file, matching this repo's own
established convention for a second independent pass on an already-verdicted
round (CR095 r1, CR131 r1, CR141 r1, CR124 r3, CR132 r1 — all today). The
prior `COMPLETE (round 2)` line is superseded, not deleted — both are still
in the file for the record.

## Setup

```
git worktree add --detach .claude/worktrees/audit-CR121-r1 04be4b91   # then superseded, see above
git worktree add --detach .claude/worktrees/audit-CR121-baseline 04be4b91
git worktree add --detach .claude/worktrees/audit-CR121-r2 c6cca556
```

## Regression suite (independent, scratch worktree, absolute interpreter)

```
cd .claude/worktrees/audit-CR121-r2/backend
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q
2656 passed, 13 warnings in 346.08s
```

Exact match to both the architect's and `AT:U66`'s claimed `2656 passed`.

## Round-2 diff — the coordinator's 4 specific attacks

1. **Collected-ID diff `04be4b91` → `c6cca556`:**
   ```
   diff <(pytest --collect-only -q | sort) <(pytest --collect-only -q | sort)
   616a617,618
   > tests/unit/test_cr121_release_floor.py::test_a_block_is_logged_with_the_numbers_an_operator_needs
   > tests/unit/test_cr121_release_floor.py::test_an_allowed_request_logs_no_block_event
   ```
   Exactly the two new tests, nothing else. `2654` → `2656`.

2. **Deletion mutation, full suite, isolated (no file touched until the run
   finished — an earlier attempt raced a file-restore against the
   background job and was discarded even though it happened to land on the
   same number):**
   ```
   # 6-line logger.warning(...) block deleted
   1 failed, 2655 passed, 13 warnings in 352.08s
   FAILED tests/unit/test_cr121_release_floor.py::test_a_block_is_logged_with_the_numbers_an_operator_needs
   ```
   Confirms nothing else in the 2656-test suite depends on that line.

3. **Field-swap mutations**, each applied alone and reverted before the
   next:
   - `client_build=floor.min_build, min_build=build` (swapped) →
     `assert blocked[0]["client_build"] == 50` fails (`assert 100 == 50`).
   - `path="/wrong/path"` → the path assertion fails
     (`- /v1/sim/portfolio/x` / `+ /wrong/path`).
   - Confirms the pin checks all three fields, not just event presence.

4. **Non-vacuity of `test_an_allowed_request_logs_no_block_event`:** made
   the middleware log unconditionally (every request, not just a block) →
   the test fails on a 200 response (`assert not [...]` sees the logged
   event). Not vacuous.

All four match the architect's and `AT:U66`'s claims exactly.

## Finding 1 (new) — MAJOR: the mobile 426 belt-and-braces path is invisible to the user

```
$ grep -rn "upgradeRequiredFrom\|UpgradeRequiredException" mobile/lib/ | grep -v "api_client.dart\|api_exceptions.dart"
(no output)
```

`_VersionGateInterceptor` annotates a 426's `DioException.error` with
`UpgradeRequiredException` correctly (unit-tested in isolation,
`version_gate_interceptor_test.dart`). Nothing in `lib/` calls
`upgradeRequiredFrom(e)` to react to it — unlike `serverUnavailableFrom(e)`
(DEF073's parallel construct for 5xx), which `room_providers.dart` DOES
consume (`on ServerUnavailableException catch`). All 15 call sites that
route errors to the user go through `friendlyError(e, ...)` (DEF148's single
funnel), which has no `UpgradeRequiredException`/426 branch:

```dart
// mobile: dart run test-style probe against the real friendly_error.dart
friendlyError(err426, action: 'place that trade')
// => "Couldn't place that trade — that request wasn't accepted.
//     Check the details before trying again."
```

Same wrong message whether `err426` is the raw `DioException` or the
interceptor-annotated one — `friendlyError` never inspects `.error` at all.
`_forStatus` has no `426` case; it falls through the same branch as a
generic non-retryable 4xx. No headline, no update language, no store link,
no route to `VersionGateBlockScreen`. `test/friendly_error_test.dart`'s
completeness guard (source-sweep for raw exception leaks) doesn't catch
this — it checks that every call site routes THROUGH `friendlyError`, not
that `friendlyError` itself knows what a 426 means; its own status table
never includes 426.

Practical effect: `VersionGateController.check()` (the mechanism that
actually shows the real block screen) only runs at app launch and on
`AppLifecycleState.resumed`. Any other API call made while a user is below
the floor — which is precisely the case `VersionGateMiddleware`'s own
docstring names as its reason to exist ("a patched binary that never calls
the [floor] endpoint... still cannot transact... makes the gate real
against a bypass") — surfaces as an indistinguishable-from-generic error on
every subsequent action, with no indication it's a version-gate block and no
path to the update CTA, until the user happens to background/foreground the
app.

MAJOR not BLOCKER: the server-side refusal itself holds (426, not 200 —
nothing transacts on a stale build), and the dominant real-world path
(launch + resume) is correctly wired. Scoped to the window between a
mid-session floor raise and the user's next backgrounding.

## Finding 2 (new, MINOR) — malformed `?build=` on the read endpoint returns 422, not `ok`

```
GET /v1/client/release-floor?build=not-a-number
→ 422 {"detail": [{"type": "int_parsing", "loc": ["query", "build"], ...}]}
```

The submission's claim ("every [degenerate] one resolves to `ok`, never
`block`") holds for the **header** path (`parse_build_number` never raises)
but not for the read endpoint's bare `build: int | None` Pydantic query
param, which never goes through `parse_build_number`. Not reachable by the
real client (`DeviceContext.buildNumber` is a real Dart `int?`) — requires a
hand-crafted request to the unauthenticated endpoint. Corollary: with
`min_build=0` (itself only reachable by writing the DB directly —
`AdminReleaseFloorRequest.min_build: int = Field(gt=0)` blocks it through
the real write API) a negative `?build=-5` resolves to `block`, contradicting
"min_build=0 never blocks a real build" — same non-reachability caveat.

## Verified, no new issue — highest_observed_build's dual-column claim (mutation gap, closed by auditor pin)

```
# deleted ONLY the user_devices.app_version loop, left users.last_app_version
$ pytest tests/unit/test_cr121_admin_release_floor.py tests/unit/test_cr121_release_floor.py -q
35 passed in 2.11s          # invisible to every existing CR121 test
```

Every existing fixture (`_seed_observed_build`) writes the same build to
both columns, so neither loop was independently proven load-bearing by the
existing suite — the round-1 pass's mutation (deleting the whole footgun
`if` check) proved the guard exists, not that both columns matter. Closed,
not left open: wrote
`backend/tests/unit/test_cr121_highest_observed_scans_both_columns_pin.py`
(registered in `MIGRATED_PINS`, DEF141) — two cases, one per column being
the max, non-overlapping values. Confirmed it passes on `main` and confirmed
it kills the mutation above in both directions (`40 == 90` failure) when
either loop is dropped.

## Also re-verified, matches both prior passes, no new issue

- **Middleware ordering**, verified empirically this time (prior passes read
  Starlette source): printed the actual built ASGI middleware stack after a
  live request — `ServerErrorMiddleware → CORSMiddleware →
  VersionGateMiddleware → HTTPAuditMiddleware → ExceptionMiddleware → ... →
  router`. Sent a blocking request through a live `TestClient`, queried
  `http_audit` for that path: `0` rows. CORS headers present on the 426.
- **Cannot 5xx**: raised inside `get_session` itself (not just
  `get_active_floor`, which round 1 already covered) — falls through to
  `call_next` correctly (401 from the unauthenticated downstream route, not
  a 5xx).
- `flutter analyze --no-fatal-infos`: 6 issues, all pre-existing, none in
  CR121 files. `flutter test`: 509 passed. Both match the submission.
- `alembic heads`: single head, `1d3f04e6d806`.

## Files touched by this auditor pass

- `orchestration/audit/cr/CR121.auditor.md` — ADDENDUM section appended.
- `backend/tests/unit/test_cr121_highest_observed_scans_both_columns_pin.py`
  — new pin (DEF141).
- `backend/tests/unit/test_def141_audit_pins_are_collected.py` —
  `MIGRATED_PINS` +1.
- `orchestration/audit/audit-trail.md` — ledger row appended.
- `orchestration/audit/runs/2026-08-07_run-08/run_report.md` — this file.

No source outside `backend/tests/unit/`'s pin carve-out was touched.
