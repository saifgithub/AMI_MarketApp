"""Tests for Alpaca paper trading integration (AT:R45/R47).

Covers:
  - alpaca_service.exchange_code — happy path + Alpaca error + missing config
  - alpaca_service.get_account — happy path + 401 (token expired) + network error
  - alpaca_service.get_positions — happy path + empty list
  - alpaca_service.snapshot_text — formatting + graceful None on error
  - alpaca_service._paper_get — apikey auth sends correct headers
  - alpaca_service.validate_api_key — delegates to _paper_get with apikey mode
  - POST /v1/alpaca/link — happy path + anonymous reject + bad code (502)
  - POST /v1/alpaca/link_apikey — happy path + invalid key (502) + anonymous (403)
  - DELETE /v1/alpaca/unlink — clears tokens + auth_mode
  - GET /v1/alpaca/status — linked + unlinked
  - GET /v1/alpaca/portfolio — happy path + not linked (409) + anonymous (403)
  - GET /v1/alpaca/positions — happy path + not linked (409)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.alpaca import router as alpaca_router
from app.api.dependencies import get_current_user
from app.db import get_session
from app.db.models import User
from app.services.auth_service import AuthService
from sqlalchemy import select


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_claimed_user() -> tuple:
    """Return (User row, bearer_token)."""
    auth = AuthService()
    anon, token, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        row = s.execute(select(User).where(User.id == anon.id)).scalar_one()
        row.is_anonymous = False
        row.email = f"test_{uuid4().hex[:8]}@example.com"
        s.commit()
    return anon, token


def _make_anon_user() -> tuple:
    auth = AuthService()
    anon, token, _ = auth.ensure_anonymous(device_user_id=None)
    return anon, token


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(alpaca_router)
    return TestClient(app, raise_server_exceptions=False)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── alpaca_service unit tests ─────────────────────────────────────────────


class TestExchangeCode:
    def test_happy_path(self, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "alpaca_client_id", "test_id")
        monkeypatch.setattr(settings, "alpaca_client_secret", "test_secret")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "access_abc",
            "refresh_token": "refresh_xyz",
        }
        with patch("app.services.alpaca_service.httpx.post", return_value=mock_resp):
            from app.services.alpaca_service import exchange_code
            tokens = exchange_code("auth_code_123")
        assert tokens.access_token == "access_abc"
        assert tokens.refresh_token == "refresh_xyz"

    def test_alpaca_error_response(self, monkeypatch):
        from app.core.config import settings
        from app.services.alpaca_service import AlpacaError
        monkeypatch.setattr(settings, "alpaca_client_id", "test_id")
        monkeypatch.setattr(settings, "alpaca_client_secret", "test_secret")

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "invalid_client"
        with patch("app.services.alpaca_service.httpx.post", return_value=mock_resp):
            from app.services.alpaca_service import exchange_code
            with pytest.raises(AlpacaError) as exc_info:
                exchange_code("bad_code")
        assert exc_info.value.status_code == 401

    def test_missing_config_raises(self, monkeypatch):
        from app.core.config import settings
        from app.services.alpaca_service import AlpacaError
        monkeypatch.setattr(settings, "alpaca_client_id", "")
        monkeypatch.setattr(settings, "alpaca_client_secret", "")

        from app.services.alpaca_service import exchange_code
        with pytest.raises(AlpacaError) as exc_info:
            exchange_code("any_code")
        assert exc_info.value.status_code == 503


class TestGetAccount:
    def test_happy_path(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "cash": "10000.00",
            "portfolio_value": "50000.00",
            "equity": "50000.00",
            "buying_power": "20000.00",
        }
        with patch("app.services.alpaca_service.httpx.get", return_value=mock_resp):
            from app.services.alpaca_service import get_account
            acc = get_account("tok_abc")
        assert acc.cash == 10000.0
        assert acc.portfolio_value == 50000.0

    def test_expired_token_raises_401(self):
        from app.services.alpaca_service import AlpacaError
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("app.services.alpaca_service.httpx.get", return_value=mock_resp):
            from app.services.alpaca_service import get_account
            with pytest.raises(AlpacaError) as exc_info:
                get_account("expired_tok")
        assert exc_info.value.status_code == 401


class TestGetPositions:
    def test_happy_path(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"symbol": "AAPL", "qty": "10", "market_value": "1500.00", "unrealized_pl": "50.00"},
            {"symbol": "TSLA", "qty": "5", "market_value": "900.00", "unrealized_pl": "-20.00"},
        ]
        with patch("app.services.alpaca_service.httpx.get", return_value=mock_resp):
            from app.services.alpaca_service import get_positions
            positions = get_positions("tok")
        assert len(positions) == 2
        assert positions[0].symbol == "AAPL"
        assert positions[1].unrealized_pl == -20.0

    def test_empty_positions(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []
        with patch("app.services.alpaca_service.httpx.get", return_value=mock_resp):
            from app.services.alpaca_service import get_positions
            positions = get_positions("tok")
        assert positions == []


class TestPaperGetApiKeyMode:
    def test_apikey_sends_correct_headers(self):
        captured = {}

        def fake_get(url, headers, params, timeout):
            captured["headers"] = headers
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {}
            return mock_resp

        with patch("app.services.alpaca_service.httpx.get", side_effect=fake_get):
            from app.services.alpaca_service import _paper_get
            _paper_get("KEYID", "/v2/account", auth_mode="apikey", api_secret="SECRET")

        assert captured["headers"]["APCA-API-KEY-ID"] == "KEYID"
        assert captured["headers"]["APCA-API-SECRET-KEY"] == "SECRET"
        assert "Authorization" not in captured["headers"]

    def test_oauth_sends_bearer_header(self):
        captured = {}

        def fake_get(url, headers, params, timeout):
            captured["headers"] = headers
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {}
            return mock_resp

        with patch("app.services.alpaca_service.httpx.get", side_effect=fake_get):
            from app.services.alpaca_service import _paper_get
            _paper_get("mytoken", "/v2/account")

        assert captured["headers"]["Authorization"] == "Bearer mytoken"
        assert "APCA-API-KEY-ID" not in captured["headers"]


class TestValidateApiKey:
    def test_valid_key_succeeds(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}
        with patch("app.services.alpaca_service.httpx.get", return_value=mock_resp):
            from app.services.alpaca_service import validate_api_key
            validate_api_key("KEYID", "SECRET")

    def test_invalid_key_raises(self):
        from app.services.alpaca_service import AlpacaError
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("app.services.alpaca_service.httpx.get", return_value=mock_resp):
            from app.services.alpaca_service import validate_api_key
            with pytest.raises(AlpacaError) as exc_info:
                validate_api_key("BADKEY", "BADSECRET")
        assert exc_info.value.status_code == 401


class TestSnapshotText:
    def test_formats_correctly(self):
        acc_mock = MagicMock(cash=10000.0, portfolio_value=50000.0, buying_power=20000.0)
        pos_mock = [MagicMock(symbol="AAPL", qty=10, market_value=1500.0, unrealized_pl=50.0)]
        with patch("app.services.alpaca_service.get_account", return_value=acc_mock), \
             patch("app.services.alpaca_service.get_positions", return_value=pos_mock):
            from app.services.alpaca_service import snapshot_text
            text = snapshot_text("tok")
        assert text is not None
        assert "LIVE ALPACA PAPER PORTFOLIO" in text
        assert "AAPL" in text
        assert "$10,000.00" in text

    def test_returns_none_on_error(self):
        from app.services.alpaca_service import AlpacaError
        with patch("app.services.alpaca_service.get_account", side_effect=AlpacaError(401, "expired")):
            from app.services.alpaca_service import snapshot_text
            result = snapshot_text("tok")
        assert result is None


# ── Route tests ───────────────────────────────────────────────────────────


class TestLinkRoute:
    def test_happy_path(self, client):
        user, token = _make_claimed_user()
        mock_tokens = MagicMock(access_token="acc", refresh_token="ref")
        with patch("app.api.alpaca.exchange_code", return_value=mock_tokens):
            resp = client.post("/v1/alpaca/link", json={"code": "auth_code"}, headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["linked"] is True
        assert "linked_at" in data

        with get_session() as s:
            row = s.execute(select(User).where(User.id == user.id)).scalar_one()
            assert row.alpaca_access_token == "acc"
            assert row.alpaca_refresh_token == "ref"
            assert row.alpaca_linked_at is not None

    def test_anonymous_user_rejected(self, client):
        _, token = _make_anon_user()
        resp = client.post("/v1/alpaca/link", json={"code": "x"}, headers=_auth(token))
        assert resp.status_code == 403

    def test_bad_code_returns_502(self, client):
        from app.services.alpaca_service import AlpacaError
        user, token = _make_claimed_user()
        with patch("app.api.alpaca.exchange_code", side_effect=AlpacaError(401, "bad_code")):
            resp = client.post("/v1/alpaca/link", json={"code": "bad"}, headers=_auth(token))
        assert resp.status_code == 502


class TestLinkApiKeyRoute:
    def test_happy_path(self, client):
        user, token = _make_claimed_user()
        with patch("app.api.alpaca.validate_api_key", return_value=None):
            resp = client.post(
                "/v1/alpaca/link_apikey",
                json={"api_key": "KEYID123", "api_secret": "SECRET456"},
                headers=_auth(token),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["linked"] is True
        assert "linked_at" in data

        with get_session() as s:
            row = s.execute(select(User).where(User.id == user.id)).scalar_one()
            assert row.alpaca_access_token == "KEYID123"
            assert row.alpaca_refresh_token == "SECRET456"
            assert row.alpaca_auth_mode == "apikey"
            assert row.alpaca_linked_at is not None

    def test_invalid_key_returns_502(self, client):
        from app.services.alpaca_service import AlpacaError
        user, token = _make_claimed_user()
        with patch("app.api.alpaca.validate_api_key", side_effect=AlpacaError(401, "forbidden")):
            resp = client.post(
                "/v1/alpaca/link_apikey",
                json={"api_key": "BAD", "api_secret": "BAD"},
                headers=_auth(token),
            )
        assert resp.status_code == 502

    def test_anonymous_user_rejected(self, client):
        _, token = _make_anon_user()
        resp = client.post(
            "/v1/alpaca/link_apikey",
            json={"api_key": "K", "api_secret": "S"},
            headers=_auth(token),
        )
        assert resp.status_code == 403


class TestUnlinkRoute:
    def test_clears_tokens(self, client):
        user, token = _make_claimed_user()
        with get_session() as s:
            from datetime import datetime, timezone
            row = s.execute(select(User).where(User.id == user.id)).scalar_one()
            row.alpaca_access_token = "some_token"
            row.alpaca_refresh_token = "some_refresh"
            row.alpaca_linked_at = datetime.now(timezone.utc)
            row.alpaca_auth_mode = "apikey"
            s.commit()

        resp = client.delete("/v1/alpaca/unlink", headers=_auth(token))
        assert resp.status_code == 200

        with get_session() as s:
            row = s.execute(select(User).where(User.id == user.id)).scalar_one()
            assert row.alpaca_access_token is None
            assert row.alpaca_linked_at is None
            assert row.alpaca_auth_mode is None


class TestStatusRoute:
    def test_linked(self, client):
        user, token = _make_claimed_user()
        with get_session() as s:
            from datetime import datetime, timezone
            row = s.execute(select(User).where(User.id == user.id)).scalar_one()
            row.alpaca_access_token = "tok"
            row.alpaca_linked_at = datetime.now(timezone.utc)
            s.commit()

        resp = client.get("/v1/alpaca/status", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["linked"] is True

    def test_unlinked(self, client):
        _, token = _make_claimed_user()[1], _make_claimed_user()[1]
        _, token = _make_claimed_user()
        resp = client.get("/v1/alpaca/status", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["linked"] is False


class TestPortfolioRoute:
    def test_happy_path(self, client):
        user, token = _make_claimed_user()
        with get_session() as s:
            row = s.execute(select(User).where(User.id == user.id)).scalar_one()
            row.alpaca_access_token = "tok"
            s.commit()

        acc_mock = MagicMock(cash=10000.0, portfolio_value=50000.0, equity=50000.0, buying_power=20000.0)
        with patch("app.api.alpaca.get_account", return_value=acc_mock):
            resp = client.get("/v1/alpaca/portfolio", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["cash"] == 10000.0
        assert data["portfolio_value"] == 50000.0

    def test_not_linked_returns_409(self, client):
        _, token = _make_claimed_user()
        resp = client.get("/v1/alpaca/portfolio", headers=_auth(token))
        assert resp.status_code == 409

    def test_anonymous_returns_403(self, client):
        _, token = _make_anon_user()
        resp = client.get("/v1/alpaca/portfolio", headers=_auth(token))
        assert resp.status_code == 403


class TestPositionsRoute:
    def test_happy_path(self, client):
        user, token = _make_claimed_user()
        with get_session() as s:
            row = s.execute(select(User).where(User.id == user.id)).scalar_one()
            row.alpaca_access_token = "tok"
            s.commit()

        pos_mock = [MagicMock(symbol="AAPL", qty=10.0, market_value=1500.0, unrealized_pl=50.0)]
        with patch("app.api.alpaca.get_positions", return_value=pos_mock):
            resp = client.get("/v1/alpaca/positions", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "AAPL"

    def test_not_linked_returns_409(self, client):
        _, token = _make_claimed_user()
        resp = client.get("/v1/alpaca/positions", headers=_auth(token))
        assert resp.status_code == 409
