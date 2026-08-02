"""Daily price-history store (CR136 M01) — read-through table over the
market-data provider, plus the deterministic bad-print detector; the Tier-1
engine's only source of return series.

Why this exists rather than a call to `get_market_data_provider()`:

1. **Window.** Portfolio Health needs ≥126 daily returns per holding. Before
   CR136 the layer served daily bars only via `"1m"` (22) and `"3m"` (65), so
   every Tier-1 metric read insufficient for every user. M01 adds a `"2y"`
   daily period (~504 bars) and persists what it fetches.

2. **Fan-out.** No batch primitive exists — `YfinanceProvider.history` is
   single-ticker. Without a table, an N-holding evaluation is N Yahoo
   round-trips *every* time the card opens, and the quote path's 60-second
   `CachingProvider` TTL is far too short to amortise that. The table does.

3. **Provenance (CR040).** `get_market_data_provider()` returns
   `FallbackProvider(cache(yfinance) → mock_walk)`. Persisting through that
   stack means one transient yfinance failure silently writes *fabricated*
   mock bars into the analytic history and every covariance downstream is
   computed on invented data, forever, with nothing to show it happened. So
   this module resolves its own leaf provider, stamps every row with the leaf
   that produced it, and — in real mode — refuses to read mock rows back. A
   missing provider means short series and a loud, visible "insufficient data"
   downstream, never a quiet fabrication. The quote/chart path is untouched.

Trading days are derived from which bars exist (weekends and holidays are
absences, not calendar arithmetic) — CR136 imports no trading calendar
anywhere, so the stored rows *are* the calendar.

Detection here is report-only: `detect_bad_print_days` flags, and M04 decides.
This module never repairs, drops, or edits a row on quality grounds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.db import get_session
from app.db.models import PriceHistoryDailyRow
from app.services.market_data import (
    Candle,
    MarketDataProvider,
    MockWalkProvider,
    YfinanceProvider,
)
from app.services.portfolio_health_constants import (
    BAD_PRINT_HARD_ABS_RETURN,
    BAD_PRINT_REVERSAL_MIN_FRACTION,
    BAD_PRINT_SPIKE_ABS_RETURN,
    BENCHMARK_TICKER,
    HISTORY_FETCH_PERIOD,
    HISTORY_MAX_ROWS,
)

# Per-ticker provider-fetch throttle. Daily bars change once per trading day,
# so re-asking inside this window can only return what we already stored.
# Convention, following `ticker_reference._REFRESH_FRESH_WINDOW_S`.
_FETCH_FRESH_WINDOW_S = 6 * 3600

# The leaf-provider name that marks a row as fabricated. Real-mode reads
# exclude it; real fetches upsert over it.
_MOCK_SOURCE = "mock_walk"


# ── Provider access ─────────────────────────────────────────────────────────

_history_provider: MarketDataProvider | None = None


def set_history_provider(provider: MarketDataProvider | None) -> None:
    """Replace the leaf provider. Test hook, mirroring
    `market_data.set_market_data_provider`; safe to call with None to reset."""
    global _history_provider
    _history_provider = provider


def _leaf_provider() -> MarketDataProvider | None:
    """The single leaf provider this module fetches through — never the
    fallback stack (see the module docstring's point 3).

    Real mode with yfinance unavailable returns None rather than degrading to
    the keyless Yahoo path (whose `history()` returns None anyway) or to the
    mock walk (which would fabricate). The caller serves whatever is already
    stored and logs the failure."""
    if _history_provider is not None:
        return _history_provider
    if settings.use_real_market_data:
        try:
            return YfinanceProvider()
        except ImportError as exc:
            logger.error("price_history_provider_unavailable", error=str(exc))
            return None
    return MockWalkProvider()


# ── Series shape ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DailySeries:
    """One ticker's stored daily history, ascending by trading day.

    `dates`, `adj_closes` and `closes` are index-aligned and equal in length.
    `sources` is every distinct leaf provider represented in the served rows —
    M04's belt-and-braces provenance check beside its own mock-mode refusal.

    `fetched_at` is the NEWEST stamp across the served rows, not the stamp of
    the newest bar. It answers "when did we last ask the provider about this
    ticker", which is the question the fetch throttle needs; the stamp on the
    last bar answers a different one and would let a series whose tail is a
    stale row re-fetch on every call.
    """

    ticker: str
    dates: list[date]
    adj_closes: list[float]
    closes: list[float]
    sources: tuple[str, ...]
    fetched_at: datetime | None


def _empty_series(ticker: str) -> DailySeries:
    return DailySeries(
        ticker=ticker, dates=[], adj_closes=[], closes=[], sources=(), fetched_at=None,
    )


# ── Storage ─────────────────────────────────────────────────────────────────


def _as_utc(stamp: datetime | None) -> datetime | None:
    """sqlite round-trips naive datetimes; treat naive as UTC (same guard as
    `ticker_reference.run_ticker_reference_refresh_tick`)."""
    if stamp is None:
        return None
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=timezone.utc)
    return stamp


def _load_rows(session, ticker: str, *, real_mode: bool) -> list[PriceHistoryDailyRow]:
    """Trailing `HISTORY_MAX_ROWS` rows for `ticker`, ascending by date."""
    stmt = select(PriceHistoryDailyRow).where(PriceHistoryDailyRow.ticker == ticker)
    if real_mode:
        stmt = stmt.where(PriceHistoryDailyRow.source != _MOCK_SOURCE)
    stmt = stmt.order_by(PriceHistoryDailyRow.date.desc()).limit(HISTORY_MAX_ROWS)
    return list(reversed(session.execute(stmt).scalars().all()))


def upsert_daily_bars(
    session,
    ticker: str,
    bars: list[tuple[date, float]],
    *,
    source: str,
    now: datetime,
) -> dict:
    """Insert-or-update `(ticker, date)` rows. Returns `{"inserted", "updated"}`.

    Existing rows are UPDATED, never skipped: a dividend or split rewrites the
    whole trailing adjusted series at the provider, so skip-if-exists would
    freeze stale values into every covariance computed afterwards.

    Runs in the caller's session/transaction. Insert-or-update by reading the
    affected dates into a dict first — portable across sqlite and Postgres,
    no dialect-specific ON CONFLICT.
    """
    t = ticker.upper().strip()
    by_date: dict[date, float] = {}
    for bar_date, price in bars:
        by_date[bar_date] = float(price)
    if not by_date:
        return {"inserted": 0, "updated": 0}

    existing = {
        row.date: row
        for row in session.execute(
            select(PriceHistoryDailyRow).where(
                PriceHistoryDailyRow.ticker == t,
                PriceHistoryDailyRow.date.in_(list(by_date)),
            )
        ).scalars()
    }

    inserted = 0
    updated = 0
    for bar_date, price in by_date.items():
        row = existing.get(bar_date)
        if row is None:
            session.add(PriceHistoryDailyRow(
                ticker=t,
                date=bar_date,
                close=price,
                adj_close=price,
                source=source,
                fetched_at=now,
            ))
            inserted += 1
        else:
            row.close = price
            row.adj_close = price
            row.source = source
            row.fetched_at = now
            updated += 1
    session.flush()
    return {"inserted": inserted, "updated": updated}


# ── Read-through ────────────────────────────────────────────────────────────


def _candles_to_bars(candles: Sequence[Candle]) -> list[tuple[date, float]]:
    """Trading date + close per candle, later bars winning a duplicate date.

    `Candle.t` is epoch seconds UTC. yfinance stamps a daily bar at midnight
    exchange-tz (or naive midnight), so the UTC date equals the exchange
    trading date either way. Weekends and holidays exist only as absent bars.
    """
    by_date: dict[date, float] = {}
    for candle in candles:
        bar_date = datetime.fromtimestamp(candle.t, timezone.utc).date()
        by_date[bar_date] = float(candle.c)
    return sorted(by_date.items())


def _build_series(ticker: str, rows: list[PriceHistoryDailyRow]) -> DailySeries:
    if not rows:
        return _empty_series(ticker)
    stamps = [s for s in (_as_utc(r.fetched_at) for r in rows) if s is not None]
    return DailySeries(
        ticker=ticker,
        dates=[r.date for r in rows],
        # Postgres round-trips Numeric as Decimal; sqlite hides this. Cast, or
        # every downstream float op raises on a Decimal/float mix.
        adj_closes=[float(r.adj_close) for r in rows],
        closes=[float(r.close) for r in rows],
        sources=tuple(sorted({r.source for r in rows})),
        fetched_at=max(stamps) if stamps else None,
    )


def _should_fetch(
    rows: list[PriceHistoryDailyRow],
    *,
    min_days: int,
    now: datetime,
    force_refresh: bool,
) -> bool:
    """Stale AND not throttled.

    "Stale" is `newest bar older than yesterday UTC` — there is no trading
    calendar to consult, and `Quote.market_state` cannot substitute for one
    (only the legacy-fallback `YahooQuoteProvider` ever sets it; the production
    `YfinanceProvider.quote` leaves it at the `"CLOSED"` default, always). Over
    a weekend this re-asks at most once per fresh window until Monday's bar
    lands — bounded, cheap, and honest about what it does not know.
    """
    if force_refresh:
        return True
    newest_date = rows[-1].date if rows else None
    stale = (
        newest_date is None
        or newest_date < now.date() - timedelta(days=1)
        or len(rows) < min_days
    )
    if not stale:
        return False
    stamps = [s for s in (_as_utc(r.fetched_at) for r in rows) if s is not None]
    newest_fetched_at = max(stamps) if stamps else None
    if newest_fetched_at is None:
        return True
    return (now - newest_fetched_at).total_seconds() >= _FETCH_FRESH_WINDOW_S


def get_daily_series(
    tickers: Sequence[str],
    *,
    min_days: int,
    now: datetime | None = None,
    force_refresh: bool = False,
) -> dict[str, DailySeries]:
    """Table-backed daily history for each ticker, keyed by normalised symbol.

    Sequential per ticker — there is no batch primitive to use, and the table
    amortises the cost: repeat calls inside the fresh window never reach the
    provider. A ticker whose fetch fails serves whatever is stored (possibly an
    empty series); nothing is ever fabricated to fill a gap.

    Synchronous. Callers on async routes must wrap this in
    `asyncio.to_thread(...)` (the DEF116/DEF120 rule).
    """
    now = now or datetime.now(timezone.utc)
    real_mode = bool(settings.use_real_market_data)

    wanted: list[str] = []
    for raw in tickers:
        t = (raw or "").upper().strip()
        if t and t not in wanted:
            wanted.append(t)

    provider: MarketDataProvider | None = None
    provider_resolved = False
    out: dict[str, DailySeries] = {}

    for ticker in wanted:
        with get_session() as session:
            rows = _load_rows(session, ticker, real_mode=real_mode)
            fetch = _should_fetch(
                rows, min_days=min_days, now=now, force_refresh=force_refresh,
            )
            series = _build_series(ticker, rows)

        if not fetch:
            out[ticker] = series
            continue

        if not provider_resolved:
            provider = _leaf_provider()
            provider_resolved = True
        if provider is None:
            out[ticker] = series
            continue

        # Network round-trip deliberately outside any open transaction.
        candles = provider.history(ticker, HISTORY_FETCH_PERIOD)
        if not candles:
            logger.warn(
                "price_history_fetch_failed",
                ticker=ticker,
                period=HISTORY_FETCH_PERIOD,
                provider=getattr(provider, "name", "unknown"),
                stored_rows=len(series.dates),
            )
            out[ticker] = series
            continue

        with get_session() as session:
            upsert_daily_bars(
                session,
                ticker,
                _candles_to_bars(candles),
                source=getattr(provider, "name", "unknown"),
                now=now,
            )
        # Re-read, so what is returned is exactly what is persisted.
        with get_session() as session:
            out[ticker] = _build_series(
                ticker, _load_rows(session, ticker, real_mode=real_mode),
            )

    return out


def get_benchmark_series(
    *,
    min_days: int,
    now: datetime | None = None,
    force_refresh: bool = False,
) -> DailySeries:
    """The SPY leg, through the identical path, table and hygiene rules as any
    holding (Rev 4 estimator pin 5) — so M04's inner join compares series that
    were built the same way."""
    return get_daily_series(
        [BENCHMARK_TICKER], min_days=min_days, now=now, force_refresh=force_refresh,
    )[BENCHMARK_TICKER]


def latest_trading_day() -> date | None:
    """Newest stored trading day for the benchmark, or None if none is stored.

    The benchmark is the market's own calendar proxy: SPY has a bar on exactly
    the days the US market traded. M03's snapshot job gates on this so the
    Tier-2 series is trading-day-aligned — calendar-day padding understates
    volatility by ~15% (√(252/365)), which is the whole reason CR136 refuses to
    do calendar arithmetic anywhere.
    """
    real_mode = bool(settings.use_real_market_data)
    stmt = select(PriceHistoryDailyRow.date).where(
        PriceHistoryDailyRow.ticker == BENCHMARK_TICKER,
    )
    if real_mode:
        stmt = stmt.where(PriceHistoryDailyRow.source != _MOCK_SOURCE)
    stmt = stmt.order_by(PriceHistoryDailyRow.date.desc()).limit(1)
    with get_session() as session:
        return session.execute(stmt).scalar_one_or_none()


# ── Data-hygiene gate ───────────────────────────────────────────────────────


def detect_bad_print_days(
    adj_closes: list[float],
    *,
    spike_abs_return: float = BAD_PRINT_SPIKE_ABS_RETURN,
    reversal_min_fraction: float = BAD_PRINT_REVERSAL_MIN_FRACTION,
    hard_abs_return: float = BAD_PRINT_HARD_ABS_RETURN,
) -> list[int]:
    """Ascending indices of days whose print looks fabricated, not traded.

    Pure and stdlib-only — no I/O, no session, and the three bounds arrive as
    arguments (their values live in `portfolio_health_constants`) so the
    detector stays independently testable at any calibration.

    Three signals, deliberately calibrated to under- rather than over-fire: a
    genuine crash day is the single most informative observation a volatility
    estimate has, and dropping it would bias σ̂ downward exactly when it matters.

      * a non-positive close on either side of a return — un-returnable garbage;
      * |r| > `hard_abs_return` — no US equity session does this honestly;
      * |r| > `spike_abs_return` where the NEXT trading day reverses at least
        `reversal_min_fraction` of it in the opposite direction — the signature
        of a bad print followed by its correction. Only the spike index is
        flagged; the reversal day IS the correction. A spike on the final day
        has no next day to test and is therefore not flagged by this rule (the
        hard bound still applies to it).

    Report-only. The caller (M04) drops the whole holding for the window with
    `reason: DATA_QUALITY_DROP_REASON` and `partial: true`; nothing here
    repairs, interpolates, or silently includes.
    """
    n = len(adj_closes)
    if n < 2:
        return []

    def simple_return(i: int) -> float | None:
        prev, cur = adj_closes[i - 1], adj_closes[i]
        if prev <= 0.0 or cur <= 0.0:
            return None
        return cur / prev - 1.0

    flagged: list[int] = []
    for i in range(1, n):
        r = simple_return(i)
        if r is None:
            flagged.append(i)
            continue
        if abs(r) > hard_abs_return:
            flagged.append(i)
            continue
        if abs(r) > spike_abs_return and i + 1 < n:
            prev, nxt = adj_closes[i], adj_closes[i + 1]
            r_next = (nxt / prev - 1.0) if prev > 0.0 else None
            if (
                r_next is not None
                and r_next * r < 0.0
                and abs(r_next) >= reversal_min_fraction * abs(r)
            ):
                flagged.append(i)
    return flagged
