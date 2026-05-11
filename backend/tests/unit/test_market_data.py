"""Unit tests for the market-data provider stack.

The YahooQuoteProvider is exercised against a mocked httpx.Client — we
verify URL/query construction, success parsing, 4xx/5xx handling, network
errors, and malformed JSON. Cache + fallback wrappers are tested with a
fake provider so behavior is deterministic.
"""

from __future__ import annotations

from typing import Iterable

import httpx
import pytest

from app.services.market_data import (
    CachingProvider,
    FallbackProvider,
    MockWalkProvider,
    YahooQuoteProvider,
)


# ── Fakes ────────────────────────────────────────────────────────────────


class _FakeProvider:
    """Returns a programmed sequence of prices/None for any ticker."""

    def __init__(self, sequence: Iterable[float | None], name: str = "fake") -> None:
        self._seq = iter(list(sequence))
        self.name = name
        self.calls: list[str] = []

    def get_price(self, ticker: str) -> float | None:
        self.calls.append(ticker.upper().strip())
        try:
            return next(self._seq)
        except StopIteration:
            return None


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict | None = None):
        self.status_code = status_code
        self._json = json_body or {}

    def json(self) -> dict:
        return self._json


class _FakeClient:
    """Drop-in for httpx.Client — records calls, returns a programmed response."""

    def __init__(self, response: _FakeResponse | Exception) -> None:
        self._response = response
        self.requests: list[tuple[str, dict]] = []

    def get(self, url: str, params: dict | None = None):
        self.requests.append((url, params or {}))
        if isinstance(self._response, Exception):
            raise self._response
        return self._response

    def close(self) -> None:
        pass


# ── MockWalkProvider ─────────────────────────────────────────────────────


def test_mock_walk_provider_returns_stable_price_per_ticker():
    p = MockWalkProvider()
    first = p.get_price("AAPL")
    second = p.get_price("AAPL")
    assert first is not None and second is not None
    # Time has passed but with no `started_at` jump it's basically the same tick
    assert abs(first - second) < 50  # generous; just confirms it's bounded


def test_mock_walk_provider_independent_walks_per_ticker():
    p = MockWalkProvider()
    a = p.get_price("AAPL")
    n = p.get_price("NVDA")
    assert a != n  # different seeds → different bases


# ── CachingProvider ──────────────────────────────────────────────────────


def test_caching_provider_returns_cached_value_on_repeat():
    inner = _FakeProvider([100.0, 200.0])  # second call would return 200
    cached = CachingProvider(inner, ttl_seconds=10.0)
    assert cached.get_price("AAPL") == 100.0
    assert cached.get_price("AAPL") == 100.0  # cache hit; inner not consulted
    assert inner.calls == ["AAPL"]  # only one call to inner


def test_caching_provider_misses_for_different_tickers():
    inner = _FakeProvider([100.0, 200.0])
    cached = CachingProvider(inner, ttl_seconds=10.0)
    assert cached.get_price("AAPL") == 100.0
    assert cached.get_price("NVDA") == 200.0
    assert inner.calls == ["AAPL", "NVDA"]


def test_caching_provider_does_not_cache_none():
    inner = _FakeProvider([None, 150.0])
    cached = CachingProvider(inner, ttl_seconds=10.0)
    assert cached.get_price("AAPL") is None
    assert cached.get_price("AAPL") == 150.0
    assert inner.calls == ["AAPL", "AAPL"]


def test_caching_provider_invalidate_specific_ticker():
    inner = _FakeProvider([100.0, 110.0])
    cached = CachingProvider(inner, ttl_seconds=10.0)
    cached.get_price("AAPL")
    cached.invalidate("AAPL")
    assert cached.get_price("AAPL") == 110.0


# ── FallbackProvider ─────────────────────────────────────────────────────


def test_fallback_uses_primary_when_available():
    primary = _FakeProvider([100.0], name="primary")
    secondary = _FakeProvider([200.0], name="secondary")
    fb = FallbackProvider(primary, secondary)
    assert fb.get_price("AAPL") == 100.0
    assert secondary.calls == []


def test_fallback_drops_to_secondary_when_primary_returns_none():
    primary = _FakeProvider([None], name="primary")
    secondary = _FakeProvider([200.0], name="secondary")
    fb = FallbackProvider(primary, secondary)
    assert fb.get_price("AAPL") == 200.0
    assert primary.calls == ["AAPL"]
    assert secondary.calls == ["AAPL"]


def test_fallback_returns_none_only_when_both_fail():
    primary = _FakeProvider([None], name="primary")
    secondary = _FakeProvider([None], name="secondary")
    fb = FallbackProvider(primary, secondary)
    assert fb.get_price("AAPL") is None


# ── YahooQuoteProvider ───────────────────────────────────────────────────


def _yahoo_ok_body(price: float) -> dict:
    return {
        "chart": {
            "result": [{"meta": {"regularMarketPrice": price, "currency": "USD"}}],
            "error": None,
        }
    }


def test_yahoo_parses_regular_market_price():
    p = YahooQuoteProvider()
    p._client = _FakeClient(_FakeResponse(200, _yahoo_ok_body(187.45)))  # type: ignore[assignment]
    assert p.get_price("aapl") == 187.45
    url, params = p._client.requests[0]  # type: ignore[attr-defined]
    assert "AAPL" in url
    assert params["interval"] == "1m"
    assert params["range"] == "1d"


def test_yahoo_returns_none_on_non_200():
    p = YahooQuoteProvider()
    p._client = _FakeClient(_FakeResponse(429, {}))  # type: ignore[assignment]
    assert p.get_price("AAPL") is None


def test_yahoo_returns_none_on_network_error():
    p = YahooQuoteProvider()
    p._client = _FakeClient(httpx.ConnectError("dns fail"))  # type: ignore[assignment]
    assert p.get_price("AAPL") is None


def test_yahoo_returns_none_on_empty_result():
    p = YahooQuoteProvider()
    body = {"chart": {"result": [], "error": None}}
    p._client = _FakeClient(_FakeResponse(200, body))  # type: ignore[assignment]
    assert p.get_price("AAPL") is None


def test_yahoo_returns_none_on_missing_price():
    p = YahooQuoteProvider()
    body = {"chart": {"result": [{"meta": {"currency": "USD"}}], "error": None}}
    p._client = _FakeClient(_FakeResponse(200, body))  # type: ignore[assignment]
    assert p.get_price("AAPL") is None


# ── Full real-stack assembly ─────────────────────────────────────────────


def test_assembled_stack_yahoo_then_cache_then_mock_fallback():
    """End-to-end: Yahoo fails → cache passes None → mock fallback fires."""
    yahoo = YahooQuoteProvider()
    yahoo._client = _FakeClient(_FakeResponse(500, {}))  # type: ignore[assignment]
    stack = FallbackProvider(
        primary=CachingProvider(yahoo, ttl_seconds=10.0),
        secondary=MockWalkProvider(),
    )
    price = stack.get_price("AAPL")
    assert price is not None and price > 0  # mock always returns something
