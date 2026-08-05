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

import math
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

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
    BAD_PRINT_MIN_ABS_RETURN,
    BAD_PRINT_REVERSAL_MIN_FRACTION,
    BAD_PRINT_SIGMA_MULT,
    BENCHMARK_TICKER,
    HISTORY_FETCH_PERIOD,
    HISTORY_MAX_ROWS,
)

# MAD → Gaussian-consistent σ. 1/Φ⁻¹(0.75); the standard robust-scale constant.
_MAD_TO_SIGMA = 1.4826

# Per-ticker provider-fetch throttle. Daily bars change once per trading day,
# so re-asking inside this window can only return what we already stored.
# Convention, following `ticker_reference._REFRESH_FRESH_WINDOW_S`.
_FETCH_FRESH_WINDOW_S = 6 * 3600

# The leaf-provider name that marks a row as fabricated. Real-mode reads
# exclude it; real fetches upsert over it.
_MOCK_SOURCE = "mock_walk"


# ── Provider access ─────────────────────────────────────────────────────────

_history_provider: MarketDataProvider | None = None

# Per-ticker timestamp of the last fetch ATTEMPT, successful or not. The stored
# `fetched_at` column cannot serve this: it is written only by a successful
# upsert, so a provider that keeps returning None would never advance it and the
# throttle would never engage — a dead feed would be re-hit on every single
# evaluation, for every holding, forever.
_last_fetch_attempt: dict[str, datetime] = {}

# M01 A1 — per-ticker: did the MOST RECENT attempt leave usable history?
#
# `fetch_failed` used to answer only for the caller that made the failing call.
# Every other caller inside `_FETCH_FRESH_WINDOW_S` — six hours — was told the
# other thing, so for 359 of every 360 minutes after a feed hiccup a dropped
# holding read `short_history` when the truth was `feed_unavailable`. That is
# verbatim the confusion `FEED_UNAVAILABLE_DROP_REASON`'s own comment exists to
# prevent, and it made that constant reachable by one request in 360.
#
# Set PESSIMISTICALLY, before the network call, and cleared only on an attempt
# that leaves usable history. That ordering is what covers the sibling case: a
# second caller throttled by an attempt still in flight reads True, because
# there is not yet a success to clear it. The residual race — the sibling's
# commit lands between this caller's row read and its flag read — narrows the
# window to that gap rather than closing it, and errs toward "the feed is
# unreliable", which is the safe direction.
_last_fetch_failed: dict[str, bool] = {}


def set_history_provider(provider: MarketDataProvider | None) -> None:
    """Replace the leaf provider. Test hook, mirroring
    `market_data.set_market_data_provider`; safe to call with None to reset.
    Also clears the failed-attempt throttle, which is in-process state."""
    global _history_provider
    _history_provider = provider
    _last_fetch_attempt.clear()
    _last_fetch_failed.clear()


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

    `fetch_failed` says **the most recent attempt for this TICKER left no
    usable history** — not merely that this particular call got nothing (M01
    A1). The narrower reading was the defect: the throttle window is six hours,
    so every caller after the one that made the failing attempt was told the
    other thing, and a dropped holding read `short_history` for 359 of every
    360 minutes after a feed hiccup. Without this a feed outage and a genuinely
    young security are the same empty series, and the engine tells a user "this
    holding does not have enough price history" when the truth is "our data
    feed is down" — the CR040 question answered the wrong way.

    A young security is still reported as young: a clean fetch that returns 20
    bars rejects nothing, and only a fetch that served bars we could not use
    (`rejected > 0`) and still left the ticker short counts as a feed failure.
    """

    ticker: str
    dates: list[date]
    adj_closes: list[float]
    closes: list[float]
    sources: tuple[str, ...]
    fetched_at: datetime | None
    fetch_failed: bool = False


def _empty_series(ticker: str, *, fetch_failed: bool = False) -> DailySeries:
    return DailySeries(
        ticker=ticker, dates=[], adj_closes=[], closes=[], sources=(),
        fetched_at=None, fetch_failed=fetch_failed,
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
    replace_foreign_rows: bool = True,
) -> dict:
    """Insert-or-update `(ticker, date)` rows.

    Returns `{"inserted", "updated", "skipped"}`.

    Existing rows are UPDATED, never skipped: a dividend or split rewrites the
    whole trailing adjusted series at the provider, so skip-if-exists would
    freeze stale values into every covariance computed afterwards.

    `replace_foreign_rows=False` makes an existing row written by a DIFFERENT
    provider untouchable. The mock path passes it: a local dev run in mock mode
    would otherwise walk over accumulated real bars in place — value and
    provenance both — and the destruction would be invisible, since the rows
    still look like ordinary history afterwards.

    Runs in the caller's session/transaction. Insert-or-update by reading the
    affected dates into a dict first — portable across sqlite and Postgres,
    no dialect-specific ON CONFLICT.
    """
    t = ticker.upper().strip()
    by_date: dict[date, float] = {}
    for bar_date, price in bars:
        by_date[bar_date] = float(price)
    if not by_date:
        return {"inserted": 0, "updated": 0, "skipped": 0}

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
    skipped = 0
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
        elif not replace_foreign_rows and row.source != source:
            skipped += 1
        else:
            row.close = price
            row.adj_close = price
            row.source = source
            row.fetched_at = now
            updated += 1
    session.flush()
    if skipped:
        logger.info(
            "price_history_preserved_foreign_rows",
            ticker=t, source=source, skipped=skipped,
        )
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


# ── Read-through ────────────────────────────────────────────────────────────


def _candles_to_bars(
    candles: Sequence[Candle], *, ticker: str,
) -> tuple[list[tuple[date, float]], int]:
    """(trading date + close per candle, rejected count), later bars winning a duplicate date.

    The rejected count is RETURNED, not just logged (M01 A1 / attack 3). It is
    the datum that separates "the provider served garbage" from "this security
    is genuinely young": both end in a series too short to use, and only the
    first is a feed failure. Counting it from `len(candles) - len(bars)` would
    be wrong — that also counts duplicate dates collapsing, which is normal.

    `Candle.t` is epoch seconds UTC. yfinance stamps a daily bar at midnight
    exchange-tz (or naive midnight), so the UTC date equals the exchange
    trading date either way. Weekends and holidays exist only as absent bars.

    Non-finite and non-positive closes are refused at the door and counted in a
    log line, never persisted. `YfinanceProvider.history` does not filter them:
    `float(row["Close"])` on a pandas NaN returns `nan` rather than raising, so
    a malformed provider row would otherwise reach `Numeric(12, 4)` — where it
    either fails the whole call with a DB error or, worse, lands in the table
    and turns every covariance built from that ticker into NaN.
    """
    by_date: dict[date, float] = {}
    rejected = 0
    for candle in candles:
        close = float(candle.c)
        if not (math.isfinite(close) and close > 0.0):
            rejected += 1
            continue
        bar_date = datetime.fromtimestamp(candle.t, timezone.utc).date()
        by_date[bar_date] = close
    if rejected:
        logger.warn(
            "price_history_rejected_unusable_close",
            ticker=ticker,
            rejected=rejected,
            served=len(candles),
        )
    return sorted(by_date.items()), rejected


def _build_series(
    ticker: str, rows: list[PriceHistoryDailyRow], *, fetch_failed: bool = False,
) -> DailySeries:
    if not rows:
        return _empty_series(ticker, fetch_failed=fetch_failed)
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
        fetch_failed=fetch_failed,
    )


def _should_fetch(
    rows: list[PriceHistoryDailyRow],
    *,
    min_days: int,
    now: datetime,
    force_refresh: bool,
    last_attempt: datetime | None = None,
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
    if last_attempt is not None:
        stamps.append(last_attempt)
    newest_attempt = max(stamps) if stamps else None
    if newest_attempt is None:
        return True
    return (now - newest_attempt).total_seconds() >= _FETCH_FRESH_WINDOW_S


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
    # A naive `now` is treated as UTC rather than raising: every stored stamp is
    # normalised the same way, and a caller that passed `datetime.now()` should
    # get a throttle decision, not a TypeError from a mixed-awareness subtract.
    now = _as_utc(now) or datetime.now(timezone.utc)
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
                last_attempt=_last_fetch_attempt.get(ticker),
            )
            series = _build_series(ticker, rows)

        if not fetch:
            # M01 A1 — throttled, so this call made no attempt of its own. If
            # the most recent attempt left no usable history, that fact belongs
            # to the TICKER, not to the unlucky caller who happened to make it.
            # Gated on the series still being unusable: a book that already has
            # what it asked for is not degraded, and flagging it would be noise
            # rather than the CR040 distinction this exists to draw.
            if _last_fetch_failed.get(ticker) and len(series.dates) < min_days:
                series = _replace_fetch_failed(series, ticker)
            out[ticker] = series
            continue

        if not provider_resolved:
            provider = _leaf_provider()
            provider_resolved = True
        if provider is None:
            # No provider is a fetch failure, not an absence of history: the
            # caller must be able to tell "our feed is down" from "this
            # security is young" (CR040).
            _last_fetch_attempt[ticker] = now
            _last_fetch_failed[ticker] = True
            logger.warn(
                "price_history_no_provider",
                ticker=ticker,
                stored_rows=len(series.dates),
                newest_stored_date=(
                    series.dates[-1].isoformat() if series.dates else None
                ),
            )
            out[ticker] = _replace_fetch_failed(series, ticker)
            continue

        # Network round-trip deliberately outside any open transaction. The
        # attempt is recorded BEFORE it is made, so a failure throttles the next
        # one exactly as a success does.
        _last_fetch_attempt[ticker] = now
        _last_fetch_failed[ticker] = True      # pessimistic; cleared on success
        candles = provider.history(ticker, HISTORY_FETCH_PERIOD)
        source = getattr(provider, "name", "unknown")
        bars, rejected = _candles_to_bars(candles or (), ticker=ticker)
        if not bars:
            logger.warn(
                "price_history_fetch_failed",
                ticker=ticker,
                period=HISTORY_FETCH_PERIOD,
                provider=source,
                stored_rows=len(series.dates),
                candles_served=len(candles or ()),
                # How degraded the served result actually is: without this an
                # operator cannot tell a one-day gap from a six-month one.
                newest_stored_date=(
                    series.dates[-1].isoformat() if series.dates else None
                ),
            )
            out[ticker] = _replace_fetch_failed(series, ticker)
            continue

        try:
            with get_session() as session:
                upsert_daily_bars(
                    session,
                    ticker,
                    bars,
                    source=source,
                    now=now,
                    # A mock run must never overwrite real history in place.
                    replace_foreign_rows=source != _MOCK_SOURCE,
                )
        except IntegrityError:
            # M01 A2 — `upsert_daily_bars` SELECTs the affected dates and
            # INSERTs what is missing, so two callers whose reads both land
            # before either commits will both INSERT and one loses the unique
            # constraint. M03 already answers this in this same CR
            # (`portfolio_snapshot.py:192`): a concurrent writer losing the race
            # wrote the same bars, so this is a skip, not a failure.
            #
            # Not hypothetical for long. `_last_fetch_attempt` is PER PROCESS
            # and the throttle is what keeps a single uvicorn to one fetcher —
            # measured at 0/60 races today. CLAUDE.md's Beta stack is Cloud Run,
            # where instances share no dict, so two users on two instances
            # hitting a cold ticker is the common case, and every evaluation
            # fetches SPY. Raising here propagates through `build_health_context`
            # → `asyncio.to_thread` → the tiles route, whose docstring commits
            # to returning 200 with an amber state rather than a 5xx.
            logger.warn(
                "price_history_concurrent_write",
                ticker=ticker, bars=len(bars), provider=source,
            )
        # Re-read, so what is returned is exactly what is persisted.
        with get_session() as session:
            series = _build_series(
                ticker, _load_rows(session, ticker, real_mode=real_mode),
            )

        # M01 A1, the third path — a fetch that SUCCEEDED and still left the
        # ticker unusable. `rejected > 0` is what makes this a feed failure
        # rather than a young security: the provider served bars we could not
        # use (NaN / non-positive closes), so the shortfall is ours, not the
        # security's age. A clean 20-bar IPO rejects nothing and is correctly
        # left reading `short_history`, which is the distinction A1 is about.
        if rejected > 0 and len(series.dates) < min_days:
            _last_fetch_failed[ticker] = True
            series = _replace_fetch_failed(series, ticker)
        else:
            _last_fetch_failed.pop(ticker, None)
        out[ticker] = series

    return out


def _replace_fetch_failed(series: DailySeries, ticker: str) -> DailySeries:
    if not series.dates:
        return _empty_series(ticker, fetch_failed=True)
    return DailySeries(
        ticker=series.ticker,
        dates=series.dates,
        adj_closes=series.adj_closes,
        closes=series.closes,
        sources=series.sources,
        fetched_at=series.fetched_at,
        fetch_failed=True,
    )


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


def _usable_price(value: float) -> bool:
    """A price that a return can honestly be computed from.

    NaN is the archetypal garbage print, and it is invisible to every ordinary
    comparison — `nan > 0.40` and `nan <= 0.0` are BOTH False, so a threshold
    screen written the obvious way lets it through untouched and it poisons
    every covariance downstream as a silent NaN.
    """
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0.0


def robust_daily_sigma(returns: Sequence[float]) -> float:
    """MAD-scaled standard deviation of a return series.

    Robust by necessity, not preference: the observation being hunted is
    precisely the one that would inflate a plain standard deviation and hide
    itself behind a widened bound. The median absolute deviation has a 50%
    breakdown point, so a handful of bad prints in a 126–504 day window cannot
    move it. ×1.4826 rescales MAD to a Gaussian-consistent σ.

    Returns 0.0 for a series too short or too degenerate to estimate — the
    caller's absolute floor takes over there.
    """
    if len(returns) < 3:
        return 0.0
    median = statistics.median(returns)
    mad = statistics.median([abs(r - median) for r in returns])
    return _MAD_TO_SIGMA * mad


def detect_bad_print_days(
    adj_closes: list[float],
    *,
    sigma_mult: float = BAD_PRINT_SIGMA_MULT,
    min_abs_return: float = BAD_PRINT_MIN_ABS_RETURN,
    reversal_min_fraction: float = BAD_PRINT_REVERSAL_MIN_FRACTION,
    hard_abs_return: float = BAD_PRINT_HARD_ABS_RETURN,
) -> list[int]:
    """Ascending indices of days whose print looks fabricated, not traded.

    Pure and stdlib-only — no I/O, no session, and every bound arrives as an
    argument (values live in `portfolio_health_constants`) so the detector stays
    independently testable at any calibration.

    Three signals:

      * a close that is non-finite or non-positive on either side of a return —
        un-returnable garbage, flagged outright;
      * `|r| > hard_abs_return` — no US equity session does this honestly;
      * `|r|` exceeding BOTH `sigma_mult` robust daily sigma AND
        `min_abs_return`, where the NEXT trading day undoes at least
        `reversal_min_fraction` of the PRICE move — the signature of a bad
        print followed by its correction. Only the spike index is flagged; the
        reversal day IS the correction. A spike on the final day has no next
        day to test and is not flagged by this rule (the hard bound still
        applies).

    **Volatility-scaled, per Rev 4's pin.** A flat absolute bound is inert
    exactly where it is needed most: on a bond ETF at 0.26%/day, a 40%
    threshold is ~150 daily sigma, so no phantom print short of the hard bound
    could ever trip it. The absolute floor sits alongside the sigma multiple —
    both must be exceeded — because a very low sigma would otherwise make the
    bound absurdly tight; measured, the binding case is BND on 2020-03-12, a
    genuine 5.44% bond dislocation that is 27.6 robust sigma and does reverse.

    **Reversal is measured on the price move, not on the two returns.** For an
    exact round trip `(cur − next)/(cur − prev)` is exactly 1.0 at any
    magnitude and in either direction, whereas comparing the two simple returns
    scores the same round trip as low as 1/(1+r) — which silently exempted
    every upward print above +66.7%.

    Report-only. The caller (M04) drops the whole holding for the window with
    `reason: DATA_QUALITY_DROP_REASON` and `partial: true`; nothing here
    repairs, interpolates, or silently includes.
    """
    n = len(adj_closes)
    if n < 2:
        return []

    clean_returns = [
        adj_closes[i] / adj_closes[i - 1] - 1.0
        for i in range(1, n)
        if _usable_price(adj_closes[i]) and _usable_price(adj_closes[i - 1])
    ]
    bound = max(sigma_mult * robust_daily_sigma(clean_returns), min_abs_return)

    flagged: list[int] = []
    for i in range(1, n):
        prev, cur = adj_closes[i - 1], adj_closes[i]
        if not _usable_price(prev) or not _usable_price(cur):
            flagged.append(i)
            continue
        r = cur / prev - 1.0
        if abs(r) > hard_abs_return:
            flagged.append(i)
            continue
        if abs(r) > bound and i + 1 < n:
            nxt = adj_closes[i + 1]
            if not _usable_price(nxt):
                continue
            move = cur - prev
            if move == 0.0:
                continue
            undone = (cur - nxt) / move
            if undone >= reversal_min_fraction:
                flagged.append(i)
    return flagged
