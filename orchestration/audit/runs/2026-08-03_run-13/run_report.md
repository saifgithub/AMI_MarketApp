# Audit run 2026-08-03 run-13 — CR136-M07, round 3

Auditor track U. Answers round 1's `AWAITING_FIXES` (1 BLOCKER — run-12).
Round 2 (`0b385dc2`) was submitted, superseded before a verdict, and never graded;
B1's fix lives in it, so this run audits the composed result of rounds 2 and 3.
Audited at **`6cbe70bc`** (code tree `46bf51ae`) in
`.claude/worktrees/audit-CR136-m07-r3`, detached and clean.

Verdict: **COMPLETE** — zero BLOCKER, zero MAJOR, 1 non-gating MINOR.
Findings in `orchestration/audit/cr/CR136-M07.auditor.md`.

## The retraction — my round-1 fix was wrong

Round 1 labelled MUT-E "the fix" (add `deleted_at IS NULL` to
`find_by_dedupe_key`). §6 rejects it. I verified the rejection rather than
accepting it: the non-partial constraint with my filter applied, driven through
my own round-1 probe, returns **500** on POST 2. The filter changes which row the
loser is handed; it does not stop the collision, so no row is written, both
counters still freeze, and the user still cannot regenerate.

I derived the fix from where the symptom surfaced. The architect derived it from
the violated invariant — *at most one **live** Finding per user per entry type per
day* — and the partial unique index follows in one step.

## B1 closed — my own round-1 probe, unmodified

```text
POST 2 after delete: created=True, a NEW id, store.get resolves, 1 row visible
counters:            daily_used=2  trial_used=2
POST 3/4/5:          created=False, generations stays at 2   (was 5)
POST 6:              429
```

Five generations became two. POSTs 3–5 are same-day idempotent replays that never
reach the gate — §6.1's self-correction, checked independently.

## Mutations — 8 run, 8 killed

His five re-performed (MUT-1 3 failed, MUT-2 1, MUT-3 1, MUT-4 1, MUT-5 1) plus
three of mine:

```
AUD-1  non-partial constraint + my round-1 filter    500 from the route
AUD-3  partial kept for POSTGRES only, not sqlite    3 failed
AUD-5  counters widened PAST the user                1 failed
```

AUD-3 is the one that matters most: "spelled identically on both dialects" is true
and would still be useless if the suite only exercised one. It does exercise both.
AUD-5 lands on the boundary test §7.3 added before I asked for it.

MUT-2 and MUT-4 are my round-1 MUT-E and MUT-G — both survived round 1 **and** the
architect's own first pinning attempt. His account of why is the most useful part
of the submission.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| gate suite | 36 passed | **36 passed, 1.84s** | match |
| gate + compose parity | — | **39 passed, 2.07s** | — |
| MUT-1…5 | 2 / 1 / 1 / 1 / 1 failed | **3 / 1 / 1 / 1 / 1 failed** | see note |
| restored | 36, tree clean | **tree clean after every mutation** | match |
| full `tests/unit/` | 2285 passed | **2285 passed, 13 warnings, 281.49s** | exact |

Bookkeeping, neither a finding: §7.1's baseline is the gate suite alone (36) while
§3's command was gate + compose parity (34 at round 1) — the quoted command changed
between rounds. And MUT-1 kills 3 for me vs 2 in his block, because m1 added a test
MUT-1 also breaks; the guard is stronger than claimed, not weaker.

## MINOR m4 — the undo refusal is right, the status it becomes is not

`restore()` returning `False` when a live row holds the key is correct and subtle.
But `journal.py:190-192` turns every `False` into 404 `"entry not found"`, and in
this case the entry exists, is owned by the caller, and is refused for a different
reason. Same misdescription class as B1's `portfolio_finding_lost_write_race` log
line, one file over.

MINOR because the UI path is near-unreachable (a 4-second undo snackbar vs a full
regeneration cycle), it is not silent (`journal_providers.dart:183-186` surfaces a
friendly error), and `restore()` has three other `False` paths where 404 is right.

## Accepted without re-litigating

DEF214's deferral (the coupling argument is the right one, and the row file states
the fix, the reason, and what its own round must test), m3 closed by a test that
sets `TZ` itself, §3.4 downgraded to a proposal, §5.7 recorded in the module doc.

## Noted

`0b385dc2` is tagged `DEF214` but fixes B1 and only *files* DEF214 — the register
row is unambiguous (`open`), so nothing is at risk, but the tag points at the wrong
item. And M08's file list moved under this fix: M08 round 1 should be audited
against a tree that includes it.
