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
    change_pct: float = 0.0      # vs previous close; 0.0 for mock/degraded
    market_state: str = "CLOSED" # REGULAR | PRE | POST | CLOSED


class Candle(NamedTuple):
    """One OHLCV bar. `t` is Unix epoch seconds (UTC)."""

    t: int
    o: float
    h: float
    low: float  # `low` because `l` shadows builtins / lint flags single-letter
    c: float
    v: float


class NewsItem(NamedTuple):
    """One news article returned by the news provider."""

    title: str
    link: str
    publisher: str
    published_at: int  # Unix epoch seconds


class EarningsInfo(NamedTuple):
    """Upcoming earnings window for a ticker (within 90 days), or nulls."""

    earnings_date: str | None   # ISO date "YYYY-MM-DD"
    quarter: str | None         # "Q1"–"Q4" derived from month
    eps_estimate: float | None  # yfinance Earnings Average


# Period → (yfinance period, yfinance interval, mock-walk candle count, mock-walk seconds-per-candle).
# Mock-walk counts mirror what yfinance returns for typical regular-session symbols.
_PERIOD_MAP: dict[str, tuple[str, str, int, int]] = {
    "1d": ("1d",  "5m",  78, 5 * 60),                  # ~6.5h session / 5m
    "1w": ("5d",  "30m", 65, 30 * 60),                 # 5 sessions × 13 bars
    "1m": ("1mo", "1d",  22, 24 * 3600),               # ~22 trading days
    "3m": ("3mo", "1d",  65, 24 * 3600),               # ~65 trading days
    "1y": ("1y",  "1wk", 52, 7 * 24 * 3600),
    "5y": ("5y",  "1mo", 60, 30 * 24 * 3600),
}

VALID_PERIODS: tuple[str, ...] = tuple(_PERIOD_MAP.keys())


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

    def history(self, ticker: str, period: str) -> list[Candle] | None:
        """Return OHLCV candles for `period`, or None on any failure.

        Wrappers (cache, fallback) propagate the inner result so the
        leaf provider that actually served the bars stays attributable
        to the caller via the surrounding API response's `source` field.
        """
        ...

    def news(self, ticker: str, limit: int = 5) -> list[NewsItem] | None:
        """Return recent news articles for `ticker`, or None on any failure."""
        ...

    def earnings(self, ticker: str) -> EarningsInfo | None:
        """Return upcoming earnings info within 90 days, or None if unavailable."""
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

    def history(self, ticker: str, period: str) -> list[Candle] | None:
        """Synthesize deterministic OHLCV from the per-ticker random walk.

        Anchors the latest candle at "now" and walks backwards by the
        period's bar interval. Open = previous close so consecutive
        candles chain visually. High/low are ±0.5% noise seeded by
        `hash((ticker, t))` so the same (ticker, period) always returns
        the same bars within the same epoch second — important for the
        cache-hit equality test. Volume is a fixed 1_000_000.
        """
        if period not in _PERIOD_MAP:
            return None
        t = ticker.upper().strip()
        with self._lock:
            walk = self._walks.get(t)
            if walk is None:
                walk = _walk_for(t)
                self._walks[t] = walk
        _, _, count, step = _PERIOD_MAP[period]
        now = int(time.time())
        # Anchor each bar at a tick boundary so repeated calls within the
        # same second hit the same timestamps (matters for cache equality).
        anchor = now - (now % step)
        timestamps = [anchor - step * (count - 1 - i) for i in range(count)]
        candles: list[Candle] = []
        prev_close: float | None = None
        for ts in timestamps:
            close = walk.price_at(float(ts))
            open_ = prev_close if prev_close is not None else close
            jitter = random.Random(hash((t, ts))).uniform(-0.005, 0.005)
            mid = (open_ + close) / 2.0
            high = round(max(open_, close) * (1 + abs(jitter)), 4)
            low = round(min(open_, close) * (1 - abs(jitter)), 4)
            # Defensive: if open == close (flat tick), nudge so high > low.
            if high <= low:
                high = round(mid * 1.001, 4)
                low = round(mid * 0.999, 4)
            candles.append(Candle(t=ts, o=round(open_, 4), h=high, low=low, c=round(close, 4), v=1_000_000.0))
            prev_close = close
        return candles

    def news(self, ticker: str, limit: int = 5) -> list[NewsItem] | None:
        return None

    def earnings(self, ticker: str) -> EarningsInfo | None:
        return None


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
            change_pct = float(meta.get("regularMarketChangePercent") or 0.0)
            market_state = str(meta.get("marketState") or "CLOSED")
            return Quote(
                price=float(price),
                source=self.name,
                change_pct=change_pct,
                market_state=market_state,
            )
        except (ValueError, KeyError, TypeError) as exc:
            logger.warn("yahoo_parse_error", ticker=t, error=str(exc))
            return None

    def get_price(self, ticker: str) -> float | None:
        q = self.quote(ticker)
        return q.price if q is not None else None

    def history(self, ticker: str, period: str) -> list[Candle] | None:
        # Keyless chart endpoint isn't wired for OHLC history here —
        # the production primary is YfinanceProvider. Return None so
        # the fallback chain hands off to MockWalkProvider.
        return None

    def news(self, ticker: str, limit: int = 5) -> list[NewsItem] | None:
        return None

    def earnings(self, ticker: str) -> EarningsInfo | None:
        return None

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
        self._history_cache: dict[str, tuple[list[Candle], float]] = {}  # f"{ticker}:{period}" → (candles, expires_at)
        self._news_cache: dict[str, tuple[list[NewsItem], float]] = {}  # f"{ticker}:{limit}" → (items, expires_at)
        self._earnings_cache: dict[str, tuple[EarningsInfo, float]] = {}  # ticker → (info, expires_at)
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

    def history(self, ticker: str, period: str) -> list[Candle] | None:
        key = f"{ticker.upper().strip()}:{period}"
        now = time.time()
        with self._lock:
            hit = self._history_cache.get(key)
            if hit is not None and hit[1] > now:
                return hit[0]
        bars = self._inner.history(ticker, period)
        if bars is not None:
            with self._lock:
                self._history_cache[key] = (bars, now + self._ttl)
        return bars

    def news(self, ticker: str, limit: int = 5) -> list[NewsItem] | None:
        key = f"{ticker.upper().strip()}:{limit}"
        now = time.time()
        with self._lock:
            hit = self._news_cache.get(key)
            if hit is not None and hit[1] > now:
                return hit[0]
        items = self._inner.news(ticker, limit)
        if items is not None:
            with self._lock:
                self._news_cache[key] = (items, now + 300.0)  # 5-min TTL
        return items

    def earnings(self, ticker: str) -> EarningsInfo | None:
        t = ticker.upper().strip()
        now = time.time()
        with self._lock:
            hit = self._earnings_cache.get(t)
            if hit is not None and hit[1] > now:
                return hit[0]
        info = self._inner.earnings(ticker)
        if info is not None:
            with self._lock:
                self._earnings_cache[t] = (info, now + 21600.0)  # 6-hour TTL
        return info

    def invalidate(self, ticker: str | None = None) -> None:
        with self._lock:
            if ticker is None:
                self._cache.clear()
                self._history_cache.clear()
                self._news_cache.clear()
                self._earnings_cache.clear()
            else:
                t = ticker.upper().strip()
                self._cache.pop(t, None)
                self._earnings_cache.pop(t, None)
                # Drop every keyed entry for this ticker.
                self._history_cache = {
                    k: v for k, v in self._history_cache.items() if not k.startswith(f"{t}:")
                }
                self._news_cache = {
                    k: v for k, v in self._news_cache.items() if not k.startswith(f"{t}:")
                }


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

    def history(self, ticker: str, period: str) -> list[Candle] | None:
        if period not in _PERIOD_MAP:
            return None
        t = ticker.upper().strip()
        yf_period, yf_interval, _, _ = _PERIOD_MAP[period]
        try:
            df = self._yf.Ticker(t).history(period=yf_period, interval=yf_interval)
        except Exception as exc:
            logger.warn("yfinance_history_error", ticker=t, period=period, error=str(exc))
            return None
        if df is None or df.empty:
            return None
        bars: list[Candle] = []
        for ts, row in df.iterrows():
            # Index is a pandas Timestamp (tz-aware UTC for intraday, naive for daily/weekly/monthly).
            try:
                epoch = int(ts.timestamp())
            except (AttributeError, ValueError):
                continue
            try:
                o = float(row["Open"])
                h = float(row["High"])
                low = float(row["Low"])
                c = float(row["Close"])
                v = float(row.get("Volume", 0) or 0)
            except (KeyError, TypeError, ValueError):
                continue
            bars.append(Candle(t=epoch, o=o, h=h, low=low, c=c, v=v))
        return bars or None

    def news(self, ticker: str, limit: int = 5) -> list[NewsItem] | None:
        t = ticker.upper().strip()
        try:
            raw = self._yf.Ticker(t).news or []
        except Exception as exc:
            logger.warn("yfinance_news_error", ticker=t, error=str(exc))
            return None
        items: list[NewsItem] = []
        for a in raw[:limit]:
            try:
                # yfinance ≥0.2 nests article fields under a "content" key;
                # fall back to the flat dict for older format.
                content = a.get("content") or a
                title = str(content.get("title", "") or a.get("title", ""))
                url_obj = content.get("clickThroughUrl") or content.get("canonicalUrl") or {}
                link = str(url_obj.get("url", "") or content.get("link", "") or a.get("link", ""))
                provider_obj = content.get("provider") or {}
                publisher = str(
                    provider_obj.get("displayName", "")
                    or content.get("publisher", "")
                    or a.get("publisher", "")
                )
                pub_str = content.get("pubDate") or a.get("pubDate") or ""
                if pub_str:
                    from datetime import datetime, timezone
                    published_at = int(
                        datetime.fromisoformat(pub_str.replace("Z", "+00:00")).timestamp()
                    )
                else:
                    published_at = int(a.get("providerPublishTime", 0))
                items.append(NewsItem(title=title, link=link, publisher=publisher, published_at=published_at))
            except (KeyError, TypeError, ValueError):
                continue
        return items or None

    def earnings(self, ticker: str) -> EarningsInfo | None:
        import datetime

        t = ticker.upper().strip()
        try:
            import pandas as pd

            cal = self._yf.Ticker(t).calendar
            if not cal:
                return None
            dates = cal.get("Earnings Date") or []
            if not isinstance(dates, list):
                dates = [dates]
            now = datetime.datetime.now(datetime.timezone.utc)
            cutoff = now + datetime.timedelta(days=90)
            target = None
            for d in dates:
                try:
                    ts = d if isinstance(d, datetime.datetime) else pd.Timestamp(d).to_pydatetime()
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=datetime.timezone.utc)
                    else:
                        ts = ts.astimezone(datetime.timezone.utc)
                    if now <= ts <= cutoff:
                        target = ts
                        break
                except Exception:
                    continue
            if target is None:
                return None
            q_map = {
                1: "Q1", 2: "Q1", 3: "Q1",
                4: "Q2", 5: "Q2", 6: "Q2",
                7: "Q3", 8: "Q3", 9: "Q3",
                10: "Q4", 11: "Q4", 12: "Q4",
            }
            eps = cal.get("Earnings Average")
            return EarningsInfo(
                earnings_date=target.strftime("%Y-%m-%d"),
                quarter=q_map.get(target.month),
                eps_estimate=float(eps) if eps is not None else None,
            )
        except Exception as exc:
            logger.warn("yfinance_earnings_error", ticker=t, error=str(exc))
            return None


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

    def history(self, ticker: str, period: str) -> list[Candle] | None:
        bars = self._primary.history(ticker, period)
        if bars:
            return bars
        return self._secondary.history(ticker, period)

    def news(self, ticker: str, limit: int = 5) -> list[NewsItem] | None:
        items = self._primary.news(ticker, limit)
        if items:
            return items
        return self._secondary.news(ticker, limit)

    def earnings(self, ticker: str) -> EarningsInfo | None:
        info = self._primary.earnings(ticker)
        if info is not None:
            return info
        return self._secondary.earnings(ticker)


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
