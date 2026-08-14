"""CR170 acceptance — the resting-order book, exercised through the real sweep.

`test_cr170_order_pricing.py` proves the arithmetic; this file proves the
arithmetic is the one that runs, and that the guards around it actually fire.
That split matters here more than usual: every guard in `sim_resting_orders.py`
is a pure function away from being testable without ever running the loop, and
a guard nothing exercises is not a guard. Three separate times this lineage has
shipped exactly that (CR173's autoplay guard, CR174's RTL guard, CR170-FE's
capability probe), so every test below drives `sweep_resting_orders()` itself.

The two that matter most, in order:

  * `test_a2_*` — the uncoachable floor. A resting order that fills without
    re-running `check_mandate_compliance` is a time-delayed bypass of a control
    the product's safety story rests on, and a 90-day TIF is a long time for a
    mandate to change underneath an order.
  * `test_a3_*` — quote quality. `current_quote` never returns None; it falls
    through to `Quote(price=0.01, source="unavailable")`, and $0.01 is below
    every plausible buy limit AND every sell stop, so one provider outage would
    fire the entire book in both directions at once.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select, update

from app.core.config import settings
from app.db import get_session
from app.db.models import SimRestingOrderRow, SimTradeRow
from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine
from app.services.sim_resting_orders import sweep_resting_orders
from app.trading_math.market_hours import session_close_on_or_after

ET = ZoneInfo("America/New_York")


def _expiry(order_id) -> datetime:
    with get_session() as s:
        exp = s.get(SimRestingOrderRow, order_id).expires_at
    return exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)


def _session_now(order_id) -> datetime:
    """A sweep time INSIDE the session the order was placed for, and before it
    expires.

    Derived from the order's own `expires_at` rather than hardcoded, because
    `placed_at` is the real wall clock: a fixed date drifts past the expiry and
    every order is retired before it can trigger — which is exactly what the
    first version of this file did, silently turning eight fill assertions into
    assertions about an expired book.

    `expires_at` is always a 16:00 ET session close, so minus an hour is 15:00
    ET on a weekday — inside 09:30–16:00 by construction, whatever day it runs.
    """
    return _expiry(order_id) - timedelta(hours=1)


def _closed_now(order_id) -> datetime:
    """Outside the session, still before expiry. 16:00 ET minus 20 hours is
    20:00 ET the previous day — after that day's close, so always shut."""
    return _expiry(order_id) - timedelta(hours=20)


def _a_live_session_time() -> datetime:
    """`_session_now` without an order to derive from — acceptance 10 sweeps a
    position bracket, and nothing rests, so there is no `expires_at` to anchor
    to. Same construction, same guarantee: a 16:00 ET close minus an hour is
    15:00 ET on a weekday, inside 09:30–16:00 whatever day the suite runs."""
    return session_close_on_or_after(datetime.now(timezone.utc)) - timedelta(hours=1)


def _a_closed_time() -> datetime:
    """The `_closed_now` counterpart. 20:00 ET is after every close."""
    return session_close_on_or_after(datetime.now(timezone.utc)) - timedelta(hours=20)


class _Pinned:
    """A provider whose price and source the test controls outright."""

    name = "pinned"

    def __init__(self, prices: dict[str, float], source: str = "yfinance"):
        self.prices = {k.upper(): v for k, v in prices.items()}
        self.source = source

    def set(self, ticker: str, price: float) -> None:
        self.prices[ticker.upper()] = price

    def quote(self, ticker: str) -> Quote | None:
        t = ticker.upper()
        if t not in self.prices:
            return Quote(price=100.0, source=self.source)
        return Quote(price=self.prices[t], source=self.source)

    def history(self, *a, **k):  # pragma: no cover - unused here
        return []

    def news(self, *a, **k):  # pragma: no cover
        return []

    def earnings(self, *a, **k):  # pragma: no cover
        return None


def _mandate(**over):
    base = {"plan": "trader", "single_name_cap_pct": 100.0, "max_open_risk_pct": 100.0}
    base.update(over)
    return hydrate_coach_mandate(base)


def _rows(user_id):
    with get_session() as s:
        return s.execute(
            select(SimRestingOrderRow).where(SimRestingOrderRow.user_id == user_id)
        ).scalars().all()


def _trades(user_id):
    with get_session() as s:
        return s.execute(
            select(SimTradeRow).where(SimTradeRow.user_id == user_id)
        ).scalars().all()


def _rest_a_buy_limit(sim, user_id, *, ticker="AAPL", limit=90.0, **kw):
    """Rest a buy limit below the market. Returns the order row id."""
    r = sim.submit(
        user_id=user_id, ticker=ticker, side=Side.BUY, quantity=2,
        mandate=kw.pop("mandate", _mandate()),
        order_type=OrderType.LIMIT, limit_price=limit, **kw,
    )
    assert r.accepted and r.resting, "precondition: the order must have rested"
    return r.resting_order.id


# ── Acceptance 1 — the P10/DEF153 regression ───────────────────────────────


def test_a1_marketable_limit_and_market_book_the_same_price():
    """A buy limit at or above the market is already through it, so it fills on
    the same path, at the same price, with the same ruling. Before CR170 the
    limit booked at whatever the caller typed."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    mkt = sim.submit(user_id=uuid4(), ticker="AAPL", side=Side.BUY, quantity=1,
                     mandate=_mandate(), order_type=OrderType.MARKET)
    lim = sim.submit(user_id=uuid4(), ticker="AAPL", side=Side.BUY, quantity=1,
                     mandate=_mandate(), order_type=OrderType.LIMIT,
                     limit_price=110.0)  # marketable: 100 <= 110
    assert mkt.accepted and lim.accepted
    assert not mkt.resting and not lim.resting
    assert mkt.trade.entry_price == lim.trade.entry_price == 100.0
    assert mkt.compliance.passed == lim.compliance.passed


def test_a1_unmarketable_limit_rests_and_moves_no_cash():
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    before = sim.ensure_portfolio(user_id).current_cash
    r = sim.submit(user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=2,
                   mandate=_mandate(), order_type=OrderType.LIMIT, limit_price=90.0)
    assert r.accepted and r.resting and r.trade is None
    assert sim.ensure_portfolio(user_id).current_cash == before
    assert _trades(user_id) == []


# ── Acceptance 2 — the uncoachable floor, re-run AT FILL ───────────────────


def test_a2_a_mandate_that_blocklists_the_ticker_before_the_trigger_refuses():
    """The most important requirement in the CR. The order was legal when
    placed and is not legal now; the floor is specified uncoachable, so a delay
    must not be a way around it."""
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id, limit=90.0)

    # The mandate changes underneath the resting order. Set on `compliance`
    # directly — `hydrate_coach_mandate` takes no flat `ticker_blocklist`, and
    # passing one silently produced a mandate that blocked NOTHING, which made
    # this test pass a fill and call it a refusal.
    blocked = _mandate()
    blocked.compliance.ticker_blocklist = ["AAPL"]
    import app.services.sim_resting_orders as sro
    orig = sro.resolve_mandate
    sro.resolve_mandate = lambda uid, override: blocked
    try:
        prov.set("AAPL", 89.0)  # triggers
        stats = sweep_resting_orders(user_id=user_id, now=_session_now(order_id), engine=sim)
    finally:
        sro.resolve_mandate = orig

    assert stats["rejected"] == 1 and stats["filled"] == 0
    row = next(r for r in _rows(user_id) if r.id == order_id)
    assert row.state == "rejected"
    assert row.cancel_reason, "the refusal must carry the violation sentence"
    assert _trades(user_id) == [], "a refused fill must write NO trade row"


def test_a2_an_unchanged_mandate_still_fills():
    """Vacuity guard for the test above — if nothing ever filled, the blocklist
    assertion would pass for the wrong reason."""
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id, limit=90.0)
    prov.set("AAPL", 89.0)
    stats = sweep_resting_orders(user_id=user_id, now=_session_now(order_id), engine=sim)
    assert stats["filled"] == 1 and stats["rejected"] == 0
    assert len(_trades(user_id)) == 1


# ── Acceptance 3 — quote quality, the highest-severity item ────────────────


def test_a3_the_unavailable_sentinel_fires_nothing():
    """`Quote(price=0.01, source="unavailable")` is below every buy limit AND
    every sell stop. Without the guard, one outage fills the whole book."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}, source="unavailable"))
    user_id = uuid4()
    # Rest it while the provider still looks healthy.
    sim._provider = _Pinned({"AAPL": 100.0})
    order_id = _rest_a_buy_limit(sim, user_id, limit=90.0)
    sim._provider = _Pinned({"AAPL": 0.01}, source="unavailable")

    stats = sweep_resting_orders(user_id=user_id, now=_session_now(order_id), engine=sim)
    assert stats["filled"] == 0
    row = next(r for r in _rows(user_id) if r.id == order_id)
    assert row.state == "working"
    assert row.last_seen_price is None, \
        "a $0.01 sentinel must never be stamped as a price the user is shown"


def test_a3_mock_walk_fills_nothing_when_real_data_is_expected(monkeypatch):
    """Under USE_REAL_MARKET_DATA a mock_walk source means Yahoo fell through —
    a degraded state. Booking a real ledger off a random walk is a fiction that
    never comes off the books."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id, limit=90.0)
    monkeypatch.setattr(settings, "use_real_market_data", True)
    sim._provider = _Pinned({"AAPL": 89.0}, source="mock_walk")

    stats = sweep_resting_orders(user_id=user_id, now=_session_now(order_id), engine=sim)
    assert stats["filled"] == 0


def test_a3_mock_walk_is_fine_when_mock_is_the_intended_provider(monkeypatch):
    """The mirror of the test above — with real data off, mock_walk IS the
    configured provider and refusing it would break every dev environment."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id, limit=90.0)
    monkeypatch.setattr(settings, "use_real_market_data", False)
    sim._provider = _Pinned({"AAPL": 89.0}, source="mock_walk")

    stats = sweep_resting_orders(user_id=user_id, now=_session_now(order_id), engine=sim)
    assert stats["filled"] == 1


def test_a3_circuit_breaker_aborts_when_most_of_the_book_is_unreadable():
    """A partial-outage sweep that fills half the book is worse than one that
    fills none."""
    prov = _Pinned({"AAPL": 100.0, "MSFT": 100.0, "NVDA": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    for t in ("AAPL", "MSFT", "NVDA"):
        order_id = _rest_a_buy_limit(sim, user_id, ticker=t, limit=90.0)

    class _MostlyBroken(_Pinned):
        def quote(self, ticker):
            if ticker.upper() == "AAPL":
                return Quote(price=89.0, source="yfinance")
            return Quote(price=0.01, source="unavailable")

    sim._provider = _MostlyBroken({})
    stats = sweep_resting_orders(user_id=user_id, now=_session_now(order_id), engine=sim)
    assert stats["aborted"] == 1
    assert stats["filled"] == 0, \
        "AAPL was fillable and must NOT fill — the abort is the whole point"


# ── Acceptance 4 — idempotency and the reaper ──────────────────────────────


def test_a4_sweeping_the_same_triggered_order_twice_writes_one_trade():
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id, limit=90.0)
    prov.set("AAPL", 89.0)

    sweep_resting_orders(user_id=user_id, now=_session_now(order_id), engine=sim)
    sweep_resting_orders(user_id=user_id, now=_session_now(order_id), engine=sim)

    assert len(_trades(user_id)) == 1


def test_a4_a_stale_claim_is_rejected_and_never_refilled():
    """Claim-first leaves an interrupted fill visible in `filling` rather than
    back in `working` to be filled twice. The reaper reports it; it must never
    retry a money-moving operation whose outcome is unknown."""
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id, limit=90.0)

    # Simulate a crash between the fill and the stamp.
    stale = datetime.now(timezone.utc) - timedelta(minutes=30)
    with get_session() as s:
        s.execute(update(SimRestingOrderRow)
                  .where(SimRestingOrderRow.id == order_id)
                  .values(state="filling", claimed_at=stale))

    prov.set("AAPL", 89.0)
    stats = sweep_resting_orders(user_id=user_id, now=_session_now(order_id), engine=sim)

    assert stats["reaped"] == 1
    row = next(r for r in _rows(user_id) if r.id == order_id)
    assert row.state == "rejected"
    assert _trades(user_id) == [], "a reaped claim must never be re-filled"


# ── Acceptance 5 — the separate-table decision, pinned ─────────────────────


def test_a5_a_working_resting_sell_writes_no_trade_row():
    """`def110_backfill` derives expected holdings by subtracting Σ quantity
    over status='open' SELL rows. A working resting sell living in `sim_trades`
    would subtract shares that never moved, and the phantom-share detector
    would report false positives across every user."""
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    sim.submit(user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=10,
               mandate=_mandate(), order_type=OrderType.MARKET)
    before = len(_trades(user_id))

    r = sim.submit(user_id=user_id, ticker="AAPL", side=Side.SELL, quantity=5,
                   mandate=_mandate(), order_type=OrderType.LIMIT,
                   limit_price=200.0)  # above the market → rests
    assert r.resting
    assert len(_trades(user_id)) == before, \
        "a working resting SELL must add no sim_trades row"


# ── Acceptance 9 — market hours ────────────────────────────────────────────


def test_a9_a_triggered_mark_outside_the_session_fills_nothing():
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id, limit=90.0)
    prov.set("AAPL", 89.0)

    stats = sweep_resting_orders(user_id=user_id, now=_closed_now(order_id), engine=sim)
    assert stats["filled"] == 0 and stats["skipped_closed"] == 1
    assert next(r for r in _rows(user_id) if r.id == order_id).state == "working"


def test_a9_the_expiry_pass_still_runs_on_a_closed_sunday():
    """An order dies at its session close whether or not the market is open
    when we notice. Gating expiry would leave dead orders looking alive all
    weekend."""
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id, limit=90.0)
    # Capture the closed-market moment BEFORE moving the expiry, since
    # `_closed_now` derives from `expires_at` and would otherwise chase it.
    closed = _closed_now(order_id)
    with get_session() as s:
        s.execute(update(SimRestingOrderRow)
                  .where(SimRestingOrderRow.id == order_id)
                  .values(expires_at=closed - timedelta(days=1)))

    stats = sweep_resting_orders(user_id=user_id, now=closed, engine=sim)
    assert stats["expired"] == 1
    row = next(r for r in _rows(user_id) if r.id == order_id)
    assert row.state == "expired"
    assert row.cancel_reason, "the system retired it, so it owes a reason"


# ── Acceptance 10 — the SHIPPED bracket, fired without a client ────────────


def test_a10_a_stopped_out_position_closes_from_the_tick_with_no_client_call():
    """*"A stop-loss that only fires when you open the app is not a stop-loss."*

    This is the one acceptance in the CR that is not about the new table at
    all. `SimTradeRow.stop`/`.target` shipped long before CR170 and were only
    ever evaluated by `POST /v1/sim/trades/{id}/evaluate`, i.e. on app open —
    so an audience asleep 22:30–05:00 local held every overnight loss in full.

    The book is deliberately EMPTY here. Nothing rests, so the close can only
    have come from `_sweep_position_brackets`, and `sweep_resting_orders`
    returns early on an empty book — which means this also pins that the
    bracket pass runs BEFORE that early return, not after it.
    """
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    r = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=2,
        mandate=_mandate(), order_type=OrderType.MARKET, stop=90.0, target=120.0,
    )
    assert r.accepted and not r.resting, "precondition: a plain open position"
    assert _rows(user_id) == [], "precondition: nothing in the resting book"

    prov.set("AAPL", 88.0)
    stats = sweep_resting_orders(
        user_id=user_id, now=_a_live_session_time(), engine=sim,
    )

    assert stats["brackets_closed"] == 1
    assert stats["checked"] == 0, "no resting order was involved in this close"
    trade = _trades(user_id)[0]
    assert trade.status == "lost"
    assert float(trade.closed_price) == 88.0


def test_a10_the_bracket_sweep_is_market_hours_gated_like_everything_else():
    """Same position, same broken price, a clock outside the session. A stop
    evaluated against a stale last print is CR109 §5.1's time machine — the
    overnight gap resolves at the NEXT open, not at 03:00."""
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=2,
        mandate=_mandate(), order_type=OrderType.MARKET, stop=90.0, target=120.0,
    )
    prov.set("AAPL", 88.0)

    stats = sweep_resting_orders(
        user_id=user_id, now=_a_closed_time(), engine=sim,
    )

    assert stats["skipped_closed"] == 1
    assert stats["brackets_closed"] == 0
    assert _trades(user_id)[0].status == "open"


def test_a10_the_unscoped_tick_reaches_a_user_it_was_not_told_about():
    """`user_id=None` is how the 5-minute tick calls it, and it is the only
    call shape that fires while the user is asleep. Scoped sweeps are proven
    above; this proves the sweep FINDS the user on its own — a
    `_users_with_open_trades` that returned nothing would leave every test
    above green and the feature dead in production."""
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=2,
        mandate=_mandate(), order_type=OrderType.MARKET, stop=90.0, target=120.0,
    )
    prov.set("AAPL", 88.0)

    sweep_resting_orders(user_id=None, now=_a_live_session_time(), engine=sim)

    assert _trades(user_id)[0].status == "lost"


# ── Acceptance 11 — post-fill effects reach the sweep's fills ──────────────


def test_a11_a_resting_buy_with_a_bracket_earns_trade_disciplined():
    """The §7 extraction's whole purpose: the sweep's fill gets the same
    watchlist / journal / reputation treatment the ticket's fill gets."""
    from sqlalchemy import select as _select
    from app.db.models import ReputationEventRow
    from app.services.auth_service import AuthService

    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    # A REAL user row, not a bare uuid4: `_award_disciplined` swallows its own
    # exception (correctly — the money has already moved by then), so an FK
    # failure on `reputation_events.user_id` is indistinguishable from "the
    # award was never attempted". Every other test here is unaffected because
    # nothing else writes a user-scoped row outside the sim tables.
    user, _, _ = AuthService().ensure_anonymous(device_user_id=None)
    user_id = user.id
    order_id = _rest_a_buy_limit(sim, user_id, limit=90.0, stop=80.0, target=120.0)
    prov.set("AAPL", 89.0)
    sweep_resting_orders(user_id=user_id, now=_session_now(order_id), engine=sim)

    with get_session() as s:
        awards = s.execute(_select(ReputationEventRow).where(
            ReputationEventRow.user_id == user_id,
            ReputationEventRow.event_type == "trade_disciplined",
        )).scalars().all()
    assert len(awards) == 1


def test_a4_the_claim_itself_is_the_duplicate_guard_not_the_query():
    """The CR is explicit: *"the state transition is the duplicate guard, not
    the Python loop"*. `test_a4_sweeping_..._twice` does NOT prove that — after
    the first fill the order is `filled`, so `_live_orders` never returns it
    again and the query does the work. Deleting the claim's `WHERE state IN
    (...)` therefore left that test green.

    This one races the claim directly: two sweeps that both saw the same
    `working` row must not both win it.
    """
    import app.services.sim_resting_orders as sro

    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id, limit=90.0)
    now = _session_now(order_id)

    first = sro._claim(order_id, now)
    second = sro._claim(order_id, now)

    assert first is True, "the first sweep to reach it must win the claim"
    assert second is False, (
        "an overlapping sweep, a concurrent user cancel and a racing /evaluate "
        "all have to LOSE here — rowcount is the claim"
    )


def test_a4_a_claimed_order_is_invisible_to_the_next_sweep():
    """`filling` is excluded from `_live_orders`, so a fill in flight cannot be
    picked up a second time even before it lands."""
    import app.services.sim_resting_orders as sro

    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id, limit=90.0)
    assert [o.id for o in sro._live_orders(user_id)] == [order_id]

    sro._claim(order_id, _session_now(order_id))
    assert sro._live_orders(user_id) == []
