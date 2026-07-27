<!--
Auditor run report — run-63 (2026-07-27, session auditor.core/track U). Round-1
audit of CR091-STREAKS. Audited SHA f57db61 on lane/CR091-STREAKS.coder.api.
Verdict COMPLETE with one MINOR finding. Owner: AUDITOR.
-->

# run-63 (round 1) — CR091-STREAKS badges/freezes/partial-credit → COMPLETE

- **Auditor session:** auditor.core (track U), 2026-07-27.
- **Audited SHA:** `f57db61`, off `main` @ `86f9746`. **Provenance:** the coder produced no
  self-report and stopped mid-lane (the CR057/P7 pattern the task explicitly forbade). The
  Architect recovered the lane — measured the suite, read source against D1–D5, wrote the
  hand-off. **No production code was changed during recovery; there are no coder claims here,
  only Architect claims**, and the Architect's own framing was explicit: "nothing in this lane
  has been mutation-tested... every D-rule is plausible, not proven. Proving them is this
  audit's main job." Audited in an isolated worktree
  `.claude/worktrees/audit-CR091-STREAKS/`, own venv.
- **The item:** four CR065-drift CRs in one lane — streak badges (CR091), the 365-day Marathoner
  milestone (CR092), paid-tier streak freezes (CR094), daily-challenge partial-credit scoring
  (CR096). All mutate `reputation_service.py`.
- **Gate:** independent — grants credits (CR092's 500-credit bonus) and rewrites the scoring
  table feeding the shipped weekly league.

## Verification

### Reproduced independently

Scope: 8 files, +563/−43, exact match. Full suite: **1338 passed** (baseline 1332 on main + 6),
matching the Architect's measurement exactly (175–200s across two runs). Migration: single head
`d4e5f6a70024`, linear chain confirmed via `alembic history`. Compose parity: grepped
`reputation_service.py` for new `settings.*`/env references — zero new ones added (the one hit,
`settings.reputation_daily_cap`, is pre-existing, confirmed absent from the diff itself) —
`test_config_compose_parity.py` → 3 passed.

### D1 — the DEF049 race contract — mutation-tested, confirmed load-bearing

Read `award()`'s `_raise_on_race` mechanism and `_grant_milestone`'s wiring in full: the badge
award AND credit grant both happen strictly after `award(..., _raise_on_race=True)` returns
without raising — a lost race raises `_AwardRaceLost`, and `_grant_milestone` returns
immediately, skipping BOTH the badge and the credits (not two independently-gated paths that
could diverge).

Mutated `except _AwardRaceLost: return` → `except _AwardRaceLost: pass` (the realistic single
regression that would let badge+credits fire anyway on a lost race). Result: exactly
`test_streak_milestone_credit_not_double_granted_under_race` failed (`credit_balance == 10`, not
5 — a genuine monetized double-grant). **Notably, no badge test failed** — `_award_badge`'s own
internal existence-check (documented as "defense-in-depth, not the primary guard") caught the
double-badge independently even with the outer guard broken, while credits (no equivalent
inner check) leaked through. Confirms both layers are genuinely load-bearing, not decorative.
Reverted; suite re-confirmed clean.

### D2 — idempotency across a real streak loss + reclimb

`test_badge_not_double_awarded_on_replay` already exercises the harder case directly (not just
the test name's literal scope): a genuine 7-day climb → streak_7 badge+credits fire → a 20-day
gap (`current == 0`, confirmed genuinely lost, not re-derived) → a fresh 7-day reclimb → asserts
exactly one badge, ever, and no re-grant. The milestone guard's `ref_id = f"streak-{milestone}"`
is deterministic and milestone-number-only (not date-keyed), so replay-safety holds by
construction regardless of when the same milestone number is re-reached — confirmed by reading,
not assumed.

### D3 — no retro-scoring

Grepped `reputation_service.py`, `daily_challenge.py`, `league.py`, and the new migration for
`backfill`/`recompute`/`retro`/any `UPDATE` touching `reputation_events` — the only hit is the
self-referential doc comment. `award()` is INSERT-only for `ReputationEventRow`; CR096's
rewritten `POINTS` values only ever apply to rows written after this lane ships.

### D4 — the freeze cap: countable by design, but a real unprotected race under Postgres

Read `freeze()` in full: the 2/year cap is enforced by `SELECT COUNT(*) FROM streak_freezes
WHERE user_id=... AND period_key=...` immediately followed by an `INSERT` — no
`SELECT ... FOR UPDATE`, no serializable isolation, no constraint that spans "count of rows per
user per year." The only DB-level constraint is `UNIQUE(user_id, frozen_date)`, which prevents
re-freezing the *same* date twice but does nothing to bound the count for two *different* dates
requested concurrently.

Attempted a direct reproduction: seeded one legitimate freeze (used=1, remaining=1), then opened
two separate uncommitted sessions and called `freeze()` on each for two different new dates
before either committed. Result: **inconclusive** — SQLite's coarse file-level write lock threw
`OperationalError: database is locked` on the second insert, which is an artifact of the *test
engine*, not a deliberate protection in the *application code*. Both calls did get past the
stale `COUNT` check before either committed (proving the race window is real at the code level);
only SQLite's locking model — not present the same way under Postgres's default READ COMMITTED
isolation, the actual production engine — stopped the double-insert in this test harness. I
cannot conclusively prove the exploit succeeds on Postgres without a live Postgres instance
(unavailable from the Mac, which is a pure editor per CLAUDE.md), so this is reported as a
structurally-reasoned gap, not a mutation-confirmed one — weaker evidence than the other
findings in this report, stated as such rather than overclaimed.

**Severity: MINOR**, not MAJOR — real, worth fixing (recommend `SELECT ... FOR UPDATE` on the
count query, or a stricter constraint), but narrow blast radius: no credits or money involved,
requires genuinely concurrent requests for different dates within the same open-transaction
window, and worst case is a paying user gaining at most a small number of extra streak-freeze
days in a year, not a security/safety/compliance issue.

### D5 — unentitled refusal is visible

Confirmed `freeze()` checks `effective_plan_for_user(user.id) != Plan.FLOOR_MANAGER` (the
canonical entitlement resolver, not a hand-rolled comparison) and returns a typed
`FreezeResult(False, "not_entitled", 0)`. Read `league.py`'s new `POST /streak/freeze` route:
`_FREEZE_REASON_STATUS` maps every non-ok reason to an explicit HTTP error (403/409) — never a
silent 200 that looks like success. Matches D5/CR040/DEF059 exactly.

### Scope review — `league.py`/`daily_challenge.py`, flagged as unreviewed by the Architect

Read both diffs in full. `league.py` (+66) adds exactly the two endpoints needed to make the new
service methods reachable at all (`GET /badges`, `POST /streak/freeze`) — without them, this
lane's backend work would itself be shipped-but-dark (this project's own established CR100/
DEF038/DEF063 lesson). Judged in-scope, not creep. `daily_challenge.py` (+13) is the mechanical
CR096 single-award change. `test_daily_challenge_attempt.py`/`test_merge_service.py`'s small
diffs are correct point-value/single-award adaptations to pre-existing tests, nothing
suspicious.

### FLAGS (Saiful's calls, not mine to resolve — recorded, one sub-question answered factually)

1. CR096 mid-season league scoring shift — recorded, Saiful's call.
2. Which "year" the 2 freezes reset on — confirmed the code uses `str(target_date.year)` as
   `period_key`, i.e. **calendar year**, not rolling 365 days or subscription anniversary.
   Recording the fact so Saiful decides against reality, not a description.
3. CR092's permanent flair — **confirmed exposed on the backend contract**: `GET
   /v1/league/badges` returns `is_permanent_flair` per badge. The mobile-rendering half remains
   unlaned, as the hand-off states — that's Saiful's call, not a backend gap.

## Findings

1. **MINOR** — `freeze()`'s 2/year cap is enforced by an unprotected COUNT-then-INSERT with no
   row lock or spanning constraint. Reproduction attempt was inconclusive on SQLite (blocked by
   the test engine's own coarse locking, not the app); reasoned as exploitable under Postgres's
   actual isolation semantics. Narrow blast radius (feature-usage cap, not money). Recommend
   `SELECT ... FOR UPDATE` or an equivalent serializing constraint as a follow-up.

## Verdict

**VERDICT: COMPLETE (round 1)** — zero BLOCKER, zero MAJOR. All five D-rules independently
verified (D1 mutation-confirmed load-bearing; D2/D3/D5 confirmed by reading + existing
comprehensive tests; D4 structurally sound in design with one MINOR unprotected-race caveat).
Scope review found the league.py/daily_challenge.py deltas correctly in-scope, not creep. One
MINOR finding, not blocking.
