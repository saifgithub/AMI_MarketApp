"""CR109 slice 3 — "the close": the SETTLING -> CLOSED scoring pass.

implementation_plan.md §2 slice 3 / §9 test matrix items 10-14, 28-34, 41-42;
CR109.md §4.3's field/entry state machines, §6.6/§6.6.1/§6.6.2 (benchmark-
relative scoring, the achievable benchmark, the alpha->points formula), §6.5
(the finish stipend) and §10.4 (the private mirrors).

Entry point: `run_scoring_pass()`, meant to be called off a background tick
(`main.py`) and directly from tests. Two phases, deliberately never
interleaved (the codebase's own convention — see `games_service.get_run_detail`
for the same shape): a READ-ONLY phase gathers every input a pending entry's
score needs (NAV history, the trade log, current marks, the benchmark
series) across several short-lived sessions, THEN a single WRITE phase opens
ONE session for the field and applies every entry's score plus its ledger
posts in one transaction. Interleaving would either (a) let an outer
session's open write transaction lock a SQLite file out from under the
read-only helper calls, or (b) require nested `get_session()` calls that
cannot see each other's uncommitted state — the write phase is single-
session specifically so `career_ledger.post_career_event`'s clamp-at-write
math sees every sibling post in the SAME field's close.

**Idempotency**: `game_entries.scored_at` is the guard, checked BOTH when
selecting candidates (phase 1) and again immediately before each write
(phase 2, belt-and-braces against a race between the two phases) — a
re-run finds nothing left to do for an already-scored entry and skips it
outright, so `career_ledger`'s own (entry_id, reason) dedup is a backstop,
never the primary mechanism.

**Field state**: LIVE -> SETTLING happens at `ends_on < today` (§4.3:
"period end; positions lock, results withheld") and SETTLING -> CLOSED
happens in the SAME call, in the SAME transaction as the settling
transition — so 'settling' is never a separately-committed, externally-
observable state a concurrent trade request could land in. "Settlement
freeze duration" is explicitly undecided (implementation_plan.md §10 item
8); zero elapsed time is the defensible first cut, same spirit as this
plan's other "first cut" constants.

**Scoring basis**: ALWAYS "benchmark" — placement is slice 4 and is not
built here (see the `n < 8` fence in implementation_plan.md §7.2). This is
correct at alpha field sizes regardless of `entrant_count`, not a shortcut.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.logging import logger
from app.db import get_session
from app.db.models import (
    GameEntryRow,
    GameFieldRow,
    GameShortPositionRow,
    SimTradeRow,
)
from app.services import career_ledger
from app.services.games_scoring import (
    TradeLeg,
    achievable_benchmark,
    alpha_to_points,
    apply_negative_twr_partial_credit,
    cadence_period_key,
    cadence_weight,
    counterfactual_hold_first_picks_pct,
    finish_stipend,
    wildness_index,
)
from app.services.portfolio_nav_daily import nav_history
from app.services.sim_engine import SimEngine, get_sim_engine
from app.trading_math.twr import NavPoint, time_weighted_return

_ET = ZoneInfo("America/New_York")
# The history window fetched for the benchmark, per cadence. Each must be a
# period from `market_data.VALID_PERIODS` — the app's OWN vocabulary
# (`1d/1w/1m/3m/1y/2y/5y`), which is not yfinance's. A string outside it makes
# `history()` return None, which this module turns into a benchmark TWR of
# 0.0: every long run would then be scored against a FLAT index and read as
# enormous alpha. `test_cr109_cadences.py` asserts the whole table against
# VALID_PERIODS for exactly that reason.
#
# Each entry is the shortest valid period that CONTAINS its run, because the
# candles are filtered to the field's own [starts_on, ends_on] window
# afterwards — over-fetching costs one call, under-fetching scores the
# benchmark over a shorter window than the player's book.
_BENCHMARK_PERIOD_BY_CADENCE: dict[str, str] = {
    "week": "1w",     # 5 sessions of 30m bars — unchanged from slice 3
    "month": "3m",    # ~65 daily bars
    "quarter": "2y",  # 504 daily bars — daily resolution across the window
    "half": "2y",
    "year": "2y",
}
_DEFAULT_BENCHMARK_PERIOD = "1w"


# ── Phase-1 snapshots (plain data — no ORM instances survive their session) ─


@dataclass
class _FieldSnap:
    id: UUID
    cadence: str
    starts_on: date
    ends_on: date
    benchmark_ticker: str


@dataclass
class _EntrySnap:
    id: UUID
    user_id: UUID
    run_id: UUID
    trade_count: int


@dataclass
class _ScoredEntry:
    entry_id: UUID
    is_void: bool
    void_reason: Optional[str]
    run_twr_pct: Optional[float]
    alpha_scored_pct: Optional[float]
    alpha_display_pct: Optional[float]
    counterfactual_hold_index_pct: Optional[float]
    counterfactual_hold_first_picks_pct: Optional[float]
    wildness_index: Optional[float]
    run_close_points: int  # 0 when void — no run_close event posted
    stipend_eligible_precheck: bool  # entered + >=1 trade — period-claim resolved at write time


def run_scoring_pass(
    *, now: datetime | None = None, sim: SimEngine | None = None,
) -> dict[str, int]:
    """The full sweep: transition due LIVE fields to SETTLING, close every
    SETTLING field. Safe to call repeatedly — an already-CLOSED field or an
    already-scored entry is simply absent from the next pass's candidates.

    `sim` is injectable (tests only; production always uses the singleton)
    because the benchmark series comes from `sim.current_history()`, whose
    default provider is a real singleton constructed once at first use —
    tests that need a deterministic benchmark inject their own `SimEngine`.
    """
    now = now or datetime.now(timezone.utc)
    sim = sim or get_sim_engine()
    today_et = now.astimezone(_ET).date()

    with get_session() as s:
        due_live_ids = [
            row.id for row in s.execute(
                select(GameFieldRow.id).where(
                    GameFieldRow.state == "live", GameFieldRow.ends_on < today_et,
                )
            ).all()
        ]
        candidate_field_ids = due_live_ids + [
            row.id for row in s.execute(
                select(GameFieldRow.id).where(GameFieldRow.state == "settling")
            ).all()
        ]

    fields_closed = 0
    entries_scored = 0
    entries_voided = 0
    stipends_paid = 0
    for field_id in candidate_field_ids:
        result = _close_field(field_id, sim=sim, now=now)
        if result is None:
            continue
        fields_closed += 1
        entries_scored += result["scored"]
        entries_voided += result["voided"]
        stipends_paid += result["stipends"]

    return {
        "fields_due": len(candidate_field_ids),
        "fields_closed": fields_closed,
        "entries_scored": entries_scored,
        "entries_voided": entries_voided,
        "stipends_paid": stipends_paid,
    }


def _close_field(field_id: UUID, *, sim: SimEngine, now: datetime) -> dict[str, int] | None:
    # ── Phase 1: read everything the score needs, write nothing. ──────────
    with get_session() as s:
        field_row = s.execute(
            select(GameFieldRow).where(GameFieldRow.id == field_id)
        ).scalar_one_or_none()
        if field_row is None or field_row.state not in ("live", "settling"):
            return None
        field = _FieldSnap(
            id=field_row.id, cadence=field_row.cadence,
            starts_on=field_row.starts_on, ends_on=field_row.ends_on,
            benchmark_ticker=field_row.benchmark_ticker or "SPY",
        )
        pending = [
            _EntrySnap(id=e.id, user_id=e.user_id, run_id=e.run_id, trade_count=e.trade_count)
            for e in s.execute(
                select(GameEntryRow).where(GameEntryRow.field_id == field_id)
            ).scalars().all()
            if e.state in ("entered", "active") and e.scored_at is None
        ]

    benchmark_twr = _benchmark_twr_for_field(sim, field)
    scored_entries = [_score_one_entry(sim, e, field, benchmark_twr) for e in pending]

    # ── Phase 2: apply every entry's score + ledger posts, then close. ────
    scored = voided = stipends = 0
    with get_session() as s:
        field_row = s.execute(
            select(GameFieldRow).where(GameFieldRow.id == field_id)
        ).scalar_one()
        for scored_entry in scored_entries:
            entry = s.execute(
                select(GameEntryRow).where(GameEntryRow.id == scored_entry.entry_id)
            ).scalar_one_or_none()
            if entry is None or entry.state not in ("entered", "active") or entry.scored_at is not None:
                continue  # raced with something else since phase 1 — skip, next pass retries
            stipend_paid = _apply_score(s, entry, field_row, scored_entry, now=now)
            if scored_entry.is_void:
                voided += 1
            else:
                scored += 1
            if stipend_paid:
                stipends += 1
        field_row.scoring_basis = "benchmark"
        field_row.state = "closed"

    logger.info(
        "game_field_closed",
        field_id=str(field_id), cadence=field.cadence,
        scored=scored, voided=voided, stipends=stipends,
    )
    return {"scored": scored, "voided": voided, "stipends": stipends}


# ── Benchmark series ─────────────────────────────────────────────────────


def _benchmark_twr_for_field(sim: SimEngine, field: _FieldSnap) -> float:
    """The benchmark's GROSS TWR (a fraction) over the field's own window.
    `sim_engine.current_history()` never raises and always returns
    *something*, per its own docstring — this mirrors that contract:
    0.0 (flat) rather than a crash when no candle is available at all.
    """
    period = _BENCHMARK_PERIOD_BY_CADENCE.get(field.cadence, _DEFAULT_BENCHMARK_PERIOD)
    candles, source = sim.current_history(field.benchmark_ticker, period)
    if not candles:
        logger.warn(
            "game_benchmark_unavailable",
            field_id=str(field.id), ticker=field.benchmark_ticker, source=source,
        )
        return 0.0

    windowed = [
        c for c in candles
        if field.starts_on <= datetime.fromtimestamp(c.t, tz=timezone.utc).date() <= field.ends_on
    ]
    use = windowed if len(windowed) >= 2 else candles
    if len(use) < 2:
        return 0.0
    baseline = use[0].o or use[0].c
    if not baseline:
        return 0.0
    return (use[-1].c / baseline) - 1.0


# ── Per-entry scoring (pure computation over gathered data) ──────────────


def _score_one_entry(
    sim: SimEngine, entry: _EntrySnap, field: _FieldSnap, benchmark_twr: float,
) -> _ScoredEntry:
    nav_rows = nav_history(entry.user_id, run_id=entry.run_id)
    mock_dates = sorted({r.as_of_date for r in nav_rows if r.price_source == "mock"})
    is_void = bool(mock_dates)

    navs = [
        NavPoint(as_of=r.as_of_date, nav=float(r.nav), capital_event=r.capital_event)
        for r in nav_rows
    ]
    run_twr = time_weighted_return(navs)
    run_twr = 0.0 if run_twr is None else run_twr
    run_twr_pct = round(run_twr * 100, 2)

    if is_void:
        void_reason = (
            "mock-priced day(s): " + ", ".join(d.isoformat() for d in mock_dates)
        )
        return _ScoredEntry(
            entry_id=entry.id, is_void=True, void_reason=void_reason,
            run_twr_pct=run_twr_pct, alpha_scored_pct=None, alpha_display_pct=None,
            counterfactual_hold_index_pct=None, counterfactual_hold_first_picks_pct=None,
            wildness_index=None, run_close_points=0,
            stipend_eligible_precheck=entry.trade_count >= 1,
        )

    achievable = achievable_benchmark(benchmark_twr)
    alpha_scored = run_twr - achievable
    alpha_display = run_twr - benchmark_twr

    base = alpha_to_points(alpha_scored)
    base = apply_negative_twr_partial_credit(base, run_twr)
    weighted = base * cadence_weight(field.cadence, negative=(base < 0))
    run_close_points = int(round(weighted))

    portfolio, marks, total_value, _dd, _source = sim.portfolio_marks_snapshot(
        entry.user_id, kind="game", run_id=entry.run_id,
    )
    trade_legs, notional_traded = _trade_legs_for_run(portfolio.id)
    # CR109 Amendment G — concentration is GROSS. A short's exposure is its
    # notional at the mark, counted as a positive weight alongside the longs:
    # a player holding $5k of a name and short $5k of another is running two
    # positions and two ways to be wrong, not a flat book. Netting them would
    # let a wild book score as a calm one, which is the one thing the
    # wildness index exists to stop.
    holding_weights = [
        (h.quantity * marks.get(h.ticker, h.avg_cost)) / total_value
        for h in portfolio.holdings
        if total_value > 0
    ] + [
        abs(sp.quantity * marks.get(sp.ticker, sp.entry_price)) / total_value
        for sp in portfolio.shorts
        if total_value > 0
    ]
    daily_returns = [
        float(nav_rows[i].nav) / float(nav_rows[i - 1].nav) - 1.0
        for i in range(1, len(nav_rows))
        if float(nav_rows[i - 1].nav) > 0
    ]
    wildness = wildness_index(
        holding_weights=holding_weights,
        total_notional_traded=notional_traded,
        starting_capital=float(portfolio.starting_capital),
        daily_returns=[float(r) for r in daily_returns],
    )
    first_picks_pct = counterfactual_hold_first_picks_pct(
        trade_legs, marks, float(portfolio.starting_capital),
    )

    return _ScoredEntry(
        entry_id=entry.id, is_void=False, void_reason=None,
        run_twr_pct=run_twr_pct,
        alpha_scored_pct=round(alpha_scored * 100, 2),
        alpha_display_pct=round(alpha_display * 100, 2),
        counterfactual_hold_index_pct=round(benchmark_twr * 100, 2),
        counterfactual_hold_first_picks_pct=first_picks_pct,
        wildness_index=wildness,
        run_close_points=run_close_points,
        stipend_eligible_precheck=entry.trade_count >= 1,
    )


def _trade_legs_for_run(portfolio_id: UUID) -> tuple[list[TradeLeg], float]:
    with get_session() as s:
        rows = s.execute(
            select(SimTradeRow)
            .where(SimTradeRow.portfolio_id == portfolio_id)
            .order_by(SimTradeRow.opened_at.asc())
        ).scalars().all()
        legs = [
            TradeLeg(
                ticker=r.ticker, side=r.side, quantity=float(r.quantity),
                price=float(r.entry_price), opened_at=r.opened_at.date(),
            )
            for r in rows
        ]
        notional_traded = sum(float(r.quantity) * float(r.entry_price) for r in rows)

        # CR109 Amendment G — shorts deliberately write NO `sim_trades` row
        # (that is what keeps `def110_backfill.py`'s phantom-share formula
        # reading what it always read), so without this they would be
        # invisible to turnover and to the first-picks counterfactual: a
        # player who spent the week shorting would score as though they had
        # never traded. Each open contributes its sell leg and each cover its
        # buy leg, which is exactly what the two fills were.
        shorts = s.execute(
            select(GameShortPositionRow)
            .where(GameShortPositionRow.portfolio_id == portfolio_id)
            .order_by(GameShortPositionRow.opened_at.asc())
        ).scalars().all()
        for sp in shorts:
            qty, entry = float(sp.quantity), float(sp.entry_price)
            legs.append(TradeLeg(
                ticker=sp.ticker, side="sell", quantity=qty,
                price=entry, opened_at=sp.opened_at.date(),
            ))
            notional_traded += qty * entry
            if sp.state == "closed" and sp.close_price is not None and sp.closed_at:
                close = float(sp.close_price)
                legs.append(TradeLeg(
                    ticker=sp.ticker, side="buy", quantity=qty,
                    price=close, opened_at=sp.closed_at.date(),
                ))
                notional_traded += qty * close
        legs.sort(key=lambda leg: leg.opened_at)
    return legs, notional_traded


# ── Phase-2 write: one entry's score + ledger posts ───────────────────────


def _apply_score(
    session, entry: GameEntryRow, field: GameFieldRow, scored: _ScoredEntry, *, now: datetime,
) -> bool:
    """Returns True iff this entry's close claimed the finish stipend."""
    was_first_ever_finish = False
    if not scored.is_void:
        prior_finished = session.execute(
            select(GameEntryRow.id).where(
                GameEntryRow.user_id == entry.user_id,
                GameEntryRow.state == "finished",
                GameEntryRow.id != entry.id,
            ).limit(1)
        ).first()
        was_first_ever_finish = prior_finished is None

    entry.state = "void" if scored.is_void else "finished"
    entry.void_reason = scored.void_reason
    entry.final_twr_pct = scored.run_twr_pct
    entry.alpha_scored_pct = scored.alpha_scored_pct
    entry.alpha_display_pct = scored.alpha_display_pct
    entry.counterfactual_hold_index_pct = scored.counterfactual_hold_index_pct
    entry.counterfactual_hold_first_picks_pct = scored.counterfactual_hold_first_picks_pct
    entry.wildness_index = scored.wildness_index
    entry.scored_at = now

    total_delta = 0
    if not scored.is_void:
        run_close_row = career_ledger.post_career_event(
            session,
            user_id=entry.user_id, delta_uncapped=scored.run_close_points,
            reason="run_close", field_id=field.id, entry_id=entry.id,
        )
        if run_close_row is not None:
            total_delta += run_close_row.delta

    stipend_paid = False
    if scored.stipend_eligible_precheck:
        period_key = cadence_period_key(field.cadence, field.starts_on)
        stipend_row = career_ledger.post_career_event(
            session,
            user_id=entry.user_id, delta_uncapped=finish_stipend(field.cadence),
            reason="finish_stipend", field_id=field.id, entry_id=entry.id,
            period_key=period_key,
        )
        if stipend_row is not None:
            entry.stipend_points = stipend_row.delta
            total_delta += stipend_row.delta
            stipend_paid = True

    entry.career_points_delta = total_delta

    if not scored.is_void:
        logger.info(
            "game_run_scored",
            user_id=str(entry.user_id), entry_id=str(entry.id), field_id=str(field.id),
            final_twr_pct=scored.run_twr_pct, alpha_scored_pct=scored.alpha_scored_pct,
            career_points_delta=total_delta,
        )
        if was_first_ever_finish:
            logger.info(
                "game_first_run_activation",
                user_id=str(entry.user_id), entry_id=str(entry.id), run_id=str(entry.run_id),
            )
    return stipend_paid
