"""Sourced Sharia universe — fetcher, cache and three-state resolver (CR069 Phase 1).

Replaces the 7-ticker `DEFAULT_HALAL_DEMO_UNIVERSE` placeholder that DEF084 exposed
as an allowlist masquerading as a screen. The `halal` mandate flag now enforces the
published constituents of the **S&P 500 Sharia Industry Exclusions Index** (AAOIFI
standard, screened by S&P Dow Jones), read from SPUS's daily-transparency holdings
CSV, carrying its as-of date.

This is a *sourced allowlist*, NOT a computed ratio screen — the three-ratio math in
`app.trading_math.screening` stays dormant (CR069 constraint 4) until a source supplies
real debt / liquid-asset / impermissible-income figures. Every comment and docstring
here describes an allowlist; do not let it drift into claiming AMI runs a screen.

Three states, not two (constraint 2): the compliant set alone cannot tell "screened
out" from "never looked at" — SPUS publishes only the compliant names, so absence means
both identically. The **parent index** (S&P 500 membership, read the same way from a
large-cap S&P 500 ETF's published holdings CSV) is what distinguishes them. In parent
index + absent from compliant ⇒ SCREENED_OUT (blocked). Not in parent index ⇒ UNKNOWN
(permitted, with the disclosure attached — G3 RESOLVED 2026-07-23).

Degrade loudly (constraint 3 / CR040): if the source can't be fetched or is stale beyond
its window, the flag PAUSES visibly — never a silent stale read, never a fall back to the
old 7-ticker set.

The `halal` enforcement seam in `safety_floor.py` / `sim_engine.py` / `room_runner.py`
threads a `set[str]`. `HalalUniverse` IS-A `frozenset` of the compliant tickers so it
drops into that seam unchanged, while carrying the parent index + provenance alongside so
every enforcement path (including the Room's, which may only change one line) resolves the
full three states rather than two.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timezone

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.schemas.sharia import ShariaStatus, ShariaVerdict

# ── Provenance constants ────────────────────────────────────────────────────
STANDARD = "AAOIFI"
SOURCE = "S&P 500 Sharia Industry Exclusions Index (via SPUS)"
PARENT_SOURCE = "S&P 500 (via iShares IVV)"

# Plain equity ticker: 1-5 letters, optional single-letter share-class suffix
# (BRK.B). Rejects the CSV's non-equity line items — cash/CVR rows carry digits
# (`003654100CVR`, `2602335D`) and footer/disclaimer text carries spaces/commas,
# so neither survives this anchor. (CR069 §2: "plain alphabetic tickers only".)
_TICKER_RE = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")
_TICKER_COLS = ("stockticker", "ticker")
_DATE_COLS = ("date",)

# A truncated download must RAISE, never yield a short universe (CR069 §2 / DEF084
# in the other direction). Floors sit well below the measured live counts with
# headroom for a quarterly-rebalance shrink: SPUS held 219 compliant names on
# 2026-07-22; the S&P 500 parent holds ~500. A body that parses to fewer than
# these is treated as truncated/corrupt.
_SPUS_MIN_ROWS = 150
_PARENT_MIN_ROWS = 400

_FETCH_TIMEOUT_S = 15.0


class ShariaSourceError(RuntimeError):
    """Raised when a holdings CSV is missing, truncated, or otherwise unusable.

    Callers must NOT swallow this into a stale/empty universe silently — the
    provider converts it into a *loudly paused* (UNAVAILABLE) universe, which is
    the visible-degrade contract (constraint 3)."""


class HalalUniverse(frozenset):
    """The sourced compliant set, carrying its provenance + parent-index membership.

    IS-A `frozenset[str]` of compliant (uppercased) tickers so it substitutes for
    the existing `halal_universe: set[str]` seam with no signature change. The
    extra attributes ride alongside so `safety_floor` can resolve three states.

    A `stale=True` universe is the loud-degrade carrier: it resolves every ticker
    to UNAVAILABLE so the halal flag pauses instead of silently answering from an
    empty or out-of-date set.
    """

    parent_index: frozenset
    as_of: date | None
    standard: str
    source: str
    stale: bool

    def __new__(
        cls,
        compliant,
        *,
        parent_index=frozenset(),
        as_of: date | None = None,
        standard: str = STANDARD,
        source: str = SOURCE,
        stale: bool = False,
    ) -> "HalalUniverse":
        obj = super().__new__(cls, (str(x).upper().strip() for x in compliant))
        obj.parent_index = frozenset(str(x).upper().strip() for x in parent_index)
        obj.as_of = as_of
        obj.standard = standard
        obj.source = source
        obj.stale = stale
        return obj

    def resolve(self, ticker: str) -> ShariaVerdict:
        """Resolve a ticker to one of the three states (+ the paused state)."""
        t = ticker.upper().strip()
        if self.stale:
            status = ShariaStatus.UNAVAILABLE
        elif t in self:
            status = ShariaStatus.PASS
        elif t in self.parent_index:
            status = ShariaStatus.SCREENED_OUT
        else:
            status = ShariaStatus.UNKNOWN
        return ShariaVerdict(
            status=status,
            ticker=t,
            standard=self.standard,
            source=self.source,
            as_of=self.as_of,
        )


# ── CSV parsing ─────────────────────────────────────────────────────────────


def _locate_header(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    """Find the header row (SPUS/Tidal have it first; iShares carry a preamble)
    and return (row_index, {lowercased_column: index}). Raises if no ticker
    column is found anywhere."""
    for i, row in enumerate(rows):
        cols = {c.strip().strip('"').lower(): j for j, c in enumerate(row)}
        if any(tc in cols for tc in _TICKER_COLS):
            return i, cols
    raise ShariaSourceError("no ticker column found in holdings CSV")


def parse_holdings_csv(text: str) -> tuple[frozenset, date | None]:
    """Parse a published-holdings CSV into (tickers, as_of).

    Tolerant of the two shapes in play: SPUS/Tidal (clean, `StockTicker` + per-row
    `Date`) and iShares (preamble + `Ticker`, no per-row date). Non-equity rows and
    footer/disclaimer lines are dropped by the ticker anchor. `as_of` comes from a
    per-row Date column when present (SPUS); None otherwise (parent index needs
    membership only)."""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise ShariaSourceError("empty holdings CSV")
    header_idx, cols = _locate_header(rows)
    ticker_col = next(cols[tc] for tc in _TICKER_COLS if tc in cols)
    date_col = next((cols[dc] for dc in _DATE_COLS if dc in cols), None)

    tickers: set[str] = set()
    as_of: date | None = None
    for row in rows[header_idx + 1:]:
        if len(row) <= ticker_col:
            continue
        raw = row[ticker_col].strip().strip('"').upper()
        if _TICKER_RE.match(raw):
            tickers.add(raw)
        if date_col is not None and as_of is None and len(row) > date_col:
            as_of = _parse_date(row[date_col].strip().strip('"'))
    return frozenset(tickers), as_of


def _parse_date(raw: str) -> date | None:
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _fetch_csv(client: httpx.Client, url: str) -> str:
    resp = client.get(url)
    resp.raise_for_status()
    return resp.text


def fetch_compliant_universe(
    client: httpx.Client, url: str
) -> tuple[frozenset, date | None]:
    """Fetch + parse the SPUS holdings CSV. Asserts the plausible-row floor so a
    truncated download raises rather than silently shrinking the universe."""
    tickers, as_of = parse_holdings_csv(_fetch_csv(client, url))
    if len(tickers) < _SPUS_MIN_ROWS:
        raise ShariaSourceError(
            f"SPUS holdings parsed to {len(tickers)} tickers (< floor {_SPUS_MIN_ROWS}) "
            f"— treating as truncated, refusing to enforce a short universe"
        )
    return tickers, as_of


def fetch_parent_index(client: httpx.Client, url: str) -> frozenset:
    """Fetch + parse the parent-index (S&P 500 ETF) holdings CSV for membership."""
    tickers, _ = parse_holdings_csv(_fetch_csv(client, url))
    if len(tickers) < _PARENT_MIN_ROWS:
        raise ShariaSourceError(
            f"parent-index holdings parsed to {len(tickers)} tickers "
            f"(< floor {_PARENT_MIN_ROWS}) — treating as truncated"
        )
    return tickers


def _is_stale(as_of: date | None, now: date, max_age_days: int) -> bool:
    if as_of is None:
        return True
    return (now - as_of).days > max_age_days


# ── Provider (cache + loud degrade) ─────────────────────────────────────────


class ShariaUniverseProvider:
    """Fetches, caches and staleness-guards the sourced universe.

    `fetcher` is injectable so tests exercise the parser + cache against a
    checked-in fixture and never touch the network. In production the default
    fetcher uses httpx.
    """

    def __init__(
        self,
        *,
        compliant_url: str,
        parent_url: str,
        staleness_days: int,
        enabled: bool,
        fetcher=None,
    ) -> None:
        self._compliant_url = compliant_url
        self._parent_url = parent_url
        self._staleness_days = staleness_days
        self._enabled = enabled
        self._fetcher = fetcher or self._default_fetcher
        self._cache: HalalUniverse | None = None

    def _default_fetcher(self) -> tuple[frozenset, date | None, frozenset]:
        with httpx.Client(timeout=_FETCH_TIMEOUT_S) as client:
            compliant, as_of = fetch_compliant_universe(client, self._compliant_url)
            parent = fetch_parent_index(client, self._parent_url)
        return compliant, as_of, parent

    def _paused(self, as_of: date | None = None) -> HalalUniverse:
        """A loud-degrade universe — resolves everything to UNAVAILABLE."""
        return HalalUniverse(frozenset(), as_of=as_of, stale=True)

    def _build(self, now: date | None = None) -> HalalUniverse:
        now = now or datetime.now(timezone.utc).date()
        if not self._enabled:
            # Feature off (default). Loud-degrade rather than silently fall back to
            # the retired 7-ticker set. Set SHARIA_SCREEN_ENABLED=true on Alpha once
            # the source fetch is verified. (CR040 convention: presence/flag gates.)
            logger.info("sharia_universe_disabled")
            return self._paused()
        try:
            compliant, as_of, parent = self._fetcher()
        except (httpx.HTTPError, ShariaSourceError) as exc:
            logger.error("sharia_universe_fetch_failed", error=str(exc))
            return self._paused()
        if _is_stale(as_of, now, self._staleness_days):
            logger.error(
                "sharia_universe_stale",
                as_of=as_of.isoformat() if as_of else None,
                max_age_days=self._staleness_days,
            )
            return self._paused(as_of=as_of)
        logger.info(
            "sharia_universe_loaded",
            compliant=len(compliant),
            parent=len(parent),
            as_of=as_of.isoformat() if as_of else None,
        )
        return HalalUniverse(compliant, parent_index=parent, as_of=as_of)

    def get(self, *, refresh: bool = False, now: date | None = None) -> HalalUniverse:
        if self._cache is None or refresh:
            self._cache = self._build(now=now)
        return self._cache


_provider: ShariaUniverseProvider | None = None


def get_sharia_universe_provider() -> ShariaUniverseProvider:
    """Process-wide singleton, built from config on first use."""
    global _provider
    if _provider is None:
        _provider = ShariaUniverseProvider(
            compliant_url=settings.sharia_spus_holdings_url,
            parent_url=settings.sharia_parent_index_url,
            staleness_days=settings.sharia_staleness_days,
            enabled=settings.sharia_screen_enabled,
        )
    return _provider


def reset_sharia_universe_provider(provider: ShariaUniverseProvider | None = None) -> None:
    """Test seam — swap or clear the singleton."""
    global _provider
    _provider = provider


def default_halal_universe() -> HalalUniverse:
    """The sourced `halal` universe for callers that don't pass one explicitly.

    Cheap after the first call (cached). When the feature is disabled or the source
    is unavailable/stale, returns a paused universe so the halal flag degrades
    loudly instead of enforcing a stale or placeholder set."""
    return get_sharia_universe_provider().get()
