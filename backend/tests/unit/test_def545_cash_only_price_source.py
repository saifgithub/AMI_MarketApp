"""DEF545 - the Total Value pill read MOCK after a full sell.

`aggregate_source` answers `mock_walk` for a book with nothing to price (right
for scoring and snapshots, which key off it), and the portfolio route forwarded
that to the LIVE/MOCK pill: a user who sold their last position saw MOCK over a
number that is exactly their cash. Third site of the same collision (DEF217
snapshot rows, CR109 NAV rows).

Drives the real route (DEF190): a helper-only test would stay green if the route
stopped calling the helper.
"""

from __future__ import annotations

from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine


class _Sourced:
    name = "sourced"

    def __init__(self, source: str):
        self.source = source

    def quote(self, ticker: str) -> Quote | None:
        return Quote(price=100.0, source=self.source, change_pct=0.0)

    def history(self, *a, **k):  # pragma: no cover
        return []

    def news(self, *a, **k):  # pragma: no cover
        return []

    def earnings(self, *a, **k):  # pragma: no cover
        return None


def _mandate():
    return hydrate_coach_mandate({
        "plan": "trader",
        "single_name_cap_pct": 100.0,
        "max_open_risk_pct": 100.0,
        "max_trades_per_day": 100,
        "max_trades_per_week": 500,
        "compliance": {"long_only": False, "halal": False},
    })


def _api(source: str):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.sim import router as sim_router
    from app.services.auth_service import AuthService
    from app.services.sim_engine import get_sim_engine

    sim = SimEngine(provider=_Sourced(source))
    app = FastAPI()
    app.include_router(sim_router)
    app.dependency_overrides[get_sim_engine] = lambda: sim
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    return TestClient(app, raise_server_exceptions=False), sim, user, token


def _read(client, user, token) -> dict:
    r = client.get(
        f"/v1/sim/portfolio/{user.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _trade(sim, user, side: Side, qty: float) -> None:
    res = sim.submit(
        user_id=user.id, ticker="AAPL", side=side, quantity=qty,
        mandate=_mandate(), order_type=OrderType.MARKET,
    )
    assert res.trade is not None, res.compliance.violations


def test_a_book_sold_down_to_cash_is_not_labelled_mock():
    client, sim, user, token = _api("yfinance")
    sim.ensure_portfolio(user.id)
    _trade(sim, user, Side.BUY, 1)
    assert _read(client, user, token)["price_source"] == "yfinance"

    _trade(sim, user, Side.SELL, 1)
    body = _read(client, user, token)
    assert body["holdings"] == []
    assert body["price_source"] == "cash"


def test_a_fresh_all_cash_book_is_labelled_cash():
    client, sim, user, token = _api("mock_walk")
    sim.ensure_portfolio(user.id)
    assert _read(client, user, token)["price_source"] == "cash"


def test_a_held_position_priced_from_the_mock_walk_still_reads_mock():
    """The fix must not turn the honest fallback into LIVE: with a holding on
    screen, a mock-priced mark is still reported as one."""
    client, sim, user, token = _api("mock_walk")
    sim.ensure_portfolio(user.id)
    _trade(sim, user, Side.BUY, 1)
    assert _read(client, user, token)["price_source"] == "mock_walk"


def test_a_quote_that_falls_back_to_the_mock_walk_is_logged(monkeypatch):
    """The mock leg serving a mark must leave a trace even when the primary did
    not raise (a None price logs nothing of its own)."""
    from app.services import market_data

    seen: list[tuple[str, dict]] = []

    class _Rec:
        def warn(self, event, **kw):
            seen.append((event, kw))

        def __getattr__(self, name):
            return lambda *a, **k: None

    monkeypatch.setattr(market_data, "logger", _Rec())

    class _Dead:
        name = "dead"

        def quote(self, ticker):
            return None

    fb = market_data.FallbackProvider(_Dead(), market_data.MockWalkProvider())
    q = fb.quote("AAPL")
    assert q is not None and q.source == "mock_walk"
    assert [e for e, _ in seen] == ["market_data_quote_fell_back"]
    assert seen[0][1]["ticker"] == "AAPL"
