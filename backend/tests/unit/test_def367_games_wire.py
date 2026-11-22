"""DEF367 — close the verifiable games (CR109) wire surfaces (AT:B1).

`backend/scripts/wire_contract/verify.py` calls a route -> Dart-model surface
UNVERIFIED when no test drives it through a `TestClient` and gets a real 2xx
JSON body to compare against the keys `api_client.dart` reads. Every
`/v1/games/*` route was in that state: the games suites call the service layer
directly (with an injected `now`), so the HTTP boundary — router, auth, the
dict the handler returns — was never observed.

Driven here, and now verified (PASS):

  GET  /v1/games/runs                      -> GameRunSummary
  GET  /v1/games/runs/$runId/orders        -> GameQueuedOrder
  GET  /v1/games/runs/$runId/board         -> GameBoard
  GET  /v1/games/runs/$runId/arc           -> GameArc
  GET  /v1/games/desks                     -> GameDeskProfile
  GET  /v1/games/record                    -> GameRecord

Deliberately NOT driven, because the wire check cannot honestly pass them and
driving them would turn an UNVERIFIED baseline entry into a hard FAIL (a FAIL
is never ratcheted). Each is a real client/server disagreement or an extractor
limitation, written up on DEF367 rather than papered over here:

  GET  /v1/games/cadences                  FAIL  `next_field` (client accepts flat too)
  POST /v1/games/runs/$runId/trade/quote   FAIL  `will_queue` (client falls back to `market_open`)
  GET  /v1/games/runs/$runId/close         FAIL  `near_miss_label`/`near_miss_gap_pct`/`stipend_awarded`

The routes take no `now`, so the entry-side tests freeze the games service's
clock at Sunday 23:00 ET (weekly field `entry_open`, US market closed — the
same instant `test_games_service.py` uses) and the settled-run test builds a
closed run through the service the way `test_cr109_close_and_record.py` does.

Test-only: no product code changes.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.games import router as games_router
from app.db import get_session
from app.db.models import GameFieldRow, GameQueuedOrderRow, PortfolioNavDailyRow
from app.schemas.trade import Side
from app.services import games_scoring_pass as pass_module
from app.services import games_service as games
from app.services.auth_service import AuthService

_ENTRY_OPEN_CLOSED_MARKET = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)
_MARKET_OPEN = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)
_STARTS_ON = date(2026, 8, 10)
_ENDS_ON = date(2026, 8, 14)
_AFTER_CLOSE = datetime(2026, 8, 17, 15, 0, tzinfo=timezone.utc)


class _FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: ARG003 - the seam IS the fixed instant
        return _ENTRY_OPEN_CLOSED_MARKET


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(games_router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(games, "datetime", _FrozenDateTime)


def _new_user():
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


def _get(client: TestClient, path: str, headers: dict):
    r = client.get(path, headers=headers)
    assert r.status_code == 200, f"{path}: {r.status_code} {r.text}"
    return r.json()


def _enter(client: TestClient, headers: dict) -> str:
    r = client.post("/v1/games/enter", json={"intent": "thesis"}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["run_id"]


def _settled_run(user_id):
    entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)
    with get_session() as s:
        field = s.execute(
            select(GameFieldRow).where(GameFieldRow.id == entry.field_id)
        ).scalar_one()
        field.state = "live"
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=5, now=_MARKET_OPEN,
    )
    with get_session() as s:
        s.add(PortfolioNavDailyRow(
            user_id=user_id, run_id=entry.run_id, as_of_date=_STARTS_ON,
            nav=10_000.0, cash=10_000.0, price_source="live", capital_event="open",
        ))
        s.add(PortfolioNavDailyRow(
            user_id=user_id, run_id=entry.run_id, as_of_date=_ENDS_ON,
            nav=10_150.0, cash=10_000.0, price_source="live", capital_event=None,
        ))
    pass_module.run_scoring_pass(now=_AFTER_CLOSE)
    return entry


def test_run_listing_and_the_house_desks(client: TestClient, frozen_clock) -> None:
    _user_id, headers = _new_user()
    run_id = _enter(client, headers)

    runs = _get(client, "/v1/games/runs", headers)
    assert [r["run_id"] for r in runs] == [run_id]

    desks = _get(client, "/v1/games/desks", headers)
    assert desks, "the house desks are published for every user"


def test_orders_list_carries_a_queued_and_a_refused_order(
    client: TestClient, frozen_clock,
) -> None:
    user_id, headers = _new_user()
    run_id = _enter(client, headers)

    placed = client.post(
        f"/v1/games/runs/{run_id}/trade",
        json={"ticker": "AAPL", "side": "buy", "quantity": 5},
        headers=headers,
    )
    assert placed.status_code == 200, placed.text
    assert placed.json()["queued"] is True

    # The refusal at the open is the only writer of `cancel_reason`, and it
    # happens in the drain tick, not on this route — so seed the row that tick
    # leaves behind rather than driving a market open through the API.
    with get_session() as s:
        s.add(GameQueuedOrderRow(
            run_id=UUID(run_id), user_id=user_id, ticker="MSFT", side="buy",
            quantity=3, order_type="market", state="cancelled",
            cancel_reason="insufficient cash: need $1200.00, have $800.00",
            queued_at=datetime.now(timezone.utc),
        ))

    orders = _get(client, f"/v1/games/runs/{run_id}/orders", headers)

    assert sorted(o["state"] for o in orders) == ["queued", "refused"]
    refused = next(o for o in orders if o["state"] == "refused")
    assert refused["ticker"] == "MSFT"
    assert "insufficient cash" in refused["cancel_reason"]


def test_board_and_arc_for_an_entered_run(client: TestClient, frozen_clock) -> None:
    _user_id, headers = _new_user()
    run_id = _enter(client, headers)

    _get(client, f"/v1/games/runs/{run_id}/board", headers)
    _get(client, f"/v1/games/runs/{run_id}/arc", headers)


def test_record_for_a_settled_run(client: TestClient) -> None:
    user_id, headers = _new_user()
    entry = _settled_run(user_id)

    record = _get(client, "/v1/games/record", headers)

    assert record["finished_count"] == 1
    assert record["run_history"][0]["run_id"] == str(entry.run_id)
