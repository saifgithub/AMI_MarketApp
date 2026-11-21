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
    # CR129/DEF187: permissive single-name cap — this test is about the
    # audit's blocklist/halal/drawdown legs, not position sizing (MSFT here
    # is 6% of the book, over the ~3% risk-tier preset).
    mandate = base_mandate.model_copy(update={"single_name_cap_pct": 100.0})
    result = check_holdings_against_mandate(
        holdings=[_holding("AAPL", 5, 100), _holding("MSFT", 3, 200)],
        marks={"AAPL": 100, "MSFT": 200},
        portfolio_value=10_000,
        current_drawdown_pct=2.0,
        mandate=mandate,
    )
    assert result.passed
    assert result.violations == []
    assert result.drawdown_breach is False
    assert result.mandate_version == base_mandate.version


def test_audit_flags_blocklisted_holding(base_mandate: Mandate) -> None:
    mandate = base_mandate.model_copy(
        update={
            "compliance": Compliance(
                long_only=True, liquid_only=True, ticker_blocklist=["AAPL"],
            ),
            # CR129/DEF187: permissive single-name cap — MSFT is 6% of the
            # book, over the ~3% risk-tier preset, which isn't this test's point.
            "single_name_cap_pct": 100.0,
        },
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
        update={
            "compliance": Compliance(
                halal=True, long_only=True, liquid_only=True,
            ),
            # CR129/DEF187: permissive single-name cap — AAPL is 5% of the
            # book, over the ~3% risk-tier preset, which isn't this test's point.
            "single_name_cap_pct": 100.0,
        },
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
    # CR129/DEF187: permissive single-name cap — this setup buy is
    # deliberately ~30% of the book (see comment below); the risk-tier
    # preset (~3%) isn't what this test is about.
    mandate = hydrate_coach_mandate({"plan": "trader", "single_name_cap_pct": 100.0})

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


# ── DEF514: concentration caps measured against current holdings ─────────────


from app.services.sector_allocation import SectorMap  # noqa: E402

_SECTORS = SectorMap(mapping={
    "NFLX": "Communication Services",
    "GOOGL": "Communication Services",
    "AAPL": "Technology",
    "MSFT": "Technology",
    "KO": "Consumer Staples",
})


def _audit(mandate: Mandate, holdings, marks, *, pv: float = 10_000.0, sector_map=_SECTORS):
    return check_holdings_against_mandate(
        holdings=holdings, marks=marks, portfolio_value=pv,
        current_drawdown_pct=0, mandate=mandate, sector_map=sector_map,
    )


def test_def514_single_name_breach_lists_the_ticker_and_weight(base_mandate: Mandate) -> None:
    # NFLX is 46.5% of the book; the user tightens the single-name cap to 3%.
    mandate = base_mandate.model_copy(
        update={"single_name_cap_pct": 3.0, "sector_cap_pct": 100.0})
    r = _audit(mandate, [_holding("NFLX", 46.5, 100), _holding("KO", 0.1, 100)],
               {"NFLX": 100, "KO": 100})
    assert r.single_name_cap_breach is True
    assert r.single_name_cap_pct == 3.0
    assert [(b.name, b.weight_pct) for b in r.single_name_breaches] == [("NFLX", 46.5)]
    assert r.single_name_breaches[0].tickers == ["NFLX"]
    assert r.sector_cap_breach is False


def test_def514_single_name_no_breach_when_cap_is_looser(base_mandate: Mandate) -> None:
    mandate = base_mandate.model_copy(
        update={"single_name_cap_pct": 50.0, "sector_cap_pct": 100.0})
    r = _audit(mandate, [_holding("NFLX", 46.5, 100)], {"NFLX": 100})
    assert r.single_name_cap_breach is False
    assert r.single_name_breaches == []
    assert r.passed


def test_def514_single_name_uses_the_trade_ticket_cap(base_mandate: Mandate) -> None:
    from app.agents.safety_floor import single_name_cap_pct

    mandate = base_mandate.model_copy(update={"single_name_cap_pct": 3.0})
    r = _audit(mandate, [_holding("NFLX", 1, 100)], {"NFLX": 100})
    assert r.single_name_cap_pct == single_name_cap_pct(mandate)


def test_def514_sector_breach_groups_holdings_by_sector(base_mandate: Mandate) -> None:
    # NFLX 25% + GOOGL 20% = 45% Communication Services, over a 40% cap;
    # Technology (AAPL) is 10%, under it.
    mandate = base_mandate.model_copy(
        update={"sector_cap_pct": 40.0, "single_name_cap_pct": 100.0})
    r = _audit(
        mandate,
        [_holding("NFLX", 25, 100), _holding("GOOGL", 20, 100), _holding("AAPL", 10, 100)],
        {"NFLX": 100, "GOOGL": 100, "AAPL": 100},
    )
    assert r.sector_cap_breach is True
    assert r.sector_cap_pct == 40.0
    assert len(r.sector_breaches) == 1
    b = r.sector_breaches[0]
    assert b.name == "Communication Services"
    assert b.weight_pct == 45.0
    assert b.tickers == ["GOOGL", "NFLX"]
    assert r.passed is False
    assert r.single_name_cap_breach is False


def test_def514_sector_no_breach_under_cap_or_when_unclassified(base_mandate: Mandate) -> None:
    mandate = base_mandate.model_copy(
        update={"sector_cap_pct": 40.0, "single_name_cap_pct": 100.0})
    holdings = [_holding("NFLX", 25, 100), _holding("GOOGL", 10, 100)]
    marks = {"NFLX": 100, "GOOGL": 100}
    assert _audit(mandate, holdings, marks).sector_cap_breach is False  # 35% < 40%
    # An unknown sector is "Other": disclosed elsewhere, never a breach.
    r = _audit(mandate, [_holding("ZZZZ", 90, 100)], {"ZZZZ": 100})
    assert r.sector_cap_breach is False
    # No resolver supplied -> not evaluated, never claimed.
    assert _audit(mandate, holdings, marks, sector_map=None).sector_cap_breach is False


def test_def514_day_trader_caps_never_breach(base_mandate: Mandate) -> None:
    # 100% caps (the Day Trader preset) permit any weight, even one name at 100%
    # and a portfolio_value that has drifted below the holdings' value.
    mandate = base_mandate.model_copy(
        update={"single_name_cap_pct": 100.0, "sector_cap_pct": 100.0})
    r = _audit(mandate, [_holding("NFLX", 100, 100)], {"NFLX": 100}, pv=9_000.0)
    assert r.single_name_cap_breach is False
    assert r.sector_cap_breach is False
    assert r.single_name_breaches == [] and r.sector_breaches == []
    # At exactly 100% the per-holding audit is clean too.
    assert _audit(mandate, [_holding("NFLX", 100, 100)], {"NFLX": 100}).passed


def test_def514_audit_fields_are_additive(base_mandate: Mandate) -> None:
    r = _audit(base_mandate.model_copy(update={"single_name_cap_pct": 100.0}),
               [_holding("AAPL", 1, 100)], {"AAPL": 100})
    body = r.model_dump()
    for k in ("passed", "mandate_version", "drawdown_breach", "max_open_positions_breach",
              "max_open_risk_pct_breach", "violations"):
        assert k in body
    for k in ("single_name_cap_breach", "sector_cap_breach", "single_name_breaches",
              "sector_breaches", "single_name_cap_pct", "sector_cap_pct"):
        assert k in body
