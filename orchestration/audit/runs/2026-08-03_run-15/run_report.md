# Audit run 2026-08-03 run-15 — CR136-M07, round 4

Auditor track U. Answers round 3's COMPLETE, whose single MINOR (m4) I said was
not worth holding the lane for. Taken anyway.
Audited at **`a0bd3576`** (code tree `1fe9d0d9`) in `.claude/worktrees/audit-m07r4`.

Verdict: **COMPLETE** — zero BLOCKER, zero MAJOR, zero MINOR. **Lane closed.**

## m4 closed

`RestoreOutcome` (`RESTORED`/`NOT_FOUND`/`SUPERSEDED`) splits the four facts
`restore()` used to collapse into one boolean; `restore()` keeps its contract and
delegates, so all seven existing call sites are untouched.

```
MUT-6 (his)  the 409 branch removed                      1 failed
MUT-7 (his)  the surviving 404 branch disabled           1 failed
AUD-6 (mine) SUPERSEDED returned as a silent 204         1 failed
AUD-7 (mine) every refusal becomes SUPERSEDED            1 failed
```

AUD-7 is the mirror defect §8 anticipated — the change could have turned every
failed undo into a conflict. It did not.

All four kill the same single test, which genuinely covers the state space (409 +
code + message, then both reachable 404 paths). Worth saying only because the whole
m4 change rests on one test function — the same observation the architect's own §4
made about QA-B. Not a finding.

## A comment, not the code

The test's comment names three genuine 404 paths — "an id that never existed, an
entry that was never deleted, and another user's row" — and asserts two. The third
is not a 404: `_own` (`journal.py:49-51`) raises **403** before
`restore_with_reason` is reached. The assertions are complete for what the route
can return; the comment would send the next reader hunting for a test that should
not exist.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| pinned command | 40 passed | **40 passed, 2.42s** | exact |
| + journal store | 48 (gate + store) | **51 passed** (37+3+11) | consistent |
| MUT-6 / MUT-7 | 1 / 1 failed | **1 / 1 failed** | exact |
| restored | 37, tree clean | **clean after every mutation** | match |
| full `tests/unit/` | 2286 passed | **2286 passed, 13 warnings, 313.44s** | exact |

§8.2's pinned command, §8.3's MUT-1 correction (kills 3, guard stronger than
claimed) and §8.4's DEF214 tag note are all accepted. The tag gap is worth raising
with Saiful as a convention question — `(AT:R## CR### DEF###)` cannot express
"files" versus "fixes", and it will recur.
