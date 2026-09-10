"""CR222 §4 — behaviour diagnostics for every training user.

CR131 built a measured before/after comparison for one cohort — users who
switched on the Day Trader preset (CR129). The modal loser in the retail-
trading evidence is not that cohort; it is the ordinary household trading at
~75% annual turnover with no preset at all (Barber & Odean 2000). This module
generalises CR131's instrument to ANY training user, over their whole trade
log and NAV series, and is the single owner of every measure both call sites
publish: `day_trader_outcomes.py` calls into it rather than keeping its own
copy (see `turnover` below for the one place its definition had to be
parameterised, not duplicated, to stay byte-identical).

Four measures, all over the TRAINING ledger only (`training_trade_scope`,
DEF269 — a game run must never read as this user's own practice behaviour):

  * **Annualised turnover** — Barber & Odean's own metric: average of gross
    buy and sell notional in the window, as a fraction of starting capital,
    annualised. Lifted verbatim from `day_trader_outcomes._window_summary`'s
    `turnover_pct` arithmetic (see that function's own comment for why the
    denominator is the fixed starting capital rather than a time-weighted
    average portfolio value).
  * **Median holding period** — calendar days between a closed lot's entry
    and its close, over every closed lot across every ticker the user has
    traded, pooled. Reconstructed per ticker via `_closing_events_by_ticker`
    below, the same disjoint-records FIFO reconciliation `cost_basis_lots.py`
    documents (an explicit sell draws down open lots FIFO; a self-closed buy
    closes its own remainder and never emits a sell row) — walked directly
    against the audited `fifo_sell` primitive rather than through
    `cost_basis_lots.compute_lots_fifo`, because this module needs each
    closing EVENT's own date, and `compute_lots_fifo` reports only each
    lot's final aggregate. Median rather than mean because a handful of
    same-day round trips would otherwise pull a mean holding period down to
    a number that describes almost none of the user's actual positions.
  * **Attention-trade share** — the fraction of BUYs placed either within 5
    TRADING days of a >=10% absolute price move in the same ticker, or
    within 1 CALENDAR day of a Room convene on that ticker (`room_runs`,
    `RoomRunRow.triggered_at` — the moment the user asked the Room to look,
    which is the behaviourally relevant "attention" instant, independent of
    whether that specific run finished or the trade cites it via
    `verdict_ref`). "Trading days" here means rows that exist in
    `price_history_daily` for that ticker, ordered by date — the codebase
    imports no trading calendar anywhere (see that table's own docstring),
    so a lookback of 5 trading days is 5 PRICE ROWS back, not 5 calendar
    days back.
  * **Disposition ratio (PGR/PLR, Odean 1998)** — proportion of gains
    realised vs proportion of losses realised. Odean's own definition:
    PGR = realised gains / (realised gains + paper gains), and likewise for
    losses, summed over every SALE in the window and every position that was
    open (elsewhere in the account) at the moment of that sale.

    **The standard closed-lot approximation, stated because the CR asked for
    it to be:** a full Odean replication marks every open lot to market on
    every trading day and classifies the paper gain/loss it carries that day.
    This module does not carry a daily portfolio revaluation loop — nothing
    in Portfolio Health does either (CR222 Corrections §6, no bootstrap) — so
    it approximates at SALE-EVENT resolution instead: for each closing event
    (an explicit sell, or a buy that self-closed via stop/target/manual), the
    realised leg is classified at its own realised_pnl sign, and every OTHER
    lot open across every ticker AT THAT INSTANT is priced at the closing
    event's own ticker's price on record nearest that date where the other
    lot's own ticker has one (`price_history_daily`, nearest close on or
    before the sale date), classified paper-gain or paper-loss against that
    lot's entry price, and folded into the same day's denominator. A lot
    whose ticker has no price on record for that window is a NAMED absence
    (excluded from that sale's paper terms, not priced at zero or at the
    entry price) — degrade loudly (CR040), never a silent zero gain.

**Honesty rules are CR131's, unchanged, restated here because this module is
the second place they apply.** Below `MIN_TRADES_FOR_DIAGNOSTICS` closed lots
or `MIN_ELAPSED_DAYS` days since the user's first training trade, the block is
`too_early` with `{status, message}` only — no numeric figure anywhere in the
payload, not a trade count, not a zero. No grade, no warning, no moralising on
the `ready` payload; identical shape for a good number and a bad one. Every
measure ships beside its own published-baseline citation in
`PUBLISHED_BASELINES` (extended here, from `day_trader_outcomes.py`'s
register — never a second copy).
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from statistics import median
from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.db import get_session
from app.db.models import PriceHistoryDailyRow, RoomRunRow, SimPortfolioRow, SimTradeRow
from app.services.sim_engine import training_trade_scope
from app.trading_math.cost_basis import fifo_sell

# `day_trader_outcomes.py` imports `turnover` (below) from THIS module, so a
# module-level `from app.services.day_trader_outcomes import
# PUBLISHED_BASELINES` here would be circular — Python would be asked to
# finish initialising a module it is still in the middle of importing.
# Deferred into `_published_baselines()` instead, called once inside
# `compute_behaviour_diagnostics` rather than at import time.

DAYS_PER_YEAR = 365.25

# ── Honesty thresholds — CR131's, restated for the whole-population block ──
#
# These mirror `settings.min_trades_for_diagnostics` /
# `settings.min_elapsed_days_for_diagnostics` (`app/core/config.py`) and exist
# as plain module constants ONLY as the fixed fallback `compute_behaviour_
# diagnostics` uses if `app.core.config.settings` is unavailable for any
# reason — the live values always come from Settings, unlike CR131's own
# `MIN_TRADES_FOR_COMPARISON` (a fixed constant with no config knob). CR222
# asked for these two specifically to be config-driven.
MIN_TRADES_FOR_DIAGNOSTICS = 10
MIN_ELAPSED_DAYS = 60

# Mirrors day_trader_outcomes.py's own fallback constant — used only if a
# user somehow has trades but no portfolio row.
_DEFAULT_STARTING_CAPITAL = 10_000.0

# Attention-trade windows (CR222 §4).
ATTENTION_MOVE_LOOKBACK_TRADING_DAYS = 5
ATTENTION_MOVE_THRESHOLD_PCT = 10.0
ATTENTION_CONVENE_LOOKBACK_CALENDAR_DAYS = 1

STATUS_TOO_EARLY = "too_early"
STATUS_READY = "ready"

BEHAVIOUR_METRIC = "behaviour"


# ── Published baselines — EXTENDS day_trader_outcomes.PUBLISHED_BASELINES ──
#
# The two new entries CR222 §4 needs (turnover already has a citation in the
# imported dict; disposition did not). Merged onto the CR131 register by
# `_published_baselines()` below — never a second copy of that register.
_NEW_BASELINES = {
    "barber_odean_2000_turnover": {
        "provenance": (
            "Barber & Odean, \"Trading Is Hazardous to Your Wealth\", Journal "
            "of Finance 2000. 66,465 US retail household brokerage accounts, "
            "1991-1996."
        ),
        "average_household_annual_turnover_pct": 75.0,
        "most_active_quintile_annual_turnover_pct": 250.0,
    },
    "odean_1998_disposition": {
        "provenance": (
            "Odean, \"Are Investors Reluctant to Realize Their Losses?\", "
            "Journal of Finance 1998. 10,000 US retail brokerage accounts, "
            "1987-1993."
        ),
        "proportion_gains_realised": 0.148,
        "proportion_losses_realised": 0.098,
    },
}


def _published_baselines() -> dict:
    """CR131's `PUBLISHED_BASELINES` register, extended — imported here
    rather than at module load time (see the import-order note above) so
    that importing THIS module never requires `day_trader_outcomes.py` to
    already be fully initialised. The single register CR131 built stays the
    single register: this only ever reads it, never redefines it."""
    from app.services.day_trader_outcomes import PUBLISHED_BASELINES as _day_trader_baselines

    return {**_day_trader_baselines, **_NEW_BASELINES}


def __getattr__(name: str):
    """PEP 562 module `__getattr__` — makes `PUBLISHED_BASELINES` readable as
    a plain module attribute (`behaviour_diagnostics.PUBLISHED_BASELINES`,
    the same shape `day_trader_outcomes.PUBLISHED_BASELINES` already has) for
    every caller EXCEPT `day_trader_outcomes.py` itself, without evaluating
    `_published_baselines()` — and therefore importing that module — at this
    module's own import time, which is what the circular import forbids."""
    if name == "PUBLISHED_BASELINES":
        return _published_baselines()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _as_utc(value: datetime) -> datetime:
    """Same guard as day_trader_outcomes._as_utc / journal_store._as_utc:
    SQLite drops tzinfo, Postgres keeps it."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@dataclass(frozen=True)
class _Trade:
    id: str
    ticker: str
    side: str
    quantity: float
    entry_price: float
    opened_at: datetime
    closed_at: datetime | None
    status: str
    realised_pnl: float


def _load_all_trades(user_id: UUID) -> list[_Trade]:
    with get_session() as s:
        rows = (
            s.execute(
                select(SimTradeRow)
                .where(training_trade_scope(user_id))
                .order_by(SimTradeRow.opened_at.asc())
            )
            .scalars()
            .all()
        )
        return [
            _Trade(
                id=str(r.id),
                ticker=str(r.ticker),
                side=str(r.side),
                quantity=float(r.quantity),
                entry_price=float(r.entry_price),
                opened_at=_as_utc(r.opened_at),
                closed_at=_as_utc(r.closed_at) if r.closed_at is not None else None,
                status=str(r.status),
                realised_pnl=float(r.realised_pnl or 0),
            )
            for r in rows
        ]


def _starting_capital(user_id: UUID) -> float:
    with get_session() as s:
        row = s.execute(
            select(SimPortfolioRow).where(
                SimPortfolioRow.user_id == user_id,
                SimPortfolioRow.kind == "training",
            )
        ).scalar_one_or_none()
        return float(row.starting_capital) if row is not None else _DEFAULT_STARTING_CAPITAL


# ── Turnover — the shared definition (CR131's `_window_summary` arithmetic) ─


@dataclass(frozen=True)
class TurnoverResult:
    """Both the raw (un-annualised) and annualised figures — `_window_summary`
    publishes `turnover_pct` and `turnover_pct_annualised` as two distinct
    fields on its `ready` payload, so the shared function has to hand both
    back rather than force `day_trader_outcomes.py` to re-derive one from the
    other (the same `round()` applied twice can disagree with rounding once)."""

    turnover_pct: float
    turnover_pct_annualised: float


def turnover(
    trades: list, *, window_days: float, starting_capital: float,
) -> TurnoverResult:
    """Barber & Odean's own metric, lifted verbatim from
    `day_trader_outcomes._window_summary`: average of gross buy and sell
    notional in the window, as a fraction of starting capital, then
    annualised by `DAYS_PER_YEAR / window_days`.

    `trades` are anything exposing `.side` ('buy'/'sell'), `.quantity` and
    `.entry_price` — both this module's own `_Trade` and
    `day_trader_outcomes._Trade` satisfy that, which is what lets
    `day_trader_outcomes.py` call this instead of keeping its own copy.
    `window_days` must already be >= the caller's own elapsed-time floor;
    this function does not itself refuse a thin window (both callers gate on
    their own honesty threshold before reaching here).
    """
    if not starting_capital:
        return TurnoverResult(turnover_pct=0.0, turnover_pct_annualised=0.0)
    buy_notional = sum(t.quantity * t.entry_price for t in trades if t.side == "buy")
    sell_notional = sum(t.quantity * t.entry_price for t in trades if t.side == "sell")
    avg_side_notional = (buy_notional + sell_notional) / 2.0
    turnover_pct = avg_side_notional / starting_capital * 100.0
    annualise = DAYS_PER_YEAR / window_days if window_days > 0 else 0.0
    return TurnoverResult(
        turnover_pct=round(turnover_pct, 2),
        turnover_pct_annualised=round(turnover_pct * annualise, 2),
    )


# ── Median holding period ───────────────────────────────────────────────────


def _median_holding_period_days(trades: list[_Trade]) -> float | None:
    """Calendar days between a closed lot's entry and its close, pooled
    across every ticker, median rather than mean (see module docstring).

    Built from `_closing_events_by_ticker`, which both this and
    `_disposition_ratio` share for event-level (not merely per-lot
    aggregate) dates — see that function's own docstring for why it walks
    `fifo_sell` directly rather than going through
    `cost_basis_lots.compute_lots_fifo`.
    """
    holds: list[float] = []
    for _ticker, events in _closing_events_by_ticker(trades).items():
        for ev in events:
            holds.append((ev.close_date - ev.entry_date).days)
    if not holds:
        return None
    return round(median(holds), 2)


# ── Closing-event reconstruction (shared by holding-period + disposition) ──


@dataclass(frozen=True)
class _ClosingEvent:
    """One FIFO-matched close: a slice of an open lot realised at one instant.

    `entry_date`/`close_date` are the CALENDAR dates (not datetimes) the lot
    opened and this slice closed, for calendar-day holding-period arithmetic.
    `close_at` keeps the full timestamp for chronological ordering against
    other tickers' events when building the disposition ratio.
    """

    ticker: str
    entry_date: date
    close_date: date
    close_at: datetime
    quantity_closed: float
    realised_pnl: float


def _closing_events_by_ticker(trades: list[_Trade]) -> dict[str, list[_ClosingEvent]]:
    """Every FIFO-matched closing event, one ticker's trade history at a
    time — the same disjoint-records reconciliation `cost_basis_lots.py`
    documents (an explicit sell draws down open lots FIFO; a self-closed buy
    closes its own remainder and never emits a sell row), applied here to
    also capture each event's OWN close date rather than only the lot's
    final aggregate."""
    by_ticker: dict[str, list[_Trade]] = {}
    for t in trades:
        by_ticker.setdefault(t.ticker, []).append(t)

    out: dict[str, list[_ClosingEvent]] = {}
    for ticker, ticker_trades in by_ticker.items():
        out[ticker] = _closing_events_one_ticker(ticker, ticker_trades)
    return out


def _closing_events_one_ticker(ticker: str, trades: list[_Trade]) -> list[_ClosingEvent]:
    # Open lots as a mutable queue of [entry_date, entry_price, quantity_open],
    # oldest first — mirrors cost_basis_lots._LotAcc, trimmed to the fields
    # this walk needs.
    lots: list[dict] = []
    events: list[_ClosingEvent] = []

    # Same event-stream construction as cost_basis_lots._event_stream: a buy
    # opens at `opened_at`; a self-closed buy (won/lost/closed) ALSO closes
    # its own remainder at `closed_at`; an explicit sell closes at its own
    # `opened_at` (sells are never themselves close targets — DEF319).
    stream: list[tuple[int, datetime, str, _Trade]] = []
    for t in trades:
        if t.side == "buy":
            stream.append((0, t.opened_at, t.id, t))
            if t.status.lower() in {"won", "lost", "closed"}:
                closed_at = t.closed_at or t.opened_at
                stream.append((2, closed_at, t.id, t))
        elif t.side == "sell":
            stream.append((1, t.opened_at, t.id, t))
        else:
            logger.warn("behaviour_diagnostics_unknown_side", side=t.side, trade_id=t.id)
    stream.sort(key=lambda e: (e[1], e[0], e[2]))

    by_id: dict[str, dict] = {}
    for kind, ts, _seq, t in stream:
        if kind == 0:
            lot = {
                "entry_date": t.opened_at.date(),
                "entry_price": t.entry_price,
                "quantity_open": t.quantity,
            }
            lots.append(lot)
            by_id[t.id] = lot
        elif kind == 1:
            open_refs = [lot for lot in lots if lot["quantity_open"] > 1e-9]
            snapshot = [(lot["quantity_open"], lot["entry_price"]) for lot in open_refs]
            result = fifo_sell(snapshot, t.quantity, t.entry_price)
            if result is None:
                logger.warn(
                    "behaviour_diagnostics_fifo_sell_rejected",
                    ticker=ticker, trade_id=t.id,
                )
                continue
            for i, close in enumerate(result.closes):
                lot = open_refs[i]
                lot["quantity_open"] = round(lot["quantity_open"] - close.quantity_closed, 6)
                events.append(_ClosingEvent(
                    ticker=ticker,
                    entry_date=lot["entry_date"],
                    close_date=ts.date(),
                    close_at=ts,
                    quantity_closed=close.quantity_closed,
                    realised_pnl=round(close.realised_pnl, 2),
                ))
        elif kind == 2:
            lot = by_id.get(t.id)
            if lot is None or lot["quantity_open"] <= 1e-9:
                continue
            events.append(_ClosingEvent(
                ticker=ticker,
                entry_date=lot["entry_date"],
                close_date=ts.date(),
                close_at=ts,
                quantity_closed=lot["quantity_open"],
                realised_pnl=round(t.realised_pnl, 2),
            ))
            lot["quantity_open"] = 0.0
    return events


# ── Disposition ratio (Odean 1998, closed-lot approximation) ───────────────


def _price_rows(ticker: str) -> list[tuple[date, float]]:
    with get_session() as s:
        rows = s.execute(
            select(PriceHistoryDailyRow)
            .where(PriceHistoryDailyRow.ticker == ticker)
            .order_by(PriceHistoryDailyRow.date.asc())
        ).scalars().all()
    return [(r.date, float(r.adj_close)) for r in rows]


def _price_on_or_before(dates: list[date], closes: list[float], as_of: date) -> float | None:
    """The last stored close on or before `as_of` — degrade loudly by
    returning None (never 0.0, never the entry price) when there is none."""
    idx = bisect_right(dates, as_of) - 1
    if idx < 0:
        return None
    return closes[idx]


def _disposition_ratio(trades: list[_Trade]) -> dict:
    """Odean 1998's PGR/PLR, at sale-event resolution (see module docstring
    for the closed-lot approximation this implements and why).

    Returns `{pgr, plr, realised_gains_count, paper_gains_count,
    realised_losses_count, paper_losses_count, priced_lots_excluded}` — the
    last a NAMED count of open lots (elsewhere in the account, at a sale's
    own instant) that were excluded from that sale's paper terms because
    their own ticker had no stored price on or before the sale date. It is
    not folded into either denominator silently.
    """
    events_by_ticker = _closing_events_by_ticker(trades)
    all_events = sorted(
        (ev for events in events_by_ticker.values() for ev in events),
        key=lambda e: e.close_at,
    )
    if not all_events:
        return {
            "pgr": None, "plr": None,
            "realised_gains_count": 0, "paper_gains_count": 0,
            "realised_losses_count": 0, "paper_losses_count": 0,
            "priced_lots_excluded": 0,
        }

    # Every OTHER open lot, across every ticker, as of each sale's own
    # instant — reconstructed once per ticker via _closing_events (which
    # already carries entry_date and quantity_closed per event, so the
    # REMAINING open quantity at time T is the lot's own buy minus every
    # close of it that happened at or before T). Built lazily from the raw
    # trades rather than from `_closing_events_by_ticker`'s output, because
    # an OPEN remainder (never closed) never appears as a `_ClosingEvent` at
    # all.
    by_ticker_trades: dict[str, list[_Trade]] = {}
    for t in trades:
        by_ticker_trades.setdefault(t.ticker, []).append(t)

    price_cache: dict[str, tuple[list[date], list[float]]] = {}

    def _prices_for(ticker: str) -> tuple[list[date], list[float]]:
        if ticker not in price_cache:
            rows = _price_rows(ticker)
            price_cache[ticker] = ([d for d, _ in rows], [c for _, c in rows])
        return price_cache[ticker]

    realised_gains = 0.0
    realised_losses = 0.0
    paper_gains = 0.0
    paper_losses = 0.0
    realised_gains_count = 0
    realised_losses_count = 0
    paper_gains_count = 0
    paper_losses_count = 0
    priced_lots_excluded = 0

    for ev in all_events:
        if ev.realised_pnl > 0:
            realised_gains += ev.realised_pnl
            realised_gains_count += 1
        elif ev.realised_pnl < 0:
            realised_losses += abs(ev.realised_pnl)
            realised_losses_count += 1
        # A breakeven close (realised_pnl == 0) contributes to neither side —
        # Odean's own definition classifies gains and losses, not flat exits.

        as_of = ev.close_date
        for ticker, ticker_trades in by_ticker_trades.items():
            open_lots = _open_lots_as_of(ticker_trades, as_of=ev.close_at)
            dates, closes = _prices_for(ticker)
            for lot_entry_price, lot_qty_open in open_lots:
                price = _price_on_or_before(dates, closes, as_of)
                if price is None:
                    priced_lots_excluded += 1
                    continue
                paper_pnl = (price - lot_entry_price) * lot_qty_open
                if paper_pnl > 0:
                    paper_gains += paper_pnl
                    paper_gains_count += 1
                elif paper_pnl < 0:
                    paper_losses += abs(paper_pnl)
                    paper_losses_count += 1

    pgr = (
        realised_gains / (realised_gains + paper_gains)
        if (realised_gains + paper_gains) > 0 else None
    )
    plr = (
        realised_losses / (realised_losses + paper_losses)
        if (realised_losses + paper_losses) > 0 else None
    )
    return {
        "pgr": round(pgr, 4) if pgr is not None else None,
        "plr": round(plr, 4) if plr is not None else None,
        "realised_gains_count": realised_gains_count,
        "paper_gains_count": paper_gains_count,
        "realised_losses_count": realised_losses_count,
        "paper_losses_count": paper_losses_count,
        "priced_lots_excluded": priced_lots_excluded,
    }


def _open_lots_as_of(trades: list[_Trade], *, as_of: datetime) -> list[tuple[float, float]]:
    """`(entry_price, quantity_open)` for every lot of ONE ticker still open
    at instant `as_of` — i.e. replay every event up to and including `as_of`
    and report what is left. Used only inside `_disposition_ratio`, where it
    is called once per (sale event, other ticker) pair; the trade lists here
    are one user's full history, never large enough for the O(events^2) cost
    to matter (the same asymptotic shape `_window_summary` already accepts)."""
    relevant = [t for t in trades if t.opened_at <= as_of]
    return _open_lots_after_replay(relevant, as_of=as_of)


def _open_lots_after_replay(trades: list[_Trade], *, as_of: datetime) -> list[tuple[float, float]]:
    lots: list[dict] = []
    by_id: dict[str, dict] = {}
    stream: list[tuple[int, datetime, str, _Trade]] = []
    for t in trades:
        if t.side == "buy":
            stream.append((0, t.opened_at, t.id, t))
            if t.status.lower() in {"won", "lost", "closed"} and t.closed_at is not None and t.closed_at <= as_of:
                stream.append((2, t.closed_at, t.id, t))
        elif t.side == "sell" and t.opened_at <= as_of:
            stream.append((1, t.opened_at, t.id, t))
    stream.sort(key=lambda e: (e[1], e[0], e[2]))

    for kind, _ts, _seq, t in stream:
        if kind == 0:
            lot = {"entry_price": t.entry_price, "quantity_open": t.quantity}
            lots.append(lot)
            by_id[t.id] = lot
        elif kind == 1:
            open_refs = [lot for lot in lots if lot["quantity_open"] > 1e-9]
            snapshot = [(lot["quantity_open"], lot["entry_price"]) for lot in open_refs]
            result = fifo_sell(snapshot, t.quantity, t.entry_price)
            if result is None:
                continue
            for i, close in enumerate(result.closes):
                open_refs[i]["quantity_open"] = round(
                    open_refs[i]["quantity_open"] - close.quantity_closed, 6,
                )
        elif kind == 2:
            lot = by_id.get(t.id)
            if lot is not None:
                lot["quantity_open"] = 0.0
    return [
        (lot["entry_price"], lot["quantity_open"])
        for lot in lots if lot["quantity_open"] > 1e-9
    ]


# ── Attention-trade share ───────────────────────────────────────────────────


def _convene_timestamps(user_id: UUID, ticker: str) -> list[datetime]:
    """Every `triggered_at` for a Room convene THIS user ran on THIS ticker —
    the moment the user asked the Room to look, which is the behaviourally
    relevant "attention" instant (CR222 §4), independent of whether that run
    finished or produced a verdict a trade later cites via `verdict_ref`."""
    with get_session() as s:
        rows = s.execute(
            select(RoomRunRow.triggered_at)
            .where(RoomRunRow.user_id == user_id)
            .where(RoomRunRow.ticker == ticker)
        ).scalars().all()
    return sorted(_as_utc(r) for r in rows)


def _moved_ge_threshold_within_lookback(
    dates: list[date], closes: list[float], *, buy_date: date,
) -> bool:
    """True if the ticker's adjusted close moved >= ATTENTION_MOVE_THRESHOLD_PCT
    in absolute value at any point in the ATTENTION_MOVE_LOOKBACK_TRADING_DAYS
    PRICE ROWS immediately before `buy_date` (rows on or before `buy_date`,
    since the buy itself cannot react to a move that has not printed yet).

    "Trading days" = rows in `price_history_daily` (see module docstring) —
    the row at `buy_date` (or the nearest one on/before it) and up to
    `ATTENTION_MOVE_LOOKBACK_TRADING_DAYS` rows back from there.
    """
    idx = bisect_right(dates, buy_date) - 1
    if idx < 0:
        return False
    window_start = max(0, idx - ATTENTION_MOVE_LOOKBACK_TRADING_DAYS)
    window = closes[window_start:idx + 1]
    if len(window) < 2:
        return False
    for i in range(1, len(window)):
        prior = window[i - 1]
        if prior == 0:
            continue
        move_pct = abs(window[i] - prior) / prior * 100.0
        if move_pct >= ATTENTION_MOVE_THRESHOLD_PCT:
            return True
    return False


def _attention_trade_share(user_id: UUID, trades: list[_Trade]) -> float | None:
    buys = [t for t in trades if t.side == "buy"]
    if not buys:
        return None

    triggered = 0
    price_cache: dict[str, tuple[list[date], list[float]]] = {}
    convene_cache: dict[str, list[datetime]] = {}

    for t in buys:
        ticker = t.ticker
        if ticker not in convene_cache:
            convene_cache[ticker] = _convene_timestamps(user_id, ticker)
        convenes = convene_cache[ticker]
        near_convene = any(
            timedelta(0) <= (t.opened_at - c) <= timedelta(
                days=ATTENTION_CONVENE_LOOKBACK_CALENDAR_DAYS,
            )
            for c in convenes
        )
        if near_convene:
            triggered += 1
            continue

        if ticker not in price_cache:
            rows = _price_rows(ticker)
            price_cache[ticker] = ([d for d, _ in rows], [c for _, c in rows])
        dates, closes = price_cache[ticker]
        if _moved_ge_threshold_within_lookback(dates, closes, buy_date=t.opened_at.date()):
            triggered += 1

    return round(triggered / len(buys) * 100.0, 2)


# ── Public entry point ──────────────────────────────────────────────────────


def compute_behaviour_diagnostics(user_id: UUID, *, now: datetime | None = None) -> dict:
    """The CR222 §4 measured block for one user's WHOLE training history.

    Two shapes:
      - `too_early` — `{status, message}` only, no numeric figure anywhere,
        when the user has fewer than `settings.min_trades_for_diagnostics`
        closed lots OR fewer than `settings.min_elapsed_days_for_diagnostics`
        days have passed since their first training trade.
      - `ready` — `{status, first_trade_at, window_days, turnover_pct_annualised,
        median_holding_period_days, attention_trade_share_pct, disposition,
        baselines}`.

    `now` is injectable for tests; defaults to the real current time.
    """
    now = _as_utc(now) if now is not None else datetime.now(timezone.utc)
    min_trades = int(settings.min_trades_for_diagnostics)
    min_elapsed_days = float(settings.min_elapsed_days_for_diagnostics)

    trades = _load_all_trades(user_id)
    if not trades:
        return {
            "status": STATUS_TOO_EARLY,
            "message": (
                "Too early to measure — no training trades on record yet."
            ),
        }

    first_trade_at = trades[0].opened_at
    elapsed_days = max((now - first_trade_at).total_seconds() / 86400.0, 0.0)

    events_by_ticker = _closing_events_by_ticker(trades)
    closed_lot_count = sum(len(events) for events in events_by_ticker.values())

    if closed_lot_count < min_trades or elapsed_days < min_elapsed_days:
        return {
            "status": STATUS_TOO_EARLY,
            "message": (
                "Too early to measure — not enough closed trades or elapsed "
                "time since this user's first training trade yet."
            ),
        }

    starting_capital = _starting_capital(user_id)
    turnover_result = turnover(
        trades, window_days=elapsed_days, starting_capital=starting_capital,
    )
    median_hold = _median_holding_period_days(trades)
    attention_share = _attention_trade_share(user_id, trades)
    disposition = _disposition_ratio(trades)

    return {
        "status": STATUS_READY,
        "first_trade_at": first_trade_at.isoformat(),
        "window_days": round(elapsed_days, 2),
        "closed_lot_count": closed_lot_count,
        "turnover_pct": turnover_result.turnover_pct,
        "turnover_pct_annualised": turnover_result.turnover_pct_annualised,
        "median_holding_period_days": median_hold,
        "attention_trade_share_pct": attention_share,
        "disposition": disposition,
        "baselines": _published_baselines(),
    }


def behaviour_diagnostics_enabled() -> bool:
    return bool(settings.portfolio_behaviour_diagnostics_enabled)


def build_behaviour_block(user_id: UUID, *, now: datetime | None = None) -> dict | None:
    """The `behaviour` block for Portfolio Health §F, or `None` when the flag
    is off — an ABSENT block, not a zeroed one, so a flag-off report stays
    byte-identical to what it was before this CR (the same contract
    `passive_twin.build_passive_twin` / `training_toll.build_toll` hold)."""
    if not behaviour_diagnostics_enabled():
        return None
    return compute_behaviour_diagnostics(user_id, now=now)
