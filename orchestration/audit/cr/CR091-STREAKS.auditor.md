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
