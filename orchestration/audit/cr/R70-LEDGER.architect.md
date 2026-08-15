<!--
R70-LEDGER.architect.md — architect submission lane. State derives from round numbers here vs
R70-LEDGER.auditor.md.
GATE: none used while building. Built inline on track R out of Saiful's 2026-08-15 directive to
investigate the training/game lane split, then his "Put validations to prevent these from happening
in future".
-->

# R70-LEDGER — audit lane (DEF316 · DEF318 · DEF319 · DEF320)

**SCOPE:** chunk — four defects that are one fact going wrong, plus the guard for the family. Not a
CR, so the Definition-of-Done table is not owed here.

**SHA:** `e5cbdcb8` on `main`, pushed to `origin/main`. Three commits carry this lane:
`0c115046` (DEF316 + DEF318), `7556c88a` (DEF319 + DEF320, alongside CR189 — see the note below),
`e5cbdcb8` (DEF321's register row, docs-only).

**`7556c88a` is shared with the R70-CR189 lane and cannot be split.** CR189's blended bracket and
DEF319's FIFO event ordering both land in `cost_basis_lots` / `sim_engine` and were tested together;
separating them after the fact would mean submitting a SHA that never existed. Audit the two lanes
against the same commit and treat the overlap as declared rather than as scope creep.

**depends-on:** none.

---

## What and why

Four defects, three days, one sentence: **a trade row and the shares behind it disagreed.**

| | |
|---|---|
| **DEF316** | A bracket outlived the shares it protected. A ticket SELL reduces the holding, writes its own SELL row, and leaves the BUY row `open` — deliberately, because `def110_backfill.py`'s detector subtracts open sells and closing the buy row would subtract the same exit twice. What was never connected is that row's own stop/target: the sweep would later "stop out" a position sold days earlier, recording the exit twice, driving `expected()` negative into false phantom shares, and showing the user a LOST outcome at **$0.00 realised** (the DEF166 clamp truthfully reporting a close that should not have happened). |
| **DEF318** | DEF316's first gate asked *"is this ticker flat"* — right when the user exited, blind when they re-entered. Measured: sell out of NVDA at $103, re-enter with a stop at **$90**, and at $94 the dead lot's $95 stop fires, liquidating the new position and stamping −$60.00 against the wrong entry. Gate is now per **lot**, off `Lot.quantity_open`. |
| **DEF319** | A partial sell followed by a stop-out double-counted the sold shares in **every** FIFO reader. Two independent causes: `compute_lots_fifo` treated a self-close as a property of the buy at `opened_at` when it is an event at `closed_at` (erasing sells in between — it was logging `cost_basis_oversell unmatched=4.0` about its own reconstruction); and `def110_backfill.py::expected()` was a **second derivation** (`Σ open buys − Σ open sells`) justified in its own docstring as "the same rule `cost_basis_lots.py` already applies". It was not the same rule. |
| **DEF320** | The guard. Three point fixes had not stopped a fourth defect, because a point test only catches the defect it was written for. |

**The premise that hid it** is stated plainly in `cost_basis_lots`' docstring — *"self-closed buys and
sell orders are disjoint records (a self-close never produces a sell row)"* — and is **true of whole
positions and false of partial ones**. Both readers were built on it, so reading either confirmed the
other. Filed as **P23** in `failure_patterns.md`.

## The fix, and the two places it deliberately does NOT collapse

- One derivation: `compute_lots_fifo`'s `quantity_open` now feeds the detector, the engine's bracket
  gates, CR189's blend, the per-lot display, and the test invariant.
- **Both gates stay in `evaluate_outcomes`** (`lot_open` AND `_held_quantity`) because they read
  different sources — the trade ledger vs `sim_holdings` — and a disagreement between them IS the
  phantom-share condition. Collapsing them deletes the signal.
- `_apply_sell_row`'s `h in s.deleted` skip is now a **backstop, not the live guard**, and says so in
  its docstring. Named rather than left for a reader to mis-trust.

## Tests — command and observed output

Run SHA-pinned in a detached worktree at `9c200d27`, per BINDINGS' DEF159 rule (the only delta to
`e5cbdcb8` is DEF321's register row — docs-only, zero backend code):

```
git worktree add --detach .claude/worktrees/promote-97 9c200d27
cd .claude/worktrees/promote-97/backend
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q
```
```
4312 passed, 4 skipped, 13 warnings in 517.64s (0:08:37)
PYTEST_EXIT=0
```

**The 4th skip is `test_config_compose_parity.py:174`** — `infra/alpha.env` is gitignored and exists
only in the main worktree, so the env-file → Settings direction was NOT checked in this run. It was
checked in the shared-tree run of the same suite (3 skips there) and passed. Stated because a skip
count that moves between runs is exactly the kind of thing that gets read as noise.

New/changed tests: `test_def316_stale_bracket_on_sold_shares.py` (9), `test_cr189_position_level_brackets.py`
(15, in the CR189 lane), `tests/conftest.py::_ledger_invariant` (autouse, all ~4,300).

## Real measurement

**Alpha, 2026-08-15, live Postgres.** `sim_trades` holds both lanes since CR109 slice 2; scoped by
`portfolio_id` (DEF269):

| lane | side | status | count |
|---|---|---|---|
| training | buy | open 7 · closed 11 · won 7 · lost 13 | 38 |
| training | **sell** | — | **0** |
| game | buy | closed 3 · open 17 | 20 |
| game | sell | open | 18 |

**Training has never held a SELL row**, which is why none of these was reachable on Alpha before —
all 31 training exits went through `manual_close`/`evaluate_outcomes`, which close the BUY row and
write no sell row. **CR188 slice 2 made ticket-sell the only training exit**, so the path that
strands a bracket became the only path there is. 2 of the 7 current training open buys carry one.

**DEF317 (filed `open`, data-only, not fixed here):** three game BUY rows closed
`2026-08-11 17:12:42–48 UTC` — ~2.5h before DEF269 shipped at `e262c12c` (19:45 UTC) — carry
`realised_pnl 0.00` beside open SELL rows for the same quantity, so `expected()` reads −261.0966 /
−1916.2194 / −139.7594 against holdings of 0. **2,317 phantom shares that do not exist.** That is
DEF269's residue (pre-fix `manual_close` reaching across lanes and selling against the TRAINING
portfolio, which held none of those tickers). Left alone deliberately: CR109's lane, and Saiful's
standing DEF305 ruling is *"leave the data, fix the code only"*.

**DEF318 reproduced live-shape in a probe before fixing** (buy 10 @$100 stop $95 → sell all @$103 →
rebuy 10 @$103 stop $90 → mark $94): `UPDATES: [('fc5b425c', 'lost', -60.0)]`, holdings emptied,
where `fc5b425c` is the DEAD lot.

**DEF319 reproduced through the new guard**, which is how it was found — `holdings=0 expected=-4` on
buy 10 · sell 4 · stop-out, within minutes of the invariant being switched on.

## Builder's revert-proof QA

- **DEF316**: reverting the `_held_quantity` gate turns `test_the_sweep_does_not_stop_out_shares_already_sold` red.
- **DEF318**: reverting the per-lot gate to the per-ticker one turns `test_a_dead_lots_stop_does_not_fire_on_a_later_lots_shares` red while every other test in that file stays green — which is the point of the two non-vacuity tests beside it (`test_a_real_stop_still_fires`, `test_the_live_lots_own_stop_still_fires_after_a_re_entry`): the natural overcorrection disables every bracket in the app and all the *defect* tests still pass. **P21, one step away.**
- **DEF319**: `_event_stream` reverted to the old ordering reproduces `cost_basis_oversell unmatched=4.0` and the invariant fails with `expected=-4`.
- **DEF320**: the invariant is *proven to fail* rather than assumed to — it caught DEF319 on first arming, plus 25 further hits across the full suite, of which 24 were legitimate divergences (splits; hand-seeded fixtures) and are now scoped or exempted **with the reason written beside each**.

## Two things the auditor should push on

1. **Seven files carry `@pytest.mark.allow_ledger_drift`** — seven places the guard does not look. Each was verified as hand-seeding sim rows past the engine, or (in `test_cr136_backfill.py`) constructing a phantom on purpose as its subject. Worth re-deriving independently: an exemption applied to something that DOES reach `submit`/`evaluate_outcomes`/`manual_close` is silencing the alarm, and the marker description says so.
2. **The invariant sums `quantity_open` rather than re-deriving `Σ open buys − Σ open sells`.** That choice is load-bearing: a third implementation written from the same premise would have *agreed with the bug*. If the auditor writes an independent pin, it should not re-derive the formula either.

**SUBMITTED: round 1**
