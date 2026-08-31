"""Recorded stock splits, and the factor that restates a share count onto the
price store's basis — DEF335.

**Why this module exists at all.** `price_history_daily` holds yfinance bars,
and yfinance splits-adjusts the OHLC series in BOTH `auto_adjust` modes;
`auto_adjust=False` withholds only the DIVIDEND adjustment. Measured 2026-08-31
(yfinance 1.3.0), the unadjusted close across each split moves:

    BKNG  2026-04-06  25:1   167.77 -> 176.19   ratio 0.952
    NFLX  2025-11-17  10:1   111.22 -> 110.29   ratio 1.008
    NOW   2025-12-18   5:1   156.48 -> 153.38   ratio 1.020

— i.e. ~1, not ~25/~10/~5. So no provider setting recovers an as-traded price,
and DEF335's original prescription (re-backfill with `auto_adjust=False` so
`close` carries the raw quote) would have rewritten 119,311 rows across 201
tickers, moved `close` by the ~0.7% cumulative dividend factor, and left the
25x market-cap error exactly where it was — while looking like it had worked.

The price basis cannot move, so the SHARE basis moves to meet it.
`edgar_pit.fetch_pit_fundamentals` pairs a stored bar with the dei cover-page
share count **as filed** — a pre-split count against a post-split-adjusted
price — and every figure built on the product inherits the mismatch.
`split_factor` restates the filed count onto the bars' own basis.

Splits are STORED, never fetched on the fact-sheet path, because
`get_asof_daily_rows` is contractually a pure read ("an as-of Room run must be
deterministic given the store"); a network call there would make a replayed
backtest depend on when it was replayed.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Iterable, Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import get_session
from app.db.models import PriceHistoryDailyRow, TickerSplitRow
from app.services.price_history import _MOCK_SOURCE

# A ratio outside this band is not a corporate action, it is a bad print.
# Applying one would move a market cap by orders of magnitude, so it is
# refused at write time rather than discovered in a fact sheet.
_MIN_RATIO = 0.001
_MAX_RATIO = 1000.0


def upsert_splits(
    session,
    ticker: str,
    pairs: Sequence[tuple[date, float]],
    *,
    source: str,
    now: datetime | None = None,
) -> dict[str, int]:
    """Write `(ex_date, ratio)` pairs for `ticker`, one row per ex-date.

    Idempotent: re-running the backfill restamps `fetched_at` and corrects a
    ratio the provider has since revised, rather than accumulating duplicates.

    A ratio of exactly 1.0 is dropped — it is not a split, and storing it would
    put a no-op row in a table whose whole purpose is that a row means "the
    basis changed here". Ratios outside `[0.001, 1000]` are dropped as bad
    prints; both counts are returned so the caller can log them rather than
    have them vanish.
    """
    stamp = now or datetime.now(timezone.utc)
    t = ticker.upper().strip()
    stats = {"inserted": 0, "updated": 0, "rejected": 0}

    existing = {
        row.ex_date: row
        for row in session.execute(
            select(TickerSplitRow).where(TickerSplitRow.ticker == t)
        ).scalars().all()
    }

    for ex_date, raw_ratio in pairs:
        try:
            ratio = float(raw_ratio)
        except (TypeError, ValueError):
            stats["rejected"] += 1
            continue
        if ratio == 1.0 or not (_MIN_RATIO <= ratio <= _MAX_RATIO):
            stats["rejected"] += 1
            continue
        row = existing.get(ex_date)
        if row is not None:
            row.ratio = ratio
            row.source = source
            row.fetched_at = stamp
            stats["updated"] += 1
            continue
        # P15 — this SELECTs then INSERTs, so two backfills running at once
        # both read "absent" and both insert, and one loses
        # `uq_ticker_splits_ticker_ex_date`. Same answer as
        # `price_history.upsert_daily_bars`: the loser wrote the same split
        # from the same provider, so it converges to an update rather than
        # failing the run. Nested in a SAVEPOINT so the violation rolls back
        # only this row — without it the outer session is poisoned and the
        # other 200 tickers' splits are lost to one collision.
        try:
            with session.begin_nested():
                session.add(TickerSplitRow(
                    ticker=t, ex_date=ex_date, ratio=ratio, source=source, fetched_at=stamp,
                ))
            stats["inserted"] += 1
        except IntegrityError:
            winner = session.execute(
                select(TickerSplitRow)
                .where(TickerSplitRow.ticker == t, TickerSplitRow.ex_date == ex_date)
            ).scalar_one_or_none()
            if winner is None:  # pragma: no cover — the constraint fired, the row must exist
                raise
            winner.ratio = ratio
            winner.source = source
            winner.fetched_at = stamp
            stats["updated"] += 1
    return stats


def get_splits(ticker: str) -> list[tuple[date, float]]:
    """Every stored split for `ticker`, ascending by ex-date. Pure read."""
    t = ticker.upper().strip()
    with get_session() as session:
        rows = session.execute(
            select(TickerSplitRow.ex_date, TickerSplitRow.ratio)
            .where(TickerSplitRow.ticker == t)
            .order_by(TickerSplitRow.ex_date)
        ).all()
    return [(r[0], float(r[1])) for r in rows]


def split_factor(
    ticker: str, *, after: date, until: date, splits: Iterable[tuple[date, float]] | None = None,
) -> float:
    """Product of split ratios with `after < ex_date <= until`. 1.0 when none.

    Multiply an as-filed share count by this to state it in the same units as a
    bar that has been adjusted through `until`.

    **Both bounds are load-bearing and neither is `as_of`.**

    `after` is the share FACT's own `period_end`, not the as-of date: a split
    between the filing and `as_of` already makes the filed count stale at
    `as_of`, so anchoring on `as_of` would under-correct. It is EXCLUSIVE — a
    count stated as of the ex-date is taken to already reflect that morning's
    split, which is the direction that cannot double-apply.

    `period_end` is the right anchor because it is what EDGAR's `end` field
    MEANS for an instant fact: the date the value is measured as of. The
    residual exposure is a filer that tags `end` to its fiscal period end while
    reporting a cover-page count measured at filing date — for such a filer a
    split inside that gap (at most ~40 days, and splits are announced weeks
    ahead) would be applied to a count that already reflects it. Anchoring on
    `filed` instead would only move the same-sized error to the other side of
    the gap, for every filer rather than the mis-tagging ones.

    `until` is the bars' own download stamp, not today. A bar is adjusted for
    every split up to the moment it was DOWNLOADED, so a split that happened
    after the last backfill is not in the stored prices; applying it anyway
    would over-correct by the whole factor — 25x, not 1%. It is INCLUSIVE: a
    split on the download date is baked into what was downloaded.

    `splits` is an injection point for callers that already hold the rows (the
    backfill audits every ticker in one pass); omitted, it reads the store.
    """
    rows = get_splits(ticker) if splits is None else splits
    factor = 1.0
    for ex_date, ratio in rows:
        if after < ex_date <= until:
            factor *= ratio
    return factor


def get_asof_bars_basis_date(ticker: str, as_of: date) -> date | None:
    """The UTC date the trailing stored bars for `ticker` were last downloaded.

    This is the `until` bound `split_factor` needs, and it must come from the
    bars rather than the clock: `date.today()` would include any split that
    happened since the last backfill, none of which is reflected in the stored
    prices. Mock rows are excluded on the same terms as `get_asof_daily_rows`,
    so a fabricated bar cannot set the basis for a real one.

    None when the ticker has no real stored bars at or before `as_of` — the
    caller must then apply no adjustment rather than guess a date.
    """
    t = ticker.upper().strip()
    with get_session() as session:
        stamp = session.execute(
            select(func.max(PriceHistoryDailyRow.fetched_at))
            .where(PriceHistoryDailyRow.ticker == t)
            .where(PriceHistoryDailyRow.date <= as_of)
            .where(PriceHistoryDailyRow.source != _MOCK_SOURCE)
        ).scalar_one_or_none()
    if stamp is None:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc).date()
