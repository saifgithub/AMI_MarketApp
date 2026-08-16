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

New/changed tests: `test_def316_stale_bracket_on_sold_shares.py` (9 → **11**, the two new ones being
the gate guards above), `test_def319_partial_sell_then_self_close.py` (**4, new this round**),
`test_cr189_position_level_brackets.py` (15, in the CR189 lane), `tests/conftest.py::_ledger_invariant`
(autouse, all ~4,300).

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

## Builder's revert-proof QA — **every row below was run, not reasoned**

Round 1's table was reasoned, and three of its four rows were false. This one is pasted out of
`pytest`: each mutation applied to real source, the file run, the source restored and `git diff`
confirmed empty before the next.

| mutation (applied ALONE) | failing test, as the runner named it |
|---|---|
| `_held_quantity` gate deleted from the sweep (`sim_engine.py:2851`) | `test_def316…::test_the_sweep_refuses_a_lot_the_holdings_table_no_longer_carries` — **1 failed, 10 passed** |
| per-lot `lot_left <= 1e-6` skip deleted (`sim_engine.py:2840`) | `::test_a_dead_lot_is_not_swept_along_when_the_live_lot_stops_out` + `::test_the_live_lots_own_stop_still_fires_after_a_re_entry` — **2 failed, 9 passed** |
| `_event_stream` dates the self-close to `opened_at` (pre-DEF319) | `test_def319…::test_a_sell_between_the_open_and_the_stop_out_is_credited_to_the_lot` + `::test_the_reconstruction_does_not_report_an_oversell_against_itself` — **2 failed, 2 passed** |
| `def110_backfill.py::expected()` back to `Σ open buys − Σ open sells` | `test_def319…::test_the_detector_finds_no_phantom_after_a_partial_sell_then_a_stop_out` — **1 failed, 39 passed** across the three backfill/DEF319 files |

- **DEF320**: the invariant is *proven to fail* rather than assumed to — it caught DEF319 on first arming, plus 25 further hits across the full suite, of which 24 were legitimate divergences (splits; hand-seeded fixtures) and are now scoped or exempted **with the reason written beside each**.

## Round 2 — what changed, and the one place I disagree with the verdict

### MAJOR-1 — accepted in full. Four gates, four tests, each red on its own mutation.

The finding is correct and the diagnosis under it is the useful part: **CR189 made the gates
redundant with the arithmetic**, so every scenario test was protected twice and none of them could
go red. A test two mechanisms both satisfy cannot tell you whether either still works.

- **DEF316's `_held_quantity` gate.** Reachable only when the two sources *disagree* — ledger says
  shares are open, `sim_holdings` has none. That is the phantom condition itself, so the test builds
  it by hand and carries `@pytest.mark.allow_ledger_drift` for the marker's own first category. It is
  the only test in the suite that fails on that gate, and it fails on nothing else.
- **DEF318's per-lot gate.** The dead lot cannot drag the blended stop (zero weight), so the damage
  it can still do is being *swept along* when someone else's trigger fires: stamped `lost`, sold
  `min(10, 0)` shares, an exit recorded that moved no shares and no cash, and `expected()` driven to
  −10. Same book as the reported case, price through the LIVE lot's stop rather than short of it.
- **DEF319, both halves, separately.** `Σ quantity_open` is 10.0 fixed or broken, exactly as the
  audit says, so the new tests pin what the aggregate cannot express: the per-lot **realised
  attribution** (−$24.00 fixed vs −$36.00 broken — the sell's $12 is what the old ordering threw
  away) and the **absence of the `cost_basis_oversell` warning** the module was logging about its own
  arithmetic. The detector's half is pinned through `_plan_and_apply` on a book the engine built and
  that is in fact clean; the old formula reports 4 phantom shares there and, under `--apply`, would
  delete four real shares and credit their proceeds.
- A third DEF319 test pins `open_quantity(...) == 10.0` on that sequence **on purpose**, so the next
  person reaching for the aggregate to guard this fix finds the audit's finding as an assertion
  rather than as prose.
- The two scenario tests now say in their own docstrings that they are scenario pins and not guards.

Filed as **P24** in `failure_patterns.md` — *a mutation claim written from reading the code, never
from running the mutation* — with the enforcing check named.

### MAJOR-2 — half accepted. One marker deleted; the other one is load-bearing.

`test_def120_blocking_io_fix.py`'s marker is **deleted**, and the finding is right about why it
mattered: its own comment claimed "no trades, so there is no ledger claim here either", and
`test_submit_trade_through_real_asgi_app_persists_across_thread_hop` POSTs a real buy through the
real ASGI app and `SimEngine.submit` across a thread hop. That comment is replaced with the history.
Without the marker: **4 passed.**

`test_def215_schema_ownership.py`'s marker **stays**, and this is the one place I am pushing back —
with output. The verdict records "6 passed"; the run also produces **6 ERRORs**, in teardown, which
a tail of the pass line does not show:

```
$ pytest tests/unit/test_def215_schema_ownership.py -q          # marker removed
E   sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such column: sim_holdings.split_adjusted_at
6 passed, 6 errors in 1.94s
```

The file's stated reason was exact: it stands up databases at older alembic revisions, and the
invariant's split-adjusted rule queries a column that does not exist there. Not drift being
silenced — the guard cannot **run**. So the fix is the marker's *description*, which is what made
this look wrong: it named two admissible categories and there are three. It now names the third
explicitly, with this file as its example, so the next auditor checking an exemption against the
description gets the right answer from the description.

Count corrected: **8 files, not 7** — seven whole-file plus one per-test decorator — and the
"constructs a phantom on purpose" comment is on `test_def110_backfill.py:193`, not
`test_cr136_backfill.py`.

**After this round it is still 8**, and stating it as a reduction would be the same kind of
convenient arithmetic that produced MAJOR-1. One whole-file marker was deleted (def120) and one
per-test decorator was added (DEF316's holdings-vs-ledger gate, whose subject is the two sources
disagreeing) — **6 whole-file + 2 per-test**. The exemption moved from a file that reaches the
engine and expects a clean ledger to a single test that deliberately breaks it, which is the change
worth having; the count is not.

One trap for whoever re-derives this: `grep -rln allow_ledger_drift tests/` now returns **9** files
excluding conftest, because `test_def120_blocking_io_fix.py` still names the marker in the comment
recording why it no longer carries one. Count `^pytestmark =` and `^@pytest.mark.` separately.

### MINOR-1 — accepted. One function, called twice.

`cost_basis_lots.open_quantity(trades) -> float`. The detector and the invariant that guards the
detector now call it rather than each writing the sum; the docstring says why a one-line function
earns its own name here.

**SUBMITTED: round 2**
