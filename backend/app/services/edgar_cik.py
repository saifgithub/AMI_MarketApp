"""CR244 — shared ticker→CIK resolver, one fetch of SEC's `company_tickers.json`
serving every live EDGAR read (company profile, filings, insider transactions).

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

_lock = threading.RLock()
_cache: dict[str, int] | None = None
_cached_at: float = 0.0


def _fetch_map() -> dict[str, int]:
    with httpx.Client(timeout=_FETCH_TIMEOUT_S, headers={"User-Agent": USER_AGENT}) as client:
        r = client.get(TICKER_MAP_URL)
        r.raise_for_status()
        payload = r.json()
    return {
        str(entry["ticker"]).upper(): int(entry["cik_str"])
        for entry in payload.values()
        if entry.get("ticker") and entry.get("cik_str") is not None
    }


def _get_map() -> dict[str, int]:
    """The cached ticker→CIK map, refetched when absent or past its 24h TTL.
    Raises whatever `httpx`/JSON errors the fetch raises — the caller decides
    what a resolver outage costs (CR040: never a silent empty map that reads
    as "no CIK for anything")."""
    global _cache, _cached_at
    with _lock:
        now = time.monotonic()
        if _cache is not None and (now - _cached_at) < _TTL_SECONDS:
            return _cache
        fresh = _fetch_map()
        _cache = fresh
        _cached_at = now
        return fresh


def resolve_cik(ticker: str) -> int | None:
    """The issuer's CIK for `ticker`, or None when SEC's own map doesn't carry
    it (foreign filer, OTC name, unlisted). Propagates a fetch failure rather
    than swallowing it into None — a resolver outage and "no CIK" must not
    look the same to the caller."""
    sym = (ticker or "").strip().upper()
    if not sym:
        return None
    return _get_map().get(sym)


def clear_cik_cache() -> None:
    """Test seam / operational escape hatch."""
    global _cache, _cached_at
    with _lock:
        _cache = None
        _cached_at = 0.0
