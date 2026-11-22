"""CR229 — BLS Public Data API fetcher for the H1 macro prints (CPI, PPI).

The non-FRED path for CR221's H1 item. FRED's terms bar use "in connection with ...
large language models ... generative AI"; BLS publishes the same two series as the
primary source, public domain, and its API terms carry no such clause. Saiful's
2026-09-23 ruling keeps FRED primary, so this is OFF by default
(`MACRO_DIRECT_BLS_ENABLED`) and nothing in the room calls it yet.

No FRED fetcher exists in the repo (CR238 slot 7 is unbuilt), so `MacroSeries` is the
source-neutral shape slot 7 should reuse: ascending monthly observations plus the
source id, a human source label and the retrieval date, so a rendered value can always
say which provider produced it.

Series (BLS ids, FRED equivalents in brackets):
  CPI_ALL_ITEMS_SA        CUSR0000SA0  [CPIAUCSL]
  PPI_ALL_COMMODITIES     WPU00000000  [PPIACO]

Auth: no key -> API v1 (GET, 25 queries/day). `BLS_API_KEY` set -> API v2 (POST,
500/day). Docs: https://www.bls.gov/developers/api_signature.htm and
https://www.bls.gov/developers/api_signature_v2.htm.

Degrade loudly (CR040): every failure raises `MacroSourceUnavailable` naming the
source and the reason. There is no fallback to another source and no stale value; a
caller that wants FRED asks for FRED. A failed fetch is negative-cached for 60 s so a
burst of requests cannot burn v1's 25-query daily budget on retries.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import date

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SOURCE_NAME = "BLS"
_V1_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
_V2_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_DISCLAIMER = "BLS.gov cannot vouch for the data or analyses derived from these data."

_TIMEOUT_S = 10.0
_TTL_S = 12 * 60 * 60.0
_NEGATIVE_TTL_S = 60.0
_USER_AGENT = "AMI-Trade/1.0 (macro-bls)"


@dataclass(frozen=True)
class SeriesSpec:
    key: str
    bls_id: str
    title: str
    units: str


SERIES: dict[str, SeriesSpec] = {
    "CPI_ALL_ITEMS_SA": SeriesSpec(
        "CPI_ALL_ITEMS_SA",
        "CUSR0000SA0",
        "Consumer Price Index for All Urban Consumers (CPI-U), all items, U.S. city average, seasonally adjusted",
        "index 1982-84=100",
    ),
    "PPI_ALL_COMMODITIES": SeriesSpec(
        "PPI_ALL_COMMODITIES",
        "WPU00000000",
        "Producer Price Index by Commodity, all commodities, not seasonally adjusted",
        "index 1982=100",
    ),
}


@dataclass(frozen=True)
class MacroObservation:
    period: str  # "YYYY-MM"
    value: float


@dataclass(frozen=True)
class MacroSeries:
    key: str
    title: str
    units: str
    source: str
    source_series_id: str
    source_label: str
    disclaimer: str
    retrieved_on: str  # ISO date
    observations: tuple[MacroObservation, ...]  # ascending by period
    gaps: tuple[str, ...]  # months BLS published with no value ("-")

    @property
    def latest(self) -> MacroObservation:
        return self.observations[-1]


class MacroSourceUnavailable(RuntimeError):
    """The BLS fetch failed. Carries which source and series, and why, so a caller
    renders a named absent state instead of a silent blank."""

    def __init__(self, series_key: str, reason: str, *, source: str = SOURCE_NAME) -> None:
        self.series_key = series_key
        self.reason = reason
        self.source = source
        super().__init__(f"{source} {series_key}: {reason}")


_lock = threading.Lock()
_cache: dict[str, tuple[float, MacroSeries]] = {}
_failed: dict[str, tuple[float, str]] = {}


def clear_cache() -> None:
    with _lock:
        _cache.clear()
        _failed.clear()


def _source_label(spec: SeriesSpec, *, keyed: bool) -> str:
    api = "v2" if keyed else "v1"
    return f"Source: U.S. Bureau of Labor Statistics, series {spec.bls_id} (BLS Public Data API {api})"


def _parse(spec: SeriesSpec, payload: object, *, keyed: bool, today: date) -> MacroSeries:
    if not isinstance(payload, dict):
        raise MacroSourceUnavailable(spec.key, "response was not a JSON object")
    status = payload.get("status")
    if status != "REQUEST_SUCCEEDED":
        messages = "; ".join(str(m) for m in (payload.get("message") or []))
        raise MacroSourceUnavailable(spec.key, f"status {status!r}: {messages or 'no message'}")
    results = payload.get("Results")
    series_list = results.get("series") if isinstance(results, dict) else None
    if not isinstance(series_list, list):
        raise MacroSourceUnavailable(spec.key, "response carried no Results.series")
    match = next((s for s in series_list if isinstance(s, dict) and s.get("seriesID") == spec.bls_id), None)
    if match is None:
        raise MacroSourceUnavailable(spec.key, f"response did not include series {spec.bls_id}")

    observations: dict[str, float] = {}
    gaps: list[str] = []
    for row in match.get("data") or []:
        period = str(row.get("period", ""))
        if not (period.startswith("M") and period != "M13" and period[1:].isdigit()):
            continue
        label = f"{row.get('year')}-{period[1:]}"
        try:
            value = float(row["value"])
        except (KeyError, TypeError, ValueError):
            gaps.append(label)
            continue
        if value <= 0:
            raise MacroSourceUnavailable(spec.key, f"non-positive index value {value} for {label}")
        observations[label] = value
    if not observations:
        raise MacroSourceUnavailable(spec.key, "no monthly observations in response")

    return MacroSeries(
        key=spec.key,
        title=spec.title,
        units=spec.units,
        source=SOURCE_NAME,
        source_series_id=spec.bls_id,
        source_label=_source_label(spec, keyed=keyed),
        disclaimer=BLS_DISCLAIMER,
        retrieved_on=today.isoformat(),
        observations=tuple(MacroObservation(p, observations[p]) for p in sorted(observations)),
        gaps=tuple(sorted(gaps)),
    )


def _request(spec: SeriesSpec, api_key: str, client: httpx.Client, today: date) -> object:
    if api_key:
        body = {
            "seriesid": [spec.bls_id],
            "startyear": str(today.year - 2),
            "endyear": str(today.year),
            "registrationkey": api_key,
        }
        return client.post(_V2_URL, json=body)
    return client.get(_V1_URL + spec.bls_id)


def fetch_series(key: str, *, client: httpx.Client | None = None, today: date | None = None) -> MacroSeries:
    """One BLS series, cached 12 h. Raises `MacroSourceUnavailable` when the flag is
    off, the key is unknown, or the fetch/parse fails."""
    spec = SERIES.get(key)
    if spec is None:
        raise MacroSourceUnavailable(key, f"unknown series key; known: {sorted(SERIES)}")
    if not settings.macro_direct_bls_enabled:
        raise MacroSourceUnavailable(key, "MACRO_DIRECT_BLS_ENABLED is false (direct BLS sourcing is off)")

    api_key = (settings.bls_api_key or "").strip()
    keyed = bool(api_key)
    cache_key = f"{key}:{'v2' if keyed else 'v1'}"
    now = time.monotonic()
    with _lock:
        hit = _cache.get(cache_key)
        if hit and now - hit[0] < _TTL_S:
            return hit[1]
        failed = _failed.get(cache_key)
        if failed and now - failed[0] < _NEGATIVE_TTL_S:
            raise MacroSourceUnavailable(key, f"{failed[1]} (retry backoff after a recent failure)")

    today = today or date.today()
    owns_client = client is None
    http = client or httpx.Client(timeout=_TIMEOUT_S, headers={"User-Agent": _USER_AGENT})
    try:
        response = _request(spec, api_key, http, today)
        response.raise_for_status()
        series = _parse(spec, response.json(), keyed=keyed, today=today)
    except MacroSourceUnavailable as exc:
        _record_failure(cache_key, exc.reason)
        logger.warning("macro_bls fetch rejected: %s", exc)
        raise
    except (httpx.HTTPError, ValueError) as exc:
        if isinstance(exc, httpx.HTTPStatusError):
            reason = f"HTTP {exc.response.status_code}"
        else:
            reason = f"request failed ({type(exc).__name__})"
        _record_failure(cache_key, reason)
        logger.warning("macro_bls fetch failed for %s: %s", key, reason)
        raise MacroSourceUnavailable(key, reason) from None
    finally:
        if owns_client:
            http.close()

    with _lock:
        _cache[cache_key] = (time.monotonic(), series)
        _failed.pop(cache_key, None)
    return series


def _record_failure(cache_key: str, reason: str) -> None:
    with _lock:
        _failed[cache_key] = (time.monotonic(), reason)


def fetch_h1_series(*, client: httpx.Client | None = None, today: date | None = None) -> dict[str, MacroSeries]:
    """Both H1 series. All-or-raise: one failing series raises its own
    `MacroSourceUnavailable`, so a caller never renders half a macro print as whole."""
    return {key: fetch_series(key, client=client, today=today) for key in SERIES}
