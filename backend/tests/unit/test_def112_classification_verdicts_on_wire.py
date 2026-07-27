"""GUARD (DEF112) — `classification_verdicts` crosses the wire on every response
site, DEF094's sibling fix for the `no_fossil_fuels` / `no_tobacco_alcohol_gambling`
/ `esg_lite` mandate flags.

`ComplianceResult.classification_verdicts` was computed and enforced (DEF061) but
never serialized: `sim.py`'s preview/submit handlers dropped it exactly like they
dropped `sharia_verdict` before DEF094. A successful (accepted) trade carried
nothing distinguishing a classified PERMITTED from an unclassified UNKNOWN — the
same silent-pass shape CR069/DEF061 exist to prevent (permit + disclose).

This file asserts the RESPONSE BODY, not the resolver — the resolver is already
proven correct elsewhere (test_def061_compliance_enforcement.py); verifying the
component is not verifying the contract that reaches a client.

Covers all three call sites in sim.py: preview_trade, submit_trade (rejected
path), submit_trade (accepted path — dark before this fix), for both
`no_fossil_fuels` and `esg_lite` (the two flags already live on mobile).
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.sim as sim_api
from app.schemas.classification import ClassificationKind, ClassificationStatus
from app.services.auth_service import AuthService
from app.services.classification_universe import ClassificationUniverse

_AS_OF = date(2026, 7, 23)

# XOM: fossil-fuel producer (EXCLUDED under no_fossil_fuels/esg_lite).
# AAPL: classified, clean (PERMITTED).
# NEVR: never classified (UNKNOWN — permitted, with disclosure).
_CLASSIFIED = {"AAPL", "XOM"}
_FOSSIL = {"XOM"}


def _universe(*, stale: bool = False) -> ClassificationUniverse:
    return ClassificationUniverse(
        fossil=_FOSSIL, sin=set(), defense=set(), classified=_CLASSIFIED,
        as_of=_AS_OF, source="AMI sector/industry classification (yfinance)",
        stale=stale,
    )


@pytest.fixture
def client(monkeypatch) -> TestClient:
    async def _fake_classification_universe_async():
        return _universe()

    monkeypatch.setattr(
        sim_api, "default_classification_universe_async",
        _fake_classification_universe_async,
    )
    app = FastAPI()
    app.include_router(sim_api.router)
    return TestClient(app, raise_server_exceptions=False)


def _make_user_and_token() -> tuple:
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, token


def _mandate_body(user_id, ticker: str, *, flag: str, **overrides) -> dict:
    body = {
        "user_id": str(user_id),
        "ticker": ticker,
        "side": "buy",
        "quantity": 1,
        "order_type": "market",
        "mandate_override": {"compliance": {flag: True, "long_only": True}},
    }
    body.update(overrides)
    return body


def _verdicts(resp_json: dict) -> list[dict]:
    return resp_json["compliance"]["classification_verdicts"]


def _for_kind(verdicts: list[dict], kind: str) -> dict | None:
    for v in verdicts:
        if v["kind"] == kind:
            return v
    return None


# ── preview: PERMITTED (no_fossil_fuels) ────────────────────────────────────


def test_preview_permitted_carries_the_verdict(client: TestClient):
    user_id, token = _make_user_and_token()
    r = client.post(
        "/v1/sim/preview",
        json=_mandate_body(user_id, "AAPL", flag="no_fossil_fuels"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["accepted"] is True
    verdicts = _verdicts(j)
    assert len(verdicts) == 1
    v = _for_kind(verdicts, ClassificationKind.FOSSIL_FUELS.value)
    assert v is not None
    assert v["status"] == ClassificationStatus.PERMITTED.value
    assert v["ticker"] == "AAPL"
    assert v["as_of"] == "2026-07-23"


# ── preview: EXCLUDED (blocked, no_fossil_fuels) ────────────────────────────


def test_preview_excluded_is_blocked_and_carries_the_verdict(client: TestClient):
    user_id, token = _make_user_and_token()
    r = client.post(
        "/v1/sim/preview",
        json=_mandate_body(user_id, "XOM", flag="no_fossil_fuels"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["accepted"] is False
    v = _for_kind(_verdicts(j), ClassificationKind.FOSSIL_FUELS.value)
    assert v is not None
    assert v["status"] == ClassificationStatus.EXCLUDED.value


# ── preview: UNKNOWN (permitted, disclosure still travels — esg_lite) ──────


def test_preview_unknown_is_permitted_and_still_carries_the_verdict(client: TestClient):
    user_id, token = _make_user_and_token()
    r = client.post(
        "/v1/sim/preview",
        json=_mandate_body(user_id, "NEVR", flag="esg_lite"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["accepted"] is True  # unknown is permitted, never blocked
    v = _for_kind(_verdicts(j), ClassificationKind.ESG_LITE.value)
    assert v is not None
    assert v["status"] == ClassificationStatus.UNKNOWN.value


# ── preview: UNAVAILABLE (stale universe, blocked, disclosure still travels) ─


def test_preview_unavailable_pauses_and_carries_the_verdict(monkeypatch):
    async def _paused():
        return _universe(stale=True)

    monkeypatch.setattr(sim_api, "default_classification_universe_async", _paused)
    app = FastAPI()
    app.include_router(sim_api.router)
    c = TestClient(app, raise_server_exceptions=False)

    user_id, token = _make_user_and_token()
    r = c.post(
        "/v1/sim/preview",
        json=_mandate_body(user_id, "AAPL", flag="no_fossil_fuels"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["accepted"] is False
    v = _for_kind(_verdicts(j), ClassificationKind.FOSSIL_FUELS.value)
    assert v is not None
    assert v["status"] == ClassificationStatus.UNAVAILABLE.value


# ── submit: rejected path ───────────────────────────────────────────────────


def test_submit_rejected_carries_the_verdict(client: TestClient):
    user_id, token = _make_user_and_token()
    r = client.post(
        "/v1/sim/submit",
        json=_mandate_body(user_id, "XOM", flag="no_fossil_fuels"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is False
    v = _for_kind(_verdicts(j), ClassificationKind.FOSSIL_FUELS.value)
    assert v is not None
    assert v["status"] == ClassificationStatus.EXCLUDED.value


# ── submit: ACCEPTED path — dark before this fix (the defect's exact shape) ─


def test_submit_accepted_carries_the_verdict(client: TestClient):
    """The defect's headline case: a successful trade previously returned
    {"ok": True, "trade": ...} with no classification_verdicts at all."""
    user_id, token = _make_user_and_token()
    r = client.post(
        "/v1/sim/submit",
        json=_mandate_body(user_id, "AAPL", flag="no_fossil_fuels"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    assert "classification_verdicts" in j["compliance"]
    v = _for_kind(_verdicts(j), ClassificationKind.FOSSIL_FUELS.value)
    assert v is not None
    assert v["status"] == ClassificationStatus.PERMITTED.value


def test_submit_accepted_unknown_ticker_is_permitted_and_discloses_esg_lite(
    client: TestClient,
):
    """G3's exact case, applied to esg_lite: an accepted trade on an
    unclassified ticker must still surface the disclosure — the silent-pass
    shape this defect exists to kill."""
    user_id, token = _make_user_and_token()
    r = client.post(
        "/v1/sim/submit",
        json=_mandate_body(user_id, "NEVR", flag="esg_lite"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    v = _for_kind(_verdicts(j), ClassificationKind.ESG_LITE.value)
    assert v is not None
    assert v["status"] == ClassificationStatus.UNKNOWN.value


def test_submit_accepted_empty_when_no_classification_flags_active(client: TestClient):
    """No `no_fossil_fuels` / `no_tobacco_alcohol_gambling` / `esg_lite` flag
    active ⇒ classification_verdicts is an empty list, never null — an empty
    list is the honest 'no classification screens requested' answer."""
    user_id, token = _make_user_and_token()
    r = client.post(
        "/v1/sim/submit",
        json={
            "user_id": str(user_id),
            "ticker": "AAPL",
            "side": "buy",
            "quantity": 1,
            "order_type": "market",
            "mandate_override": {"compliance": {"long_only": True}},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    assert j["compliance"]["classification_verdicts"] == []


# ── regression: PERMITTED and UNKNOWN accepted bodies not byte-identical ────


def test_permitted_and_unknown_accepted_bodies_are_not_byte_identical(
    client: TestClient,
):
    user_id, token = _make_user_and_token()
    r_permitted = client.post(
        "/v1/sim/submit",
        json=_mandate_body(user_id, "AAPL", flag="esg_lite"),
        headers={"Authorization": f"Bearer {token}"},
    )
    r_unknown = client.post(
        "/v1/sim/submit",
        json=_mandate_body(user_id, "NEVR", flag="esg_lite"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_permitted.status_code == 200 and r_unknown.status_code == 200
    v_permitted = _for_kind(
        _verdicts(r_permitted.json()), ClassificationKind.ESG_LITE.value
    )
    v_unknown = _for_kind(
        _verdicts(r_unknown.json()), ClassificationKind.ESG_LITE.value
    )
    assert v_permitted["status"] != v_unknown["status"]
    assert v_permitted["status"] == ClassificationStatus.PERMITTED.value
    assert v_unknown["status"] == ClassificationStatus.UNKNOWN.value


# ── OpenAPI: ClassificationVerdict now appears in a response schema ─────────


def test_classificationverdict_appears_in_the_openapi_schema():
    app = FastAPI()
    app.include_router(sim_api.router)
    schema = app.openapi()
    assert "ClassificationVerdict" in schema.get("components", {}).get("schemas", {}), (
        "ClassificationVerdict must appear in the generated OpenAPI response "
        "schema — the deployed spec is the artefact coder.mobile mirrors by hand."
    )
