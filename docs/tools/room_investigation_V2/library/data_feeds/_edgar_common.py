"""Shared SEC EDGAR plumbing for the CR244 Part 2 data-feed library modules.

Ported from `backend/app/services/edgar_cik.py` (the ONE paced-GET helper and
the ticker→CIK resolver that every live SEC read in CR244 routes through),
adapted to stand alone: stdlib + httpx only, no `backend.app` imports, so the
`data_feeds` package is liftable into the main backend unchanged when CR244's
Part 2 rows are adopted there.

Adaptations from the backend original (semantics preserved, mechanism
changed):

- **asyncio instead of threads.** The backend module paces requests with a
  `threading.Lock` and `time.sleep`; this port uses `asyncio.Lock` and
  `asyncio.sleep` so the public feed API can be `async` end to end. The slot
  reservation is still what is serialized — the lock is released BEFORE the
  network call, so two concurrent fetches for different URLs don't serialize
  on the round trip, only on scheduling when the next one may fire.
- **stdlib `logging` instead of `structlog`.** The library carries no
  observability dependency; adopters wire their own logger at the seam.

Everything else is verbatim semantics: SEC fair-use User-Agent with a contact
email (mandatory per https://www.sec.gov/os/accessing-edgar-data), ≤10 req/s
pacing on ONE shared clock (the CIK map, the submissions JSON, and the
ownership XML all reserve slots on the same clock — three independently paced
schemes would each be under the limit while the sum exceeds it), one retry
with a fixed backoff on 429/5xx, a 24h in-process CIK map cache with a 60s
negative-cache backoff after a failed refresh, and stale-map fallback so a
resolver outage is distinguishable from "no SEC registrant for this symbol"
(`CikResolutionUnavailable` — CR040: the two must never read the same).
"""

from __future__ import annotations

import asyncio
import time

import httpx

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"

USER_AGENT = "AMI Trade CR244 (saiful.mazli@gmail.com)"
FETCH_TIMEOUT_S = 15.0

_MAP_TTL_SECONDS = 24 * 60 * 60.0
_NEGATIVE_TTL_SECONDS = 60.0

_MIN_REQUEST_INTERVAL_S = 0.1
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_RETRY_BACKOFF_S = 1.0


class CikResolutionUnavailable(RuntimeError):
    """The CIK map could not be fetched AND no stale copy exists to fall
    back on (first-ever fetch failed cold). Callers degrade the
    CIK-dependent section with a reason distinct from "no registrant
    found" — an outage and "not in SEC's map" must never look the same."""


_pace_lock = asyncio.Lock()
_last_request_at: list[float] = [0.0]


async def paced_get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    """The one rate-limited GET every live SEC fetch in this package makes.
    Reserves the next time slot under `_pace_lock`, then releases the lock
    before the actual request — the slot is what's serialized, not the
    round-trip. One retry with a fixed backoff on a 429/5xx; anything else
    (a transport error, a 404) is returned/raised to the caller as-is."""

    async def _get_once() -> httpx.Response:
        async with _pace_lock:
            now = time.monotonic()
            wait = _MIN_REQUEST_INTERVAL_S - (now - _last_request_at[0])
            if wait > 0:
                await asyncio.sleep(wait)
            _last_request_at[0] = time.monotonic()
        return await client.get(url)

    r = await _get_once()
    if r.status_code in _RETRYABLE_STATUS:
        await asyncio.sleep(_RETRY_BACKOFF_S)
        r = await _get_once()
    return r


_map_lock = asyncio.Lock()
_map_cache: dict[str, int] | None = None
_map_cached_at: float = 0.0
_map_last_failed_at: float | None = None


async def _fetch_map() -> dict[str, int]:
    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT_S, headers={"User-Agent": USER_AGENT}
    ) as client:
        r = await paced_get(client, TICKER_MAP_URL)
        r.raise_for_status()
        payload = r.json()
    return {
        str(entry["ticker"]).upper(): int(entry["cik_str"])
        for entry in payload.values()
        if entry.get("ticker") and entry.get("cik_str") is not None
    }


async def _get_map() -> dict[str, int]:
    global _map_cache, _map_cached_at, _map_last_failed_at
    async with _map_lock:
        now = time.monotonic()
        if _map_cache is not None and (now - _map_cached_at) < _MAP_TTL_SECONDS:
            return _map_cache
        if _map_last_failed_at is not None and (now - _map_last_failed_at) < _NEGATIVE_TTL_SECONDS:
            if _map_cache is not None:
                return _map_cache
            raise CikResolutionUnavailable(
                "SEC ticker map fetch is in backoff after a recent failure"
            )
        try:
            fresh = await _fetch_map()
        except (httpx.HTTPError, ValueError):
            _map_last_failed_at = now
            if _map_cache is not None:
                return _map_cache
            raise CikResolutionUnavailable(
                "SEC ticker map fetch failed and no cached copy exists"
            ) from None
        _map_cache = fresh
        _map_cached_at = now
        _map_last_failed_at = None
        return fresh


async def resolve_cik(ticker: str) -> int | None:
    """The issuer's CIK for `ticker`, or None when SEC's own map doesn't carry
    it (foreign filer, OTC name, unlisted). Raises `CikResolutionUnavailable`
    on a resolver outage with no stale map to serve — that must never look
    like "no CIK for anything" to the caller (CR040)."""
    sym = (ticker or "").strip().upper()
    if not sym:
        return None
    return (await _get_map()).get(sym)
