"""Sourced sector/industry classification universe — classifier, cache and
four-state resolver (DEF061).

A near-exact analog of `sharia_universe.py` (CR069/CR075). The `no_fossil_fuels`
and `no_tobacco_alcohol_gambling` mandate flags were advertised in Settings as hard
per-trade filters but never enforced by the deterministic safety floor — they only
became LLM prompt narration (DEF061). This module supplies the sourced exclusion
sets that `safety_floor.check_mandate_compliance()` now enforces against, built on
the same proven architecture:

  * The universe to classify is the ~503 S&P parent constituents ALREADY persisted
    by CR075 in `sharia_universe_snapshots` — reused, not re-fetched.
  * Each ticker's `sector` / `industry` comes from `yf.Ticker(t).info` (the same
    field `fundamentals.py` reads). The reviewable artifact is the pinned
    industry-string map below (`_FOSSIL_INDUSTRIES` / `_SIN_INDUSTRIES`).
  * A daily background refresh (`run_classification_refresh_tick`, driven by
    `main.py::_classification_universe_refresh`) makes the ~500 provider calls
    OFF the request path and appends one snapshot row per successful run.
  * The read path resolves from the latest stored row — NO network on any request
    path (the CR075 lesson).
  * Degrade loudly (CR040): a refresh that classifies fewer than `_CLASSIFIED_MIN_ROWS`
    of the parent set RAISES rather than storing a short/empty universe; a disabled
    flag, an absent snapshot (seed), or a snapshot aged past the hold window all
    resolve to UNAVAILABLE (the flag pauses visibly) — never a silent empty set that
    would permit every name.

UNKNOWN handling (DEF061 build-lane decision, stated not inherited): a ticker absent
from the classified universe is PERMITTED with a disclosure, NOT blocked — mirrors
halal G3. Blocking-on-unknown would reject every unclassified name (the DEF059
inversion trap).
"""

from __future__ import annotations

import asyncio
import time
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.db import get_session
from app.db.models import ClassificationUniverseSnapshotRow
from app.schemas.classification import (
    ClassificationKind,
    ClassificationStatus,
    ClassificationVerdict,
)
from app.services.sharia_universe import latest_snapshot as latest_sharia_snapshot

# ── Provenance ──────────────────────────────────────────────────────────────
SOURCE = "AMI sector/industry classification (yfinance)"

# ── The reviewable classification map (like AAOIFI's thresholds) ─────────────
# yfinance industry strings drift — notably the em-dash in "Beverages—Brewers"
# and hyphen/dash variants. We MATCH on a normalised form (lower-cased, every
# dash flattened to a plain hyphen, whitespace collapsed) so a cosmetic dash swap
# upstream doesn't silently un-classify a name. The pinned strings below are the
# canonical normalised forms; `_normalise_industry` maps a live yfinance string
# onto them. These were the yfinance `industry` values observed for S&P 500 names
# in each bucket (verify live on promote, per DEF089 — the refresh logs its
# fossil/sin counts so a drift that empties a bucket is visible).
_FOSSIL_INDUSTRIES: frozenset[str] = frozenset({
    "oil & gas integrated",
    "oil & gas e&p",
    "oil & gas midstream",
    "oil & gas refining & marketing",
    "oil & gas equipment & services",
    "oil & gas drilling",
    "thermal coal",
    "coking coal",
})

_SIN_INDUSTRIES: frozenset[str] = frozenset({
    "tobacco",
    "beverages-brewers",
    "beverages-wineries & distilleries",
    "gambling",
    "resorts & casinos",
})

# esg_lite is a CURATED best-effort proxy (founder ruling 2026-07-25: "curate for
# now; a real rated-ESG feed comes later as a paid value-added service"). Its
# exclusion set = fossil ∪ sin ∪ this weapons/defense bucket. yfinance tags the
# weapons primes (LMT/RTX/NOC/GD/LHX, and BA on the commercial side) all under a
# single "Aerospace & Defense" industry, so that string IS the curated proxy —
# deliberately broad, and disclosed as curation, never as a rated score.
_DEFENSE_INDUSTRIES: frozenset[str] = frozenset({
    "aerospace & defense",
})

# Fossil-fuel classification is additionally gated on sector == Energy (all the
# oil/gas/coal industry strings above are Energy-sector in yfinance) so a future
# non-Energy name that happens to reuse one of these industry labels can't be
# swept in by an industry-only match.
_ENERGY_SECTOR = "energy"

# The parent set is ~503 names; nearly all resolve a sector/industry. A run that
# classifies fewer than this is treated as throttled/broken (yfinance rate-limited
# most calls) and RAISES rather than storing a short universe that would flip most
# names to UNKNOWN=permitted. Floor sits below the ~503 with headroom for the
# handful yfinance genuinely can't tag. Mirrors `sharia_universe._PARENT_MIN_ROWS`.
_CLASSIFIED_MIN_ROWS = 400

# Per-ticker throttle for the daily background classify pass (~500 sequential
# yfinance calls). Off the request path, so a ~100s pass is fine; the delay keeps
# us under yfinance's rate limiter.
_CLASSIFY_THROTTLE_S = 0.2

# How often the in-process cache re-reads the stored row (a cheap local DB read,
# never a socket — same reasoning as sharia's `_ROW_READ_REFETCH_S`).
_ROW_READ_REFETCH_S = 60.0

# A stored row younger than this counts as "already refreshed today", so a restart
# shortly after a refresh does NOT re-run the ~500-call classify pass (idempotency
# guard, mirrors `sharia_universe._SNAPSHOT_FRESH_WINDOW_S`).
_SNAPSHOT_FRESH_WINDOW_S = 20 * 60 * 60  # 20 h


class ClassificationSourceError(RuntimeError):
    """Raised when the classification universe can't be built (no parent set to
    classify, or too few names classified). Callers must NOT swallow this into an
    empty universe silently — the provider converts it into a loudly-paused
    (UNAVAILABLE) universe (CR040)."""


class ClassificationUniverse:
    """The sourced exclusion sets, carrying provenance + the classified membership.

    Four-state resolver (per kind): PERMITTED / EXCLUDED / UNKNOWN / UNAVAILABLE.
    A `stale=True` universe is the loud-degrade carrier: it resolves every ticker
    to UNAVAILABLE so the flag pauses instead of silently permitting from an empty
    set.

    Unlike `HalalUniverse`, this is NOT a `frozenset` — it holds TWO exclusion sets
    (fossil, sin) plus the classified membership, and it is threaded through the
    safety floor as its own `classification_universe` param rather than substituting
    for the `halal_universe` seam.
    """

    __slots__ = ("fossil", "sin", "defense", "classified", "as_of", "source", "stale")

    def __init__(
        self,
        *,
        fossil=frozenset(),
        sin=frozenset(),
        defense=frozenset(),
        classified=frozenset(),
        as_of: date | None = None,
        source: str = SOURCE,
        stale: bool = False,
    ) -> None:
        up = lambda xs: frozenset(str(x).upper().strip() for x in xs)  # noqa: E731
        self.fossil = up(fossil)
        self.sin = up(sin)
        self.defense = up(defense)
        self.classified = up(classified)
        self.as_of = as_of
        self.source = source
        self.stale = stale

    @property
    def esg(self) -> frozenset:
        """The curated esg_lite exclusion set — fossil ∪ sin ∪ weapons/defense.
        Derived, so the three reviewable buckets stay the single source of truth."""
        return self.fossil | self.sin | self.defense

    def _excluded_for(self, ticker: str, kind: ClassificationKind) -> bool:
        if kind is ClassificationKind.FOSSIL_FUELS:
            return ticker in self.fossil
        if kind is ClassificationKind.SIN:
            return ticker in self.sin
        if kind is ClassificationKind.ESG_LITE:
            return ticker in self.esg
        return False

    def resolve(self, ticker: str, kind: ClassificationKind) -> ClassificationVerdict:
        """Resolve a ticker to one of the four states for a given exclusion kind."""
        t = ticker.upper().strip()
        if self.stale:
            status = ClassificationStatus.UNAVAILABLE
        elif self._excluded_for(t, kind):
            status = ClassificationStatus.EXCLUDED
        elif t in self.classified:
            status = ClassificationStatus.PERMITTED
        else:
            status = ClassificationStatus.UNKNOWN
        return ClassificationVerdict(
            status=status, ticker=t, kind=kind, source=self.source, as_of=self.as_of
        )


# ── Classifier (the pure, testable core) ─────────────────────────────────────


def _normalise_industry(raw: str | None) -> str:
    if not raw:
        return ""
    s = str(raw).lower().strip()
    for dash in ("—", "–", "−"):  # em-dash, en-dash, minus
        s = s.replace(dash, "-")
    s = " ".join(s.split())  # collapse internal whitespace
    # yfinance renders these as "Beverages - Brewers" (spaced hyphen), while the
    # pinned map uses the compact "beverages-brewers". Strip spaces around hyphens
    # so both forms match — without this, every alcohol name (STZ/TAP/BF-B) was
    # silently unscreened by no_tobacco_alcohol_gambling (DEF107). Fossil/defense
    # entries carry no hyphen, so this cannot affect them.
    return "-".join(p.strip() for p in s.split("-"))


def canonical_sector(raw: str | None) -> str | None:
    """The raw GICS sector string for the per-ticker sector map (CR026).

    yfinance already returns clean title-cased sector names ("Technology",
    "Consumer Defensive", "Financial Services", …); we only strip and collapse
    whitespace so the stored key is stable. Returns None for a missing/blank
    sector — the caller then leaves the ticker OUT of the sector map, so it
    resolves to "Other" (disclosed, never blocking — the DEF059 inversion guard).
    Pure — no network."""
    if not raw:
        return None
    s = " ".join(str(raw).split()).strip()
    return s or None


def classify_info(info: dict) -> tuple[bool, bool, bool]:
    """(is_fossil, is_sin, is_defense) for one yfinance `info` dict. Pure — no network.

    Fossil  = sector Energy AND industry in the pinned oil/gas/coal set.
    Sin     = industry in the pinned tobacco/alcohol/gambling set (sector-agnostic:
              casinos are Consumer Cyclical, tobacco is Consumer Defensive).
    Defense = industry in the pinned weapons/defense set (the curated esg_lite
              third bucket; esg = fossil ∪ sin ∪ defense, derived at resolve time)."""
    sector = _normalise_industry(info.get("sector"))
    industry = _normalise_industry(info.get("industry"))
    is_fossil = sector == _ENERGY_SECTOR and industry in _FOSSIL_INDUSTRIES
    is_sin = industry in _SIN_INDUSTRIES
    is_defense = industry in _DEFENSE_INDUSTRIES
    return is_fossil, is_sin, is_defense


def _parent_universe_to_classify() -> frozenset[str]:
    """The set of tickers to classify — the ~503 S&P parent constituents already
    persisted by CR075 in `sharia_universe_snapshots`. Reused, never re-fetched.

    Raises `ClassificationSourceError` when no Sharia snapshot exists yet (the
    parent set hasn't been seeded), so the refresh degrades loudly instead of
    classifying an empty universe."""
    with get_session() as session:
        row = latest_sharia_snapshot(session)
    if row is None or not row.parent:
        raise ClassificationSourceError(
            "no Sharia universe snapshot to source the parent constituent set from "
            "— the CR075 refresh must seed `sharia_universe_snapshots.parent` first"
        )
    return frozenset(str(t).upper().strip() for t in row.parent)


def _yf_info(ticker: str) -> dict:
    """One live yfinance `info` read. Isolated so the classify pass can try/except
    per ticker without importing yfinance at module scope (it's an optional dep,
    same as `fundamentals.py`)."""
    import yfinance as yf

    # Index constituent lists use a dot for class shares (BF.B, BRK.B); yfinance
    # keys them with a hyphen (BF-B). Normalise for the lookup ONLY — the caller
    # still keys results by the original symbol, so the stored set matches what the
    # sim/parent-set proposes (DEF108: BF.B / Brown-Forman was silently unscreened).
    return yf.Ticker(ticker.upper().replace(".", "-")).info or {}


def _network_classify(
    tickers,
    *,
    info_fetcher=None,
    throttle_s: float = _CLASSIFY_THROTTLE_S,
    sectors_out: dict[str, str] | None = None,
) -> tuple[frozenset, frozenset, frozenset, frozenset]:
    """Classify every ticker via yfinance → (classified, fossil, sin, defense).

    This is the ONLY place a socket opens; it runs inside the background refresh
    task (off the request path), never on a read. A ticker whose info read fails is
    simply left UNclassified (it resolves UNKNOWN=permitted+disclosed, the safe
    direction) — a failed name never becomes a false EXCLUDED or a false PERMITTED.

    `sectors_out` (CR026): when a dict is supplied, it is populated with the raw
    per-ticker GICS sector (`ticker → sector string`) for every classified name, so
    the same pass that derives fossil/sin also captures the sector map persisted for
    the concentration check + allocation donut. A side-channel out-param keeps the
    4-tuple return contract the DEF061 refresh + tests already depend on.

    Raises `ClassificationSourceError` if fewer than `_CLASSIFIED_MIN_ROWS` classify,
    so a throttled run that lost most calls is treated as broken (CR040) rather than
    stored as a short universe that would un-enforce the filter for most names."""
    info_fetcher = info_fetcher or _yf_info
    classified: set[str] = set()
    fossil: set[str] = set()
    sin: set[str] = set()
    defense: set[str] = set()
    failures = 0
    for i, t in enumerate(sorted(str(x).upper().strip() for x in tickers)):
        try:
            info = info_fetcher(t)
        except Exception as exc:  # noqa: BLE001 — any provider error → leave unclassified
            failures += 1
            logger.debug("classification_ticker_failed", ticker=t, error=str(exc)[:120])
            info = None
        if not info or not info.get("sector"):
            # No sector back ⇒ we didn't classify it. Do NOT add to `classified`.
            if info is not None:
                failures += 1
            if throttle_s and i + 1 < len(tickers):
                time.sleep(throttle_s)
            continue
        classified.add(t)
        if sectors_out is not None:
            sec = canonical_sector(info.get("sector"))
            if sec is not None:
                sectors_out[t] = sec
        is_fossil, is_sin, is_defense = classify_info(info)
        if is_fossil:
            fossil.add(t)
        if is_sin:
            sin.add(t)
        if is_defense:
            defense.add(t)
        if throttle_s and i + 1 < len(tickers):
            time.sleep(throttle_s)

    if len(classified) < _CLASSIFIED_MIN_ROWS:
        raise ClassificationSourceError(
            f"classified only {len(classified)} of {len(tickers)} parent names "
            f"(< floor {_CLASSIFIED_MIN_ROWS}, {failures} failures) — treating as a "
            f"throttled/broken run, refusing to store a short exclusion universe"
        )
    logger.info(
        "classification_pass_complete",
        classified=len(classified),
        fossil=len(fossil),
        sin=len(sin),
        defense=len(defense),
        failures=failures,
    )
    return frozenset(classified), frozenset(fossil), frozenset(sin), frozenset(defense)


# ── Snapshot storage (append-only) ───────────────────────────────────────────


def latest_snapshot(session) -> ClassificationUniverseSnapshotRow | None:
    """The most recently fetched classification snapshot row (append-only table,
    ordered by `fetched_at`). None when the table is empty (seed state)."""
    return session.execute(
        select(ClassificationUniverseSnapshotRow)
        .order_by(ClassificationUniverseSnapshotRow.fetched_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def latest_sector_map(session) -> dict[str, str]:
    """The per-ticker GICS sector map from the latest snapshot row (CR026).

    A cheap LOCAL DB read — NEVER a yfinance socket (the CR075/DEF089 rule). Empty
    dict when no row is stored yet (seed) or the row predates CR026; the caller then
    resolves every ticker to "Other" (disclosed, never blocking)."""
    row = latest_snapshot(session)
    if row is None or not row.sectors:
        return {}
    return {str(k).upper().strip(): str(v) for k, v in row.sectors.items()}


def write_snapshot(
    session, *, classified, fossil, sin, defense, fetched_at: datetime, sectors=None
) -> ClassificationUniverseSnapshotRow:
    """Append one snapshot row. Never updates or deletes — the history answers
    "which names did AMI treat as fossil/sin/defense on day X". `as_of` is set to the
    fetch date (yfinance carries no source date; our classify date is the honest
    freshness signal the reader gates on). The esg_lite set is derived (fossil ∪ sin
    ∪ defense), so only the three buckets are persisted.

    `sectors` (CR026): the per-ticker raw GICS sector map (ticker → sector string).
    Optional so pre-CR026 callers (and DEF061's fixture refresh) store an empty map;
    the request-path resolver treats an absent ticker as "Other"."""
    row = ClassificationUniverseSnapshotRow(
        source=SOURCE,
        as_of=fetched_at.date(),
        fetched_at=fetched_at,
        classified=sorted(str(t).upper().strip() for t in classified),
        fossil=sorted(str(t).upper().strip() for t in fossil),
        sin=sorted(str(t).upper().strip() for t in sin),
        defense=sorted(str(t).upper().strip() for t in defense),
        sectors={
            str(k).upper().strip(): str(v)
            for k, v in (sectors or {}).items()
            if v
        },
    )
    session.add(row)
    session.flush()
    return row


# ── Provider (cache + loud degrade) ──────────────────────────────────────────


def _is_stale(as_of: date | None, now: date, max_age_days: int) -> bool:
    if as_of is None:
        return True
    return (now - as_of).days > max_age_days


class ClassificationUniverseProvider:
    """Fetches, caches and staleness-guards the classification universe.

    `fetcher` is injectable so tests exercise the resolver + cache against a
    fixture and never touch the DB or the network. In production the fetcher is
    `_snapshot_fetcher` (a cheap LOCAL read of the latest stored row), so the read
    path never opens a socket. Staleness is re-derived on every `get()` (pure
    arithmetic) — same fetch-once-then-recheck lifecycle as the Sharia provider's
    F2 fix, so a container that booted with a fresh row still notices it ageing out
    of the hold window without a restart."""

    def __init__(
        self,
        *,
        hold_window_days: int,
        enabled: bool,
        fetcher=None,
        refetch_interval_s: float = _ROW_READ_REFETCH_S,
    ) -> None:
        self._hold_window_days = hold_window_days
        self._enabled = enabled
        self._fetcher = fetcher or _snapshot_fetcher
        self._refetch_interval_s = refetch_interval_s
        self._cache: ClassificationUniverse | None = None
        self._last_attempt: float | None = None

    def _paused(self, as_of: date | None = None) -> ClassificationUniverse:
        return ClassificationUniverse(as_of=as_of, stale=True)

    def _build(self, now: date | None = None) -> ClassificationUniverse:
        now = now or datetime.now(timezone.utc).date()
        if not self._enabled:
            logger.info("classification_universe_disabled")
            return self._paused()
        try:
            classified, fossil, sin, defense, as_of = self._fetcher()
        except ClassificationSourceError as exc:
            logger.error("classification_universe_fetch_failed", error=str(exc))
            return self._paused()
        if _is_stale(as_of, now, self._hold_window_days):
            logger.error(
                "classification_universe_stale",
                as_of=as_of.isoformat() if as_of else None,
                max_age_days=self._hold_window_days,
            )
            return self._paused(as_of=as_of)
        logger.info(
            "classification_universe_loaded",
            classified=len(classified),
            fossil=len(fossil),
            sin=len(sin),
            defense=len(defense),
            as_of=as_of.isoformat() if as_of else None,
        )
        return ClassificationUniverse(
            fossil=fossil, sin=sin, defense=defense, classified=classified, as_of=as_of
        )

    def _refetch_due(self) -> bool:
        if self._last_attempt is None:
            return True
        return (time.monotonic() - self._last_attempt) >= self._refetch_interval_s

    def get(
        self, *, refresh: bool = False, now: date | None = None
    ) -> ClassificationUniverse:
        now = now or datetime.now(timezone.utc).date()
        if self._cache is None or refresh or self._refetch_due():
            self._last_attempt = time.monotonic()
            self._cache = self._build(now=now)
            return self._cache
        if not self._cache.stale and _is_stale(
            self._cache.as_of, now, self._hold_window_days
        ):
            logger.error(
                "classification_universe_stale",
                as_of=self._cache.as_of.isoformat() if self._cache.as_of else None,
                max_age_days=self._hold_window_days,
            )
            return self._paused(as_of=self._cache.as_of)
        return self._cache


# ── Read path (resolve from the stored row, never a socket) ──────────────────


def _snapshot_fetcher() -> tuple[frozenset, frozenset, frozenset, frozenset, date | None]:
    """The production read-path 'fetcher' — a cheap LOCAL DB read of the latest
    stored snapshot, NOT a network call. Empty table ⇒ raises (seed path; the daily
    refresh hasn't written a row), which the provider converts into a loudly-paused
    (UNAVAILABLE) universe."""
    with get_session() as session:
        row = latest_snapshot(session)
    if row is None:
        raise ClassificationSourceError(
            "no classification snapshot stored yet — seed pending "
            "(the daily refresh has not yet written a row)"
        )
    return (
        frozenset(row.classified),
        frozenset(row.fossil),
        frozenset(row.sin),
        frozenset(row.defense or []),
        row.as_of,
    )


_provider: ClassificationUniverseProvider | None = None


def get_classification_universe_provider() -> ClassificationUniverseProvider:
    """Process-wide singleton, built from config on first use. The fetcher is
    `_snapshot_fetcher` (a local read of the stored row) and the window is
    `classification_hold_window_days`, so every request resolves from persisted
    data with no socket. The network classify pass lives in
    `run_classification_refresh_tick()`, off the request path."""
    global _provider
    if _provider is None:
        _provider = ClassificationUniverseProvider(
            hold_window_days=settings.classification_hold_window_days,
            enabled=settings.classification_screen_enabled,
        )
    return _provider


def reset_classification_universe_provider(
    provider: ClassificationUniverseProvider | None = None,
) -> None:
    """Test seam — swap or clear the singleton."""
    global _provider
    _provider = provider


def default_classification_universe() -> ClassificationUniverse:
    """The sourced classification universe for callers that don't pass one.

    Resolves from the latest stored snapshot row — a cheap local DB read, NEVER a
    network fetch. Synchronous contexts only; anything on the event loop uses
    `default_classification_universe_async()`.

    When the feature is disabled, the universe has never been classified (seed), or
    the held row has aged past its window, returns a paused universe so both flags
    degrade loudly instead of enforcing (or un-enforcing) a stale/empty set."""
    return get_classification_universe_provider().get()


async def default_classification_universe_async() -> ClassificationUniverse:
    """Event-loop-safe accessor — the local DB read stays off the loop via
    `asyncio.to_thread` (the one uvicorn process serves every concurrent request)."""
    return await asyncio.to_thread(get_classification_universe_provider().get)


# ── Background refresh (the ONLY socket; degrade loudly on the refresher) ─────

_consecutive_refresh_failures = 0
_REFRESH_FAILURE_LOUD_THRESHOLD = 3


def consecutive_refresh_failures() -> int:
    return _consecutive_refresh_failures


def reset_refresh_failures() -> None:
    global _consecutive_refresh_failures
    _consecutive_refresh_failures = 0


def _record_refresh_failure(exc: Exception) -> None:
    global _consecutive_refresh_failures
    _consecutive_refresh_failures += 1
    logger.error(
        "classification_refresh_failed",
        error=str(exc),
        consecutive_failures=_consecutive_refresh_failures,
    )
    if _consecutive_refresh_failures >= _REFRESH_FAILURE_LOUD_THRESHOLD:
        logger.error(
            "classification_refresh_failing_repeatedly",
            consecutive_failures=_consecutive_refresh_failures,
            threshold=_REFRESH_FAILURE_LOUD_THRESHOLD,
        )


def _snapshot_is_fresh(
    row: ClassificationUniverseSnapshotRow, now: datetime
) -> bool:
    fetched = row.fetched_at
    if fetched.tzinfo is None:  # sqlite round-trips naive; treat as UTC
        fetched = fetched.replace(tzinfo=timezone.utc)
    return (now - fetched).total_seconds() < _SNAPSHOT_FRESH_WINDOW_S


def run_classification_refresh_tick(
    *,
    classifier=None,
    now: datetime | None = None,
    force: bool = False,
    enabled: bool | None = None,
) -> str:
    """One refresh cycle: classify the parent set over the network and, unless a
    fresh row is already stored, append a snapshot row (append-only). Returns a
    status string: `disabled` | `skipped_fresh` | `stored` | `fetch_failed`.

    Idempotent (mirrors `run_sharia_refresh_tick`): a tick that finds a fresh
    stored row does nothing, so a restart shortly after a run never re-classifies.
    Degrades loudly on the REFRESHER: a failed classify pass bumps the
    consecutive-failure counter and logs, but leaves the held row untouched so the
    reader keeps serving it. The classify pass is the ONLY socket in this feature.

    `classifier` is injectable (tests pass a fixture classifier); the default reads
    the parent set from the Sharia snapshot and classifies each name via yfinance."""
    now = now or datetime.now(timezone.utc)
    enabled = settings.classification_screen_enabled if enabled is None else enabled
    if not enabled:
        logger.info("classification_refresh_skipped_disabled")
        return "disabled"

    if not force:
        with get_session() as session:
            latest = latest_snapshot(session)
        if latest is not None and _snapshot_is_fresh(latest, now):
            logger.info(
                "classification_refresh_skipped_fresh",
                fetched_at=latest.fetched_at.isoformat(),
            )
            return "skipped_fresh"

    # CR026: the default classify pass captures the per-ticker sector map via the
    # `sectors_out` side-channel (same 4-tuple return DEF061 depends on). An injected
    # fixture classifier stores an empty map — its tests assert only fossil/sin.
    sectors: dict[str, str] = {}
    classify = classifier or (
        lambda: _network_classify(_parent_universe_to_classify(), sectors_out=sectors)
    )
    try:
        classified, fossil, sin, defense = classify()
    except Exception as exc:  # ClassificationSourceError, yfinance errors, anything
        _record_refresh_failure(exc)
        return "fetch_failed"

    with get_session() as session:
        write_snapshot(
            session,
            classified=classified,
            fossil=fossil,
            sin=sin,
            defense=defense,
            fetched_at=now,
            sectors=sectors,
        )
    reset_refresh_failures()
    logger.info(
        "classification_refresh_stored",
        classified=len(classified),
        fossil=len(fossil),
        sin=len(sin),
        defense=len(defense),
        sectors=len(sectors),
        fetched_at=now.isoformat(),
    )
    return "stored"
