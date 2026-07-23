"""HLAL/FTSE Shariah divergence monitor — log-only (CR069-DIVERGE, CR069 Phase 1).

§3a of the CR069 spec measured the two free sources disagreeing on 47.9% of
their union (SPUS/AAOIFI 216, HLAL/FTSE 210, agree 146). That number is why a
failover must never be built: it would flip a user's observance verdict with
no signal. This module makes the disagreement *visible* — a structured log
line per divergence — without letting it near the answer.

Hard boundaries (CR069-DIVERGE assign lane):
  1. The HLAL/FTSE set never reaches `safety_floor.py`, `ShariaVerdict`, or any
     API response. Nothing in this module is imported by the enforcement seam
     (`safety_floor.py`, `sim_engine.py`, `room_runner.py`, `mandate.py`).
  2. No union, no intersection with the AAOIFI set. AAOIFI/SPUS stays the one
     named standard the `halal` flag enforces; this module only ever *reads*
     an already-resolved `ShariaVerdict`, never writes into one.
  3. HLAL/FTSE being unreachable degrades to "no observation logged" — it must
     never pause or otherwise affect the AAOIFI-sourced halal flag. A monitor
     that can take down the thing it monitors is worse than no monitor.

Wiring a call site into a live request/Room path is deliberately out of scope
for this lane (see "Deferred teaching surface" in the CR069-DIVERGE assign
lane) — this module is dormant until that's picked up.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.schemas.sharia import ShariaStatus, ShariaVerdict
from app.services.sharia_universe import HalalUniverse, ShariaSourceError, parse_holdings_csv

STANDARD = "FTSE Shariah"
SOURCE = "FTSE Shariah USA Screened Index (via HLAL/Wahed)"

_FETCH_TIMEOUT_S = 15.0

# Same WAF-avoidance User-Agent as sharia_universe.py's SPUS fetch (DEF092):
# the free-tier holdings sources 403 python-httpx's/python-requests' default UA.
_USER_AGENT = "AMI-Trade/1.0 (+https://agenticmarketintel.ai)"

# Measured 2026-07-22: 213 rows. Floor sits well below that with headroom for a
# rebalance shrink, mirroring sharia_universe.py's SPUS floor (constraint: a
# truncated download must raise, never silently yield a short observation).
_HLAL_MIN_ROWS = 150


@dataclass(frozen=True)
class HlalObservation:
    """One fetch of the HLAL/FTSE compliant set.

    Deliberately NOT a `HalalUniverse` — it carries no parent index and must
    never substitute for one in the enforcement seam's `set[str]` argument.
    `available=False` means the fetch failed; carries no tickers, and callers
    must treat that as "no observation," not "empty universe."
    """

    compliant: frozenset[str]
    as_of: date | None
    available: bool


@dataclass(frozen=True)
class DivergenceRecord:
    """One ticker where the AAOIFI/SPUS verdict and the FTSE/HLAL observation
    disagree. Log-only payload — see module docstring boundary 1."""

    ticker: str
    aaoifi_status: ShariaStatus
    aaoifi_as_of: date | None
    ftse_compliant: bool
    ftse_as_of: date | None


def fetch_hlal_universe(client: httpx.Client, url: str) -> tuple[frozenset[str], date | None]:
    """Fetch + parse the HLAL/FTSE holdings CSV — same Tidal schema as SPUS
    (CR069-DIVERGE assign lane, measured 2026-07-22: 213 rows, identical shape
    to the SPUS fetch `sharia_universe.fetch_compliant_universe` parses)."""
    resp = client.get(url)
    resp.raise_for_status()
    tickers, as_of = parse_holdings_csv(resp.text)
    if len(tickers) < _HLAL_MIN_ROWS:
        raise ShariaSourceError(
            f"HLAL holdings parsed to {len(tickers)} tickers (< floor {_HLAL_MIN_ROWS}) "
            f"— treating as truncated"
        )
    return tickers, as_of


def _default_fetcher(url: str) -> tuple[frozenset[str], date | None]:
    # follow_redirects=True: the Google Sheets `export?format=csv` URL 307s to a
    # signed googleusercontent URL. Found live against the real shipped client
    # (httpx.Client defaults to NOT following redirects) — without this the
    # fetch always 307s to an empty body and the monitor silently sits
    # "unavailable" forever. Same DEF089 failure mode one level down: verified
    # with a different client behaviour than the one that ships.
    with httpx.Client(
        timeout=_FETCH_TIMEOUT_S, headers={"User-Agent": _USER_AGENT}, follow_redirects=True
    ) as client:
        return fetch_hlal_universe(client, url)


class HlalDivergenceProvider:
    """Fetches + caches the HLAL/FTSE observation.

    Never raises past its own boundary — a fetch failure here is a monitor
    outage, not the halal flag's outage (hard boundary 3). `fetcher` is
    injectable so tests never touch the network.
    """

    def __init__(self, *, url: str, fetcher=None) -> None:
        self._url = url
        self._fetcher = fetcher or (lambda: _default_fetcher(self._url))
        self._cache: HlalObservation | None = None

    def get(self, *, refresh: bool = False) -> HlalObservation:
        if self._cache is None or refresh:
            try:
                compliant, as_of = self._fetcher()
                self._cache = HlalObservation(compliant=compliant, as_of=as_of, available=True)
            except (httpx.HTTPError, ShariaSourceError) as exc:
                logger.error("sharia_divergence_hlal_fetch_failed", error=str(exc))
                self._cache = HlalObservation(compliant=frozenset(), as_of=None, available=False)
        return self._cache


_provider: HlalDivergenceProvider | None = None


def get_hlal_divergence_provider() -> HlalDivergenceProvider:
    """Process-wide singleton, built from config on first use."""
    global _provider
    if _provider is None:
        _provider = HlalDivergenceProvider(url=settings.sharia_hlal_holdings_url)
    return _provider


def reset_hlal_divergence_provider(provider: HlalDivergenceProvider | None = None) -> None:
    """Test seam — swap or clear the singleton."""
    global _provider
    _provider = provider


def log_divergence(
    ticker: str, aaoifi: ShariaVerdict, hlal: HlalObservation
) -> DivergenceRecord | None:
    """Compare one ticker's AAOIFI verdict against the HLAL/FTSE observation
    and emit a structured log line if they disagree.

    Returns the record (useful for tests and for a future caller that wants to
    aggregate it), but the return value is not itself wired into any verdict,
    response, or enforcement path by this module — see boundary 1.
    """
    if not hlal.available:
        return None
    if aaoifi.status not in (ShariaStatus.PASS, ShariaStatus.SCREENED_OUT):
        return None  # no concrete AAOIFI opinion to diverge from (UNKNOWN/UNAVAILABLE)

    t = ticker.upper().strip()
    ftse_compliant = t in hlal.compliant
    aaoifi_compliant = aaoifi.status is ShariaStatus.PASS
    if aaoifi_compliant == ftse_compliant:
        return None

    record = DivergenceRecord(
        ticker=t,
        aaoifi_status=aaoifi.status,
        aaoifi_as_of=aaoifi.as_of,
        ftse_compliant=ftse_compliant,
        ftse_as_of=hlal.as_of,
    )
    logger.info(
        "sharia_divergence_detected",
        ticker=record.ticker,
        aaoifi_status=record.aaoifi_status.value,
        aaoifi_as_of=record.aaoifi_as_of.isoformat() if record.aaoifi_as_of else None,
        ftse_compliant=record.ftse_compliant,
        ftse_as_of=record.ftse_as_of.isoformat() if record.ftse_as_of else None,
        standard=STANDARD,
        source=SOURCE,
    )
    return record


def log_divergences(
    tickers: Iterable[str], aaoifi: HalalUniverse, hlal: HlalObservation
) -> list[DivergenceRecord]:
    """Batch form for a set of tickers (a user's holdings/watchlist).

    Resolves each ticker against `aaoifi` (read-only — `HalalUniverse.resolve`
    is a pure lookup) and logs any divergence against `hlal`. See boundary 1:
    this function only ever reads from `aaoifi`; it never writes into it, into
    any `ShariaVerdict`, or into any response.
    """
    records = []
    for ticker in tickers:
        verdict = aaoifi.resolve(ticker)
        record = log_divergence(ticker, verdict, hlal)
        if record is not None:
            records.append(record)
    return records
