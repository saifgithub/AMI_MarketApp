"""Malaysian headline CPI from OpenDOSM (CR282 lane E).

The one Malaysian macro print on a Bursa Room's Macro & Events sheet besides the
BNM OPR. Source: the Department of Statistics Malaysia open-data API
(`api.data.gov.my/data-catalogue?id=cpi_headline`, CC BY 4.0, rate limit 4
requests/minute). The API serves the CPI INDEX (overall division); year-on-year
inflation is AMI's own quotient of the latest index over the same month a year
earlier, and the rendered line says so.

Behind `OPENDOSM_CPI_ENABLED` (default off). Off, unreachable or malformed all
yield a `CpiRead` whose `reason` is rendered as an explicit "not available" line:
never a number from memory (CR040, CR104). Cached for a day in-process — the
series moves monthly and the rate limit is 4/min.

Network is confined to `_fetch_rows` so tests stub exactly one seam.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import date

import httpx

from app.core.config import settings
from app.core.logging import logger

URL = "https://api.data.gov.my/data-catalogue/"
ATTRIBUTION = "DOSM (OpenDOSM, CC BY 4.0)"
_CACHE_TTL_S = 24 * 3600
_TIMEOUT_S = 8.0

_lock = threading.Lock()
_cache: tuple[float, "CpiRead"] | None = None


@dataclass(frozen=True)
class CpiRead:
    yoy_pct: float | None
    month: date | None
    index: float | None
    prior_year_index: float | None
    reason: str | None = None


def _fetch_rows() -> list[dict]:
    resp = httpx.get(
        URL,
        params={"id": "cpi_headline", "filter": "overall@division", "sort": "-date", "limit": 14},
        timeout=_TIMEOUT_S,
        follow_redirects=True,
    )
    resp.raise_for_status()
    rows = resp.json()
    if not isinstance(rows, list):
        raise ValueError("unexpected OpenDOSM payload shape")
    return rows


def _compute(rows: list[dict]) -> CpiRead:
    by_month: dict[date, float] = {}
    for r in rows:
        if r.get("division") not in (None, "overall"):
            continue
        by_month[date.fromisoformat(str(r["date"]))] = float(r["index"])
    if not by_month:
        return CpiRead(None, None, None, None, "OpenDOSM returned no overall CPI rows")
    latest = max(by_month)
    prior = date(latest.year - 1, latest.month, 1)
    if prior not in by_month:
        return CpiRead(None, latest, by_month[latest], None,
                       "OpenDOSM did not return the same month a year earlier")
    idx, prev = by_month[latest], by_month[prior]
    return CpiRead(round((idx / prev - 1.0) * 100.0, 1), latest, idx, prev)


def fetch_cpi(*, now: float | None = None) -> CpiRead:
    """The latest year-on-year CPI read, or a `CpiRead` carrying why there is none."""
    global _cache
    if not settings.opendosm_cpi_enabled:
        return CpiRead(None, None, None, None,
                       "the OpenDOSM CPI feed is not enabled on this deployment")
    t = time.time() if now is None else now
    with _lock:
        if _cache is not None and t - _cache[0] < _CACHE_TTL_S:
            return _cache[1]
    try:
        read = _compute(_fetch_rows())
    except Exception as exc:  # noqa: BLE001 — degrade loudly, never fabricate
        logger.warning("opendosm_cpi_unreadable", error=str(exc)[:200])
        return CpiRead(None, None, None, None, "the OpenDOSM CPI feed could not be read")
    with _lock:
        _cache = (t, read)
    return read


def reset_cache() -> None:
    global _cache
    with _lock:
        _cache = None


def cpi_line(read: CpiRead) -> str:
    if read.yoy_pct is None or read.month is None:
        return f"Malaysia headline CPI: not available this call — {read.reason}. Do not supply a CPI figure from memory."
    return (
        f"Malaysia headline CPI: {read.yoy_pct:+.1f}% year-on-year for {read.month.strftime('%b %Y')} "
        f"(index {read.index} vs {read.prior_year_index} a year earlier; AMI's own quotient of "
        f"the published index). Source: {ATTRIBUTION}."
    )
