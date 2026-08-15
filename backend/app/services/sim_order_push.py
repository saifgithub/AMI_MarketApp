"""CR187 — the resting-order book tells the user what happened to their order.

The sweep is the only thing that knows. It runs on a 300s tick whether or not
the app is open, and until this module existed the *outcome* of a resting order
reached the user only when they next opened the Portfolio screen and looked. For
a stop-loss that is the wrong shape: the fill is the most time-sensitive event
the training simulator produces, and it is the one the user is least likely to
be watching for.

CR170 registered the gap as out of scope — *"tempting, and `notification_service
.notify` exists and `price_alert_evaluator` is the working precedent, but it is a
separate consent and quota surface"* — and Saiful reopened it on 2026-08-15:
*"this is a very important part of the trading simulation as it covers how a real
brokerage house works."*

## Three events, and the two that are missing are deliberate

| event | notified | why |
|---|---|---|
| `filled` | yes | the order became a position; money moved while they were away |
| `rejected` | yes | the SYSTEM refused it, and the reason is the teaching content |
| `triggered` | yes | a stop-limit that triggers and then never fills is the classic failure of the type — a user who is not told it triggered cannot learn it |
| `expired` | **no** | the user chose the TIF. The card now dates the row and the RECENTLY CLOSED group shows it, and a handful of DAY orders would otherwise push at every session close |
| `cancelled` | **no** | the user did it, in the app, and got a toast |

The split is *things that happened to them* against *things they did*.

## Everything here is best-effort, and that direction is load-bearing

`notify()` already writes its durable row first and treats push as best-effort on
top (CR027). This module adds the second half of that discipline: **a
notification failure must never touch the fill.** The order is already stamped
`filled` and the trade row is already written by the time we get here, so an
exception raised on the way to OneSignal that propagated would abort the sweep
mid-book and leave later orders unswept — a delivery problem escalated into a
money problem. Every call is wrapped and logged.

## Dedupe is the constraint, not the caller

`source_ref` is the order id, so `uq_notifications_dedupe` on
`(user_id, type, source_ref)` makes each event at most once per order, forever —
including across an overlapping sweep or a container restart mid-tick. That is
the same guarantee `games_push` relies on, and it is why no lookback window is
needed here: unlike a settled-game beat, nothing in this module scans history. It
is called at the moment of transition and nowhere else.
"""

from __future__ import annotations

from uuid import UUID

from app.core.logging import logger
from app.services.notification_service import notify

TYPE_FILLED = "resting_order_filled"
TYPE_REJECTED = "resting_order_rejected"
TYPE_TRIGGERED = "resting_order_triggered"


def _deep_link(ticker: str) -> dict:
    """The ticker's own screen, via the route CR027 already ships.

    Not a new route: `open_holding_detail` is live in
    `mobile/lib/services/notifications/deep_link_dispatcher.dart` and opens
    `TickerDetailScreen`, so this works on every build already in the field. A
    new route string would land in the dispatcher's unknown branch and do
    nothing at all on any client that predates it.
    """
    return {"screen": "open_holding_detail", "route": "open_holding_detail",
            "ticker": ticker}


def _send(
    *,
    user_id: UUID,
    order_id: UUID,
    type: str,
    title: str,
    body: str,
    ticker: str,
) -> bool:
    """Returns whether a NEW notification was written. Never raises."""
    try:
        result = notify(
            user_id,
            type,
            title,
            body,
            _deep_link(ticker),
            source_ref=str(order_id),
        )
        return not result.was_duplicate
    except Exception:
        # The fill already happened. Losing the message is a delivery failure;
        # letting it escape would abort the sweep and leave the rest of the book
        # unchecked, which is a money failure.
        logger.exception(
            "sim_order_push_failed", order_id=str(order_id), type=type,
        )
        return False


def notify_filled(
    *, user_id: UUID, order_id: UUID, ticker: str, side: str,
    quantity: float, fill_price: float,
) -> bool:
    verb = "Bought" if str(side).lower().endswith("buy") else "Sold"
    return _send(
        user_id=user_id, order_id=order_id, type=TYPE_FILLED, ticker=ticker,
        title=f"Your {ticker} order filled",
        body=f"{verb} {quantity:g} {ticker} at ${fill_price:,.2f}.",
    )


def notify_rejected(
    *, user_id: UUID, order_id: UUID, ticker: str, side: str,
    quantity: float, reason: str,
) -> bool:
    """The reason is the message.

    A refusal with no reason is the state DEF309 was about — an order that
    disappears and teaches nothing. `cancel_reason` is non-NULL exactly when the
    system refused, and it is written to be read by a user.
    """
    return _send(
        user_id=user_id, order_id=order_id, type=TYPE_REJECTED, ticker=ticker,
        title=f"Your {ticker} order was not filled",
        body=f"{str(side).split('.')[-1].upper()} {quantity:g} {ticker} — {reason}",
    )


def notify_triggered(
    *, user_id: UUID, order_id: UUID, ticker: str, limit_price: float,
) -> bool:
    """A stop-limit's first phase.

    Worth a message on its own because of what happens next: the order is now a
    limit at a price the market may have already gone through, in which case it
    rests and never fills. A user told only about the eventual fill would never
    see the half of the mechanic the order type exists to teach.
    """
    return _send(
        user_id=user_id, order_id=order_id, type=TYPE_TRIGGERED, ticker=ticker,
        title=f"Your {ticker} stop triggered",
        body=(
            f"It is now a limit order at ${limit_price:,.2f}. "
            "It fills only if the price is there."
        ),
    )
