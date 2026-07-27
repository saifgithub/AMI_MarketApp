# PROMOTION HOLD — do not promote `main` to Alpha

**If this file exists and lists an ACTIVE hold below, `/promote-to-alpha` must ABORT at preflight.**

This file is the structural guard for the case where `main` is green, audited, and still must not
ship — because a backend change depends on a *client* change that hasn't reached devices yet. Backend
promotion is an rsync; a Flutter build is a store release. Those are days apart, and nothing else in
the pipeline notices the gap.

To clear a hold: delete its block, and record in the trail *why* the precondition is now met
(measured, not assumed). An empty holds list means promotion is unblocked.

---

## ACTIVE HOLDS

### CR090-ROOM — charging code on `main`, disclosure not on devices

**Raised:** 2026-07-27 (AT:R65) · **Blocks:** any Alpha promotion carrying `backend/app/services/room_runner.py`'s surcharge charge

`main` now carries CR090-ROOM (merged at AT:R65, audited COMPLETE r1, zero findings). It debits a
live-data surcharge on every entitled Room run and emits a structural `live_data_notice` SSE event as
the disclosure.

**The disclosure has exactly one delivery channel and it is not on any device yet.** Verified twice,
independently — by the Architect and re-verified by the track-U auditor rather than relayed:

- `mobile/lib/services/api/api_client.dart` and `mobile/lib/state/room_providers.dart` both parse the
  event **only as of CR090-MOBILE**, which is on `main` but **not in any shipped build**.
- The state is **not persisted** — `RoomRun` (`backend/app/schemas/room.py:44-68`) and `RoomRunRow`
  (`backend/app/db/models.py:383-410`) carry `credit_cost` but no live-data field, so a reopened run
  cannot surface it retroactively either.

Promote the backend alone and every Room run costs more with **no explanation anywhere, ever**. That
is CR090's own first acceptance criterion inverted, with a price attached.

**Clear this hold when:** a mobile build containing CR090-MOBILE is in testers' hands (TestFlight +
Play), confirmed by an actual install — not by a green `flutter test`.

**Do NOT clear it by:** reverting the charge, gating it behind a flag nobody flips, or promoting "just
the other files" — the rsync ships the whole tree.
