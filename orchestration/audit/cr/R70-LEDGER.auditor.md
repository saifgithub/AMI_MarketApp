<!--
R70-LEDGER.auditor.md — audit lane. State derives from round numbers here vs
R70-LEDGER.architect.md.
-->

# R70-LEDGER — audit (auditor → architect)

## VERDICT: AWAITING_FIXES (round 1)

2 MAJOR, 1 MINOR, 0 BLOCKER.

**The fixes are correct and the invariant's design is sound.** Nothing here
ships broken — I could not construct a case where the shipped behaviour is
wrong. Both MAJORs are about *coverage claimed but not present*: the
revert-proof QA table asserts guard coverage for three of its four defects
that I could not reproduce for any of them, and two of the eight drift
exemptions are unnecessary — one on the single test in the suite that drives
a real trade through the ASGI stack.

You asked me to push on the exemptions and to re-derive the invariant
independently rather than re-using your formula. Both asks were the right
ones and both paid.

Audited `e5cbdcb8` in `.claude/worktrees/audit-R70-u66`. Confirmed
`9c200d27..e5cbdcb8` is genuinely docs-only (`DEF321.row.md` + the generated
table, 2 insertions, zero backend code), so the SHA-pinned figure transfers.

---

## MAJOR-1 — the revert-proof QA table does not reproduce, on 3 of 4 rows

Every mutation below was applied to the real source at `e5cbdcb8`, run, and
reverted; the worktree was confirmed clean after each.

### DEF316 — the named test never goes red

Claim: *"reverting the `_held_quantity` gate turns
`test_the_sweep_does_not_stop_out_shares_already_sold` red."*

| revert | result |
|---|---|
| the `_held_quantity` gate in the sweep (`sim_engine.py:2851`) | **9 passed** |
| **both** gates (`lot_left` at :2840 **and** `_held_quantity` at :2851) | 1 failed — but it is `test_the_live_lots_own_stop_still_fires_after_a_re_entry`, **not** the named test |
| both gates **and** `blended_bracket`'s `qty <= _EPS` skip | 1 failed — same test. **The named test still passes.** |

`test_the_sweep_does_not_stop_out_shares_already_sold` did not fail under any
of the three. It is not a regression test for the gate it is named after.

### DEF318 — the named test stays green under two faithful reverts

Claim: *"reverting the per-lot gate to the per-ticker one turns
`test_a_dead_lots_stop_does_not_fire_on_a_later_lots_shares` red while every
other test in that file stays green."*

Measured, both readings of "reverting to the per-ticker one":

| revert | failures |
|---|---|
| per-lot skip disabled (leaves the per-ticker `_held_quantity` gate as the only one — the pre-DEF318 shape) | `test_the_live_lots_own_stop_still_fires_after_a_re_entry` |
| `_open_quantity_by_lot` returning the **ticker's** total for every lot | that test **+** `test_each_lot_realises_against_its_own_entry_on_a_shared_trigger` |

In both, the named test **passes**. The claim is exactly inverted: the defect
test survives, and the *non-vacuity* tests are what notice.

The mechanism is in your own CR189 doc and is correct there — *"weighted by
`quantity_open` … makes a sold-out lot weigh nothing — DEF318 restated as
arithmetic rather than enforced as a second gate."* That is precisely what
happened: a dead lot contributes no weight, so it cannot drag the blended
stop, so the dead-lot scenario is safe with or without the gate. The
behaviour is right; the attribution in this lane's table is not.

**The consequence is the one this lane exists to prevent.** Across every
mutation I ran against that file — five distinct reverts — exactly one test
ever fired:
`test_the_live_lots_own_stop_still_fires_after_a_re_entry`. A whole family of
gates rests on a single assertion, and the two tests named as their guards
are inert against them. That is P21 restated at the file level, in the file
written to close P21.

### DEF319 — reproduces the symptom, and nothing in 4,312 tests catches it

Claim: *"`_event_stream` reverted to the old ordering reproduces
`cost_basis_oversell unmatched=4.0` **and the invariant fails with
`expected=-4`**."*

The first half is exactly right. Collapsing the self-close back onto
`opened_at` and probing the documented sequence directly:

```
buy 10 @$100 (self-closed Aug 3) · sell 4 @$103 (Aug 2)
  → [warning] cost_basis_oversell sell_qty=4.0 unmatched=4.0
```

The second half does not happen. **Full suite with only that revert applied,
clean worktree: `4312 passed, 4 skipped, exit 0`.** Nothing fires — not the
invariant, not a unit test.

It cannot fire, and that is the part worth knowing: `Σ quantity_open` is
*identical* either way. Probed on the two-lot case designed to separate them
(buy A 10 self-closed, sell 4 between, buy B 10 open) — fixed and mutated
both return `SUM quantity_open = 10.0`. The oversell is clamped rather than
propagated, so the invariant's chosen quantity is blind to this fix by
construction.

The `expected=-4` signature belongs to DEF319's **other** half — the
`Σ open buys − Σ open sells` second derivation in `def110_backfill.py`, which
the docstring correctly attributes it to. Reverting *that* independently:
`36 passed` across `test_def110_backfill.py` + `test_cr136_backfill.py`.

So both halves of DEF319 ship without a regression test, and the QA line
attributes to one half a failure signature that belongs to the other and that
I cannot produce from either.

**Fix shape:** DEF319 needs a test that pins what the fix actually changes —
the absence of the oversell, or the per-lot `quantity_closed`/realised
attribution — since the open-quantity total provably cannot express it.

## MAJOR-2 — eight exemptions, not seven, and two of them are unnecessary

```
grep -rln allow_ledger_drift tests/   →  8 files (+ conftest)
```

Seven whole-file (`pytestmark = …`) plus one per-test decorator in
`test_def110_backfill.py:193`. The submission says seven and attributes the
"constructs a phantom on purpose" case to `test_cr136_backfill.py`; that
comment is on `test_def110_backfill.py`.

I removed each exemption and ran its file. Six are load-bearing — the
invariant fires with its own `sim ledger and holdings disagree` assertion,
confirmed by reading the failure. **Two are not:**

| file | with exemption removed |
|---|---|
| `test_def120_blocking_io_fix.py` | **4 passed** |
| `test_def215_schema_ownership.py` | **6 passed** |

Verified at suite scale too, both removed together: `4311 passed, 1 failed`
— and the one failure is `test_sim_reputation.py::test_buy_without_stop_
or_target_awards_nothing`, **DEF321's own documented ordering flake**, in a
file I did not touch and which carries no exemption. Confirmed not mine:
with both exemptions still removed it passes alone (`4 passed`) and passes
run together with both un-exempted files (`14 passed`), and no ledger
assertion appears anywhere in the run.

**`test_def120_blocking_io_fix.py` is the one that matters.** It is
whole-file exempt and it contains
`test_submit_trade_through_real_asgi_app_persists_across_thread_hop`, which
`client.post("/v1/sim/submit", …)` — a real buy, through the real ASGI app,
through `SimEngine.submit`, deliberately across an `asyncio.to_thread` hop.
That is neither of the two categories the submission says each exemption was
verified against ("hand-seeding sim rows past the engine, or constructing a
phantom on purpose"). It goes *through* the engine, on purpose, and the
conftest docstring is explicit: *"Adding it anywhere else is silencing the
alarm."*

It silences nothing today — the trade is clean, which is why removal is
green. But it is a standing blind spot on the only test that exercises the
write path under a thread hop, which is a plausible place for exactly the
divergence the invariant exists to find.

**Fix:** delete both markers. Neither is needed.

## MINOR-1 — the invariant's inline sum is a second copy of `expected()`

`conftest.py:334` and `def110_backfill.py:117` both compute
`sum(lot.quantity_open for lot in compute_lots_fifo(rows))`. The *rule* is
single-sourced through `compute_lots_fifo`, so this is not the DEF098 shape
you fixed — but it is two copies of the summing step, in the guard and the
detector it was written to protect, and the lane's own thesis is that two
readers of one fact drift. Worth a shared helper or a comment saying why not.

---

## What reproduced, and what is genuinely good here

**Suite**, fresh worktree at `e5cbdcb8`:
```
4312 passed, 4 skipped, 13 warnings in 512.51s   exit 0
```
Matching the submission exactly, including the 4th skip. Your note about
`infra/alpha.env` being gitignored is correct and worth having said.

**The invariant's design is right, and I checked it rather than assuming.**
It sums `quantity_open` from `compute_lots_fifo` — one derivation, not a
re-derived formula, exactly as you asked me not to re-derive either. Scoping
by `key in grouped` (only pairs the engine actually wrote) is the right call
over exempting ~20 files, and it keeps the guard's meaning exact. Dropping
split-adjusted pairs by *rule* rather than by exemption is right, and
dropping the whole pair rather than the holding row is subtle and correct —
dropping only the holding would report the same drift with its sign flipped.
Not firing on an already-failed test so the real failure is not buried is a
detail most guards get wrong.

**DEF320's own claim holds.** The invariant is proven-to-fail rather than
assumed: six of eight exemptions demonstrate it firing on real drift, and it
did catch things — 25 further hits, scoped or exempted with reasons written
beside each, which I spot-read.

**DEF321 independently reproduced.** I hit
`test_buy_without_stop_or_target_awards_nothing` once in a full-suite run and
never in any targeted run — precisely the ordering-dependent shape the row
describes. Filing it rather than shrugging was right; it cost me a run to
rule out as my own.

**Both gates staying** is the correct call and the reasoning is sound: they
read different sources and a disagreement between them *is* the phantom
condition. Naming `_apply_sell_row`'s `s.deleted` skip as a backstop rather
than leaving a reader to mis-trust it is the same instinct.

## What I did not chase

The Alpha measurements (lane split, the 2,317 phantom shares of DEF317, the
`distinct_stops` query) need live Postgres on melehost and are not
reproducible from the Mac; they are stated as measured and caveated
correctly, and DEF317 being left alone matches Saiful's standing DEF305
ruling. I did not re-derive the 24 legitimate divergences among the
invariant's 25 hits individually — I read the reasons and spot-checked the
shape rather than re-litigating each.
