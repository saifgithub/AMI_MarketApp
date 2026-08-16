<!--
R70-LEDGER.auditor.md — audit lane. State derives from round numbers here vs
R70-LEDGER.architect.md.
-->

# R70-LEDGER — audit (auditor → architect)

## VERDICT: COMPLETE (round 2)

0 MAJOR, 1 MINOR, 0 BLOCKER.

MAJOR-1 is fixed in full — **all four mutation rows reproduce exactly as
printed**, including the one that was invisible to all 4,312 tests last
round. MAJOR-2's material half is fixed. MINOR-1 is fixed. The one MINOR
below is the half of MAJOR-2 you pushed back on: the push-back's evidence
does not reproduce at the submitted SHA, and I found the mechanism that
explains both readings.

Audited `e10a112f` in `.claude/worktrees/audit-R70-r2-u66`. Verified
independently that `353cb66a` and `0716d098` are register-row-only —
`git diff --stat e5cbdcb8..0716d098 -- backend/` and
`0716d098..353cb66a -- backend/` are both empty — so `e10a112f` is the only
code between rounds, as claimed.

---

## MAJOR-1 — fixed, and the diagnosis under it is the valuable part

Four mutations, each applied alone to real source, file run, source restored
and `git status` confirmed clean between each:

| mutation | claimed | measured |
|---|---|---|
| `_held_quantity` gate deleted (`sim_engine.py:2851`) | `::test_the_sweep_refuses_a_lot_the_holdings_table_no_longer_carries` — 1 failed, 10 passed | **identical** ✓ |
| per-lot `lot_left` skip deleted (`:2840`) | `::test_a_dead_lot_is_not_swept_along_when_the_live_lot_stops_out` + `::test_the_live_lots_own_stop_still_fires_after_a_re_entry` — 2 failed, 9 passed | **identical** ✓ |
| `_event_stream` dates the self-close to `opened_at` | `::test_a_sell_between_the_open_and_the_stop_out_is_credited_to_the_lot` + `::test_the_reconstruction_does_not_report_an_oversell_against_itself` — 2 failed, 2 passed | **identical** ✓ |
| `expected()` back to `Σ open buys − Σ open sells` | `::test_the_detector_finds_no_phantom_after_a_partial_sell_then_a_stop_out` — 1 failed, 39 passed | **identical** ✓ |

Every failing test name matches what the runner printed for me. Row 3 is the
one that matters most: last round that exact revert reproduced the real
symptom and **the entire 4,312-test suite stayed green**. It now dies on two
tests in 0.58s.

**The diagnosis is better than the fix.** *"CR189 made the gates redundant
with the arithmetic, so every scenario test was protected twice and none of
them could go red. A test two mechanisms both satisfy cannot tell you whether
either still works."* That is exactly what I measured from the other side —
five reverts, one test ever firing — and it is a sharper statement of the
problem than my finding was. Each gate now has a scenario only it can
protect: the `_held_quantity` gate reachable only when the two sources
genuinely disagree (which is the phantom condition, hence its own per-test
exemption, correctly the marker's first category), and the per-lot gate
pinned on being *swept along* rather than on dragging the blend.

**Turning the finding into an assertion was the right move.**
`test_the_open_total_is_the_same_either_way_which_is_why_it_is_not_the_guard`
pins `open_quantity(...) == 10.0` on the two-lot sequence — the exact probe I
built — with a docstring saying why the aggregate cannot express this fix.
The next person reaching for it finds the finding where they will look
instead of in an audit file. **P24** is the right generalisation, and filing
it jointly with CR188's mirror-image error (claiming an absence of coverage)
is the correct scope: both are *a mutation claim written from reading the
code, never from running the mutation*.

Reporting the three suite runs including the red one, rather than only the
green, is the same discipline and I want it on the record.

## MAJOR-2 — the material half is fixed

`test_def120_blocking_io_fix.py`'s marker is deleted, and the replacement
comment records the history rather than the old false claim ("no trades, so
there is no ledger claim here either"). Verified: **4 passed** without it.
That was the half that mattered — the only test in the suite driving a real
buy through `/v1/sim/submit` and `SimEngine.submit` across a thread hop is no
longer exempt from the guard that would notice if that path ever diverged.

The count correction is accepted and your framing of it is right: **it is
still 8**, one whole-file marker removed and one per-test decorator added,
and calling that a reduction would have been the same convenient arithmetic.
The warning about `grep -rln` now returning 9 because def120 still names the
marker in a comment is a good catch and saved me a re-derivation error.

## MINOR-2 — the `test_def215_schema_ownership.py` push-back does not reproduce

You quote:

```
$ pytest tests/unit/test_def215_schema_ownership.py -q          # marker removed
E   sqlalchemy.exc.OperationalError: … no such column: sim_holdings.split_adjusted_at
6 passed, 6 errors in 1.94s
```

At `e10a112f` I cannot produce that, by any of three routes:

| how the marker was removed | result |
|---|---|
| `pytestmark = []` | `6 passed` — **0 errors** |
| the `pytestmark` line deleted outright | `6 passed` — **0 errors** |
| removed, **full suite** | `4319 passed, 4 skipped`, exit 0 — **0 errors, 0 failures** |

That last figure is your own round-2 baseline exactly, so the marker's
removal changes nothing at suite scale either.

**The mechanism, which explains both readings.** `fresh_db_url` rebinds the
global engine to the module's own sqlite file (`reset_for_tests(url)`) and
restores it in `finally: reset_for_tests()`. That teardown runs *before* the
autouse invariant's teardown, so by the time the invariant calls
`get_session()` the engine already points back at the suite's own
head-revision DB. The older-revision database is never the one it queries.
Your reasoning — *a file that stands up older schemas could defeat the guard*
— is sound in principle and would hold if the fixture ordering were the other
way round. It is not, here.

So: the third category you added to the marker description is a defensible
category, but **this file is not an example of it**, and the description now
cites it as one. Low severity — the file touches no ledger rows, so an
unnecessary exemption there silences nothing. Worth correcting because the
description is explicitly written to be the thing a future auditor checks an
exemption against, and it now hands them a wrong answer for this file.

I am closing rather than bouncing: nothing ships wrong, the marker is inert,
and a third round over one harmless marker would be disproportionate against
work that verified this cleanly everywhere else.

## MINOR-1 (round 1) — fixed

`cost_basis_lots.open_quantity(trades)`, called by both the detector and the
invariant that guards the detector. The docstring earns the one-line
function. Verified in the conftest diff: the invariant now imports
`open_quantity` rather than re-writing the sum.

---

## Suite

`4319 passed, 4 skipped, 13 warnings`, exit 0 at `e10a112f` (measured with
def215's marker removed; identical to your clean baseline, since that removal
changes nothing). Up 7 from round 1's 4,312 — the four new DEF319 tests, the
two new DEF316 tests, and the open-total pin.

Your note on the intermittent `test_sim_reputation` failure is correct and I
hit it independently last round: DEF321, ordering-dependent, in no file this
lane touches.

## What I did not chase

Unchanged from round 1: the Alpha-only measurements (lane split, DEF317's
2,317 phantom shares, `distinct_stops`) need live Postgres on melehost and
are correctly caveated as measured; DEF317 being left alone matches Saiful's
standing DEF305 ruling. I did not re-derive the 24 legitimate divergences
among the invariant's 25 hits individually.
