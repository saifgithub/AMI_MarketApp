<!--
CR233-BE.auditor.md — audit lane verdicts. Auditor-owned; the architect never writes here.
Newest round at the bottom. State derives from round numbers here vs CR233-BE.architect.md.
-->

# CR233-BE — auditor verdicts (preview price basis + bracket check for non-market orders)

## Round 1 — auditor U68 (taken over from U67, which posted no verdict)

**SHA audited:** lane `0167e999`, as merged and running live on backend `685dbdd0`
(`alpha-2026-09-25-4`) and mobile build `+111`. The mobile `lib/` at `685dbdd0` is identical to
the `+111` bump commit `5c751bb8`. From the lane to the live SHA, `sim_engine.py`, `api/sim.py` and
the lane's tests are unchanged. The only files that moved are the CR234 mobile files. Scratch
worktree `audit-U68-L` per DEF159, clean after every mutation. The probe test was untracked
scratch and was deleted with the worktree.

**What must hold.** For a linked Alpaca paper account, `/v1/sim/preview` is the whole safety floor.
`_submitAlpacaOnly` and `_legAlpaca` post to Alpaca only after `preview.accepted`
(`trade_ticket_sheet.dart:785-799,969-980`). The backend never sees the order again. So the
preview must size an order at the price it can actually fill at, or the D-071/D-074 promise
("the same mandate/compliance floor as AMI's own sim") does not hold.

### MAJOR-1 — the new basis ignores whether the order fills at once, and a STOP_LIMIT's limit

`preview()` now sets `fill_price = named_price_for(...) or mark` and hands `named` to the floor
(`sim_engine.py:2542-2559`). `named_price_for` returns the **trigger** for both STOP and STOP_LIMIT
(`order_pricing.py:111-124`). Two consequences follow, and `submit()` avoids both:

1. **A marketable stop is sized at its trigger, while it fills at the mark.** `submit()` rests an
   order only when `not is_triggered(...)`. Otherwise it fills now, at `fill_price = mark`
   (`sim_engine.py:1503-1531`, CR170 §3). `preview()` does not ask the question.
2. **A STOP_LIMIT is sized at its trigger, while it can fill at any price up to its limit.**

Measured through the real `/v1/sim/preview` and `/v1/sim/submit` routes (mark 408.14):

```
P1 AMI path, BUY STOP trigger 4.08 (1% of mark), qty = $30,000 at mark, cash $10,000:
   preview accepted=True  fill_price=4.08   |  submit -> refused: 'position size 300.0% exceeds single-name cap 150.0%'
P2 Alpaca-snapshot path, same BUY STOP, equity $100k, single_name_cap 10%:
   STOP   preview accepted=True  fill_price=4.08
   MARKET preview (same qty)      accepted=False 'position size 30.0% exceeds single-name cap 10.0%'
P3 Alpaca-snapshot path, BUY STOP_LIMIT trigger 412.22, limit 816.28, qty 21.8:
   preview accepted=True, sized at 412.22 -> 9.0% of equity; at its own limit the order can commit $17,822 = 17.8% vs cap 10%
```

- **P1** is the *"dry-run that answers a question other than the one being asked"* this lane
  set out to close. It is now open the other way round: the preview accepts what submit refuses.
- **P2 is the one that matters.** On the Alpaca-only path, nothing checks the order after P2's
  `accepted=True`. A buy stop entered below the market passes the floor at 1% of its real price.
  I could not measure what Alpaca does next, whether it fills at once or rejects the order. There
  are no Alpaca credentials in the audit sandbox, and placing an order is a brokerage write I am
  not cleared to make.
- **P3 is guaranteed by the order's own terms.** Alpaca may fill a triggered stop-limit anywhere
  up to the limit.

On the AMI path the damage stops at P1's mismatch, because `fill_resting_order` re-checks
compliance at the actual fill (`sim_engine.py:1976`). The snapshot path has no fill-time check.

**Fix:** size the way `submit()` fills. Use the mark when
`is_triggered(side, order_type, named, mark)`. Otherwise use `named`, except a buy STOP_LIMIT,
which should be sized at its limit (the most it can pay). Add tests for a marketable buy stop and
for a wide stop-limit on the snapshot path. Note that
`test_stop_preview_accepted_when_trigger_affordable_even_if_mark_is_not`
(`test_cr233_preview_price_basis.py`) says "a trigger UNDER the mark", but its numbers put the
trigger at 5× the mark, so the marketable case is not pinned.

### Verified, no finding

- **§3, `stop`/`target` omitted:** `bracket_is_wrong_side(stop=None, target=None)` is a no-op on
  both branches. MARKET previews are unchanged (`test_market_preview_still_sizes_at_mark`, green).
- **§5:** LIMIT's `named` is `limit_price` and MARKET's is `None`, which falls through to the mark,
  so only STOP and STOP_LIMIT changed. MAJOR-1 is exactly that change.
- **§2, the snapshot path skips the server bracket check:** the client validates brackets for
  every non-market order (`validateAlpacaOrder`, see CR233), and Alpaca validates a market bracket
  itself. No finding.
- **§6:** exactly four `SimNotifier.preview` overrides plus the base exist
  (`grep -rn "Future<SimPreviewResult?> preview(" mobile/`). None is missing.

### Mutations, mine (each reverted, tree re-checked clean)

- `preview_trade` stops forwarding `trigger_price` (`api/sim.py:708`): 3 failed.
- The builder's price-basis and bracket mutations (6 and 2 failed) are recorded, not repeated.

### Evidence, run bare in the pinned worktree

```
pytest test_cr233_preview_price_basis.py test_sim_engine.py test_def419_per_account_mandate_check.py -q -p no:cacheprovider
55 passed     EXIT=0
```

Full unit suite at `685dbdd0` (my run today): 6849 passed, 1 failed. The failure is the
pre-existing, order-dependent `test_def247`.

FOREIGN: not run — no `foreign/CR233-BE.r1` branch exists. Not a clean bill.

### Verdict

The lane forwards the trigger price end to end, and that part is sound and guarded. But the price
it picked is wrong for two order shapes, and on the Alpaca path the preview is the only floor
there is. A buy stop below the market, or a stop-limit with a wide limit, passes the mandate caps
at a fraction of what it can actually commit.

Counts, round 1: 0 BLOCKER, 1 MAJOR, 0 MINOR.

VERDICT: AWAITING_FIXES (round 1)

---

## Round 2 — auditor U68

**SHA audited:** fix `472905e8`, merged at `main` `b065b4ba`. Not live: Alpha runs `685dbdd0`.
Scratch worktree `audit-U68-Q` at `b065b4ba` per DEF159. The probe file there was untracked
scratch, and it was deleted with the worktree.

**The same question as round 1.** On the Alpaca path, the preview is the whole floor. Does it now
size an order at the price it can actually commit? I re-ran my round-1 probes, unchanged, through
the real `/v1/sim/preview` and `/v1/sim/submit` routes (mark 408.14):

```
P1 AMI path, BUY STOP trigger 4.08, $30k at mark:  preview accepted=False fill_price=408.14 'position size 300.0% exceeds single-name cap 150.0%'
                                                   submit  refused                         'position size 300.0% exceeds single-name cap 150.0%'
P2 snapshot path, same BUY STOP, cap 10%:          STOP   accepted=False fill_price=408.14 'position size 30.0% exceeds single-name cap 10.0%'
                                                   MARKET accepted=False fill_price=408.14 'position size 30.0% …'   (identical)
P3 snapshot path, BUY STOP_LIMIT 412.22/816.28:    accepted=False fill_price=816.28 'position size 17.8% exceeds single-name cap 10.0%'
```

### MAJOR-1 — fixed

- **P1:** the preview and submit now refuse at the same number.
- **P2:** a buy stop below the market is now priced exactly like the market order it becomes.
- **P3:** a resting stop-limit is sized at its limit, the most it can pay. That gives the 17.8% I
  computed in round 1.
- **One helper.** `committed_price_for` (`order_pricing.py:151-229`) now serves all three call
  sites: preview, submit's compliance check and the fill-time re-check.
- **The fill-time fix is right.** `fill_resting_order` now values the proposal at the exact price
  it books (Rule 2). The old code used the stored `limit_price`, which is `None` for a plain STOP
  and silently fell back to the mark.

**Mutations, mine**, on the helper and run against the lane's files plus `test_sim_engine`,
`test_def419` and `test_safety_floor` (baseline 104 passed):

| Mutation | Result |
|---|---|
| A marketable STOP sized at its trigger (`if triggered and ot != STOP`) | 5 failed |
| A resting STOP_LIMIT sized at its trigger, not its limit | 4 failed |

The builder's three call-site mutations (11, 3 and 1 failed) are recorded and not repeated.

### I checked the sell side as well. No finding.

For a sell stop-limit, the limit is the *lowest* price it can fill at. So sizing a resting sell
stop-limit at its limit would understate a *short*. I drove it with `long_only` OFF: trigger
0.99×, limit 0.01×, 30% of equity. The cap passes at the limit, and then the preview refuses the
order anyway: `cannot sell 73.5 AAPL: not enough held` (`sim_engine.py:2760-2767`). The preview
refuses every sell-to-open on both paths, so no short reaches Alpaca through the ticket. On the
AMI path, `/submit` rests it with the cap sized at the limit, and the limit is the price Rule 2
then books it at. That is consistent, if odd. It is recorded here only because I measured it.

### MINOR-1 — the route-level test I flagged in round 1 still describes the opposite case

`test_stop_preview_accepted_when_trigger_affordable_even_if_mark_is_not`
(`test_cr233_preview_price_basis.py:154`) still says *"a trigger UNDER the mark"*, but its
numbers put the trigger at 5× the mark, which is a resting order. The substance is now covered:
`test_stop_marketable_preview_sizes_at_mark_on_alpaca_snapshot_path` pins the marketable case.
Only the docstring misleads. **Fix:** say "a resting trigger above the mark".

### Recorded, not scored (pre-existing, outside this lane)

- **A stop-limit that is marketable at entry fills straight through its own limit.** `submit()` fills any
  marketable order at the mark (`fill_price = mark`), and the helper mirrors that on purpose
  (`order_pricing.py:188-193`). Measured on the AMI path through the real `/submit`:

  ```
  BUY  STOP_LIMIT trigger 367.33, limit 387.73, mark 408.14  -> filled at 408.14  ($20.41 ABOVE the limit)
  SELL STOP_LIMIT trigger 448.95, limit 428.55, mark 408.14  -> filled at 408.14  ($20.41 BELOW the limit)
  ```

  This is DEF310's defect class, a stop-limit filled without its limit being consulted, at submit
  time instead of in the sweep. The curriculum teaches the limit as the protection, and the sim
  breaks it at entry. For the floor, the mark is conservative on the buy side, so this does not
  weaken CR233-BE. It needs its own defect. When that fix lands, `committed_price_for`'s
  triggered STOP_LIMIT branch has to follow it.
- **A marketable buy LIMIT is now sized at the mark, not its limit.** That matches what `/submit`
  books. Alpaca reserves buying power at the limit, so it may refuse an order AMI's preview
  accepted. That is the venue refusing, not the floor being bypassed.

### Evidence

```
pytest test_cr233be_preview_submit_price_parity.py test_cr233_preview_price_basis.py test_sim_engine.py test_def419_per_account_mandate_check.py test_safety_floor.py -q -p no:cacheprovider
104 passed     EXIT=0
```

Full unit suite at `b065b4ba`: 3 melehost shards plus the 5 git-dependent files run on the Mac.

- **Totals:** 6929 passed, 9 skipped, 3 failed. None of the 3 is in this lane's area.
- **Two failures are DEF417's.** They are the blocking-I/O guard, recorded as DEF417 round 2
  MAJOR-3.
- **The third is a timing flake.** `test_cr077_phase_parallelism` passes when run alone.

FOREIGN: not run — no `foreign/CR233-BE.r2` branch exists. Not a clean bill.

### Verdict

Strong. The preview now asks the question `/submit` asks: does this order fill now, or does it
rest? It then prices the answer the same way through one shared helper. My three round-1 probes
now refuse at the right numbers on both paths. The third call site, the fill-time re-check, was
found and fixed without prompting. The only residue is one mislabelled docstring.

One pre-existing sim bug came up along the way: a stop-limit that is marketable at entry fills
through its limit. It is not this lane's, and it needs its own defect.

Counts, round 2: 0 BLOCKER, 0 MAJOR, 1 MINOR.

VERDICT: COMPLETE (round 2)
