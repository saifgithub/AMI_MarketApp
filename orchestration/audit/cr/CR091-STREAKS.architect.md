<!--
CR091-STREAKS.architect.md — architect/coder submission lane (track R owns).
State derives from round numbers here vs CR091-STREAKS.auditor.md (see PROTOCOL.md).
-->

# CR091-STREAKS — audit lane (closes CR091 + CR092 + CR094 + CR096)

SUBMITTED: round 1

**Item:** four CR065-drift CRs delivered as one lane — streak badge system (CR091), the 365-day
Marathoner milestone (CR092), paid-tier streak freezes (CR094), and daily-challenge partial-credit
scoring (CR096). Laned together because all four mutate `reputation_service.py` and three mutate the
same 25-line constant block at `:42-64`.

Acceptance: the four CR docs under `docs/forward_planning/` (CR091/CR092/CR094/CR096).
Assign (carries **D1–D5** — audit against those): `orchestration/dispatch/lanes/CR091-STREAKS.assign.md`
Hand-off: `orchestration/dispatch/lanes/CR091-STREAKS.coder.api.md`

**Code branch:** `lane/CR091-STREAKS.coder.api` @ **`f57db61`** (off `main`). Scope **8 files, +563/−43**.

**GATE: independent** — grants credits (CR092's 500-credit bonus, CR091's milestone grants) and
rewrites the scoring table feeding the shipped weekly league.

## ⚠️ Provenance — this changes what you should be sceptical of

**The coder produced no self-report.** It ended with *"I'll stop here and wait for the monitor's
completion notification rather than continuing to poll"* — the CR057 / P7 pattern the task body
explicitly forbade — and wrote no hand-off, no row updates, and one non-incremental commit.

The Architect recovered the lane: measured the suite, read the source against D1–D5, wrote the
hand-off and this bridge, and updated the four register rows. **No production code was changed
during recovery.** So: **there are no coder claims here, only Architect claims.** Weight your
scepticism accordingly.

## Audit this hardest — nothing in this lane has been mutation-tested

The Architect established D1–D5 by **reading source and test names alongside a green suite**. That is
materially weaker than the evidence CR090-ROOM and CR100 carried, both of which were mutation-proven
before they reached you. **Every D-rule below is plausible, not proven. Proving them is this audit's
main job.**

1. **D1 — the DEF049 race contract.** `_raise_on_race` is threaded through `award()`
   (`:160,172,258`) and the badge/milestone path opts in at `:439`. Badge awards and CR092's **500
   credits** are precisely the double-grant risk that machinery exists to prevent. Force a lost race
   and confirm **no row and no follow-on grant** — and that the non-opted-in callers still get the
   plain return-0 contract.
2. **D2 — idempotency.** `test_badge_not_double_awarded_on_replay` passes. Break the guard and
   confirm *that* test is what goes red. Then check the harder case the test name doesn't cover:
   user hits 100 days, **loses the streak**, climbs to 100 again — no second badge, no second grant.
3. **D4 — the freeze is countable.** `StreakFreezeRow` (`models.py:738`) has
   `UniqueConstraint("user_id","frozen_date")`. Confirm the 2/year cap is derived from **counting
   rows**, not from a tolerated gap in the streak scan — the latter silently grants infinite freezes.
4. **D5 — unentitled refusal is visible.** Confirm it refuses through
   `entitlements.effective_plan_for_user` and that a non-Floor-Manager gets an explicit refusal, never
   a silent no-op that looks like success (CR040 / DEF059).
5. **D3 — no retro-scoring.** `:55` claims "future-awards-only … no backfill" and no
   backfill/recompute/retro token appears in the service or migration. Confirm CR096's rewritten
   `POINTS` cannot touch historical `reputation_events`.

## Verify independently — the Architect measured only the first of these

```bash
./backend/.venv/bin/python -m pytest backend/tests/unit/ -q   # Architect measured 1338 passed, exit 0 (baseline 1332 on main, +6)
git diff --stat main...lane/CR091-STREAKS.coder.api            # 8 files, +563/-43
```

**Not measured by the Architect, and both are explicit acceptance items:**
- **Migration single-head** — 27 files now in `backend/alembic/versions/`. Check the head doesn't fork.
- **Compose parity** — any new env-driven setting must be forwarded in `docker-compose.yml`'s
  `api-alpha` block or `test_config_compose_parity.py` fails. A green suite is weak evidence none was
  added; check directly. DEF038 and DEF063 were each dark for months for want of that one line.

## Also worth your eye

`backend/app/api/league.py` (+66) and `backend/app/api/daily_challenge.py` (+13) were **not reviewed
by the Architect** beyond the green suite. The assign scoped this lane to `reputation_service.py` plus
the badge tables — judge whether those deltas are in scope or creep.

## FLAGS — unanswered, and they need Saiful not you

The coder never reported, so all three assign FLAGS are still open:

1. **CR096 shifts the live weekly league's scoring mid-season.** Challenge points feed the shipped
   CR004 promote/relegate league; changing `challenge_attempted` and `challenge_correct` mid-week
   means users competing this week are scored on two different tables. Land at a week boundary, or
   accept the discontinuity — **Saiful's call**.
2. **Which "year" do the 2 freezes reset on?** Calendar year, rolling 365 days, or subscription
   anniversary — materially different for someone who subscribes in December. Record what the code
   actually does so Saiful is deciding against reality.
3. **CR092's "permanent profile flair" is a mobile surface.** This backend lane cannot render it. If
   the field ships with no client reading it, that is the CR100 shipped-but-dark class again. Confirm
   whether the flair is at least exposed on the profile response, and flag the client half as unlaned.
