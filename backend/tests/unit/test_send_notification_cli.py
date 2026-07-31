"""send_notification.py CLI — CR027. Covers deep_link assembly and that
main() reaches notification_service.notify() with the right arguments;
notify() itself is covered by test_notification_service.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from scripts import send_notification


@dataclass
class _FakeResult:
    notification_id: object
    push_status: str = "not_configured"
    push_detail: str | None = None


def test_deep_link_assembled_from_route_ticker_and_params(monkeypatch):
    user_id = uuid4()
    calls: list[dict] = []

    def _fake_notify(user_id, type, title, body, deep_link, source_ref=None):
        calls.append(dict(
            user_id=user_id, type=type, title=title, body=body,
            deep_link=deep_link, source_ref=source_ref,
        ))
        return _FakeResult(notification_id=uuid4())

    monkeypatch.setattr(send_notification, "notify", _fake_notify)
    rc = send_notification.main([
        "--user-id", str(user_id),
        "--title", "t", "--body", "b", "--type", "price_alert",
        "--route", "open_holding_detail", "--ticker", "AAPL",
        "--param", "extra=1",
    ])
    assert rc == 0
    assert len(calls) == 1
    call = calls[0]
    assert call["user_id"] == user_id
    assert call["type"] == "price_alert"
    assert call["deep_link"] == {"route": "open_holding_detail", "ticker": "AAPL", "extra": "1"}


def test_source_ref_passed_through(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(
        send_notification, "notify",
        lambda user_id, type, title, body, deep_link, source_ref=None: (
            calls.append(source_ref) or _FakeResult(notification_id=uuid4())
        ),
    )
    send_notification.main([
        "--user-id", str(uuid4()), "--title", "t", "--body", "b",
        "--source-ref", "alert-123",
    ])
    assert calls == ["alert-123"]


def test_param_without_equals_is_rejected():
    with pytest.raises(SystemExit):
        send_notification.main([
            "--user-id", str(uuid4()), "--title", "t", "--body", "b",
            "--param", "not-a-kv-pair",
        ])
