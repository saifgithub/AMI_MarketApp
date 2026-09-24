<!--
RETRO-SIM-OPTIONS.auditor.md — audit lane verdicts. Auditor-owned; the architect never writes here.
Newest round at the bottom. State derives from round numbers here vs RETRO-SIM-OPTIONS.architect.md.
-->

# RETRO-SIM-OPTIONS — auditor verdicts (options simulation + sim order-book defects, retroactive)

## Round 1 — auditor U68

**SHA audited:** `8c43c88e`, in a detached scratch worktree `audit-U68-SEC` per DEF159 (shared
with RETRO-SECURITY — same SHA). Worktree verified clean after every probe and mutation was
reverted. (`8c43c88e..34941fa1` is 12 docs/register files, no source; the backend suite below
ran at `34941fa1`.)

**Tier A.** Position and cash state.

### What is live, measured

- **`SIM_BRACKET_SWEEP_ENABLED=true`** in the running `ami_api_alpha` (and in `~/ami_trade/.env`).
  The lane and the DEF305 register row both say it is still `false`. See MINOR-1.
- Options unexercised in production: current mandates with `derivatives_allowed` true =
  **0 of 52**; `sim_option_legs` 0 rows, `sim_option_trades` 0 rows; `sim_short_positions` 1 row.
- DEF377 census, replicated as read-only SQL on Alpha (the script opens an app session, so I ran
  its predicate as a `SELECT` instead): wrong-side long brackets = **3, all `closed`**
  (historical), **0 active**; wrong-side shorts = 0. The census's exit-0 condition holds.
- DEF309 backfill on Alpha: 5 terminal resting orders, 5 with `retired_at` set.

### MAJOR-1 — DEF368's fix moves option positions into the adopter without their cash or their cover

DEF368 stopped the claim-merge CASCADE from deleting the orphan's option legs by re-keying them
into the adopter's portfolio (`merge_service.py:246-253`, `_rekey_options`). In that same
branch the orphan's **holdings and cash are dropped** with its portfolio — by the existing
"keep the adopter's" rule (`:230-234`, "Holdings get dropped along with the orphan portfolio
cascade"). So the legs arrive without the cash that paid for them and without the shares that
covered them.

`option_leg_value` is `collateral + q × multiplier × mark` (`option_strategy.py:362-380`): the
term exists to balance cash that left at open. Moved without that cash, it is value from nothing.
Driven — orphan holds 100 AAPL + a covered call, and a cash-secured MSFT 50 put ($5,000
collateral); both users have portfolios; `MergeService().execute`:

```
PROBE counts={'sim_trades': 0, 'sim_holdings': 0, 'sim_option_legs': 2, 'sim_watchlists': 0}
PROBE adopter_tv before=10000.0 after=14650.0 delta=+4650.00 adopter_cash_after=10000.0
PROBE adopter AAPL held=0 locked_by_short_calls=100.0 uncovered_by=100.0
```

Two defects in one move:

1. **Phantom NAV** — the adopter's total value rises $4,650 (collateral $5,000 − the two short
   liabilities) with its cash unchanged. Nothing reconciles it.
2. **A naked short call, created by claiming an account** — the call lands locking 100 shares the
   adopter does not hold. That is the one position D3 forbids outright, reached without
   `check_option_open` — a fifth entry into position state that bypasses both floors, which is
   precisely what the lane's attack surface 6 asked me to look for. The margin sweep
   (`force_close_uncovered_calls`) would buy it back at the next market-hours tick, billing the
   adopter's cash for a position they never opened — or leave it open if the chain cannot price
   it.

Before DEF368 the same merge silently destroyed the legs; after it, it silently mints value and
a forbidden position. `test_def368_merge_keeps_options.py` checks the legs moved and the counts
reported — nothing asserts value continuity or cover. Latent today (0/52 mandates permit
derivatives), which is DEF368's own framing of why it mattered: *"the kind of latent loss that
becomes a live incident on the day the flag is flipped."*

**Fix:** whether an adopter inherits the orphan's positions is a product call (Saiful's) — it
already goes one way for shares (dropped) and now the other for options (kept). What is not a
call: a position must not move without its funding and cover. Either drop the orphan's option
legs like its holdings, *disclosed* (the DEF368 complaint was silence, not loss), or carry legs
together with the cash they encumber and the shares that cover them. Guard both invariants after
a merge: adopter total-value delta equals the value carried, and `locked_call_cover_shares ≤
held` per underlying.

### MINOR-1 — the lane and the DEF305 row say the bracket sweep is off; it has been on since 2026-08-26

Flipped deliberately — the checkpoint memo `20260826T111820Z_13fe7252…md:83-85` records Saiful's
ruling (*"SIM_BRACKET_SWEEP_ENABLED=false can be changed at any time. we onky have alpha test
users."*) and promotion `alpha-2026-08-26-1`. The behaviour is authorised; the record is wrong.
It matters for how this lane reads: DEF305's fillability guard, DEF311's orphaned-sell retirement,
DEF312's side check and DEF377's `bracket_hit` refusal are not dormant safeguards, they are on a
money path that fires every 5 minutes. **Fix:** correct the DEF305 row (and this lane's
"Known limits").

### MINOR-2 — DEF357's reachability pin is cited in the wrong file

The table cites `test_cr172_option_lifecycle.py::test_the_production_sweep_reaches_the_lifecycle`.
Removing the `_sweep_option_lifecycle` call (`sim_resting_orders.py:789`) leaves that file
`23 passed`. The pin lives in `test_cr172_option_margin_sweep.py:542`, and against the same
mutation it is red (`2 failed, 15 passed` — also `test_the_lifecycle_runs_with_the_market_shut`).
The guard is real; the citation would send the next auditor to a file that cannot see it (P24).

### MINOR-3 — DEF354's overrun multiple still prints "1.0x" for the case its comment says it fixes

`option_strategist.py:201-210`: the comment says a $9,030 loss on a $9,000 budget must not read as
"exactly the budget", and chooses one decimal under 10x to prevent it — but
`f"{9030/9000:.1f}x"` is `"1.0x"`. The two dollar figures beside it carry the fact, so the
disclosure is not false; the multiple just does not do the job its comment claims. **Fix:** print
the overrun as a percentage below 2x, or always two significant figures. (Attack surface 1's
other half holds: `_size_to_budget` has one call site, `:447`, so every strategy shape sizes
through it.)

### Verified and sound

- **Every function that creates a position row**, enumerated rather than grepped for "floor":
  `_execute_fill` ← `submit` (floor `:1454`), `fill_resting_order` (floor `:1965`),
  `submit_game_trade` (game lane — floor absent by design, `:2132`); `open_structure` ←
  `open_option_structure` (`check_option_open`); `_apply_buy_row` ← `_apply_option_settlement`
  (allow-and-flag via `check_exercise_outcome`, by design: an exercise cannot be refused);
  `open_short` ← `_open_short_fill` (inside `_execute_fill`) / game lane. The merge is the one
  path in position state with no floor — MAJOR-1.
- **Settlement arithmetic, re-derived by hand** (`option_lifecycle.py:169-327`), value continuity
  checked across the event for each: long call exercised (cash −K·100, basis K+premium, NAV
  continuous); short put assigned (cash_delta = collateral − K·100 = 0, basis K−premium,
  continuous); covered call assigned (cash +K·100, premium realised, continuous); long put
  exercised with and without shares (parity cash settlement: realised = intrinsic·100 −
  premium·100). Exercise-by-exception: ITM ≥ $0.01 exercises, $0.0099999 does not. Early
  assignment: short call only, ex-date in `(today, expiry]`, extrinsic < dividend. All correct.
- **DEF356's share-sale door** is left open deliberately, with the reason in `2bae6d0b`'s message
  (no user-initiated close path for a structure, so refusing the sale would trap the user until
  expiry) and the sweep as the backstop. A documented decision, not a gap.
- **Mutations, mine, each reverted:** DEF357 lifecycle call removed -> `2 failed` (in the right
  file); DEF356 open-site netting removed (`sim_engine.py:3305`) -> `1 failed, 16 passed`;
  DEF311 `_retire_orphaned_resting_sells` call removed -> `4 failed, 4 passed`; DEF305
  `is_fillable` in `evaluate_outcomes` bypassed -> `2 failed, 22 passed`; DEF310 phase-2 branch
  disabled (`state == "triggered"` -> never) -> `2 failed, 2 passed`; DEF312 wrong-side refusal
  bypassed (`sim_engine.py:1624`) -> `4 failed, 14 passed`.
- **DEF305's money-path registry:** `is_fillable` is called in `submit`, `evaluate_outcomes`,
  `manual_close`, `evaluate_short_brackets`, `accrue_short_borrow`, `force_close_breached_shorts`,
  `cover_short`, `run_option_lifecycle` and the resting-order sweep — every automatic close.

### Evidence, run bare in the pinned worktree

```
pytest <the 33 files in the submission's table> -q -p no:cacheprovider
494 passed, 1 warning in 51.17s     EXIT=0
flutter test test/models/option_proposal_test.dart test/widgets/option_proposal_ticket_test.dart
+27: All tests passed!              EXIT=0
```

Both match the submission exactly.

The source at `8c43c88e` is byte-identical to `34941fa1` (the 12 files between them are docs and register rows), so the full suite was run once, at `34941fa1`, for all four RETRO lanes.

Full backend unit suite, `34941fa1`, on melehost (the deploy target) — `git archive` tree in a
throwaway container built from the Alpha API image plus pytest, `/tmp` on tmpfs, split into three
file-shards capped at 0.9 CPU each so live Alpha kept a core; run bare, exit code read from each
shard's own log:

```
shard 0   2103 passed, 2 skipped                         EXIT=0
shard 1   2194 passed, 2 skipped, 2 failed               EXIT=1
shard 2   2433 passed, 5 skipped, 4 failed, 4 errors     EXIT=1
total     6730 passed, 9 skipped, 6 failed, 4 errors
```

All ten non-passes are one environmental cause: the image has no `git` binary
(`FileNotFoundError: [Errno 2] No such file or directory: 'git'`) and those files shell out to it
— `test_def278_…immutable`, `test_def405_…`, `test_cr216_…`, `test_def178_…`, `test_p30_…`.
Re-run bare on the Mac in the pinned worktree, where git exists:

```
pytest test_def278_… test_def405_… test_cr216_… test_def178_… test_p30_… test_cr175_readiness.py
42 passed, 2 failed
FAILED test_p30_registers_name_things_that_exist.py::test_every_file_a_register_row_claims_actually_exists
FAILED test_p30_registers_name_things_that_exist.py::test_no_new_register_identifier_is_absent_from_the_codebase
```

Those two are real and belong to `34941fa1` itself — the CR231 governance commit this lane rests
on added DEF416–418 rows with `../../../backend/…` links and an uncited identifier
(`check_dry_run_compliance`). Already fixed on `main` by `8e550a57`; not this lane's code, not a
finding here. At `8c43c88e` those rows do not exist. (An earlier unsharded attempt also tripped
`test_cr175_readiness::test_unstamped_build…` because the image carries `GIT_SHA`; with it unset
the test passes, as it does on the Mac.) Totals reconcile to 6749 of the 6751 the Mac collects for
this tree; the two-test gap is untraced.

Nothing product-side fails at this SHA or at `8c43c88e`.

FOREIGN: not run — no `foreign/RETRO-SIM-OPTIONS.r1` branch exists, and this audit's brief limits
writes to the lane, run and ledger files. Not a clean bill.

### Verdict

The engine's arithmetic is right where I re-derived it, the floors sit where the lane says, and
the four guards I mutated all bite. The one thing I would not ship to beta is the fix for DEF368:
turning a silent loss into a silent gain plus a forbidden naked call is not a fix, and it is the
only path into option state that meets no floor at all. It is latent until the first mandate
permits derivatives — which is exactly when it would fire.

VERDICT: AWAITING_FIXES (round 1)

---

## Round 2 — auditor U68

**SHA audited:** `ae468eff` (the `+112` integration merge; this lane's fix is `3e822fa5`).
Detached scratch worktree `audit-U68-R2` per DEF159, verified clean after the mutation below.
**Not live yet:** Alpha runs `alpha-2026-09-25-3`; these fixes ship in +112.

### MAJOR-1 — fixed

When both accounts already have a portfolio, the orphan's option legs and structures are no
longer re-keyed into the adopter. They are dropped along with the holdings and cash that funded
and covered them. The drop is counted (`sim_option_legs_dropped`) and logged, and explicit
deletes make the sqlite suite match Postgres' CASCADE (`merge_service.py:240-337`). My round-1
probe, re-run unchanged on this tree, plus the other branch:

```
PROBE adopter_has_portfolio=True  counts={'sim_option_legs': 0, 'sim_option_legs_dropped': 2, …}
PROBE   adopter_tv 10000.0 -> 10000.0 delta=+0.00; AAPL held=0 locked=0.0; dangling legs=0      (round 1: +4650.00, locked 100 / held 0)
PROBE adopter_has_portfolio=False counts={'sim_option_legs': 2, 'sim_holdings': 1, …}
PROBE   adopter_tv 0.0 -> 60814.0 (= orphan_tv 60814.0); AAPL held=100.0 locked=100.0; dangling legs=0
```

No value is minted and no naked call is created. When the adopter has no portfolio of its own,
the whole portfolio moves as one unit, and total value and cover both carry over exactly. The
builder's choice to drop rather than carry the options is one of the two options I offered, and
its reasoning is sound: the cover can be a partial claim on a shared holding, so "the shares
behind this one structure" is not a quantity the ledger can produce.

**Mutation, mine:** re-inserted the round-1 re-key (`update(SimOptionLegRow)` and
`update(SimOptionTradeRow)` into `target_portfolio`) ahead of the count -> `5 failed, 3 passed`.
This includes both invariant tests, `…never_creates_value_from_nothing…` and
`…never_creates_a_naked_short_call…`. The invariants are guarded.

### MINOR-4 (round 2, new) — the drop is disclosed to the logs, not to the user

My round-1 fix option was "drop …, *disclosed* (the DEF368 complaint was silence, not loss)".
What ships records the drop in a log line and in `MergeResult.counts`, which the app does not
display. The consent sheet the user acts on is built from `/merge/preview`. That preview has no
option count, and the sheet reads *"Would you like to bring it into your account?"* above a
**MERGE EVERYTHING** button (`app_en.arb` `mergeSheetBody` / `mergeSheetConfirm`;
`merge_sheet.dart:90-104,132,196`). A user whose consented structure disappears on claim is still told
nothing, and that silence is DEF368's own complaint. It is latent: 0 of 54 current mandates
permit derivatives and 0 option legs exist on Alpha (re-read, 2026-09-25). Hence MINOR, but it has to close **before
`derivatives_allowed` is turned on for any user.** **Fix:** add the option count to
`MergePreview`, and have the sheet say what will be dropped. The mandate line already does this:
*"yours stays — we'll drop the older one"*.

### MINOR-1 — closed

The DEF305 row now carries a dated correction quoting Saiful's 2026-08-26 ruling. Verified in the
diff.

### MINOR-2 — closed

The DEF357 citation is corrected to `test_cr172_option_margin_sweep.py`.

### MINOR-3 — not fixed: the near-miss now prints `"1.00x"`

```
_size_to_budget(put 95, budget $9,000) -> 'the risk budget of $9,000 does not cover one contract, whose
                                          loss is $9,030 — offered at the minimum size of one, which
                                          risks 1.00x the budget'
```

`"1.00x"` reads as exactly the budget just as `"1.0x"` did; a 0.3% overrun is simply below
two-decimal resolution. The restored test now **asserts** that output
(`assert "1.00x" in near`, `test_cr172_option_strategist.py:369`). It locks in the misleading
text rather than guarding against it. Separately, `9.999` now prints `"10.00x"` while `10.0`
prints `"10x"`. The dollar figures beside the multiple still carry the fact, so the message is
not false. MINOR, carried forward. **Fix:** below 2x, state the overrun as a percentage
(*"0.3% over the budget"*).

**Worth recording:** the builder found that this test had asserted nothing since it was
written. Its assertions had been spliced, unreachably, after a `return` in a neighbouring
helper. That is a real find. No suite run could have shown it.

### OUT-OF-SCOPE (pre-existing, not caused by this round)

- **Holdings are dropped just as silently, and that is live today.** In the both-portfolios
  branch, the orphan's holdings and cash have always been dropped under the same **MERGE
  EVERYTHING** sheet, whose only related line lists *"N simulated trades"* as coming across. This
  is reachable by any user who signs in to an existing account from a device that used the app
  anonymously.
- **In that same branch the orphan's open BUY trade rows *are* re-keyed into the adopter's
  portfolio.** The shares behind them are dropped, so after such a claim the trade ledger and
  `sim_holdings` disagree (the DEF316 / `def110_backfill` phantom-share shape). I read this; I did
  not drive it. `evaluate_outcomes`' `_held_quantity` gate keeps those brackets from firing
  unless the adopter holds the same ticker.

### Evidence, run bare in the pinned worktree

```
pytest test_def368_merge_keeps_options.py test_cr172_option_strategist.py -q -p no:cacheprovider      (and in the full suite)
```

Full unit suite at `ae468eff`. The melehost part ran in a throwaway container from the Alpha image,
3 shards on tmpfs. The 5 files that need `git` ran on the Mac. All runs bare, exit codes read directly:

```
melehost s0   1 failed, 2126 passed, 2 skipped    EXIT=1   test_def200_ratchet.py::test_no_new_handler_blocks_the_event_loop
melehost s1   2669 passed, 3 skipped              EXIT=0
melehost s2   1 failed, 2013 passed, 4 skipped    EXIT=1   test_def247_displaced_stance_envelope.py::test_a_displaced_envelope_is_still_reported
Mac (5 git-dependent files)  34 passed            EXIT=0
total         6842 passed, 2 failed, 9 skipped
```

I diagnosed both failures:

- **`test_def200_ratchet`: a real regression, from RETRO-SECURITY's round-2 fix (`717cd8ff`).**
  It fails alone on the Mac at `ae468eff` and passes at `0accfeed`. The new sync `refund()` in
  `brief.py`'s `async def event_stream` is blocking DB I/O on the event loop. It is graded in
  RETRO-SECURITY (MAJOR-3). The Architect's 281 targeted tests did not include the ratchet.
- **`test_def247…`: pre-existing and order-dependent, not caused by round 2.** It passes alone.
  I ran shard 2's first 95 files in their shard order on the Mac: it fails identically at
  `ae468eff` **and** at `0accfeed` (`1 failed, 1474 passed`). The event is emitted (it shows in
  captured stdout), but `structlog.testing.capture_logs` does not see it, because an earlier test
  in the same process caches the logger. It passes in the default full-suite order that the
  +111 gate ran. Recorded as out-of-scope; no fix is owed by this round.

This lane's own files are green in every run. The one real regression is in another lane.
**+112 cannot pass its gate until RETRO-SECURITY's MAJOR-3 is fixed.** That does not bear on
this verdict.

FOREIGN: not run — no `foreign/RETRO-SIM-OPTIONS.r2` branch exists. Not a clean bill.

### Verdict

The MAJOR is fixed the right way. The merge no longer mints value or a forbidden position,
I re-drove my own reproduction to prove it, and both invariants are now guarded. Two MINORs
remain, and neither forces a round. The drop needs to reach the user, not just the log, and
that is a hard condition before options go live. The DEF354 multiple still reads as "exactly the
budget", now pinned by a test that asserts it.

Counts, round 2: 0 BLOCKER, 0 MAJOR (MAJOR-1 fixed), 2 MINOR open (MINOR-3 carried, MINOR-4
new). MINOR-1 and MINOR-2 are closed.

VERDICT: COMPLETE (round 2)
