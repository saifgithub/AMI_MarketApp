"""CR109 slice 5 — the period arc's LIVE beats (design §10).

§10's table has nine beats. Six of them ship: the Close, the Record, the
re-entry CTA, and the three the Record renders after a run ends. The three
*before* the Close — the entry countdown, the bell, the final stretch — did
not exist at all, and §10 names the missing set precisely: *"the anticipation
engine."* Without them a run is a screen you visit, remember to visit, and
eventually stop visiting; there is nothing in it that says *something is
about to happen.*

This module computes the one beat a run is currently in. It is a pure read
over the field row, the board and the trade log — it writes nothing and
schedules nothing.

**The two clocks, and why they are different on purpose.**

1. **Standing moves once per close.** `your_rank`, `gap_to_next_pct` and
   `entrant_count` come straight from `games_board.board_for_run`, which
   ranks on the stored daily NAV series and says which close it is as of.
   §10: *"one rank-movement beat per US market close. Not per tick — per-tick
   movement is a slot machine, and this is a training product."*
2. **Your own attribution is live.** It is computed from the marks already on
   the run screen, and it moves when *you* trade rather than when the market
   twitches. That is a reading of §10 rather than a quotation of it, and the
   reasoning is: the slot-machine failure the rule guards against is watching
   your STANDING flicker — a number produced by other people's books, which
   you cannot act on. Your own P&L split by ticker is the same live data the
   positions list already renders one scroll down; grouping it does not make
   it more tick-shaped, and pinning it to yesterday's close would make the
   beat disagree with the rows directly beneath it.

**The near-miss fence is structural here, not a copy note.** §10 permits
*"You were 0.3% off 2nd"* and forbids the downward twin — *"you almost
avoided the debit"* is the slot-machine near-miss, the pattern that
measurably prolongs gambling persistence. So this module emits `gap_to_next`
(the entrant ABOVE you) and has no field for the entrant below you at all.
A future copy change cannot cross the line because the number it would need
is not in the payload.

**No push.** §10.1's matrix marks four beats as *needing* push and records
Saiful's ruling — *in-app ceremony now, push next* — with push as its own CR
(implementation_plan.md slice 5). Until it lands, every beat here reaches
only a player who already opened the app. Stated rather than glossed, which
is the same posture `games_board` takes about `updates: daily_close`.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.db import get_session
from app.db.models import GameEntryRow, GameFieldRow, SimPortfolioRow
from app.services import games_board
from app.services.games_scoring import contribution_by_ticker
from app.services.games_scoring_pass import trade_legs_for_run

# How many days before the end the run enters its FINAL STRETCH — the beat
# §10 calls the anticipation engine (*"3 days left. You're 4th. 2nd is 1.1%
# ahead."*). Config over code, per cadence, because "the last few days" of a
# week and of a year are not the same span. Roughly the last quarter of the
# period for the short cadences, tapering for the long ones: a year whose
# last 90 days were all "final stretch" would have no ordinary middle left.
FINAL_STRETCH_DAYS = {
    "week": 2,
    "month": 5,
    "quarter": 10,
    "half": 15,
    "year": 20,
}

# The §10 beats, in order. `closed` is terminal and hands off to the Close
# screen, which is a different surface with its own three-beat budget —
# nothing in this module competes with it.
PHASE_ENTRY_OPEN = "entry_open"
PHASE_BELL = "bell"
PHASE_LIVE = "live"
PHASE_FINAL_STRETCH = "final_stretch"
PHASE_SETTLING = "settling"
PHASE_CLOSED = "closed"


class ArcNotAvailable(Exception):
    """No such run for this user. Never says whether it exists for someone
    else — same posture as `games_board.BoardNotAvailable`."""


def phase_for(field_state: str, entry_state: str, cadence: str, days_left: int) -> str:
    """Which §10 beat a run is in, from state the caller already holds.

    Public and argument-only so `games_service.list_live_runs` can stamp a
    phase on every live run without a second query or a board scan — the
    home screen renders one line per cadence, and paying for a field rank
    per line to print "3 days left" is the cost `arc_for_run` refuses.
    """
    if entry_state in ("finished", "void", "forfeited") or field_state in (
        "closed", "archived",
    ):
        return PHASE_CLOSED
    if field_state == "settling":
        return PHASE_SETTLING
    if field_state in ("announced", "entry_open"):
        return PHASE_ENTRY_OPEN
    if field_state == "locked":
        return PHASE_BELL
    if days_left <= FINAL_STRETCH_DAYS.get(cadence, 2):
        return PHASE_FINAL_STRETCH
    return PHASE_LIVE


def _gap_to_next(rows: list[dict], your_rank: int | None) -> tuple[float | None, int | None]:
    """The TWR gap to the entrant ranked immediately above, and that rank.

    `(None, None)` when you lead, when you are unmeasured, or when the field
    has nobody above you — three different facts that all mean "there is no
    upward gap to state", and none of which may be rendered as 0.0.

    There is deliberately no downward twin (see the module docstring).
    """
    if your_rank is None or your_rank <= 1:
        return None, None
    above = [r for r in rows if r["rank"] is not None and r["rank"] < your_rank]
    if not above:
        return None, None
    nearest = max(above, key=lambda r: r["rank"])
    yours = next((r for r in rows if r["rank"] == your_rank and r["is_you"]), None)
    if yours is None or yours["twr_pct"] is None or nearest["twr_pct"] is None:
        return None, None
    return round(nearest["twr_pct"] - yours["twr_pct"], 2), nearest["rank"]


def _attribution(user_id: UUID, run_id: UUID) -> dict | None:
    """The run's biggest mover, named — §10's *"NVDA drove +1.9% of your
    +2.3%"*. `None` when the run has not traded, when the stake is unknown,
    or when every contribution rounds to zero: a beat that says a name drove
    nothing is worse than no beat.
    """
    from app.services.sim_engine import get_sim_engine

    with get_session() as s:
        portfolio_id, starting_capital = s.execute(
            select(SimPortfolioRow.id, SimPortfolioRow.starting_capital)
            .where(
                SimPortfolioRow.user_id == user_id,
                SimPortfolioRow.run_id == run_id,
                SimPortfolioRow.kind == "game",
            )
        ).first() or (None, None)
    if portfolio_id is None or not starting_capital:
        return None

    legs, _notional = trade_legs_for_run(portfolio_id)
    if not legs:
        return None
    _portfolio, marks, _total, _dd, source = (
        get_sim_engine().portfolio_marks_snapshot(user_id, kind="game", run_id=run_id)
    )
    ranked = contribution_by_ticker(legs, marks, float(starting_capital))
    if not ranked or ranked[0].pct_points == 0:
        return None

    top = ranked[0]
    return {
        "ticker": top.ticker,
        "pct_points": top.pct_points,
        "still_held": top.open_quantity != 0,
        # CR040 — the beat says which prices produced it. A mock-priced
        # attribution that reads as fact is the exact shape of DEF059.
        "price_source": source,
        # Everything the run touched, largest mover first. The client shows
        # the head of this list and nothing else; the full split belongs on
        # the Close's debrief, not in a beat whose whole job is one sentence.
        "all": [
            {"ticker": c.ticker, "pct_points": c.pct_points}
            for c in ranked
        ],
    }


def arc_for_run(user_id: UUID, run_id: UUID, *, now: datetime | None = None) -> dict:
    """`GET /v1/games/runs/{run_id}/arc` — which beat this run is in.

    Deliberately NOT folded into `GET /v1/games/runs/{run_id}`. That payload
    is polled while the run screen is open; this one walks every entrant's
    NAV series to rank the field, and a per-poll board scan would multiply
    that cost by the entrant count for a number that changes once a day.
    """
    now = now or datetime.now(timezone.utc)
    today = now.date()

    with get_session() as s:
        row = s.execute(
            select(GameEntryRow.state, GameFieldRow)
            .join(GameFieldRow, GameEntryRow.field_id == GameFieldRow.id)
            .where(GameEntryRow.user_id == user_id, GameEntryRow.run_id == run_id)
        ).first()
    if row is None:
        raise ArcNotAvailable(f"no run {run_id} for user {user_id}")
    entry_state, field = row
    ends_on: date = field.ends_on
    days_left = max((ends_on - today).days, 0)
    phase = phase_for(field.state, entry_state, field.cadence, days_left)

    board = games_board.board_for_run(user_id, run_id)
    gap_pct, gap_rank = _gap_to_next(board["rows"], board["your_rank"])

    return {
        "run_id": str(run_id),
        "cadence": field.cadence,
        "phase": phase,
        # Both clocks the client counts down to. `locks_at` is an instant
        # (entries close at a wall-clock time); `ends_on` is a trading DATE,
        # because a period ends on a market close, not at a timestamp.
        "locks_at": field.locks_at.isoformat(),
        "starts_on": field.starts_on.isoformat(),
        "ends_on": ends_on.isoformat(),
        "days_left": days_left,
        "entrant_count": board["entrant_count"],
        "desk_count": board["desk_count"],
        "standings_open": board["standings_open"],
        "your_rank": board["your_rank"],
        "your_twr_pct": board["your_twr_pct"],
        # Upward only — see the module docstring's near-miss fence.
        "gap_to_next_pct": gap_pct,
        "gap_to_next_rank": gap_rank,
        "attribution": _attribution(user_id, run_id),
        # Same sentence `games_board` ships, for the same reason: a player
        # watching an unchanged rank all afternoon must be told it is
        # supposed to be unchanged, not left to conclude it is broken.
        "standings_update": "daily_close",
        "as_of": board["as_of"],
    }
