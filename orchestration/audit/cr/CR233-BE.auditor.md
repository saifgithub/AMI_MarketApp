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
