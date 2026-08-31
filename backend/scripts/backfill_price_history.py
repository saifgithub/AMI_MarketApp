"""CR164 — bulk-load daily OHLCV bars into `price_history_daily` and write the
survivorship audit into `backtest_universe_membership`.

The as-of read path (`price_history.get_asof_daily_rows`) is a PURE read: it
never fetches, and missing bars surface as UNAVAILABLE in the Room. This script
is the only thing that fills the store for the backtest window — full OHLCV
(auto_adjust=True, so the whole bar shares `adj_close`'s adjusted basis) per
ticker in `tickers_150.txt` plus SPY (the benchmark leg; loaded, not audited —
it is not a universe member).

**Do not "fix" the split basis by flipping this to `auto_adjust=False`.** DEF335
prescribed exactly that for months and it does not work: yfinance splits-adjusts
the OHLC series in BOTH modes and `auto_adjust` withholds only the DIVIDEND
adjustment. Measured 2026-08-31 (yfinance 1.3.0), the unadjusted close across
BKNG's 25:1 split moves 167.77 -> 176.19 — a ratio of 0.95, not 25; NFLX 10:1
gives 1.008 and NOW 5:1 gives 1.020. The flip would rewrite 119,311 rows, move
`close` by the ~0.7% dividend factor, and leave the market-cap mismatch exactly
in place while reporting success. The basis is corrected on the SHARE side
instead — see `app/services/ticker_splits.py`, populated by this script.

The audit is the survivorship control: `tickers_150.txt` was screened 2026-07
from live names, so using it at earlier as-of dates embeds survivorship bias
unless per-ticker membership over the sweep window is recorded and the
exclusion counts published verbatim (CR164 scope decision). One row per
(universe, ticker) in `backtest_universe_membership`, re-derived from the
stored bars on every run.

One dead ticker must not kill the other 149: a fetch failure or empty return
is logged loudly, audited from whatever the store holds, and the run continues.
Aborts only on structural problems (missing/empty tickers file, bad dates).

Usage (from backend/, or in-container with PYTHONPATH=/app):
    .venv/bin/python scripts/backfill_price_history.py
    .venv/bin/python scripts/backfill_price_history.py \
        --tickers-file path/to/tickers.txt --start 2024-06-01 --end 2026-08-10 \
        --universe-id tickers150_v1 --force
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

# Make `from app...` resolve both for `python scripts/<name>.py` (sys.path[0]
# is scripts/) and `python -m scripts.<name>` (already on path — insert is a
# harmless duplicate).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.db import get_session, init_schema
from app.db.models import BacktestUniverseMembershipRow, PriceHistoryDailyRow
from app.services.price_history import _MOCK_SOURCE, upsert_daily_bars
from app.services.ticker_splits import upsert_splits

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TICKERS_FILE = REPO_ROOT / "docs/forward_planning/CR035_room_benchmark/tickers_150.txt"

SOURCE = "yfinance_backfill"
BENCHMARK = "SPY"

# "Already backfilled" heuristic: ~240 trading days of full-OHLCV rows inside
# [start, end] means a prior run covered this ticker; re-fetching would only
# rewrite the same bars. --force overrides.
SKIP_ROW_THRESHOLD = 240

# Fewer stored bars than this over the whole load range and the name cannot
# support the sweep's trailing windows.
MIN_CANDLES = 150

# A last bar this close to `end` means "still trading at the data edge", so
# eligible_to is open-ended (NULL) rather than the incidental final bar date.
DELIST_EDGE_DAYS = 10


def read_tickers(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(f"FATAL: tickers file not found: {path}")
    out: list[str] = []
    for raw in path.read_text().splitlines():
        text = raw.split("#", 1)[0].strip()
        if not text:
            continue
        token = text.split()[0].upper()
        if token not in out:
            out.append(token)
    if not out:
        raise SystemExit(f"FATAL: no tickers parsed from {path}")
    return out


def _clean_price(value) -> float | None:
    """Same guard as `price_history._candles_to_bars`: non-finite OR
    non-positive → None, so a partial bar stays usable for close-readers."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) and v > 0.0 else None


def fetch_bars(ticker: str, start: date, end: date) -> tuple[list[tuple], int]:
    """(6-tuple bars `(date, close, open, high, low, volume)`, bad-close count)."""
    hist = yf.Ticker(ticker).history(
        start=start.isoformat(), end=end.isoformat(), interval="1d", auto_adjust=True,
    )
    if hist is None or hist.empty:
        return [], 0
    bars: list[tuple] = []
    bad_close = 0
    for ts, row in hist.iterrows():
        close = _clean_price(row.get("Close"))
        if close is None:
            bad_close += 1
            continue
        try:
            vol_f = float(row.get("Volume"))
            volume = int(vol_f) if math.isfinite(vol_f) and vol_f >= 0.0 else None
        except (TypeError, ValueError):
            volume = None
        bars.append((
            ts.date(),
            close,
            _clean_price(row.get("Open")),
            _clean_price(row.get("High")),
            _clean_price(row.get("Low")),
            volume,
        ))
    return bars, bad_close


def fetch_splits(ticker: str) -> list[tuple[date, float]] | None:
    """Every split the provider knows for `ticker`, as `(ex_date, ratio)`
    ascending. None on a provider failure — which is NOT the same fact as an
    empty list, and the two must not be conflated (DEF335).

    Derived from the provider, never hand-listed (CR175 F3): a hardcoded ticker
    list is correct on the day it is written and silently wrong at the next
    corporate action.

    The whole history is returned, not just the audit window, because the
    fact-sheet restatement in `edgar_pit` needs every split between a filing
    and the bars' download date — a range the audit window does not bound.
    """
    try:
        raw = yf.Ticker(ticker).splits
    except Exception:  # pragma: no cover — provider/network
        return None
    if raw is None:
        return None
    if len(raw) == 0:
        return []
    out: list[tuple[date, float]] = []
    for stamp, value in raw.items():
        try:
            ratio = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(ratio) and ratio > 0.0:
            out.append((stamp.date(), ratio))
    return sorted(out)


def splits_in_window(ticker: str, window_start: date, window_end: date) -> list[date]:
    """Split dates for `ticker` inside the window — the audit's exclusion rule.

    Bars are downloaded split-adjusted, so a bar stored for date X has been
    adjusted for **every split between X and the download**, while the share
    count `edgar_pit` pairs it with is the figure **as filed** — pre-split.

    Returns [] on a provider failure rather than raising — but the CALLER must
    treat that as unknown-not-clean; see `audit_ticker`.
    """
    fetched = fetch_splits(ticker)
    if not fetched:
        return []
    return sorted(d for d, _ in fetched if window_start <= d <= window_end)


def stored_backfilled_count(session, ticker: str, start: date, end: date) -> int:
    """Real rows in [start, end] that carry OHLCV (open IS NOT NULL) — i.e.
    rows a prior run of THIS script (not the close-only live path) wrote."""
    return session.execute(
        select(func.count())
        .select_from(PriceHistoryDailyRow)
        .where(
            PriceHistoryDailyRow.ticker == ticker,
            PriceHistoryDailyRow.date >= start,
            PriceHistoryDailyRow.date <= end,
            PriceHistoryDailyRow.open.is_not(None),
            PriceHistoryDailyRow.source != _MOCK_SOURCE,
        )
    ).scalar_one()


def audit_ticker(
    session,
    universe_id: str,
    ticker: str,
    start: date,
    end: date,
    window_start: date,
    window_end: date,
    split_dates: list[date] | None = None,
) -> str | None:
    """Upsert this ticker's `backtest_universe_membership` row from the STORED
    real bars in [start, end] and return the exclusion reason (None = clean)."""
    dates = session.execute(
        select(PriceHistoryDailyRow.date)
        .where(
            PriceHistoryDailyRow.ticker == ticker,
            PriceHistoryDailyRow.date >= start,
            PriceHistoryDailyRow.date <= end,
            PriceHistoryDailyRow.source != _MOCK_SOURCE,
        )
        .order_by(PriceHistoryDailyRow.date)
    ).scalars().all()

    first = dates[0] if dates else None
    last = dates[-1] if dates else None
    eligible_from = first
    eligible_to = last if (last is not None and last < end - timedelta(days=DELIST_EDGE_DAYS)) else None

    # DEF335 — the split rule, and it is checked BEFORE the coverage rules
    # because a ticker can have complete, contiguous bars and still be unusable:
    # nothing about candle count reveals that the price basis and the share
    # basis disagree. This exclusion was recorded as "applied" for months and
    # was never implemented — measured 2026-08-27, all 150 membership rows
    # carried a NULL exclusion_reason and BKNG sat eligible across the whole
    # window, which is how a 141.5% FCF yield reached a published verdict.
    #
    # The cutoff is the LAST split in the window, not the first: a bar is
    # adjusted for every split after it, so a name that split twice (HON:
    # 2025-10-30 and 2026-06-29) stays mismatched until the later one.
    splits = split_dates if split_dates is not None else []
    if splits:
        eligible_from = max(splits)
        reason = "split_after_as_of"
    elif len(dates) < MIN_CANDLES:
        reason = "insufficient_candles"
    elif first > window_start:
        reason = "listed_after_asof"
    elif last < window_end:
        reason = "delisted_in_window"
    else:
        reason = None

    row = session.execute(
        select(BacktestUniverseMembershipRow).where(
            BacktestUniverseMembershipRow.universe_id == universe_id,
            BacktestUniverseMembershipRow.ticker == ticker,
        )
    ).scalar_one_or_none()
    if row is None:
        session.add(BacktestUniverseMembershipRow(
            universe_id=universe_id,
            ticker=ticker,
            eligible_from=eligible_from,
            eligible_to=eligible_to,
            exclusion_reason=reason,
        ))
    else:
        row.eligible_from = eligible_from
        row.eligible_to = eligible_to
        row.exclusion_reason = reason
        row.noted_at = datetime.now(timezone.utc)
    return reason


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tickers-file", type=Path, default=DEFAULT_TICKERS_FILE)
    ap.add_argument("--start", type=date.fromisoformat, default=date(2024, 6, 1))
    ap.add_argument("--end", type=date.fromisoformat, default=date.today())
    ap.add_argument("--universe-id", default="tickers150_v1")
    ap.add_argument("--window-start", type=date.fromisoformat, default=date(2025, 2, 28))
    ap.add_argument("--window-end", type=date.fromisoformat, default=date(2026, 7, 3))
    ap.add_argument("--force", action="store_true", help="refetch even if rows exist")
    ap.add_argument("--sleep", type=float, default=0.5, help="seconds between tickers")
    args = ap.parse_args()

    if args.start >= args.end:
        raise SystemExit(f"FATAL: --start {args.start} must be before --end {args.end}")
    if args.window_start >= args.window_end:
        raise SystemExit(
            f"FATAL: --window-start {args.window_start} must be before --window-end {args.window_end}"
        )

    universe = read_tickers(args.tickers_file)
    load_list = list(universe)
    if BENCHMARK not in load_list:
        load_list.append(BENCHMARK)
    print(
        f"[plan] {len(universe)} universe tickers + benchmark {BENCHMARK} · "
        f"range {args.start}..{args.end} · window {args.window_start}..{args.window_end} · "
        f"universe_id={args.universe_id} · force={args.force}",
        flush=True,
    )

    init_schema()

    loaded = skipped = failed = empty = 0
    total_rows = 0
    total_bad_close = 0
    reasons: dict[str, int] = {}

    for i, ticker in enumerate(load_list, 1):
        prefix = f"[{i}/{len(load_list)}] {ticker}"
        fetched = False
        if not args.force:
            with get_session() as session:
                have = stored_backfilled_count(session, ticker, args.start, args.end)
            if have >= SKIP_ROW_THRESHOLD:
                skipped += 1
                print(f"{prefix}: SKIP — {have} backfilled rows already stored", flush=True)
            else:
                fetched = True
        else:
            fetched = True

        if fetched:
            fetch_error = None
            try:
                bars, bad_close = fetch_bars(ticker, args.start, args.end)
            except Exception as exc:
                fetch_error = exc
                bars, bad_close = [], 0
            total_bad_close += bad_close
            if fetch_error is not None:
                failed += 1
                print(
                    f"{prefix}: FETCH FAILED — {type(fetch_error).__name__}: {fetch_error}",
                    flush=True,
                )
            elif bars:
                now = datetime.now(timezone.utc)
                with get_session() as session:
                    stats = upsert_daily_bars(session, ticker, bars, source=SOURCE, now=now)
                loaded += 1
                total_rows += stats["inserted"] + stats["updated"]
                extra = f" · {bad_close} bad closes dropped" if bad_close else ""
                print(
                    f"{prefix}: {len(bars)} bars → inserted={stats['inserted']} "
                    f"updated={stats['updated']}{extra}",
                    flush=True,
                )
            else:
                # Empty return without an exception: dead/unknown symbol at
                # yfinance. The audit below records it from whatever the store
                # holds (an all-empty store → insufficient_candles, NULL dates).
                empty += 1
                print(f"{prefix}: EMPTY — yfinance returned no bars; auditing from store", flush=True)

        if ticker in universe:
            # DEF335 — asked once per ticker, outside the session, because it is
            # a network call and the audit must not hold a transaction open for
            # it. A provider failure returns [], which reads as "no split": that
            # is the one direction this can be wrong, and it is stated here
            # rather than discovered later. The audit is re-runnable, so a
            # ticker mis-cleared by a transient failure is corrected by the next
            # pass; a ticker wrongly excluded would not self-correct, which is
            # why the bias is this way round.
            all_splits = fetch_splits(ticker)
            if all_splits is None:
                print(f"{prefix}: SPLITS UNAVAILABLE — provider failed; "
                      f"audit reads clean and edgar_pit will not restate shares", flush=True)
                all_splits = []
            elif all_splits:
                # DEF335 — persisted for the fact-sheet restatement, which
                # cannot fetch: `get_asof_daily_rows` is contractually a pure
                # read so an as-of Room run is deterministic given the store.
                with get_session() as session:
                    st = upsert_splits(
                        session, ticker, all_splits, source=SOURCE,
                    )
                print(f"{prefix}: splits → inserted={st['inserted']} "
                      f"updated={st['updated']} rejected={st['rejected']}", flush=True)
            ticker_splits = sorted(
                d for d, _ in all_splits
                if args.window_start <= d <= args.window_end
            )
            with get_session() as session:
                reason = audit_ticker(
                    session, args.universe_id, ticker,
                    args.start, args.end, args.window_start, args.window_end,
                    split_dates=ticker_splits,
                )
            reasons[reason or "clean"] = reasons.get(reason or "clean", 0) + 1
            if reason:
                print(f"{prefix}: audit → {reason}", flush=True)

        if fetched and i < len(load_list):
            time.sleep(args.sleep)

    print(
        f"\n[summary] loaded={loaded} skipped={skipped} failed={failed} empty={empty} "
        f"rows_written={total_rows} bad_closes_dropped={total_bad_close}",
        flush=True,
    )
    print(f"[audit] universe={args.universe_id} · " + ", ".join(
        f"{k}={v}" for k, v in sorted(reasons.items())
    ), flush=True)


if __name__ == "__main__":
    main()
