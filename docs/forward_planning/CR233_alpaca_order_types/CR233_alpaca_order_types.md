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

## Known gap — CLOSED round 2, price basis CORRECTED round 3 (backend)

**Round 1 gap, as originally filed:** `POST /v1/sim/preview`'s handler
(`backend/app/api/sim.py::preview_trade`) forwarded `limit_price` to
`SimEngine.preview()`, but that engine method had no `trigger_price` parameter at
all (only `submit_trade`'s call path did) — so a STOP/STOP_LIMIT Alpaca-leg preview
sized cash sufficiency against the live mark, not the stop price. `preview()` also
ran no bracket-validity check at all (`stop`/`target` were not parameters on it;
only `submit_trade` validated a bracket). Mobile sent `trigger_price` on the wire
regardless — Pydantic accepted it harmlessly (`SubmitTradeRequest` has no
`extra="forbid"`), so it was forwards-compatible, but nothing on the client could
assume it was honoured.

**Round 2 fix (backend + mobile, this session):**

- `SimEngine.preview()` gained `trigger_price`/`target` parameters
  (`backend/app/services/sim_engine.py`). Its `fill_price` is now
  `named_price_for(order_type, trigger_price=..., limit_price=...) or mark` — the
  order's own named price for LIMIT/STOP/STOP_LIMIT, the mark only for MARKET —
  reusing the exact pricing rule `commitment_for()` (`sim_resting_orders.py`)
  already applies to a resting order's committed cash at read time. The SAME
  `named` value is passed as `ProposedTrade.limit_price`, so
  `check_mandate_compliance`'s `unit_price` chokepoint (DEF153) also sizes the
  single-name/sector caps and the open-risk contribution off the order's own
  price, not the mark, for a STOP/STOP_LIMIT preview.
- `preview()` now runs the same DEF312/DEF377 wrong-side-bracket refusal
  `_execute_fill` already runs on `submit()` — scoped to the AMI (no-account)
  path, matching `_execute_fill`'s own `kind == "training"` gate (the Alpaca
  snapshot path has no AMI short-position concept to decide "opens a short"
  from; Alpaca's own bracket validation runs client-side in
  `validateAlpacaOrder`, this CR's round-1 mobile half).
- `backend/app/api/sim.py::preview_trade` forwards `req.trigger_price`/`req.target`
  to `sim.preview()` (previously dropped both on the floor).
- Mobile: `ApiClient.simPreview` gained `stop`/`target` params;
  `SimNotifier.preview()` forwards them; both trade-ticket call sites
  (`_submitAlpacaOnly`, the BOTH Alpaca leg in `_legAlpaca`) now send the
  ticket's own `_stop`/`_target` fields, matching the pattern already used at
  the `/submit` call sites.

**Round 3 fix (backend, this session — auditor U68 MAJOR-1 on the round-2 lane):**

The round-2 basis above (`named_price_for(...) or mark`) was itself wrong for two
shapes the auditor measured through the real routes: a marketable stop/limit (one
whose named price the mark has ALREADY crossed) fills at once, at the mark
(`submit()`'s own unconditional `fill_price = mark` before its rest-vs-fill branch —
CR170 §3 acceptance 1, no order-type exception) — sizing it at the named price
instead understated a BUY STOP set 1% below the mark as 1% of its real notional,
passing a single-name cap the identical market order failed at 30%. And a
STOP_LIMIT that still rests can fill anywhere up to its own LIMIT once triggered,
never just the trigger — sizing it at the trigger alone understated a 17.8%-of-
equity commitment as 9.0%. Both diverged in a way `submit()` did not, which matters
because on the Alpaca-snapshot path `preview()` is the ONLY mandate check an order
ever meets.

Fix: `SimEngine.preview()` and `SimEngine.submit()` now both size their compliance
check through ONE shared helper, `committed_price_for()`
(`backend/app/trading_math/order_pricing.py`) — mark when already triggered
(matching what `submit()` actually books), the order's own trigger when a STOP
still rests, and a STOP_LIMIT's own LIMIT (never the trigger alone) when it still
rests. `fill_resting_order()`'s own re-run of the compliance check (CR170's
no-time-delayed-bypass guarantee) got the same fix, for the same reason — it used
to size against the stale `order.limit_price` (`None` for a plain STOP) rather than
the price Rule 2 is about to actually book the fill at.

Full detail, tests, and mutation evidence: `orchestration/audit/cr/CR233-BE.architect.md`
(round 2 of that lane's own review).

## Non-goals

- Round 1: no backend change (see **Known gap** — closed round 2, backend included).
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

**Round 2 (backend gap closure):**

- [x] A STOP/STOP_LIMIT preview sizes cash-sufficiency and concentration at the
  order's own `trigger_price`, not the live mark — on both the AMI path and the
  DEF419 Alpaca-snapshot path (`backend/tests/unit/test_sim_engine.py`,
  `backend/tests/unit/test_cr233_preview_price_basis.py`).
- [x] A MARKET preview is unaffected — still sizes at the live mark, byte-identical
  to before round 2.
- [x] `preview()` refuses a wrong-side bracket (DEF312/DEF377) the same way
  `submit()` does, on the AMI path.
- [x] Mobile forwards the ticket's `stop`/`target` fields on both preview call sites
  (`_submitAlpacaOnly`, `_legAlpaca`) — widget-level assertions in
  `cr233_ticket_order_types_test.dart`.
- [x] `flutter analyze` clean at the pre-existing baseline (11 info-level issues, 0
  errors — unchanged).
- [x] Full `flutter test` suite green (1589/1589 — 1575 baseline + 14 new).
- [x] Mutation checks (one backend, one mobile): reverting the `named_price_for`
  fallback in `SimEngine.preview()` back to always-mark fails 6 tests across
  `test_sim_engine.py` + `test_cr233_preview_price_basis.py`; reverting the
  bracket-validity check fails 2 more; dropping `stop`/`target` from
  `_submitAlpacaOnly`'s preview call fails the round-2 mobile tests in
  `cr233_ticket_order_types_test.dart`. All three verified, then reverted.

**Round 3 (auditor U68 MAJOR-1 fix — preview/submit price-basis parity):**

- [x] A STOP/STOP_LIMIT already marketable (mark has crossed its named price) sizes
  cash-sufficiency/concentration at the MARK, matching what `submit()` actually
  books — on both the AMI path and the DEF419 Alpaca-snapshot path
  (`test_sim_engine.py`, `test_cr233_preview_price_basis.py`).
  A STOP_LIMIT still resting sizes at its own LIMIT, never the trigger alone.
- [x] `SimEngine.preview()` and `SimEngine.submit()` share ONE pricing helper
  (`committed_price_for()`, `backend/app/trading_math/order_pricing.py`) so the two
  cannot diverge again — `test_cr233be_preview_submit_price_parity.py` pins the
  helper's own table (every order type x side x triggered/untriggered) and proves
  `preview()`/`submit()` agree at the exact single-name-cap boundary, on both the
  AMI and Alpaca-snapshot paths.
- [x] `fill_resting_order()`'s own re-run of the compliance check (the fill-time
  re-check CR170 added so a resting order is never a time-delayed bypass) sizes at
  the SAME price Rule 2 is about to book the fill at, not the stale `order.limit_price`.
- [x] Full targeted backend suite green: `test_sim_engine.py`,
  `test_cr233_preview_price_basis.py`, `test_cr233be_preview_submit_price_parity.py`,
  `test_def419_per_account_mandate_check.py`, `test_safety_floor.py`,
  `test_wire_contract_parity.py` — 131 passed, 1 pre-existing skip.
- [x] Mutation checks: reverting `preview()`'s `committed_price_for` call back to
  round-2's `named_price_for(...) or mark` fails 11 tests across three files;
  reverting `submit()`'s compliance-sizing back to raw `limit_price` fails 3 parity
  tests; reverting `fill_resting_order()`'s compliance-sizing back to
  `order.limit_price` fails the dedicated fill-time parity test. All three verified,
  then reverted (`git diff` confirmed clean after each).

Full detail: `orchestration/audit/cr/CR233-BE.architect.md` (round 2 of that lane's
own review).

## Status

`in_progress` — mobile implementation + tests landed round 1, submitted to the CR005
audit handshake per `orchestration/audit/cr/CR233.architect.md` (mid-review, not
touched this round). The round-1 backend gap was closed round 2; round 2's own price
basis had a MAJOR finding (auditor U68), fixed round 3 — see above and
`orchestration/audit/cr/CR233-BE.architect.md` (round 2 of that lane's own review,
submitted). Not yet promoted to Alpha.
