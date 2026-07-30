"""DEF161: reconnecting to a run persisted before the CR106-B2 stance envelope
must not draw an all-gutter comb that reads as "everyone abstained".

The Journal mapper already tells the two cases apart by dict key presence
(`room_board_mappers.dart:183`: `stanceRecorded: row?.containsKey('stance')`)
and the mobile SSE decoder is already written to do the same on the wire
(`api_client.dart` `agent_done` case: `if (j.containsKey('stance')) ...`).
The bug is entirely server-side: `room.py`'s cached-replay branch always
emits all three keys — even `null` — so a pre-B2 row (whose stored JSON never
had a 'stance' key at all) is indistinguishable on the wire from a post-B2 row
where the agent stated a real, recorded "neutral". This test drives the actual
`/v1/room/stream` dedup-to-completed-run path against a real RoomRunRow so the
wire-level JSON is what's asserted on, not an internal helper.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.room import router as room_router
from app.api.room import get_room_runner
from app.db import get_session
from app.db.models import RoomRunRow, SimPortfolioRow
from app.services.auth_service import AuthService
from app.services.room_runner import RoomRunner


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(room_router)
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _new_user() -> tuple[UUID, str]:
    auth = AuthService()
    u, t, _ = auth.ensure_anonymous(device_user_id=None)
    return u.id, t


def _seed_completed_run(user_id: UUID, ticker: str, transcript: list[dict]) -> UUID:
    """Persist a COMPLETED run directly, bypassing the runner, so `transcript`
    is exactly the raw JSON dict shape a real pre- or post-B2 row would have —
    the point under test is dict key presence, which a schema-validated
    round-trip would erase."""
    run_id = uuid4()
    with get_session() as s:
        s.add(SimPortfolioRow(
            id=uuid4(),
            user_id=user_id,
            name="Main",
            starting_capital=10_000.0,
            current_cash=10_000.0,
        ))
        s.add(RoomRunRow(
            id=run_id,
            user_id=user_id,
            ticker=ticker,
            triggered_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            finished_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            mandate_version=1,
            model_tier="mid",
            rounds=1,
            transcript=transcript,
            verdict={
                "action": "APPROVE",
                "reason": "test verdict",
                "violations": [],
                "opinions_not_included": [],
            },
            credit_cost=0,
            status="completed",
        ))
    return run_id


def _stream(client: TestClient, app: FastAPI, user_id: UUID, token: str, ticker: str) -> str:
    runner = RoomRunner()
    app.dependency_overrides[get_room_runner] = lambda: runner
    try:
        r = client.post(
            "/v1/room/stream",
            json={"user_id": str(user_id), "ticker": ticker, "locale": "en"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    return r.text


def _agent_done_lines(body: str) -> list[str]:
    lines = body.splitlines()
    out = []
    for i, line in enumerate(lines):
        if line == "event: agent_done":
            # the following line is "data: {...}"
            out.append(lines[i + 1])
    return out


def test_pre_b2_row_replays_stance_absent_not_null(app: FastAPI, client: TestClient):
    """A row persisted before the stance envelope existed has no 'stance' key
    in its stored transcript dict at all. The replayed SSE `agent_done` event
    must likewise omit the key — not send `"stance": null` — so the client's
    `containsKey` check (already written for exactly this) can tell "not
    recorded" apart from "recorded, and it's neutral"."""
    user_id, token = _new_user()
    transcript = [{
        "agent_id": "fundamentals_analyst",
        "content": "Solid fundamentals.",
        "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat(),
        # no stance / conviction / headline keys — pre-B2 shape.
    }]
    _seed_completed_run(user_id, "AAPL", transcript)

    body = _stream(client, app, user_id, token, "AAPL")
    lines = _agent_done_lines(body)
    assert len(lines) == 1
    assert "stance" not in lines[0], (
        f"pre-B2 replay must omit the stance key entirely, got: {lines[0]}"
    )


def test_recorded_neutral_still_round_trips_as_neutral(app: FastAPI, client: TestClient):
    """A row persisted after B2 where the agent explicitly stated a neutral
    position must still replay `"stance": "neutral"` — the fix must not
    collapse a genuine, recorded neutral into "not recorded"."""
    user_id, token = _new_user()
    transcript = [{
        "agent_id": "fundamentals_analyst",
        "content": "Mixed signals.",
        "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat(),
        "stance": "neutral",
        "conviction": "medium",
        "headline": "Wait for confirmation.",
    }]
    _seed_completed_run(user_id, "MSFT", transcript)

    body = _stream(client, app, user_id, token, "MSFT")
    lines = _agent_done_lines(body)
    assert len(lines) == 1
    assert '"stance": "neutral"' in lines[0]


def test_agent_that_stated_no_view_post_b2_still_omits_the_key(app: FastAPI, client: TestClient):
    """Post-B2, an agent that genuinely stated no position stores stance=None
    (the key IS present, value null) — the comb's gutter case, a real
    recorded fact, not an unknown. Wire behaviour for this case is untouched
    by DEF161's fix; documented here so the two null-shaped cases (key
    absent vs key present-but-null) don't get conflated in review."""
    user_id, token = _new_user()
    transcript = [{
        "agent_id": "fundamentals_analyst",
        "content": "No strong view either way.",
        "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat(),
        "stance": None,
        "conviction": None,
        "headline": None,
    }]
    _seed_completed_run(user_id, "GOOG", transcript)

    body = _stream(client, app, user_id, token, "GOOG")
    lines = _agent_done_lines(body)
    assert len(lines) == 1
    assert '"stance": null' in lines[0]
