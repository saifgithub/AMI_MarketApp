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

DISPATCH: OPEN
