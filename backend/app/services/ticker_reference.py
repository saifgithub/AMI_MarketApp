"""Ticker existence reference — fetcher, store and suggestion resolver (CR128).

None of the three ticker-entry points (Convene the Room, Start Trade, Add to
Watchlist) validated that a typed ticker actually existed. Verified before
building this: the trade path's `current_quote()` is built to never fail (it
falls through to `MockWalkProvider`, which fabricates a plausible price from
`hash(ticker)`), and Room convene charges credits + paid feed quota
(`_resolve_and_charge_feeds`) before any agent speaks — a garbage ticker ran a
full fake 12-agent debate and spent real money on nothing.

Source: NASDAQ Trader's public, no-auth symbol-directory files —
`nasdaqlisted.txt` (NASDAQ-listed) + `otherlisted.txt` (NYSE/NYSE American/NYSE
Arca/Cboe-listed) — together ~13k US-listed symbols including ETFs. Chosen over
CR075's Sharia `parent` set (only ~503 S&P-500 tickers — would false-reject real
tickers) and over live yfinance (no bulk/list API exists at all) and over
Alpaca's `/v2/assets` (would need a brand-new app-level credential; this needs
none).

One row per symbol (`TickerReferenceRow`), unlike the Sharia/classification
snapshot tables' append-only-blob shape — existence checks need an O(1) point
lookup, not a scan. The daily `_ticker_reference_refresh()` background task
(wired in `main.py`, same pattern as `_sharia_universe_refresh()`) marks every
row inactive then reactivates everything the fresh fetch returns, so a symbol
missing from the latest fetch is soft-deleted (`is_active = False`), never hard
-deleted — a delisting or a transient source hiccup must not make a
previously-valid ticker silently vanish. A failed fetch leaves the held table
untouched (degrade loudly on the refresher, not the reader — same convention as
CR075).
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, update

from app.core.config import settings
from app.core.logging import logger
from app.db import get_session
from app.db.models import TickerReferenceRow
from app.schemas.tickers import TickerSuggestion

# ── Parsing ──────────────────────────────────────────────────────────────────

# otherlisted.txt's single-letter Exchange code → a name worth showing in a
# confirmation dialog. Codes observed live 2026-07-31; an unrecognised code
# falls back to the raw code rather than raising — a listing on an exchange
# this map doesn't yet know about should still exist, just with a plainer label.
_OTHER_EXCHANGE_NAMES = {
    "A": "NYSE American",
    "N": "NYSE",
    "P": "NYSE Arca",
    "Z": "Cboe BZX",
    "V": "IEX",
}

# Truncation floors, same purpose as `sharia_universe.py`'s `_SPUS_MIN_ROWS` /
# `_PARENT_MIN_ROWS`: a body that parses to far fewer rows than expected is
# corrupt or truncated, not a genuinely shrunk universe — refuse to overwrite
# the held table with it. Measured live 2026-07-31: nasdaqlisted.txt ≈ 5.5k rows
# (~5.5k real symbols after dropping test issues), otherlisted.txt ≈ 7.5k rows
# (~7.5k real). Floors sit with generous headroom below both.
_LISTED_MIN_ROWS = 4000
_OTHER_MIN_ROWS = 5000

_FETCH_TIMEOUT_S = 15.0
_USER_AGENT = "AMI-Trade/1.0 (+https://agenticmarketintel.ai)"


class TickerReferenceSourceError(RuntimeError):
    """A listed-securities file is missing, truncated, or otherwise unusable.

    Callers must not swallow this into a partial overwrite — the refresh tick
    converts it into a logged failure and leaves the held table untouched."""


def _parse_symbol_file(
    text: str, *, required_cols: tuple[str, ...],
) -> tuple[list[str], dict[str, int]]:
    lines = text.splitlines()
    if not lines:
        raise TickerReferenceSourceError("empty listed-securities file")
    header = lines[0].split("|")
    idx = {c: i for i, c in enumerate(header)}
    if not all(c in idx for c in required_cols):
        raise TickerReferenceSourceError(
            f"listed-securities file missing expected columns {required_cols}: {header}"
        )
    return lines, idx


def parse_nasdaq_listed(text: str) -> list[dict]:
    """Parse `nasdaqlisted.txt` — pipe-delimited, footer line
    `File Creation Time: ...`. Drops NASDAQ's own `Test Issue = Y` rows (IEX/
    NASDAQ test symbols, not real tickers)."""
    required = ("Symbol", "Security Name", "Test Issue", "ETF")
    lines, idx = _parse_symbol_file(text, required_cols=required)
    records: list[dict] = []
    for line in lines[1:]:
        if not line or line.startswith("File Creation Time"):
            continue
        cols = line.split("|")
        if len(cols) < len(idx) or cols[idx["Test Issue"]].strip() == "Y":
            continue
        symbol = cols[idx["Symbol"]].strip().upper()
        if not symbol:
            continue
        records.append({
            "symbol": symbol,
            "company_name": cols[idx["Security Name"]].strip(),
            "exchange": "NASDAQ",
            "is_etf": cols[idx["ETF"]].strip() == "Y",
        })
    return records


def parse_nasdaq_other(text: str) -> list[dict]:
    """Parse `otherlisted.txt` — NYSE/AMEX/Arca/Cboe-listed symbols, keyed by
    NASDAQ Trader's own `ACT Symbol` column (not the `NASDAQ Symbol` column,
    which is a compatibility alias)."""
    required = ("ACT Symbol", "Security Name", "Exchange", "Test Issue", "ETF")
    lines, idx = _parse_symbol_file(text, required_cols=required)
    records: list[dict] = []
    for line in lines[1:]:
        if not line or line.startswith("File Creation Time"):
            continue
        cols = line.split("|")
        if len(cols) < len(idx) or cols[idx["Test Issue"]].strip() == "Y":
            continue
        symbol = cols[idx["ACT Symbol"]].strip().upper()
        if not symbol:
            continue
        exch_code = cols[idx["Exchange"]].strip()
        records.append({
            "symbol": symbol,
            "company_name": cols[idx["Security Name"]].strip(),
            "exchange": _OTHER_EXCHANGE_NAMES.get(exch_code, exch_code or "Unknown"),
            "is_etf": cols[idx["ETF"]].strip() == "Y",
        })
    return records


def _fetch_text(client: httpx.Client, url: str) -> str:
    resp = client.get(url)
    resp.raise_for_status()
    return resp.text


def fetch_listed_universe(client: httpx.Client, url: str) -> list[dict]:
    records = parse_nasdaq_listed(_fetch_text(client, url))
    if len(records) < _LISTED_MIN_ROWS:
        raise TickerReferenceSourceError(
            f"nasdaqlisted.txt parsed to {len(records)} symbols "
            f"(< floor {_LISTED_MIN_ROWS}) — treating as truncated"
        )
    return records


def fetch_other_universe(client: httpx.Client, url: str) -> list[dict]:
    records = parse_nasdaq_other(_fetch_text(client, url))
    if len(records) < _OTHER_MIN_ROWS:
        raise TickerReferenceSourceError(
            f"otherlisted.txt parsed to {len(records)} symbols "
            f"(< floor {_OTHER_MIN_ROWS}) — treating as truncated"
        )
    return records


def _network_fetch(listed_url: str, other_url: str) -> list[dict]:
    """Two real httpx round-trips. This is the ONLY place a socket opens; it
    runs inside the background refresh task, off the request path."""
    with httpx.Client(timeout=_FETCH_TIMEOUT_S, headers={"User-Agent": _USER_AGENT}) as client:
        listed = fetch_listed_universe(client, listed_url)
        other = fetch_other_universe(client, other_url)
    return listed + other


# ── Storage (one row per symbol, soft-delete on absence) ────────────────────


def upsert_reference(session, records: list[dict], now: datetime) -> dict:
    """Mark every existing row inactive, then reactivate everything in
    `records`. A symbol absent from `records` (delisted, or a source hiccup
    that dropped it) ends this call with `is_active = False` — soft-deleted,
    row kept. Runs inside one transaction (the caller's `get_session()` block),
    so concurrent readers see either the fully-old or fully-new state, never a
    transient all-inactive gap."""
    session.execute(update(TickerReferenceRow).values(is_active=False))
    seen: set[str] = set()
    upserted = 0
    for rec in records:
        symbol = rec["symbol"]
        if symbol in seen:
            continue
        seen.add(symbol)
        upserted += 1
        row = session.get(TickerReferenceRow, symbol)
        if row is None:
            session.add(TickerReferenceRow(
                symbol=symbol,
                company_name=rec["company_name"],
                exchange=rec["exchange"],
                is_etf=rec["is_etf"],
                is_active=True,
                last_seen_at=now,
            ))
        else:
            row.company_name = rec["company_name"]
            row.exchange = rec["exchange"]
            row.is_etf = rec["is_etf"]
            row.is_active = True
            row.last_seen_at = now
    session.flush()
    deactivated = session.execute(
        select(TickerReferenceRow.symbol).where(TickerReferenceRow.is_active.is_(False))
    ).scalars().all()
    return {"upserted": upserted, "deactivated": len(deactivated)}


def _latest_refresh_at(session) -> datetime | None:
    return session.execute(
        select(TickerReferenceRow.last_seen_at)
        .where(TickerReferenceRow.is_active.is_(True))
        .order_by(TickerReferenceRow.last_seen_at.desc())
        .limit(1)
    ).scalar_one_or_none()


# A stored refresh younger than this counts as "already refreshed today" —
# same idempotency guard as `_sharia_universe_refresh`, so a restart shortly
# after a fetch does not re-hit the network.
_REFRESH_FRESH_WINDOW_S = 20 * 60 * 60  # 20h

# Degrade-loudly-on-the-refresher: once the fetch has failed this many times
# in a row, emit a distinct loud signal on top of the per-failure log — the
# held table is still served, so nothing is visibly wrong to a user, but a
# source dead for days should not be invisible to us.
_REFRESH_FAILURE_LOUD_THRESHOLD = 3

_consecutive_refresh_failures = 0


def consecutive_refresh_failures() -> int:
    return _consecutive_refresh_failures


def reset_refresh_failures() -> None:
    global _consecutive_refresh_failures
    _consecutive_refresh_failures = 0


def _record_refresh_failure(exc: Exception) -> None:
    global _consecutive_refresh_failures
    _consecutive_refresh_failures += 1
    logger.error(
        "ticker_reference_refresh_failed",
        error=str(exc),
        consecutive_failures=_consecutive_refresh_failures,
    )
    if _consecutive_refresh_failures >= _REFRESH_FAILURE_LOUD_THRESHOLD:
        logger.error(
            "ticker_reference_refresh_failing_repeatedly",
            consecutive_failures=_consecutive_refresh_failures,
            threshold=_REFRESH_FAILURE_LOUD_THRESHOLD,
        )


def run_ticker_reference_refresh_tick(
    *, fetcher=None, now: datetime | None = None, force: bool = False,
) -> str:
    """One refresh cycle. Returns `skipped_fresh` | `stored` | `fetch_failed`.

    Idempotent: a tick that finds a refresh already stored within the fresh
    window does nothing. A failed fetch leaves the held table untouched — the
    reader keeps serving it, soft-deletion only happens on a SUCCESSFUL fetch
    that genuinely omits a symbol, never on a fetch failure."""
    now = now or datetime.now(timezone.utc)
    if not force:
        with get_session() as session:
            latest = _latest_refresh_at(session)
        if latest is not None:
            if latest.tzinfo is None:  # sqlite round-trips naive; treat as UTC
                latest = latest.replace(tzinfo=timezone.utc)
            if (now - latest).total_seconds() < _REFRESH_FRESH_WINDOW_S:
                logger.info(
                    "ticker_reference_refresh_skipped_fresh",
                    last_seen_at=latest.isoformat(),
                )
                return "skipped_fresh"

    fetch = fetcher or (
        lambda: _network_fetch(
            settings.ticker_reference_nasdaq_listed_url,
            settings.ticker_reference_nasdaq_other_url,
        )
    )
    try:
        records = fetch()
    except Exception as exc:  # httpx.HTTPError, TickerReferenceSourceError, anything
        _record_refresh_failure(exc)
        return "fetch_failed"

    with get_session() as session:
        counts = upsert_reference(session, records, now)
    reset_refresh_failures()
    _invalidate_active_symbol_cache()
    logger.info("ticker_reference_refresh_stored", fetched_at=now.isoformat(), **counts)
    return "stored"


# ── Read path: exact lookup + closest-match suggestion ──────────────────────

# In-process cache of (symbol, company_name) for `suggest_closest` — fuzzy
# matching has no SQL equivalent, and re-listing ~13k rows on every miss is
# wasted work. TTL, not tied to the refresh tick, so a fresh refresh is picked
# up within minutes without the reader and refresher coordinating directly.
_ACTIVE_SYMBOLS_CACHE_TTL_S = 300.0

_active_rows_cache: list[tuple[str, str]] | None = None
_active_rows_cached_at: float | None = None


def _invalidate_active_symbol_cache() -> None:
    global _active_rows_cache, _active_rows_cached_at
    _active_rows_cache = None
    _active_rows_cached_at = None


def _active_rows(session) -> list[tuple[str, str]]:
    """(symbol, NORMALIZED company name) for every active row, in-process
    cached. Normalizing at cache-fill rather than per query matters: it is
    ~13k regex substitutions, which measured ~77ms per lookup when done on
    every call and ~1ms from the primed cache."""
    global _active_rows_cache, _active_rows_cached_at
    now = time.monotonic()
    if (
        _active_rows_cache is not None
        and _active_rows_cached_at is not None
        and (now - _active_rows_cached_at) < _ACTIVE_SYMBOLS_CACHE_TTL_S
    ):
        return _active_rows_cache
    rows = session.execute(
        select(TickerReferenceRow.symbol, TickerReferenceRow.company_name)
        .where(TickerReferenceRow.is_active.is_(True))
    ).all()
    _active_rows_cache = [(s, _normalize_name(c)) for s, c in rows]
    _active_rows_cached_at = now
    return _active_rows_cache


def lookup_ticker(session, symbol: str) -> TickerReferenceRow | None:
    """Exact-match lookup. Returns None for an unknown OR soft-deleted symbol —
    callers don't need to distinguish "never listed" from "delisted"."""
    symbol = symbol.upper().strip()
    if not symbol:
        return None
    row = session.get(TickerReferenceRow, symbol)
    if row is not None and row.is_active:
        return row
    return None


def _edit_distance(a: str, b: str) -> int:
    """Plain Levenshtein distance (stdlib only, no new dependency)."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * lb
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[lb]


# Loosest symbol typo tolerated. Tried difflib.get_close_matches first
# (stdlib, ratio-based) but it ranks "AAPLE" -> "APLE" ahead of the
# obviously-intended "AAPL" — a character-overlap ratio doesn't weight a
# single-edit typo highly enough.
_MAX_SUGGEST_DISTANCE = 2

# Boilerplate that follows the actual company name in NASDAQ Trader's
# `Security Name` column ("Netflix, Inc. - Common Stock"). Stripped before
# matching so a typed company name compares against the name a human would
# recognise, not against the share-class tail.
_NAME_NOISE = re.compile(
    r"\s*(-\s*)?\b("
    r"common stock|common shares|ordinary shares|class [a-z]|"
    r"american depositary shares?|depositary shares?|"
    r"warrants?|rights?|units?|notes?|preferred|series [a-z]|"
    r"inc|incorporated|corp|corporation|company|co|ltd|limited|plc|"
    r"holdings?|group|s\.?a\.?|n\.?v\.?|the"
    r")\b\.?,?",
    re.IGNORECASE,
)


def _normalize_name(name: str) -> str:
    """"Netflix, Inc. - Common Stock" -> "NETFLIX"."""
    cleaned = _NAME_NOISE.sub(" ", name)
    return re.sub(r"[^A-Z0-9 ]", " ", cleaned.upper()).strip()


def suggest_closest(session, symbol: str, limit: int = 1) -> list[TickerReferenceRow]:
    """Best active match(es) for what the user typed.

    DEF207: symbol edit-distance alone was the wrong model. Users type COMPANY
    NAMES ("NETFLIX", "TESLA"), not near-miss symbols, and against the live
    13k-row table that produced no suggestion for NETFLIX (distance to NFLX is
    3) and actively wrong ones for TESLA -> ESLA and APPLE -> APLE (Apple
    Hospitality REIT). So the name column is searched too, and a name hit
    outranks a symbol typo — "TESLA" resolving to Estrella Immunopharma
    because five of six letters line up is worse than no suggestion at all.

    Tiers, best first:
      0. normalized company name == query           NETFLIX -> NFLX
      1. company name starts with query             APPLE   -> AAPL
      2. symbol is one edit away                    AAPLE   -> AAPL
      3. company name contains query as a word      -
      4. symbol is two edits away                   -

    Within a tier: shorter normalized name first (so "Apple Inc." beats
    "Apple Hospitality REIT"), then shorter symbol, then alphabetical — a
    total order, so the same query always returns the same suggestion.
    Empty list when nothing qualifies; callers show a plain "not found"
    rather than a low-confidence guess."""
    query = symbol.upper().strip()
    if not query:
        return []
    scored: list[tuple[int, int, int, str]] = []
    for sym, norm in _active_rows(session):
        tier = None
        if norm == query:
            tier = 0
        elif norm.startswith(query):
            tier = 1
        elif abs(len(sym) - len(query)) <= _MAX_SUGGEST_DISTANCE and (
            _edit_distance(query, sym) == 1
        ):
            tier = 2
        elif query in norm.split():
            tier = 3
        elif abs(len(sym) - len(query)) <= _MAX_SUGGEST_DISTANCE and (
            _edit_distance(query, sym) <= _MAX_SUGGEST_DISTANCE
        ):
            tier = 4
        if tier is not None:
            scored.append((tier, len(norm), len(sym), sym))
    scored.sort()
    rows = []
    for _, _, _, sym in scored[:limit]:
        row = session.get(TickerReferenceRow, sym)
        if row is not None:
            rows.append(row)
    return rows


class TickerNotFoundError(ValueError):
    """Raised by `require_ticker_exists` — the guard inside the three action
    endpoints (Room convene, trade preview/submit, watchlist add). Carries the
    nearest suggestion (if any) as a plain `TickerSuggestion`, NOT the
    `TickerReferenceRow` ORM object — this is routinely raised inside a
    `with get_session():` block and caught outside it (the route's except
    clause), by which point an attached ORM row would be detached and any
    attribute access would raise `DetachedInstanceError`. Extracting plain
    values here, while the session is still open, is what the route can
    safely read later to build the structured 422 body — the same shape
    `GET /v1/tickers/validate` returns.

    The client is expected to have already called the validate endpoint
    before submitting, so this only fires for a stale client or a direct API
    call — defense in depth (CR128), not the primary UX path."""

    def __init__(self, ticker: str, suggestion: TickerSuggestion | None = None) -> None:
        self.ticker = ticker
        self.suggestion = suggestion
        super().__init__(f"ticker not found: {ticker}")


def require_ticker_exists(session, ticker: str) -> None:
    """Raise `TickerNotFoundError` unless `ticker` is a known active symbol."""
    ticker = ticker.upper().strip()
    if lookup_ticker(session, ticker) is not None:
        return
    candidates = suggest_closest(session, ticker, limit=1)
    suggestion = None
    if candidates:
        row = candidates[0]
        suggestion = TickerSuggestion(
            ticker=row.symbol, company_name=row.company_name, exchange=row.exchange,
        )
    raise TickerNotFoundError(ticker, suggestion)


def ticker_not_found_detail(exc: TickerNotFoundError) -> dict:
    """The 422 `detail` body for a `TickerNotFoundError` — same shape as
    `GET /v1/tickers/validate`'s response, so a client that somehow reaches
    this guard (rather than the validate endpoint) can render the same "did
    you mean X" confirmation instead of a bare error string."""
    from app.schemas.tickers import TickerValidateResponse

    return TickerValidateResponse(
        ticker=exc.ticker, exists=False, suggestion=exc.suggestion,
    ).model_dump(mode="json")
