"""DEF417 round 2 — on-demand, per-ticker liquidity lookup for `liquid_only`.

Round 1 shipped `ClassificationUniverse.resolve_liquidity`, which answers the
`liquid_only` mandate flag ONLY off the daily classification snapshot — the
~503 S&P parent constituents. The auditor (DEF417 MAJOR-1) measured that
12,743 of 13,246 tradable symbols (96%) sit outside that set, so a real
microcap outside the S&P (e.g. GNS) resolved UNKNOWN=permitted every time —
the filter could not refuse any ticker a user could actually type.

Saiful's ruling (2026-09-25): **"Look it up on demand."** When a `liquid_only`
mandate BUYs a ticker the snapshot didn't classify, fetch market cap + average
volume from the SAME source the snapshot uses (`yf.Ticker(t).info` — see
`classification_universe.py::_yf_info`, no new provider), cache it per ticker
for 24h, and enforce the SAME two floors
(`app.schemas.liquidity.MICROCAP_FLOOR_USD_M` /
`ILLIQUID_AVG_DOLLAR_VOLUME_USD`) against the fetched figures. Only a lookup
that itself fails or times out falls back to "allow + disclose"
(`LiquidityStatus.LOOKUP_FAILED`) — never a silent permit, and never a block on
a name AMI never actually measured.

Round 3 split the fetch from the floor. One cache, one fetch, three functions:
  * `resolve_liquidity_cached(universe, ticker, price=...)` — what the safety
    floor calls. It NEVER fetches, so it is safe on the event loop, where the
    Room runs its compliance checks. A miss (never fetched, or its short
    failure window has lapsed) resolves LOOKUP_FAILED: permitted and
    disclosed, never a blocking call and never a silent permit.
  * `ensure_liquidity_cached(universe, proposed, mandate)` — SYNC, blocking.
    Fetches into the cache before the floor runs, for a `liquid_only` BUY of a
    name the snapshot doesn't cover. SimEngine calls it in `submit`,
    `preview` and `fill_resting_order`, which already run off the loop
    (`asyncio.to_thread` in their route or the resting-order sweep tick). The
    network call is bounded by a worker-thread timeout (`concurrent.futures`),
    so a hung yfinance call cannot pin the calling thread.
  * `prewarm_on_demand_liquidity(ticker)` — ASYNC. The Room's equivalent:
    `RoomRunner.run()` awaits it (via `asyncio.to_thread`) before its on-loop
    compliance calls, the live-CIO path and the scripted `_assemble_verdict`
    path. The floor still only reads the cache: if the pre-warm failed or the
    entry has lapsed, the check sees a miss and discloses it. It is NOT a
    guaranteed hit, and the floor must never be switched to a fetching
    resolver to "fix" that.
`resolve_liquidity_with_lookup` is the fetching variant (snapshot, cache,
bounded fetch). No app code path calls it; it is blocking, so never put it on
the floor path.

Cache: an in-process `dict[str, tuple[dict | None, float]]` + `RLock`, TTL
24h — the SAME shape `fundamentals.py::_statements_cache` and
`market_data.py::CachingProvider._cache` already use. Not Redis: no
application code opens a Redis connection anywhere in this codebase today
(`readiness.py`'s probe is read-only/advisory) — inventing a Redis-backed
cache for one ticker-info lookup would be new infra the "no new provider, no
new socket" mandate doesn't ask for.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _FutureTimeoutError
from threading import RLock

from app.core.logging import logger

# 24h — Saiful's ruling, verbatim. Matches the daily classification refresh's
# own cadence, so an on-demand read is never staler than the thing it stands in
# for between refreshes.
_ON_DEMAND_CACHE_TTL_S = 24 * 60 * 60.0
_FAILED_LOOKUP_TTL_S = 5 * 60.0

# Short — this fires on the hot path (a BUY preview/submit, or a live Room
# convene), for a ticker the daily snapshot never saw. `fetch_live_fundamentals`
# / `_yf_info` carry NO timeout of their own anywhere else in this codebase
# (measured: neither wraps its `yf.Ticker(...).info` call), so an explicit,
# short bound here is a new guarantee, not a copy of an existing one. 4s
# matches `YahooQuoteProvider`'s own httpx client timeout
# (`market_data.py:523`) — the nearest sibling of "one blocking read, short
# budget, degrade on miss."
_ON_DEMAND_TIMEOUT_S = 4.0


class _LookupFailed:
    """Sentinel distinguishing "the fetch itself errored or timed out" from
    "the fetch succeeded and yfinance genuinely has neither field for this
    ticker" — both used to collapse to `None` here, which would have reported
    a real empty-but-successful read as `LOOKUP_FAILED` (wrong message: "AMI
    ... couldn't get an answer in time" when AMI DID get an answer, an empty
    one) instead of `UNKNOWN` (the correct "not a ruling either way" reading,
    same as the snapshot path already gives a classified-but-dataless
    ticker). Cached and returned exactly like a real result dict."""


_LOOKUP_FAILED = _LookupFailed()

_cache: dict[str, tuple[dict[str, float] | None | _LookupFailed, float]] = {}
_lock = RLock()

# Test seam, mirrors `_network_classify`'s injectable `info_fetcher` param and
# `classification_universe.reset_classification_universe_provider` — a fixture
# fetcher swaps in here so a unit test never opens a socket (yfinance) or pays
# `_ON_DEMAND_TIMEOUT_S` waiting on a real network call. `None` means "use the
# real fetch"; a test's `finally:` restores it.
_fetcher_override: object | None = None


def set_on_demand_fetcher(fetcher) -> None:
    """Test seam — swap the live `yf.Ticker(t).info` fetch for a fixture
    callable `(ticker: str) -> dict[str, float] | None`. Pass `None` to
    restore the real fetch."""
    global _fetcher_override
    _fetcher_override = fetcher


def clear_on_demand_liquidity_cache() -> None:
    """Test seam + operational escape hatch, mirrors
    `fundamentals.clear_statement_cache()`."""
    with _lock:
        _cache.clear()


def _num_or_none(v: object) -> float | None:
    """Same DEF052 F1 rule `classification_universe._num_or_none` /
    `fundamentals._num` already apply: yfinance's missing-value sentinel is
    often NaN, not an absent key."""
    if v is None:
        return None
    try:
        result = float(v)
    except (TypeError, ValueError):
        return None
    import math

    return result if math.isfinite(result) else None


def _yahoo_symbol(ticker: str) -> str:
    """Our symbol → Yahoo's: class shares use a hyphen (BRK.B → BRK-B) and
    NASDAQ-style preferreds are written `-P` (BAC$L → BAC-PL)."""
    t = ticker.upper().strip()
    if "$" in t:
        base, series = t.split("$", 1)
        t = f"{base}-P{series}"
    return t.replace(".", "-")


def _fetch_liquidity_info_uncached(ticker: str) -> dict[str, float] | None:
    """One live `yf.Ticker(t).info` read for market cap + average volume —
    the SAME fields `classification_universe._network_classify` already reads
    from the SAME kind of call, the SAME normalisation
    (`classification_universe._yf_info`) applied to the dot/hyphen class-share
    quirk (BF.B / BRK.B). Isolated import: yfinance is an optional dependency,
    same reasoning as every other caller in this codebase.

    Returns `{"market_cap_usd_m": ..., "avg_volume": ...}`, omitting whichever
    key yfinance didn't return (same "absent, not zero" contract
    `resolve_liquidity` already expects for the snapshot path), or `None` when
    yfinance answered but had neither field.

    Deliberately does NOT catch a provider error here — RAISES instead, so
    `_cached_lookup_sync`'s `ThreadPoolExecutor.result()` call sees the
    exception and can tell "the fetch itself failed" (→ `LOOKUP_FAILED`) apart
    from "the fetch succeeded and returned nothing" (→ `UNKNOWN`), which
    swallowing the error here into a bare `None` would have collapsed into one
    state (Saiful's ruling names the failure case specifically).
    """
    import yfinance as yf

    info = yf.Ticker(_yahoo_symbol(ticker)).info or {}
    out: dict[str, float] = {}
    cap = _num_or_none(info.get("marketCap"))
    if cap is not None:
        out["market_cap_usd_m"] = cap / 1_000_000
    vol = _num_or_none(info.get("averageVolume"))
    if vol is not None:
        out["avg_volume"] = vol
    return out or None


def _cached_lookup_sync(ticker: str) -> dict[str, float] | None | _LookupFailed:
    """Cache-first, bounded-timeout, synchronous lookup — the one function
    both entry points below call. Bounding the fetch with its own
    `ThreadPoolExecutor` (rather than trusting the caller's own thread budget)
    means a hang here cannot pin the `to_thread` worker (sim_engine path) or
    the pre-warm coroutine (room_runner path) past `_ON_DEMAND_TIMEOUT_S`,
    even though it cannot kill the underlying OS thread outright — the same
    orphaned-thread reality `asyncio.wait_for` around `asyncio.to_thread`
    already accepts elsewhere in this codebase (e.g. `room_runner.py`'s LLM
    stream timeouts), bounded to one throwaway thread per miss rather than an
    unbounded pool.

    Returns `_LOOKUP_FAILED` when the fetch itself errored or timed out (→
    `LiquidityStatus.LOOKUP_FAILED` at the caller), or `None`/a dict when the
    fetch actually ran — `None`/an empty dict means yfinance answered but has
    neither field for this ticker (→ `LiquidityStatus.UNKNOWN`, same "asked
    and got no ruling" meaning the snapshot path already carries). Saiful's
    ruling names the FAILURE case specifically ("only if the lookup itself
    fails/times out"); collapsing both into one sentinel would report a real
    empty answer with "AMI ... couldn't get an answer in time," which is not
    what happened.
    """
    t = ticker.upper().strip()
    now = time.time()
    with _lock:
        hit = _cache.get(t)
        if hit is not None and hit[1] > now:
            return hit[0]
    fetch = _fetcher_override or _fetch_liquidity_info_uncached
    # Not a `with` block: its exit calls shutdown(wait=True), which joins the
    # worker — a hung fetch would then hold the caller for as long as Yahoo
    # hangs and the timeout below would bound nothing.
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        fut = pool.submit(fetch, t)
        result: dict[str, float] | None | _LookupFailed = fut.result(
            timeout=_ON_DEMAND_TIMEOUT_S
        )
    except _FutureTimeoutError:
        logger.warn("liquidity_on_demand_timeout", ticker=t, timeout_s=_ON_DEMAND_TIMEOUT_S)
        result = _LOOKUP_FAILED
    except Exception as exc:  # noqa: BLE001 — degrade, never raise, into the caller's floor
        logger.warn("liquidity_on_demand_lookup_error", ticker=t, error=str(exc)[:200])
        result = _LOOKUP_FAILED
    finally:
        pool.shutdown(wait=False)
    # A failure is cached briefly so a burst of retries doesn't each re-pay the
    # timeout — but only briefly: a failure means "allowed with a disclosure",
    # and one Yahoo blip must not open a microcap to liquid_only buys all day.
    ttl = _FAILED_LOOKUP_TTL_S if isinstance(result, _LookupFailed) else _ON_DEMAND_CACHE_TTL_S
    with _lock:
        _cache[t] = (result, now + ttl)
    return result


_MISS = object()


def _cache_peek(ticker: str):
    """Cache read only — never fetches. `_MISS` when absent or expired."""
    with _lock:
        hit = _cache.get(ticker)
    if hit is None or hit[1] <= time.time():
        return _MISS
    return hit[0]


def _snapshot_verdict(universe, ticker: str, price: float | None):
    """The snapshot's own ruling, or None when it resolved UNKNOWN and the
    on-demand figures should decide."""
    from app.schemas.liquidity import LiquidityStatus, LiquidityVerdict

    resolve = getattr(universe, "resolve_liquidity", None)
    if not callable(resolve):
        return LiquidityVerdict(status=LiquidityStatus.UNAVAILABLE, ticker=ticker.upper().strip())
    verdict = resolve(ticker, price=price)
    if verdict.status is not LiquidityStatus.UNKNOWN:
        return verdict
    return None


def _verdict_from_info(info, t: str, price: float | None):
    from app.schemas.liquidity import (
        ILLIQUID_AVG_DOLLAR_VOLUME_USD,
        MICROCAP_FLOOR_USD_M,
        ON_DEMAND_SOURCE,
        LiquidityStatus,
        LiquidityVerdict,
    )

    if isinstance(info, _LookupFailed):
        logger.info("liquidity_on_demand_permitted_lookup_failed", ticker=t)
        return LiquidityVerdict(status=LiquidityStatus.LOOKUP_FAILED, ticker=t, source=ON_DEMAND_SOURCE)
    if info is None:
        # The fetch RAN and yfinance genuinely has neither field for this
        # ticker — a real answer, just an empty one. UNKNOWN (not
        # LOOKUP_FAILED): AMI asked and still has no ruling, same meaning the
        # snapshot path already carries for a classified-but-dataless name.
        return LiquidityVerdict(status=LiquidityStatus.UNKNOWN, ticker=t, source=ON_DEMAND_SOURCE)

    cap = info.get("market_cap_usd_m")
    vol = info.get("avg_volume")
    dollar_volume = (
        vol * price if vol is not None and price is not None and price > 0 else None
    )
    if cap is None and dollar_volume is None:
        return LiquidityVerdict(status=LiquidityStatus.UNKNOWN, ticker=t, source=ON_DEMAND_SOURCE)

    cap_breach = cap is not None and cap < MICROCAP_FLOOR_USD_M
    volume_breach = dollar_volume is not None and dollar_volume < ILLIQUID_AVG_DOLLAR_VOLUME_USD
    status = LiquidityStatus.EXCLUDED if (cap_breach or volume_breach) else LiquidityStatus.PERMITTED
    logger.info(
        "liquidity_on_demand_resolved", ticker=t, status=status.value,
        market_cap_usd_m=cap, avg_dollar_volume_usd=dollar_volume,
    )
    return LiquidityVerdict(
        status=status, ticker=t, market_cap_usd_m=cap,
        avg_dollar_volume_usd=dollar_volume, source=ON_DEMAND_SOURCE,
    )


def resolve_liquidity_cached(universe, ticker: str, *, price: float | None = None):
    """What the safety floor calls. It NEVER fetches, so it is safe on the event
    loop (the Room runs its compliance checks there). The fetch happens before
    the floor, off the loop: `ensure_liquidity_cached` in SimEngine (already
    run via `asyncio.to_thread`), `prewarm_on_demand_liquidity` in the Room.
    A miss — never fetched, or its short failure window has lapsed — resolves
    LOOKUP_FAILED: permitted and disclosed, never a blocking call and never a
    silent permit."""
    snapshot = _snapshot_verdict(universe, ticker, price)
    if snapshot is not None:
        return snapshot
    t = ticker.upper().strip()
    info = _cache_peek(t)
    if info is _MISS:
        logger.info("liquidity_on_demand_cache_miss", ticker=t)
        info = _LOOKUP_FAILED
    return _verdict_from_info(info, t, price)


def resolve_liquidity_with_lookup(universe, ticker: str, *, price: float | None = None):
    """Fetching variant: snapshot, then cache, then a bounded live fetch.
    Blocking — off the event loop only."""
    snapshot = _snapshot_verdict(universe, ticker, price)
    if snapshot is not None:
        return snapshot
    t = ticker.upper().strip()
    return _verdict_from_info(_cached_lookup_sync(t), t, price)


def ensure_liquidity_cached(universe, proposed, mandate) -> None:
    """Fetch into the cache before the floor runs, for a liquid_only BUY of a
    name the snapshot doesn't cover. Blocking — SimEngine calls it from methods
    that already run off the loop."""
    if mandate is None or not mandate.compliance.liquid_only or not proposed.is_buy:
        return
    from app.schemas.liquidity import LiquidityStatus

    resolve = getattr(universe, "resolve_liquidity", None)
    if not callable(resolve):
        return
    if resolve(proposed.ticker, price=None).status is LiquidityStatus.UNKNOWN:
        _cached_lookup_sync(proposed.ticker.upper().strip())


async def prewarm_on_demand_liquidity(ticker: str) -> None:
    """Async pre-warm for the two on-loop call sites (`room_runner.py`'s
    live-PM + scripted paths). Populates the SAME cache
    `resolve_liquidity_cached` reads, off the event loop via
    `asyncio.to_thread` — the established seam
    (`default_classification_universe_async`, `default_halal_universe_async`)
    applied to a ticker-keyed fetch instead of the whole-snapshot read.

    Never raises and returns nothing: the caller doesn't need the result here,
    only the cache being warm by the time the floor runs. The floor's resolver
    is cache-only, so a miss there (this pre-warm failed and its short failure
    window lapsed before the CIO's check) resolves LOOKUP_FAILED — disclosed,
    never a blocking fetch on the loop.
    """
    import asyncio

    try:
        await asyncio.to_thread(_cached_lookup_sync, ticker)
    except Exception:  # noqa: BLE001 — best-effort warm; never block the caller on it
        logger.warn("liquidity_on_demand_prewarm_failed", ticker=ticker)
