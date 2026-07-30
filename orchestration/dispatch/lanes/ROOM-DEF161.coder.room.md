<!-- lane hand-off — coder.room. CR052. -->
# ROOM-DEF161 — hand-off (coder.room, round 1)

STATUS: READY_FOR_AUDIT (round 1)
BRANCH: lane/ROOM-DEF161.coder.room

## What changed

`backend/app/api/room.py` — the cached-replay branch of `POST /v1/room/stream`
(the path a client hits reconnecting to a run whose events already finished).

Root cause confirmed: `runner.get_run(run_id)` returns `RoomRun.transcript` as
a list of **validated** `AgentMessage` objects. Pydantic fills a missing
`stance` key in the stored JSON with the model default (`None`) — the exact
same value a genuinely-recorded "agent stated no position" produces. By the
time `room.py` saw `msg.stance`, the two cases (never-existed vs.
recorded-null) were already indistinguishable, and the old code unconditionally
emitted all three keys (`'stance': msg.stance`, always present, `null` or not).

Fix: read the row's **raw JSON transcript** directly (`get_session()` +
`RoomRunRow`, zipped by index against `persisted.transcript`) and only include
`stance`/`conviction`/`headline` in the SSE `agent_done` payload when the
source dict actually had the `stance` key. Absent-from-snapshot → the keys
are omitted from the JSON entirely. Recorded (real or null) → all three keys
are emitted as before, verbatim.

No other file touched. `backend/app/agents/*`, `schemas/mandate.py`,
`api/journal.py`, `reputation_service.py`, `api/sse.py`, and everything in
`mobile/` are untouched.

## The two surfaces now agree — and the client side already existed

This is the useful discovery: **the mobile client was already written for
this.** Two places already do exactly the key-presence check the wire needed
to support:

- Journal mapper, `mobile/lib/models/room_board_mappers.dart:169-179`
  (`_voiceFromRow`): `stanceRecorded: row?.containsKey('stance') ?? false` —
  reads presence, not value, off the Journal payload's stored transcript dict.
- **Live/reconnect SSE decoder**, `mobile/lib/services/api/api_client.dart:173-185`
  (the `agent_done` case): already does
  `if (j.containsKey('stance')) 'stance': j['stance']` (and the same for
  `conviction`/`headline`) with a comment reading *"a server that predates B2
  sends neither key, and that is a different fact from an agent that took no
  side."* — dated to CR106 B2 itself.

So the client-side half of this fix **already shipped** — it just had nothing
correct arriving on the wire to act on, because `room.py`'s cached-replay
branch always sent the key. **The backend half alone is not inert — it is the
entire missing half.** No client change is owed. I read the widget/line above
to confirm this rather than assume it; I did not edit `mobile/`.

Practical effect once this ships: a pre-B2 run reconnected-to now arrives at
the client with `agent_done` events missing `stance`/`conviction`/`headline`
entirely → `api_client.dart`'s existing `containsKey` guard omits them from
the parsed map → downstream comb-building code sees "not recorded" for that
run, the same as the Journal already does for the identical run. The two
surfaces converge without a mobile-side change.

## Tests

New file: `backend/tests/unit/test_def161_room_replay_stance_absence.py`,
three tests driving the real `/v1/room/stream` dedup-to-completed-run path
(seeds a `RoomRunRow` directly, not through the runner, so the transcript
dict shape under test is exactly what a real pre/post-B2 row has):

1. `test_pre_b2_row_replays_stance_absent_not_null` — pre-B2 shaped row (no
   `stance`/`conviction`/`headline` keys at all) → replayed `agent_done` must
   omit `stance` entirely. **This is the one that was RED against the
   unfixed code** (asserted, see mutation below).
2. `test_recorded_neutral_still_round_trips_as_neutral` — post-B2 row with an
   explicit recorded `stance: "neutral"` → still replays
   `"stance": "neutral"` verbatim. Guards against the fix over-collapsing a
   genuine abstention into "not recorded".
3. `test_agent_that_stated_no_view_post_b2_still_omits_the_key` — documents
   the adjacent case for review: post-B2, agent genuinely stated no position
   (`stance: null`, key present) → still replays `"stance": null` (key
   present, value null) — this case is unchanged by the fix, only the
   never-had-the-key case changed.

Mutation check performed: `git checkout -- backend/app/api/room.py` (revert),
re-ran the three tests → test 1 goes RED (`AssertionError: pre-B2 replay must
omit the stance key entirely, got: ...`), tests 2 and 3 stay green (they were
already true of the unfixed code — the fix only had to correct the absent
case, not regress the recorded ones). Re-applied the fix → all three green
again.

## Full suite

Run from repo root of THIS worktree (own venv-less checkout, uses the root
repo's `backend/.venv`):

```
cd .claude/worktrees/coder.room-ROOM-DEF161
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest backend/tests/unit/ -q
```

Result: **[[FULL_SUITE_RESULT — fill in before flipping DISPATCH]]**

Expected baseline 1798, `>= 1798` with zero failures except the known
`test_cr084_revenuecat_webhook.py::test_test_store_expiration_revokes_to_floor_pass`
(another track's uncommitted work in the shared checkout — not touched here).

## Registers

DEF161 row: leaving status as **`open`** pending the note below — see
"Register note" — flip to `fixed` only once the full-suite line above is
filled in and clean.

**Register note (goes in the DESCRIPTION column, not the status cell,
per DEF203):** backend replay path now distinguishes absent-from-snapshot
from recorded-neutral in `room.py`'s cached SSE branch; mobile's
`api_client.dart` `agent_done` decoder already had the matching
`containsKey` guard (predates this fix, written at CR106 B2) — the two
surfaces (Room live/reconnect and Journal) now agree for pre-B2 runs. No
mobile-side change was needed or made.

## Fences respected

Only `backend/app/api/room.py` (source) and
`backend/tests/unit/test_def161_room_replay_stance_absence.py` (new test)
were touched. `mobile/`, `backend/app/agents/*`, `backend/app/schemas/mandate.py`,
`backend/app/api/journal.py`, `reputation_service.py`, `api/sse.py`,
`webhooks.py`, `scripts/` — untouched.

ASSIGNED: coder.room round 1
DISPATCH: OPEN
