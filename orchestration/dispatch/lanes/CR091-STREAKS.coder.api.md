<!-- coder.api lane hand-off — CR091-STREAKS. Architect-recovered; see Provenance. -->
# CR091-STREAKS — coder.api lane (closes CR091 + CR092 + CR094 + CR096)

STATUS: READY_FOR_AUDIT (round 1)

## ⚠️ Provenance — read before auditing

**The coder emitted no self-report at all.** Its final message was *"I'll stop here and wait for the
monitor's completion notification rather than continuing to poll"* — it backgrounded work and ended
its turn without reporting a single test result. That is exactly the **CR057 / failure_patterns P7**
pattern the task body explicitly forbade. It also wrote **no hand-off file** and made **one
non-incremental commit** despite being told to commit incrementally.

**Consequence for you: there are no coder claims to be sceptical of, because there are none.**
Everything below was measured or read by the **Architect** after the fact. Weight the usual
coder-self-report scepticism onto the Architect instead.

The code itself was left complete and green. Nothing was rewritten during recovery — the Architect
added only this hand-off, the audit bridge, and the four register row updates.

**Branch:** `lane/CR091-STREAKS.coder.api` @ `f57db61` (off `main`). Scope **8 files, +563/−43**.

## What was built

| File | What |
|---|---|
| `backend/app/services/reputation_service.py` | +178 — badge awards, 365-day milestone, freeze-aware streak, rewritten `POINTS` |
| `backend/app/db/models.py` | +61 — `StreakFreezeRow` + badge storage |
| `backend/alembic/versions/d4e5f6a70024_badges_streak_freezes.py` | +73, new migration |
| `backend/app/api/league.py` | +66 |
| `backend/app/api/daily_challenge.py` | +13 |
| `backend/tests/unit/test_reputation_service.py` | +207 — 6 new tests |
| `test_daily_challenge_attempt.py`, `test_merge_service.py` | ±8 — existing tests updated for the new `POINTS` values (CR096) |

### New tests (6)

```
test_streak_milestone_awards_badge
test_badge_not_double_awarded_on_replay
test_marathoner_365_day_milestone_grants_badge_flair_and_credits
test_freeze_refuses_visibly_for_non_floor_manager
test_freeze_capped_at_two_per_year_for_floor_manager
test_frozen_day_pauses_streak_without_breaking_it
```

## Architect-measured evidence

- **Full suite from the repo root, absolute venv path, foreground: `1338 passed, exit 0`** (175.96s).
  Baseline on `main` today is **1332**, so +6 — matching the 6 new tests exactly, with no pre-existing
  test lost.
- Worktree clean at `f57db61`; scope reproduced via `git diff --stat main...HEAD`.

## D1–D5 — Architect read the source, did NOT mutation-test

- **D1 (DEF049 race contract):** `_raise_on_race` is threaded through `award()` (`:160,172,258`) and
  the milestone/badge path opts in at `:439` with an in-source comment naming DEF049. Not a parallel
  grant path.
- **D2 (idempotent badges):** `test_badge_not_double_awarded_on_replay` exists and passes.
- **D3 (no retro-scoring):** no `backfill`/`recompute`/`retro` anywhere in the service or the
  migration; `:55` carries an explicit "future-awards-only change (D3) — no backfill over historical"
  comment.
- **D4 (freeze is a countable row):** `StreakFreezeRow` (`models.py:738`, table `streak_freezes`) with
  `UniqueConstraint("user_id", "frozen_date")` — not a tolerated gap in a scan.
- **D5 (unentitled refuses visibly):** `test_freeze_refuses_visibly_for_non_floor_manager` exists and
  passes.

## Claims explicitly NOT verified — treat as unchecked

- **No mutation testing of any kind.** D1–D5 above were established by **reading source and test
  names plus a green suite**, never by breaking the code and confirming a specific test goes red.
  Every D-rule is therefore *plausible*, not *proven*. This is the single biggest gap in the lane.
- **Migration single-head not verified**, and it was an explicit acceptance item. 27 files now in
  `alembic/versions/`.
- **Compose parity for any new setting not verified** — if the lane added an env-driven setting it
  must be forwarded in `docker-compose.yml`'s `api-alpha` block or `test_config_compose_parity.py`
  fails (DEF038/DEF063 were dark for months over exactly that line). The suite is green, which is
  weak evidence none was added, but nobody checked directly.
- **The three assign FLAGS were never answered** because the coder never reported: (1) CR096 shifts
  the live weekly league's scoring mid-season — users competing this week get scored on two different
  tables; (2) which "year" the 2 freezes reset on (calendar / rolling 365 / subscription anniversary)
  — materially different for a December subscriber; (3) CR092's "permanent profile flair" is a mobile
  surface this backend lane cannot render, so it risks becoming another shipped-but-dark contract
  (the CR100 class). **All three still need Saiful.**
- **`league.py` +66 and `daily_challenge.py` +13 were not reviewed by the Architect** beyond the green
  suite — the assign scoped this lane to `reputation_service.py` and the badge tables, so those two
  deltas are worth an auditor's eye for scope creep.
