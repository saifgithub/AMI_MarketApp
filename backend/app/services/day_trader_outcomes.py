"""CR131 — Day Trader preset outcome instrumentation.

CR129 shipped a Day Trader preset that sets every user-controlled risk limit
permissive. Saiful's own framing for CR131: "a preset that only removes
limits is a faster way to lose with nothing learned." This module computes,
for one user, a measured before/after comparison of their own sim-trading
activity around the moment they switched the preset on, placed beside the
published Barber & Odean / Taiwan retail-trading baselines CR129 is already
grounded in (and `content/lessons/366-370` now teach).

THE HONESTY RULES ARE THE ACCEPTANCE CRITERIA, NOT DECORATION:

  - Never fabricate a comparison from a thin sample. Below
    `MIN_TRADES_FOR_COMPARISON` trades OR `MIN_ELAPSED_DAYS_FOR_COMPARISON`
    days on EITHER side of the switch, the whole response is a plain
    refusal (`status: "too_early"`) with no numeric figure anywhere in the
    payload — not a trade count, not a zero, not an extrapolated rate. A
    partial number is still an invitation to over-read a small sample, which
    is exactly what this rule exists to prevent.
  - No moralising. The `ready` payload is numbers and the published
    baselines' own provenance — never a grade, a warning, or a verdict.
  - Works identically for a winning and a losing user: same shape, same
    fields, always including the <1%-sustain-it figure and the short-
    winning-window/overconfidence mechanism, regardless of which way this
    user's own numbers point.
  - Baselines are US (Barber & Odean, 66,465 households, 1991-1996) and
    Taiwan (Barber, Lee, Liu & Odean, 1992-2006) retail-equity data —
    `PUBLISHED_BASELINES` states that explicitly so nothing implies the
    baseline describes this user's own market.

DEF166 (fixed, AT:R65) — read before trusting `realised_pnl`: it used to be
stamped on a trade's full REQUESTED quantity even when `_apply_sell_row`
clamped the actual close to fewer shares (not enough held), so the P&L and
the cash movement could disagree about how many shares moved. Both closing
paths (`SimEngine.manual_close` and the outcome-liquidation branch of
`evaluate_outcomes`) now stamp `realised_pnl` on the shares ACTUALLY sold.
Confirmed here by reading sim_engine.py directly (not by trusting the
registry note alone): both sites round `(price - entry_price) * sold`, where
`sold` is `_apply_sell_row`'s return value, not `t.quantity`. That makes
`status != "open"` the correct, sufficient filter for "this row carries a
trustworthy realised_pnl" — see `_window_summary` below. It also explains why
SELL-side trade rows are excluded from every P&L/win-rate figure here: a
direct `submit(side=SELL, ...)` (a manual partial/full reduce, as opposed to
`manual_close`/`evaluate_outcomes` closing the original BUY row) creates a
SEPARATE trade row that is created "open" and NEVER transitions — DEF110's
own comment in sim_engine.py calls this permanently-open shape load-bearing
for `def110_backfill.py`'s phantom-share formula, so it is not this module's
place to disturb it. Its `realised_pnl` is always 0, which the `status !=
"open"` filter already excludes; SELL rows are still counted in trade
frequency and turnover (both of which are about activity, not P&L).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from uuid import UUID

from sqlalchemy import select

from app.db import get_session
from app.db.models import JournalEntryRow, SimPortfolioRow, SimTradeRow
from app.schemas.journal import EntryType


# ── Cohort marker ───────────────────────────────────────────────────────
#
# mandate.py:154 stamps a MANDATE_EDIT journal entry whose summary begins
# with this exact sentence whenever `is_day_trader_preset()` recognises a
# PATCH as the Day Trader preset applied verbatim. Matched by PREFIX (SQL
# LIKE 'marker%'), not equality, because the summary sentence continues past
# it — prefix-matching keeps this module decoupled from the rest of that
# wording.
DAY_TRADER_JOURNAL_MARKER = "Day Trader preset applied"

# ── Honesty thresholds — the CR131 acceptance criteria ─────────────────
#
# Applied to BOTH the "before" and "active" windows independently: if either
# window falls short on trade count OR elapsed days, the entire response
# refuses rather than compute (or annualise) anything from it.
#
#   MIN_TRADES_FOR_COMPARISON = 10 — a conventional floor below which a
#   win-rate / avg-win-vs-avg-loss bucket is dominated by single-trade
#   noise (one trade swings a 5-trade win rate by 20 points).
#
#   MIN_ELAPSED_DAYS_FOR_COMPARISON = 7 — keeps the annualisation multiplier
#   (365.25 / window_days) at or below ~52x. Below a week, that multiplier
#   is large enough that ordinary day-to-day variance reads as a confident
#   annual rate — exactly what the project's "never present an estimate as
#   a measurement" rule forbids. A user three days in has no annualisable
#   return; this is the number that says so.
MIN_TRADES_FOR_COMPARISON = 10
MIN_ELAPSED_DAYS_FOR_COMPARISON = 7.0

DAYS_PER_YEAR = 365.25

# Mirrors sim_engine.py's private `_STARTING_CAPITAL` (not imported directly,
# to keep this module decoupled from sim_engine's internals). Used only as a
# defensive fallback if a user somehow has trades but no portfolio row; the
# real value is always read from the user's own `sim_portfolios` row first.
_DEFAULT_STARTING_CAPITAL = 10_000.0

STATUS_NOT_IN_COHORT = "not_in_cohort"
STATUS_TOO_EARLY = "too_early"
STATUS_READY = "ready"


# ── Published baselines (verified figures — reused, not re-derived) ────
#
# Exactly the figures `content/lessons/366-370` ship with and CR129's README
# cites: US most-active-quintile 11.4%/yr vs least-active 18.5%/yr, market
# 17.9%, 66,465 households; Taiwan survival 44%/24%/15% at 1/2/3 years;
# under 1% reliably profitable. Included verbatim, unconditionally, in every
# `ready` response — a winning user sees the same baselines object a losing
# user does (the CR131 "must work honestly for the user who is WINNING" rule).
PUBLISHED_BASELINES = {
    "us_barber_odean_1991_1996": {
        "provenance": (
            "Barber & Odean, 66,465 US retail household brokerage accounts, "
            "1991-1996. Before costs, the most-active and least-active "
            "groups picked stocks about equally well — the return gap below "
            "is attributable to trading activity, not stock-picking."
        ),
        "households": 66465,
        "most_active_quintile_annual_return_pct": 11.4,
        "least_active_quintile_annual_return_pct": 18.5,
        "market_annual_return_pct": 17.9,
    },
    "taiwan_day_traders_1992_2006": {
        "provenance": (
            "Barber, Lee, Liu & Odean, Taiwan day-trading population, "
            "1992-2006. Survival = share of day traders still day trading N "
            "years after starting."
        ),
        "reliably_profitable_pct_under": 1.0,
        "survival_1yr_pct": 44,
        "survival_2yr_pct": 24,
        "survival_3yr_pct": 15,
    },
    "market_note": (
        "US and Taiwan retail-equity datasets — reference material about "
        "those markets, not a description of this user's own market."
    ),
    "overconfidence_note": (
        "A short winning window is Barber & Odean's own proposed mechanism "
        "for the overconfidence that drives excess trading — not a "
        "prediction about whether this user's own current result will "
        "continue."
    ),
}


def _as_utc(value: datetime) -> datetime:
    """SQLite (test fixtures) drops tzinfo; Postgres keeps it. Same guard as
    `journal_store._as_utc` / `entitlements.py` — every stored or caller-
    supplied timestamp is normalised before comparison."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@dataclass(frozen=True)
class _Trade:
    side: str
    quantity: float
    entry_price: float
    opened_at: datetime
    closed_at: datetime | None
    status: str
    realised_pnl: float


def _earliest_day_trader_switch(user_id: UUID) -> datetime | None:
    """The cohort boundary: the EARLIEST MANDATE_EDIT entry whose summary
    starts with the Day Trader preset marker. A user who has never applied
    the preset is not in the cohort (returns None); a user who applied it,
    edited other limits afterward, then re-applied it, is bound by the
    FIRST switch — that is the moment their trading behaviour changed, and
    later re-applications of an already-active preset don't move it.

    Queried directly against `journal_entries` rather than through
    `journal_store.list_for_user` so this internal computation is never
    silently truncated by that method's Floor Pass 30-day retention window
    — that window governs a user-facing journal READ, not whether the
    switch historically happened, and a user who switched 40 days ago on
    Floor Pass must not read back as "not in cohort".
    """
    with get_session() as s:
        row = s.execute(
            select(JournalEntryRow)
            .where(JournalEntryRow.user_id == user_id)
            .where(JournalEntryRow.entry_type == EntryType.MANDATE_EDIT.value)
            .where(JournalEntryRow.deleted_at.is_(None))
            .where(JournalEntryRow.summary.like(f"{DAY_TRADER_JOURNAL_MARKER}%"))
            .order_by(JournalEntryRow.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()
        return _as_utc(row.created_at) if row is not None else None


def _load_all_trades(user_id: UUID) -> list[_Trade]:
    with get_session() as s:
        rows = (
            s.execute(
                select(SimTradeRow)
                .where(SimTradeRow.user_id == user_id)
                .order_by(SimTradeRow.opened_at.asc())
            )
            .scalars()
            .all()
        )
        return [
            _Trade(
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
            select(SimPortfolioRow).where(SimPortfolioRow.user_id == user_id)
        ).scalar_one_or_none()
        return float(row.starting_capital) if row is not None else _DEFAULT_STARTING_CAPITAL


def _split_by_switch(
    trades: list[_Trade], switched_at: datetime,
) -> tuple[list[_Trade], list[_Trade]]:
    """Partition every trade into (before, active) by `opened_at` — the
    moment the trade was PLACED, never `closed_at`.

    Why `opened_at` for every metric here (frequency, turnover, P&L,
    win-rate), not just frequency: a trade opened before the switch but
    closed after it was a decision made under the OLD limits. Crediting it
    to "active" would attribute a pre-switch decision to the day-trader
    regime that didn't cause it. Using one field for every metric also
    keeps a single partition instead of several metrics disagreeing about
    which window a straddling trade belongs to.

    Boundary choice: a trade opened at EXACTLY `switched_at` lands in
    `active` (`>=`, not `>`). The preset takes effect at that instant, so a
    trade timestamped the same moment as the switch is already operating
    under the permissive limits, not the ones it replaced.
    """
    before = [t for t in trades if t.opened_at < switched_at]
    active = [t for t in trades if t.opened_at >= switched_at]
    return before, active


def _window_days(*, start: datetime, end: datetime) -> float:
    return max((end - start).total_seconds() / 86400.0, 0.0)


def _meets_threshold(trade_count: int, days: float) -> bool:
    return (
        trade_count >= MIN_TRADES_FOR_COMPARISON
        and days >= MIN_ELAPSED_DAYS_FOR_COMPARISON
    )


def _avg_hold_days(subset: list[_Trade]) -> float | None:
    holds = [
        (t.closed_at - t.opened_at).total_seconds() / 86400.0
        for t in subset
        if t.closed_at is not None
    ]
    return round(mean(holds), 2) if holds else None


def _window_summary(trades: list[_Trade], days: float, starting_capital: float) -> dict:
    """One side of the comparison (before OR active). Only ever called once
    both windows have already cleared `_meets_threshold`, so `days` here is
    always >= `MIN_ELAPSED_DAYS_FOR_COMPARISON` > 0."""
    trade_count = len(trades)

    # DEF166: `status != "open"` is the correct filter for "this row's
    # realised_pnl is trustworthy" — see the module docstring. It also
    # naturally excludes every SELL-side row (permanently "open") without
    # needing a side check.
    closed = [t for t in trades if t.status != "open"]
    winners = [t for t in closed if t.realised_pnl > 0]
    losers = [t for t in closed if t.realised_pnl < 0]
    breakeven = [t for t in closed if t.realised_pnl == 0]

    # Turnover (Barber & Odean's own metric): average of gross buy and sell
    # notional traded in the window, as a fraction of starting capital, then
    # annualised. Approximated against the fixed starting capital rather
    # than a time-weighted average portfolio value — every sim portfolio
    # starts at the same known figure, so this needs no second table (no
    # migration) and stays a stable, always-available denominator; it is an
    # approximation of the literal Barber-Odean definition, not a
    # reproduction of it.
    buy_notional = sum(t.quantity * t.entry_price for t in trades if t.side == "buy")
    sell_notional = sum(t.quantity * t.entry_price for t in trades if t.side == "sell")
    avg_side_notional = (buy_notional + sell_notional) / 2.0
    turnover_pct = (avg_side_notional / starting_capital * 100.0) if starting_capital else 0.0

    annualise = DAYS_PER_YEAR / days
    realised_pnl_total = round(sum(t.realised_pnl for t in closed), 2)

    return {
        "window_days": round(days, 2),
        "trade_count": trade_count,
        "trades_per_day": round(trade_count / days, 3),
        "trades_per_week": round(trade_count / days * 7.0, 3),
        "turnover_pct": round(turnover_pct, 2),
        "turnover_pct_annualised": round(turnover_pct * annualise, 2),
        "realised_pnl": realised_pnl_total,
        "realised_pnl_annualised_pct": (
            round(realised_pnl_total / starting_capital * 100.0 * annualise, 2)
            if starting_capital
            else 0.0
        ),
        "closed_trade_count": len(closed),
        "win_count": len(winners),
        "loss_count": len(losers),
        "breakeven_count": len(breakeven),
        "win_rate_pct": (
            round(len(winners) / len(closed) * 100.0, 2) if closed else None
        ),
        "avg_win": round(mean(t.realised_pnl for t in winners), 2) if winners else None,
        "avg_loss": round(mean(t.realised_pnl for t in losers), 2) if losers else None,
        # Disposition-effect view (CR131 README point 3): are losers held
        # longer than winners before being closed?
        "avg_hold_days_winners": _avg_hold_days(winners),
        "avg_hold_days_losers": _avg_hold_days(losers),
    }


def compute_day_trader_outcomes(user_id: UUID, *, now: datetime | None = None) -> dict:
    """The CR131 measured comparison for one user.

    Three shapes, and only three:
      - `not_in_cohort` — no Day Trader switch on record. `{status, message}`
        only.
      - `too_early` — in the cohort, but the before and/or active window is
        too thin to compare honestly. `{status, message}` only — NO numeric
        figure anywhere in the payload, by construction (this branch never
        touches trade data at all once the threshold check fails).
      - `ready` — `{status, switched_at, before, active, baselines}`, where
        `before`/`active` are `_window_summary` and `baselines` is
        `PUBLISHED_BASELINES` verbatim.

    `now` is injectable for tests; defaults to the real current time.
    """
    now = _as_utc(now) if now is not None else datetime.now(timezone.utc)

    switched_at = _earliest_day_trader_switch(user_id)
    if switched_at is None:
        return {
            "status": STATUS_NOT_IN_COHORT,
            "message": (
                "This user has not switched on the Day Trader preset — "
                "there is nothing to compare."
            ),
        }

    trades = _load_all_trades(user_id)
    before, active = _split_by_switch(trades, switched_at)

    before_start = before[0].opened_at if before else switched_at
    before_days = _window_days(start=before_start, end=switched_at)
    active_days = _window_days(start=switched_at, end=now)

    if not (
        _meets_threshold(len(before), before_days)
        and _meets_threshold(len(active), active_days)
    ):
        return {
            "status": STATUS_TOO_EARLY,
            "message": (
                "Too early to compare — not enough trades or elapsed time "
                "on one or both sides of the Day Trader switch yet."
            ),
        }

    starting_capital = _starting_capital(user_id)
    return {
        "status": STATUS_READY,
        "switched_at": switched_at.isoformat(),
        "before": _window_summary(before, before_days, starting_capital),
        "active": _window_summary(active, active_days, starting_capital),
        "baselines": PUBLISHED_BASELINES,
    }
