"""CR136 M10 backfill — reconstruct each sim portfolio's daily value series from its trade ledger and insert historical portfolio_value_snapshots rows (dry-run default, --apply to write; runs inside ami_api_alpha — the Mac has no DB).

M03 persists a value row forward, one per trading day. This is the other half:
it walks the trade ledger backwards in time so Tier-2 (rolling max drawdown,
realised return) has depth on day one instead of twenty-one days after go-live.

PRICE BASIS — UNADJUSTED daily Close, priced against the recorded share counts.
The yfinance fetch passes `auto_adjust=False` deliberately. `SimTradeRow` share
counts were executed against live unadjusted quotes, the sim has no
corporate-action handling anywhere (no split ever rewrites a recorded
`quantity`, no dividend is ever credited), and the live engine values holdings
at live unadjusted marks. An adjusted series would misprice every
pre-adjustment day the moment a dividend or split lands, because adjusted
series rewrite the past and ledger share counts do not. This is also why M01's
`price_history_daily` is NOT the valuation source: it stores the ADJUSTED close
in both of its columns. M01 is still used for a dry-run cross-check of the
trading-day grid, where dates are basis-independent.

    Known limitation: a split between execution and today distorts BOTH the
    live sim and this backfill identically — a 2:1 split halves the close while
    the recorded share count stays fixed. Corporate-action handling is out of
    CR136 scope end to end, and the backfill must not "fix" what the live
    engine does not.

DRAWDOWN COLUMN — `drawdown_pct` here is the sim's vs-STARTING-CAPITAL number,
the same quantity live rows carry, floored at zero. It is NOT the Tier-2
peak-to-trough drawdown. On the path $10k → $15k → $12k this column stores 0.0
while the Tier-2 tile, which computes peak-to-trough from the `total_value`
series, reads 20.0. Two different quantities that were both once called
"drawdown" is the Rev 2 defect this warning exists to stop recurring.

F16 COLUMNS ARE NULL on every backfilled row — `predicted_vol_ann`,
`n_observations`, `engine_version`. No engine ran historically, and a backcast
sigma back-dated onto history would be fabricated auditability. The F16 bias
test therefore starts accumulating at go-live: `bias_z_stats` skips pairs whose
prior row has a null prediction, so backfilled rows are structurally excluded.

SYNTHETIC USERS are backfilled too — it keeps the table uniform and costs
nothing — but their plan line carries `[synthetic]` so the operator never picks
a CR035 room-benchmark account for the spot-check that is supposed to validate
REAL-user correctness.

Usage — runs INSIDE the api container, the only place with both the real
`DATABASE_URL` and the `app` package. `backend/Dockerfile` copies only `app/`,
`tests/` and `alembic/`, so this file is not in the image and has to be copied
in. `ENV PYTHONPATH=/app` makes the `app.*` imports resolve from anywhere.

    scp backend/scripts/cr136_backfill_portfolio_snapshots.py melehost:/tmp/
    ssh melehost "docker cp /tmp/cr136_backfill_portfolio_snapshots.py ami_api_alpha:/tmp/"

    # dry run (default) — prints the plan, writes nothing
    ssh melehost "docker exec ami_api_alpha python /tmp/cr136_backfill_portfolio_snapshots.py"

    # spot-check one user, full day-by-day series (still a dry run)
    ssh melehost "docker exec ami_api_alpha python /tmp/cr136_backfill_portfolio_snapshots.py --user-id <uuid>"

    # apply
    ssh melehost "docker exec ami_api_alpha python /tmp/cr136_backfill_portfolio_snapshots.py --apply"

Exit codes: 0 clean; 2 if any portfolio failed the terminal-state guard. Under
`--apply`, exit 2 does NOT mean nothing was written — portfolios that passed
the guard are committed, and only the failing ones are skipped and `!!`-flagged.
A walk that cannot reproduce the present has no business writing the past, so a
mismatch means a ledger anomaly wants eyes, not that the run should be rolled
back. Read the printed plan, not just the exit code.
"""

from __future__ import annotations

import argparse
import bisect
import sys
from datetime import date, datetime, timezone
from typing import NamedTuple, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select

from app.db.models import (
    PortfolioValueSnapshotRow,
    SimHoldingRow,
    SimPortfolioRow,
    SimTradeRow,
    User,
)
from app.db.session import get_sessionmaker
from app.trading_math.portfolio import drawdown_pct

# Script knobs, not engine pins — these do not belong in
# `portfolio_health_constants.py`, which holds the thresholds the engine and
# its rules are judged against.
_EPS = 1e-6            # share-count tolerance, matching `_apply_sell_row`
_CASH_TOL = 0.05       # dollars; the walk rounds to 2 dp exactly as the engine does
_BACKFILL_SOURCE = "yahoo_backfill"   # provenance and backfill marker in one string
_BENCHMARK = "SPY"
_SYNTHETIC_APP_VERSION = "room-benchmark"


# ── Price provider — the only I/O seam besides the DB ───────────────────────


class BackfillPriceProvider(Protocol):
    def unadjusted_daily(self, ticker: str, start: date) -> list[tuple[date, float]]:
        """Ascending (trading_date, unadjusted_close); [] on failure — never raises."""


class _YfinanceProvider:
    """Yahoo, unadjusted, with no fallback of any kind.

    Deliberately NOT `get_market_data_provider()`: its `FallbackProvider` ends
    in a deterministic mock walk, so a transient Yahoo failure would silently
    persist fabricated bars into a table the Tier-2 tiles read as realised
    history. An empty grid and a loud no-op is the honest failure (CR040).
    """

    def __init__(self) -> None:
        # Keyed by (ticker, start), not by ticker. A ticker-only key returns
        # the FIRST caller's window to every later caller, so two portfolios
        # holding the same name with different first-trade dates would leave
        # the later one silently short of its own early history — measured:
        # five days valued at the last execution price instead of the market
        # close, `terminal OK`, exit 0, and permanent, because §3.8 never
        # updates an existing row. `_run` also asks every ticker for the
        # run-global earliest date, so in practice there is one window per
        # ticker per run; this key is what makes that a property of the cache
        # rather than a convention the caller has to remember.
        self._cache: dict[tuple[str, date], list[tuple[date, float]]] = {}

    def unadjusted_daily(self, ticker: str, start: date) -> list[tuple[date, float]]:
        key = (ticker, start)
        if key in self._cache:
            return self._cache[key]
        series: list[tuple[date, float]] = []
        try:
            import yfinance as yf

            frame = yf.Ticker(ticker).history(
                start=start.isoformat(), interval="1d", auto_adjust=False,
            )
            by_day: dict[date, float] = {}
            if frame is not None and not frame.empty:
                for stamp, row in frame.iterrows():
                    close = row["Close"]
                    if close is None:
                        continue
                    # Last bar wins on a duplicate date. Trading days exist by
                    # the presence of a bar — no calendar maths anywhere.
                    by_day[stamp.date()] = float(close)
            series = sorted(by_day.items())
        except Exception as exc:   # noqa: BLE001 — a bad ticker must not kill the run
            print(f"  !! price fetch failed for {ticker}: {exc}")
        if not series:
            print(f"  !! no unadjusted bars for {ticker} — it will be ledger-priced")
        self._cache[key] = series
        return series


def trading_day_grid(
    provider: BackfillPriceProvider, start: date,
) -> list[date]:
    """The NYSE session calendar, as SPY's own bar dates.

    SPY trades every session, so its bars ARE the trading-day grid — the same
    convention M01 uses, and the reason there is no holiday table anywhere in
    CR136.
    """
    return [day for day, _close in provider.unadjusted_daily(_BENCHMARK, start)]


# ── Pure reconstruction core (no DB, no network) ────────────────────────────


class _Event(NamedTuple):
    ts: datetime
    rank: int
    trade_id: str
    kind: str        # "buy" | "sell" | "close"
    ticker: str
    qty: float
    price: float


class DayValue(NamedTuple):
    as_of: date
    total_value: float
    cash: float
    invested_value: float


class TerminalState(NamedTuple):
    holdings: dict[str, float]
    cash: float


def _as_utc(value: datetime) -> datetime:
    """Sqlite hands back naive datetimes; Postgres hands back aware ones. Sorting
    a mixed list raises, so everything is normalised on the way in."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def events_from_trades(trades) -> tuple[list[_Event], list[str]]:
    """The ledger as an ordered event stream, plus any anomaly lines.

    Three event kinds, and the ranks give same-timestamp determinism:
    buy-open (0) at `opened_at`, sell-open (1) at `opened_at`, buy-close (2) at
    `closed_at`. SELL rows are created "open" and never transition — that is
    load-bearing here and is itself guarded by
    `test_def110_backfill.py::test_sell_trade_rows_stay_open_forever`.
    """
    events: list[_Event] = []
    anomalies: list[str] = []

    for t in trades:
        side = t.side.value if hasattr(t.side, "value") else str(t.side)
        ticker = str(t.ticker)
        qty = float(t.quantity)
        trade_id = str(t.id)

        if side == "sell":
            events.append(_Event(
                ts=_as_utc(t.opened_at), rank=1, trade_id=trade_id, kind="sell",
                ticker=ticker, qty=qty, price=float(t.entry_price),
            ))
            continue

        events.append(_Event(
            ts=_as_utc(t.opened_at), rank=0, trade_id=trade_id, kind="buy",
            ticker=ticker, qty=qty, price=float(t.entry_price),
        ))
        if str(t.status) == "open":
            continue
        if t.closed_at is None or t.closed_price is None:
            # A ledger anomaly, not a pricing question: the close cannot be
            # placed in time or priced. Skipping it leaves the shares held, so
            # the terminal guard catches the drift and refuses the portfolio.
            anomalies.append(
                f"  !! trade {trade_id} ({ticker}) is {t.status} with "
                f"closed_at={t.closed_at} closed_price={t.closed_price} — "
                f"close event skipped"
            )
            continue
        events.append(_Event(
            ts=_as_utc(t.closed_at), rank=2, trade_id=trade_id, kind="close",
            ticker=ticker, qty=qty, price=float(t.closed_price),
        ))

    events.sort(key=lambda e: (e.ts, e.rank, e.trade_id))
    return events, anomalies


def _apply(
    event: _Event, holdings: dict[str, float], cash: float,
) -> float:
    """One event against the running book. Cash rounds to 2 dp after every
    apply, exactly as `_apply_buy_row` / `_apply_sell_row` do, so terminal cash
    matches the live column rather than merely approaching it."""
    if event.kind == "buy":
        holdings[event.ticker] = holdings.get(event.ticker, 0.0) + event.qty
        return round(cash - event.price * event.qty, 2)

    # Sells and closes are clamped to what is actually held (DEF166): the live
    # engine credits cash only for shares it could sell, and a walk that sold
    # more would drift from the ledger it is trying to reproduce.
    held = holdings.get(event.ticker, 0.0)
    sold = min(event.qty, held)
    if sold <= _EPS:
        return cash
    remaining = held - sold
    if remaining > _EPS:
        holdings[event.ticker] = remaining
    else:
        holdings.pop(event.ticker, None)
    return round(cash + event.price * sold, 2)


def _close_on_or_before(
    index: tuple[list[date], list[float]], day: date,
) -> tuple[float, bool]:
    """(close, was_carried_forward). The last bar on a date ≤ `day`; a halt or a
    missing bar carries the previous close forward rather than dropping the
    holding out of the valuation. The date list is prebuilt once per ticker —
    rebuilding it per lookup would make the bisect pointless."""
    days, closes = index
    position = bisect.bisect_right(days, day)
    if position == 0:
        return (0.0, False)
    return (closes[position - 1], days[position - 1] != day)


def reconstruct_daily_values(
    events: list[_Event],
    grid_days: list[date],
    prices: dict[str, list[tuple[date, float]]],
    starting_capital: float,
) -> tuple[list[DayValue], TerminalState, dict[str, int]]:
    """The whole walk: ledger in, one value row per trading day out.

    Deterministic and side-effect free, which is what makes it the thing the
    unit tests actually exercise — the DB and the network are both seams
    outside it.
    """
    holdings: dict[str, float] = {}
    cash = float(starting_capital)
    last_event_price: dict[str, float] = {}
    stats = {"carried_forward": 0, "ledger_priced": 0}
    rows: list[DayValue] = []
    cursor = 0
    indexed = {
        ticker: ([d for d, _ in series], [c for _, c in series])
        for ticker, series in prices.items()
    }
    empty: tuple[list[date], list[float]] = ([], [])

    for day in grid_days:
        while cursor < len(events) and events[cursor].ts.date() <= day:
            event = events[cursor]
            cash = _apply(event, holdings, cash)
            last_event_price[event.ticker] = event.price
            cursor += 1

        invested = 0.0
        for ticker, qty in holdings.items():
            close, carried = _close_on_or_before(indexed.get(ticker, empty), day)
            if close <= 0.0:
                # No bar for this ticker on or before `day` at all. The most
                # recent execution price is the only defensible number left,
                # and it is counted so the plan says so out loud.
                close = last_event_price.get(ticker, 0.0)
                stats["ledger_priced"] += 1
            elif carried:
                stats["carried_forward"] += 1
            invested += qty * close

        rows.append(DayValue(
            as_of=day,
            total_value=round(cash + invested, 2),
            cash=round(cash, 2),
            invested_value=round(invested, 2),
        ))

    # Events after the last grid day (today's trades) still belong to the
    # terminal state, which is compared against the live DB, not against the
    # last row written.
    while cursor < len(events):
        cash = _apply(events[cursor], holdings, cash)
        cursor += 1

    return rows, TerminalState(holdings=dict(holdings), cash=cash), stats


def terminal_mismatches(
    state: TerminalState, holding_rows, current_cash: float,
) -> list[str]:
    """[] when the walk reproduced the present, else one line per discrepancy.

    This is def110's `expected()` identity generalised to every day: if the
    reconstruction cannot land on today's holdings and today's cash, its
    reconstruction of last month is not evidence of anything.
    """
    lines: list[str] = []
    live = {str(h.ticker): float(h.quantity) for h in holding_rows}

    for ticker in sorted(set(live) | set(state.holdings)):
        walked = state.holdings.get(ticker, 0.0)
        actual = live.get(ticker, 0.0)
        if abs(walked - actual) > _EPS:
            lines.append(
                f"  !! {ticker}: walk holds {walked:.4f}, sim_holdings has "
                f"{actual:.4f}"
            )

    if abs(state.cash - float(current_cash)) > _CASH_TOL:
        lines.append(
            f"  !! cash: walk has {state.cash:.2f}, current_cash is "
            f"{float(current_cash):.2f}"
        )
    return lines


# ── DB-facing run ───────────────────────────────────────────────────────────


class _PortfolioResult(NamedTuple):
    line: str
    detail: list[str]
    series: list[DayValue]
    planned: int
    inserted: int
    skipped_existing: int
    mismatched: bool
    skipped_no_trades: bool


def _first_event_date(events: list[_Event]) -> date | None:
    return events[0].ts.date() if events else None


def _run(
    session,
    provider: BackfillPriceProvider,
    user_id: UUID | None,
    today: date,
) -> tuple[list[_PortfolioResult], list[date]]:
    query = select(SimPortfolioRow)
    if user_id is not None:
        query = query.where(SimPortfolioRow.user_id == user_id)
    portfolios = session.execute(query).scalars().all()

    synthetic: set[UUID] = set()
    if portfolios:
        rows = session.execute(
            select(User.id).where(
                User.id.in_([p.user_id for p in portfolios]),
                User.last_app_version == _SYNTHETIC_APP_VERSION,
            )
        ).scalars().all()
        synthetic = set(rows)

    # One pass to find the earliest event across everything in scope, so the
    # grid and every price series are fetched exactly once per run.
    ledgers: dict[UUID, list[_Event]] = {}
    anomalies: dict[UUID, list[str]] = {}
    earliest: date | None = None
    for p_row in portfolios:
        trades = session.execute(
            select(SimTradeRow).where(SimTradeRow.portfolio_id == p_row.id)
        ).scalars().all()
        events, notes = events_from_trades(trades)
        ledgers[p_row.id] = events
        anomalies[p_row.id] = notes
        first = _first_event_date(events)
        if first is not None and (earliest is None or first < earliest):
            earliest = first

    # No events anywhere means no grid to fetch — every portfolio then falls
    # through the no-trades branch below, marker and all, rather than through a
    # second early-return path that would have to repeat the same formatting.
    grid: list[date] = []
    if earliest is not None:
        # Today is excluded: M03's live tick owns today's row, and today's bar
        # may still be forming.
        grid = [d for d in trading_day_grid(provider, earliest) if d < today]

    results: list[_PortfolioResult] = []
    for p_row in portfolios:
        events = ledgers[p_row.id]
        detail = list(anomalies[p_row.id])
        marker = " [synthetic]" if p_row.user_id in synthetic else ""

        if not events:
            results.append(_PortfolioResult(
                line=f"user {p_row.user_id}{marker}  no trades — skipped",
                detail=detail, series=[], planned=0, inserted=0,
                skipped_existing=0, mismatched=False, skipped_no_trades=True,
            ))
            continue

        first = _first_event_date(events)
        days = [d for d in grid if first is not None and d >= first]

        # Every ticker is fetched from the RUN-GLOBAL earliest date, not this
        # portfolio's own. Asking per portfolio means one window per
        # (ticker, portfolio) and re-fetching a popular name once per holder;
        # asking once from `earliest` gives every portfolio a series that
        # already covers its own range.
        prices: dict[str, list[tuple[date, float]]] = {}
        for ticker in sorted({e.ticker for e in events}):
            prices[ticker] = provider.unadjusted_daily(ticker, earliest)

        series, terminal, stats = reconstruct_daily_values(
            events, days, prices, float(p_row.starting_capital),
        )

        holding_rows = session.execute(
            select(SimHoldingRow).where(SimHoldingRow.portfolio_id == p_row.id)
        ).scalars().all()
        mismatches = terminal_mismatches(
            terminal, holding_rows, float(p_row.current_cash),
        )
        detail.extend(mismatches)

        span = (
            f"days {series[0].as_of}..{series[-1].as_of}" if series
            else "days none"
        )
        if mismatches:
            # Nothing is written for a portfolio whose walk cannot reproduce
            # the present.
            results.append(_PortfolioResult(
                line=(
                    f"user {p_row.user_id}{marker}  {span}  planned 0  "
                    f"inserted 0  skipped_existing 0  carried_forward "
                    f"{stats['carried_forward']}  ledger_priced "
                    f"{stats['ledger_priced']}  terminal !!"
                ),
                detail=detail, series=series, planned=0, inserted=0,
                skipped_existing=0, mismatched=True, skipped_no_trades=False,
            ))
            continue

        existing = set(session.execute(
            select(PortfolioValueSnapshotRow.as_of).where(
                PortfolioValueSnapshotRow.portfolio_id == p_row.id
            )
        ).scalars().all())

        inserted = 0
        skipped_existing = 0
        captured_at = datetime.now(timezone.utc)
        for row in series:
            if row.as_of in existing:
                # Never an update. A live row carries live marks and an F16
                # prediction; overwriting it with a reconstruction would trade
                # recorded truth for a re-derivation. A prior backfill's row is
                # byte-identical anyway, by determinism.
                skipped_existing += 1
                continue
            session.add(PortfolioValueSnapshotRow(
                id=uuid4(),
                user_id=p_row.user_id,
                portfolio_id=p_row.id,
                as_of=row.as_of,
                total_value=row.total_value,
                cash=row.cash,
                invested_value=row.invested_value,
                # vs-STARTING-CAPITAL, floored at 0 — the same quantity live
                # rows carry. NOT peak-to-trough; see the module docstring.
                drawdown_pct=drawdown_pct(
                    float(p_row.starting_capital), row.total_value,
                ),
                source=_BACKFILL_SOURCE,
                captured_at=captured_at,
                # No engine ran historically.
                predicted_vol_ann=None,
                n_observations=None,
                engine_version=None,
            ))
            inserted += 1

        # Flush here, not at the end: a constraint violation should name the
        # portfolio that caused it.
        #
        # There is deliberately NO per-row `IntegrityError` catch. The obvious
        # way to write one is a SAVEPOINT per row, and under pysqlite a
        # SAVEPOINT implicitly commits the pending transaction — measured: with
        # `begin_nested()` in place, a DRY RUN wrote all ten rows and the
        # closing `rollback()` did nothing. The dry run's promise is the more
        # important property of the two, so a duplicate now aborts the whole
        # run loudly with nothing committed. It can only arise from a second
        # concurrent `--apply` of this same script: `uq_pvs_portfolio_asof`'s
        # other writer is M03's tick, which only ever writes TODAY, and today
        # is excluded from the grid by construction.
        session.flush()

        results.append(_PortfolioResult(
            line=(
                f"user {p_row.user_id}{marker}  {span}  planned {len(series)}  "
                f"inserted {inserted}  skipped_existing {skipped_existing}  "
                f"carried_forward {stats['carried_forward']}  ledger_priced "
                f"{stats['ledger_priced']}  terminal OK"
            ),
            detail=detail, series=series, planned=len(series), inserted=inserted,
            skipped_existing=skipped_existing, mismatched=False,
            skipped_no_trades=False,
        ))

    return results, grid


def main(
    argv: list[str] | None = None,
    provider: BackfillPriceProvider | None = None,
) -> int:
    ap = argparse.ArgumentParser(description="CR136 M10 portfolio-snapshot backfill")
    ap.add_argument(
        "--apply", action="store_true",
        help="commit the inserts (default is a dry run that rolls back)",
    )
    ap.add_argument(
        "--user-id", type=str, default=None,
        help="one user — prints the full day-by-day series (spot-check mode)",
    )
    args = ap.parse_args(argv)

    user_id = UUID(args.user_id) if args.user_id else None
    provider = provider or _YfinanceProvider()
    today = datetime.now(timezone.utc).date()

    session = get_sessionmaker()()
    try:
        results, grid = _run(session, provider, user_id, today)

        mode = "APPLY" if args.apply else "DRY RUN"
        print(f"CR136 M10 portfolio-snapshot backfill — {mode}")
        print("-" * 78)
        if grid:
            print(
                f"trading-day grid ({_BENCHMARK}): {len(grid)} days "
                f"{grid[0]}..{grid[-1]}  (today {today} excluded)"
            )
        else:
            print("trading-day grid: EMPTY — nothing can be valued this run")
        print("-" * 78)

        for result in results:
            print(result.line)
            for line in result.detail:
                print(line)
            if user_id is not None and result.series:
                print("  as_of        total_value        cash   invested_value")
                for row in result.series:
                    print(
                        f"  {row.as_of}  {row.total_value:>12.2f}  "
                        f"{row.cash:>10.2f}  {row.invested_value:>14.2f}"
                    )

        scanned = len(results)
        no_trades = sum(1 for r in results if r.skipped_no_trades)
        mismatched = sum(1 for r in results if r.mismatched)
        planned = sum(r.planned for r in results)
        inserted = sum(r.inserted for r in results)
        skipped = sum(r.skipped_existing for r in results)

        print("-" * 78)
        print(f"  portfolios scanned      : {scanned}")
        print(f"  skipped (no trades)     : {no_trades}")
        print(f"  TERMINAL MISMATCH       : {mismatched}")
        print(f"  rows planned            : {planned}")
        print(f"  rows inserted           : {inserted}")
        print(f"  rows skipped (existing) : {skipped}")

        if args.apply:
            session.commit()
            print("\ncommitted.")
        else:
            session.rollback()
            print("\nrolled back — re-run with --apply to write.")
        return 2 if mismatched else 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
