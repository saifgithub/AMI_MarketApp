"""DEF309 — a closed order can be dated, so the recent-history window works.

`SimEngine.list_resting_orders` includes terminal rows from the last 24h so a
refusal is never invisible. It measured that window with
`(filled_at or placed_at) >= terminal_since`, and `filled_at` is set on exactly
ONE of the four exits — so cancelled, expired and rejected orders fell back to
*when they were placed*. `test_the_window_*` below is the defect: a GTD-90 order
placed four days ago and refused at fill a minute ago was filtered out of its
own 24h window, and the longer an order had rested the more certainly its
refusal was hidden.

The other half of the file is why the fix is a helper rather than five edits.
Five call sites retire an order and each was a place to forget the timestamp, so
they all route through `retire_values` — and `test_every_exit_*` drives all five
through the real sweep rather than reading them, because a stamp nothing
exercises is the same class of thing as a guard nothing exercises (the failure
`test_cr170_resting_orders.py`'s own docstring records three times in this
lineage).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from app.db import get_session
from app.db.models import SimRestingOrderRow
from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote
from app.services.sim_engine import (
    TERMINAL_RESTING_STATES,
    SimEngine,
    retire_values,
)
from app.services.sim_resting_orders import sweep_resting_orders


class _Pinned:
    def __init__(self, prices: dict[str, float], source: str = "yfinance"):
        self.prices = {k.upper(): v for k, v in prices.items()}
        self.source = source

    def quote(self, ticker: str) -> Quote | None:
        return Quote(price=self.prices.get(ticker.upper(), 100.0), source=self.source)

    def history(self, *a, **k):  # pragma: no cover - unused
        return []

    def news(self, *a, **k):  # pragma: no cover
        return []

    def earnings(self, *a, **k):  # pragma: no cover
        return None


def _mandate(**over):
    base = {"plan": "trader", "single_name_cap_pct": 100.0, "max_open_risk_pct": 100.0}
    base.update(over)
    return hydrate_coach_mandate(base)


def _row(order_id) -> SimRestingOrderRow:
    with get_session() as s:
        return s.get(SimRestingOrderRow, order_id)


def _set(order_id, **values) -> None:
    with get_session() as s:
        s.execute(
            update(SimRestingOrderRow)
            .where(SimRestingOrderRow.id == order_id)
            .values(**values)
        )


def _rest_a_buy_limit(sim, user_id, *, ticker="AAPL", limit=90.0):
    r = sim.submit(
        user_id=user_id, ticker=ticker, side=Side.BUY, quantity=2,
        mandate=_mandate(), order_type=OrderType.LIMIT, limit_price=limit,
    )
    assert r.accepted and r.resting, "precondition: the order must have rested"
    return r.resting_order.id


def _session_now(order_id) -> datetime:
    """Inside the session the order was placed for, before it expires. Lifted
    from `test_cr170_resting_orders.py` for the same reason it exists there: a
    hardcoded date drifts past `expires_at` and every order retires before it
    can trigger, silently turning fill assertions into expiry assertions."""
    exp = _row(order_id).expires_at
    exp = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
    return exp - timedelta(hours=1)


# ── The defect ─────────────────────────────────────────────────────────────


def test_the_window_shows_a_refusal_on_an_order_older_than_the_window():
    """The defect, stated as the case that matters most.

    A GTD-90 order rests for days, is refused at fill this minute, and the user
    opens the app. Keyed on `placed_at` it is filtered out — the compliance
    sentence explaining why their order died is the one guaranteed to be hidden,
    because it is the orders that waited longest that accumulate the mandate
    changes that refuse them.
    """
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id)

    four_days_ago = datetime.now(timezone.utc) - timedelta(days=4)
    _set(order_id, placed_at=four_days_ago)
    _set(order_id, **retire_values(
        "rejected", datetime.now(timezone.utc),
        cancel_reason="AAPL is on your blocklist",
    ))

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    listed = sim.list_resting_orders(user_id, terminal_since=since)
    assert [o.id for o in listed] == [order_id]
    assert listed[0].cancel_reason == "AAPL is on your blocklist"


def test_the_window_still_excludes_an_order_that_retired_before_it():
    """Non-vacuity. The fix must not be "show everything" — a row that really
    did retire outside the window still goes, or the group heading lies and the
    list grows without bound."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id)
    _set(order_id, **retire_values(
        "cancelled", datetime.now(timezone.utc) - timedelta(days=3),
    ))

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    assert sim.list_resting_orders(user_id, terminal_since=since) == []


def test_a_live_order_is_never_windowed_out_however_old():
    """A working order is not history and is not subject to the window at all —
    a 90-day order placed 89 days ago is the most live thing on the screen."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id)
    _set(order_id, placed_at=datetime.now(timezone.utc) - timedelta(days=89))

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    listed = sim.list_resting_orders(user_id, terminal_since=since)
    assert [o.id for o in listed] == [order_id]


def test_a_terminal_row_predating_the_column_is_shown_not_hidden():
    """The migration backfills every existing terminal row, so this should be
    unreachable — and if it ever is reached, the failure direction is the one
    that is visible. Hiding is what the defect was."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id)
    _set(order_id, state="expired", retired_at=None,
         placed_at=datetime.now(timezone.utc) - timedelta(days=30))

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    assert [o.id for o in sim.list_resting_orders(user_id, terminal_since=since)] \
        == [order_id]


# ── Every exit stamps it, driven through the real paths ────────────────────


def test_every_exit_fill_stamps_retired_at():
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id, limit=90.0)
    prov.prices["AAPL"] = 85.0  # through the limit

    sweep_resting_orders(user_id=user_id, now=_session_now(order_id), engine=sim)

    row = _row(order_id)
    assert row.state == "filled"
    assert row.retired_at is not None


def test_every_exit_user_cancel_stamps_retired_at():
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id)

    cancelled, order = sim.cancel_resting_order(user_id, order_id)

    assert cancelled and order.state == "cancelled"
    assert order.retired_at is not None
    # The invariant the client's copy is built on survives the change: a user
    # cancel leaves NO reason, so "you did this" stays distinguishable from
    # "this was taken away from you".
    assert order.cancel_reason is None


def test_every_exit_expiry_stamps_retired_at():
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id)
    _set(order_id, expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))

    sweep_resting_orders(user_id=user_id, engine=sim)

    row = _row(order_id)
    assert row.state == "expired"
    assert row.retired_at is not None


def test_every_exit_refusal_at_fill_stamps_retired_at():
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id, limit=90.0)
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

    row = _row(order_id)
    assert row.state == "rejected"
    assert row.retired_at is not None
    assert row.cancel_reason  # the system refused, and says why


def test_every_exit_stale_claim_reap_stamps_retired_at():
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id)
    _set(order_id, state="filling",
         claimed_at=datetime.now(timezone.utc) - timedelta(hours=2))

    sweep_resting_orders(user_id=user_id, engine=sim)

    row = _row(order_id)
    assert row.state == "rejected"
    assert row.retired_at is not None


# ── The helper's own guard ─────────────────────────────────────────────────


@pytest.mark.parametrize("state", ["working", "triggered", "filling"])
def test_retire_values_refuses_a_state_that_is_not_an_exit(state):
    """`retired_at` means *left the book*. Stamping it on a `filling` order
    would date an order that is still mid-fill, and the client reads the
    presence of that timestamp as "this is history"."""
    with pytest.raises(ValueError):
        retire_values(state, datetime.now(timezone.utc))


@pytest.mark.parametrize("state", TERMINAL_RESTING_STATES)
def test_retire_values_stamps_every_terminal_state(state):
    out = retire_values(state, datetime(2026, 8, 15, tzinfo=timezone.utc))
    assert out["state"] == state
    assert out["retired_at"] == datetime(2026, 8, 15, tzinfo=timezone.utc)


def test_retired_at_reaches_the_wire():
    """`to_json` is the client's only source. The client dates its RECENTLY
    CLOSED group off this field, so a value that stops at the DTO is the same
    outage as one that was never stamped."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    order_id = _rest_a_buy_limit(sim, user_id)
    _, order = sim.cancel_resting_order(user_id, order_id)

    assert order.to_json()["retired_at"] is not None
