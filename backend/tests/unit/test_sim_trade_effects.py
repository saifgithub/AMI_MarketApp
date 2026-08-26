"""CR170 §7 — `apply_post_fill_effects` outside the route.

`test_sim_reputation.py` already pins the effects as reached *through*
`POST /v1/sim/submit`, and it still passes unchanged — that is the
behaviour-neutral half of this extraction. These tests pin the half that
extraction was FOR: the same three effects, reached with no HTTP request in the
call stack, which is how the resting-order sweep will reach them.

The load-bearing assertion is `test_award_reads_the_trade_not_a_request`. The
route decided `trade_disciplined` from `req.stop`/`req.target` — the values on
the *request being handled*. A sweep has no request; a resting order carries its
bracket from placement, days earlier. Reading the trade is what makes the two
paths the same rule rather than two rules that happen to agree today.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import ReputationEventRow
from app.schemas.trade import Side
from app.services.auth_service import AuthService
from app.services.sim_engine import SimTrade
from app.services.sim_trade_effects import apply_post_fill_effects
from app.services.watchlist_store import get_watchlist_store


@pytest.fixture
def user_id():
    auth = AuthService()
    user, _, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id


def _trade(user_id, *, side=Side.BUY, stop=95.0, target=120.0, ticker="AAPL"):
    return SimTrade(
        id=uuid4(),
        user_id=user_id,
        portfolio_id=uuid4(),
        ticker=ticker,
        side=side,
        quantity=3,
        entry_price=100.0,
        stop=stop,
        target=target,
        horizon_days=None,
        opened_at=datetime.now(timezone.utc),
    )


def _awards(user_id):
    with get_session() as s:
        return s.execute(
            select(ReputationEventRow).where(
                ReputationEventRow.user_id == user_id,
                ReputationEventRow.event_type == "trade_disciplined",
            )
        ).scalars().all()



def test_no_award_without_a_target(user_id):
    apply_post_fill_effects(user_id=user_id, trade=_trade(user_id, target=None))
    assert _awards(user_id) == []


def test_no_award_without_a_stop(user_id):
    apply_post_fill_effects(user_id=user_id, trade=_trade(user_id, stop=None))
    assert _awards(user_id) == []


def test_a_sell_is_never_disciplined(user_id):
    apply_post_fill_effects(user_id=user_id, trade=_trade(user_id, side=Side.SELL))
    assert _awards(user_id) == []



def test_the_ticker_lands_on_the_watchlist(user_id):
    apply_post_fill_effects(user_id=user_id, trade=_trade(user_id, ticker="MSFT"))
    tickers = {w.ticker for w in get_watchlist_store().list_for_user(user_id)}
    assert "MSFT" in tickers


def test_a_failing_journal_does_not_cost_the_watchlist_add(user_id, monkeypatch):
    """Independent try/excepts per effect — inherited from the route and
    deliberately kept. The money has already moved by the time any of this
    runs, so one failing effect must not silently swallow another.

    **Re-aimed, not deleted (CR109 slice 7).** This asserted that a raising
    journal store could not cost the user their `trade_disciplined` reputation
    award. That award is gone with the league it scored for — but the property
    the test was actually protecting is the ISOLATION between the effects, and
    that survives the award. Deleting it would have retired a live guarantee
    because the example it happened to use went away.
    """
    import app.services.sim_trade_effects as effects

    def _boom():
        raise RuntimeError("journal is down")

    monkeypatch.setattr(effects, "get_journal_store", _boom)
    apply_post_fill_effects(user_id=user_id, trade=_trade(user_id))
    tickers = {w.ticker for w in get_watchlist_store().list_for_user(user_id)}
    assert "AAPL" in tickers
