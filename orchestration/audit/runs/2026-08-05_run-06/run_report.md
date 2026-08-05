# Audit run 2026-08-05 run-06 — CR136-M10, round 1

Audited at **`c56e2c41`** — the only one of today's three lanes whose declared
files have zero drift, so the submitted SHA is the right tree.

Verdict: **AWAITING_FIXES (round 1)** — zero BLOCKER, **1 MAJOR**, 3 non-gating
MINOR. Round 2 scope: A1 only.

## MAJOR A1 — the runbook's spot-check validates a different valuation

`earliest` is the minimum first-event date over the portfolios **the run
selected** (`:405-406` filter, `:423-433` loop), and the price window comes from
it (`:468`). `--user-id` narrows the set, moves `earliest` later, shortens the
window, and days the full run carries forward from a real close fall back to
`last_event_price`.

```text
spot-check --user-id B   ledger_priced 5  terminal OK  exit 0   total_value 10000.00
full run   --apply       same five days                        total_value 11000.00
```

Checklist 2.8's acceptance sequence is dry-run → `--user-id` spot-check →
`--apply`, and it was executed that way on 2026-08-06 with the spot-check
recorded as evidence. The step that exists to catch a bad backfill reads
different numbers from the ones that ship, and reports success either way.

## MINOR m1 — empty grid under `--apply` exits 0 and prints `committed.`

Reproduced (`EXIT_CODE = 0`, `ROWS_WRITTEN = 0`). Considered MAJOR for
consistency with M11's A1 and rejected: nothing false is printed — `rows
inserted : 0` is quantitative and true — and the documented contract makes an
empty grid "clean". The exit code is the only misleading channel.

## MINOR m2 — the blocker's regression test does not catch the blocker

`key = (ticker, start) -> ticker` kills only `test_the_price_cache_is_keyed_by_
ticker_and_start`. `test_two_books_sharing_a_ticker_each_get_their_own_early_
history` — whose docstring calls itself "the audit's blocker, with the REAL
provider" — survives, structurally: one `start` per ticker per run.

## MINOR m3 — two silences the plan cannot distinguish

`ledger_priced` gates nothing (six sites, none a branch) while `mismatched`
reaches the exit code; and `_close_on_or_before`'s `(0.0, False)` makes "no bar",
"zero close" and "negative close" the same event at `:324`.

## Reproduced

Module suite **26 passed**; QA-A/B/C/D **1/3/1/1** with every named test
matching; ~20 cited `file:line` anchors all exact but one (`:143-151` → `:142-150`).
The rejected `begin_nested()` variant reproduces exactly — **ten rows written
during a dry run**.
