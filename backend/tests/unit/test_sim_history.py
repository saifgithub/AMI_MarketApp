"""Tests for GET /v1/sim/history/{ticker} and the history-cache pattern.

Bundle 2 of the TickerDetail surface (AT:R41). The route is the chart's
data source; this file covers the route + every shape it returns.

Conftest pins to MockWalkProvider via `set_market_data_provider`, so the
tests are fully deterministic — no live yfinance calls. The mock walk's
`history()` synthesizes OHLCV anchored at "now" rounded to the period's
bar interval, so successive calls within the same second produce
identical timestamps + identical bars (this is what makes the cache-
hit equality test meaningful).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.sim import router as sim_router
from app.services import market_data as _md
from app.services.market_data import (
    VALID_PERIODS,
    CachingProvider,
    MockWalkProvider,
)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(sim_router)
    return TestClient(app, raise_server_exceptions=False)


# ── Route ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("period", list(VALID_PERIODS))
def test_history_returns_candles_for_each_period(client: TestClient, period: str) -> None:
    r = client.get(f"/v1/sim/history/AAPL?period={period}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert body["period"] == period
    assert body["source"] == "mock_walk"
    candles = body["candles"]
    assert isinstance(candles, list)
    assert len(candles) > 0
    for c in candles:
        # Shape contract — the iPhone painter keys on these.
        assert set(c.keys()) == {"t", "o", "h", "l", "c", "v"}
        assert isinstance(c["t"], int)
        assert c["t"] > 0
        assert c["l"] <= c["o"]
        assert c["l"] <= c["c"]
        assert c["h"] >= c["o"]
        assert c["h"] >= c["c"]
        assert c["h"] > c["l"]
        assert c["v"] > 0


def test_history_lowercase_ticker_is_normalized(client: TestClient) -> None:
    r = client.get("/v1/sim/history/aapl?period=1m")
    assert r.status_code == 200
    assert r.json()["ticker"] == "AAPL"


def test_history_default_period_is_1m(client: TestClient) -> None:
    r = client.get("/v1/sim/history/AAPL")
    assert r.status_code == 200
    assert r.json()["period"] == "1m"


def test_history_invalid_period_returns_422(client: TestClient) -> None:
    r = client.get("/v1/sim/history/AAPL?period=bogus")
    assert r.status_code == 422


def test_history_is_public_no_auth_required(client: TestClient) -> None:
    """Mirrors the /quote contract — no Bearer header needed."""
    r = client.get("/v1/sim/history/AAPL?period=1m")
    assert r.status_code == 200


# ── Provider — mock walk determinism ─────────────────────────────────────


def test_mock_walk_history_is_deterministic_for_same_ticker_period() -> None:
    """Same input within a single anchor tick produces identical bars.

    The anchor rounds `now` to the period's bar interval, so two calls
    in the same second hit the same anchor and emit the same candles.
    """
    p = MockWalkProvider()
    bars_a = p.history("AAPL", "1m")
    bars_b = p.history("AAPL", "1m")
    assert bars_a is not None and bars_b is not None
    assert bars_a == bars_b


def test_mock_walk_history_differs_by_ticker() -> None:
    p = MockWalkProvider()
    aapl = p.history("AAPL", "1m")
    nvda = p.history("NVDA", "1m")
    assert aapl is not None and nvda is not None
    # Different tickers walk on different seeds — closes should differ.
    assert [c.c for c in aapl] != [c.c for c in nvda]


def test_mock_walk_history_invalid_period_returns_none() -> None:
    p = MockWalkProvider()
    assert p.history("AAPL", "bogus") is None


# ── Provider — caching ───────────────────────────────────────────────────


def test_caching_provider_history_hits_inner_once_within_ttl() -> None:
    """Two history calls within the TTL hit the inner provider only once."""

    class CountingInner:
        name = "counting"

        def __init__(self) -> None:
            self.calls = 0

        def quote(self, ticker: str):  # noqa: ANN201 — protocol shim
            return None

        def get_price(self, ticker: str):  # noqa: ANN201
            return None

        def history(self, ticker: str, period: str):  # noqa: ANN201
            self.calls += 1
            return _md.MockWalkProvider().history(ticker, period)

    inner = CountingInner()
    cached = CachingProvider(inner, ttl_seconds=60.0)
    first = cached.history("AAPL", "1m")
    second = cached.history("AAPL", "1m")
    assert first is not None
    assert second is not None
    assert first == second
    assert inner.calls == 1


def test_caching_provider_invalidate_drops_history_cache_for_ticker() -> None:
    inner = MockWalkProvider()
    cached = CachingProvider(inner, ttl_seconds=60.0)
    cached.history("AAPL", "1m")
    cached.history("AAPL", "3m")
    cached.history("NVDA", "1m")
    # Force a re-fetch by invalidating AAPL only.
    cached.invalidate("AAPL")
    assert "AAPL:1m" not in cached._history_cache
    assert "AAPL:3m" not in cached._history_cache
    assert "NVDA:1m" in cached._history_cache
