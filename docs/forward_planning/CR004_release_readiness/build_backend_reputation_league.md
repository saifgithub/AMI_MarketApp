# Build spec — backend: reputation engine, attempts, weekly league (Plans B2/B5/C1/C2)

Part of [CR004](CR004_release_readiness.md). Implementation commits tag `(AT:R<N> CR004)`.
Decisions locked 2026-07-07: D-060 (reputation-only competition). Resolves OQ-007.

---

## Migration `..._0014_reputation_league.py`

`down_revision = "b2c3d4e50013"`. Follow the `<12-hex>_00NN_<name>` convention. New-table precedent: `c7f2a1d30003_bug_reports.py`; column-add precedent: `b3f9d2a80007_users_display_name.py`.

```
reputation_events
  id            Uuid PK
  user_id       Uuid, indexed
  event_type    String            # enum below
  points        Integer
  ref_id        String NULL       # challenge_id / lesson_id / trade uuid / milestone key — dedup anchor
  created_at    DateTime, indexed

daily_challenge_attempts
  id, user_id (idx), challenge_id String, selected_option Int,
  correct Bool, created_at
  UNIQUE(user_id, challenge_id)

leagues
  id Uuid PK, week String(8) 'YYYY-Www' (idx), tier String, created_at

league_members
  id, league_id Uuid FK->leagues (idx), user_id Uuid (idx),
  week String(8),                  # denormalized for UNIQUE(user_id, week)
  points Int default 0, rank_final Int NULL,
  outcome String NULL ('promoted'|'relegated'|'stay'), joined_at
  UNIQUE(user_id, week)

users  + handle String NULL UNIQUE
       + handle_regenerated_at DateTime NULL
       + reputation Int NOT NULL default 0        # backs schemas/user.py:30 at last
       + show_display_name Bool NOT NULL default false
```

ORM rows in `backend/app/db/models.py` (single-file convention, `Uuid`/`JsonB` from `app/db/base.py`, `_utcnow` defaults). Merge service: add all three user-keyed tables to the re-key list in `merge_service.py` (attempts collide on UNIQUE(user_id, challenge_id) → keep adopter's row, drop orphan's, same rule as `lessons_progress`).

## `app/services/reputation_service.py` (new)

- `POINTS: dict[str, int]` — the D-060 table: `challenge_attempted 2, challenge_correct 3, lesson_passed 5, agent_unlocked 10, room_verdict 3, trade_disciplined 2, trade_reviewed 3, streak_7 10, streak_30 25, streak_100 50`. `DAILY_CAP = 25` (env-overridable `REPUTATION_DAILY_CAP`).
- `award(session, *, user_id, event_type, ref_id=None) -> int` — returns points granted (0 if capped/deduped). Logic: dedup on `(user_id, event_type, ref_id)` existence; per-type daily count caps (`trade_disciplined`/`trade_reviewed` ≤3/day); global cap = sum(points today) vs DAILY_CAP, clamp partial. Writes `reputation_events`, increments `users.reputation` and current-week `league_members.points` if member. Same-transaction pattern as `_record_event` (`api/admin.py:71-92`) — caller owns commit.
- `streak(session, user_id) -> StreakInfo` — activity days = date-in-user-tz (`users.timezone`, fallback UTC) union of: `daily_challenge_attempts.created_at`, `lessons_progress.started_at|completed_at`, `journal_entries.created_at` (journal captures room/trade/1-on-1/brief — the spec's "agent interaction"). Returns `{current, longest, next_milestone}`. Milestone crossing → `award(streak_N, ref_id=f"streak-{N}")` + credit grant per [daily_and_streaks.md](../../initial_specs/04_education/daily_and_streaks.md) (7d +5, 30d +25, 100d +100) as a `subscription_events` row `event_type=credits_added, source=app, note=streak_milestone_N`.
- Singleton via module-level `get_reputation_service()` (pattern: `sim_engine.py:770`).

## `app/services/league_service.py` (new)

- `HANDLE_ADJ`/`HANDLE_NOUN` word lists (~40×40, finance/hex flavored: Cobalt, Amber, Vector… Falcon, Ledger, Signal…). `ensure_handle(session, user)` on first league contact; retry on UNIQUE collision; one regeneration allowed (`handle_regenerated_at is None`).
- `weekly_roll(session)` — idempotent, safe to call hourly: if `leagues` rows for current ISO week exist → no-op. Else: (1) finalize prior week — set `rank_final` by points desc, `outcome` = top 5 promoted / bottom 5 relegated / else stay (cohorts <10: no relegation); (2) assemble current week — eligible = users with ≥1 `reputation_events` row in prior 7 days; group by tier (Apprentice→Floor Veteran ladder; new user = Apprentice; move one tier per outcome); shuffle within tier, chunk ≤ `LEAGUE_COHORT_SIZE` (default 30); mint `leagues` + `league_members`.
- `standings(user_id)` — my cohort ordered by points desc with rank, handle, tier, `display_name` only where `show_display_name`. Cached 60s behind the TTL-singleton pattern (`market_data.py` `CachingProvider` precedent), key = league_id.
- Background task: extend the lifespan hook in `main.py:56-64` (`_nightly_audit_trim` precedent) with an hourly `_league_roll_tick` calling `weekly_roll` — container restarts can't miss the Monday 00:00 UTC boundary.

## Route changes

**New `app/api/league.py`** — `APIRouter(prefix="/v1/league", tags=["league"])`, register in `main.py:111-128`. All routes `get_current_user`:

| Route | Returns |
|---|---|
| `GET /standings` | `{league_id, week, tier, ends_at, members: [{rank, handle, display_name?, points, is_me}]}` — 404 `not_in_league` if unassigned |
| `GET /me` | `{handle, tier, reputation, points_this_week, rank, streak: {current, longest, next_milestone}}` |
| `GET /history` | past `league_members` rows (week, tier, rank_final, outcome) |
| `PATCH /handle` | regenerate once; 409 `already_regenerated` |

**`app/api/daily_challenge.py`** — attempt route (`:103-156`): insert `daily_challenge_attempts` first; on duplicate → 200 with stored result + `already_attempted: true` (mobile B5 renders result-of-the-day, friendlier than 409). Award `challenge_attempted` (+`challenge_correct`). Keep the journal write. Extend `GET /today` response with `my_attempt` when authed.

**`app/api/lessons.py`** — on first `quiz_passed` transition: award `lesson_passed`; at the agent-activation insert: award `agent_unlocked`.

**`room_runner.py`** — in the journal-writing `on_complete`: award `room_verdict` (ref_id = run id; the existing `ROOM_DEDUP_*` window plus ref dedup prevents farming).

**`app/api/sim.py`** — `submit()`: if buy has stop AND target and passed mandate check → award `trade_disciplined` (ref_id = trade id). Reset route (`:119-127`): 24h cooldown — portfolio `created_at` < 24h ago → 429 + `Retry-After` (reset recreates the portfolio, so `created_at` IS the last-reset time; no new column).

**`app/api/journal.py`** — outcome/note attach on a trade-type entry whose trade is closed → award `trade_reviewed` (ref_id = entry id).

## Config knobs (`config.py` + `infra/alpha.env`)

`REPUTATION_DAILY_CAP=25` · `LEAGUE_COHORT_SIZE=30` · `LEAGUE_PROMOTE_COUNT=5` · `LEAGUE_RELEGATE_COUNT=5` · `LEAGUE_ELIGIBLE_PLANS=` (empty = everyone during Engagement; set to `trader,floor_manager` at M1 per paywall axis 21).

## Tests (`backend/tests/unit/`, sqlite fixture as usual)

`test_reputation_service.py` — points table, ref dedup, per-type caps, daily cap clamp, streak calc across tz boundary, milestone credit grant fires once. `test_league_service.py` — roll idempotency, cohort chunking, promote/relegate, <10 cohort rule, handle collision retry + single regen. `test_league_routes.py` — standings shape, anonymity (display_name hidden unless opted), 404 unassigned. `test_daily_challenge_attempt.py` — extend: duplicate → `already_attempted`, attempt awards points. `test_sim_engine.py`/route — extend: reset cooldown 429, disciplined-trade award. Target: ~+30 tests.

## Sequencing

1. Migration + models + merge re-key (0.5 session)
2. reputation_service + award call sites + tests (0.5)
3. league_service + routes + roll job + tests (1)
4. daily_challenge attempt rework + streak endpoint + tests (0.5)
5. `/promote-to-alpha` (migration applies via existing pipeline)
