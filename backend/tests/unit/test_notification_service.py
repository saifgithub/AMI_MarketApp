"""notification_service.notify() — CR027.

The core contract under test: the `notifications` row is written
UNCONDITIONALLY, regardless of what happens to the push attempt (empty
key, network error, rejection, rate limit) — CR040 degrade-loudly, never
a silently-dropped notification.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select

from app.core.config import settings
from app.db import get_session
from app.db.models import NotificationRow
from app.services import notification_service


def _row(notification_id):
    with get_session() as s:
        return s.execute(
            select(NotificationRow).where(NotificationRow.id == notification_id)
        ).scalar_one_or_none()


def test_notify_writes_row_unconditionally_when_push_key_empty():
    """Real Alpha state today: onesignal_rest_key is empty."""
    user_id = uuid4()
    result = notification_service.notify(
        user_id, "price_alert", "Price Alert: AAPL", "crossed $150",
        {"route": "open_holding_detail", "ticker": "AAPL"},
    )
    assert result.push_status == "not_configured"
    row = _row(result.notification_id)
    assert row is not None
    assert row.user_id == user_id
    assert row.type == "price_alert"
    assert row.title == "Price Alert: AAPL"
    assert row.deep_link == {"route": "open_holding_detail", "ticker": "AAPL"}
    assert row.read_at is None


def test_notify_logs_warning_not_silent_noop_on_empty_key(monkeypatch):
    warnings: list[str] = []
    monkeypatch.setattr(
        notification_service.logger, "warning",
        lambda event, **kw: warnings.append(event),
    )
    notification_service.notify(uuid4(), "price_alert", "t", "b", {"route": "x"})
    assert "notification_push_not_configured" in warnings


def test_notify_writes_row_even_when_onesignal_call_raises(monkeypatch):
    monkeypatch.setattr(settings, "onesignal_app_id", "app-id")
    monkeypatch.setattr(settings, "onesignal_rest_key", "rest-key")

    def _boom(*a, **k):
        raise notification_service.httpx.RequestError("boom")

    monkeypatch.setattr(notification_service.httpx, "post", _boom)
    result = notification_service.notify(uuid4(), "price_alert", "t", "b", {"route": "x"})
    assert result.push_status == "failed"
    assert _row(result.notification_id) is not None


def test_notify_writes_row_even_when_onesignal_rejects(monkeypatch):
    monkeypatch.setattr(settings, "onesignal_app_id", "app-id")
    monkeypatch.setattr(settings, "onesignal_rest_key", "rest-key")
    monkeypatch.setattr(
        notification_service.httpx, "post",
        lambda *a, **k: SimpleNamespace(status_code=400, text="bad request"),
    )
    result = notification_service.notify(uuid4(), "price_alert", "t", "b", {"route": "x"})
    assert result.push_status == "failed"
    assert _row(result.notification_id) is not None


def test_notify_posts_expected_payload(monkeypatch):
    monkeypatch.setattr(settings, "onesignal_app_id", "app-id")
    monkeypatch.setattr(settings, "onesignal_rest_key", "rest-key")
    captured: dict = {}
    user_id = uuid4()

    def _fake_post(url, *, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return SimpleNamespace(status_code=200, text="")

    monkeypatch.setattr(notification_service.httpx, "post", _fake_post)
    result = notification_service.notify(
        user_id, "price_alert", "Price Alert: AAPL", "body",
        {"route": "open_holding_detail", "ticker": "AAPL"},
    )
    assert result.push_status == "sent"
    assert captured["url"].endswith("/notifications")
    assert captured["json"]["app_id"] == "app-id"
    assert captured["json"]["include_external_user_ids"] == [str(user_id)]
    assert captured["json"]["headings"] == {"en": "Price Alert: AAPL"}
    assert captured["json"]["data"] == {"route": "open_holding_detail", "ticker": "AAPL"}
    assert captured["headers"]["Authorization"] == "Key rest-key"


def test_notify_per_minute_rate_limit_still_writes_row(monkeypatch):
    monkeypatch.setattr(settings, "onesignal_app_id", "app-id")
    monkeypatch.setattr(settings, "onesignal_rest_key", "rest-key")
    monkeypatch.setattr(
        notification_service.httpx, "post",
        lambda *a, **k: SimpleNamespace(status_code=200, text=""),
    )
    user_id = uuid4()
    first = notification_service.notify(user_id, "price_alert", "t", "b", {"route": "x"})
    second = notification_service.notify(user_id, "price_alert", "t", "b", {"route": "x"})
    assert first.push_status == "sent"
    assert second.push_status == "rate_limited"
    assert _row(first.notification_id) is not None
    assert _row(second.notification_id) is not None


def test_notify_per_hour_rate_limit_after_three_pushes(monkeypatch):
    monkeypatch.setattr(settings, "onesignal_app_id", "app-id")
    monkeypatch.setattr(settings, "onesignal_rest_key", "rest-key")
    monkeypatch.setattr(
        notification_service.httpx, "post",
        lambda *a, **k: SimpleNamespace(status_code=200, text=""),
    )
    user_id = uuid4()
    statuses = []
    for _ in range(4):
        # Bypass the per-minute limiter so only the per-hour cap is exercised.
        notification_service._push_per_minute.reset()
        statuses.append(
            notification_service.notify(user_id, "price_alert", "t", "b", {"route": "x"}).push_status
        )
    assert statuses == ["sent", "sent", "sent", "rate_limited"]


def test_different_users_do_not_share_a_rate_limit_bucket(monkeypatch):
    monkeypatch.setattr(settings, "onesignal_app_id", "app-id")
    monkeypatch.setattr(settings, "onesignal_rest_key", "rest-key")
    monkeypatch.setattr(
        notification_service.httpx, "post",
        lambda *a, **k: SimpleNamespace(status_code=200, text=""),
    )
    a = notification_service.notify(uuid4(), "price_alert", "t", "b", {"route": "x"})
    b = notification_service.notify(uuid4(), "price_alert", "t", "b", {"route": "x"})
    assert a.push_status == "sent"
    assert b.push_status == "sent"
