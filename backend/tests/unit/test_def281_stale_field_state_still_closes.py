"""DEF281 — a field whose `state` column went stale still gets scored.

**Found on live Alpha, 2026-08-13.** The weekly field that locked on 08-10 was
still reading `entry_open` three days later, with **4 active runs in it** and
`ends_on = 08-14`. The scoring pass selected `WHERE state == 'live'`, so it
would have skipped that field on every pass, forever — no error, no log, four
runs that simply never close.

**Why the column goes stale is by design, not by accident.** `ensure_field`
refreshes the state of the field it is currently TARGETING, and mid-period
that is the NEXT period's row — its own docstring says so, and warns that
*"a field that is currently locked or live can therefore hold a stale
`state`"*. Nothing else advances a calendar field. So this week's row reads
`entry_open` for the entire week it is actually live.

`games_desks.fields_in_lock_window` already hit this exact wall and already
derives from timestamps, with a docstring reading *"filtering on the stale
column would have found nothing, every week, silently."* **That fix was
applied to one query and not to its sibling** — which is the whole shape of
this defect, and the reason the guard below is written against the calendar
rather than against a list of acceptable state strings.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.db import get_session
from app.db.models import GameEntryRow, GameFieldRow, PortfolioNavDailyRow
from app.schemas.trade import Side
from app.services import games_scoring_pass as pass_module
from app.services import games_service as games

_ENTRY_OPEN_CLOSED_MARKET = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)
_MARKET_OPEN = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)
_STARTS_ON = date(2026, 8, 10)
_MID = date(2026, 8, 12)
_ENDS_ON = date(2026, 8, 14)
_AFTER_CLOSE = datetime(2026, 8, 17, 15, 0, tzinfo=timezone.utc)


def _entrant(end_nav: float = 10_400.0):
    user_id = uuid4()
    entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=1,
        now=_MARKET_OPEN,
    )
    for as_of, nav, ev in (
        (_STARTS_ON, 10_000.0, "open"),
        (_MID, (10_000.0 + end_nav) / 2, None),
        (_ENDS_ON, end_nav, None),
    ):
        with get_session() as s:
            s.add(PortfolioNavDailyRow(
                user_id=user_id, run_id=entry.run_id, as_of_date=as_of, nav=nav,
                cash=nav, price_source="live", capital_event=ev,
            ))
    return user_id, entry.id


def _force_field_state(value: str) -> None:
    """Reproduce the live condition exactly: the period is over, the runs are
    active, and the column still says entries are open."""
    with get_session() as s:
        for field in s.execute(select(GameFieldRow)).scalars().all():
            if field.starts_on == _STARTS_ON:
                field.state = value


def _entry_states() -> list[str]:
    with get_session() as s:
        return [
            e.state for e in s.execute(select(GameEntryRow)).scalars().all()
        ]


def test_a_field_stuck_at_entry_open_still_closes():
    """The live case. Without the fix this asserts `['active']` — the run is
    never scored and never will be."""
    _entrant()
    _force_field_state("entry_open")

    stats = pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    assert stats["fields_closed"] == 1
    assert _entry_states() == ["finished"]


def test_a_field_stuck_at_locked_still_closes():
    """The other stale value `_resolve_state` can leave behind — a field that
    locked but whose market open had not arrived when it was last refreshed."""
    _entrant()
    _force_field_state("locked")

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    assert _entry_states() == ["finished"]


def test_an_abandoned_field_is_still_never_scored():
    """§12 — a rolling lobby that never filled has no result. Closing it would
    mint a close for a contest that did not happen, so the widening must not
    reach it."""
    _entrant()
    _force_field_state("abandoned")

    stats = pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    assert stats["fields_closed"] == 0
    assert _entry_states() == ["active"]


def test_a_closed_field_is_not_rescored():
    """Re-scoring would change a result the player has already been shown."""
    _entrant()
    _force_field_state("live")
    pass_module.run_scoring_pass(now=_AFTER_CLOSE)
    assert _entry_states() == ["finished"]

    stats = pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    assert stats["fields_closed"] == 0


def test_a_field_whose_period_has_not_ended_is_left_alone():
    """The guard is the CALENDAR. A live field mid-period must not be swept
    up by widening the state filter."""
    _entrant()
    _force_field_state("entry_open")

    stats = pass_module.run_scoring_pass(
        now=datetime(2026, 8, 12, 15, 0, tzinfo=timezone.utc),
    )

    assert stats["fields_closed"] == 0
    assert _entry_states() == ["active"]


# ── The surface Saiful actually saw ──────────────────────────────────────


def test_a_mid_run_field_does_not_claim_entries_are_open():
    """Saiful, 2026-08-13, on a run three days into its week: *"Market closed
    a while ago. Telling it it closes soon."*

    The weekly field that locked on 08-10 still read `entry_open`, so the arc
    beat rendered the entry countdown — on a field whose entries had closed
    days earlier and whose countdown had long since run out.
    """
    from app.services.games_arc import (
        PHASE_ENTRY_OPEN, PHASE_FINAL_STRETCH, PHASE_LIVE, phase_for,
    )

    phase = phase_for(
        "entry_open", "active", "week", 1,
        now=datetime(2026, 8, 13, 5, 30, tzinfo=timezone.utc),
        locks_at=datetime(2026, 8, 10, 13, 0, tzinfo=timezone.utc),
        starts_on=date(2026, 8, 10),
    )

    assert phase != PHASE_ENTRY_OPEN
    assert phase in (PHASE_LIVE, PHASE_FINAL_STRETCH)


def test_entries_genuinely_still_open_still_read_as_open():
    """The clock is the authority in both directions — the fix must not
    swallow a real entry window."""
    from app.services.games_arc import PHASE_ENTRY_OPEN, phase_for

    assert phase_for(
        "entry_open", "entered", "week", 7,
        now=datetime(2026, 8, 13, 5, 30, tzinfo=timezone.utc),
        locks_at=datetime(2026, 8, 17, 13, 0, tzinfo=timezone.utc),
        starts_on=date(2026, 8, 17),
    ) == PHASE_ENTRY_OPEN


def test_locked_but_not_started_is_the_bell():
    from app.services.games_arc import PHASE_BELL, phase_for

    assert phase_for(
        "entry_open", "entered", "week", 7,
        now=datetime(2026, 8, 17, 14, 0, tzinfo=timezone.utc),
        locks_at=datetime(2026, 8, 17, 13, 0, tzinfo=timezone.utc),
        starts_on=date(2026, 8, 18),
    ) == PHASE_BELL
