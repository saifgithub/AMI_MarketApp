"""CR239 / WP-38 - the scoped UAT fault switch answers 503 for one user + route only.

Pins: a matching user+route gets a 503 whose body and header carry the same
server-minted request id (the real `app`, so the real exception handler and
`HTTPAuditMiddleware` run); every other user and route is untouched; outside
local/dev/staging the switch is inert; malformed config stops the boot.
"""

from __future__ import annotations

import json
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import uat_fault_inject
from app.services.auth_service import AuthService

ROUTE = "GET /v1/messages"


@pytest.fixture(autouse=True)
def _reset_switch():
    yield
    uat_fault_inject.configure("", "staging")


def _user() -> tuple[UUID, dict[str, str]]:
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _arm(user_id: UUID, env: str = "staging", routes: list[str] | None = None) -> None:
    uat_fault_inject.configure(json.dumps({str(user_id): routes or [ROUTE]}), env)


def test_matching_user_and_route_gets_503_with_server_minted_request_id() -> None:
    uid, headers = _user()
    _arm(uid)
    with patch("app.middleware.http_audit.record_http") as record:
        r = _client().get("/v1/messages", headers={**headers, "X-Request-Id": "client-chosen"})
    assert r.status_code == 503
    header_id = r.headers["x-request-id"]
    assert r.json()["request_id"] == header_id
    assert header_id != "client-chosen"
    UUID(header_id)
    assert record.call_args.kwargs["status_code"] == 503
    assert str(record.call_args.kwargs["request_id"]) == header_id


def test_other_user_is_untouched() -> None:
    uid, _ = _user()
    _, other_headers = _user()
    _arm(uid)
    with patch("app.middleware.http_audit.record_http"):
        r = _client().get("/v1/messages", headers=other_headers)
    assert r.status_code == 200


def test_other_route_is_untouched() -> None:
    uid, headers = _user()
    _arm(uid)
    with patch("app.middleware.http_audit.record_http"):
        r = _client().get("/v1/notifications/" + str(uid), headers=headers)
    assert r.status_code != 503


def test_unauthenticated_call_is_untouched() -> None:
    uid, _ = _user()
    _arm(uid)
    with patch("app.middleware.http_audit.record_http"):
        r = _client().get("/v1/messages")
    assert r.status_code == 401


@pytest.mark.parametrize("env", ["prod", "beta"])
def test_non_alpha_env_is_inert(env: str) -> None:
    uid, headers = _user()
    _arm(uid, env=env)
    with patch("app.middleware.http_audit.record_http"):
        r = _client().get("/v1/messages", headers=headers)
    assert r.status_code == 200


def test_refusal_and_activation_are_logged() -> None:
    uid = UUID(int=1)
    with patch.object(uat_fault_inject, "logger") as log:
        _arm(uid, env="prod")
        log.error.assert_called_once_with("uat_fault_inject_refused", env="prod")
        _arm(uid, routes=[ROUTE, "POST /v1/messages/x/read"])
        log.warning.assert_called_once_with("uat_fault_inject_active", users=1, routes=2)


@pytest.mark.parametrize(
    "raw",
    [
        "{not json",
        "[]",
        '{"not-a-uuid": ["GET /v1/messages"]}',
        '{"00000000-0000-0000-0000-000000000001": "GET /v1/messages"}',
        '{"00000000-0000-0000-0000-000000000001": ["/v1/messages"]}',
        '{"00000000-0000-0000-0000-000000000001": []}',
    ],
)
def test_malformed_config_fails_the_boot(raw: str) -> None:
    with pytest.raises(RuntimeError, match="UAT_FAULT_INJECT"):
        uat_fault_inject.configure(raw, "staging")


@pytest.mark.parametrize("raw", ["", "   "])
def test_empty_is_inert(raw: str) -> None:
    uid, headers = _user()
    uat_fault_inject.configure(raw, "staging")
    with patch("app.middleware.http_audit.record_http"):
        r = _client().get("/v1/messages", headers=headers)
    assert r.status_code == 200


def test_setting_defaults_to_empty() -> None:
    from app.core.config import Settings

    assert Settings.model_fields["uat_fault_inject"].default == ""
