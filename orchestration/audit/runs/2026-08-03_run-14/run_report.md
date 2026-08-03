# Audit run 2026-08-03 run-14 — CR136-M04, round 3

Auditor track U. Answers round 2's COMPLETE, whose two MINORs were explicitly
non-gating. Both closed anyway.
Audited at **`7d852306`** (code tree `33e0fcd6`) in `.claude/worktrees/audit-m04r3`,
detached and clean.

Verdict: **COMPLETE** — zero BLOCKER, zero MAJOR, zero MINOR.
Findings in `orchestration/audit/cr/CR136-M04.auditor.md`.

## m2 closed — and the complication was the part I left implicit

My round-2 PROBE B, re-run rather than trusted to its new test:

```text
AMI could not measure how many independent bets this book holds over the available window.
AMI could not measure how this book's risk splits across its holdings over the available window.
```

The second line is the finding, gone.

I raised m2 knowing `share_cause` feeds both share-basis blocks from one variable;
I did not work out that a naive branch therefore prints the T/N note **twice** on
the live path. The obvious repair — have the risk branch consult the bets block's
cause — reintroduces exactly the coupling the fix exists to remove, and would have
looked right. `out.toSet().toList()` keeps every branch keyed on its own block.

Live path re-verified: `PROBE A (t_over_n)` prints the shared note once, not twice.

## m3 closed — both round-2 survivors now die

```
AUD-A  bets inversion reverted     r2: 36 passed (SURVIVED)  →  r3: 1 failed
AUD-B  volatility note deleted     r2: 36 passed (SURVIVED)  →  r3: 1 failed
AUD-C  risk_contribution branch removed                          1 failed
AUD-D  dedupe removed                                            2 failed
```

AUD-D's second kill is a **pre-existing** test that had no idea it was going to be
load-bearing — the better of the two. The volatility test's non-vacuity assertion
(the BETA tile is still on screen) is the one I would have missed: without it the
test passes against `_InsufficientState` and proves nothing.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| card suite | 40 passed | **40 passed** | match |
| MUT-H / I / J / K | 1 / 1 / 1 / 2 failed | **1 / 1 / 1 / 2 failed**, same names | exact |
| restored | 40, tree clean | **clean after every mutation** | match |
| `flutter test` | 501 passed | **501 passed** | exact |
| `flutter analyze` | 6 pre-existing infos, 0 errors | **6 issues** | exact |
| backend | 2280, unchanged | **not re-run — diff is mobile-only** | accepted |

The architect's MUT-J self-report (first attempt was a load failure, `+0 -1`, not
a kill — the patch sliced across a method boundary because `final mdd = …` appears
in both `_tiles` and `_notes`) is the right call, and is the same error as this
lane's round-1 QA-C. Recording it is what makes the rest of the table readable.

## Noted, not graded

The dedupe is by **rendered string**, not identity. It collapses the two T/N notes
because they render identically, which holds because every block takes
`n_observations` from the same `common` dict in `_block` — asserted nowhere. A
future divergence would print the same sentence twice with different numbers:
cosmetic, not a false statement, not worth a change today. A coupling rather than
a coincidence.

Third round in which a closed lane's files (M09's) were edited. M09's card suite is
36 → 40 and green so its closure holds; what does not hold is that its verdict
describes the tree anyone runs today.
