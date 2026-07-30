<!-- lane hand-off — coder.api. CR052. -->
# SIM-DEF166 — hand-off (coder.api)

STATUS: READY_FOR_AUDIT (round 1)

## What I did

Fixed both sites where a clamped close stamps `realised_pnl` on the full requested quantity
instead of the shares `_apply_sell_row` actually sold:

1. **`manual_close`** (`backend/app/services/sim_engine.py`) — now captures `_apply_sell_row`'s
   return value (`sold`) and stamps `realised_pnl` on `sold`, not `row.quantity`.
2. **`evaluate_outcomes`** (DEF110 outcome-liquidation path, same file) — same fix, same pattern:
   `sold = self._apply_sell_row(...)`, then `realised_pnl` computed on `sold`.

Both preserve the pre-existing `p_row is None` edge case by falling back to the full requested
quantity (matches prior behaviour when there's no portfolio row to sell against — unreachable in
practice since `ensure_portfolio` runs upstream, but not touched).

## Tests (acceptance 1–3)

- **New, red-before-fix:** `test_manual_close_clamped_by_holding_realises_pnl_on_shares_actually_sold`
  in `test_sim_engine.py` — buy 5, sell 2 outright, manual_close the original buy (still `quantity=5`
  against a holding of 3). Asserts cash credited for 3 AND `realised_pnl == 30.0` (not 50.0, the
  unclamped answer). Confirmed red against pre-fix code (`50.0 == 30.0` failure), green after.
- **Extended existing clamp test** (acceptance 3):
  `test_a_trade_larger_than_its_holding_sells_only_what_is_there` in
  `test_def110_outcome_liquidates.py` now also asserts `updates[0].realised_pnl == cash_credited - 3*100.0 == 30.0`,
  not just the cash figure it pinned before.

Ran both files plus `test_def110_backfill.py` together: 34 passed.

## Coupling (acceptance 4) — chose a test, not just a comment

Per the instruction to prefer a guard: added
`test_sell_trade_rows_stay_open_forever` to `test_def110_backfill.py`. It buys, sells, forces a
price move that would flip a BUY via `evaluate_outcomes`, and asserts the SELL trade row's status
is still `"open"` afterward — pinning the invariant `def110_backfill.py`'s `expected()` formula
depends on (Σ quantity over status='open' SELL trades). Also left a comment at the actual sell-row
creation site in `sim_engine.py::submit()` (where `SimTradeRow(... status="open" ...)` is built for
a SELL) pointing at both the backfill formula and the new test, since acceptance 4 asked for the
note to live at the sell-row site itself, not only in the backfill.

**Honest caveat:** the test guards "does status stay open" — it does NOT reproduce a scenario where
flipping status would visibly corrupt a backfill run (I worked through a few candidate scenarios;
they either required stacking phantom-bug state on a manual sell, or landed on a case where the
formula degrades safely, i.e. lower phantom count with the flip, not a wrong repair. A test that
exercises the *actual* corruption would need `_plan_and_apply` in the loop and a manufactured phantom,
which felt like it was demonstrating a different, contrived bug rather than the coupling itself).
So: the guard is real and will catch a status-mutation regression, but it is not proof that flipping
status is unsafe in every case — just that nothing today flips it, and if something starts to, this
fails first.

## def110_backfill.py docstring fix (acceptance 5)

Old text: "Exit codes: 0 clean (nothing to do, or applied); 2 if any phantom shares could not be
attributed to a closed trade — that is unexplained drift and wants eyes, not an automatic write."

That's wrong for `--apply`: on exit 2, whatever WAS attributable is still committed — it is not
"not an automatic write," it's a **partial** write. Rewrote to say so explicitly and to point at
the "LEFT IN PLACE" line in the printed plan as the actual signal for what didn't get written.

## Mutation testing (acceptance 6)

Reverted the P&L fix at each site in turn, one at a time, re-ran the site's own new/extended test:

- **`manual_close`** reverted to `row.realised_pnl = round((price - entry) * float(row.quantity), 2)`
  (pre-fix): `test_manual_close_clamped_by_holding_realises_pnl_on_shares_actually_sold` → **RED**
  (`50.0 != 30.0`), as expected.
- **`evaluate_outcomes`** reverted to `t.realised_pnl = round((price - entry) * float(t.quantity), 2)`
  (pre-fix): `test_a_trade_larger_than_its_holding_sells_only_what_is_there` → **RED**
  (`50.0 != 30.0`), as expected.

No GREEN-on-revert surprises to report — both mutations were caught by their respective tests.
Re-applied both fixes after confirming red; current tree has both fixes in.

## Full suite (acceptance 7)

`"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q` from repo root against this
worktree: **1745 passed, 0 failed** (302.72s). Baseline per the lane brief was 1743; this lane
added 2 new tests (the manual_close clamp test, the sell-row-stays-open guard) plus extended one
existing test in place, so 1745 is exactly baseline + 2. No `-x`, exit code read from the
`N passed, M failed` line, not piped through tail/head.

Note: I ran the full suite once in the background *before* doing the mutation-testing pass below,
then killed that run and re-ran it clean afterward — the mutation pass edits and reverts
`sim_engine.py` in place, and I didn't want a stale/racing result. The 1745 figure above is from
the clean re-run against the final, fixed tree.

## Fences respected

Touched only `backend/app/services/sim_engine.py`, `backend/scripts/def110_backfill.py`, and their
test files (`test_sim_engine.py`, `test_def110_outcome_liquidates.py`, `test_def110_backfill.py`).
Did not touch `mobile/`, did not run the backfill script against anything, did not "tidy up" the
permanently-open sell rows.

## Answer to the standing question — do already-written rows carry wrong `realised_pnl`?

**Only if a clamped close has ever actually happened in production**, i.e. a case where a trade's
requested quantity exceeded what `_apply_sell_row` found on the holding at close time (another open
trade or a manual sell already drew the position down before this trade's stop/target hit or its
`manual_close`). That is exactly the scenario `test_only_the_hit_trade_liquidates_partial_position_survives`-
style tests guard, and it's a narrower condition than "any won/lost/closed trade" — most closes are
unclamped (quantity == what's held) and their `realised_pnl` was always correct.

**How to identify affected rows:** for every `sim_trades` row with `status IN ('won','lost','closed')`
and a non-null `closed_price`, the stamped `realised_pnl` should equal
`(closed_price - entry_price) * <shares actually credited to cash at that close>`. That "shares
actually credited" figure isn't stored directly — it has to be reconstructed from the cash delta
around that close, which isn't clean either since a portfolio's cash column doesn't carry per-trade
attribution. The more tractable signal: any user/ticker where **multiple trades on the same ticker
overlapped in "open" status and one of them closed while the other(s) were still open or had already
partially sold** is a candidate — that's the shape of clamp. I did not attempt to write a query for
this; it needs your judgement on whether it's worth a scan given how rare overlapping-trade closes
are likely to have been before today.

## Registers

`docs/defect/_registry/DEF166.row.md` flipped to `fixed`, `docs/defect/def_list.md` regenerated via
`scripts/registers/gen_registers.py gen def`. Row file + regenerated table committed together
(DEF159), pathspec-only, in a separate commit from the code fix.

## Commits (lane branch `lane/SIM-DEF166.coder.api`)

1. `998f5c8a` — the fix + all tests + docstring correction.
2. `f3c7bb85` — register flip (row file + regenerated table only).

Pushed to origin. This hand-off file goes to main directly per the dispatch convention.
