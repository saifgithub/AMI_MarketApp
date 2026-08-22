"""DEF360 — what happened to a push must survive the next deploy.

`notify()` returned a `push_status` to its caller and logged it. Nothing
stored it. Container logs do not survive `docker compose up --build`, which is
what every promotion does, so the record of every delivery was being deleted
on a schedule.

Measured on 2026-08-22: CR176 had been open for days on "never proven to send
a real push" while `notifications` held 17 beat rows written between
2026-08-14 and that morning — three of them at 08:09Z, four hours before a
promotion recreated the container and destroyed their outcomes. The rows
proving the beats fired were all there. Every record of whether they were
delivered was gone.

The properties:
  * a delivered push is recorded on its own row, and so is one that reached
    nobody — the DEF359 outcome is what makes the second case distinguishable;
  * the suppressed paths (`skipped`, `pref_disabled`) record themselves too,
    or a NULL would be ambiguous between "not recorded" and "never attempted";
  * annotating the row is best-effort and can never turn a delivered push into
    an exception for the caller, because the durable row is the product and
    the annotation is commentary on it.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db import get_session
from app.db.models import NotificationRow
from app.services import notification_service
from app.core.config import settings


def _row(notification_id):
    with get_session() as s:
        row = s.get(NotificationRow, notification_id)
        return (row.push_status, row.push_detail) if row else None


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    monkeypatch.setattr(settings, "onesignal_app_id", "app-id")
    monkeypatch.setattr(settings, "onesignal_rest_key", "rest-key")


def _post(payload, status_code=200):
    return lambda *a, **k: SimpleNamespace(
        status_code=status_code, text="", json=lambda: payload,
    )


def test_a_delivered_push_is_recorded_on_the_row(monkeypatch):
    monkeypatch.setattr(
        notification_service.httpx, "post",
        _post({"id": "onesignal-id", "recipients": 1}),
    )
    result = notification_service.notify(
        uuid4(), "game_settled", "t", "b", {"route": "x"},
    )
    assert result.push_status == "sent"
    assert _row(result.notification_id) == ("sent", None)


def test_a_push_that_reached_nobody_is_recorded_as_such(monkeypatch):
    """The DEF359 case, now durable — this is the one CR176 needed.

    Without it, a beat delivered to zero devices leaves a notifications row
    indistinguishable from a beat that reached someone.
    """
    monkeypatch.setattr(
        notification_service.httpx, "post",
        _post({"id": "", "errors": ["All included players are not subscribed"]}),
    )
    result = notification_service.notify(
        uuid4(), "game_settled", "t", "b", {"route": "x"},
    )
    status, detail = _row(result.notification_id)
    assert status == "no_recipients"
    assert "not subscribed" in detail


def test_a_suppressed_push_records_why(monkeypatch):
    """`skipped` must be stored, or NULL cannot be read as "no answer"."""
    result = notification_service.notify(
        uuid4(), "game_settled", "t", "b", {"route": "x"}, attempt_push=False,
    )
    assert result.push_status == "skipped"
    assert _row(result.notification_id) == ("skipped", None)


def test_annotating_never_breaks_delivery(monkeypatch):
    """A failure to write the annotation must not reach the caller.

    The notification row is the product and this column is commentary on it.
    Inverting that would let a bookkeeping fault turn a push that was actually
    delivered into an exception — trading a missing note for a broken feature.
    """
    monkeypatch.setattr(
        notification_service, "get_session",
        lambda: (_ for _ in ()).throw(RuntimeError("db went away")),
    )
    assert notification_service._record_push_outcome(uuid4(), "sent", None) is None


def test_the_outcome_is_recorded_after_the_attempt_not_before(monkeypatch):
    """Order matters: the value stored must be the one the attempt produced.

    Recording before the call would store an optimistic guess, which is the
    whole class of defect this column exists to close.
    """
    seen: list[str] = []
    real = notification_service._record_push_outcome

    def _spy(notification_id, status, detail):
        seen.append(status)
        return real(notification_id, status, detail)

    monkeypatch.setattr(notification_service, "_record_push_outcome", _spy)
    monkeypatch.setattr(
        notification_service.httpx, "post",
        _post({"id": "", "errors": ["All included players are not subscribed"]}),
    )
    result = notification_service.notify(
        uuid4(), "game_settled", "t", "b", {"route": "x"},
    )
    assert seen == ["no_recipients"]
    assert _row(result.notification_id)[0] == "no_recipients"


def test_a_null_still_means_no_answer_not_a_default():
    """Rows predating this column must not be backfilled into a claim.

    A default of 'unknown' or 'sent' would manufacture a fact about a delivery
    nobody observed — the DEF059 shape. NULL is the honest value and the
    column must stay nullable.
    """
    col = NotificationRow.__table__.c.push_status
    assert col.nullable is True
    assert col.default is None
    assert col.server_default is None
