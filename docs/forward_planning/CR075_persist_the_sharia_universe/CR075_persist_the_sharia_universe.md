# CR075 — Download the Sharia universe once a day and hold it

**Status:** proposed · **Filed:** 2026-07-23 · **Track:** `AT:architect`
**Depends on:** CR069-BE (merged `bdc410f`) · **Closes:** the freshness residual carried by
[DEF092](../../defect/DEF092_spus_403s_the_shipping_client/DEF092_spus_403s_the_shipping_client.md) ·
**Softens:** [DEF093](../../defect/DEF093_disabled_flag_blocks_every_halal_trade/DEF093_disabled_flag_blocks_every_halal_trade.md)

## Why

Saiful: *"Why don't we download and hold it for other users? We can do the download every day."*

Right, and it fixes more than it looks like it does.

**Today the universe lives only in process memory.** Each container holds its own copy, built on
first use and re-fetched no more often than every 900 s. That means:

| | Today | With a held copy |
|---|---|---|
| Network on the request path | yes — first halal trade after a restart pays for the fetch | never |
| Container restart | re-downloads | reads the stored row |
| Two workers | two downloads, possibly two different as-of dates | one universe, one date |
| Source down for an hour | `UNAVAILABLE` ⇒ **every halal trade blocked** | serve the last good list, disclosing its age |
| "What list did we use on 22 July?" | unanswerable | a row with a date |

That fourth line is the important one. **A transient network blip currently produces DEF093's blast
radius** — not because anything is broken, but because a source we do not control had a bad minute.
For a filter a user turned on for religious reasons, "we could not reach a CSV, so you may not
trade" is a bad answer when we had a perfectly good list yesterday and the standard itself only
changes at rebalance.

**It also closes the freshness gap I could not close otherwise.** The parent-index mirror publishes
no as-of of its own, so SPUS's date is currently the only staleness signal in the system — a frozen
parent list would go unnoticed. A stored row carries **`fetched_at`**, which *is* the missing
signal: we stamp when we pulled it, so a mirror that stops changing is visible even though the file
never says so.

**And it makes the claim defensible.** CR069 constraint 1 requires naming the standard, the source
and the as-of date wherever a verdict is shown. Holding the list means that date is a fact we
recorded rather than a property of whatever we happened to fetch — and if anyone ever asks which
companies AMI treated as compliant on a given day, there is a row that answers it.

## What

**Persist the universe, refresh it daily, and read it from storage on every request.**

1. **Storage** — a small table owned by `coder.api` (sole schema owner): standard, source URL,
   `as_of` from the file, `fetched_at` stamped by us, the compliant set, the parent set. Two lists of
   a few hundred tickers; size is a non-issue.
2. **Refresh** — a background task in the existing pattern. `main.py` already runs
   `_nightly_audit_trim()` and `_league_roll_tick()` as startup `asyncio` tasks, so this needs **no
   new dependency and no new mechanism** — a `_sharia_universe_refresh()` beside them. A tick that
   finds a fresh row does nothing, so restarts cannot miss a boundary (the same reasoning already
   written into `_league_roll_tick`).
3. **Read path** — resolve from the stored row. No network, no `asyncio.to_thread`, no first-request
   stall. The in-process cache becomes a plain read-through of the row rather than the source of
   truth.
4. **Staleness, unchanged in spirit** — constraint 3 still governs. Serve the held list while it is
   inside its window; past the window, pause loudly exactly as now. The change is that the window is
   measured against a date we recorded, and a failed refresh no longer means an empty universe — it
   means an ageing one, which we can say out loud.

## What this does NOT change

- **No failover, no union, no intersection.** One named primary standard (§3a). Holding a copy of
  one standard is not the same as blending two.
- **`sharia_screen()` stays dormant** (constraint 4). This is still a sourced list, not computed
  ratios.
- **Blocking on genuine unavailability stays.** If the held list ages out of its window, the filter
  pauses. Degrading loudly is the point; this CR only buys a much longer runway before it fires.
- **G3 unchanged** — unknown permits, with the disclosure.

## Open questions for the build lane

- **Window length.** SPUS rebalances periodically; `sharia_staleness_days` is 7 today. Whether a
  held list should be servable for longer than a fetched one is a judgement, and it should be
  *stated* rather than inherited by accident.
- **Seeding.** First boot with an empty table and an unreachable source is still `UNAVAILABLE`. That
  is correct, and it should be the only path that produces it.
- **Refresh-failure visibility.** A refresh that fails for three days running while the list is
  still inside its window is invisible to a user and should not be invisible to us. This is the
  degrade-loudly rule applied to the *refresher* rather than the reader.

## Acceptance

1. A restart performs **no** network fetch when a fresh row exists; the first halal trade after boot
   touches no socket.
2. Source made unreachable, held row inside its window ⇒ trades resolve normally against the held
   list, and the as-of shown is the held date.
3. Held row aged past its window ⇒ pauses loudly, exactly as today.
4. `fetched_at` visibly advances on a refresh where `as_of` does not — proving the parent-mirror
   freshness signal actually exists.
5. Two processes reading the same row resolve identically.
6. Backend suite green; the new guard red before the fix.

## Gate

`GATE: independent` — recorded upfront. It changes what a religious-observance filter enforces and
how it fails, which is the CR069/DEF084 class, and it touches the schema.
