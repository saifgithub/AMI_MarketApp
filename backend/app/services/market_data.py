"""Market data — pluggable real/mock price providers behind a single interface.

SimEngine used to own a deterministic per-ticker random walk. That was fine
for a demo but it lies: AAPL drifts according to `hash("AAPL")` rather than
what the market did this morning. This module replaces that surface with a
composable provider stack:

  YahooQuoteProvider   → keyless HTTP fetch of Yahoo's public chart endpoint
  CachingProvider      → 60-second TTL so a tick refresh doesn't hammer Yahoo
  MockWalkProvider     → the original deterministic random walk
  FallbackProvider     → primary first; if it returns None, drop to secondary

`get_market_data_provider()` returns the configured stack:
  - When `USE_REAL_MARKET_DATA=true` in env: cached Yahoo, falling back to
    the mock walk on network errors / unknown tickers.
  - Otherwise: just the mock walk (legacy behavior).

The provider returns `None` on failure rather than raising, so the caller
can decide whether to retry, fall back, or surface an error. The fallback
chain hides that complexity from `SimEngine`.

Sync, not async — `SimEngine` and the `/v1/sim/*` route are sync. The
network fetch is fast (~150ms) and behind a 60s cache, so blocking is fine
for MVP. If this becomes hot, swap `httpx.Client` for `httpx.AsyncClient`
and the rest of the stack lifts unchanged.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.logging import logger


# ── Interface ────────────────────────────────────────────────────────────


class MarketDataProvider(Protocol):
    name: str

    def get_price(self, ticker: str) -> float | None:
        """Return the current price for `ticker`, or None on any failure."""
        ...


# ── Mock walk (extracted from sim_engine.py so SimEngine no longer owns it) ──


@dataclass
class _PriceWalk:
    """Per-ticker deterministic random walk seeded by ticker."""

    base: float
    drift_per_sec: float
    volatility: float
    started_at: float = field(default_factory=time.time)
    rng_seed: int = 0

    def price_at(self, now_ts: float | None = None) -> float:
        now_ts = now_ts or time.time()
        elapsed = max(0.0, now_ts - self.started_at)
        steps = int(elapsed)
        rng = random.Random(self.rng_seed)
        v = self.base
        for _ in range(steps):
            shock = rng.gauss(0, self.volatility)
            v = v * (1 + self.drift_per_sec + shock)
        return max(0.01, round(v, 2))


def _walk_for(ticker: str) -> _PriceWalk:
    seed = hash(ticker.upper())
    rng = random.Random(seed)
    base = 50 + rng.uniform(0, 400)
    drift = rng.uniform(-0.0002, 0.0004)
    vol = rng.uniform(0.002, 0.008)
    return _PriceWalk(
        base=round(base, 2),
        drift_per_sec=drift,
        volatility=vol,
        rng_seed=seed,
    )


class MockWalkProvider:
    """Deterministic per-ticker random walk; never fails."""

    name = "mock_walk"

    def __init__(self) -> None:
        self._walks: dict[str, _PriceWalk] = {}
        self._lock = RLock()

    def get_price(self, ticker: str) -> float | None:
        t = ticker.upper().strip()
        with self._lock:
            walk = self._walks.get(t)
            if walk is None:
                walk = _walk_for(t)
                self._walks[t] = walk
        return walk.price_at()


# ── Yahoo Finance ────────────────────────────────────────────────────────


_YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
# Yahoo blocks the default httpx user-agent. Pretend to be a browser.
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class YahooQuoteProvider:
    """Keyless real-time-ish quotes from Yahoo's public chart endpoint.

    The endpoint serves the same data yfinance pulls. Up to ~15min delayed
    on free access; good enough for a sim portfolio.
    """

    name = "yahoo"

    def __init__(self, timeout_seconds: float = 4.0) -> None:
        self._client = httpx.Client(
            timeout=timeout_seconds,
            headers={"User-Agent": _BROWSER_UA, "Accept": "application/json"},
        )

    def get_price(self, ticker: str) -> float | None:
        t = ticker.upper().strip()
        try:
            resp = self._client.get(
                _YAHOO_URL.format(ticker=t),
                params={"interval": "1m", "range": "1d"},
            )
        except httpx.HTTPError as exc:
            logger.warn("yahoo_network_error", ticker=t, error=str(exc))
            return None

        if resp.status_code != 200:
            logger.warn("yahoo_bad_status", ticker=t, status=resp.status_code)
            return None

        try:
            payload = resp.json()
            result = (payload.get("chart") or {}).get("result") or []
            if not result:
                return None
            meta = result[0].get("meta") or {}
            price = meta.get("regularMarketPrice")
            if price is None:
                return None
            return float(price)
        except (ValueError, KeyError, TypeError) as exc:
            logger.warn("yahoo_parse_error", ticker=t, error=str(exc))
            return None

    def close(self) -> None:
        self._client.close()


# ── Caching wrapper ──────────────────────────────────────────────────────


class CachingProvider:
    """Wrap any provider with a small per-ticker TTL cache."""

    def __init__(self, inner: MarketDataProvider, ttl_seconds: float = 60.0) -> None:
        self._inner = inner
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[float, float]] = {}  # ticker → (price, expires_at)
        self._lock = RLock()
        self.name = f"cache({inner.name})"

    def get_price(self, ticker: str) -> float | None:
        t = ticker.upper().strip()
        now = time.time()
        with self._lock:
            hit = self._cache.get(t)
            if hit is not None and hit[1] > now:
                return hit[0]
        # Miss — go to inner. Don't hold the lock during a possibly-slow call.
        price = self._inner.get_price(t)
        if price is not None:
            with self._lock:
                self._cache[t] = (price, now + self._ttl)
        return price

    def invalidate(self, ticker: str | None = None) -> None:
        with self._lock:
            if ticker is None:
                self._cache.clear()
            else:
                self._cache.pop(ticker.upper().strip(), None)


# ── Fallback chain ───────────────────────────────────────────────────────


class FallbackProvider:
    """Try `primary`; if it returns None, fall through to `secondary`."""

    def __init__(self, primary: MarketDataProvider, secondary: MarketDataProvider) -> None:
        self._primary = primary
        self._secondary = secondary
        self.name = f"fallback({primary.name}->{secondary.name})"

    def get_price(self, ticker: str) -> float | None:
        price = self._primary.get_price(ticker)
        if price is not None:
            return price
        return self._secondary.get_price(ticker)


# ── Singleton factory ────────────────────────────────────────────────────


_provider: MarketDataProvider | None = None


def get_market_data_provider() -> MarketDataProvider:
    """Returns the configured provider stack.

    Honours `settings.use_real_market_data`. Switching env requires a
    backend restart (singleton). Tests can call `set_market_data_provider()`
    to inject a fake.
    """
    global _provider
    if _provider is None:
        if settings.use_real_market_data:
            _provider = FallbackProvider(
                primary=CachingProvider(YahooQuoteProvider(), ttl_seconds=60.0),
                secondary=MockWalkProvider(),
            )
            logger.info("market_data_provider_registered", stack=_provider.name)
        else:
            _provider = MockWalkProvider()
            logger.info("market_data_provider_registered", stack=_provider.name)
    return _provider


def set_market_data_provider(provider: MarketDataProvider | None) -> None:
    """Replace the singleton. Used by tests; safe to call with None to reset."""
    global _provider
    _provider = provider
