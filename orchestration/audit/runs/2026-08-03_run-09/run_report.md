# Audit run 2026-08-03 run-09 — CR136-M04, round 1

Auditor track U. Audited at **`c56e2c41`** in `.claude/worktrees/audit-CR136-m04`,
detached and clean at checkout.

Verdict: **AWAITING_FIXES** — 1 MAJOR, 1 MINOR, zero BLOCKER.
Findings in `orchestration/audit/cr/CR136-M04.auditor.md`.

## The lane's own question: keep it

The submission asked to be returned as misallocated if its premise failed, and named
what would falsify it — sufficiency being independently re-checked downstream. It is
not: M06 strips on `sufficient` and never re-derives it, M09 renders card state off the
same flag, M05 never asks whether a metric should exist. Decided once, trusted
everywhere.

## MAJOR M1 — executed, then narrowed

Flutter widget test against the real card, beta insufficient and every other block
sufficient so the card stays populated:

```
cause=benchmark_misaligned   betaTile=no   benchmarkNote=YES
cause=feed_unavailable       betaTile=no   benchmarkNote=no
```

`health_card.dart:376` draws the tile only when sufficient; `:430-434` gates the only
explanation on `== 'benchmark_misaligned'`. A SPY feed outage deletes the tile and puts
nothing in its place.

I first got four silent causes by forcing them into a fixture, then traced which the
engine can actually emit on a populated card: `short_window`,
`dropped_weight_exceeded` and `zero_variance` all set `estimator_cause`, which makes
all four core blocks insufficient at once and routes the card to `_InsufficientState`,
which explains itself and has a documented `default`. Only `feed_unavailable` and
`benchmark_misaligned` fire with the card populated. So the live gap is one cause, not
four — the one the submission predicted. `effective_bets` is clean for the same reason.

MAJOR because it is live (a Yahoo rate-limit on SPY is the ordinary case), because the
enum has no guard in either direction, and because it is the second occurrence of the
DEF210 shape after M09's audit produced the guard for the first.

## MINOR m1 — the contract's teeth have no test

```
MUT-1  _block()'s null-forcing disabled   module suite 39 passed · every CR136 test 285 passed
```

Nothing pins it. §2.1 asked whether the guard is load-bearing or belt-and-braces; the
answer is that it is unprotected either way. No live leak — all nine call sites pass
`None` today — so MINOR.

## Attack 3 — the mutation the submission could not run

Left out of QA because reverting the mock-marks refusal drives the test into a live
provider fetch. Stub the fetch with a pytest plugin and it is clean:

```
guard reverted + network stubbed      1 failed, 38 passed  (test_fabricated_marks_are_refused…)
control: stub applied, guard INTACT   39 passed
```

The control is the load-bearing half — the stub alone changes nothing, so the failure
is the guard's absence. Guard is real and cleanly covered. Worth adding as QA-E.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| module suite | 39 passed | **39 passed, 1.97s** | match |
| full `tests/unit/` | 2269 passed, 13 warnings | **2269 passed, 13 warnings, 294.63s** | exact |
| QA-A / QA-B / QA-C / QA-D | 1 failed, 38 passed each | **1 failed, 38 passed each, all four test names match** | exact |
| restored | 39 passed | **39 passed**, tree clean | match |

## Not graded

Attack 2 (non-contiguous grid → overstated σ) is real and correctly reasoned, and I did
not measure the magnitude either — it wants a number before a verdict, and deserves its
own DEF with the boundary already specified. Attack 5 confirmed from the M06 side
(`InsufficientContextError` unreachable) but it is M06's problem. Attack 6 verified
latent. Attacks 4, 7, 8 read, not executed. DEF211/DEF212 not re-filed.
