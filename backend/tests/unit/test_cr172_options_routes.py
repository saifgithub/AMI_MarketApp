"""CR172 §10 — the propose/open HTTP surface, and the one control it exists for.

`test_the_premium_is_never_the_clients_to_state` is why this file matters more
than its size suggests. `net_cost` is what moves `current_cash`, so a leg whose
premium arrives from the client is a leg that mints money: sell a call for a
stated $900 and the portfolio is $900 richer for nothing. The route therefore
accepts `(right, strike, quantity)` and re-prices every leg off the live chain,
which the test proves by sending a premium field and asserting the fill used
the chain's mid instead.

The rest pin the shapes the shipped mobile ticket already reads
(`option_proposal.dart` mirrors `StrategyLeg` / `StrategyMetrics` / `Greeks` /
`ComplianceResult` key for key), the refusals that must never half-write, and
the ownership check.
"""

from __future__ import annotations

import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.options import router as options_router
from app.services.auth_service import AuthService
from app.services.market_data import (
    OptionChain,
    OptionQuote,
    Quote,
    set_market_data_provider,
)

EXPIRY = datetime.date.today() + datetime.timedelta(days=45)
FAR_EXPIRY = datetime.date.today() + datetime.timedelta(days=120)
SPOT = 100.0


def _quote(strike, bid, ask, iv=0.30):
    return OptionQuote(
        strike=strike, bid=bid, ask=ask, last=None, volume=50,
        open_interest=500, implied_vol=iv,
    )


class _ChainProvider:
    """A liquid two-expiry board around $100, plus the two side-inputs the
    enrichment layer reads: the `^IRX` yield and the dividend rate. Both are
    served rather than stubbed to None so the greeks in these responses are
    real figures — a chain whose rate is missing renders every greek as
    `not_evaluated`, which would let the serialiser tests pass on absences."""

    source = "test_chain"

    def quote(self, ticker: str):
        if ticker.upper() == "^IRX":
            return Quote(price=4.2, source="yfinance", change_pct=0.0)
        return Quote(price=SPOT, source="yfinance", change_pct=0.0)

    def earnings(self, ticker: str):
        return None

    def expiries(self, underlying: str):
        return [EXPIRY, FAR_EXPIRY]

    def option_chain(self, underlying: str, expiry: datetime.date):
        if expiry not in (EXPIRY, FAR_EXPIRY):
            return None
        calls = tuple(
            _quote(k, round(max(0.5, 105 - k) + 4.0, 2), round(max(0.5, 105 - k) + 4.4, 2))
            for k in (90.0, 95.0, 100.0, 105.0, 110.0)
        )
        puts = tuple(
            _quote(k, round(max(0.5, k - 95) + 4.0, 2), round(max(0.5, k - 95) + 4.4, 2))
            for k in (90.0, 95.0, 100.0, 105.0, 110.0)
        )
        return OptionChain(
            underlying=underlying.upper(), expiry=expiry, calls=calls, puts=puts,
            source="yfinance",
        )


@pytest.fixture(autouse=True)
def _provider():
    set_market_data_provider(_ChainProvider())
    yield
    set_market_data_provider(None)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(options_router)
    return TestClient(app, raise_server_exceptions=True)


def _user():
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


def _propose(client, headers, user_id, **over):
    body = {
        "user_id": str(user_id), "ticker": "AAPL", "direction": "bullish",
        "target": 110.0, "stop": 90.0, "horizon_days": 30,
    }
    body.update(over)
    return client.post("/v1/sim/options/propose", json=body, headers=headers)


def _open(client, headers, user_id, legs, **over):
    body = {
        "user_id": str(user_id), "ticker": "AAPL",
        "strategy_name": "long_call", "expiry": EXPIRY.isoformat(),
        "legs": legs,
    }
    body.update(over)
    return client.post("/v1/sim/options/open", json=body, headers=headers)


# ── propose ─────────────────────────────────────────────────────────────────

def test_propose_returns_costed_candidates(client):
    user_id, headers = _user()
    r = _propose(client, headers, user_id)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["underlying"] == "AAPL"
    assert body["expiry"] == EXPIRY.isoformat()
    names = {c["strategy_name"] for c in body["candidates"]}
    assert "long_call" in names
    for c in body["candidates"]:
        assert c["metrics"]["net_cost"] is not None
        assert c["legs"] and all(leg["premium"] > 0 for leg in c["legs"])


def test_propose_writes_nothing(client):
    from app.db import get_session
    from app.db.models import SimOptionLegRow

    user_id, headers = _user()
    _propose(client, headers, user_id)
    with get_session() as s:
        assert s.query(SimOptionLegRow).count() == 0


def test_every_candidate_carries_a_compliance_block_with_passed(client):
    """The client fails closed on a missing `passed` — never omit it."""
    user_id, headers = _user()
    body = _propose(client, headers, user_id).json()
    for c in body["candidates"]:
        assert "passed" in c["compliance"]
        assert isinstance(c["compliance"]["passed"], bool)


def test_a_forbidden_structure_is_returned_marked_not_missing(client):
    user_id, headers = _user()
    body = _propose(
        client, headers, user_id,
        mandate={"plan": "trader", "compliance": {"long_only": True}},
    ).json()
    csp = next(
        (c for c in body["candidates"] if c["strategy_name"] == "cash_secured_put"),
        None,
    )
    assert csp is not None, "the mandate-violating structure must still appear"
    assert csp["compliance"]["passed"] is False
    assert csp["compliance"]["violations"]


def test_an_unlisted_expiry_is_refused_not_snapped(client):
    user_id, headers = _user()
    body = _propose(
        client, headers, user_id,
        expiry=(EXPIRY + datetime.timedelta(days=1)).isoformat(),
    ).json()
    assert body["candidates"] == []
    assert body["not_evaluated"]


def test_propose_refuses_a_ticker_the_registry_does_not_know(client):
    user_id, headers = _user()
    r = _propose(client, headers, user_id, ticker="NOTREAL")
    assert r.status_code == 422


def test_propose_rejects_another_users_portfolio(client):
    _user_id, headers = _user()
    other_id, _other_headers = _user()
    r = _propose(client, headers, other_id)
    assert r.status_code == 403


# ── open — the control ──────────────────────────────────────────────────────

def test_the_premium_is_never_the_clients_to_state(client):
    """A client-stated premium must not reach the ledger."""
    user_id, headers = _user()
    r = _open(
        client, headers, user_id,
        [{"right": "call", "strike": 100.0, "quantity": 1.0, "premium": 0.01}],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accepted"] is True
    # The chain's own mid for the 100 call: bid 9.0 / ask 9.4 → 9.2.
    assert body["legs"][0]["premium"] == 9.2
    assert body["net_cost"] == 920.0


def test_the_open_moves_cash_by_the_servers_figure(client):
    user_id, headers = _user()
    body = _open(
        client, headers, user_id,
        [{"right": "call", "strike": 100.0, "quantity": 1.0}],
    ).json()
    portfolio = body["portfolio"]
    assert round(10_000.0 - portfolio["current_cash"], 2) == body["net_cost"]
    assert len(portfolio["options"]) == 1


def test_a_strike_that_is_not_listed_is_refused_and_charges_nothing(client):
    user_id, headers = _user()
    body = _open(
        client, headers, user_id,
        [{"right": "call", "strike": 137.5, "quantity": 1.0}],
    ).json()
    assert body["accepted"] is False
    assert body["portfolio"]["current_cash"] == 10_000.0
    assert any("not listed" in n for n in body["compliance"]["not_evaluated"])


def test_a_naked_call_is_refused_at_the_route(client):
    from app.agents.safety_floor import NAKED_CALL_REFUSAL

    user_id, headers = _user()
    body = _open(
        client, headers, user_id,
        [{"right": "call", "strike": 100.0, "quantity": -1.0}],
        strategy_name="naked_call",
    ).json()
    assert body["accepted"] is False
    assert NAKED_CALL_REFUSAL in body["compliance"]["violations"]
    assert body["portfolio"]["current_cash"] == 10_000.0


def test_open_rejects_another_users_portfolio(client):
    _user_id, headers = _user()
    other_id, _ = _user()
    r = _open(
        client, headers, other_id,
        [{"right": "call", "strike": 100.0, "quantity": 1.0}],
    )
    assert r.status_code == 403


def test_a_structure_may_not_exceed_four_legs(client):
    """DEF191's four-leg invariant, enforced at the edge."""
    user_id, headers = _user()
    r = _open(
        client, headers, user_id,
        [{"right": "call", "strike": k, "quantity": 1.0}
         for k in (90.0, 95.0, 100.0, 105.0, 110.0)],
    )
    assert r.status_code == 422


def test_the_response_carries_every_key_the_ticket_reads(client):
    user_id, headers = _user()
    body = _propose(client, headers, user_id).json()
    candidate = body["candidates"][0]
    assert set(candidate["metrics"]) == {
        "net_cost", "max_loss", "max_gain", "unbounded_loss", "unbounded_gain",
        "break_evens", "collateral_required", "has_uncovered_short_call",
        "shares_locked", "covered_by_shares",
    }
    if candidate["net_greeks"] is not None:
        assert set(candidate["net_greeks"]) == {
            "delta", "gamma", "theta_per_day", "vega_per_point", "rho_per_point",
        }
