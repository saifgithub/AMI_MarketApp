"""Sector allocation + concentration enforcement (CR026).

The mandate advertises a sector-concentration rule ("no sector > 40%", default —
`lifecycle.md:120`) that had ZERO backend enforcement and no Portfolio-screen feed.
This module supplies the three pieces that close that gap:

  * `allocate_by_sector` — the pure aggregation (holdings + quotes → sector → weight),
    normalised over invested market value. Empty portfolio → `{}`; a ticker whose
    sector is unknown lands in the "Other" bucket (logged, never raises — the
    `fundamentals.py` never-raises pattern).
  * `SectorMap` + `default_sector_map()` — the ticker → GICS-sector resolver. It reads
    the per-ticker sector map persisted on the DEF061 classification snapshot
    (`classification_universe.latest_sector_map`), a cheap LOCAL DB read — NEVER a
    `yf.Ticker().info` fetch on the request path (the CR075/DEF089 rule). An unknown
    ticker resolves to "Other" — disclosed, but NEVER a block (the DEF059 inversion
    guard: blocking-on-unknown would reject every unclassified name).
  * `sector_concentration_cap` + `sector_cap_breach` — the mandate-derived cap and the
    deterministic "would this BUY push its sector over the cap?" check that
    `safety_floor.check_mandate_compliance()` wires in alongside the single-name block.

The "Other" bucket is display-only for the cap: only a KNOWN sector can breach, so an
unrefreshed/empty sector map degrades to no-enforcement + a visible "Other" disclosure
rather than blocking every trade. The loud-degrade for the sector DATA lives on the
refresh side (`classification_universe._CLASSIFIED_MIN_ROWS`), same as the fossil/sin
sets it rides alongside.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from app.core.logging import logger
from app.db import get_session
from app.schemas.mandate import Mandate
from app.services.classification_universe import latest_sector_map

# The catch-all bucket for a ticker with no stored GICS sector. Disclosed on the
# allocation feed, but it can NEVER trigger a concentration block (DEF059 guard).
OTHER = "Other"

# Uninvested cash, as its own allocation bucket (DEF149). Disclosed on the feed so the
# donut's slices are honest about what fraction of the portfolio is NOT invested, and
# excluded from the concentration judgement for the same reason OTHER is — holding cash
# is never a concentration breach.
CASH = "Cash"

# Buckets that are disclosed but can never breach the concentration cap.
NON_SECTOR_BUCKETS = frozenset({OTHER, CASH})

# Default sector-concentration cap when the mandate carries the middle
# concentration_tolerance (per `lifecycle.md:120` — "any sector > 40% (default)").
_DEFAULT_SECTOR_CAP = 0.40

# concentration_tolerance (1..5, the RiskComponents scale) → sector cap fraction.
# The middle value (3, the mandate default) anchors to the advertised 0.40; a more
# concentration-averse user gets a tighter cap, a tolerant one a looser cap. Read
# from the user's mandate — never hard-coded at the call site.
_TOLERANCE_TO_CAP: dict[int, float] = {
    1: 0.25,
    2: 0.30,
    3: 0.40,
    4: 0.50,
    5: 0.60,
}


def _ticker_of(h: Any) -> str:
    return str(getattr(h, "ticker", "") or "").upper().strip()


def _qty_of(h: Any) -> float:
    try:
        return float(getattr(h, "quantity", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _resolve_sector(sector_of: Callable[[str], str], ticker: str) -> str:
    """Never raise — a broken resolver degrades a name to 'Other', it does not sink
    the whole aggregation (fundamentals.py never-raises pattern)."""
    try:
        sec = sector_of(ticker)
    except Exception as exc:  # noqa: BLE001 — degrade to Other, log, never raise
        logger.debug("sector_resolve_failed", ticker=ticker, error=str(exc)[:120])
        return OTHER
    return sec or OTHER


def _sector_values(
    holdings: Iterable[Any],
    quotes: dict[str, float],
    sector_of: Callable[[str], str],
) -> dict[str, float]:
    """Raw market value ($) per sector from holdings × quotes. Unknown sector → Other."""
    q = {str(k).upper().strip(): v for k, v in (quotes or {}).items()}
    values: dict[str, float] = {}
    for h in holdings or ():
        t = _ticker_of(h)
        if not t:
            continue
        price = q.get(t)
        if price is None:
            logger.debug("sector_allocation_missing_quote", ticker=t)
            continue
        val = _qty_of(h) * float(price or 0.0)
        if val <= 0:
            continue
        sec = _resolve_sector(sector_of, t)
        values[sec] = values.get(sec, 0.0) + val
    return values


def allocate_by_sector(
    holdings: Iterable[Any],
    quotes: dict[str, float],
    *,
    cash: float = 0.0,
    sector_of: Callable[[str], str] | None = None,
) -> dict[str, float]:
    """Sector → weight (0.0–1.0), normalised over TOTAL portfolio value.

    Sums `quantity × current_price` per sector, adds `cash` as its own bucket, and
    divides by the total. Empty portfolio (or all-zero value) → `{}`. A ticker whose
    sector is unknown lands in the "Other" bucket — logged, never raised. Pure given
    `sector_of` (the ticker → sector resolver); production callers omit it and get the
    snapshot-backed `default_sector_map().sector`, tests inject a fixture.

    DEF149: the denominator used to be invested value alone, so a user's FIRST buy was
    100% of "the portfolio" no matter how small it was against their cash. Cash is a
    position — it is the one every allocation is measured against — and the breach copy
    already said "of your portfolio". Callers that hold cash MUST pass it; the 0.0
    default exists for the genuinely cash-free caller, not as a convenience.
    """
    resolver = sector_of or default_sector_map().sector
    values = _sector_values(holdings, quotes, resolver)
    if not values:
        # Nothing invested — there is no allocation to speak of, and the CR026
        # contract is `{}` so the client hides the card entirely. Returning a
        # lone 100%-Cash ring would put a meaningless donut on every new user's
        # portfolio screen, restating the cash figure already above it.
        return {}
    if cash and cash > 0:
        values[CASH] = float(cash)
    total = sum(values.values())
    if total <= 0:
        return {}
    return {sec: val / total for sec, val in values.items()}


def sector_concentration_cap(mandate: Mandate) -> float:
    """The user's sector-concentration cap (0.0–1.0), read from the mandate's
    `risk_components.concentration_tolerance`. Defaults to 0.40 when the tolerance is
    unset/out of range — never hard-coded at the enforcement site."""
    rc = getattr(mandate, "risk_components", None)
    tol = getattr(rc, "concentration_tolerance", None)
    try:
        return _TOLERANCE_TO_CAP.get(int(tol), _DEFAULT_SECTOR_CAP)
    except (TypeError, ValueError):
        return _DEFAULT_SECTOR_CAP


@dataclass(frozen=True)
class SectorBreach:
    """A proposed BUY that would push its sector over the mandate cap."""

    sector: str
    projected_weight: float
    cap: float

    def message(self) -> str:
        """User-facing line — AMI by name, never "the AI"."""
        return (
            f"this BUY would push {self.sector} to {self.projected_weight * 100:.1f}% "
            f"of your portfolio, over your {self.cap * 100:.0f}% sector-concentration "
            f"limit — AMI's mandate blocks it."
        )


def sector_cap_breach(
    *,
    holdings: Iterable[Any],
    quotes: dict[str, float],
    proposed_ticker: str,
    proposed_value: float,
    sector_map: Any,
    cap: float,
    portfolio_value: float,
) -> SectorBreach | None:
    """Deterministic sector-concentration check for a proposed BUY.

    Returns a `SectorBreach` when adding `proposed_value` of `proposed_ticker` would
    push that ticker's sector past `cap` **as a fraction of total portfolio value**,
    else None. Buying a sector only raises THAT sector's weight, so only the proposed
    sector can newly breach — an existing over-cap sector is never used to block a
    DIFFERENT-sector buy that would actually improve diversification.

    DEF149 — the denominator is `portfolio_value` (cash + invested), NOT invested
    alone. A BUY spends cash to acquire shares, so it moves value between two buckets
    and leaves the total unchanged: the correct denominator is the PRE-trade total,
    and adding `proposed_value` to it (as this did) double-counts the purchase. With
    the old invested-only denominator a brand-new user's first buy was always exactly
    100% of "the portfolio" and was always blocked, whatever its size against their
    cash. `portfolio_value` is required, not defaulted — a caller that cannot supply
    it must not silently fall back to the arithmetic that caused the defect.

    The "Other" (unknown) bucket NEVER breaches — an unclassified ticker is no ruling
    either way (the DEF059 inversion guard), mirroring the classification UNKNOWN=
    permitted rule. `sector_map` is the resolver (a `SectorMap`); no network."""
    if proposed_value is None or proposed_value <= 0:
        return None
    resolver = getattr(sector_map, "sector", None)
    if not callable(resolver):
        return None
    proposed_sector = _resolve_sector(resolver, str(proposed_ticker).upper().strip())
    if proposed_sector == OTHER:
        return None  # unknown sector → disclosed elsewhere, never a block
    current = _sector_values(holdings, quotes, resolver)
    projected_sector_val = current.get(proposed_sector, 0.0) + proposed_value
    # Guard a stale/short portfolio_value: the total can never be less than what the
    # post-trade portfolio demonstrably holds, or the weight reads above 1.0.
    projected_total = max(
        float(portfolio_value or 0.0),
        sum(current.values()) + proposed_value,
    )
    if projected_total <= 0:
        return None
    weight = projected_sector_val / projected_total
    if weight > cap + 1e-9:
        return SectorBreach(sector=proposed_sector, projected_weight=weight, cap=cap)
    return None


# ── ticker → sector resolver (reads the stored snapshot, never a socket) ──────


@dataclass(frozen=True)
class SectorMap:
    """A ticker → GICS-sector resolver over the stored snapshot map.

    `.sector(ticker)` returns the stored sector or "Other" for an unknown name. Held
    as a plain dict resolved once off the request path — no network on any lookup."""

    mapping: dict[str, str]

    def sector(self, ticker: str) -> str:
        return self.mapping.get(str(ticker).upper().strip(), OTHER)

    @property
    def is_empty(self) -> bool:
        return not self.mapping


class SectorMapProvider:
    """Process-wide cache of the stored sector map (CR026).

    Reads `classification_universe.latest_sector_map` — a cheap LOCAL DB read — and
    re-reads it at most every `refetch_interval_s` seconds. NEVER opens a socket on a
    lookup; the yfinance calls that build the map live in the daily classification
    refresh, off the request path (the CR075/DEF089 rule)."""

    def __init__(self, *, fetcher: Callable[[], dict[str, str]] | None = None,
                 refetch_interval_s: float = 60.0) -> None:
        self._fetcher = fetcher or _db_sector_map_fetcher
        self._refetch_interval_s = refetch_interval_s
        self._cache: SectorMap | None = None
        self._last_attempt: float | None = None

    def _refetch_due(self) -> bool:
        if self._last_attempt is None:
            return True
        return (time.monotonic() - self._last_attempt) >= self._refetch_interval_s

    def get(self, *, refresh: bool = False) -> SectorMap:
        if self._cache is None or refresh or self._refetch_due():
            self._last_attempt = time.monotonic()
            try:
                mapping = self._fetcher()
            except Exception as exc:  # noqa: BLE001 — degrade to empty map, never raise
                logger.warning("sector_map_fetch_failed", error=str(exc)[:160])
                mapping = {}
            if not mapping:
                # Loud-but-safe: an empty map means every ticker resolves to "Other"
                # (no enforcement, disclosed). Surfaced so a persistently-empty map
                # after refreshes is visible, not silent.
                logger.info("sector_map_empty", note="no per-ticker sectors stored yet")
            self._cache = SectorMap(mapping=mapping)
        return self._cache


def _db_sector_map_fetcher() -> dict[str, str]:
    with get_session() as session:
        return latest_sector_map(session)


_provider: SectorMapProvider | None = None


def get_sector_map_provider() -> SectorMapProvider:
    global _provider
    if _provider is None:
        _provider = SectorMapProvider()
    return _provider


def reset_sector_map_provider(provider: SectorMapProvider | None = None) -> None:
    """Test seam — swap or clear the singleton."""
    global _provider
    _provider = provider


def default_sector_map() -> SectorMap:
    """The snapshot-backed ticker → sector resolver for callers that don't inject one.
    A cheap LOCAL read of the stored map — NEVER a network fetch (CR075/DEF089)."""
    return get_sector_map_provider().get()


async def default_sector_map_async() -> SectorMap:
    """Event-loop-safe accessor — the local DB read stays off the loop via
    `asyncio.to_thread` (the one uvicorn process serves every concurrent request)."""
    return await asyncio.to_thread(get_sector_map_provider().get)
