"""An anonymous->claimed merge must carry the CAREER, not just the runs.

`merge_service` re-keyed 24 tables and missed three, all of which the game
depends on. The runs moved, so the gap was invisible from the surfaces that
get looked at:

  * **`career_events`** — `career_points_total` is `SUM(delta)` for a
    user_id, so leaving it behind does not lose a history, it silently sets
    the adopted account's career score to ZERO, and every title and rung
    with it. A player who played a week anonymously and then signed up would
    watch their score vanish at the exact moment the product asks them to
    commit.
  * **`game_duels`** — two user columns, so the usual re-key helper does not
    reach it. Losing them costs the W-L record; worse, `opponent_of()`
    decides which side is "you" by comparing `user_a_id == user_id`, so
    against a stale id it returns the WRONG side and the duel card shows the
    player their own book as the opponent.
  * **`game_short_positions`** — every read is by `portfolio_id` and the
    portfolio moves, so the position keeps working and the row simply
    carries a dead owner. That is exactly why it would not have been noticed.

Two of the three were added the same day as this fix (slice 3b / Amendment
G), which is the argument for testing the merge by INVARIANT — "nothing the
player earned is lost" — rather than table by table.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import (
    CareerEventRow,
    GameDuelRow,
    GameEntryRow,
    GameFieldRow,
    GameShortPositionRow,
    SimPortfolioRow,
    User,
)
from app.services import career_ledger, games_duels
from app.services.auth_service import AuthService
from app.services.merge_service import MergeService

_NOW = datetime(2026, 8, 11, 13, 0, tzinfo=timezone.utc)


def _make_users() -> tuple[User, User]:
    auth = AuthService()
    orphan_au, _, _ = auth.ensure_anonymous(device_user_id=None)
    adopter_au, _, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        orphan = s.execute(select(User).where(User.id == orphan_au.id)).scalar_one()
        adopter = s.execute(select(User).where(User.id == adopter_au.id)).scalar_one()
        adopter.email = "adopter@example.com"
        adopter.is_anonymous = False
        adopter.claimed_at = datetime.now(timezone.utc)
        return orphan, adopter


def _plain_user() -> User:
    """A third party to duel against. NOT `_make_users()[0]` — that helper
    also claims an adopter with a fixed email, and calling it twice trips
    `users.email`'s UNIQUE constraint."""
    au, _, _ = AuthService().ensure_anonymous(device_user_id=None)
    with get_session() as s:
        return s.execute(select(User).where(User.id == au.id)).scalar_one()


def _field(starts_on: date = date(2026, 8, 10)):
    field_id = uuid4()
    with get_session() as s:
        s.add(GameFieldRow(
            id=field_id, cadence="week", starts_on=starts_on,
            ends_on=starts_on + timedelta(days=4),
            entry_opens_at=_NOW - timedelta(days=3),
            locks_at=_NOW - timedelta(hours=1), state="locked",
        ))
    return field_id


def _entry(field_id, user_id):
    entry_id, run_id = uuid4(), uuid4()
    with get_session() as s:
        s.add(GameEntryRow(
            id=entry_id, field_id=field_id, user_id=user_id, run_id=run_id,
            state="finished", entered_at=_NOW, fees_paid=0, trade_count=1,
            final_twr_pct=2.0,
        ))
    return entry_id, run_id


def _award(user_id, field_id, entry_id, delta, reason="run_close", period_key=None):
    with get_session() as s:
        career_ledger.post_career_event(
            s, user_id=user_id, delta_uncapped=delta, reason=reason,
            field_id=field_id, entry_id=entry_id, period_key=period_key,
        )


def _merge(orphan, adopter):
    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)


def _points(user_id) -> int:
    with get_session() as s:
        return career_ledger.career_points_total(s, user_id)


# ── career_events ───────────────────────────────────────────────────────


def test_career_points_survive_the_claim():
    """The headline. Zero here means a player's score vanished on sign-up."""
    orphan, adopter = _make_users()
    field_id = _field()
    entry_id, _run = _entry(field_id, orphan.id)
    _award(orphan.id, field_id, entry_id, 53)
    assert _points(orphan.id) == 53

    _merge(orphan, adopter)

    assert _points(adopter.id) == 53


def test_every_ledger_reason_moves_not_just_the_stipend():
    """The bug the obvious implementation would have had: reusing the
    generic `_rekey_skipping_conflicts(conflict_col=period_key)` leaves every
    row whose `period_key` is NULL behind, because `NULL NOT IN (...)` is
    NULL — falsy. That is every `run_close` and every `duel_result`, i.e.
    almost the whole ledger, and it would have reported a non-zero count and
    looked like a partial success."""
    orphan, adopter = _make_users()
    field_id = _field()
    e1, _ = _entry(field_id, orphan.id)
    _award(orphan.id, field_id, e1, 40, reason="run_close")
    _award(orphan.id, field_id, e1, 5, reason="finish_stipend", period_key="2026-W33")
    _award(orphan.id, field_id, e1, 10, reason="duel_result")

    _merge(orphan, adopter)

    with get_session() as s:
        reasons = sorted(r for (r,) in s.execute(
            select(CareerEventRow.reason).where(CareerEventRow.user_id == adopter.id)
        ).all())
    assert reasons == ["duel_result", "finish_stipend", "run_close"]
    assert _points(adopter.id) == 55


def test_a_stipend_already_claimed_for_the_period_does_not_move():
    """The one real conflict: `uq_career_event_stipend_period` is
    UNIQUE(user_id, period_key) WHERE reason = 'finish_stipend'. Both
    accounts claimed the same week. The adopter's claim wins — the same
    keep-the-adopter's-version rule every other conflict on this path
    follows — and the merge must not raise."""
    orphan, adopter = _make_users()
    field_id = _field()
    orphan_entry, _ = _entry(field_id, orphan.id)
    adopter_entry, _ = _entry(_field(date(2026, 8, 3)), adopter.id)
    _award(orphan.id, field_id, orphan_entry, 5,
           reason="finish_stipend", period_key="2026-W33")
    _award(adopter.id, field_id, adopter_entry, 5,
           reason="finish_stipend", period_key="2026-W33")

    _merge(orphan, adopter)

    with get_session() as s:
        stipends = s.execute(
            select(CareerEventRow).where(
                CareerEventRow.user_id == adopter.id,
                CareerEventRow.reason == "finish_stipend",
            )
        ).scalars().all()
    # Exactly one — not two, which the partial index would have refused.
    assert len(stipends) == 1
    assert stipends[0].period_key == "2026-W33"


def test_a_stipend_for_a_DIFFERENT_period_still_moves():
    """The mutation guard for the test above: dropping every stipend, rather
    than only the colliding one, would also pass it."""
    orphan, adopter = _make_users()
    field_id = _field()
    orphan_entry, _ = _entry(field_id, orphan.id)
    adopter_entry, _ = _entry(_field(date(2026, 8, 3)), adopter.id)
    _award(orphan.id, field_id, orphan_entry, 5,
           reason="finish_stipend", period_key="2026-W33")
    _award(adopter.id, field_id, adopter_entry, 5,
           reason="finish_stipend", period_key="2026-W32")

    _merge(orphan, adopter)

    with get_session() as s:
        periods = sorted(p for (p,) in s.execute(
            select(CareerEventRow.period_key).where(
                CareerEventRow.user_id == adopter.id,
                CareerEventRow.reason == "finish_stipend",
            )
        ).all())
    assert periods == ["2026-W32", "2026-W33"]


# ── game_duels ──────────────────────────────────────────────────────────


def _duel(field_id, a_user, a_run, b_user, b_run, *, winner=None):
    duel_id = uuid4()
    with get_session() as s:
        s.add(GameDuelRow(
            id=duel_id, field_id=field_id, cadence="week", kind="auto",
            user_a_id=a_user, run_a_id=a_run,
            user_b_id=b_user, run_b_id=b_run,
            state="settled", created_at=_NOW, settled_at=_NOW,
            winner_user_id=winner, twr_a_pct=3.0, twr_b_pct=1.0,
            points_delta=10,
        ))
    return duel_id


def test_the_duel_record_survives_the_claim_on_side_a():
    orphan, adopter = _make_users()
    field_id = _field()
    _, orphan_run = _entry(field_id, orphan.id)
    other = _plain_user()
    _, other_run = _entry(_field(date(2026, 8, 3)), other.id)
    _duel(field_id, orphan.id, orphan_run, other.id, other_run, winner=orphan.id)

    _merge(orphan, adopter)

    with get_session() as s:
        rec = games_duels.duel_record(s, adopter.id)
    assert rec["wins"] == 1
    assert rec["losses"] == 0


def test_the_duel_record_survives_when_the_orphan_was_side_b():
    """`_rekey_all` only knows about a `user_id` column. A duel names a user
    on each side and the orphan may be either — a fix that moved only side A
    would pass the test above and lose half the real cases."""
    orphan, adopter = _make_users()
    field_id = _field()
    _, orphan_run = _entry(field_id, orphan.id)
    other = _plain_user()
    _, other_run = _entry(_field(date(2026, 8, 3)), other.id)
    _duel(field_id, other.id, other_run, orphan.id, orphan_run, winner=orphan.id)

    _merge(orphan, adopter)

    with get_session() as s:
        rec = games_duels.duel_record(s, adopter.id)
        duel = s.execute(select(GameDuelRow)).scalars().one()
    assert rec["wins"] == 1
    assert duel.user_b_id == adopter.id
    assert duel.winner_user_id == adopter.id, "the winner pointer moved too"


def test_the_opponent_is_still_the_opponent_after_a_claim():
    """The nastiest consequence of leaving these behind. `opponent_of()`
    decides which side is "you" by comparing `user_a_id == user_id`; against
    a stale id it falls through and returns side A — the player's OWN book —
    as their opponent."""
    orphan, adopter = _make_users()
    field_id = _field()
    _, orphan_run = _entry(field_id, orphan.id)
    other = _plain_user()
    _, other_run = _entry(_field(date(2026, 8, 3)), other.id)
    _duel(field_id, orphan.id, orphan_run, other.id, other_run, winner=orphan.id)

    _merge(orphan, adopter)

    with get_session() as s:
        duel = s.execute(select(GameDuelRow)).scalars().one()
        opponent_user, opponent_run = games_duels.opponent_of(duel, adopter.id)
    assert opponent_user == other.id
    assert opponent_run == other_run
    assert opponent_run != orphan_run, "the player was shown their own book"


# ── game_short_positions ────────────────────────────────────────────────


def test_an_open_short_changes_owner_with_the_portfolio():
    orphan, adopter = _make_users()
    field_id = _field()
    _, run_id = _entry(field_id, orphan.id)
    portfolio_id = uuid4()
    with get_session() as s:
        s.add(SimPortfolioRow(
            id=portfolio_id, user_id=orphan.id, kind="game", run_id=run_id,
            name="Game", starting_capital=10_000, current_cash=9_000,
        ))
        s.add(GameShortPositionRow(
            id=uuid4(), user_id=orphan.id, run_id=run_id,
            portfolio_id=portfolio_id, ticker="TSLA",
            quantity=10, entry_price=200, cash_posted=2_000, fee_paid=6,
            opened_at=_NOW, state="open",
        ))

    _merge(orphan, adopter)

    with get_session() as s:
        row = s.execute(select(GameShortPositionRow)).scalars().one()
        portfolio = s.execute(
            select(SimPortfolioRow).where(SimPortfolioRow.id == portfolio_id)
        ).scalars().one()
    # The row must not be left pointing at a dead owner while the portfolio
    # it belongs to has moved on.
    assert row.user_id == adopter.id
    assert portfolio.user_id == adopter.id


# ── the invariant, not the table list ───────────────────────────────────


def test_nothing_the_player_earned_stays_on_the_dead_account():
    """Written as an invariant on purpose. Two of the three tables this
    fixes were added the same day the gap was found, so a table-by-table
    test would go stale the next time the game grows a table."""
    orphan, adopter = _make_users()
    field_id = _field()
    entry_id, run_id = _entry(field_id, orphan.id)
    _award(orphan.id, field_id, entry_id, 30)
    other = _plain_user()
    _, other_run = _entry(_field(date(2026, 8, 3)), other.id)
    _duel(field_id, orphan.id, run_id, other.id, other_run, winner=orphan.id)

    _merge(orphan, adopter)

    with get_session() as s:
        assert career_ledger.career_points_total(s, orphan.id) == 0
        assert s.execute(
            select(CareerEventRow).where(CareerEventRow.user_id == orphan.id)
        ).scalars().all() == []
        assert s.execute(
            select(GameEntryRow).where(GameEntryRow.user_id == orphan.id)
        ).scalars().all() == []
        rec = games_duels.duel_record(s, orphan.id)
    assert rec["settled"] == 0, "a duel still names the dead account"
