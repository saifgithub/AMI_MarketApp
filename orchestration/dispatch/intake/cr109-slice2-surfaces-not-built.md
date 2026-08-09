# Intake — CR109 slice 2 shipped without several surfaces its own spec requires

**Handle:** `cr109-slice2-surfaces-not-built` (pre-triage; no `DEF###` minted — the
Architect is the single ID-minter and other tracks are live on this checkout).
**Found:** 2026-08-09 by Saiful, using the shipped build (AT:R66).
**Severity:** high. One of these is the surface the design calls *"the most-seen state
in the product"*, and another makes the app promise something it cannot do.

## What Saiful hit

> *"1. This was the second order placed. But it is still showing I have 10K. All the
> Account is wrong. 2. Where do I see the orders placed? 3. You need to look back at
> all the requirements. Some basic ones are missing."*

He is right, and these are not gaps in the spec — they are requirements in
`CR109.md` §13.3 that the build skipped.

## The gap, against §13.3's own table

| Specified surface | Built? |
|---|---|
| **Queued orders** — pending fills, estimated costs, **cash committed**, cancel-any-time. §13.3 calls it *"the most-seen state in the product"* for GCC/SEA players | **No** |
| **The empty book** — *"the highest-anxiety moment in the product"*; explicitly *"must not be a blank list"*: the clock, one action, and the honest note that nothing stops them putting the whole stake in one name | **No** |
| **My run** — stake, TWR, equity curve, days left, **book heat gauge** (§10.4), final-stretch line | Partial — no curve, no heat gauge |
| **Trade ticket** — three taps, size, **stop/target presets**, cost before confirm | Partial — no stop/target presets |
| Lobby / all cadences, one tap deeper, cadences already held locked | No |
| Holdings list inside a run | No |

## Two consequences that are worse than "missing UI"

1. **The app made a promise it could not keep.** The ticket copy says *"free to cancel
   any time before it fills"* (§5.1's own wording). There was no way to see a queued
   order, let alone cancel one. Shipping a written promise with no mechanism behind it
   is the CR040 class applied to copy.

2. **Cash was over-offered.** Queued orders committed no cash, so the ticket showed the
   full 10,000 as available no matter how many orders were already queued against it.
   A player could commit several times their book; at the open the surplus fills would
   fail. §13.3 names `cash committed` as a required field of the queued-orders surface
   precisely to stop this.

## Done in this session (backend only)

- `games_service.list_queued_orders()` / `cancel_queued_order()`
- `_queued_orders_priced()` — prices queued orders **at read time** and returns the
  committed total. This does **not** breach the market-hours fence: that fence exists
  so a queued order never *fills* at a stale price, and this is a recomputed display
  estimate that is never stored and never used for a fill. The queue path still stores
  no price at all.
- `GET /v1/games/runs/{run_id}/orders`, `POST /v1/games/runs/{run_id}/orders/{id}/cancel`
- Run detail now returns `cash_committed`, `cash_available`, `queued_order_count`.

## Still to do

- The **mobile** queued-orders surface (list, est. cost + `price_source`, committed
  cash, cancel), and the ticket sizing against `cash_available` rather than
  `current_cash`.
- The empty book, the holdings list, the heat gauge, stop/target presets, the lobby.

## The pattern worth recording separately

Six client/server contract defects were found in one evening by *using the app*, none
by either test suite — every one was a client field name that never matched the wire,
read null-safely, defaulting silently (`cash`/`current_cash`, `shares`/`quantity`,
`est_fee`/`estimated_fee`, `status` defaulting to `'filled'`, the bare-array envelope,
the flat-vs-nested cadence). The briefs specified FIELDS and never SHAPES, so each lane
tested against its own reading and both stayed green.

`mobile/test/models/games_wire_contract_test.dart` now pins payloads verbatim from live
Alpha responses with real-value assertions. A test that only checks "parses without
throwing" would have passed on all six.
