"""Tests for email_service.send_magic_link.

The SMTP call is mocked so no network traffic is made in unit tests.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import app.services.email_service as email_mod
from app.services.email_service import send_magic_link


def test_send_magic_link_skips_when_no_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(email_mod.settings, "smtp_host", "")
    with patch("smtplib.SMTP_SSL") as mock_ssl:
        send_magic_link("user@example.com", "123456")
    mock_ssl.assert_not_called()


def test_send_magic_link_ssl_port_465(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(email_mod.settings, "smtp_host", "mail.example.com")
    monkeypatch.setattr(email_mod.settings, "smtp_port", 465)
    monkeypatch.setattr(email_mod.settings, "smtp_user", "user@example.com")
    monkeypatch.setattr(email_mod.settings, "smtp_password", "secret")
    monkeypatch.setattr(email_mod.settings, "smtp_from", "noreply@example.com")

    mock_smtp = MagicMock()
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)

    with patch("smtplib.SMTP_SSL", return_value=mock_smtp) as mock_ssl:
        send_magic_link("recipient@example.com", "654321")

    mock_ssl.assert_called_once()
    mock_smtp.login.assert_called_once_with("user@example.com", "secret")
    # sendmail call — check recipient and that code appears in the message
    args = mock_smtp.sendmail.call_args
    assert args[0][1] == "recipient@example.com"
    assert "654321" in args[0][2]


def test_send_magic_link_starttls_port_587(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(email_mod.settings, "smtp_host", "smtp.gmail.com")
    monkeypatch.setattr(email_mod.settings, "smtp_port", 587)
    monkeypatch.setattr(email_mod.settings, "smtp_user", "user@gmail.com")
    monkeypatch.setattr(email_mod.settings, "smtp_password", "app-pw")
    monkeypatch.setattr(email_mod.settings, "smtp_from", "")

    mock_smtp = MagicMock()
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)

    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_magic_link("recipient@example.com", "111222")

    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once_with("user@gmail.com", "app-pw")


def test_send_magic_link_failure_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(email_mod.settings, "smtp_host", "mail.example.com")
    monkeypatch.setattr(email_mod.settings, "smtp_port", 465)
    monkeypatch.setattr(email_mod.settings, "smtp_user", "u")
    monkeypatch.setattr(email_mod.settings, "smtp_password", "p")
    monkeypatch.setattr(email_mod.settings, "smtp_from", "f@e.com")

    with patch("smtplib.SMTP_SSL", side_effect=ConnectionRefusedError("refused")):
        # Must not raise — failure is logged and swallowed
        send_magic_link("user@example.com", "000000")


def test_send_magic_link_sign_out_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """DELETE /v1/auth/session returns 200 with valid bearer, 401 without."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.api.auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router)
    client = TestClient(app, raise_server_exceptions=False)

    # No bearer → 401
    r = client.request("DELETE", "/v1/auth/session")
    assert r.status_code == 401

    # Valid bearer → 200
    from app.services.auth_service import AuthService
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    r = client.request(
        "DELETE", "/v1/auth/session",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() == {"signed_out": True}
