"""CR120 Phase 3 — opt-in pagination on GET /v1/sim/trades/{user_id}.

The contract under test:

- Both params omitted ⇒ the `trades` array is the FULL training ledger,
  exactly as before Phase 3 — the shipped client computes its across-all
  summary, tab count, and SHOW ALL count from that full list, so a default
  cap is a silent data amputation (CR040).
- `total` is ALWAYS present and counts the ledger under the same
  scope + status filter PRE-slice — reusing `training_trade_scope`, so a
  user's game fills can never inflate it (DEF269's lane firewall, extended
  to the count).
- Order is a TOTAL order: `opened_at DESC, id DESC`. `opened_at` defaults
  to _utcnow and can tie; without the id tiebreaker, pages could overlap
  or drop rows at the boundary.
- Bounds are enforced at the route (`limit` 1..500, `offset` >= 0): a
  negative limit is a silent no-op in SQLite (this fixture) and an error
  in Postgres (Alpha), so 422 here is the only place the suite can see it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.api.sim import router as sim_router
from app.db import get_session
from app.db.models import SimTradeRow
from app.schemas.trade import Side
from app.services import market_data as _md
from app.services.auth_service import AuthService
from app.services.coach_engine import hydrate_coach_mandate
from app.services.sim_engine import SimEngine


class _ConstProvider:
    name = "fake"

    def __init__(self, price: float = 100.0) -> None:
        self.price = price

    def quote(self, ticker: str):
        return _md.Quote(price=self.price, source=self.name)

    def get_price(self, ticker: str):
        return self.price

    def history(self, ticker: str, period: str):
        return None

    def news(self, ticker: str, limit: int = 5):
        return None

    def earnings(self, ticker: str):
        return None


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(sim_router)
    return TestClient(app, raise_server_exceptions=False)


def _make_user_and_token() -> tuple:
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, token


def _training_buy(sim: SimEngine, user_id, ticker: str, qty: float = 1) -> None:
    result = sim.submit(
        user_id=user_id, ticker=ticker, side=Side.BUY, quantity=qty,
        mandate=hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0}),
    )
    assert result.accepted, result.compliance.violations


def _game_buy(sim: SimEngine, user_id, run_id, ticker: str, qty: float = 1) -> None:
    result = sim.submit_game_trade(
        user_id=user_id, run_id=run_id, ticker=ticker, side=Side.BUY, quantity=qty,
    )
    assert result.accepted, result.reason


def _set_opened_at(user_id, ticker: str, when: datetime) -> None:
    with get_session() as s:
        s.execute(
            update(SimTradeRow)
            .where(SimTradeRow.user_id == user_id, SimTradeRow.ticker == ticker)
            .values(opened_at=when)
        )


def _close(sim: SimEngine, user_id, ticker: str) -> None:
    """A REAL close (shares sold, holdings updated) — a raw status flip
    trips the conftest ledger invariant, correctly."""
    with get_session() as s:
        trade_id = s.execute(
            select(SimTradeRow.id).where(
                SimTradeRow.user_id == user_id,
                SimTradeRow.ticker == ticker,
                SimTradeRow.status == "open",
            )
        ).scalar_one()
    assert sim.manual_close(user_id, trade_id) is not None


def _get(client: TestClient, user_id, token, **params):
    return client.get(
        f"/v1/sim/trades/{user_id}",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
    )


T0 = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)

# Today's wire shape of each trade dict (SimTrade.to_json) — pinned so a
# field rename cannot ship unnoticed under the new envelope.
_TRADE_KEYS = {
    "id", "user_id", "portfolio_id", "ticker", "side", "quantity",
    "entry_price", "stop", "target", "horizon_days", "opened_at",
    "closed_at", "closed_price", "status", "verdict_ref", "realised_pnl",
}


def _seed_three(user_id) -> None:
    """AAPL oldest, MSFT middle, NVDA newest — all distinct opened_at."""
    sim = SimEngine(provider=_ConstProvider(100.0))
    for i, ticker in enumerate(["AAPL", "MSFT", "NVDA"]):
        _training_buy(sim, user_id, ticker)
        _set_opened_at(user_id, ticker, T0 + timedelta(hours=i))


def test_default_call_is_the_full_ledger_with_total(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    _seed_three(user_id)

    r = _get(client, user_id, token)
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"trades", "total", "limit", "offset"}
    assert [t["ticker"] for t in body["trades"]] == ["NVDA", "MSFT", "AAPL"]
    assert body["total"] == 3
    assert body["limit"] is None
    assert body["offset"] == 0
    for t in body["trades"]:
        assert set(t.keys()) == _TRADE_KEYS


def test_limit_returns_newest_slice_but_total_stays_full(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    _seed_three(user_id)

    r = _get(client, user_id, token, limit=2)
    assert r.status_code == 200
    body = r.json()
    assert [t["ticker"] for t in body["trades"]] == ["NVDA", "MSFT"]
    assert body["total"] == 3, "total is pre-slice, not the page size"
    assert body["limit"] == 2
    assert body["offset"] == 0


def test_pages_tile_the_ledger_even_across_an_opened_at_tie(client: TestClient) -> None:
    """The defect-factory case: two rows share one opened_at, and the tie
    straddles the page boundary. Only the id tiebreaker makes the pages
    disjoint and exhaustive."""
    user_id, token = _make_user_and_token()
    sim = SimEngine(provider=_ConstProvider(100.0))
    for ticker in ["NVDA", "AAPL", "MSFT", "TSLA"]:
        _training_buy(sim, user_id, ticker)
    _set_opened_at(user_id, "NVDA", T0 + timedelta(hours=3))
    _set_opened_at(user_id, "AAPL", T0 + timedelta(hours=2))
    _set_opened_at(user_id, "MSFT", T0 + timedelta(hours=2))  # tie with AAPL
    _set_opened_at(user_id, "TSLA", T0 + timedelta(hours=1))

    full = _get(client, user_id, token).json()["trades"]
    page1 = _get(client, user_id, token, limit=2).json()["trades"]
    page2 = _get(client, user_id, token, limit=2, offset=2).json()["trades"]

    assert [t["id"] for t in page1] + [t["id"] for t in page2] == [t["id"] for t in full]
    assert not {t["id"] for t in page1} & {t["id"] for t in page2}

    # The tied pair sits at full[1:3]; its order must be id DESC (stored as
    # hex in sqlite, so hex-lexical), not whatever the engine felt like.
    tied = full[1:3]
    assert {t["ticker"] for t in tied} == {"AAPL", "MSFT"}
    assert [t["id"] for t in tied] == sorted(
        (t["id"] for t in tied), key=lambda u: UUID(u).hex, reverse=True,
    )


def test_total_is_scoped_to_training_and_the_status_filter(client: TestClient) -> None:
    """DEF269 extended to the count: game fills for the SAME user must not
    inflate `total`, and `status_filter` narrows it."""
    user_id, token = _make_user_and_token()
    sim = SimEngine(provider=_ConstProvider(100.0))
    for ticker in ["AAPL", "MSFT", "NVDA"]:
        _training_buy(sim, user_id, ticker)
    _close(sim, user_id, "NVDA")
    run_id = uuid4()
    _game_buy(sim, user_id, run_id, ticker="META")
    _game_buy(sim, user_id, run_id, ticker="AMZN")

    r = _get(client, user_id, token, limit=1)
    body = r.json()
    assert len(body["trades"]) == 1
    assert body["total"] == 3, "training rows only — game fills must not count"

    r = _get(client, user_id, token, status_filter="open", limit=1)
    body = r.json()
    assert len(body["trades"]) == 1
    assert body["trades"][0]["status"] == "open"
    assert body["total"] == 2, "the closed trade and both game fills excluded"


def test_out_of_bounds_params_are_422_not_silent(client: TestClient) -> None:
    user_id, token = _make_user_and_token()
    assert _get(client, user_id, token, limit=0).status_code == 422
    assert _get(client, user_id, token, limit=501).status_code == 422
    assert _get(client, user_id, token, offset=-1).status_code == 422


def test_forbids_reading_another_users_trades(client: TestClient) -> None:
    _user_id, token = _make_user_and_token()
    other_id, _other_token = _make_user_and_token()
    assert _get(client, other_id, token).status_code == 403


def test_empty_ledger_is_empty_with_zero_total_on_both_paths(client: TestClient) -> None:
    """Both total paths: the len() short-circuit (no params) and the real
    count query (paginated)."""
    user_id, token = _make_user_and_token()

    body = _get(client, user_id, token).json()
    assert body == {"trades": [], "total": 0, "limit": None, "offset": 0}

    body = _get(client, user_id, token, limit=5).json()
    assert body == {"trades": [], "total": 0, "limit": 5, "offset": 0}
