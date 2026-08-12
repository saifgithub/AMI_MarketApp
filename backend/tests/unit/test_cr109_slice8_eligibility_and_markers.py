"""CR109 slice 8 — §8.5 eligibility, §8.4 progress markers.

**§8.5 is not hypothetical and it is not distant.** Slice 3c's house desks
fill every field to the target size, so at alpha field sizes the desks ARE
most of the field and the likeliest winner of the first weekly field with
desks in it is a desk. Without the pass-down the game's first champion is the
house — which is why the tests below use a field the house wins.

**§8.4 is the half the design says matters more than the champion prize:**
*"If one player in 26 receives something, twenty-five received nothing, and
that is the churn."* The property under test throughout is that a marker is
a THRESHOLD CROSSED and never a thing that happens for showing up — the
stipend already pays for showing up.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import GameEntryRow, GameFieldRow, PortfolioNavDailyRow, User
from app.schemas.trade import Side
from app.services import games_board, games_eligibility, games_markers
from app.services import games_record_service as record_service
from app.services import games_scoring_pass as pass_module
from app.services import games_service as games

_ENTRY_OPEN_CLOSED_MARKET = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)
_MARKET_OPEN = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)
_STARTS_ON = date(2026, 8, 10)
_MID = date(2026, 8, 12)
_ENDS_ON = date(2026, 8, 14)
_AFTER_CLOSE = datetime(2026, 8, 17, 15, 0, tzinfo=timezone.utc)


# ── §8.5 as one rule ─────────────────────────────────────────────────────


def test_the_one_rule_covers_desks_and_affiliates_alike():
    assert games_eligibility.ineligibility_reason(
        is_desk=False, title_ineligible=False,
    ) is None
    assert games_eligibility.ineligibility_reason(
        is_desk=True, title_ineligible=False,
    ) == games_eligibility.REASON_HOUSE_DESK
    assert games_eligibility.ineligibility_reason(
        is_desk=False, title_ineligible=True,
    ) == games_eligibility.REASON_AFFILIATED


def test_a_desk_is_ineligible_from_is_desk_not_from_the_stored_flag():
    """A desk minted by a future `ensure_desk_users()` that forgot to set the
    flag would otherwise be eligible for the title it was built to be
    excluded from — and the failure would be SILENT: the house simply wins,
    which reads as a strong strategy rather than as a bug."""
    assert games_eligibility.ineligibility_reason(
        is_desk=True, title_ineligible=False,
    ) is not None


def test_an_unknown_user_is_not_awarded_to():
    """Defaulting the other way would make a missing row an award."""
    assert games_eligibility.title_eligible(uuid4()) is False


# ── The champion passes down ─────────────────────────────────────────────


def _nav(user_id, run_id, *, end_nav):
    for as_of, nav, ev in (
        (_STARTS_ON, 10_000.0, "open"),
        (_MID, (10_000.0 + end_nav) / 2, None),
        (_ENDS_ON, end_nav, None),
    ):
        with get_session() as s:
            s.add(PortfolioNavDailyRow(
                user_id=user_id, run_id=run_id, as_of_date=as_of, nav=nav,
                cash=nav, price_source="live", capital_event=ev,
            ))


def _entrant(end_nav: float, *, desk: bool = False, affiliated: bool = False):
    user_id = uuid4()
    with get_session() as s:
        s.add(User(
            id=user_id, handle=f"E{str(user_id)[:4]}", is_desk=desk,
            desk_key=f"k{str(user_id)[:8]}" if desk else None,
            title_ineligible=affiliated,
        ))
    entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=1,
        now=_MARKET_OPEN,
    )
    _nav(user_id, entry.run_id, end_nav=end_nav)
    return user_id, entry.run_id, entry.id


def _make_live():
    with get_session() as s:
        for field in s.execute(select(GameFieldRow)).scalars().all():
            if field.state in ("entry_open", "locked"):
                field.state = "live"


def _the_field() -> GameFieldRow:
    with get_session() as s:
        return s.execute(
            select(GameFieldRow).where(GameFieldRow.state == "closed")
        ).scalars().first()


def test_the_house_wins_the_field_but_does_not_hold_the_title():
    """The case that arrives the moment desks meet a real player."""
    _desk = _entrant(12_000.0, desk=True)
    human = _entrant(11_000.0)
    _make_live()

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    field = _the_field()
    assert field.champion_entry_id == human[2]
    assert field.champion_rank == 2, "the title passed down from rank 1"


def test_the_board_still_shows_what_actually_happened():
    """*"Ineligible does not mean invisible"* — the desk keeps rank 1 on the
    board. Only the TITLE moves, and the board says so."""
    _desk = _entrant(12_000.0, desk=True)
    human = _entrant(11_000.0)
    _make_live()
    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    board = games_board.board_for_run(human[0], human[1])

    leader = next(r for r in board["rows"] if r["rank"] == 1)
    assert leader["is_desk"] is True
    assert leader["title_ineligible_reason"] == games_eligibility.REASON_HOUSE_DESK
    assert board["champion"]["rank"] == 2
    assert board["champion"]["displaced"] is True


def test_an_eligible_winner_is_not_marked_as_displaced():
    human = _entrant(12_000.0)
    _desk = _entrant(11_000.0, desk=True)
    _make_live()
    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    board = games_board.board_for_run(human[0], human[1])

    assert board["champion"]["rank"] == 1
    assert board["champion"]["displaced"] is False


def test_an_affiliated_human_ranks_but_does_not_hold_the_title():
    """The operator dogfooding. §8.5: *"2026 Annual Champion: Saiful" is a
    problem whether or not anyone doubts he earned it.*"""
    operator = _entrant(12_000.0, affiliated=True)
    other = _entrant(11_000.0)
    _make_live()
    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    field = _the_field()
    board = games_board.board_for_run(other[0], other[1])

    assert field.champion_entry_id == other[2]
    leader = next(r for r in board["rows"] if r["rank"] == 1)
    assert leader["title_ineligible_reason"] == games_eligibility.REASON_AFFILIATED


def test_an_all_desk_field_has_a_leader_and_no_champion():
    """A hole is the honest answer. Inventing a champion here would be the
    silent renumbering §8.5 names as the failure to avoid."""
    _entrant(12_000.0, desk=True)
    _entrant(11_000.0, desk=True)
    _make_live()

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    field = _the_field()
    assert field.champion_entry_id is None
    assert field.champion_rank is None


def test_career_points_still_accrue_to_the_ineligible():
    """§8.5's scope is narrow ON PURPOSE — titles, champion rewards and
    permanent flair only. Points still move so Saiful can dogfood progression
    and the desks populate a meaningful spread."""
    desk = _entrant(12_000.0, desk=True)
    _entrant(11_000.0)
    _make_live()
    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    with get_session() as s:
        row = s.execute(
            select(GameEntryRow).where(GameEntryRow.id == desk[2])
        ).scalar_one()
    assert row.state == "finished"
    assert row.final_rank == 1


# ── §8.4 progress markers ────────────────────────────────────────────────


def _close_a_run(
    *, end_nav: float, week: int, user_id: UUID | None = None,
) -> tuple[UUID, UUID]:
    """One full run for `user_id`, closed, in the weekly field `week` weeks
    on. The offset is required rather than derived: the one-live-run-per-
    cadence rule means a second entry into the SAME field is refused, so a
    run HISTORY only exists if each run sits in its own week.
    """
    from datetime import timedelta

    user_id = user_id or uuid4()
    shift = timedelta(days=7 * week)
    entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET + shift)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=1,
        now=_MARKET_OPEN + shift,
    )
    for as_of, nav, ev in (
        (_STARTS_ON + shift, 10_000.0, "open"),
        (_MID + shift, (10_000.0 + end_nav) / 2, None),
        (_ENDS_ON + shift, end_nav, None),
    ):
        with get_session() as s:
            s.add(PortfolioNavDailyRow(
                user_id=user_id, run_id=entry.run_id, as_of_date=as_of, nav=nav,
                cash=nav, price_source="live", capital_event=ev,
            ))
    _make_live()
    pass_module.run_scoring_pass(now=_AFTER_CLOSE + shift)
    return user_id, entry.run_id


def test_the_first_finish_is_its_own_marker():
    user_id, run_id = _close_a_run(end_nav=9_500.0, week=0)

    marker = games_markers.marker_for_close(user_id, run_id)

    assert marker["kind"] == games_markers.MARKER_FIRST_FINISH


def test_a_first_positive_run_outranks_a_personal_best():
    """A first can never happen again; a best can. §8.4's priority follows
    firsts → bests → streaks for exactly that reason."""
    user_id, _first = _close_a_run(end_nav=9_000.0, week=0)
    _same, second = _close_a_run(end_nav=10_400.0, week=1, user_id=user_id)

    marker = games_markers.marker_for_close(user_id, second)

    assert marker["kind"] == games_markers.MARKER_FIRST_POSITIVE
    assert marker["value"] > 0


def test_beating_your_own_best_is_a_marker():
    user_id, _a = _close_a_run(end_nav=10_200.0, week=0)
    _same, _b = _close_a_run(end_nav=10_100.0, week=1, user_id=user_id)
    _same2, c = _close_a_run(end_nav=10_900.0, week=2, user_id=user_id)

    marker = games_markers.marker_for_close(user_id, c)

    assert marker["kind"] == games_markers.MARKER_PERSONAL_BEST


def test_an_ordinary_close_earns_no_marker():
    """`None` is a real and frequent answer. A marker invented for every
    close is the participation trophy §8.4 opens by excluding."""
    user_id, _a = _close_a_run(end_nav=10_500.0, week=0)
    _same, b = _close_a_run(end_nav=10_100.0, week=1, user_id=user_id)

    assert games_markers.marker_for_close(user_id, b) is None


def test_the_podium_marker_needs_a_field_worth_placing_in():
    """§8.4 says "first time in the top ten", which presupposes more than ten
    entrants. In a field of two, everyone is in the top ten — the phrase is
    not a smaller version of itself there, it is meaningless."""
    assert games_markers.PODIUM_MIN_FIELD >= 8


def test_a_void_run_earns_no_marker():
    """A run whose prices were never usable has nothing to be evidence of."""
    user_id, run_id = _close_a_run(end_nav=10_500.0, week=0)
    with get_session() as s:
        row = s.execute(
            select(GameEntryRow).where(GameEntryRow.run_id == run_id)
        ).scalar_one()
        row.state = "void"

    assert games_markers.marker_for_close(user_id, run_id) is None


def test_the_marker_rides_the_close_payload():
    user_id, run_id = _close_a_run(end_nav=10_500.0, week=0)

    close = record_service.get_close_payload(user_id, run_id)

    assert close["marker"]["kind"] == games_markers.MARKER_FIRST_FINISH


def test_markers_never_touch_the_career_ledger():
    """§10.4's fence, asserted against the module rather than reviewed: the
    ledger must never pay for a marker, or markers become a farm."""
    source = (games_markers.__file__)
    with open(source, "r", encoding="utf-8") as fh:
        text = fh.read()
    assert "career_ledger" not in text.split('"""')[-1], (
        "games_markers must not import or call the career ledger"
    )
