# Run report — 2026-08-07_run-09

Item: CR121, round 3. SHA: `0423c1a6`. Verdict: **COMPLETE (round 3)** — 0
BLOCKER, 0 MAJOR, 1 MINOR (new, non-blocking). Full findings in
`orchestration/audit/cr/CR121.auditor.md`'s RECONCILIATION section (the tail
of the file).

## Collision with a concurrent auditor pass — again, and this time it swept a file

Dispatched to round 3 by the coordinator (round 2's addendum findings were
confirmed fixed). Audited independently in `.claude/worktrees/audit-CR121-r3`
against all 5 items the submission asked to be attacked. While writing up
the verdict, a concurrent `AT:U66` instance — independently auditing the
same round in its own worktree (`audit-CR121-r3-u66`) — committed and pushed
its own round-3 `COMPLETE` (`92261805`) first. Because both sessions write
the SAME lane file in the SAME shared checkout, `AT:U66`'s `git add` picked
up this session's already-written-but-not-yet-committed "ROUND 3" section
along with its own and committed both together in one commit. Confirmed via
`git diff f5c47b5b 92261805 -- orchestration/audit/cr/CR121.auditor.md` —
the diff's first ~230 lines are this session's own text verbatim, followed
by `AT:U66`'s independent write-up.

Nothing was lost (both write-ups are intact, unedited, in the committed
file) but the two "## VERDICT: COMPLETE (round 3)" headings are two
independent verdicts landed by accident in one commit, not one restated —
and critically, `AT:U66`'s pass did not read this session's section (it
couldn't have; this session's text was still uncommitted, local-only, when
`AT:U66` read the lane before writing its own), so `AT:U66`'s own finding
list does not net in the one thing this pass found that theirs didn't (see
below). Did not rewrite or delete either committed section — both are
historical record, same convention this lane has followed all day (round 1's
original text stays under round 2's addendum, etc.). Appended a
RECONCILIATION section explaining the collision plainly and carrying the
one net-new finding + the corrected final verdict/count.

## Setup

```
cd "/Volumes/Extreme Pro/AMI_MarketApp"
git worktree add --detach .claude/worktrees/audit-CR121-r3 0423c1a6
```

Declared files (`backend/app/main.py`, `backend/tests/unit/test_cr121_release_floor.py`,
`mobile/lib/services/api/api_client.dart`, `mobile/lib/services/api/api_exceptions.dart`,
`mobile/lib/services/api/friendly_error.dart`, `mobile/lib/state/version_gate_providers.dart`,
`mobile/test/state/version_gate_raise_from_server_test.dart`) — zero drift
`0423c1a6` → `main`.

## Regression suite (independent, scratch worktree, absolute interpreter)

```
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q
2682 passed, 13 warnings in 353.74s
```

Exact match to the submission.

## Item 5 — the number, re-derived per-SHA independently (not relayed)

```
git worktree add --detach .claude/worktrees/audit-cnt-<sha> <sha>   # 82fd43fd, a0f122f0, 6bcb616d
pytest tests/unit/ --collect-only -q | grep -c "::"

82fd43fd -> 2675
a0f122f0 -> 2678   (+3)
6bcb616d -> 2681   (+3)
0423c1a6 -> 2682   (+1)
```

Exact match to the submission's decomposition. Diffed the collected IDs for
the final hop:

```
$ diff <(pytest --collect-only in worktree 6bcb616d | sort) <(pytest --collect-only in worktree 0423c1a6 | sort)
625a626
> tests/unit/test_cr121_release_floor.py::test_a_negative_or_unparseable_build_is_refused_at_the_boundary
```

## Item 1 — wrapped shape confirmed live, both bare and wrapped give correct copy

`_VersionGateInterceptor.onError` always re-wraps (`handler.next(DioException(...,
error: upgrade))`) before a real call site ever sees the error;
`_ServerErrorInterceptor` (processes after it in Dio's error-interceptor
stack) only rewrites for `code >= 500`, passing 426 through unchanged.
Reproduced directly (not just via the shipped test):

```dart
friendlyError(const UpgradeRequiredException(minBuild: 58, action: 'block'), action: 'place that trade')
// bare    -> "Couldn't place that trade — this version of AMI is out of date. Update to continue."
friendlyError(DioException(..., error: const UpgradeRequiredException(...)), action: 'place that trade')
// wrapped -> "Couldn't place that trade — this version of AMI is out of date. Update to continue."
```

`flutter test test/state/version_gate_raise_from_server_test.dart` → `40
passed`.

## Item 3a — non-`block` actions don't escalate: correct, no issue

Middleware only ever emits 426 for the block case (confirmed unchanged in
`version_gate.py`) — pure defense-in-depth, not reachable today, correctly
conservative.

## Item 3b — refusing to overwrite an existing block: correct in one
## direction, misses the reverse — NEW MINOR

The shipped test proves only "real detail first, bodyless second → bodyless
ignored." The reverse is unguarded:

```dart
final c = controller();
c.raiseFromServer(const UpgradeRequiredException());               // bodyless, arrives first
// state: blocked=true, headline=null, storeUrl=null
c.raiseFromServer(const UpgradeRequiredException(
  minBuild: 58, action: 'block', headline: 'Update required',
  body: 'Build 57 can no longer place trades.',
  storeUrl: 'https://testflight.apple.com/join/ABC123',
));                                                                  // real detail, second
// state UNCHANGED: headline=null, storeUrl=null
```

Bounded: requires a real 426's body to fail client-side JSON parsing (not
the ordinary case), and the block screen's own always-visible "check again"
button (`.check()`, an unconditional overwrite, no `isBlocked` guard) is a
one-tap fix already on screen. The safety property (stale build can't
transact) holds throughout. MINOR, not MAJOR. Suggested fix: key the
refusal on whether the incoming exception carries MORE information than the
current state, not on `isBlocked` alone.

## Item 2 — `ServerUnavailableException`'s identical latent bug

Confirmed real (same annotate-and-rewrap pattern `_VersionGateInterceptor`
had before this round's fix, unchanged in `_ServerErrorInterceptor`/DEF073)
and confirmed currently harmless — reproduced bare vs. wrapped giving
byte-identical copy and identical `isRetryable`:

```dart
friendlyError(const ServerUnavailableException(503), action: 'load your lessons')
// -> "Couldn't load your lessons — AMI is temporarily unavailable. Try again in a moment."
friendlyError(DioException(..., type: badResponse, response: [503], error: const ServerUnavailableException(503)), action: 'load your lessons')
// -> identical string; isRetryable identical (true, true)
```

Traced the one live bare-throw site (`streamRoom`, `api_client.dart:935`,
the SSE transport that bypasses Dio entirely) — caught by
`room_providers.dart`'s own specific `on ServerUnavailableException` handler
before it would ever reach `friendlyError`. No execution path in the current
codebase reaches `friendly_error.dart`'s `ServerUnavailableException` branch
at all. Verified-and-closed, not filed as a new item — matches the
submission's own framing and `AT:U66`'s independent pass reached the
identical conclusion.

## Item 4 — `Query(ge=0)`: verified, mutation-killed

`?build=not-a-number` / `?build=-5` → 422; `?build=0` / omitted → 200.
Reverted `Query(ge=0)` to plain `None` default — the new test fails exactly
as expected (`assert 200 == 422` on `?build=-5`). Reverted clean.

## Files touched by this pass

- `orchestration/audit/cr/CR121.auditor.md` — RECONCILIATION section
  appended (the two round-3 sections above it are `AT:U66`'s commit,
  untouched).
- `orchestration/audit/audit-trail.md` — ledger row appended.
- `orchestration/audit/runs/2026-08-07_run-09/run_report.md` — this file.

No source outside the two auditor-owned pin-carve-out files already carried
in `0423c1a6` was touched this round.
