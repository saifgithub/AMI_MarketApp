# CR187 — the resting-order book tells the user what happened

**Filed:** 2026-08-15 (AT:R70) · **Status:** in_progress (backend complete) · **Follows:** CR170, CR186, DEF309

Saiful, on the scope call for the resting-order display work: *"this is a very important part of the
trading simulation as it covers how a real brokerage house works. We must get this working today."*

---

## Why

The sweep is the only thing that knows. It runs on a 300s tick whether or not the app is open, and
until now the **outcome** of a resting order reached the user only when they next opened the
Portfolio screen and looked.

For a stop-loss that is the wrong shape. The fill is the most time-sensitive event the training
simulator produces, and it is the one the user is least likely to be watching for.

CR170 registered the gap and deferred it — *"tempting, and `notification_service.notify` exists and
`price_alert_evaluator` is the working precedent, but it is a separate consent and quota surface. The
obvious follow-up; one line here, not in the build."* This is that follow-up.

---

## Three events, and the two that are missing are deliberate

| event | notified | why |
|---|---|---|
| `filled` | **yes** | the order became a position; money moved while they were away |
| `rejected` | **yes** | the system refused it, and the reason is the teaching content |
| `triggered` | **yes** | a stop-limit that triggers and then never fills is the classic failure of the type — a user who is not told it triggered cannot learn it |
| `expired` | no | the user chose the TIF. CR186's card dates the row and the RECENTLY CLOSED group shows it; a handful of DAY orders would otherwise push at every session close |
| `cancelled` | no | the user did it, in the app, and got a toast on the same tap |

The split is **things that happened to them** against **things they did**. That is the line to hold
if a fourth event is ever proposed.

## Design decisions

- **Dedupe is the constraint, not the caller.** `source_ref` is the order id, so
  `uq_notifications_dedupe` on `(user_id, type, source_ref)` makes each event at most once per order,
  forever — across an overlapping sweep, a `/evaluate` racing the tick, or a container restart
  mid-tick. Same guarantee `games_push` relies on.
- **No lookback window, unlike `games_push`.** That module needs `SETTLED_LOOKBACK` because it scans
  history and would otherwise push every historical close on its first tick. Nothing here scans:
  every call sits at the moment of transition. Worth stating, because the absence looks like an
  omission next to the sibling module.
- **`_stamp_triggered` now returns whether it made the transition.** The sweep re-reads a triggered
  stop-limit on every tick until it fills or dies, so notifying on *"we are past the trigger"* rather
  than *"we just crossed it"* would push once every five minutes for as long as the order lives. The
  conditional UPDATE's `rowcount` is the answer, exactly as it is in `_claim`.
- **Everything is best-effort, and the direction is load-bearing.** The order is stamped and the
  trade row written before this module is reached, so an exception escaping on the way to OneSignal
  would abort the sweep mid-book and leave later orders unswept — a delivery problem escalated into a
  money problem. Every call is wrapped and logged, and the fill notification is deliberately the
  **last** statement in its block.
- **The deep link uses `open_holding_detail`**, which is live in the Flutter dispatcher today. A new
  route string would land in its unknown branch and do nothing at all on every build already in the
  field.
- **No new config setting**, so no `docker-compose.yml` forwarding and no compose-parity surface.
  `notify()` already reports an unconfigured OneSignal key as a loud `not_configured` and still writes
  the durable row.

## Acceptance

1. A fill, a refusal and a stop-limit trigger each write exactly one notification for the owner, with
   the order id as `source_ref`.
2. A trigger notifies **once** across repeated sweeps of the same order.
3. A second delivery attempt for the same order and event returns "not fresh" and writes nothing.
4. An expiry and a user cancel write **nothing**.
5. A raising `notify` does not break the fill: the order is still `filled`, the trade row still
   exists, and the sweep still reports it.
6. The deep link names a route the shipped client already knows.

## Verification

`backend/tests/unit/test_cr187_resting_order_push.py`, 8 tests, every one driving
`sweep_resting_orders()` and then reading the `notifications` table — not calling the push helpers
directly, because the sweep being the only caller is the half that was missing for the whole life of
CR170.

**This CR found DEF310.** Acceptance 2's test sweeps three times to prove the trigger fires once, and
the third sweep filled an order that should have rested forever — a triggered stop-limit was being
evaluated against its trigger rather than its limit. Fixed under its own defect.

## Not in scope

- **Client rendering of the notification list.** CR135's territory; these rows appear there when it
  ships. The push itself works today.
- **Per-user preferences for which of the three events push.** One consent surface exists
  (`notification_service`'s own rate limits); a per-event toggle is a settings surface and a product
  decision.
- **Localised push copy.** Server-side copy is English, as every existing `notify()` caller's is.
