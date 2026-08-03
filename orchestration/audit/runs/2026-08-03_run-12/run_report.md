# Audit run 2026-08-03 run-12 — CR136-M07, round 1

Auditor track U. First independent audit of this module.
Audited at **`c56e2c41`** in `.claude/worktrees/audit-CR136-m07-r1`, detached and clean.

Verdict: **AWAITING_FIXES** — 1 BLOCKER, zero MAJOR, 3 non-gating MINOR.
Findings in `orchestration/audit/cr/CR136-M07.auditor.md`.

## BLOCKER B1 — §5.1 confirmed, and worse than submitted

The submission self-reported this and asked for a grade rather than fixing it
(concurrent lanes on the shared checkout). I reproduced it independently against
the real POST route with the real M06 persistence path, with a control run in the
same file:

```text
POST 1: 200 created=True  id=14f41765-…
soft_delete -> True
POST 2: 200 created=False id=14f41765-…   ← the same id
store.get(returned id) -> None
journal list_for_user -> 0 rows visible, total=0
CONTROL (no delete): store.get -> RESOLVES
```

Every submitted number matched. The `list_for_user` line is new: the journal is
empty, and the route hands back an id into it.

**The escalation — neither spend counter ever advances again.** `daily_used`
counts journal rows; the write always collides; no row is created; the counter is
frozen:

```text
POST 2: created=False daily_used=1 cap=2 trial_used=1 generations=2
POST 3: created=False daily_used=1 cap=2 trial_used=1 generations=3
POST 4: created=False daily_used=1 cap=2 trial_used=1 generations=4
POST 5: created=False daily_used=1 cap=2 trial_used=1 generations=5
POST 6: 429  ← the rate limiter, not the gate
```

Five generations against a cap of two; `trial_findings_used` frozen at 1 of 7.
The only bound is the 5/min limiter, whose own comment says it is explicitly not
the spend control. On the LLM-enabled path that is ~7,200 billed calls per user
per day, reached by an ordinary delete-then-regenerate.

§2.3 deliberately counts soft-deleted rows so a delete does not refund budget.
That decision is right; the collision defeats it by ensuring there is no row to
count.

## Mutations — 9 run, 7 killed

The architect's four, all exact matches:

```
QA-A  counters stop counting soft-deleted rows   1 failed, 33 passed
QA-B  402-before-429 inverted                    1 failed, 33 passed
QA-C  tiles route made to enforce the gate       3 failed, 31 passed  (same 3 tests)
QA-D  append_unique -> append                    1 failed, 33 passed
```

Mine:

```
MUT-E  THE FIX: find_by_dedupe_key skips soft-deleted   34 passed — SURVIVED
MUT-F  the route's deleted-prior guard removed          1 failed
MUT-G  _as_utc dropped, bare astimezone                 34 passed — SURVIVED
MUT-H  rate limiter 5/min -> 5000/min                   1 failed
MUT-I  trial window/budget `and` -> `or`                3 failed
```

MUT-E and MUT-F together are B1's coverage statement: the guard alone is pinned,
the constraint alone is pinned, **their composition is pinned in neither
direction** — nothing notices the defect and nothing would notice the fix.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| module + compose-parity | 34 passed, 1.90s | **34 passed, 1.82s** | match |
| QA-A / QA-B / QA-C / QA-D | 1 / 1 / 3 / 1 failed | **1 / 1 / 3 / 1 failed**, same test names | exact |
| restored | 34 passed | **34 passed**, tree clean | match |
| full `tests/unit/` | 2269 passed, 13 warnings | **2269 passed, 13 warnings, 285.57s** | exact |

Wall-time divergence (467 s vs 286 s) is concurrent-lane noise, as the submission
said; the count is the datum.

## MINORs

- **m1** — §5.3, the daily cap resets with the book. Spec-conformant and tested as
  intended, so not graded a defect; escalated to Saiful as a pricing question,
  because after B1 it is the only remaining path by which "the only limiter on an
  entitled user" does not limit.
- **m2** — §5.4, `portfolio_health_stats` selects every row ever and counts in
  Python, on every gate evaluation. Bounded by the cap only while the cap works.
- **m3** — MUT-G survived: the five-line `_as_utc` hazard comment is pinned by
  nothing. Downgraded after checking the call site — `evaluate_gate` always passes
  an aware datetime, so the guard is defensive against a caller that does not
  exist yet.

## Answered without grading

§5.2 (the tiles route's "never 5xx" is not a guarantee — restate it or enforce it
with a narrow named M04 contract; DEF211 stays deferred), §5.5 (`${VAR:-default}`
handles empty correctly; a typo'd mode crash-loops `api-alpha` under
`restart: unless-stopped`, which is total outage and therefore the loud
direction), §5.6 (the ungated replay is not an entitlement leak — and it is the
one path B1 does not reach), §5.8 (ordering right; `enforce_gate` confirmed sole
producer of 402/429 in the module).

## Round 2 scope

B1 only. The filter is one line; the regression test is the round — it must drive
the real route through real persistence (the `wired` fixture cannot see this,
because `_fake_generate` seeds with `dedupe_key=None`) and must assert the
counter advances, not merely that the id resolves.
