"""CR236 — the `done` SSE event must carry what the run actually cost.

Before this CR the client had no way to learn a Room's charge: `credit_cost`/
`duration_ms` lived only on `RoomRun` server-side (room_screen.dart's own
`_stripMeta` docstring said so). Saiful's ask was concrete: "the Room would
then say what it cost when it finishes."

Uses the same `_FakeRunner` technique as test_room.py — `is_active` always
False routes `/v1/room/stream` straight to the cached-replay branch with no
persisted transcript (so no agent_token/verdict frames), letting the test
drive `get_run`'s return value directly rather than needing a real LLM-backed
run to reach FAILED/COMPLETED. The single thing under test — the `done`
event's own JSON, built once at the end of `event_stream()` regardless of
which branch produced it — is unaffected by that shortcut: it re-reads
`runner.get_run(run_id)` itself, which is exactly the seam `_FakeRunner`
controls.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.room import router as room_router
from app.api.room import get_room_runner
from app.schemas.room import RoomRun, RoomStatus
from app.services.auth_service import AuthService


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


class _FakeRunner:
    """Same shape as test_room.py's `_FakeRunner`: hands `start_run` a fixed
    run_id, reports not-active (routes to cached replay, D2 in room.py), and
    serves a caller-chosen `RoomRun` from `get_run` — exactly the value the
    `done` event build re-reads at the end of `event_stream()`."""

    def __init__(self, run: RoomRun | None) -> None:
        self._run_id = run.id if run is not None else uuid4()
        self._run = run

    async def start_run(self, **kwargs):
        return self._run_id

    def is_active(self, run_id) -> bool:
        return False

    def get_run(self, run_id):
        return self._run


def _make_run(*, credit_cost: int, status: RoomStatus) -> RoomRun:
    from datetime import datetime, timezone

    return RoomRun(
        id=uuid4(),
        user_id=uuid4(),
        ticker="AAPL",
        triggered_at=datetime.now(timezone.utc),
        mandate_version=1,
        model_tier="mid",
        rounds=1,
        transcript=[],
        verdict=None,
        credit_cost=credit_cost,
        status=status,
    )


def _stream(client: TestClient, app: FastAPI, user_id: UUID, token: str, fake: _FakeRunner) -> str:
    app.dependency_overrides[get_room_runner] = lambda: fake
    try:
        r = client.post(
            "/v1/room/stream",
            json={"user_id": str(user_id), "ticker": "AAPL", "locale": "en"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    return r.text


def _done_line(body: str) -> str:
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if line == "event: done":
            return lines[i + 1]
    raise AssertionError(f"no 'event: done' frame found in body: {body!r}")


def test_completed_run_reports_its_actual_charge_not_refunded(
    app: FastAPI, client: TestClient,
):
    user_id, token = _new_user()
    fake = _FakeRunner(_make_run(credit_cost=8, status=RoomStatus.COMPLETED))

    done = _done_line(_stream(client, app, user_id, token, fake))

    assert '"credit_cost": 8' in done
    assert '"refunded": false' in done


def test_failed_run_reports_the_same_credit_cost_and_refunded_true(
    app: FastAPI, client: TestClient,
):
    """CR039/DEF425/DEF432 refund the FULL `credit_cost` on a FAILED run — the
    stored value is never zeroed or partially adjusted after the refund, so
    `done` must read back the same number that was charged, with `refunded`
    flipped to true. This is a pure read of `status`/`credit_cost` off the
    persisted row — no refund decision is made here, only reported."""
    user_id, token = _new_user()
    fake = _FakeRunner(_make_run(credit_cost=8, status=RoomStatus.FAILED))

    done = _done_line(_stream(client, app, user_id, token, fake))

    assert '"credit_cost": 8' in done
    assert '"refunded": true' in done


def test_zero_cost_run_still_reports_an_explicit_zero_not_absence(
    app: FastAPI, client: TestClient,
):
    """A Floor Pass promo run (or any zero-price tier) must not look like an
    unreadable row — 0 is a real, known charge and must round-trip as the
    integer 0, not be dropped or coerced into the DEF437-class 'unknown'."""
    user_id, token = _new_user()
    fake = _FakeRunner(_make_run(credit_cost=0, status=RoomStatus.COMPLETED))

    done = _done_line(_stream(client, app, user_id, token, fake))

    assert '"credit_cost": 0' in done
    assert '"refunded": false' in done


def test_cancelled_run_is_not_reported_as_refunded(
    app: FastAPI, client: TestClient,
):
    """CANCELLED (client disconnect mid-run) is a DIFFERENT terminal state
    from FAILED and is never refunded (room_runner.py's cancel branch charges
    stand). `refunded` must track `status == "failed"` exactly, not any
    non-completed status, or a cancelled run would misreport a refund that
    never happened."""
    user_id, token = _new_user()
    fake = _FakeRunner(_make_run(credit_cost=8, status=RoomStatus.CANCELLED))

    done = _done_line(_stream(client, app, user_id, token, fake))

    assert '"credit_cost": 8' in done
    assert '"refunded": false' in done


def test_a_run_id_with_no_row_degrades_to_null_never_fabricates(
    app: FastAPI, client: TestClient,
):
    """DEF437 class, server-side mirror: if the row cannot be read back at
    the point `done` is built (raced-away row, `get_run` returns None), the
    event must say so honestly (null / false) rather than inventing a
    plausible-looking cost."""
    user_id, token = _new_user()
    fake = _FakeRunner(None)

    done = _done_line(_stream(client, app, user_id, token, fake))

    assert '"credit_cost": null' in done
    assert '"refunded": false' in done
