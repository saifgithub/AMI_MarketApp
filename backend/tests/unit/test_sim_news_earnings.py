"""Tests for GET /v1/sim/news/{ticker} and GET /v1/sim/earnings/{ticker}.

Bundles 4+5 of the TickerDetail surface (AT:R42). Both routes are public
(no auth) and delegate to sim.current_news() / sim.current_earnings().
CachingProvider wraps news at 300s TTL and earnings at 21600s TTL.
MockWalkProvider returns None for both (news/earnings are real-world only),
so a FakeProvider stub is used for route-shape tests.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.sim import router as sim_router
from app.services import market_data as _md
from app.services.market_data import (
    CachingProvider,
    EarningsInfo,
    MockWalkProvider,
    NewsItem,
)


# ── Shared fake provider ──────────────────────────────────────────────────


class FakeProvider:
    """Minimal provider stub returning canned news + earnings."""

    name = "fake"

    def __init__(
        self,
        news_items: list[NewsItem] | None = None,
        earnings_info: EarningsInfo | None = None,
    ) -> None:
        self._news = news_items
        self._earnings = earnings_info
        self.news_calls = 0
        self.earnings_calls = 0

    def quote(self, ticker: str) -> _md.Quote | None:
        return _md.Quote(price=100.0, source=self.name)

    def get_price(self, ticker: str) -> float | None:
        return 100.0

    def history(self, ticker: str, period: str) -> list[_md.Candle] | None:
        return None

    def news(self, ticker: str, limit: int = 5) -> list[NewsItem] | None:
        self.news_calls += 1
        return self._news

    def earnings(self, ticker: str) -> EarningsInfo | None:
        self.earnings_calls += 1
        return self._earnings


_FAKE_ARTICLES = [
    NewsItem(
        title="Apple hits $4T market cap",
        link="https://example.com/a1",
        publisher="Reuters",
        published_at=1748000000,
    ),
    NewsItem(
        title="iPhone sales surge",
        link="https://example.com/a2",
        publisher="Bloomberg",
        published_at=1748010000,
    ),
]

_FAKE_EARNINGS = EarningsInfo(
    earnings_date="2026-07-25",
    quarter="Q3",
    eps_estimate=2.04,
)


@pytest.fixture(autouse=True)
def inject_fake_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the market data singleton with FakeProvider for every test."""
    fake = FakeProvider(news_items=_FAKE_ARTICLES, earnings_info=_FAKE_EARNINGS)
    monkeypatch.setattr(_md, "_provider", fake)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(sim_router)
    return TestClient(app, raise_server_exceptions=False)


# ── News route ────────────────────────────────────────────────────────────


def test_news_returns_articles(client: TestClient) -> None:
    r = client.get("/v1/sim/news/AAPL")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert "source" in body
    articles = body["articles"]
    assert isinstance(articles, list)
    assert len(articles) == 2
    for a in articles:
        assert set(a.keys()) == {"title", "link", "publisher", "published_at"}
        assert isinstance(a["title"], str) and a["title"]
        assert isinstance(a["link"], str) and a["link"]
        assert isinstance(a["publisher"], str)
        assert isinstance(a["published_at"], int) and a["published_at"] > 0


def test_news_empty_when_no_data(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_md, "_provider", FakeProvider(news_items=None))
    r = client.get("/v1/sim/news/AAPL")
    assert r.status_code == 200
    assert r.json()["articles"] == []


def test_news_ticker_normalized(client: TestClient) -> None:
    r = client.get("/v1/sim/news/aapl")
    assert r.status_code == 200
    assert r.json()["ticker"] == "AAPL"


def test_news_is_public_no_auth_required(client: TestClient) -> None:
    r = client.get("/v1/sim/news/AAPL")
    assert r.status_code == 200


def test_news_limit_respected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Route passes the limit param through — FakeProvider always returns _FAKE_ARTICLES (2 items);
    what matters is the route doesn't error."""
    r = client.get("/v1/sim/news/AAPL?limit=1")
    assert r.status_code == 200


# ── Earnings route ────────────────────────────────────────────────────────


def test_earnings_returns_date_shape(client: TestClient) -> None:
    r = client.get("/v1/sim/earnings/AAPL")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert "source" in body
    assert set(body.keys()) == {"ticker", "source", "earnings_date", "quarter", "eps_estimate"}
    assert body["earnings_date"] == "2026-07-25"
    assert body["quarter"] == "Q3"
    assert body["eps_estimate"] == pytest.approx(2.04)


def test_earnings_returns_null_fields_when_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_md, "_provider", FakeProvider(earnings_info=None))
    r = client.get("/v1/sim/earnings/AAPL")
    assert r.status_code == 200
    body = r.json()
    assert body["earnings_date"] is None
    assert body["quarter"] is None
    assert body["eps_estimate"] is None


def test_earnings_ticker_normalized(client: TestClient) -> None:
    r = client.get("/v1/sim/earnings/aapl")
    assert r.status_code == 200
    assert r.json()["ticker"] == "AAPL"


def test_earnings_is_public_no_auth_required(client: TestClient) -> None:
    r = client.get("/v1/sim/earnings/AAPL")
    assert r.status_code == 200


# ── CachingProvider — TTL tests ───────────────────────────────────────────


def test_caching_provider_news_hits_inner_once_within_ttl() -> None:
    inner = FakeProvider(news_items=_FAKE_ARTICLES)
    cached = CachingProvider(inner, ttl_seconds=60.0)
    first = cached.news("AAPL", 5)
    second = cached.news("AAPL", 5)
    assert first is not None
    assert second is not None
    assert first == second
    assert inner.news_calls == 1  # second call was a cache hit


def test_caching_provider_earnings_hits_inner_once_within_ttl() -> None:
    inner = FakeProvider(earnings_info=_FAKE_EARNINGS)
    cached = CachingProvider(inner, ttl_seconds=60.0)
    first = cached.earnings("AAPL")
    second = cached.earnings("AAPL")
    assert first is not None
    assert second is not None
    assert first == second
    assert inner.earnings_calls == 1


def test_caching_provider_invalidate_clears_news_and_earnings() -> None:
    inner = FakeProvider(news_items=_FAKE_ARTICLES, earnings_info=_FAKE_EARNINGS)
    cached = CachingProvider(inner, ttl_seconds=60.0)
    cached.news("AAPL", 5)
    cached.earnings("AAPL")
    cached.news("NVDA", 5)
    cached.invalidate("AAPL")
    assert "AAPL:5" not in cached._news_cache
    assert "AAPL" not in cached._earnings_cache
    # NVDA news entry should be untouched.
    assert "NVDA:5" in cached._news_cache
