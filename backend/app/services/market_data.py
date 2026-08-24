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

Sync, deliberately. The `/v1/sim/*` and related routes are `async def` on a
single-uvicorn-process, no-`--workers` event loop (see
`test_no_blocking_io_in_async_routes.py`) — a synchronous fetch called
directly from a route handler DOES block every other user's request for the
round-trip; that was DEF116 and DEF120. The routes stay correct by wrapping
`SimEngine`'s sync accessors in `await asyncio.to_thread(...)` at the call
site, and `SimEngine._marks_with_quotes` fans out multi-ticker fetches over
a `concurrent.futures.ThreadPoolExecutor`, not by making this provider
stack `async`. Swapping `httpx.Client` for `httpx.AsyncClient` here would
need `SimEngine` to become `async def` throughout and would collide with
that sync fan-out (DEF120 D8) — out of scope unless the provider stack
itself becomes the bottleneck.
"""

from __future__ import annotations

import datetime
import math
import random
import time
import zlib
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, NamedTuple, Protocol

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.services.asof_context import current_asof
from app.trading_math.market_hours import is_us_market_open


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
    """One news article returned by the news provider.

    CR147 B.2 / CR179 Leg 3 — `summary` is the provider's own abstract, present
    on 40 of 40 articles measured across NVDA/GRAB/KTOS/BAC (median 183 chars,
    max 500). It was parsed past for the entire life of this feed. Defaulted to
    "" so every other provider and test that builds a NewsItem without it is
    unaffected.
    """

    title: str
    link: str
    publisher: str
    published_at: int  # Unix epoch seconds
    summary: str = ""


class EarningsInfo(NamedTuple):
    """Upcoming earnings window for a ticker (within 90 days), or nulls.

    CR030 added the two dividend fields — they ride on the same object (and the
    same 6-hour earnings cache) rather than a second endpoint. Defaulted to None
    so every other provider / test that builds an EarningsInfo without them is
    unaffected. Both are None for a non-dividend payer; a suspended dividend can
    surface an ex-date with a None rate (see `_dividend_fields_from_info`).
    """

    earnings_date: str | None   # ISO date "YYYY-MM-DD"
    quarter: str | None         # "Q1"–"Q4" derived from month
    eps_estimate: float | None  # yfinance Earnings Average
    ex_dividend_date: str | None = None  # CR030 — ISO "YYYY-MM-DD" from yfinance exDividendDate (unix ts)
    dividend_rate: float | None = None   # CR030 — annual per-share USD; None when 0.0 / absent


class OptionQuote(NamedTuple):
    """One strike row of an option chain, as served (CR172 §4).

    Any field the provider did not serve is None, never a zero — on an
    illiquid strike Yahoo legitimately serves `bid=0/ask=0.05` (a real quote
    meaning "worthless") and NaN for volume, and collapsing the two cases
    would erase exactly the distinction `classify_option_quote` exists to
    make. `implied_vol` is the provider's OWN figure, provenance unknown and
    occasionally absurd; sanity-gating it is the enrichment layer's job
    (`services/option_chain.py`), not this transport shape's.
    """

    strike: float
    bid: float | None
    ask: float | None
    last: float | None
    volume: int | None
    open_interest: int | None
    implied_vol: float | None
    in_the_money: bool | None = None


class OptionChain(NamedTuple):
    """One (underlying, expiry) chain. `source` names the LEAF provider —
    the same contract `Quote.source` carries, for the same LIVE/MOCK-pill
    honesty reason: wrappers forward it, never substitute a stack name."""

    underlying: str
    expiry: datetime.date
    calls: tuple[OptionQuote, ...]
    puts: tuple[OptionQuote, ...]
    source: str


# CR172 D2 (ratified 2026-08-20): a strike whose relative spread exceeds this
# is blocked from filling, with the width surfaced as the reason — a wide
# spread is a LIQUIDITY failure and one of the real lessons options teach.
OPTION_MAX_SPREAD_PCT = 0.25

# CR172 §4 — chain-specific cache TTLs (the 60s quote TTL is wrong here: a
# chain is a bigger, slower-moving payload; the expiry list changes daily).
OPTION_CHAIN_TTL_SECONDS = 300.0

# CR206 — dividend history's cache TTL. Far longer than the chain's 300s
# because the underlying fact moves on a different clock: a chain reprices
# every tick, while a dividend is declared once a quarter and its ex-date is
# known weeks ahead. Re-fetching it per lifecycle sweep would be a per-ticker
# network call a day for a number that changed last quarter.
DIVIDEND_HISTORY_TTL_SECONDS = 6 * 60 * 60.0
OPTION_EXPIRIES_TTL_SECONDS = 3600.0


class OptionQuoteState(NamedTuple):
    """`classify_option_quote`'s verdict plus the reason to surface."""

    state: str   # "tradeable" | "worthless" | "unusable"
    reason: str  # "ok" | "zero_bid" | "no_quote" | "crossed" | "wide_spread"


def classify_option_quote(
    bid: float | None, ask: float | None
) -> OptionQuoteState:
    """CR172 §4's three-state fillability guard, extended from CR170's two.

    tradeable — both sides live and the spread within OPTION_MAX_SPREAD_PCT.
    worthless — bid=0 with a live ask: a REAL quote meaning the position is
                closeable at 0 but never openable. Not a data failure.
    unusable  — missing/degenerate/crossed/wide: no fill, no mark, and the
                caller degrades loudly (CR040), because CR170 §5 measured
                what a silent fallback does to a resting book.
    """
    if bid is None or ask is None:
        return OptionQuoteState("unusable", "no_quote")
    if not (math.isfinite(bid) and math.isfinite(ask)) or bid < 0 or ask <= 0:
        return OptionQuoteState("unusable", "no_quote")
    if bid == 0:
        return OptionQuoteState("worthless", "zero_bid")
    if ask < bid:
        return OptionQuoteState("unusable", "crossed")
    mid = (bid + ask) / 2.0
    if (ask - bid) / mid > OPTION_MAX_SPREAD_PCT:
        return OptionQuoteState("unusable", "wide_spread")
    return OptionQuoteState("tradeable", "ok")


def _dividend_fields_from_info(info: dict | None) -> tuple[str | None, float | None]:
    """Extract (ex_dividend_date ISO, dividend_rate) from a yfinance `.info` dict.

    Pure + total (never raises) so the null-handling is unit-testable without
    yfinance. CR030 rules:
      - No `exDividendDate` → not a dividend payer → the ex-date is None and the
        mobile chip hides entirely (no "N/A" row).
      - `exDividendDate` is a unix timestamp in SECONDS; rendered ISO "YYYY-MM-DD"
        to match `earnings_date`'s shape. A non-finite / unparseable / out-of-range
        value is treated as absent (DEF052 NaN-sentinel lesson), never passed through.
      - `dividendRate` of 0.0 or absent → rate None. A 0.0 rate WITH an ex-date
        present (rare — a suspended dividend) surfaces the date with a None rate,
        exactly as the CR specifies.
    """
    if not info:
        return None, None
    ex_iso: str | None = None
    ex_ts = info.get("exDividendDate")
    if ex_ts is not None:
        try:
            ts = float(ex_ts)
            if math.isfinite(ts):
                ex_iso = datetime.datetime.fromtimestamp(
                    ts, datetime.timezone.utc
                ).strftime("%Y-%m-%d")
        except (TypeError, ValueError, OSError, OverflowError):
            ex_iso = None
    rate: float | None = None
    rate_raw = info.get("dividendRate")
    if rate_raw is not None:
        try:
            r = float(rate_raw)
            if math.isfinite(r) and r > 0.0:
                rate = round(r, 2)
        except (TypeError, ValueError):
            rate = None
    return ex_iso, rate


# Period → (yfinance period, yfinance interval, mock-walk candle count, mock-walk seconds-per-candle).
# Mock-walk counts mirror what yfinance returns for typical regular-session symbols.
_PERIOD_MAP: dict[str, tuple[str, str, int, int]] = {
    "1d": ("1d",  "5m",  78, 5 * 60),                  # ~6.5h session / 5m
    "1w": ("5d",  "30m", 65, 30 * 60),                 # 5 sessions × 13 bars
    "1m": ("1mo", "1d",  22, 24 * 3600),               # ~22 trading days
    "3m": ("3mo", "1d",  65, 24 * 3600),               # ~65 trading days
    "1y": ("1y",  "1wk", 52, 7 * 24 * 3600),
    "2y": ("2y",  "1d",  504, 24 * 3600),              # CR136 — ~504 trading days, daily bars
    "5y": ("5y",  "1mo", 60, 30 * 24 * 3600),
}

VALID_PERIODS: tuple[str, ...] = tuple(_PERIOD_MAP.keys())


@dataclass(frozen=True)
class DividendPayment:
    """One dividend that was ACTUALLY paid, with the date it went ex.

    CR206 exists because the obvious source is wrong. `EarningsInfo` already
    carries `dividend_rate`, but that is the **annual** per-share figure, and
    D9's early-assignment rule needs the amount of the **next single
    payment**. Dividing by four assumes a quarterly payer: US large caps
    mostly are, monthly REITs and semi-annual ADRs are not, and the number
    decides whether a real user's position is taken away early. An assumed
    per-payment amount is DEF059's shape on a rule with a consequence, so
    this carries a measured payment instead.
    """

    ex_date: datetime.date
    amount_per_share: float
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

    def expiries(self, underlying: str) -> list[datetime.date] | None:
        """Listed option expiries for `underlying`, or None if unavailable.

        None means "no chain data here" and the caller must render options
        as unavailable — visibly, never as an empty-but-fine list (CR172 §4).
        """
        ...

    def option_chain(
        self, underlying: str, expiry: datetime.date
    ) -> OptionChain | None:
        """The chain for one (underlying, expiry), or None on any failure.

        `OptionChain.source` MUST identify the leaf provider that served
        it — wrappers forward the inner's chain untouched, exactly as
        `quote()` forwards `Quote.source`.
        """
        ...

    def dividend_history(self, underlying: str) -> list[DividendPayment] | None:
        """Dividends actually paid on `underlying`, oldest first, or None.

        CR206. **None and `[]` are different answers and must stay so.** None
        is "this provider could not tell you" — the feed errored, or does not
        carry dividends — and the early-assignment rule must then report
        `not_evaluated` rather than deciding. `[]` is a measurement: this
        company pays no dividend, so there is no early-assignment trigger and
        the rule can say so with confidence. Collapsing them would turn an
        outage into a confident "your short call is safe", which is DEF059
        pointed at a position that can be taken away.
        """
        ...


# ── Mock walk (extracted from sim_engine.py so SimEngine no longer owns it) ──


@dataclass
class _PriceWalk:
    """Per-ticker deterministic random walk seeded by ticker.

    Deterministic ACROSS PROCESSES since DEF323 — it was not before, and this
    docstring said it was. See `_stable_seed`.
    """

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


def _stable_seed(*parts: object) -> int:
    """A seed that survives leaving the process. DEF323.

    `hash()` on a str is salted per interpreter (PEP 456) unless
    `PYTHONHASHSEED` is set, and it is set nowhere in this repo — so seeding a
    "deterministic" walk with `hash(ticker)` re-rolled every price on every
    process start. Measured across three consecutive interpreters, AAPL's base
    came out $108.61, $186.81, $432.78.

    That is not a test-only concern: `USE_REAL_MARKET_DATA=true` resolves to
    Yahoo falling back to this walk, so a container restart during a Yahoo
    outage silently re-prices the whole universe while the source string still
    reads `mock_walk`. `crc32` is stable across processes, versions and
    platforms, which is the only property being asked of it here — it is a
    checksum standing in for a hash, not a security choice.
    """
    return zlib.crc32("\x00".join(str(p) for p in parts).encode("utf-8"))


def _walk_for(ticker: str) -> _PriceWalk:
    seed = _stable_seed(ticker.upper())
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
            jitter = random.Random(_stable_seed(t, ts)).uniform(-0.005, 0.005)
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

    def expiries(self, underlying: str) -> list[datetime.date] | None:
        # CR172 D10 (ratified): no synthesised chain. Options are DARK when
        # the mock provider is active, and that has to be visible in the
        # logs rather than discovered — the honest behaviour, said loudly.
        logger.warn("mock_walk_options_unavailable", underlying=underlying)
        return None

    def option_chain(
        self, underlying: str, expiry: datetime.date
    ) -> OptionChain | None:
        logger.warn(
            "mock_walk_options_unavailable",
            underlying=underlying, expiry=expiry.isoformat(),
        )
        return None

    def dividend_history(self, underlying: str) -> list[DividendPayment] | None:
        # CR206 — None, never []. The mock invents prices; inventing a
        # dividend would let D9 decide a real assignment off a fabricated
        # number, and returning [] would assert "this company pays nothing",
        # which is a measurement this provider has not made. Same posture as
        # `expiries` above: dark, and loudly so.
        logger.warn("mock_walk_dividends_unavailable", underlying=underlying)
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

    def expiries(self, underlying: str) -> list[datetime.date] | None:
        # The keyless chart endpoint serves no chains; this provider only
        # runs when yfinance failed to import. Loud, so a chain-dark Alpha
        # names its cause in the logs (CR040).
        logger.warn("yahoo_keyless_options_not_wired", underlying=underlying)
        return None

    def option_chain(
        self, underlying: str, expiry: datetime.date
    ) -> OptionChain | None:
        logger.warn(
            "yahoo_keyless_options_not_wired",
            underlying=underlying, expiry=expiry.isoformat(),
        )
        return None

    def dividend_history(self, underlying: str) -> list[DividendPayment] | None:
        # CR206 — the keyless endpoint carries no dividend series. Not wired,
        # said out loud, and None rather than [] for the reason in the
        # protocol docstring.
        logger.warn("yahoo_keyless_dividends_not_wired", underlying=underlying)
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
        self._history_cache: dict[str, tuple[list[Candle], float, str]] = {}  # f"{ticker}:{period}" → (candles, expires_at, source)
        self._news_cache: dict[str, tuple[list[NewsItem], float]] = {}  # f"{ticker}:{limit}" → (items, expires_at)
        self._earnings_cache: dict[str, tuple[EarningsInfo, float]] = {}  # ticker → (info, expires_at)
        # CR172 §4 — chains get their OWN TTLs, not the 60s quote TTL: a
        # chain is a far bigger payload that moves far slower, and the
        # expiry LIST changes at most daily.
        self._expiries_cache: dict[str, tuple[list[datetime.date], float]] = {}  # underlying → (dates, expires_at)
        self._chain_cache: dict[str, tuple[OptionChain, float]] = {}  # f"{underlying}:{expiry}" → (chain, expires_at)
        # CR206 — underlying → (payments, expires_at). Its own TTL, because a
        # dividend is declared once a quarter while a chain reprices per tick.
        self._dividend_cache: dict[str, tuple[list[DividendPayment], float]] = {}
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

    def history_with_source(self, ticker: str, period: str) -> tuple[list[Candle] | None, str]:
        # Cache the SOURCE beside the bars, exactly as `quote()` caches the
        # full Quote — a cached series is honestly attributed to the leaf that
        # produced it, under any composition. Reading `self._inner.name`
        # instead would be right only while the inner is a leaf: wrap this
        # around a FallbackProvider and a cache hit for bars the mock leg
        # served during an outage would report the fallback's stack name,
        # which matches nothing in SYNTHETIC_HISTORY_SOURCES and would let a
        # synthetic series pass the refusal check (DEF229 audit r1, MINOR).
        key = f"{ticker.upper().strip()}:{period}"
        now = time.time()
        with self._lock:
            hit = self._history_cache.get(key)
            if hit is not None and hit[1] > now:
                return hit[0], hit[2]
        bars, source = history_with_source(self._inner, ticker, period)
        if bars is not None:
            with self._lock:
                self._history_cache[key] = (bars, now + self._ttl, source)
        return bars, source

    def history(self, ticker: str, period: str) -> list[Candle] | None:
        bars, _ = self.history_with_source(ticker, period)
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

    def expiries(self, underlying: str) -> list[datetime.date] | None:
        t = underlying.upper().strip()
        now = time.time()
        with self._lock:
            hit = self._expiries_cache.get(t)
            if hit is not None and hit[1] > now:
                return hit[0]
        dates = self._inner.expiries(t)
        if dates:
            with self._lock:
                self._expiries_cache[t] = (dates, now + OPTION_EXPIRIES_TTL_SECONDS)
        return dates

    def option_chain(
        self, underlying: str, expiry: datetime.date
    ) -> OptionChain | None:
        key = f"{underlying.upper().strip()}:{expiry.isoformat()}"
        now = time.time()
        with self._lock:
            hit = self._chain_cache.get(key)
            if hit is not None and hit[1] > now:
                return hit[0]
        chain = self._inner.option_chain(underlying, expiry)
        if chain is not None:
            with self._lock:
                self._chain_cache[key] = (chain, now + OPTION_CHAIN_TTL_SECONDS)
        return chain


    def dividend_history(self, underlying: str) -> list[DividendPayment] | None:
        """CR206 — cached for `DIVIDEND_HISTORY_TTL_SECONDS`.

        **An empty list is cached; a None is not.** `[]` is a measurement
        ("pays no dividend") and is as cacheable as any other. `None` is a
        failure, and caching a failure for six hours would turn one bad
        request into six hours of `not_evaluated` on every short call.
        """
        key = underlying.upper().strip()
        now = time.time()
        with self._lock:
            hit = self._dividend_cache.get(key)
            if hit is not None and hit[1] > now:
                return hit[0]
        paid = self._inner.dividend_history(underlying)
        if paid is not None:
            with self._lock:
                self._dividend_cache[key] = (paid, now + DIVIDEND_HISTORY_TTL_SECONDS)
        return paid
    def invalidate(self, ticker: str | None = None) -> None:
        with self._lock:
            if ticker is None:
                self._cache.clear()
                self._history_cache.clear()
                self._news_cache.clear()
                self._earnings_cache.clear()
                self._expiries_cache.clear()
                self._chain_cache.clear()
            else:
                t = ticker.upper().strip()
                self._cache.pop(t, None)
                self._earnings_cache.pop(t, None)
                self._expiries_cache.pop(t, None)
                # Drop every keyed entry for this ticker.
                self._history_cache = {
                    k: v for k, v in self._history_cache.items() if not k.startswith(f"{t}:")
                }
                self._news_cache = {
                    k: v for k, v in self._news_cache.items() if not k.startswith(f"{t}:")
                }
                self._chain_cache = {
                    k: v for k, v in self._chain_cache.items() if not k.startswith(f"{t}:")
                }
                # CR206 — keyed by bare underlying, so an exact-key drop, not
                # a prefix one. A `startswith` here would also evict AAPLD's
                # entry when AAPL is invalidated.
                self._dividend_cache.pop(t, None)


# ── yfinance (preferred over raw Yahoo HTTP) ─────────────────────────────


def _previous_close(fast_info: Any) -> float | None:
    """The reference close a session's change is measured against (DEF252).

    Two keys, in this order on purpose. `regular_market_previous_close` is what
    Yahoo's own `regularMarketChangePercent` divides by, and the two genuinely
    disagree — 313.33 against 313.25 on AAPL, 2026-08-10. Matching Yahoo matters
    more than picking the fresher-looking figure, because this number is rendered
    beside a price the user can check against Yahoo in another tab.

    `fast_info` raises rather than returning None for an absent key, and which
    keys a ticker carries varies by quote type, so both lookups are guarded and
    the caller is told when neither answered.
    """
    for key in ("regular_market_previous_close", "previous_close"):
        try:
            value = fast_info[key]
        except Exception:
            continue
        if value:
            return float(value)
    return None


def _chain_float(value: Any) -> float | None:
    """A finite float from a chain cell, else None — pandas NaN included.

    NaN is how yfinance spells "not served" on illiquid strikes; letting it
    through as a float would make every downstream comparison silently
    false (the DEF052 NaN-sentinel lesson, again).
    """
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _option_rows_from_df(df: Any) -> tuple[OptionQuote, ...]:
    """OptionQuote rows from one half (calls/puts) of a yfinance chain."""
    if df is None or getattr(df, "empty", True):
        return ()
    rows: list[OptionQuote] = []
    for _, row in df.iterrows():
        strike = _chain_float(row.get("strike"))
        if strike is None or strike <= 0:
            continue
        volume = _chain_float(row.get("volume"))
        open_interest = _chain_float(row.get("openInterest"))
        itm = row.get("inTheMoney")
        rows.append(OptionQuote(
            strike=strike,
            bid=_chain_float(row.get("bid")),
            ask=_chain_float(row.get("ask")),
            last=_chain_float(row.get("lastPrice")),
            volume=int(volume) if volume is not None else None,
            open_interest=int(open_interest) if open_interest is not None else None,
            implied_vol=_chain_float(row.get("impliedVolatility")),
            in_the_money=bool(itm) if isinstance(itm, (bool,)) or itm in (0, 1) else None,
        ))
    rows.sort(key=lambda r: r.strike)
    return tuple(rows)


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
        # DEF252: this used to return the price alone, so `change_pct` and
        # `market_state` fell through to their NamedTuple defaults — 0.0 and
        # "CLOSED" — and the app rendered both as fact. Every quote on Alpha read
        # a dead-flat closed market, including 14:37 ET on a -2% session.
        #
        # Both come from data already in hand. The previous close is on the SAME
        # `fast_info` object, so there is no second round-trip; `market_state` is
        # NOT on it (KeyError, verified) and lives only on the heavy `.info` call
        # CR145 flags as the uncached hot-path hazard — so it is derived from the
        # pure no-network session calendar CR109 already built instead of bought.
        prev = _previous_close(info)
        if prev:
            change_pct = round((float(price) - prev) / prev * 100.0, 2)
        else:
            # Loud, not silent (CR040). 0.0 is indistinguishable from "flat" on
            # the pixel, so the one case that still asserts a number it does not
            # have says so in the logs. A nullable `change_pct` end-to-end is the
            # real answer and needs the Flutter half — recorded on DEF252's row.
            logger.warn("yfinance_quote_no_previous_close", ticker=t)
            change_pct = 0.0
        return Quote(
            price=float(price),
            source=self.name,
            change_pct=change_pct,
            market_state=(
                "REGULAR"
                if is_us_market_open(datetime.datetime.now(datetime.timezone.utc))
                else "CLOSED"
            ),
        )

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
                summary = str(content.get("summary", "") or a.get("summary", "") or "").strip()
                items.append(NewsItem(
                    title=title, link=link, publisher=publisher,
                    published_at=published_at, summary=summary,
                ))
            except (KeyError, TypeError, ValueError):
                continue
        return items or None

    def earnings(self, ticker: str) -> EarningsInfo | None:
        t = ticker.upper().strip()
        try:
            import pandas as pd

            yt = self._yf.Ticker(t)
            cal = yt.calendar
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
            # CR030: dividend fields ride on the same object + 6h cache. A slow/
            # failed `.info` fetch degrades loudly to None dividends rather than
            # losing the earnings data we already resolved.
            ex_div: str | None = None
            div_rate: float | None = None
            try:
                ex_div, div_rate = _dividend_fields_from_info(yt.info)
            except Exception as exc:
                logger.warn("yfinance_dividend_error", ticker=t, error=str(exc))
            return EarningsInfo(
                earnings_date=target.strftime("%Y-%m-%d"),
                quarter=q_map.get(target.month),
                eps_estimate=float(eps) if eps is not None else None,
                ex_dividend_date=ex_div,
                dividend_rate=div_rate,
            )
        except Exception as exc:
            logger.warn("yfinance_earnings_error", ticker=t, error=str(exc))
            return None

    def expiries(self, underlying: str) -> list[datetime.date] | None:
        t = underlying.upper().strip()
        try:
            raw = self._yf.Ticker(t).options or ()
        except Exception as exc:
            logger.warn("yfinance_expiries_error", underlying=t, error=str(exc))
            return None
        dates: list[datetime.date] = []
        for value in raw:
            try:
                dates.append(datetime.date.fromisoformat(str(value)))
            except ValueError:
                continue
        return dates or None

    def option_chain(
        self, underlying: str, expiry: datetime.date
    ) -> OptionChain | None:
        t = underlying.upper().strip()
        try:
            raw = self._yf.Ticker(t).option_chain(expiry.isoformat())
        except Exception as exc:
            logger.warn(
                "yfinance_chain_error",
                underlying=t, expiry=expiry.isoformat(), error=str(exc),
            )
            return None
        calls = _option_rows_from_df(getattr(raw, "calls", None))
        puts = _option_rows_from_df(getattr(raw, "puts", None))
        if not calls and not puts:
            return None
        return OptionChain(
            underlying=t, expiry=expiry, calls=calls, puts=puts,
            source=self.name,
        )

    def dividend_history(self, underlying: str) -> list[DividendPayment] | None:
        """CR206 — the ACTUAL payments, from `Ticker.dividends`.

        This is the whole point of the CR. `EarningsInfo.dividend_rate` is
        already on hand and is the annual figure; deriving a per-payment
        amount from it means assuming a payment frequency, and the assumption
        is wrong for monthly REITs and semi-annual ADRs. `Ticker.dividends`
        is a series of payments that really happened, indexed by ex-date, so
        the most recent entry is a measured number.

        An empty series is returned as `[]`, not None: yfinance answered, and
        the answer is that this company has never paid one.
        """
        t = underlying.upper().strip()
        try:
            series = self._yf.Ticker(t).dividends
        except Exception as exc:
            logger.warn("yfinance_dividends_error", underlying=t, error=str(exc))
            return None
        if series is None:
            return None

        out: list[DividendPayment] = []
        try:
            for idx, amount in series.items():
                ex = getattr(idx, "date", None)
                ex = ex() if callable(ex) else idx
                if not isinstance(ex, datetime.date):
                    continue
                if isinstance(ex, datetime.datetime):
                    ex = ex.date()
                value = float(amount)
                # A zero or negative payment is not a payment. Dropped rather
                # than carried, so "most recent" cannot land on a placeholder
                # row and report a $0.00 dividend as this quarter's.
                if not math.isfinite(value) or value <= 0:
                    continue
                out.append(DividendPayment(ex_date=ex, amount_per_share=value,
                                           source=self.name))
        except Exception as exc:
            logger.warn("yfinance_dividends_parse_error", underlying=t, error=str(exc))
            return None

        out.sort(key=lambda d: d.ex_date)
        return out


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

    def history_with_source(self, ticker: str, period: str) -> tuple[list[Candle] | None, str]:
        bars, source = history_with_source(self._primary, ticker, period)
        if bars:
            return bars, source
        return history_with_source(self._secondary, ticker, period)

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

    def expiries(self, underlying: str) -> list[datetime.date] | None:
        dates = self._primary.expiries(underlying)
        if dates:
            return dates
        return self._secondary.expiries(underlying)

    def option_chain(
        self, underlying: str, expiry: datetime.date
    ) -> OptionChain | None:
        # The chain object is forwarded untouched, so `OptionChain.source`
        # keeps naming the leaf that served it — never this wrapper.
        chain = self._primary.option_chain(underlying, expiry)
        if chain is not None:
            return chain
        return self._secondary.option_chain(underlying, expiry)

    def dividend_history(self, underlying: str) -> list[DividendPayment] | None:
        # CR206 — falls through only on None ("could not tell"), NEVER on an
        # empty list. `[]` is a real measurement meaning "pays no dividend",
        # and falling through it would let a secondary that knows nothing
        # overwrite a primary that knows something.
        paid = self._primary.dividend_history(underlying)
        if paid is not None:
            return paid
        return self._secondary.dividend_history(underlying)


# ── History provenance ───────────────────────────────────────────────────


SYNTHETIC_HISTORY_SOURCES = frozenset({"mock_walk", "unavailable"})
"""Leaf providers whose OHLCV is fabricated, not measured."""


def history_with_source(
    provider: MarketDataProvider, ticker: str, period: str
) -> tuple[list[Candle] | None, str]:
    """`provider.history(...)` plus the leaf that actually served the bars.

    `Quote.source` has always carried its leaf so the LIVE/MOCK pill can't
    lie about which leg fired. History carried no such marker, so a caller
    that asserts provenance over its output — `compute_technicals`, whose
    block is rendered under an explicit "Real yfinance OHLCV" claim — could
    not tell a yfinance series from the synthetic walk the chain falls
    through to (DEF229). This closes that gap the same way quotes did.

    Providers that don't implement `history_with_source` (test fakes, and
    any future leaf) report their own `name`, so a fake is never mistaken
    for the mock walk it isn't.
    """
    fn = getattr(provider, "history_with_source", None)
    if fn is not None:
        return fn(ticker, period)
    return provider.history(ticker, period), getattr(provider, "name", "unknown")


# ── As-of store-backed provider (CR164) ──────────────────────────────────


class AsOfStoreProvider:
    """The SAME provider protocol, served from `price_history_daily` with a
    hard `date <= as_of` cutoff (CR164).

    Returned by `get_market_data_provider()` whenever an `AsOfContext` is
    active, so every consumer — `compute_technicals` first among them — sees
    as-of-correct data with zero changes of its own. A PURE reader: nothing
    here fetches, and a window the store cannot serve honestly comes back as
    None (→ the CR104 UNAVAILABLE rendering), never as a partial or mock
    substitute.

    Daily-bar periods only. The store holds daily OHLCV; `1y` is resampled
    week-ends-from-daily, and the intraday/monthly periods (`1d`/`1w`/`5y`)
    are refused loudly — no Room-path consumer asks for them, and serving a
    fake resolution would be fabrication with a provenance stamp.
    """

    name = "asof_store"

    _DAILY_BARS = {"1m": 22, "3m": 65, "2y": 504}

    def __init__(self, as_of: "datetime.date") -> None:
        self._as_of = as_of

    def _rows(self, ticker: str, max_rows: int) -> list[tuple]:
        from app.services.price_history import get_asof_daily_rows  # lazy: avoids cycle

        return get_asof_daily_rows(ticker, self._as_of, max_rows=max_rows)

    def quote(self, ticker: str) -> Quote | None:
        rows = self._rows(ticker, 2)
        if not rows:
            logger.warn("asof_store_no_quote", ticker=ticker, as_of=self._as_of.isoformat())
            return None
        price = rows[-1][5]
        change = (price / rows[-2][5] - 1.0) * 100.0 if len(rows) > 1 else 0.0
        return Quote(price=price, source=self.name, change_pct=change, market_state="CLOSED")

    def get_price(self, ticker: str) -> float | None:
        q = self.quote(ticker)
        return q.price if q else None

    def history(self, ticker: str, period: str) -> list[Candle] | None:
        if period == "1y":
            rows = self._rows(ticker, 370)
            rows = [r for i, r in enumerate(rows)
                    if i + 1 == len(rows) or rows[i + 1][0].isocalendar()[:2] != r[0].isocalendar()[:2]]
            rows = rows[-52:]
        elif period in self._DAILY_BARS:
            rows = self._rows(ticker, self._DAILY_BARS[period])
        else:
            logger.warn(
                "asof_store_period_unservable",
                ticker=ticker, period=period, as_of=self._as_of.isoformat(),
            )
            return None
        if not rows:
            logger.warn(
                "asof_store_no_history",
                ticker=ticker, period=period, as_of=self._as_of.isoformat(),
            )
            return None
        incomplete = sum(1 for r in rows if r[1] is None or r[2] is None or r[3] is None or r[6] is None)
        if incomplete:
            # A half-real OHLCV window would feed technicals a fabricated
            # volume baseline — refuse the whole window instead (CR040).
            logger.warn(
                "asof_store_ohlcv_incomplete",
                ticker=ticker, period=period, as_of=self._as_of.isoformat(),
                incomplete=incomplete, rows=len(rows),
            )
            return None
        return [
            Candle(
                t=int(datetime.datetime.combine(
                    r[0], datetime.time.min, tzinfo=datetime.timezone.utc,
                ).timestamp()),
                o=r[1], h=r[2], low=r[3], c=r[5], v=float(r[6]),
            )
            for r in rows
        ]

    def news(self, ticker: str, limit: int = 5) -> list[NewsItem] | None:
        return None  # v1: News analyst runs ablated; `news_archive` is the later hook

    def earnings(self, ticker: str) -> EarningsInfo | None:
        return None  # a forward calendar is not PIT-reconstructable from free sources

    def expiries(self, underlying: str) -> list[datetime.date] | None:
        # CR172 §4: there is NO historical options store, so a backtest must
        # say "options not evaluated" — never value them at zero. Loud, so
        # the refusal is attributable (the DEF169 silent-pass shape is the
        # single most likely bug here, per the CR).
        logger.warn(
            "asof_store_no_options_history",
            underlying=underlying, as_of=self._as_of.isoformat(),
        )
        return None

    def option_chain(
        self, underlying: str, expiry: datetime.date
    ) -> OptionChain | None:
        logger.warn(
            "asof_store_no_options_history",
            underlying=underlying, expiry=expiry.isoformat(),
            as_of=self._as_of.isoformat(),
        )
        return None

    def dividend_history(self, underlying: str) -> list[DividendPayment] | None:
        # CR206 — a historical replay must not be handed today's dividends;
        # that is the look-ahead this provider exists to prevent.
        logger.warn(
            "asof_store_no_dividend_history",
            underlying=underlying, as_of=self._as_of.isoformat(),
        )
        return None


# ── Singleton factory ────────────────────────────────────────────────────


_provider: MarketDataProvider | None = None


def get_market_data_provider() -> MarketDataProvider:
    """Returns the configured provider stack.

    CR164: when an `AsOfContext` is active (backtest Room runs only), the
    store-backed as-of provider is returned instead — request-scoped, so live
    traffic on the same process is untouched.

    Honours `settings.use_real_market_data`. Switching env requires a
    backend restart (singleton). Tests can call `set_market_data_provider()`
    to inject a fake.

    Stack: cached yfinance primary → MockWalkProvider secondary.
    yfinance handles the rate-limit dance Yahoo's keyless chart endpoint
    couldn't, so the secondary is rarely needed in practice — but it's
    a guaranteed never-fail floor for the quote-on-demand UX.
    """
    ctx = current_asof()
    if ctx is not None:
        return AsOfStoreProvider(ctx.as_of)
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
