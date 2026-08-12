"""CR109 — the field board: where you stand against everyone else in your run.

Saiful, playing the shipped build: *"How do I see my current standing against
the rest of the field in the weekly game?"* The answer until now was "you
can't" — the Close payload carried a rank, but only after the run ended, and
with a field of one there was nothing to rank against anyway. Slice 3c supplies
the field (house desks); this supplies the board.

**Three invariants, and each one is a rule from the design rather than a
preference.**

1. **Rank on % TWR only, never absolute AMI Cash** (§6.1, written down as an
   invariant precisely so it would be tested). The moment a board ranks money,
   capital tier becomes pay-to-win and the "no purchase necessary" position in
   `competition_rules.md` collapses. No row in this module's output carries a
   currency amount — not another player's, not your own.

2. **A board never renders a mirror.** `counterfactual_hold_index_pct` and
   `counterfactual_hold_first_picks_pct` are private measurement (§10.4), and
   the fence says assert it at the serializer, not the widget. The serializer
   here builds its rows field-by-field from an explicit allowlist, so a mirror
   cannot arrive by a later `**row` splat.

3. **Standings move once per close, never per tick** (§10). Ranking off live
   marks would make the board flicker all day and turn a contest into a slot
   machine; it would also cost one quote per holding per entrant per pull. The
   board is therefore computed from the daily NAV series — the same series the
   Close scores on — and says out loud which close it is as of.

The third invariant has a consequence worth stating plainly rather than hiding:
**on day one a run has no completed close, so it has no TWR.** That is reported
as `null` with an explicit `standings_open` flag. It is deliberately NOT
reported as 0.00% — a run that has not been measured and a run that is exactly
flat are different facts, and collapsing them is the `?? 0` defect class that
has bitten this feature nine times already.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.db import get_session
from app.db.models import GameEntryRow, GameFieldRow, User
from app.services import games_eligibility
from app.services.games_desks import DESKS_BY_KEY
from app.services.portfolio_nav_daily import nav_history, twr_pct_for_window

# Entry states that belong on a live board. A forfeited entry leaves the board
# (its owner restarted into a new run); a scored one stays, because after the
# close the board IS the result.
_RANKABLE_STATES = ("entered", "active", "finished", "void")


class BoardNotAvailable(Exception):
    """The run has no field, or the caller does not own the run."""


def _entrant_row(user_id: UUID, run_id: UUID) -> dict:
    """One entrant's board row. Built field-by-field from an allowlist — never
    by splatting a DB row — so a column added to `game_entries` later (a
    mirror, a fee total, a cash balance) cannot leak onto a public board just
    because someone widened a select."""
    rows = nav_history(user_id, run_id=run_id)
    twr = twr_pct_for_window(rows)
    with get_session() as s:
        handle, display_name, is_desk, desk_key, title_ineligible = s.execute(
            select(User.handle, User.display_name, User.is_desk, User.desk_key,
                   User.title_ineligible)
            .where(User.id == user_id)
        ).first() or (None, None, False, None, False)
    desk = DESKS_BY_KEY.get(desk_key or "")
    return {
        "handle": handle or display_name or "Unnamed",
        "is_desk": bool(is_desk),
        "desk_key": desk_key,
        "desk_rule": desk.rule if desk else None,
        # CR109 slice 8 §8.5 — published, not hidden. *"Ineligible does not
        # mean invisible"*: the entrant ranks, the board shows what actually
        # happened, and the row says out loud that this one cannot hold the
        # title. A silent exclusion is the tell §11.2 exists to avoid.
        "title_ineligible_reason": games_eligibility.ineligibility_reason(
            is_desk=bool(is_desk), title_ineligible=bool(title_ineligible),
        ),
        # None means "not measured yet", NOT "flat". The client renders a dash.
        "twr_pct": twr,
        "closes_counted": max(0, len(rows) - 1),
    }


def _rank(rows: list[dict]) -> list[dict]:
    """Standard competition ranking on TWR descending. Unmeasured entrants
    (no close yet) sort last and carry `rank: None` rather than a made-up
    position — an unranked entrant is a fact, not a tie for last."""
    measured = [r for r in rows if r["twr_pct"] is not None]
    unmeasured = [r for r in rows if r["twr_pct"] is None]
    measured.sort(key=lambda r: (-r["twr_pct"], r["handle"]))

    out: list[dict] = []
    previous: float | None = None
    previous_rank = 0
    for i, row in enumerate(measured, start=1):
        if previous is not None and row["twr_pct"] == previous:
            row = {**row, "rank": previous_rank}
        else:
            row = {**row, "rank": i}
            previous_rank = i
            previous = row["twr_pct"]
        out.append(row)
    unmeasured.sort(key=lambda r: r["handle"])
    out.extend({**r, "rank": None} for r in unmeasured)
    return out


def _champion_view(entry_id: UUID | None, rank: int | None) -> dict | None:
    """The field's title-holder, resolved to a handle. Carries `displaced` so
    a client can say *"Title: SLATE_07 (2nd overall)"* — §8.5's own example —
    instead of printing a 2 where a 1 is expected and looking like a bug."""
    if entry_id is None or rank is None:
        return None
    with get_session() as s:
        row = s.execute(
            select(User.handle, User.display_name)
            .join(GameEntryRow, GameEntryRow.user_id == User.id)
            .where(GameEntryRow.id == entry_id)
        ).first()
    if row is None:
        return None
    return {
        "handle": row[0] or row[1] or "Unnamed",
        "rank": rank,
        "displaced": rank > 1,
    }


def board_for_run(user_id: UUID, run_id: UUID) -> dict:
    """`GET /v1/games/runs/{run_id}/board`.

    Ownership is checked against the caller's own entry, so a run id alone
    does not open somebody else's field — which matters here because the board
    is the one payload that names other entrants at all.
    """
    with get_session() as s:
        mine = s.execute(
            select(GameEntryRow.field_id, GameEntryRow.user_id)
            .where(GameEntryRow.run_id == run_id, GameEntryRow.user_id == user_id)
        ).first()
        if mine is None:
            raise BoardNotAvailable(f"no run {run_id} for user {user_id}")
        field_id = mine[0]

        field = s.execute(
            select(
                GameFieldRow.cadence, GameFieldRow.state, GameFieldRow.starts_on,
                GameFieldRow.ends_on, GameFieldRow.benchmark_ticker,
                GameFieldRow.champion_entry_id, GameFieldRow.champion_rank,
            ).where(GameFieldRow.id == field_id)
        ).first()

        entrants = s.execute(
            select(GameEntryRow.user_id, GameEntryRow.run_id)
            .where(
                GameEntryRow.field_id == field_id,
                GameEntryRow.state.in_(_RANKABLE_STATES),
            )
        ).all()

    cadence, state, starts_on, ends_on, benchmark, champion_entry_id, champion_rank = field

    # Marked by run_id, not by name: two entrants can share a display name and
    # the "(you)" marker has to be right regardless.
    built = []
    for uid, rid in entrants:
        row = _entrant_row(uid, rid)
        row["is_you"] = rid == run_id
        built.append(row)
    rows = _rank(built)

    your_row = next((r for r in rows if r["is_you"]), None)
    measured = [r for r in rows if r["rank"] is not None]
    return {
        "field_id": str(field_id),
        "cadence": cadence,
        "state": state,
        "starts_on": starts_on.isoformat() if isinstance(starts_on, date) else str(starts_on),
        "ends_on": ends_on.isoformat() if isinstance(ends_on, date) else str(ends_on),
        "benchmark_ticker": benchmark or "SPY",
        "entrant_count": len(rows),
        "desk_count": sum(1 for r in rows if r["is_desk"]),
        # False until at least one entrant has a completed close. The client
        # must render "standings open after the first close", never a field of
        # zeroes that reads like everyone is tied and flat.
        "standings_open": bool(measured),
        "your_rank": your_row["rank"] if your_row else None,
        "your_twr_pct": your_row["twr_pct"] if your_row else None,
        # CR109 slice 8 §8.5. Present only on a CLOSED field. `rank > 1` is
        # the case the design cares about: the leader could not hold the
        # title, so it passed down, and the board must say so rather than
        # renumber. `None` on an all-desk field — a leader with no champion
        # is a fact, and inventing one would be the silent promotion §8.5
        # names as the failure to avoid.
        "champion": _champion_view(champion_entry_id, champion_rank),
        "rows": rows,
        "as_of": datetime.now(timezone.utc).isoformat(),
        # Said out loud: this board moves once per close, not per tick. Without
        # it a player watching an unchanged number all afternoon concludes the
        # feature is broken (CR040 — degrade loudly applies to staleness too).
        "updates": "daily_close",
    }
