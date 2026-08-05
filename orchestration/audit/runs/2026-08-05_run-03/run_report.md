# Audit run 2026-08-05 run-03 — CR136-M11, round 2

Auditor track U. Round 1 returned 1 MAJOR (the ship gate could exit 0 having
compared a strict subset). Scope for this round was A1 only; m2 was taken
voluntarily.

Audited at **`3d06da35`** in detached worktree `.claude/worktrees/audit-m11r2`;
both r2 files unchanged `3d06da35` → `main`.

Verdict: **COMPLETE (round 2)** — zero BLOCKER, zero MAJOR, 1 non-gating MINOR.
**Lane closed.**

## A1 — the three round-1 cases, re-run verbatim

```text
                                     round 1        round 2
control: honest payload              exit=0 PASS    exit=0  compared 7 of 7
benchmark dropped                    exit=0 PASS    exit=1  compared 4 of 7
r_squared renamed -> rsq             exit=0 PASS    exit=1  compared 6 of 7
control: sigma_p 0.1pp wrong         exit=1 FAIL    exit=1  compared 7 of 7
```

## The waiver, attacked four ways

```text
--allow-unchecked beta,r_squared,tracking_error   exit=0  names all three
--allow-unchecked beta,r_squared      (2 of 3)    exit=1  fails on tracking_error
sigma_p WRONG + --allow-unchecked portfolio_volatility  exit=1  numeric, unwaivable
--allow-unchecked '*'                             exit=1  no wildcard special case
full payload + --allow-unchecked beta             exit=0  "named, but PUBLISHED: ['beta']"
```

The third matters most: a waiver covers **absence only**. A published metric
that disagrees is compared and fails whatever the flag names, so the waiver
cannot launder a wrong number.

## MINOR m5 — the waiver's distinguishing property is unpinned

```text
AUD-1  surprises = [] if allowed_unchecked else list(unchecked)   6 passed  SURVIVED
```

§A1 claims the waiver "is not a blanket 'allow any subset'". True in the shipped
code — measured above — but `test_an_expected_absence_can_be_waived_by_name`
waives *all* the unchecked metrics, so it passes under a blanket implementation
too. One case waiving two of three and asserting `exit 1` closes it.

Same class, not separately graded: AUD-3 (deleting the stale-allowance print)
also survives; it is a print, so cosmetic.

## Mutations

```text
MUT-1  surprises = []                      2 failed  (reported 2)
MUT-2  surprises = list(unchecked)         1 failed  (reported 1)
MUT-3  FAIL prints, then returns 0         2 failed  (reported 1)
AUD-1  blanket waiver                      6 passed  SURVIVED
AUD-2  harness imports app.trading_math    1 failed
AUD-3  stale-allowance print deleted       6 passed  SURVIVED
```

AUD-2 answers round 1's m1: the independence guard genuinely fires. His choice
to read the **source** rather than `sys.modules` corrects my own round-1 method
— under pytest the whole app is already imported, so a runtime check would pass
regardless.

MUT-1's self-report is the keeper: it killed one test at first because the
renamed-field test was passing for the wrong reason (replacing the whole `beta`
block replaced its value too, so the run failed numerically and never exercised
the rename). A test passing for the wrong reason is what A1 was, one level down.

## m2 — fixed as a docstring, correctly

`_joined_returns` now states it does not mirror M04's order, quotes the measured
divergence (390 vs 252 dates), and records why the divergence is structurally
loud. Realigning the join order mid-fix-round would have been the larger change;
the false statement was the defect.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| gate suite | 6 | **6 passed, 0.51s** | exact |
| full `tests/unit/` | — | **2304 passed, 289.52s** | — |
| MUT-1…3 | 2/1/1 | **2/1/2, names match** | 3/3 killed |

**Not reproduced, attributed:** checklist 2.14 records the rebuilt gate re-run
live on Alpha (2026-08-06, `EXIT=0, compared: 9 of 9`, every diff ±0.0000).
melehost is reachable from here and I attempted an independent re-run; minting
the bearer token the `_own`-guarded route requires was blocked by this session's
permission classifier, so that reading is **track R's measurement, not mine**.

## Probes preserved

`m11r2_probe.py`, `m11r2_mut.sh`.
