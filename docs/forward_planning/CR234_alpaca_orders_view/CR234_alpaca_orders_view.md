## CR234 — Alpaca orders view (list, cancel, history) + one shared Alpaca identity

## What

`AlpacaClient` (CR202/CR227/CR233) could place an order (`submitOrder`) and read the
account/positions, but had no way to LIST or CANCEL an order once placed. A limit order
that reached Alpaca and sat resting there was invisible to the app forever — Portfolio's
Orders/History sections only ever read AMI's own `sim_resting_orders`/`sim_trades`. This
CR adds `AlpacaClient.orders()` (`GET /v2/orders`) and `cancelOrder()` (`DELETE
/v2/orders/{id}`), a new `AlpacaOrder` shape (type/side/qty/filled_qty/limit/stop
prices/tif/status/submitted_at/legs), and Orders/History sections that show Alpaca's
open/closed orders alongside AMI's own book, each labelled by destination, with a cancel
action on open orders.

**Scope addition, same day** — Saiful, from a TestFlight +110 screenshot of the
Portfolio screen mid-review: *"The alpaca section needs to be done along the same design
as the rest, but with a clear indicator for alpaca paper."* The screenshot showed the
pre-existing Alpaca account/positions section (added under CR202, unrelated to this CR's
core order-view work) rendering as a visibly different, lesser design: a plain
`Text('ALPACA PAPER')` header with a green dot instead of a badge; a bordered `Container`
with three `_AlpacaStat` columns whose BUYING PWR value ($362,137.57) wrapped onto two
lines; and Alpaca positions as bare `Row`s of plain `Text` (ticker, `x10`, market value,
P&L) — no card, no chevron, no expand, no % change, no stop indicator — while AMI's own
holdings were full `_HoldingCard`s (big ticker, "21 sh · \$210.48", a STOP chip, coloured
% change, tap-to-expand, chevron to per-lot detail) under a `_ValueCard` TOTAL VALUE
header with a LIVE/MOCK pill. This CR now also closes that gap.

## Why

Saiful, verbatim, on the original problem (2026-09-25): *"I am not seeing orders from
alpaca in the orders section after putting a limit buy."* Verified by the Architect: the
order genuinely reached Alpaca — the CR230 audit table shows an ASML buy 10, `order_type=
limit tif=gtc limit=1700.00 bracket_stop_loss=1619.15 bracket_take_profit=1946.42`,
`alpaca_status=accepted` — resting at Alpaca, with no way in the app to ever see or
cancel it. CR233 made real Alpaca order types possible; this CR is the missing read/cancel
half.

On the design-consistency addition: a second, visually inconsistent design language for
the same feature (Alpaca-linked trading) erodes trust in the "this is one coherent app"
signal a mobile UI depends on, and the wrapped BUYING PWR value is a genuine rendering
defect (a `RenderFlex`/text-wrap issue), not merely a stylistic gap.

## Scope

**Mobile-only.** No backend change for the identity/layout half. The order-log outcome
enum backend change (below) is the one server-side touch, needed for the cancel action's
audit trail.

### 1. `AlpacaClient` — list + cancel (`mobile/lib/services/alpaca/alpaca_client.dart`)

- `orders({status, limit, nested})` — `GET` the user's paper orders. `nested: true`
  (default) asks Alpaca to inline a bracket's child legs (stop-loss/take-profit) under
  the parent rather than as unexplained standalone rows.
- `cancelOrder(orderId)` — `DELETE` a resting order. Re-checks `isAlpacaPaperHost` itself
  before the call (same D-071/D-074 posture `submitOrder` already has for writes) rather
  than trusting the caller; refuses with `AlpacaOrderRejected` on a non-paper host or an
  unlinked device, before any network call.

### 2. `AlpacaOrder` model (`mobile/lib/models/alpaca.dart`)

Extended with `type`, `filledQty`, `limitPrice`, `stopPrice`, `timeInForce`,
`submittedAt`, and `legs` (a nested `List<AlpacaOrder>` for bracket children). New
`isClosed`/`isCancellable` getters read Alpaca's own documented order-lifecycle states —
`isResting` (CR233) is unchanged. `AlpacaPosition` gained `avgEntryPrice` (parses
`avg_entry_price`) so a position card can show "qty · avg cost" the same way an AMI
holding does.

### 3. Orders tab (`AlpacaOpenOrdersSection`, `mobile/lib/widgets/sim/alpaca_orders_section.dart`)

Renders Alpaca's OPEN orders below AMI's own `RestingOrdersSection`, gated on
`alpacaLinkedProvider`. Each row: type/side/qty, limit/stop price, TIF, status, bracket
legs, and a CANCEL ORDER action (confirm dialog → `cancelOrder` → refresh both Alpaca
providers → best-effort audit report with `outcome: cancelled`). **CR040 — a fetch
failure renders a visible "Couldn't load Alpaca orders" row, never an empty list**, which
would read exactly like "no orders" (the false negative this CR exists to close).

### 4. History tab (`AlpacaHistorySection`, same file)

Renders Alpaca's recently CLOSED orders (last 50: filled/cancelled/expired/rejected).
Empty renders nothing at all (AMI's own "no trades yet" empty state already covers the
tab); a fetch failure still renders a labelled error row (CR040 applies even here — see
**Known trade-off** below).

### 5. Backend — `cancelled` outcome (`backend/app/schemas/alpaca.py`, `backend/app/services/audit.py` unchanged)

`AlpacaOrderLogIn.outcome`'s pattern widened from
`submitted|rejected_by_alpaca|refused_client_side` to add `cancelled`, so the CR230
audit table (permanent retention, unchanged) gets a row for every cancel the same way it
already does for every submit. `record_alpaca_order` itself needed no change — it already
takes `outcome` as an opaque string. New backend test:
`test_cr230_alpaca_order_log.py::test_cancelled_lands_a_row_with_the_alpaca_order_id`.

### 6. Refresh (`portfolio_screen.dart`)

Pull-to-refresh now also invalidates `alpacaOpenOrdersProvider`/
`alpacaClosedOrdersProvider`, alongside the existing `alpacaLinkedProvider`/
`alpacaPortfolioProvider`/`alpacaPositionsProvider`.

### 7. Design-consistency scope addition — one shared identity + shared components

- **`AlpacaBadge`** (`mobile/lib/widgets/alpaca/alpaca_badge.dart`) — the ONE badge every
  Alpaca surface uses: account card, position cards, orders rows, history rows. Accent is
  `AmiColors.hexPurple` (`alpacaAccent`), chosen because it is already a general-purpose
  "another tier/system" accent elsewhere in the app (Floor Manager, the You screen, the
  CIO role) and carries no colliding meaning among the accents already load-bearing on
  THIS screen (cyan=primary/live, green/red=gain/loss, amber=stop/warning). Deliberately
  not Alpaca's own brand colour — the badge identifies which book the data came from
  inside AMI's own design language, not a co-branding mark. `kAlpacaPaperLabel` is the
  same literal, un-localized `'ALPACA PAPER'` string the trade ticket's destination
  picker already used — the ticket's 9 call sites now reference this one constant instead
  of repeating the literal.
- **`PositionCard`** (`mobile/lib/widgets/sim/position_card.dart`) — the position-card
  SHELL extracted from what was `_HoldingCard`: ticker/subtitle/badge-slot/stop-chip/%
  change/chevron/expand, with every fact passed in as a primitive or widget slot.
  `_HoldingCard` (AMI) and the new `AlpacaPositionCard` (Alpaca) both build on it now — one
  component, not two forks. The trailing cluster (badge + stop chip + % + chevron) is
  wrapped in a `FittedBox` so a card carrying BOTH a badge and a stop chip (an Alpaca
  position with a bracket stop — a combination AMI's own cards never had before this CR)
  scales down together rather than overflowing on a narrow phone.
- **`ValueCard`** (`mobile/lib/widgets/sim/value_card.dart`) — the value-card SHELL
  extracted from what was `_ValueCard`: title row + badge/pill slot, a headline WIDGET
  slot (so AMI's `TweenAnimationBuilder` count-up plugs in completely unchanged — this
  shell imposes no animation and no `FittedBox` of its own on the headline, so AMI's
  pre-CR234 rendering is byte-identical), and a stats row in one of two layouts:
  `inline` (AMI's original CASH row shape) or `columns` (Alpaca's original 3-stat
  CASH/PORTFOLIO/BUYING PWR shape, kept distinct rather than forced into `inline`'s
  2-item shape). Every stat value is `Flexible`+`ellipsis` — the one guard the
  pre-CR234 Alpaca card skipped, which is exactly what let BUYING PWR wrap.
- **`AlpacaAccountCard`** (`mobile/lib/widgets/alpaca/alpaca_account_card.dart`) — builds
  on `ValueCard`, wraps its own headline in a `FittedBox` (AMI's headline does not, and
  must not start now) because a fresh Alpaca paper account routinely starts at six
  figures — the exact value class that wrapped in the screenshot.
- **`AlpacaPositionCard`** (`mobile/lib/widgets/alpaca/alpaca_position_card.dart`) —
  builds on `PositionCard`. The stop chip is read off Alpaca's own OPEN bracket orders
  (`alpacaOpenOrdersProvider`, matched by symbol, preferring a bracket child leg's
  `stop_price` and falling back to a standalone open `stop` order on the same symbol) —
  never invented, matching CR189's "the position's actual stop, not a guess" rule already
  applied to AMI holdings. No matching order ⇒ no chip, the same "absence is information"
  posture `_HoldingCard` already has for an unprotected AMI holding.
- Orders/History rows (`alpaca_orders_section.dart`) and the trade ticket's own
  destination labels (`trade_ticket_sheet.dart`, 9 call sites) now reference
  `AlpacaBadge`/`kAlpacaPaperLabel` instead of a bespoke `Container`+`Text` chip or a
  repeated literal.
- Two now-orphaned ARB keys (`alpacaOrdersHeading`, `alpacaHistoryHeading` — the
  plain-text headings the badge replaced) were removed from `app_en.arb`/`app_ar.arb`/
  `app_ms.arb` rather than left dead.

## Tab-count decision (explicitly asked for; DECIDED, not deferred) — REVERSED by DEF422

Positions/Orders/History tab-bar counts originally shipped **AMI-only**, unchanged by the
Alpaca group each tab also renders. Alpaca's own counts come from async `FutureProvider`s;
a combined badge would either have to show a number that changes shape mid-load ("some
number, plus maybe more") or silently omit Alpaca's contribution on every loading/error
frame — the exact "quietly wrong count" CR040 forbids. Each tab already states which book
a row belongs to via the ALPACA PAPER badge directly above the Alpaca group, so the
book/count split is visible without the tab-bar number itself having to carry it.

**Saiful overrode this call (DEF422, TestFlight +111, 2026-09-25):** *"The 'order' header
was showing '0' orders. But I still have one order open in alpaca."* An AMI-only count that
reads "0" while a real Alpaca order sits open is the worse lie — CR040 exists to prevent
exactly this class of quietly-wrong number, and an honest-but-partial count fired that same
guard from the other direction. DEF422 combines each tab's AMI count with its Alpaca
counterpart once linked, and resolves this CR's own stated risk (a number that "changes
shape mid-load") the way CR040 actually requires: an explicit loading spinner or warning
glyph next to the AMI count while Alpaca's side is still resolving or failed, rather than a
combined number that looks final before it is, or one that silently drops Alpaca's
contribution forever. See `_TabCount`/`_TabCountMarker`/`_TabCountMarkerIcon` at the
`_PortfolioTabBar` call site in `portfolio_screen.dart`.

## Known trade-off

`AlpacaHistorySection`'s error state (a failed fetch) renders a heading + error row even
though its EMPTY (success, zero rows) state renders nothing at all — an asymmetry
deliberately kept: collapsing the error case to nothing too would make an Alpaca outage
indistinguishable from "you have no closed Alpaca orders," which is the CR040 failure
mode this CR exists to close, even in the one section where an empty *success* state is
legitimately silent.

## Non-goals

- No AMI/Alpaca reconciliation — the two books stay visually separate (destination-
  labelled), never merged into one list or one total.
- No change to `AlpacaSnapshotIn`/`AccountSnapshotIn` (CR202/DEF419's prompt-facing and
  mandate-facing wire contracts) — untouched, per the same "concurrently-edited surface,
  leave it alone" instruction CR233 already recorded.
- No currency abbreviation (e.g. "$362K") introduced anywhere — `ValueCard`'s headline
  slot is a caller-supplied widget precisely so AMI's exact pre-CR234 number formatting
  is preserved; only the wrapping/overflow behaviour changed, not the digits shown.
- Alpaca's own GTD expiry mechanics unchanged from CR233 (`gtd30`/`gtd90` → `gtc`,
  documented approximation).

## Acceptance

- [x] `AlpacaClient.orders()` builds the exact `GET /v2/orders` request (status/nested/
  limit query params), parses the response into `AlpacaOrder` including nested bracket
  legs.
- [x] `AlpacaClient.cancelOrder()` builds the exact `DELETE /v2/orders/{id}` request;
  refuses on a non-paper host or unlinked device before any network call, same posture as
  `submitOrder`.
- [x] Orders tab shows Alpaca OPEN orders alongside AMI's resting book, each destination-
  labelled, with type/side/qty/price(s)/TIF/status/bracket legs and a working cancel
  action (confirm → DELETE → refresh → best-effort `outcome: cancelled` audit report).
- [x] History tab shows Alpaca CLOSED orders (last 50), destination-labelled; a filled
  limit order is now visible after it fills.
- [x] Alpaca unreachable renders a visible error row on both Orders and History — never
  an empty list.
- [x] Pull-to-refresh invalidates the new Alpaca order providers.
- [x] One shared `AlpacaBadge`/`alpacaAccent` used on the account card, position cards,
  orders rows, history rows, and the trade ticket's destination labels.
- [x] Alpaca positions render from the same `PositionCard` shell AMI holdings use (ticker
  box, subtitle, % change, chevron, expand) — not a bare-text fork.
- [x] No overflow/wrap of currency values on `ValueCard`/`AlpacaAccountCard` at
  320/375/430dp and at 1.0x/1.3x text scale (`test/widgets/alpaca/
  cr234_alpaca_identity_test.dart`), including the exact $362,137.57 figure from
  Saiful's screenshot.
- [x] AMI's own `_ValueCard`/`_HoldingCard` rendering unchanged — full pre-existing
  `flutter test` suite (1575 baseline + this CR's new tests) green with no assertion
  changes to any pre-existing AMI-only test.
- [x] `flutter analyze` clean at the pre-existing baseline (11 info-level issues, 0
  errors).
- [x] Full `flutter test` green (1688/1688).
- [x] Backend: `cancelled` accepted by `AlpacaOrderLogIn`; targeted + DEF145 read-only
  guard + register-drift tests green.
- [x] Mutation check: reverting `PositionCard`'s trailing-cluster `FittedBox` guard back
  to a plain `Row` fails 4 of the overflow tests in `cr234_alpaca_identity_test.dart`
  (verified, then reverted).

Full detail, attack surface and test/mutation evidence:
`orchestration/audit/cr/CR234.architect.md`.

## Status

`in_progress` — implementation + tests landed, submitted to the CR005 audit handshake
(Tier A: brokerage-account writes via cancel, plus a user-facing consistency surface).
Not yet promoted to Alpha.
