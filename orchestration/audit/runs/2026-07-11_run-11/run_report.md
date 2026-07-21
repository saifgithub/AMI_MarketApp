<!--
Auditor run report — run-11 (2026-07-11, session AT:U1). Batch audit of the
AT:R54 defect wave, part 1: DEF042 (security), DEF039 (reputation dedup index),
DEF040 (merge league-points recompute). All backend; DEF042 also mobile. One
shared full-suite run + tree-equivalence proof; per-DEF verification below.
Owner: AUDITOR.
-->

# run-11 (round 1) — DEF042 + DEF039 + DEF040 (AT:R54 defect wave, part 1)

- **Auditor session:** AT:U1 (track U), 2026-07-11
- **Audited tip:** `7ebc123` (cumulative: `85ec04e` DEF042 → `2208f99` DEF039 →
  `7ebc123` DEF040, stacked on origin/main). My `HEAD == 7ebc123`.
- **Equivalence:** `git diff 7ebc123..HEAD -- backend/` empty AND
  `git diff 7ebc123..HEAD -- mobile/` empty, working tree clean for both →
  live `backend/`+`mobile/` == committed tip. So pytest/analyze run against the
  main checkout (deps resolved) are valid for the committed SHAs.
- **Shared backend run:** `backend/.venv/bin/python -m pytest tests/unit/ -q`
  (python 3.13.13, sqlite tempfile, Mac pure-editor) → **587 passed**
  (matches the DEF040-tip self-test claim). Each DEF's regression test also
  re-run in isolation (2 passed).

---

## DEF042 — security (`85ec04e`) → COMPLETE

The daily-challenge `answer` + `explanation` no longer leak pre-attempt.

**Source (verified file:line):**
- `schemas/daily_challenge.py` — new `DailyChallengePublic` is a *genuinely
  narrower model*: `from_challenge()` = `cls(**ch.model_dump(exclude={"answer",
  "explanation"}))`, so the giveaway fields are **not attributes on the object**
  — the defense does NOT rely on `response_model` pruning (which a dict-returning
  route could bypass).
- `api/daily_challenge.py` — all **four** read routes converted: `/today` &
  `/by_date` build `DailyChallengePublic.from_challenge(ch)` into the response;
  `/by_id` `response_model=DailyChallengePublic` + returns it; `/all` maps every
  item through it. Grepped: no route declares `response_model=DailyChallenge`;
  `challenge=ch`/`return ch` leak sites gone.
- Post-attempt reveal is safe: the only `MyAttempt(` construction (line 66) is
  inside the `if row:` (already-attempted) block; every `.answer`/`.explanation`
  ref at lines 168–246 is in `POST /attempt` — grading is internal (168), the two
  `already_attempted` returns require `existing is not None` (post-attempt), and
  the final return follows a **recorded** attempt row.
- **Exploit closed:** to learn the answer you must spend your one attempt (the
  row is inserted before the answer is returned), so you can't learn-then-answer.

**Mobile (`85ec04e`):** `DailyChallenge` model drops both fields (declaration +
`fromJson`); `MyAttempt` gains `correctOption`/`explanation` matching the backend
keys; `daily_challenge_card.dart` highlights the correct option only when
`_correctOption != null && i == _correctOption` and shows `_explanation ?? ''`
— **pre-attempt it literally has no answer to render.** `flutter analyze` → 4
pre-existing infos, 0 new (reproduced).

**LIVE (reproduced, LAN-direct to melehost `192.168.20.59:8000`,
`alpha-2026-07-11-2`):**
- `GET /v1/daily_challenge/today` → challenge keys = the public shape, **no
  `answer`, no `explanation`**, `my_attempt: null`.
- `GET /v1/daily_challenge/all` → 183 items, **zero** leaking `answer`/
  `explanation`; item keys = `DailyChallengePublic` exactly. Widened scope
  deployed.

**Finding — M1 (MINOR, non-blocking):** the +1 regression test pins only
`/today`'s public shape; `/by_id`, `/by_date`, `/all` are not pinned by a test.
Same `from_challenge()` backs all four and I verified each in source **and**
live-confirmed `/all` — low risk. Recommend a shape assertion on the other three.

**NEEDS-DEVICE-CHECK:** mobile answered-state render (correct option green +
explanation) after submit and after restart via `my_attempt`.

---

## DEF039 — reputation dedup backstop (`2208f99`) → COMPLETE

**Scope met:** partial unique index `uq_reputation_event_dedup` on
`(user_id, event_type, ref_id) WHERE ref_id IS NOT NULL` on both the ORM model
(`postgresql_where` **and** `sqlite_where` — so `create_all()`-backed tests get
it) and migration `d1e2f3a40015` (`down_revision = c3d4e5f60014`, chains cleanly
onto the CR004-R2 tip). `award()` wraps `session.flush()` in
`except IntegrityError: session.rollback(); return 0`.

**Regression test is real (not tautological):**
`test_award_race_on_dedup_check_is_caught_by_db_index` commits a winner, then
monkeypatches `_already_awarded → False` so the loser's INSERT reaches the DB —
the *only* thing that can make `granted == 0` + single row is the index firing.
Re-run in isolation: passed. (If `sqlite_where` were broken the index wouldn't
exist and the loser would insert → `granted == 3` → test fails. It passes ⇒
sqlite partial index is created & enforced.)

**Rollback blast-radius assessed (the real risk of a whole-transaction
rollback):** `award()` is called in a **dedicated `with get_session() as s:`
block that does nothing but award** in `lessons.py`, `room.py`, `sim.py`,
`journal.py` — rollback there discards only award state. `daily_challenge.py`
shares its session with the attempt row, but `UNIQUE(user, challenge)` serializes
concurrent `/attempt` requests so the award-race can't fire there. Sole
`streak()` caller is `GET /league/me`; a milestone-race rollback would discard a
lazy `ensure_handle` write — benign (idempotent, recreated next call), non-
monetized.

**Finding — O1 (OUT-OF-SCOPE, recommend new DEF):** `_grant_milestone`
(reputation_service.py:281) calls `self.award(..., always_record=True)` then
**unconditionally** grants credits (`user.credit_balance += credits` +
`SubscriptionEventRow`) with no check of `award()`'s return. Under a concurrent
same-milestone race the loser's guard-row insert rolls back (DEF039) yet it still
grants credits → a one-time double credit of a *monetized* currency. This is
**pre-existing and orthogonal** (before DEF039 the same double-credit occurred
*plus* a duplicate guard row; DEF039 is neutral on credits, positive on the
ledger) — NOT a DEF039 regression, so it does not bounce this lane. But it's a
real monetized-currency race worth its own DEF (gate the credit grant on
`award()` returning > 0, or move the credit grant inside award's success path).

---

## DEF040 — merge league-points recompute (`7ebc123`) → COMPLETE

**Scope met + ordering correct:** the DEF040 recompute is inserted *after* both
re-keys — `LeagueMemberRow` conflict-drop (line 239-243) and
`_rekey_all(ReputationEventRow)` (line 246-248) — so it sums the **already
re-keyed** ledger. If the adopter holds a current-week seat it resyncs
`seat.points = sum(reputation_events.points)` over `[week_end(w)-7d, week_end(w))`
— a full resync, correct regardless of which seat survived.

**Week bounds consistent:** `award()` accrues to the seat keyed by
`iso_week(utcnow)` and stamps `created_at = utcnow` (UTC); the recompute sums by
`created_at` within the UTC ISO-week bounds of `iso_week(utcnow)`. An event
accrued to week W has `created_at ∈ [week_start(W), week_end(W))` — matches.

**Regression test pins it:**
`test_execute_recomputes_adopter_current_week_league_points_on_seat_conflict` —
both sides hold a week seat, orphan earns 8, adopter earns 3; post-merge the
single surviving seat is the adopter's with `points == 11` and the ledger sums to
11. Re-run in isolation: passed. Architect's stash-check (fails at `3 == 11`
without the fix) is logically airtight (without the recompute the seat stays at
its pre-merge 3).

**Finding — M1 (MINOR, out of scope):** the same conflict-drop still discards a
**past-week** seat's points on merge (DEF040 recomputes current week only). Past
leagues are settled/historical → low impact; noted, non-blocking. No live merge
exercised on Alpha (architect noted) — acceptable; reproduced in the unit fixture
against a real sqlite merge path.

---

## Verdicts

| Item | SHA | Verdict |
|---|---|---|
| DEF042 | `85ec04e` | **COMPLETE (round 1)** — zero BLOCKER/MAJOR; M1 minor (test-coverage of the other 3 routes); live-confirmed. |
| DEF039 | `2208f99` | **COMPLETE (round 1)** — zero BLOCKER/MAJOR; O1 out-of-scope (milestone credit double-grant, recommend DEF). |
| DEF040 | `7ebc123` | **COMPLETE (round 1)** — zero BLOCKER/MAJOR; M1 minor (past-week seat, out of scope). |
