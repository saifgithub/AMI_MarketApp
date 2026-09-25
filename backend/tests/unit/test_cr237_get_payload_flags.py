"""CR237 round 2 (auditor MAJOR-3) — the Room GET payload carries `refunded`.

The mobile client recovers a dropped SSE stream by polling `GET /v1/room/{id}`
(`_recoverViaPolling`). The `done` event it missed carries `refunded`,
`cio_retry_available` and `cio_retried`; the GET payload carried only the
last two, so a recovered outage run had no truthful cost line. `refunded` is
computed by the route through `run_was_refunded` — the same predicate the
`done` event uses — and never persisted.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.room import get_room_runner
from app.schemas.room import RoomStatus, Verdict, VerdictAction
from app.services.room_runner import PM_ROOM_INCOMPLETE_REASON
from tests.unit.test_cr236_room_done_credit_cost import (  # noqa: F401 — fixtures
    _FakeRunner,
    _make_run,
    _new_user,
    app,
    client,
)


def _get(client: TestClient, app: FastAPI, token: str, fake: _FakeRunner, run_id):
    app.dependency_overrides[get_room_runner] = lambda: fake
    try:
        r = client.get(
            f"/v1/room/{run_id}", headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    return r.json()


def _owned(run, user_id):
    return run.model_copy(update={"user_id": user_id})


def test_get_reports_refunded_true_for_a_refunded_outage_run(app, client):
    user_id, token = _new_user()
    verdict = Verdict(
        action=VerdictAction.NO_VERDICT,
        reason=f"{PM_ROOM_INCOMPLETE_REASON} 8 of 12 desks responded. "
               "This Room wasn't charged.",
        overridden_from_llm=True,
    )
    run = _owned(_make_run(
        credit_cost=8, status=RoomStatus.COMPLETED, verdict=verdict,
        refund_recorded=True,
    ), user_id)

    body = _get(client, app, token, _FakeRunner(run), run.id)

    assert body["refunded"] is True
    assert body["credit_cost"] == 8
    assert body["cio_retry_available"] is False
    assert body["cio_retried"] is False


def test_get_reports_refunded_false_for_a_charged_run(app, client):
    user_id, token = _new_user()
    verdict = Verdict(action=VerdictAction.APPROVE, reason="Clears the mandate.")
    run = _owned(_make_run(
        credit_cost=8, status=RoomStatus.COMPLETED, verdict=verdict,
    ), user_id)

    body = _get(client, app, token, _FakeRunner(run), run.id)

    assert body["refunded"] is False


def test_get_reports_refunded_true_for_a_failed_run(app, client):
    user_id, token = _new_user()
    run = _owned(_make_run(credit_cost=8, status=RoomStatus.FAILED), user_id)

    body = _get(client, app, token, _FakeRunner(run), run.id)

    assert body["refunded"] is True


class _ListRunner(_FakeRunner):
    def __init__(self, runs) -> None:
        super().__init__(runs[0])
        self._runs = runs

    def list_runs_for_user(self, user_id, limit: int = 50):
        return list(self._runs)


def test_list_reports_refunded_per_run(app, client):
    """CR237 round 3 (auditor U66 MINOR-3) — the list route sets `refunded`
    through the same predicate as the single-run GET; removing that line
    survived every round-2 test."""
    user_id, token = _new_user()
    outage = Verdict(
        action=VerdictAction.NO_VERDICT,
        reason=f"{PM_ROOM_INCOMPLETE_REASON} This Room wasn't charged.",
        overridden_from_llm=True,
    )
    runs = [
        _owned(_make_run(credit_cost=8, status=RoomStatus.COMPLETED,
                         verdict=outage, refund_recorded=True), user_id),
        _owned(_make_run(credit_cost=8, status=RoomStatus.COMPLETED,
                         verdict=Verdict(action=VerdictAction.APPROVE, reason="ok")), user_id),
        _owned(_make_run(credit_cost=8, status=RoomStatus.FAILED), user_id),
    ]
    app.dependency_overrides[get_room_runner] = lambda: _ListRunner(runs)
    try:
        r = client.get(
            f"/v1/room/user/{user_id}", headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    assert [row["refunded"] for row in r.json()] == [True, False, True]
