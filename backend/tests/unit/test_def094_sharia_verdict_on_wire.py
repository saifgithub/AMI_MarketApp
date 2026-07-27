"""GUARD (DEF094) — the Sharia verdict crosses the wire on every response site.

`ComplianceResult.sharia_verdict` was computed and enforced but never serialized:
`sim.py`'s preview/submit handlers hand-built a three-key `compliance` dict and
dropped it. A successful (accepted) trade carried nothing distinguishing a
screened PASS from an unscreened UNKNOWN — the exact silent-pass shape CR069
exists to prevent (G3: unknown is permitted, WITH the disclosure attached).

This file asserts the RESPONSE BODY, not the resolver — DEF089/DEF092's lesson
pointed at this surface: the resolver was already correct and proven so
elsewhere (test_cr069_halal_guard.py); verifying the component is not verifying
the contract that reaches a client.

Covers all three call sites in sim.py: preview_trade, submit_trade (rejected
path), submit_trade (accepted path — dark before this fix).
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.sim as sim_api
from app.schemas.sharia import ShariaStatus
from app.services.auth_service import AuthService
from app.services.sharia_universe import HalalUniverse

_STANDARD = "AAOIFI"
_SOURCE = "S&P 500 Sharia Industry Exclusions Index (via SPUS)"
_AS_OF = date(2026, 7, 23)

# PASS, SCREENED_OUT (in parent but not compliant), UNKNOWN (outside parent).
_COMPLIANT = {"AAPL"}
_PARENT = {"AAPL", "JPMX"}


def _universe(*, stale: bool = False) -> HalalUniverse:
    return HalalUniverse(
        _COMPLIANT, parent_index=_PARENT, as_of=_AS_OF,
        standard=_STANDARD, source=_SOURCE, stale=stale,
    )


@pytest.fixture
def client(monkeypatch) -> TestClient:
    async def _fake_halal_universe_async():
        return _universe()

    monkeypatch.setattr(
        sim_api, "default_halal_universe_async", _fake_halal_universe_async
    )
    app = FastAPI()
    app.include_router(sim_api.router)
    return TestClient(app, raise_server_exceptions=False)


def _make_user_and_token() -> tuple:
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, token


def _halal_body(user_id, ticker: str, **overrides) -> dict:
    body = {
        "user_id": str(user_id),
        "ticker": ticker,
        "side": "buy",
        "quantity": 1,
        "order_type": "market",
        "mandate_override": {"compliance": {"halal": True, "long_only": True}},
    }
    body.update(overrides)
    return body


def _verdict(resp_json: dict) -> dict | None:
    return resp_json["compliance"]["sharia_verdict"]


# ── preview: PASS ──────────────────────────────────────────────────────────


def test_preview_pass_carries_the_verdict(client: TestClient):
    user_id, token = _make_user_and_token()
    r = client.post(
        "/v1/sim/preview", json=_halal_body(user_id, "AAPL"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["accepted"] is True
    v = _verdict(j)
    assert v is not None
    assert v["status"] == ShariaStatus.PASS.value
    assert v["ticker"] == "AAPL"
    assert v["standard"] == _STANDARD
    assert v["source"] == _SOURCE
    assert v["as_of"] == "2026-07-23"


# ── preview: SCREENED_OUT (blocked) ────────────────────────────────────────


def test_preview_screened_out_is_blocked_and_carries_the_verdict(client: TestClient):
    user_id, token = _make_user_and_token()
    r = client.post(
        "/v1/sim/preview", json=_halal_body(user_id, "JPMX"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["accepted"] is False
    v = _verdict(j)
    assert v is not None
    assert v["status"] == ShariaStatus.SCREENED_OUT.value


# ── preview: UNKNOWN (permitted, disclosure still travels) ────────────────


def test_preview_unknown_is_permitted_and_still_carries_the_verdict(client: TestClient):
    user_id, token = _make_user_and_token()
    r = client.post(
        "/v1/sim/preview", json=_halal_body(user_id, "NEVR"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["accepted"] is True  # G3: unknown is permitted, never blocked
    v = _verdict(j)
    assert v is not None
    assert v["status"] == ShariaStatus.UNKNOWN.value


# ── preview: UNAVAILABLE (paused source, blocked, disclosure still travels) ─


def test_preview_unavailable_pauses_and_carries_the_verdict(monkeypatch):
    async def _paused():
        return _universe(stale=True)

    monkeypatch.setattr(sim_api, "default_halal_universe_async", _paused)
    app = FastAPI()
    app.include_router(sim_api.router)
    c = TestClient(app, raise_server_exceptions=False)

    user_id, token = _make_user_and_token()
    r = c.post(
        "/v1/sim/preview", json=_halal_body(user_id, "AAPL"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["accepted"] is False
    v = _verdict(j)
    assert v is not None
    assert v["status"] == ShariaStatus.UNAVAILABLE.value


# ── submit: rejected path already had a compliance block; verdict now too ──


def test_submit_rejected_carries_the_verdict(client: TestClient):
    user_id, token = _make_user_and_token()
    r = client.post(
        "/v1/sim/submit", json=_halal_body(user_id, "JPMX"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is False
    v = _verdict(j)
    assert v is not None
    assert v["status"] == ShariaStatus.SCREENED_OUT.value


# ── submit: ACCEPTED path — dark before this fix (the defect's exact shape) ─


def test_submit_accepted_carries_the_verdict(client: TestClient):
    """The defect's headline case: a successful trade previously returned
    {"ok": True, "trade": ...} with no compliance block at all."""
    user_id, token = _make_user_and_token()
    r = client.post(
        "/v1/sim/submit", json=_halal_body(user_id, "AAPL"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    assert "compliance" in j
    v = _verdict(j)
    assert v is not None
    assert v["status"] == ShariaStatus.PASS.value


def test_submit_accepted_unknown_ticker_is_permitted_and_discloses(client: TestClient):
    """G3's exact case: an accepted trade on an unruled ticker must still
    surface the disclosure — the silent-pass shape this defect exists to kill."""
    user_id, token = _make_user_and_token()
    r = client.post(
        "/v1/sim/submit", json=_halal_body(user_id, "NEVR"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    v = _verdict(j)
    assert v is not None
    assert v["status"] == ShariaStatus.UNKNOWN.value


# ── regression: a PASS ticker and an UNKNOWN ticker must not read identical ─


def test_pass_and_unknown_accepted_bodies_are_not_byte_identical(client: TestClient):
    user_id, token = _make_user_and_token()
    r_pass = client.post(
        "/v1/sim/submit", json=_halal_body(user_id, "AAPL"),
        headers={"Authorization": f"Bearer {token}"},
    )
    r_unknown = client.post(
        "/v1/sim/submit", json=_halal_body(user_id, "NEVR"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_pass.status_code == 200 and r_unknown.status_code == 200
    v_pass = _verdict(r_pass.json())
    v_unknown = _verdict(r_unknown.json())
    assert v_pass["status"] != v_unknown["status"]
    assert v_pass["status"] == ShariaStatus.PASS.value
    assert v_unknown["status"] == ShariaStatus.UNKNOWN.value


# ── OpenAPI: ShariaVerdict now appears in a response schema ────────────────


def test_shariaverdict_appears_in_the_openapi_schema():
    app = FastAPI()
    app.include_router(sim_api.router)
    schema = app.openapi()
    assert "ShariaVerdict" in schema.get("components", {}).get("schemas", {}), (
        "ShariaVerdict must appear in the generated OpenAPI response schema — "
        "the deployed spec is the artefact coder.mobile mirrors by hand."
    )
