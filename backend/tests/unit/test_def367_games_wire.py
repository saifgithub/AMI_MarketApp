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

  GET  /v1/games/record/prs                UNVERIFIED  (driven below, still unverified) the server
       sends a category-keyed object; the client's `prs` list branch never matches and
       `kind`/`value`/`cadence` are synthesised by the `gamesRecordPrs` adapter.

Also found re-checking the cadences route: the client reads the entrant count from
`GameFieldSummary.entrant_count` (flat cadence object), the server sends `queue_count`,
so `games_home_screen` / `games_close_screen` always show 0 entrants. Not fixed here.

DEF527 fixed the five real disagreements (enter, run detail, trade, restart,
close) and those routes ARE driven at the bottom of this file.

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
from app.db.models import (
    GameEntryRow,
    GameFieldRow,
    GameQueuedOrderRow,
    PortfolioNavDailyRow,
)
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


# ── DEF527 — the five routes whose shape disagreed with the Dart models ──────
#
# Each assertion pins a key `mobile/lib/models/games.dart` reads, on the real
# route's real response, so the wire-contract ratchet can verify the surface
# and either side drifting fails here.

_MARKET_OPEN_NOW = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)


class _OpenMarketDateTime(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: ARG003 - the seam IS the fixed instant
        return _MARKET_OPEN_NOW


def _entry_and_open(user_id):
    """Enter the field (market closed) then make it live, as `_settled_run`."""
    entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)
    with get_session() as s:
        field = s.execute(
            select(GameFieldRow).where(GameFieldRow.id == entry.field_id)
        ).scalar_one()
        field.state = "live"
    return entry


def test_enter_carries_cadence_and_entry_id(client: TestClient, frozen_clock) -> None:
    user_id, headers = _new_user()

    r = client.post("/v1/games/enter", json={"cadence": "week"}, headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cadence"] == "week"
    with get_session() as s:
        entry = s.execute(
            select(GameEntryRow).where(GameEntryRow.user_id == user_id)
        ).scalar_one()
    assert body["entry_id"] == str(entry.id)
    assert body["run_id"] == str(entry.run_id)
    assert body["field_id"] == str(entry.field_id)


def test_run_detail_carries_days_left_and_field_id(
    client: TestClient, frozen_clock,
) -> None:
    _user_id, headers = _new_user()
    run_id = _enter(client, headers)

    detail = _get(client, f"/v1/games/runs/{run_id}", headers)

    runs = _get(client, "/v1/games/runs", headers)
    assert detail["field_id"] == runs[0]["field_id"]
    assert detail["days_left"] == runs[0]["days_left"] == 4  # Mon 08-10 -> Fri 08-14


def test_a_queued_order_echoes_its_own_side(client: TestClient, frozen_clock) -> None:
    _user_id, headers = _new_user()
    run_id = _enter(client, headers)

    for side in ("buy", "sell"):
        r = client.post(
            f"/v1/games/runs/{run_id}/trade",
            json={"ticker": "aapl", "side": side, "quantity": 2},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["queued"] is True
        assert body["status"] == "queued"
        assert (body["ticker"], body["side"], body["quantity"]) == ("AAPL", side, 2)
        assert body["price"] is None, "a queued order has no price by design"


def test_a_filled_sell_is_a_sell_with_its_price(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, headers = _new_user()
    entry = _entry_and_open(user_id)
    monkeypatch.setattr(games, "datetime", _OpenMarketDateTime)
    path = f"/v1/games/runs/{entry.run_id}/trade"

    bought = client.post(
        path, json={"ticker": "AAPL", "side": "buy", "quantity": 5}, headers=headers,
    )
    sold = client.post(
        path, json={"ticker": "AAPL", "side": "sell", "quantity": 5}, headers=headers,
    )

    assert bought.status_code == sold.status_code == 200, (bought.text, sold.text)
    b, s = bought.json(), sold.json()
    assert b["filled"] is True and b["side"] == "buy"
    assert s["filled"] is True, s
    assert s["status"] == "filled"
    assert s["side"] == "sell", "a SELL must never read back as a buy"
    assert s["ticker"] == "AAPL" and s["quantity"] == 5
    assert isinstance(s["price"], float) and s["price"] > 0


def test_restart_says_whether_it_committed(client: TestClient, frozen_clock) -> None:
    _user_id, headers = _new_user()
    run_id = _enter(client, headers)
    path = f"/v1/games/runs/{run_id}/restart"

    preview = client.post(path, headers=headers)
    assert preview.status_code == 200, preview.text
    assert preview.json()["committed"] is False

    committed = client.post(path, params={"commit": "true"}, headers=headers)
    assert committed.status_code == 200, committed.text
    assert committed.json()["committed"] is True
    assert committed.json()["state"] == "forfeit"


def _closed_pair(rank_a, twr_a, *, rank_b=1, twr_b=1.8, basis="placement"):
    """User A (the one under test) and a rival B in the SAME field, both
    settled with stored columns — the Close reads stored columns only."""
    user_a, headers = _new_user()
    user_b, _ = _new_user()
    a = games.enter_field(user_a, now=_ENTRY_OPEN_CLOSED_MARKET)
    b = games.enter_field(user_b, now=_ENTRY_OPEN_CLOSED_MARKET)
    assert a.field_id == b.field_id
    with get_session() as s:
        field = s.execute(
            select(GameFieldRow).where(GameFieldRow.id == a.field_id)
        ).scalar_one()
        field.state = "closed"
        field.scoring_basis = basis
        for entry_id, rank, twr in ((a.id, rank_a, twr_a), (b.id, rank_b, twr_b)):
            row = s.execute(
                select(GameEntryRow).where(GameEntryRow.id == entry_id)
            ).scalar_one()
            row.state = "finished"
            row.final_rank = rank
            row.final_twr_pct = twr
            row.scored_entrant_count = 2
    return a.run_id, headers


def test_close_carries_the_near_miss_to_the_rank_above(client: TestClient) -> None:
    run_id, headers = _closed_pair(rank_a=2, twr_a=1.5)

    close = _get(client, f"/v1/games/runs/{run_id}/close", headers)

    assert close["near_miss_label"] == "1st"
    assert close["near_miss_gap_pct"] == pytest.approx(0.3)
    assert close["stipend_awarded"] is False  # read by GameCloseResult.fromJson
    assert close["scored_entrant_count"] == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(rank_a=1, twr_a=1.8, rank_b=2, twr_b=1.5),   # won: nobody above
        dict(rank_a=2, twr_a=-0.4, twr_b=1.8),            # a loss: never near-miss
        dict(rank_a=2, twr_a=1.5, basis="benchmark"),     # thin field: no position
    ],
    ids=["winner", "loss", "thin_field"],
)
def test_close_withholds_the_near_miss_where_the_fence_says(
    client: TestClient, kwargs: dict,
) -> None:
    run_id, headers = _closed_pair(**kwargs)

    close = _get(client, f"/v1/games/runs/{run_id}/close", headers)

    assert close["near_miss_label"] is None
    assert close["near_miss_gap_pct"] is None


# ── DEF367 tail — the three routes the first pass left unobserved ────────────
#
# `GET /record/prs` is driven here, empty and populated, and the shape
# `gamesRecordPrs` adapts from is pinned. It stays UNVERIFIED in the baseline:
# the client's list read (`data['prs']`) never matches the category-keyed object
# the server sends, and the scalar read sees `GamePersonalRecord`'s `kind` /
# `value` / `cadence` only as keys the adapter synthesises client-side.
#
# `GET /cadences` and `POST .../trade/quote` are deliberately NOT driven (see
# the module docstring): observing them flips each from UNVERIFIED to a hard
# FAIL (`next_field` / `will_queue`), which the ratchet does not absorb.


def test_personal_records_empty_board_is_an_object_of_nulls(client: TestClient) -> None:
    _user_id, headers = _new_user()

    prs = _get(client, "/v1/games/record/prs", headers)

    assert prs["has_any_finished_runs"] is False
    for category in (
        "best_weekly_twr", "best_alpha", "best_drawdown_control",
        "longest_hold_days", "longest_finish_streak",
    ):
        assert prs[category] is None, category
    assert "prs" not in prs  # the client's flat-list branch is a legacy shape


def test_personal_records_populated_for_a_settled_run(client: TestClient) -> None:
    user_id, headers = _new_user()
    entry = _settled_run(user_id)

    prs = _get(client, "/v1/games/record/prs", headers)

    assert prs["has_any_finished_runs"] is True
    # `gamesRecordPrs` reads each category's `entry_id` plus its own value key.
    for category, value_key in (
        ("best_weekly_twr", "final_twr_pct"),
        ("longest_hold_days", "days"),
        ("longest_finish_streak", "count"),
    ):
        block = prs[category]
        assert isinstance(block, dict), category
        assert block["entry_id"] == str(entry.run_id) or block["entry_id"], category
        assert isinstance(block[value_key], (int, float)), (category, value_key)
    assert prs["longest_finish_streak"]["count"] == 1
    assert prs["longest_hold_days"]["days"] == 4
    for category in ("best_alpha", "best_drawdown_control"):
        assert prs[category] is None or prs[category]["entry_id"]
