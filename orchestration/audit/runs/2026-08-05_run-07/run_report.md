# Audit run 2026-08-05 run-07 — CR136-M10, round 2

Auditor track U. Round 1 returned 1 MAJOR (the `--user-id` spot-check valued
days differently from the `--apply` run it precedes). Scope was A1; m1, m2 and
m3 were taken as well.

Audited at **`c654329d`**; both declared files unchanged → `main`.

Verdict: **COMPLETE (round 2)** — zero BLOCKER, zero MAJOR, zero MINOR.
**Lane closed. CR136 is 11 of 11.**

## A1 — re-measured on my own construction, not his regression test

```text
                                    round 1        round 2
spot-check --user-id B (dry run)    10000.00 x5    11000.00 x5
--apply, unfiltered, same days      11000.00 x5    11000.00 x5
AGREE                               False          True
fetch start requested for ZZZ       B's own first  2026-06-01 = _GRID[0]
```

`earliest` now comes from the unfiltered `select(SimPortfolioRow)` while `scope`
gates only ledger retention (`:452-473`). A filtered run also prints its scope
and says the window is run-global (`:648-650`).

## Row 2.8 is not retroactively wrong

`--apply` was always unfiltered, so it always used the correct window: the
defect could only make the *spot-check* wrong, never the data. His live Alpha
re-run under the fix (22 days each side, 0 disagreements, `ledger_priced 0`) is
**his measurement — I could not reproduce it**, since minting an Alpha bearer
token was blocked in this session. The structural half I can check, and it holds.

## Mutations

```text
MUT-1  window from the FILTERED set        1 failed  (the new A1 regression test)
MUT-2  drop the `scope` filter            28 passed  EQUIVALENT — correct, verified in code
MUT-3  cold grid exits 0 again             1 failed
MUT-4  exit 3 on a no-trades run too       1 failed
QA-C   cache re-keyed to `ticker`          1 failed
```

m1's `any(not r.skipped_no_trades …)` is the whole finding — a grid can be empty
because nobody traded, which is a clean no-op. His first version collapsed that
and a shipped test caught it. MUT-3/MUT-4 pin both directions.

Bookkeeping: my first MUT-3/MUT-4 patterns did not match the shipped text, so
both appeared to survive. They were no-ops, not survivals — re-performed
correctly, both die. Recorded because a mutation that silently fails to apply
reads exactly like a passing guard.

## Reproduced

Module suite **28 passed** (was 26); full `tests/unit/` **2320 passed /
285.20s** — exact. m3 verified live: a book with no bars prints
`ledger-priced valuations: 10` plus the `!!` execution-price warning.

## Probes preserved

`m10r2_probe.py`.
