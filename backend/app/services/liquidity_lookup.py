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

Two entry points, same cache, same fetch:
  * `resolve_liquidity_with_lookup(universe, ticker, price=...)` — SYNC. Safe
    to call from any of the THREE call sites already proven to run off the
    event loop via `asyncio.to_thread` (`SimEngine.submit` / `.preview` /
    `.fill_resting_order`, each wrapped by their API route or the resting-order
    sweep tick). Bounds the blocking network call with a worker-thread timeout
    (`concurrent.futures`) so a hung yfinance call cannot pin the calling
    `to_thread` thread forever.
  * `prewarm_on_demand_liquidity(ticker)` — ASYNC. For the two call sites that
    run `check_mandate_compliance` / `enforce_safety_floor` directly ON the
    event loop (`room_runner.py`'s live-PM path and its scripted
    `_assemble_verdict` path — both inside `RoomRunner.run()`, an
    `asyncio.Task`, never `to_thread`-wrapped). Awaited BEFORE the sync
    compliance call, so the cache is already warm (hit or cached failure) by
    the time the sync path calls `resolve_liquidity_with_lookup` a few lines
    later — the sync call site never blocks the loop because it never misses.
    Mirrors the existing `default_classification_universe_async()` seam
    (`asyncio.to_thread` at the async boundary, never inside the sync core).

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
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutureTimeoutError
from threading import RLock

from app.core.logging import logger

# 24h — Saiful's ruling, verbatim. Matches the daily classification refresh's
# own cadence, so an on-demand read is never staler than the thing it stands in
# for between refreshes.
_ON_DEMAND_CACHE_TTL_S = 24 * 60 * 60.0

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

    info = yf.Ticker(ticker.upper().replace(".", "-")).info or {}
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
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
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
    with _lock:
        # A failed/timed-out result is cached too, same reasoning as
        # `fundamentals.fetch_statement_facts`: without this, a ticker
        # yfinance can't answer for becomes the EXPENSIVE case, and every
        # retry inside the TTL window re-pays the same timeout.
        _cache[t] = (result, now + _ON_DEMAND_CACHE_TTL_S)
    return result


def resolve_liquidity_with_lookup(universe, ticker: str, *, price: float | None = None):
    """DEF417 round 2 — `resolve_liquidity`, extended with the on-demand path.

    SYNC. Safe wherever `check_mandate_compliance`/`enforce_safety_floor` is
    already proven to run off the event loop (every `SimEngine` call site,
    each reached via `asyncio.to_thread` from its API route or the resting-
    order sweep tick) — never call this directly from a coroutine running on
    the loop; use `prewarm_on_demand_liquidity` first there instead (see
    module docstring).

    Only fires the on-demand path when the SNAPSHOT resolved the ticker
    UNKNOWN (outside the ~503-name classified universe) — a stale/absent
    snapshot already resolves UNAVAILABLE upstream in `resolve_liquidity`
    itself and is left exactly as round 1 shipped it (Saiful's ruling 2,
    unchanged): the on-demand path is about tickers the snapshot never
    covers, not about a broken snapshot.
    """
    from app.schemas.liquidity import ON_DEMAND_SOURCE, LiquidityStatus, LiquidityVerdict
    from app.schemas.liquidity import ILLIQUID_AVG_DOLLAR_VOLUME_USD, MICROCAP_FLOOR_USD_M

    resolve = getattr(universe, "resolve_liquidity", None)
    if not callable(resolve):
        return LiquidityVerdict(status=LiquidityStatus.UNAVAILABLE, ticker=ticker.upper().strip())
    verdict = resolve(ticker, price=price)
    if verdict.status is not LiquidityStatus.UNKNOWN:
        return verdict

    t = ticker.upper().strip()
    info = _cached_lookup_sync(t)
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
        # yfinance answered but returned neither field (a genuinely un-priced
        # / delisted-adjacent name) — same UNKNOWN semantics `resolve_liquidity`
        # itself uses when the snapshot has nothing: AMI asked and still has no
        # ruling, so this is not a ruling either way.
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


async def prewarm_on_demand_liquidity(ticker: str) -> None:
    """Async pre-warm for the two on-loop call sites (`room_runner.py`'s
    live-PM + scripted paths). Populates the SAME cache
    `resolve_liquidity_with_lookup` reads, off the event loop via
    `asyncio.to_thread` — the established seam
    (`default_classification_universe_async`, `default_halal_universe_async`)
    applied to a ticker-keyed fetch instead of the whole-snapshot read.

    Never raises and returns nothing: the caller doesn't need the result here,
    only the cache being warm by the time the sync compliance call runs a few
    lines later. A cache MISS at that later sync call (this pre-warm itself
    timed out, or was never reached) still resolves correctly — just via a
    same-thread bounded fetch inside `resolve_liquidity_with_lookup`'s own
    `ThreadPoolExecutor`, at worst repeating the bounded wait once more.
    """
    import asyncio

    try:
        await asyncio.to_thread(_cached_lookup_sync, ticker)
    except Exception:  # noqa: BLE001 — best-effort warm; never block the caller on it
        logger.warn("liquidity_on_demand_prewarm_failed", ticker=ticker)
