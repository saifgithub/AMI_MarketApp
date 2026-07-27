# CR091-STREAKS — closed lane archive (AT:R65, 2026-07-27)

Four CR065-drift CRs delivered as one lane: **CR091** streak badge system · **CR092** 365-day
Marathoner milestone · **CR094** paid-tier streak freezes · **CR096** daily-challenge partial-credit
scoring. Laned together because all four mutate `reputation_service.py` and three touch the same
`POINTS`/milestone constant block — concurrent lanes would have conflicted on every commit.

Audited **COMPLETE round 1** by track U (independent). **One MINOR**, not blocking. Merged to
`main`; full suite **1338 passed** re-verified post-merge from the repo root; `alembic heads` →
single head `d4e5f6a70024`. Worktree + branch reaped.

**Provenance note:** the coder abandoned the lane with no self-report (CR057/P7 — 4th worker
protocol failure in ~26h). The Architect recovered it without touching production code and handed
it to audit with the evidence explicitly labelled unproven. Track U then did the proving —
including mutating `except _AwardRaceLost: return` → `pass` and confirming the DEF049 race contract
is genuinely load-bearing on the **credit** path.

**MINOR carried forward as DEF119** — `freeze()`'s 2/year cap is an unprotected COUNT-then-INSERT.

---

## assign

<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR091-STREAKS — assign (closes CR091 + CR092 + CR094 + CR096)

KIND: code
INSTANCE: coder.api
GATE: independent    <!-- Grants credits (CR092 = 500 bonus credits; CR091 milestone grants) and rewrites the scoring table that drives the shipped weekly league. Money + a retroactive-fairness question on live user data. Same class as CR090-ROOM. -->
ACCEPTANCE: docs/forward_planning/CR091_streak_badge_system/, CR092_marathoner_365day_milestone/, CR094_paid_streak_freezes/, CR096_challenge_partial_credit/ (four CR docs — read all four)
DEPENDS-ON: none. Branch from `main` @ `7111b0c` or later.
HOT-FILES: `backend/app/services/reputation_service.py` (**377 lines, and you own all of it for this lane**), `backend/app/db/models.py` (badge table + migration), `backend/tests/unit/`. NOT `league_service.py` (CR093, unlaned). NOT `main.py` (CR095, unlaned).

## Why these four CRs are ONE lane and not four

They are not merely related — **they mutate the same file, and three of them mutate the same
25-line constant block.** Measured, not assumed:

```python
# backend/app/services/reputation_service.py:42-64
POINTS: dict[str, int] = {
    "challenge_attempted": 2,      # ← CR096 rewrites these two
    "challenge_correct": 3,        # ←
    ...
    "streak_7": 10, "streak_30": 25, "streak_100": 50,   # ← CR092 adds streak_365
}
STREAK_MILESTONES: tuple[int, ...] = (7, 30, 100)         # ← CR092
STREAK_CREDITS: dict[int, int] = {7: 5, 30: 25, 100: 100} # ← CR092
```

Plus `award()` (line 114) and `streak()` (line 233) — CR091's badge award hook and CR094's freeze
logic respectively, both in the same class.

Four concurrent lanes would conflict on every commit. Four sequential lanes would cost four audit
round-trips for one 377-line file. **One lane, four CR IDs.** Same reasoning CR100 used for the three
mobile halves, and it audited COMPLETE round 1.

**You must update all four row files at hand-off** — `docs/forward_planning/_registry/CR091.row.md`,
`CR092.row.md`, `CR094.row.md`, `CR096.row.md` — then `./backend/.venv/bin/python
scripts/registers/gen_registers.py gen cr` and `verify all`. **Never hand-edit `cr_list.md`** (CR081);
it is generated. **Never edit a row by `split("|")` index** — rows can contain an escaped `\|` inside a
code span which shifts every cell; a healthy row is **8** raw cells, check before and after.

## What each CR is

Read the four CR docs for the full text. Summary, and all four already carry Saiful's "build it":

- **CR091 — streak badge system.** `daily_and_streaks.md` promises named badges (Week One /
  Month Strong / Centurion / Marathoner); no badge table, model or service exists — only the credit
  grants fire. Build the badge table + award-on-milestone wiring for the three existing milestones
  (7 / 30 / 100).
- **CR092 — the 365-day "Marathoner" milestone.** Badge + permanent profile flair + **500 bonus
  credits**. Needs CR091's plumbing, which is why they share a lane.
- **CR094 — paid-tier streak freezes.** Floor Manager perk, **2 freezes/year**, pauses the streak for
  a day. Streak currently derives purely from activity-day runs (`streak()`, line 233).
- **CR096 — daily-challenge partial credit.** Spec's 3-outcome table (**right +5 / close +2 /
  wrong-but-tried +1**) vs the code's 2-outcome dict (`challenge_attempted: 2` /
  `challenge_correct: 3`). Both shipped values are also wrong against spec — this is a numeric
  reconciliation, not just a missing middle tier.

## Architect decisions — settled, do not re-open

**D1 — `award()`'s DEF049 race contract is load-bearing. Do not refactor it.**
`award()` carries `_AwardRaceLost` (line 67) — an internal signal that a call lost the concurrent
insert race for its `(user, event_type, ref_id)` and rolled back **having written no row**, raised
only when the caller opts in via `_raise_on_race` (the milestone path) so it can skip its follow-on
credit grant. Every other caller keeps the plain return-0 contract. Badge awards (CR091) and the 500
credits (CR092) are **exactly** the double-grant risk that machinery exists to prevent. Route new
grants through it; do not invent a parallel path and do not "simplify" the two contracts into one.

**D2 — Badges award exactly once, ever, and are idempotent under replay.**
Same guarantee as the existing milestone grants (`event_type=f"streak_{milestone}"`,
`ref_id=f"streak-{milestone}"`, line 305). A user who hits 100 days, loses the streak, and climbs to
100 again does **not** get a second Centurion badge or a second credit grant. Test the replay directly.

**D3 — CR096 changes future awards only. Do NOT retro-score existing rows.**
Points are awarded at event time and stored. Rewriting `POINTS` must not trigger any backfill,
recompute, or migration over historical `reputation_events`. Users' existing totals stand.
**Flag, don't fix:** this does shift the shipped weekly league's scoring mid-season — surface it as a
FLAG for Saiful (below), don't design around it.

**D4 — A freeze is a recorded, countable artifact, not a gap in a derivation.**
CR094's 2-per-year allowance can only be enforced if each freeze is a row you can count. Do not
implement it as "tolerate one missing day in the streak scan" — that is unbounded, unauditable, and
silently gives every user infinite freezes. Persist a freeze record with the consuming user + date,
and derive both the streak and the remaining allowance from it.

**D5 — The freeze is a paid perk and must fail loudly when unentitled.**
Floor Manager only. A non-entitled user attempting a freeze gets an explicit refusal, never a silent
no-op that looks like it worked (CR040 "degrade loudly"; DEF059 is what silent-success costs). Use the
existing entitlement seam — `entitlements.effective_plan_for_user` — not a hand-rolled plan check.

## Acceptance

1. **Full backend suite green from the repo root**, absolute venv path, foreground:
   `./backend/.venv/bin/python -m pytest backend/tests/unit/ -q` — currently **1332 passed** on `main`,
   ~170s. Never bare `pytest`, never `cd backend` first; worktrees have no `.venv` of their own.
2. **Migration is single-head.** New tables need a migration and the head must not fork.
3. **Idempotency tested by replay, not by assertion** (D2): award twice, assert one row and one grant.
4. **The unentitled freeze path is tested** (D5) and refuses visibly.
5. **No backfill** of historical reputation rows (D3) — say so explicitly in the hand-off.
6. Config-driven settings, if you add any, are forwarded in `docker-compose.yml`'s `api-alpha` block —
   `backend/tests/unit/test_config_compose_parity.py` fails the build otherwise. DEF038 and DEF063
   were each dark for months for want of that one line.

## Working rules — read these, three lane workers have died in 24h

- **Create your own worktree and work in it** (`DISPATCH_PROTOCOL.md` §183) —
  `.claude/worktrees/coder.api-CR091-STREAKS`, branch `lane/CR091-STREAKS.coder.api`. **The
  CR090-MOBILE worker skipped this and branched inside the shared `main` checkout**, which put the
  Architect's own commits onto its lane branch. Do not repeat it.
- **Commit incrementally.** Two of three deaths were budget caps, and CR090-ROOM's worker died with
  the **entire lane uncommitted** — zero commits, the only copy dirty files in a worktree, recovered
  by hand. Commit every meaningful step so a cap costs you the last step, not the lane.
- **Never background a command and then emit your final message** (CR057 / failure_patterns P7). Wait
  for the suite in the foreground and report its real exit code.
- **Pathspec-commit only** — `git commit -m "…" -- <files>`. Never `git add -A`, `-am`, or bare.
- Report what you measured, not what you expect. An honest "not verified" costs far less than a claim
  that doesn't reproduce — the auditor is told to weight self-reports sceptically.

## FLAGS — raise, don't decide

1. **CR096 shifts the live weekly league's scoring mid-season.** Challenge points feed the shipped
   CR004 league (promote/relegate). Changing `challenge_attempted` 2→1 and `challenge_correct` 3→5
   mid-week means users competing this week are scored on two different tables. Options are: land it
   at a week boundary, or accept the discontinuity. **Saiful's call, not yours.**
2. **"2 freezes/year" — which year?** Calendar year, rolling 365 days, or subscription anniversary?
   They differ materially for a user who subscribes in December. Pick the one you can defend, state
   it in the hand-off, and flag it.
3. **CR092's "permanent profile flair"** is a mobile surface. This lane is backend-only — expose the
   flair on the profile response and flag that the client half is unlaned, so it does not become
   another shipped-but-dark contract (the CR100 class: three backends live, client read none of them).

---

ASSIGNED: coder.api round 1
DISPATCH: ACCEPTED (round 1)

---

## coder hand-off

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

---

## architect bridge

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

---

## auditor verdict

<!--
CR091-STREAKS.auditor.md — auditor lane file (track U owns). State derives
from round numbers here vs CR091-STREAKS.architect.md (see PROTOCOL.md).
-->

# CR091-STREAKS — audit lane (auditor)

**Item:** four CR065-drift CRs delivered as one lane — streak badge system (CR091), the 365-day
Marathoner milestone (CR092), paid-tier streak freezes (CR094), daily-challenge partial-credit
scoring (CR096). All mutate `reputation_service.py` (three touch the same POINTS/milestone
constant block).

**Gate:** independent — grants credits (CR092's 500-credit bonus, CR091's milestone grants) and
rewrites the scoring table feeding the shipped weekly league.

**Audited SHA:** `f57db61`, off `main` @ `86f9746`. **Provenance:** the coder abandoned the lane
with no self-report (the CR057/P7 pattern the task body explicitly forbade). The Architect
recovered it — measured the suite, read source against D1–D5, wrote the hand-off. No production
code changed during recovery. There are no coder claims here, only Architect claims, explicitly
self-described as unproven: *"nothing in this lane has been mutation-tested... every D-rule is
plausible, not proven."* Audited in an isolated worktree
`.claude/worktrees/audit-CR091-STREAKS/`, own venv.

## Round 1

### Reproduced independently

| Check | Result |
|---|---|
| Scope | `git diff 86f9746 f57db61 --stat` — 8 files, **+563/−43**, exact match. |
| Full suite | `.venv/bin/pytest tests/unit/ -q` — **1338 passed** (baseline 1332 + 6), matching the Architect's measurement exactly (175–200s across two runs). |
| Migration | `alembic heads` → single head `d4e5f6a70024`. `alembic history` confirms the linear chain onto CR026's prior head. |
| Compose parity | Grepped `reputation_service.py` for `settings.*` — the one hit (`reputation_daily_cap`) is pre-existing, confirmed absent from this diff. `test_config_compose_parity.py` → 3 passed. No new env-driven setting introduced. |

### D1 — the DEF049 race contract — mutation-tested, confirmed load-bearing

Read `award()`'s `_raise_on_race` mechanism and `_grant_milestone`'s wiring in full: badge award
and credit grant both happen strictly after `award(..., _raise_on_race=True)` returns without
raising; a lost race raises `_AwardRaceLost` and `_grant_milestone` returns immediately, skipping
BOTH — not two independently-gated paths that could diverge.

Mutated `except _AwardRaceLost: return` → `... pass` (the realistic regression that lets
badge+credits fire anyway on a lost race). Exactly `test_streak_milestone_credit_not_double_granted_under_race`
failed (`credit_balance == 10`, a genuine monetized double-grant). **No badge test failed** —
`_award_badge`'s own internal existence-check (documented "defense-in-depth, not the primary
guard") independently caught the double-badge even with the outer guard broken, while credits
(no equivalent inner check) leaked through — confirms both layers are genuinely load-bearing.
Reverted; suite re-confirmed clean.

### D2 — idempotency across a real streak loss + reclimb

`test_badge_not_double_awarded_on_replay` already exercises the harder case directly: a genuine
7-day climb → badge+credits fire → a 20-day gap (`current == 0`, confirmed genuinely lost, not
re-derived) → a fresh reclimb → exactly one badge ever, no re-grant. `ref_id =
f"streak-{milestone}"` is deterministic and milestone-number-only (not date-keyed), so
replay-safety holds by construction regardless of when the milestone is re-reached — confirmed
by reading, not assumed.

### D3 — no retro-scoring

Grepped `reputation_service.py`/`daily_challenge.py`/`league.py`/the new migration for
`backfill`/`recompute`/`retro`/any `UPDATE` on `reputation_events` — only the self-referential
doc comment. `award()` is INSERT-only; CR096's rewritten `POINTS` only ever apply to rows
written after this lane ships.

### D4 — the freeze cap: sound design, one MINOR unprotected race

Read `freeze()` in full: the 2/year cap is a `SELECT COUNT(*)` immediately followed by an
`INSERT` — no `SELECT ... FOR UPDATE`, no constraint spanning "count of rows per user per year."
The only DB constraint is `UNIQUE(user_id, frozen_date)` — prevents re-freezing the *same* date,
does nothing for two *different* dates requested concurrently.

Attempted a direct reproduction: seeded one legitimate freeze, opened two separate uncommitted
sessions, called `freeze()` on each for different new dates before either committed. Result:
**inconclusive** — SQLite's coarse file-level write lock threw `database is locked` on the
second insert, an artifact of the *test engine*, not the *application code*. Both calls did get
past the stale COUNT check before either committed (the race window is real at the code level);
only SQLite's locking — absent the same way under Postgres's default READ COMMITTED, the actual
production engine — stopped the double-insert here. Cannot conclusively prove the exploit on
Postgres without a live instance (unavailable — Mac is a pure editor). Reported as
structurally-reasoned, not mutation-confirmed — weaker evidence than the other findings here,
stated as such.

**Severity: MINOR** — real, worth fixing, but narrow blast radius (no money/credits, requires
genuinely concurrent requests, worst case a few extra streak-freeze days/year on a paid tier —
not security/safety/compliance). Recommend `SELECT ... FOR UPDATE` on the count query, or an
equivalent serializing constraint, as a follow-up.

### D5 — unentitled refusal is visible

`freeze()` checks `effective_plan_for_user(user.id) != Plan.FLOOR_MANAGER` (the canonical
resolver, not a hand-rolled comparison), returns a typed `FreezeResult(False, "not_entitled", 0)`.
`league.py`'s `POST /streak/freeze` maps every non-ok reason to an explicit HTTP error
(`_FREEZE_REASON_STATUS`: 403/409) — never a silent 200. Matches D5/CR040/DEF059 exactly.

### Scope review — league.py/daily_challenge.py, flagged unreviewed by the Architect

Read both diffs in full. `league.py` (+66) adds exactly the two endpoints needed to make the new
service methods reachable at all (`GET /badges`, `POST /streak/freeze`) — without them this
lane's backend work would itself be shipped-but-dark (this project's own CR100/DEF038/DEF063
lesson). In-scope, not creep. `daily_challenge.py` (+13) is the mechanical CR096 single-award
change. The two small test-file diffs are correct point-value/single-award adaptations, nothing
suspicious.

### FLAGS — Saiful's calls, one sub-question answered factually

1. CR096 mid-season league scoring shift — recorded, Saiful's call.
2. Which "year" the freezes reset on — confirmed via code: `period_key = str(target_date.year)`,
   i.e. **calendar year**, not rolling 365 days or subscription anniversary. Recording the fact.
3. CR092's permanent flair — **confirmed exposed on the backend contract**
   (`GET /v1/league/badges`'s `is_permanent_flair` field). Mobile-rendering half remains unlaned
   per the hand-off — Saiful's call, not a backend gap.

### Findings

1. **MINOR** — `freeze()`'s 2/year cap enforced by an unprotected COUNT-then-INSERT, no row lock
   or spanning constraint. Reproduction inconclusive on SQLite (test-engine artifact);
   structurally reasoned as exploitable under Postgres. Narrow blast radius.

### Verdict

**VERDICT: COMPLETE (round 1)** — zero BLOCKER, zero MAJOR. All five D-rules independently
verified: D1 mutation-confirmed genuinely load-bearing; D2/D3/D5 confirmed by reading plus
existing comprehensive tests; D4 sound in design with one MINOR unprotected-race caveat, honestly
reported as reasoned rather than mutation-proven given the SQLite/Postgres isolation-model gap.
Scope review found the flagged league.py/daily_challenge.py deltas correctly in-scope. One MINOR
finding, not blocking.

Run report: [`../runs/2026-07-27_run-63/run_report.md`](../runs/2026-07-27_run-63/run_report.md)
