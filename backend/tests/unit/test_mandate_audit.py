"""Tests for BL12 — mandate audit on hard edits (AT:R33).

Covers:
  - check_holdings_against_mandate() pure function: blocklist, halal, locale,
    single-name cap, drawdown breach, clean-pass.
  - GET /v1/mandate/{user_id}/audit endpoint: surfaces violations for current
    holdings under the persisted mandate; returns clean result when nothing
    is wrong.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.safety_floor import check_holdings_against_mandate
from app.api.auth import router as auth_router
from app.api.mandate import router as mandate_router
from app.schemas import Compliance, Mandate
from app.schemas.trade import Holding, OrderType, Side
from app.services.auth_service import AuthService
from app.services.coach_engine import hydrate_coach_mandate
from app.services.mandate_store import get_mandate_store
from app.services.sim_engine import SimEngine, get_sim_engine


def _holding(ticker: str, qty: float = 1.0, avg_cost: float = 100.0) -> Holding:
    return Holding(
        ticker=ticker, quantity=qty, avg_cost=avg_cost,
        opened_at=datetime.now(timezone.utc),
    )


# ── Pure-function tests ──────────────────────────────────────────────────


def test_audit_passes_when_holdings_compliant(base_mandate: Mandate) -> None:
    result = check_holdings_against_mandate(
        holdings=[_holding("AAPL", 5, 100), _holding("MSFT", 3, 200)],
        marks={"AAPL": 100, "MSFT": 200},
        portfolio_value=10_000,
        current_drawdown_pct=2.0,
        mandate=base_mandate,
    )
    assert result.passed
    assert result.violations == []
    assert result.drawdown_breach is False
    assert result.mandate_version == base_mandate.version


def test_audit_flags_blocklisted_holding(base_mandate: Mandate) -> None:
    mandate = base_mandate.model_copy(
        update={"compliance": Compliance(
            long_only=True, liquid_only=True, ticker_blocklist=["AAPL"],
        )},
    )
    result = check_holdings_against_mandate(
        holdings=[_holding("AAPL", 5, 100), _holding("MSFT", 3, 200)],
        marks={"AAPL": 100, "MSFT": 200},
        portfolio_value=10_000,
        current_drawdown_pct=0,
        mandate=mandate,
    )
    assert not result.passed
    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.ticker == "AAPL"
    assert any("blocklist" in issue for issue in v.issues)


def test_audit_flags_halal_violation(base_mandate: Mandate) -> None:
    mandate = base_mandate.model_copy(
        update={"compliance": Compliance(
            halal=True, long_only=True, liquid_only=True,
        )},
    )
    # NEVR is not in halal universe; AAPL is.
    result = check_holdings_against_mandate(
        holdings=[_holding("NEVR", 5, 100), _holding("AAPL", 5, 100)],
        marks={"NEVR": 100, "AAPL": 100},
        portfolio_value=10_000,
        current_drawdown_pct=0,
        mandate=mandate,
        halal_universe={"AAPL", "MSFT"},
    )
    assert not result.passed
    assert [v.ticker for v in result.violations] == ["NEVR"]
    # CR069: legacy bare-set path (no parent index) → "outside the configured halal
    # universe" (the sourced three-state path is exercised in the sharia_universe tests).
    assert any(
        "outside the configured halal universe" in issue
        for issue in result.violations[0].issues
    )


def test_audit_flags_single_name_concentration(base_mandate: Mandate) -> None:
    # One holding takes 60% of the portfolio — exceeds 50% single-name cap.
    result = check_holdings_against_mandate(
        holdings=[_holding("NVDA", 60, 100)],
        marks={"NVDA": 100},
        portfolio_value=10_000,
        current_drawdown_pct=0,
        mandate=base_mandate,
    )
    assert not result.passed
    v = result.violations[0]
    assert v.ticker == "NVDA"
    assert v.weight_pct == 60.0
    assert any("single-name cap" in issue for issue in v.issues)


def test_audit_flags_drawdown_breach(base_mandate: Mandate) -> None:
    # current drawdown 35% exceeds the default 30% cap.
    result = check_holdings_against_mandate(
        holdings=[_holding("AAPL", 1, 100)],
        marks={"AAPL": 100},
        portfolio_value=6_500,
        current_drawdown_pct=35.0,
        mandate=base_mandate,
    )
    assert not result.passed
    assert result.drawdown_breach is True


# ── Endpoint tests ────────────────────────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(mandate_router)
    return TestClient(app, raise_server_exceptions=False)


def _make_user_and_token() -> tuple[UUID, str]:
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, token


def test_audit_endpoint_clean_portfolio_returns_passed(
    client: TestClient,
) -> None:
    user_id, token = _make_user_and_token()
    r = client.get(
        f"/v1/mandate/{user_id}/audit",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["passed"] is True
    assert body["violations"] == []
    assert body["drawdown_breach"] is False


def test_audit_endpoint_surfaces_violation_after_blocklist_patch(
    client: TestClient,
) -> None:
    """End-to-end BL12 flow: user buys AAPL, then PATCH-adds AAPL to the
    blocklist, then GET /audit returns a violation for the held AAPL."""
    user_id, token = _make_user_and_token()
    hdr = {"Authorization": f"Bearer {token}"}
    sim = get_sim_engine()
    mandate = hydrate_coach_mandate({"plan": "trader"})

    # Buy something — genuinely under the 50% single-name cap, sized against the
    # live mark rather than a fixed 20 shares. DEF153: at 20 shares this was 77%
    # of the book and only ever accepted because the cap was dark on MARKET
    # orders; the comment claiming "under 50%" was never checked by anything.
    res = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY,
        quantity=int(10_000 * 0.30 / sim.current_price("AAPL")),
        mandate=mandate, order_type=OrderType.MARKET,
    )
    assert res.accepted, res.compliance.violations

    # Persist a mandate with AAPL on the blocklist.
    store = get_mandate_store()
    store.patch(user_id, {"compliance": {"ticker_blocklist": ["AAPL"]}})

    r = client.get(f"/v1/mandate/{user_id}/audit", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["passed"] is False
    assert len(body["violations"]) == 1
    v = body["violations"][0]
    assert v["ticker"] == "AAPL"
    assert any("blocklist" in issue for issue in v["issues"])


def test_audit_endpoint_requires_ownership(client: TestClient) -> None:
    _, token = _make_user_and_token()
    other_user = uuid4()
    r = client.get(
        f"/v1/mandate/{other_user}/audit",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
