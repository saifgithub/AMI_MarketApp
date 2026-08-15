"""CR187 — the sweep tells the user what happened to their order.

Every test drives `sweep_resting_orders()` and then reads the `notifications`
table. That is the point: the sweep is the ONLY thing that knows a resting order
filled, and the notification is the only channel that reaches a user who is not
looking at the Portfolio screen. Asserting on `sim_order_push.notify_filled`
directly would prove the copy and say nothing about whether the sweep ever calls
it — which is exactly the half that was missing for the whole life of CR170.

The deliberate absences get tests too. An expiry and a user cancel must NOT
notify, and a test that only checked the positives would let a later change turn
every DAY order's session close into a push.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from app.db import get_session
from app.db.models import NotificationRow, SimRestingOrderRow
from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine
from app.services.sim_order_push import (
    TYPE_FILLED,
    TYPE_REJECTED,
    TYPE_TRIGGERED,
)
from app.services.sim_resting_orders import sweep_resting_orders


class _Pinned:
    def __init__(self, prices: dict[str, float], source: str = "yfinance"):
        self.prices = {k.upper(): v for k, v in prices.items()}
        self.source = source

    def quote(self, ticker: str) -> Quote | None:
        return Quote(price=self.prices.get(ticker.upper(), 100.0), source=self.source)

    def history(self, *a, **k):  # pragma: no cover
        return []

    def news(self, *a, **k):  # pragma: no cover
        return []

    def earnings(self, *a, **k):  # pragma: no cover
        return None


def _mandate(**over):
    base = {"plan": "trader", "single_name_cap_pct": 100.0, "max_open_risk_pct": 100.0}
    base.update(over)
    return hydrate_coach_mandate(base)


def _notes(user_id, type_: str | None = None) -> list[NotificationRow]:
    with get_session() as s:
        stmt = select(NotificationRow).where(NotificationRow.user_id == user_id)
        if type_ is not None:
            stmt = stmt.where(NotificationRow.type == type_)
        return list(s.execute(stmt).scalars().all())


def _row(order_id) -> SimRestingOrderRow:
    with get_session() as s:
        return s.get(SimRestingOrderRow, order_id)


def _expiry(order_id) -> datetime:
    exp = _row(order_id).expires_at
    return exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)


def _session_now(order_id) -> datetime:
    return _expiry(order_id) - timedelta(hours=1)


def _rest(sim, user_id, **kw):
    r = sim.submit(
        user_id=user_id, ticker=kw.pop("ticker", "AAPL"),
        side=kw.pop("side", Side.BUY), quantity=kw.pop("quantity", 2),
        mandate=kw.pop("mandate", _mandate()), **kw,
    )
    assert r.accepted and r.resting, "precondition: the order must have rested"
    return r.resting_order.id


# ── The events that reach the user ─────────────────────────────────────────


def test_a_fill_notifies_the_owner():
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    order_id = _rest(sim, user_id, order_type=OrderType.LIMIT, limit_price=90.0)
    prov.prices["AAPL"] = 85.0

    sweep_resting_orders(user_id=user_id, now=_session_now(order_id), engine=sim)

    assert _row(order_id).state == "filled"
    notes = _notes(user_id, TYPE_FILLED)
    assert len(notes) == 1
    assert notes[0].source_ref == str(order_id)
    assert "AAPL" in notes[0].title
    # The price is the fact the user is away from the app for.
    assert "90.00" in notes[0].body


def test_a_refusal_notifies_with_the_reason():
    """The reason IS the message. A refusal with no reason is the state the
    book was in before DEF309 — an order that disappears and teaches nothing."""
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    order_id = _rest(sim, user_id, order_type=OrderType.LIMIT, limit_price=90.0)
    prov.prices["AAPL"] = 85.0

    blocked = _mandate()
    blocked.compliance.ticker_blocklist = ["AAPL"]
    import app.services.sim_resting_orders as sro
    orig = sro.resolve_mandate
    sro.resolve_mandate = lambda uid, override: blocked
    try:
        sweep_resting_orders(user_id=user_id, now=_session_now(order_id), engine=sim)
    finally:
        sro.resolve_mandate = orig

    assert _row(order_id).state == "rejected"
    notes = _notes(user_id, TYPE_REJECTED)
    assert len(notes) == 1
    assert _row(order_id).cancel_reason in notes[0].body


def test_a_stop_limit_trigger_notifies_once_however_many_sweeps_run():
    """The trigger is worth its own message because of what happens next: the
    order is now a limit at a price the market may have already gone through,
    and a user told only about the eventual fill would never see the half of the
    mechanic the type exists to teach.

    Once, though. The sweep re-reads a triggered order on every tick, so
    notifying on "we are past the trigger" rather than "we just crossed it"
    would push every five minutes for as long as the order lives.
    """
    prov = _Pinned({"NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    sim.ensure_portfolio(user_id)
    sim.submit(user_id=user_id, ticker="NVDA", side=Side.BUY, quantity=5,
               mandate=_mandate(), order_type=OrderType.MARKET)
    order_id = _rest(
        sim, user_id, ticker="NVDA", side=Side.SELL, quantity=5,
        order_type=OrderType.STOP_LIMIT, trigger_price=90.0, limit_price=88.0,
    )
    # Gaps straight through the limit: triggers, then rests unfilled. The
    # classic stop-limit failure, and the case the message is for.
    prov.prices["NVDA"] = 85.0

    at = _session_now(order_id)
    sweep_resting_orders(user_id=user_id, now=at, engine=sim)
    sweep_resting_orders(user_id=user_id, now=at, engine=sim)
    sweep_resting_orders(user_id=user_id, now=at, engine=sim)

    assert _row(order_id).state == "triggered", "it must not have filled"
    assert len(_notes(user_id, TYPE_TRIGGERED)) == 1
    assert len(_notes(user_id, TYPE_FILLED)) == 0


def test_the_same_fill_never_notifies_twice():
    """`uq_notifications_dedupe` on (user, type, source_ref) is the guard, not
    the caller — so an overlapping sweep or a restart mid-tick cannot double-send.
    """
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    order_id = _rest(sim, user_id, order_type=OrderType.LIMIT, limit_price=90.0)
    prov.prices["AAPL"] = 85.0
    at = _session_now(order_id)

    sweep_resting_orders(user_id=user_id, now=at, engine=sim)
    from app.services.sim_order_push import notify_filled
    # A second delivery attempt for the same order, as a re-entrant sweep would
    # make it.
    fresh = notify_filled(
        user_id=user_id, order_id=order_id, ticker="AAPL", side="buy",
        quantity=2, fill_price=90.0,
    )

    assert fresh is False
    assert len(_notes(user_id, TYPE_FILLED)) == 1


# ── The deliberate absences ────────────────────────────────────────────────


def test_an_expiry_does_not_notify():
    """The user chose the TIF. The card dates the row and the RECENTLY CLOSED
    group shows it; a handful of DAY orders would otherwise push at every
    session close, which is the noise that gets notifications turned off."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    order_id = _rest(sim, user_id, order_type=OrderType.LIMIT, limit_price=90.0)
    with get_session() as s:
        row = s.get(SimRestingOrderRow, order_id)
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    sweep_resting_orders(user_id=user_id, engine=sim)

    assert _row(order_id).state == "expired"
    assert _notes(user_id) == []


def test_a_user_cancel_does_not_notify():
    """They did it, in the app, and got a toast on the same tap. The split is
    things that happened TO them against things they did."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    order_id = _rest(sim, user_id, order_type=OrderType.LIMIT, limit_price=90.0)

    cancelled, _ = sim.cancel_resting_order(user_id, order_id)

    assert cancelled
    assert _notes(user_id) == []


# ── Delivery must never reach the ledger ───────────────────────────────────


def test_a_notification_failure_does_not_break_the_fill():
    """The order is stamped and the trade row is written before this module is
    reached. An exception escaping on the way to OneSignal would abort the sweep
    mid-book and leave later orders unswept — a delivery problem escalated into
    a money problem."""
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    order_id = _rest(sim, user_id, order_type=OrderType.LIMIT, limit_price=90.0)
    prov.prices["AAPL"] = 85.0

    import app.services.sim_order_push as push
    orig = push.notify

    def _boom(*a, **k):
        raise RuntimeError("onesignal is down")

    push.notify = _boom
    try:
        stats = sweep_resting_orders(
            user_id=user_id, now=_session_now(order_id), engine=sim,
        )
    finally:
        push.notify = orig

    assert stats["filled"] == 1
    assert _row(order_id).state == "filled"
    assert _row(order_id).filled_trade_id is not None


def test_the_deep_link_uses_a_route_the_shipped_client_knows():
    """`open_holding_detail` is live in the Flutter dispatcher today. A new
    route string would land in its unknown branch and do nothing at all on every
    build already in the field — a push that opens the app to nowhere."""
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    order_id = _rest(sim, user_id, order_type=OrderType.LIMIT, limit_price=90.0)
    prov.prices["AAPL"] = 85.0

    sweep_resting_orders(user_id=user_id, now=_session_now(order_id), engine=sim)

    link = _notes(user_id, TYPE_FILLED)[0].deep_link
    assert link["route"] == "open_holding_detail"
    assert link["ticker"] == "AAPL"
