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

Each call returns a `Quote(price, source)` so the caller knows WHICH leaf
provider actually served the price — not just the stack name. The Flutter
LIVE / MOCK pill keys on this: substring "yahoo" in the source string
means we honestly served real prices for that quote. Without per-call
source the pill silently lied during Yahoo rate-limits — the stack name
contains "yahoo" even when every fetch fell through to mock.

The legacy `get_price(ticker) -> float | None` API is kept as a thin
wrapper over `quote()` so callers that don't care about provenance stay
simple. Returning `None` instead of raising lets the caller decide whether
to retry, fall back, or surface an error.

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
from typing import NamedTuple, Protocol

import httpx

from app.core.config import settings
from app.core.logging import logger


# ── Interface ────────────────────────────────────────────────────────────


class Quote(NamedTuple):
    """A priced quote plus the leaf provider that produced it."""

    price: float
    source: str


class MarketDataProvider(Protocol):
    name: str

    def quote(self, ticker: str) -> Quote | None:
        """Return the current quote for `ticker`, or None on any failure.

        `Quote.source` MUST identify the leaf provider that actually
        produced the price (e.g. `"yahoo"` or `"mock_walk"`) — not a
        stack name like `"fallback(...)"`. Wrappers (cache, fallback)
        forward the inner's source rather than substituting their own.
        """
        ...

    def get_price(self, ticker: str) -> float | None:
        """Back-compat shim — returns just the price."""
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

    def quote(self, ticker: str) -> Quote | None:
        t = ticker.upper().strip()
        with self._lock:
            walk = self._walks.get(t)
            if walk is None:
                walk = _walk_for(t)
                self._walks[t] = walk
        return Quote(price=walk.price_at(), source=self.name)

    def get_price(self, ticker: str) -> float | None:
        q = self.quote(ticker)
        return q.price if q is not None else None


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

    def quote(self, ticker: str) -> Quote | None:
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
            return Quote(price=float(price), source=self.name)
        except (ValueError, KeyError, TypeError) as exc:
            logger.warn("yahoo_parse_error", ticker=t, error=str(exc))
            return None

    def get_price(self, ticker: str) -> float | None:
        q = self.quote(ticker)
        return q.price if q is not None else None

    def close(self) -> None:
        self._client.close()


# ── Caching wrapper ──────────────────────────────────────────────────────


class CachingProvider:
    """Wrap any provider with a small per-ticker TTL cache.

    Caches the FULL Quote (price + source) so callers see the original
    leaf provider name even on a cache hit — vital for the LIVE / MOCK
    pill: a cached Yahoo quote is still honestly a Yahoo quote.
    """

    def __init__(self, inner: MarketDataProvider, ttl_seconds: float = 60.0) -> None:
        self._inner = inner
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[Quote, float]] = {}  # ticker → (quote, expires_at)
        self._lock = RLock()
        self.name = f"cache({inner.name})"

    def quote(self, ticker: str) -> Quote | None:
        t = ticker.upper().strip()
        now = time.time()
        with self._lock:
            hit = self._cache.get(t)
            if hit is not None and hit[1] > now:
                return hit[0]
        # Miss — go to inner. Don't hold the lock during a possibly-slow call.
        q = self._inner.quote(t)
        if q is not None:
            with self._lock:
                self._cache[t] = (q, now + self._ttl)
        return q

    def get_price(self, ticker: str) -> float | None:
        q = self.quote(ticker)
        return q.price if q is not None else None

    def invalidate(self, ticker: str | None = None) -> None:
        with self._lock:
            if ticker is None:
                self._cache.clear()
            else:
                self._cache.pop(ticker.upper().strip(), None)


# ── yfinance (preferred over raw Yahoo HTTP) ─────────────────────────────


class YfinanceProvider:
    """Quotes via the `yfinance` Python lib.

    yfinance handles the Yahoo-side dance the keyless HTTP path couldn't:
    UA rotation, the cookie + crumb session that the chart endpoint
    started requiring in 2024, and exponential backoff on 429. As a
    result it actually serves LIVE prices most of the time, where the
    raw httpx client was getting 429'd persistently.

    Returned Quote.source is `"yfinance"` — distinct from the legacy
    `"yahoo"` so the LIVE/MOCK pill stays honest about which path
    fired. The Flutter `isLivePrice` check should accept either as
    "real" (anything that's not `mock_walk` / `unavailable`).

    Heavy import: yfinance pulls pandas + numpy. We do the import
    lazily inside __init__ so test environments that mock the
    provider don't pay the boot cost.
    """

    name = "yfinance"

    def __init__(self) -> None:
        import yfinance as yf  # lazy — saves ~0.5s on test/cold imports
        self._yf = yf

    def quote(self, ticker: str) -> Quote | None:
        t = ticker.upper().strip()
        try:
            info = self._yf.Ticker(t).fast_info
            price = info.last_price
        except Exception as exc:
            logger.warn("yfinance_error", ticker=t, error=str(exc))
            return None
        if price is None or price <= 0:
            return None
        return Quote(price=float(price), source=self.name)

    def get_price(self, ticker: str) -> float | None:
        q = self.quote(ticker)
        return q.price if q is not None else None


# ── Fallback chain ───────────────────────────────────────────────────────


class FallbackProvider:
    """Try `primary`; if it returns None, fall through to `secondary`.

    The returned Quote carries the leaf provider that actually served it —
    NOT this wrapper's name. Otherwise the LIVE / MOCK pill can't tell
    which leg fired: during sustained Yahoo rate-limits the secondary
    (mock_walk) serves every call, but the stack name still contains
    "yahoo", so the pill would lie.
    """

    def __init__(self, primary: MarketDataProvider, secondary: MarketDataProvider) -> None:
        self._primary = primary
        self._secondary = secondary
        self.name = f"fallback({primary.name}->{secondary.name})"

    def quote(self, ticker: str) -> Quote | None:
        q = self._primary.quote(ticker)
        if q is not None:
            return q
        return self._secondary.quote(ticker)

    def get_price(self, ticker: str) -> float | None:
        q = self.quote(ticker)
        return q.price if q is not None else None


# ── Singleton factory ────────────────────────────────────────────────────


_provider: MarketDataProvider | None = None


def get_market_data_provider() -> MarketDataProvider:
    """Returns the configured provider stack.

    Honours `settings.use_real_market_data`. Switching env requires a
    backend restart (singleton). Tests can call `set_market_data_provider()`
    to inject a fake.

    Stack: cached yfinance primary → MockWalkProvider secondary.
    yfinance handles the rate-limit dance Yahoo's keyless chart endpoint
    couldn't, so the secondary is rarely needed in practice — but it's
    a guaranteed never-fail floor for the quote-on-demand UX.
    """
    global _provider
    if _provider is None:
        if settings.use_real_market_data:
            try:
                primary = YfinanceProvider()
            except ImportError:
                # yfinance not installed (slim test image, frozen env).
                # Fall back to the legacy keyless Yahoo path so the
                # demo still has SOMETHING beyond mock — even if it's
                # rate-limit-prone.
                logger.warn("yfinance_unavailable_falling_back_to_keyless_yahoo")
                primary = YahooQuoteProvider()  # type: ignore[assignment]
            _provider = FallbackProvider(
                primary=CachingProvider(primary, ttl_seconds=60.0),
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
