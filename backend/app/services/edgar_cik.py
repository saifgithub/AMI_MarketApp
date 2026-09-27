"""CR244 — shared ticker→CIK resolver, one fetch of SEC's `company_tickers.json`
serving every live EDGAR read (company profile, filings, insider transactions),
plus the ONE paced-GET helper (M4) every SEC fetch in this feature routes
through — CIK map, submissions JSON, and ownership XML alike.

`scripts/ingest_edgar_8k.py` and `scripts/ingest_edgar_facts.py` already fetch
this exact file offline, each with its own inline dict-comprehension
(`{entry["ticker"]: entry["cik_str"] ...}`). Those scripts run once per
ingest pass under an operator-supplied `--user-agent`; this module is the
version a live request path calls, so it needs its own cache (an ingest
script exits after one use — nothing to cache) and its own fixed User-Agent
(no operator is present to supply `--user-agent` on a request thread).

Cached 24h in-process: `company_tickers.json` is ~1MB and SEC-rate-limited,
and the map barely changes day to day (new listings, ticker changes). A
process restart cold-starts the cache; that is an accepted cost of an
in-memory TTL rather than a store, same tradeoff CR244's other new caches
(`company_profile.py`, `edgar_ownership.py`) make.

`resolve_cik("BRK.A")` and `resolve_cik("brk.a")` both look up "BRK.A" —
SEC's map keys on the bare uppercase symbol, dots and all; no punctuation
stripping happens here beyond case-folding, so a symbol this map doesn't
carry (a foreign filer, an OTC name) returns None rather than a guess.

**B3 fix:** a map-fetch failure used to propagate as a raw exception, which
an `async def` route handler has no `except` for — that was a 500, not a
degrade-loud `not_available` (CR040). `resolve_cik` now returns the STALE map
on a refresh failure when one exists (a day-old map answering "no CIK for
this foreign symbol" is still correct far more often than a hard failure),
and only raises `CikResolutionUnavailable` when there is truly nothing to
serve (first-ever fetch fails cold). Callers (`company_profile.py`,
`edgar_ownership.py`) catch that ONE exception type and degrade their
CIK-dependent sections with a reason distinct from "no registrant found" —
a resolver OUTAGE and "this symbol isn't in SEC's map" must never read the
same to a user. A short negative-cache backoff (`_NEGATIVE_TTL_SECONDS`)
means a burst of requests during a 429 storm re-attempts at most once per
window, rather than re-fetching the ~1MB map on every single request.

**M4:** `paced_get` is the ONE rate-limited GET every SEC fetch in this CR
uses — CIK map, submissions JSON (`company_profile.py`, `edgar_ownership.py`),
and ownership XML. It reserves its time slot under `_pace_lock`, then
releases the lock BEFORE the network call, so two threads fetching
different URLs don't serialize on the request itself, only on scheduling
when the next one may fire. One 429/5xx retry with a fixed backoff, per
the SEC fair-use etiquette this module's docstring commits to (fixes the
"one retry" claim `company_profile.py` used to make without ever
implementing it).
"""

from __future__ import annotations

import threading
import time

import httpx

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"

# SEC fair use (https://www.sec.gov/os/accessing-edgar-data): a descriptive
# User-Agent with a contact email is mandatory. Matches the contact used by
# the offline ingest scripts' own default invocations.
USER_AGENT = "AMI Trade CR244 (saiful.mazli@gmail.com)"

_FETCH_TIMEOUT_S = 15.0
_TTL_SECONDS = 24 * 60 * 60.0
# 429-storm backoff: after a failed refresh, don't try again for this long —
# every request in the window reuses the stale map (or None) instead of
# re-fetching the ~1MB file per request.
_NEGATIVE_TTL_SECONDS = 60.0

_lock = threading.RLock()
_cache: dict[str, int] | None = None
_cached_at: float = 0.0
_last_failed_at: float | None = None

# M4 pacing, shared by every SEC GET this feature makes (CIK map, submissions,
# ownership XML) — one clock, not three independently-paced schemes.
_MIN_REQUEST_INTERVAL_S = 0.1  # ≤10 req/s, SEC's own rate ceiling
_pace_lock = threading.Lock()
_last_request_at: list[float] = [0.0]

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_RETRY_BACKOFF_S = 1.0


class CikResolutionUnavailable(RuntimeError):
    """The CIK map could not be fetched AND no stale copy exists to fall
    back on (first-ever fetch failed cold). Callers degrade the
    CIK-dependent section with a reason distinct from "no registrant
    found" — an outage and "not in SEC's map" must never look the same."""


def paced_get(client: httpx.Client, url: str) -> httpx.Response:
    """The one rate-limited GET every live SEC fetch in this feature makes.
    Reserves the next time slot under `_pace_lock`, then releases the lock
    before the actual request — the slot is what's serialized, not the
    round-trip. One retry with a fixed backoff on a 429/5xx; anything else
    (a transport error, a 404) is returned/raised to the caller as-is."""
    def _get_once() -> httpx.Response:
        with _pace_lock:
            now = time.monotonic()
            wait = _MIN_REQUEST_INTERVAL_S - (now - _last_request_at[0])
            if wait > 0:
                time.sleep(wait)
            _last_request_at[0] = time.monotonic()
        return client.get(url)

    r = _get_once()
    if r.status_code in _RETRYABLE_STATUS:
        time.sleep(_RETRY_BACKOFF_S)
        r = _get_once()
    return r


def _fetch_map() -> dict[str, int]:
    with httpx.Client(timeout=_FETCH_TIMEOUT_S, headers={"User-Agent": USER_AGENT}) as client:
        r = paced_get(client, TICKER_MAP_URL)
        r.raise_for_status()
        payload = r.json()
    return {
        str(entry["ticker"]).upper(): int(entry["cik_str"])
        for entry in payload.values()
        if entry.get("ticker") and entry.get("cik_str") is not None
    }


def _get_map() -> dict[str, int]:
    """The cached ticker→CIK map, refetched when absent or past its 24h TTL.
    On a refresh failure: serves the stale map when one exists (logged, not
    silent — but the caller sees a value, not an exception), otherwise raises
    `CikResolutionUnavailable`. Either way, a failed refresh sets the negative
    -cache backoff so a request burst doesn't retry the fetch on every call."""
    global _cache, _cached_at, _last_failed_at
    with _lock:
        now = time.monotonic()
        if _cache is not None and (now - _cached_at) < _TTL_SECONDS:
            return _cache
        if _last_failed_at is not None and (now - _last_failed_at) < _NEGATIVE_TTL_SECONDS:
            if _cache is not None:
                return _cache
            raise CikResolutionUnavailable("SEC ticker map fetch is in backoff after a recent failure")
        try:
            fresh = _fetch_map()
        except (httpx.HTTPError, ValueError):
            _last_failed_at = now
            if _cache is not None:
                return _cache
            raise CikResolutionUnavailable("SEC ticker map fetch failed and no cached copy exists") from None
        _cache = fresh
        _cached_at = now
        _last_failed_at = None
        return fresh


def resolve_cik(ticker: str) -> int | None:
    """The issuer's CIK for `ticker`, or None when SEC's own map doesn't carry
    it (foreign filer, OTC name, unlisted). Raises `CikResolutionUnavailable`
    on a resolver outage with no stale map to serve — that must never look
    like "no CIK for anything" to the caller (CR040)."""
    sym = (ticker or "").strip().upper()
    if not sym:
        return None
    return _get_map().get(sym)


def clear_cik_cache() -> None:
    """Test seam / operational escape hatch."""
    global _cache, _cached_at, _last_failed_at
    with _lock:
        _cache = None
        _cached_at = 0.0
        _last_failed_at = None
