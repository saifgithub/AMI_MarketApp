## CR233 — real Alpaca order types (limit/stop/stop_limit/bracket)

## What

`AlpacaClient.submitOrder()` (CR227) placed a market order only — every other order
type was refused before this CR, and the trade ticket's destination picker hid itself
for any non-market order as the enforcing check for that refusal. This CR gives
`submitOrder()` the ticket's other three order types natively (limit, stop, stop_limit)
plus an optional bracket (stop-loss + take-profit legs, via Alpaca's own
`order_class: bracket`), and removes the order-type lock on the destination picker now
that the client can actually honour what it asks for.

## Why

Saiful, 2026-09-24, verbatim: *"During trading, the 'destination' AMI, Alpaca, both,
only appears when 'market' is selected. Everything else does not show it. Fix it
please."*

The cause was structural, not a UI oversight. CR227's round-1 independent audit
(`orchestration/audit/cr/CR227.auditor.md`, MAJOR-1) found that `AlpacaClient
.submitOrder()` had no order-type parameter at all and hard-coded `type: 'market'`
unconditionally — a LIMIT or STOP ticket routed to Alpaca was silently converted to an
immediate market fill, with nothing telling the user their limit was never honoured.
CR227's own Non-goals section already said this must not happen ("mixing AMI's
resting order triggers three days later with Alpaca fills immediately today is a
correctness problem this CR does not attempt to solve"), so the round-1 fix was to
close the *silent-conversion* hole by refusing every non-market order outright and
hiding the destination picker for one — the friendly half of the fix, with
`submitOrder()`'s own type check as the structural half. That was the right fix for
what CR227 was scoped to ship, but it left the underlying capability gap unaddressed:
Alpaca's own paper API natively supports all four order types AMI's ticket already
has, so "the picker only appears for market" was never a compliance boundary, just an
unfinished client. This CR is that follow-through.

## Scope

**Mobile-only.** No backend change. The backend's role in this flow (`POST
/v1/sim/preview` as the mandate/compliance gate) is unchanged in shape by this CR —
mobile now sends the order's own `order_type`/`limit_price`/`trigger_price` on that
call (previously always `order_type: 'market'` with no limit/trigger price at all), a
wire-compatible widening since `SubmitTradeRequest` has no `extra="forbid"` and
already declared these fields for the AMI-submit path. See **Known gap** below for
what this widening does *not* yet achieve server-side.

### 1. `AlpacaClient.submitOrder()` — the real order types

`mobile/lib/services/alpaca/alpaca_client.dart` gains:

- `buildAlpacaOrderPayload(...)` — builds the exact `POST /v2/orders` body for
  market/limit/stop/stop_limit, plus an optional bracket. Extracted as a pure,
  exported function so the mobile test suite can assert on the wire body directly
  (golden-style), the same "extracted decision function" convention `isAlpacaPaperHost`
  already established in this file.
- `validateAlpacaOrder(...)` — checks the order's price relationships BEFORE any
  network call and throws `AlpacaOrderRejected` (the same exception CR227's refusal
  already used, so every existing `on AlpacaOrderRejected catch` — including CR230's
  `outcome: refused_client_side` reporting — covers this for free) on the first
  violation: an unrecognised order type, a missing required price, or a bracket whose
  stop/target sits on the wrong side of the entry. Mirrors
  `short_rules.dart`'s DEF312/DEF377 wrong-side-bracket rule (long: stop below entry,
  target above; short: inverted), applied to the Alpaca leg.
- `AlpacaBracket` — the two optional leg prices (`stopLoss`/`takeProfit`), built from
  the ticket's existing `_stop`/`_target` fields.
- `alpacaTimeInForce(SimOrderTif)` — maps AMI's resting-order TIF to Alpaca's own. See
  **TIF decision** below.

`submitOrder()` itself now takes `limitPrice`/`triggerPrice`/`tif`/`bracket` (all
optional, defaulting to today's market-only shape when omitted) and calls
`validateAlpacaOrder` then `buildAlpacaOrderPayload` before the `POST`. The
`orderType != market` unconditional refusal is gone; `orderType == unknown` still
refuses, for the same "never guess at a type this build does not recognise" reasoning.

### 2. `trade_ticket_sheet.dart` — the lock comes off order type

`_destinationLocked` was `coverTicker != null || sellTicker != null || orderType !=
market`. The third clause is removed — cover-a-short and sell-from-holding stay locked
(unrelated reasoning: AMI's own position sizes don't translate to Alpaca's independent
holdings), but any order type may now route to Alpaca, Both, or AMI Sim.

### 3. The Alpaca-leg preview is sized at the order's own price

`SimNotifier.preview()` and `ApiClient.simPreview()` gain `orderType`/`limitPrice`/
`triggerPrice` parameters, forwarded to `POST /v1/sim/preview`. Both call sites in the
ticket (`_submitAlpacaOnly`, `_legAlpaca`) now pass the order's own values instead of
always previewing as a market order — cash sufficiency for a LIMIT buy is checked at
the limit price, matching how AMI's own preview already prices a resting order.

**What the market-only leg did with stop/target before this CR:** nothing — there was
no stop/target concept on the Alpaca leg at all pre-CR233 (CR227 was explicitly
market-only, and a market fill carries no bracket in Alpaca's request). This is not a
"found it silently dropping a field that used to work" defect; the capability is new.

### 4. CR230 order log — order type, prices, TIF, bracket

`AlpacaOrderLogIn.detail` (backend, unchanged schema — a free-text field capped at 500
chars) now carries `order_type=... tif=... limit=... stop_trigger=...
bracket_stop_loss=... bracket_take_profit=...` for any non-market or bracketed order,
built once in `trade_ticket_sheet.dart`'s `_alpacaOrderLogDetail` so the log call and
the order call read the same facts (DEF098). No new column — widening the schema to
structured fields is future work if this needs to be queried rather than read, out of
scope here.

### 5. Result panel — "resting", never "filled"

`AlpacaOrder.isResting` (new getter, `mobile/lib/models/alpaca.dart`) reads Alpaca's
own order `status` (`new`/`accepted`/`pending_new`/`accepted_for_bidding`/`held` all
read as resting) rather than inferring from order type — a marketable limit can come
back already `filled`, the same "server states it, client never infers it" rule
`_showOutcome` already applies to AMI's own `resting` field. `_placeAlpacaOrder`'s
success message now says *"accepted, resting at Alpaca (<status>)"* for a resting
order and *"— <status>."* otherwise, never claiming a fill that has not happened.

## TIF decision

AMI's resting-order TIF (`SimOrderTif`: `day`/`gtd30`/`gtd90`) has no direct Alpaca
equivalent for the GTD cases. AMI's `day` already means "this session" (CR170's
`resting_order_expiry` anchors DAY to the session close at placement) — the same thing
Alpaca's own `day` means, so that leg maps exactly. AMI's `gtd30`/`gtd90` resolve
server-side to a fixed session-close N calendar-days out
(`RESTING_ORDER_TIFS = {"gtd_30": 30, "gtd_90": 90}`); Alpaca's REST API has no
"N days then expire" time in force on the simple orders endpoint — its own `gtd`
requires a client-supplied `expires_at` timestamp with narrower rules (a market-hours
cutoff, not honoured by every asset class), a second, independent expiry mechanism
this CR does not attempt to keep in lock-step with AMI's own sweep. Both AMI GTD values
map to Alpaca's `gtc` (good-till-cancelled) instead: the order rests at Alpaca
indefinitely until filled or cancelled there directly.

**This is a documented approximation, not an equivalence** — an AMI GTD-30 order and
its Alpaca `gtc` mirror do not expire at the same time (AMI's expires in 30 days;
Alpaca's never expires on its own). Alpaca paper orders are cancellable from Alpaca's
own dashboard/API, so the gap is recoverable, but nothing in the ticket's copy claims
the two expire together. Documented in `alpacaTimeInForce`'s docstring
(`alpaca_client.dart`).

## Bracket behaviour

A bracket order (`order_class: bracket`) is sent whenever the ticket's stop and/or
target fields are filled, regardless of the primary order's own type (market, limit,
stop, or stop_limit can all carry a bracket). `take_profit.limit_price` and
`stop_loss.stop_price` are sent as whichever legs are set — a one-sided bracket (only
a stop, or only a target) sends only that leg, not both. Validated client-side against
the DEF312/DEF377 wrong-side rule before any network call: for a BUY, the stop belongs
below the named entry (limit/trigger price) and the target above; inverted for a SELL.
When the order has no named entry (a plain market order), the bracket price
relationship is not judged — the same "nothing to check yet" convention
`stopIsWrongSide` uses for a null entry.

## Known gap — not fixed by this CR (mobile-only change)

`POST /v1/sim/preview`'s handler (`backend/app/api/sim.py::preview_trade`) forwards
`limit_price` to `SimEngine.preview()`, but that engine method has no `trigger_price`
parameter at all today (only `submit_trade`'s call path does) — so a STOP/STOP_LIMIT
Alpaca-leg preview still sizes cash sufficiency against the live mark, not the stop
price. `preview()` also runs no bracket-validity check at all (`stop`/`target` are not
parameters on it; only `submit_trade` validates a bracket). Mobile sends
`trigger_price` on the wire regardless — Pydantic accepts it harmlessly today
(`SubmitTradeRequest` has no `extra="forbid"`), so this is forwards-compatible with a
future backend fix, but nothing on the client should assume it is currently honoured.
A backend follow-up CR is needed to close this; flagged to the Architect, not
attempted here since this worktree's brief is mobile-only.

## Non-goals

- No backend change (see **Known gap**).
- No change to `toMandateSnapshotJson` or DEF419's account-snapshot wiring — that is a
  concurrently-edited surface per the dispatch brief, left untouched.
- No new order-log schema column — `detail` (free text) carries the new facts.
- Options remain out of scope (`OptionVerdictCta` stays AMI-sim-only, unchanged).
- Alpaca's own `expires_at`-based GTD is not implemented; `gtc` is the documented
  stand-in for both AMI GTD tiers.

## Acceptance

- [x] `AlpacaClient.submitOrder()` places market, limit, stop, and stop_limit orders
  against Alpaca with the exact expected wire body (golden-style assertions,
  `test/services/alpaca/cr233_alpaca_order_types_test.dart`).
- [x] A bracket (stop-loss/take-profit) is sent when either or both ticket fields are
  filled, on any primary order type, with only the set leg(s) included.
- [x] An order type Alpaca cannot take as asked (unrecognised type, missing required
  price, wrong-side bracket) is refused loudly (`AlpacaOrderRejected`) before any HTTP
  call — never silently converted.
- [x] The destination picker is visible for limit/stop/stop_limit orders and remains
  locked (hidden) for the cover-a-short and sell-from-holding entry paths.
- [x] The Alpaca-leg preview (`/v1/sim/preview`) is called with the order's own
  limit/trigger price, not always as a market order.
- [x] BOTH with a limit order places AMI's resting leg and Alpaca's resting leg
  independently, each reporting its own outcome.
- [x] The result panel says "resting"/"accepted" for an order Alpaca has not filled,
  never "filled", read from Alpaca's own order status.
- [x] `flutter analyze` clean at the pre-existing baseline (11 info-level issues, 0
  errors — unchanged by this CR).
- [x] Full `flutter test` suite green (1575/1575).
- [x] Mutation check: reintroducing the order-type clause in `_destinationLocked`
  fails 8 of the 10 tests in `cr233_ticket_order_types_test.dart` (verified, then
  reverted).

## Status

`in_progress` — mobile implementation + tests landed this session (round 1, submitted
to the CR005 audit handshake per `orchestration/audit/cr/CR233.architect.md`). Not yet
promoted to Alpha; the backend gap above is unresolved and flagged for a follow-up CR.
