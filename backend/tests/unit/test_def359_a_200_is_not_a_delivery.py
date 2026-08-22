"""DEF359 — OneSignal's 200 does not mean anybody got the push.

`notify()` read `resp.status_code` and nothing else, so the one response
OneSignal returns for "this user has no subscribed device" —

    HTTP 200  {"id": "", "errors": ["All included players are not subscribed"]}

— was logged as `notification_push_sent` and returned `"sent"`. Measured
against live Alpha's own credentials on 2026-08-22: the channel is reachable
and authenticated, and a request naming an unregistered external id comes back
exactly like that.

The consequence is the CR040 shape rather than a crash: the success signal
could not distinguish a delivered push from one delivered to nobody, so
CR176's open question — *has a real push ever reached a device?* — was
unanswerable from our own logs no matter how many we sent.

`"no_recipients"` is deliberately NOT `"failed"`. The API did not reject us;
the user simply has no device registered, which is a fact about that user and
a normal state at alpha. Collapsing the two would trade a silent success for a
noisy false alarm.
"""

from __future__ import annotations

import uuid

import pytest

from app.services import notification_service


class _Resp:
    def __init__(self, status_code: int, payload, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is _NO_JSON:
            raise ValueError("not json")
        return self._payload


_NO_JSON = object()


@pytest.fixture
def push(monkeypatch):
    """Drive only the push half, with OneSignal configured and stubbed."""
    monkeypatch.setattr(
        notification_service.settings, "onesignal_app_id", "app-id", raising=False,
    )
    monkeypatch.setattr(
        notification_service.settings, "onesignal_rest_key", "rest-key", raising=False,
    )

    def _run(resp):
        monkeypatch.setattr(
            notification_service.httpx, "post", lambda *a, **kw: resp,
        )
        return notification_service._attempt_push(
            user_id=uuid.uuid4(),
            notification_id=uuid.uuid4(),
            type="game_close",
            title="t",
            body="b",
            deep_link={},
        )

    return _run


def test_the_unsubscribed_body_is_not_a_send(push):
    """The exact live shape — id "", an errors array, HTTP 200."""
    status, detail = push(_Resp(200, {
        "id": "", "errors": ["All included players are not subscribed"],
    }))
    assert status == "no_recipients"
    assert "not subscribed" in detail


def test_zero_recipients_is_not_a_send(push):
    """OneSignal also answers with an id and recipients: 0."""
    status, _ = push(_Resp(200, {"id": "abc", "recipients": 0}))
    assert status == "no_recipients"


def test_one_recipient_is_a_send(push):
    status, detail = push(_Resp(200, {"id": "abc", "recipients": 1}))
    assert status == "sent"
    assert detail is None


def test_a_send_with_no_recipients_field_is_still_a_send(push):
    """Non-vacuity: an id and no errors must not be swept into the new branch.

    If this ever flipped, every real push would report itself undelivered —
    the opposite failure, and a louder one.
    """
    status, _ = push(_Resp(200, {"id": "abc"}))
    assert status == "sent"


def test_an_unparseable_body_is_still_a_send(push):
    """A 200 we cannot read is not evidence of non-delivery."""
    status, _ = push(_Resp(200, _NO_JSON))
    assert status == "sent"


def test_a_rejection_stays_failed_not_no_recipients(push):
    """`failed` means the API refused us; the two must not collapse."""
    status, detail = push(_Resp(400, {"errors": ["Invalid app_id"]}, text="bad"))
    assert status == "failed"
    assert "400" in detail


def test_no_recipients_is_a_declared_outcome():
    import typing

    assert "no_recipients" in typing.get_args(notification_service.PushStatus)
