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
  * **Disposition ratio (PGR/PLR, Odean 1998)** — Odean's own tally
    (p.1781), by COUNT: on each day a sale takes place in a portfolio that
    held two or more stocks at the start of that day, each stock sold that
    day is ONE realised gain or loss (its selling price against its average
    purchase price), and each stock held at the start of that day and NOT
    sold that day is ONE paper gain or loss (its price that day against its
    average purchase price). A stock sold that day, fully or partly, is
    never also a paper event. Days with no sale, and sale days on which
    fewer than two stocks were held at the start of the day, count nothing.
    PGR = realised gains / (realised gains + paper gains); PLR likewise for
    losses. The counts are pooled over this user's own measured sale days,
    so the result is ONE account's ratio: the quantity Odean's per-account
    averages (p.1784, 0.57 / 0.36) average over, which is why those, and not
    the pooled all-account Table I figures, are the published baseline. A
    user with no qualifying sale day (one position at a time, say) gets
    `pgr`/`plr` = None — not measured, never a forced 100%.

    **Where this still differs from the paper, stated because the CR asked
    for it to be:**
      - Paper side: Odean scores a held stock a paper gain only if the day's
        high AND low are both above its average purchase price (a paper loss
        if both are below, neither if the average lies between them).
        `price_history_daily` stores one close a day, so this scores the
        close on or before the sale day against the average purchase price;
        a stock Odean would score "neither" is scored here by the close's
        side.
      - Prices are `adj_close` (split- and dividend-adjusted, see
        `PriceHistoryDailyRow`); average purchase price is the nominal fill
        price. A split after a fill, or a dividend after the sale day, can
        move the stored close relative to the fill without the position's
        value moving.
      - "Day" is the UTC calendar date of the sale's timestamp. "Held at the
        start of the day" means opened before 00:00 UTC of that date and not
        fully closed before it.
      - A stock bought and sold within the same day is a realised event (it
        was sold that day) but does not count toward the two-stock threshold
        (it was not held at the start of the day).
      - Several sales of one stock on one day are one realised event, scored
        by their quantity-weighted average selling price against the average
        purchase price just before that day's first sale of it.
    A held stock with no stored close on or before the sale day, or a sale
    with no recorded selling price, is a NAMED absence
    (`unpriced_positions_excluded`), never priced at zero or at its own
    purchase price — degrade loudly (CR040).

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
from datetime import date, datetime, time, timedelta, timezone
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
    # Odean 1998 p.1784: "PGR and PLR are then estimated for each account …
    # The average account PGR is 0.57, the average account PLR is 0.36."
    # Per-account, because `_disposition_ratio` computes ONE account's ratio
    # and this is the average of that same quantity across his accounts.
    # That test also drops any sale (or paper event) of a stock within a week
    # of a counted one of the same stock in ANY account, a cross-account
    # control one account has no counterpart for. The pooled Table I figures
    # (PGR 0.148 / PLR 0.098, p.1783) are deliberately NOT carried: they pool
    # counts across all accounts, so accounts with many holdings dominate,
    # and set beside one account's ratio they read as a ~4x gap that is not
    # there (CR222-D audit round 2, MAJOR-2).
    "odean_1998_disposition": {
        "provenance": (
            "Odean, \"Are Investors Reluctant to Realize Their Losses?\", "
            "Journal of Finance 1998. 10,000 US retail brokerage accounts, "
            "1987-1993. PGR and PLR estimated for each account separately, "
            "then averaged across accounts."
        ),
        "average_account_pgr": 0.57,
        "average_account_plr": 0.36,
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
    closed_price: float | None = None


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
                closed_price=float(r.closed_price) if r.closed_price is not None else None,
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

    Built from `_closing_events_by_ticker`, whose per-ticker walk
    (`_closing_events_one_ticker`) `_disposition_ratio` shares for
    event-level (not merely per-lot aggregate) dates — see that function's
    own docstring for why it walks
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
    `sell_price` is the price the shares left at (None when the row carries
    none); `avg_cost_before` is the quantity-weighted average purchase price
    of the ticker's whole open position immediately before this sale, which
    is what Odean classifies a sale against — not this one lot's entry.
    """

    ticker: str
    entry_date: date
    close_date: date
    close_at: datetime
    quantity_closed: float
    realised_pnl: float
    sell_price: float | None
    avg_cost_before: float


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
            if not result.closes:
                continue
            avg_cost = _average_cost(open_refs)
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
                    sell_price=t.entry_price,
                    avg_cost_before=avg_cost,
                ))
        elif kind == 2:
            lot = by_id.get(t.id)
            if lot is None or lot["quantity_open"] <= 1e-9:
                continue
            avg_cost = _average_cost([lot for lot in lots if lot["quantity_open"] > 1e-9])
            events.append(_ClosingEvent(
                ticker=ticker,
                entry_date=lot["entry_date"],
                close_date=ts.date(),
                close_at=ts,
                quantity_closed=lot["quantity_open"],
                realised_pnl=round(t.realised_pnl, 2),
                sell_price=t.closed_price,
                avg_cost_before=avg_cost,
            ))
            lot["quantity_open"] = 0.0
    return events


def _average_cost(open_lots: list[dict]) -> float:
    """Quantity-weighted average purchase price over open lots (Odean's
    reference point). Callers pass only lots with quantity_open > 0."""
    qty = sum(lot["quantity_open"] for lot in open_lots)
    return sum(lot["entry_price"] * lot["quantity_open"] for lot in open_lots) / qty


# ── Disposition ratio (Odean 1998, per stock per sale day) ─────────────────


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
    """Odean 1998's PGR/PLR, tallied his way: per stock per sale day, only on
    sale days when two or more stocks were held at the start of the day, each
    stock against its average purchase price (see the module docstring for
    the method and the deviations that remain).

    Returns `{pgr, plr, realised_gains_count, paper_gains_count,
    realised_losses_count, paper_losses_count, unpriced_positions_excluded}`.
    The last is a NAMED count of (sale day, stock) pairs on a measured sale
    day that could not be classified for want of a price: a held stock with
    no stored close on or before that day, or a sold stock whose sale carries
    no selling price. It is not folded into either denominator silently.
    `pgr`/`plr` are None when their denominator is empty — including every
    account that never had a qualifying sale day.
    """
    by_ticker_trades: dict[str, list[_Trade]] = {}
    for t in trades:
        by_ticker_trades.setdefault(t.ticker, []).append(t)

    sales_by_day: dict[date, dict[str, list[_ClosingEvent]]] = {}
    for ticker, ticker_trades in by_ticker_trades.items():
        for ev in _closing_events_one_ticker(ticker, ticker_trades):
            sales_by_day.setdefault(ev.close_date, {}).setdefault(ticker, []).append(ev)

    price_cache: dict[str, tuple[list[date], list[float]]] = {}

    def _prices_for(ticker: str) -> tuple[list[date], list[float]]:
        if ticker not in price_cache:
            rows = _price_rows(ticker)
            price_cache[ticker] = ([d for d, _ in rows], [c for _, c in rows])
        return price_cache[ticker]

    counts = {"realised_gain": 0, "realised_loss": 0, "paper_gain": 0, "paper_loss": 0}
    unpriced_positions_excluded = 0

    def _tally(kind: str, price: float, avg_cost: float) -> None:
        # A price equal to the average purchase price is neither a gain nor a
        # loss — Odean classifies gains and losses, not flat positions.
        if price - avg_cost > 1e-9:
            counts[f"{kind}_gain"] += 1
        elif price - avg_cost < -1e-9:
            counts[f"{kind}_loss"] += 1

    for day in sorted(sales_by_day):
        start_of_day = datetime.combine(day, time.min, tzinfo=timezone.utc)
        held_at_start: dict[str, float] = {}
        for ticker, ticker_trades in by_ticker_trades.items():
            avg_cost = _average_cost_held_before(ticker_trades, cutoff=start_of_day)
            if avg_cost is not None:
                held_at_start[ticker] = avg_cost
        if len(held_at_start) < 2:
            continue

        sold_today = sales_by_day[day]
        for ticker, events in sold_today.items():
            events = sorted(events, key=lambda e: e.close_at)
            if any(ev.sell_price is None for ev in events):
                unpriced_positions_excluded += 1
                continue
            qty = sum(ev.quantity_closed for ev in events)
            sell_price = sum(ev.sell_price * ev.quantity_closed for ev in events) / qty
            _tally("realised", sell_price, events[0].avg_cost_before)

        for ticker, avg_cost in held_at_start.items():
            if ticker in sold_today:
                continue
            dates, closes = _prices_for(ticker)
            price = _price_on_or_before(dates, closes, day)
            if price is None:
                unpriced_positions_excluded += 1
                continue
            _tally("paper", price, avg_cost)

    realised_gains_count = counts["realised_gain"]
    realised_losses_count = counts["realised_loss"]
    paper_gains_count = counts["paper_gain"]
    paper_losses_count = counts["paper_loss"]
    pgr = (
        realised_gains_count / (realised_gains_count + paper_gains_count)
        if (realised_gains_count + paper_gains_count) > 0 else None
    )
    plr = (
        realised_losses_count / (realised_losses_count + paper_losses_count)
        if (realised_losses_count + paper_losses_count) > 0 else None
    )
    return {
        "pgr": round(pgr, 4) if pgr is not None else None,
        "plr": round(plr, 4) if plr is not None else None,
        "realised_gains_count": realised_gains_count,
        "paper_gains_count": paper_gains_count,
        "realised_losses_count": realised_losses_count,
        "paper_losses_count": paper_losses_count,
        "unpriced_positions_excluded": unpriced_positions_excluded,
    }


def _average_cost_held_before(trades: list[_Trade], *, cutoff: datetime) -> float | None:
    """Average purchase price of ONE ticker's position as it stood just
    before `cutoff` (every event strictly earlier than it replayed), or None
    when nothing was held. Strictly earlier, so a lot opened or closed at
    exactly 00:00 of a sale day belongs to that day, not to its start.

    Same event-stream construction as `_closing_events_one_ticker`. Called
    once per (sale day, ticker); one user's trade list is never large enough
    for the repeated replay to matter."""
    lots: list[dict] = []
    by_id: dict[str, dict] = {}
    stream: list[tuple[int, datetime, str, _Trade]] = []
    for t in trades:
        if t.side == "buy" and t.opened_at < cutoff:
            stream.append((0, t.opened_at, t.id, t))
            if t.status.lower() in {"won", "lost", "closed"}:
                closed_at = t.closed_at or t.opened_at
                if closed_at < cutoff:
                    stream.append((2, closed_at, t.id, t))
        elif t.side == "sell" and t.opened_at < cutoff:
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
    open_lots = [lot for lot in lots if lot["quantity_open"] > 1e-9]
    return _average_cost(open_lots) if open_lots else None


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
