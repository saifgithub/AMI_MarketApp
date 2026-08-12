"""CR109 slice 4 — demand-gated rolling starts for Q/H/Y, and ABANDONED.

Saiful named the hole this closes: *"we need to think the cohorts for the
longer game, since we allow rolling start. on a popular platform, this is
great. but on a new platform, we may find a month with a single player!"*

Calendar anchoring answers it badly in the other direction — a player who
finds the game on 2 October waits until 1 January to start an annual run.

The invariant that must survive all of it: **everyone in a field still starts
the same day.** That is the property §6.2 chose placement scoring for, and it
is why thin fields cannot instead be fixed by merging cohorts across start
dates — which is the obvious first idea and the wrong one.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import GameEntryRow, GameFieldRow
from app.services import games_service as games

_NOW = datetime(2026, 8, 12, 3, 0, tzinfo=timezone.utc)


def _lobby(cadence: str) -> GameFieldRow:
    with get_session() as s:
        return s.execute(
            select(GameFieldRow).where(
                GameFieldRow.cadence == cadence,
                GameFieldRow.state.in_(("announced", "entry_open")),
            )
        ).scalars().first()


def _field_by_id(field_id) -> GameFieldRow:
    with get_session() as s:
        return s.execute(
            select(GameFieldRow).where(GameFieldRow.id == field_id)
        ).scalar_one()


def _fill(cadence: str, n: int, *, now=_NOW) -> list:
    return [
        games.enter_field(uuid4(), cadence=cadence, now=now) for _ in range(n)
    ]


# ── The pure rule ────────────────────────────────────────────────────────


def test_a_filled_lobby_starts_immediately():
    assert games.rolling_decision(entrants=8, lobby_age_days=0) == "start_now"


def test_a_lobby_that_waited_out_its_month_as_a_contest_starts():
    # Two people who each waited a month should play, not wait for a
    # calendar boundary neither of them chose.
    assert games.rolling_decision(entrants=2, lobby_age_days=30) == "start_now"


def test_a_lone_entrant_who_waited_out_the_month_is_rolled_not_started():
    # §6.6 problem 2: first-of-one pays the largest prize in the game for
    # beating nobody, which makes "find the rolling start nobody entered"
    # the rational play on a thin platform.
    assert games.rolling_decision(entrants=1, lobby_age_days=30) == "abandon"


def test_an_empty_lobby_waits_rather_than_churning():
    # Nobody is being kept waiting and there is nothing to roll forward, so
    # abandoning and recreating an empty row every 30 days would be motion
    # with no purpose. It rides its calendar anchor — "quarterly on a new
    # platform", which is §6.6's own description of the desired behaviour.
    assert games.rolling_decision(entrants=0, lobby_age_days=365) == "wait"


@pytest.mark.parametrize("age", [0, 1, 29.9])
def test_a_partial_lobby_inside_the_wait_keeps_waiting(age):
    assert games.rolling_decision(entrants=3, lobby_age_days=age) == "wait"


# ── The run length ───────────────────────────────────────────────────────


def test_a_rolling_run_is_a_full_period_from_the_day_it_started():
    # NOT the remainder of the calendar period it landed in. The existing
    # `_add_months` snaps to the 1st, which every calendar cadence wants and
    # this one must not have: it would sell a 72-day run as a quarter.
    assert games.rolling_end("quarter", date(2026, 8, 20)) == date(2026, 11, 19)
    assert games.rolling_end("half", date(2026, 8, 20)) == date(2027, 2, 19)
    assert games.rolling_end("year", date(2026, 8, 20)) == date(2027, 8, 19)


def test_month_end_arithmetic_clamps_rather_than_overflowing():
    assert games.rolling_end("quarter", date(2026, 11, 30)) == date(2027, 2, 27)
    assert games.rolling_end("year", date(2028, 2, 29)) == date(2029, 2, 27)


# ── The lobby ────────────────────────────────────────────────────────────


def test_a_rolling_lobby_accepts_entries_the_moment_it_exists():
    # The calendar `entry_opens_at` would leave a quarterly lobby
    # `announced` — visible and unjoinable — for most of a quarter, which is
    # the wait this whole mechanism exists to remove.
    with get_session() as s:
        field = games.ensure_field(s, "quarter", now=_NOW)
        assert field.state == "entry_open"
        assert field.min_entrants == games.ROLLING_MIN_ENTRANTS
        assert field.max_wait_days == games.ROLLING_MAX_WAIT_DAYS


def test_a_calendar_cadence_carries_no_demand_gate():
    # Those two columns have no reading on a weekly field: it starts on
    # Monday whoever turned up.
    with get_session() as s:
        for cadence in ("week", "month"):
            field = games.ensure_field(s, cadence, now=_NOW)
            assert field.min_entrants is None
            assert field.max_wait_days is None


def test_filling_a_lobby_pulls_its_start_forward():
    _fill("quarter", games.ROLLING_MIN_ENTRANTS)
    before = _lobby("quarter")
    assert before.starts_on > date(2026, 9, 1), "precondition: anchored a quarter out"

    stats = games.run_rolling_start_tick(now=_NOW)

    assert stats["started"] == 1
    after = _field_by_id(before.id)
    assert after.starts_on <= date(2026, 8, 14)
    assert after.ends_on == games.rolling_end("quarter", after.starts_on)


def test_the_pulled_forward_field_still_has_a_lock_window_for_the_desks():
    # `games_desks.fields_in_lock_window` fills a field between `locks_at`
    # and its market open. A rolling start that skipped that window would
    # ship opponent-less fields, silently.
    _fill("quarter", games.ROLLING_MIN_ENTRANTS)
    games.run_rolling_start_tick(now=_NOW)

    row = _field_by_id(_lobby("quarter").id)
    assert games._as_utc(row.locks_at) < games._market_open_et(row.starts_on)
    assert games._market_open_et(row.starts_on) - games._as_utc(row.locks_at) \
        == games._LOCK_BUFFER


def test_everyone_in_a_pulled_forward_field_starts_the_same_day():
    # The property placement scoring rests on. A rolling start moves the
    # WHOLE field's date, never one entrant's.
    entries = _fill("quarter", games.ROLLING_MIN_ENTRANTS)
    games.run_rolling_start_tick(now=_NOW)
    with get_session() as s:
        field_ids = {
            s.execute(
                select(GameEntryRow.field_id).where(GameEntryRow.id == e.id)
            ).scalar_one()
            for e in entries
        }
    assert len(field_ids) == 1


def test_a_scheduled_lobbys_start_never_moves_again():
    # The bug this closes: a lobby that keeps filling would re-decide its
    # own start on every tick, so the players already waiting on a date
    # would watch it recede as the field grew.
    _fill("quarter", games.ROLLING_MIN_ENTRANTS)
    first = games.run_rolling_start_tick(now=_NOW)
    scheduled = _lobby("quarter")
    assert first["started"] == 1

    # A day later, with more entrants, and the tick runs again.
    _fill("quarter", 4, now=_NOW + timedelta(hours=2))
    second = games.run_rolling_start_tick(now=_NOW + timedelta(hours=2))

    assert second["started"] == 0
    assert _field_by_id(scheduled.id).starts_on == scheduled.starts_on


def test_a_scheduled_lobby_keeps_taking_entrants_until_it_locks():
    # Scheduling is not closing. The lock window is what the desks fill in,
    # and a player who arrives an hour after the gate trips should join the
    # field that is about to run rather than wait for the next one.
    _fill("quarter", games.ROLLING_MIN_ENTRANTS)
    games.run_rolling_start_tick(now=_NOW)
    scheduled = _lobby("quarter")
    assert scheduled.starts_decided_at is not None

    late = games.enter_field(uuid4(), cadence="quarter", now=_NOW)
    assert late.field_id == scheduled.id
    assert _field_by_id(scheduled.id).entrant_count == games.ROLLING_MIN_ENTRANTS + 1


def test_a_locked_lobby_is_replaced_by_a_fresh_one_for_the_next_player():
    _fill("quarter", games.ROLLING_MIN_ENTRANTS)
    games.run_rolling_start_tick(now=_NOW)
    scheduled_id = _lobby("quarter").id

    # Past the lock: the scheduled field is no longer accepting.
    after_lock = _NOW + timedelta(days=1)
    with get_session() as s:
        fresh = games.ensure_field(s, "quarter", now=after_lock)
    assert fresh.id != scheduled_id
    assert fresh.entrant_count == 0
    assert fresh.starts_decided_at is None


# ── ABANDONED ────────────────────────────────────────────────────────────


_LATE = _NOW + timedelta(days=31)


def test_a_lobby_that_never_filled_is_abandoned_and_its_entrant_rolls_forward():
    entry = _fill("quarter", 1)[0]
    lobby_id = _lobby("quarter").id

    stats = games.run_rolling_start_tick(now=_LATE)

    assert stats["abandoned"] == 1
    assert stats["entrants_rolled"] == 1
    assert _field_by_id(lobby_id).state == "abandoned"
    with get_session() as s:
        moved = s.execute(
            select(GameEntryRow).where(GameEntryRow.id == entry.id)
        ).scalar_one()
    assert moved.field_id != lobby_id
    assert _field_by_id(moved.field_id).state in ("announced", "entry_open")


def test_the_rolled_entrant_keeps_their_run_and_pays_nothing():
    # §12: "no forfeit, no debit, no record." The entry is re-pointed rather
    # than closed and recreated, so the same run_id and the same game
    # portfolio carry over and there is nothing to migrate.
    entry = _fill("quarter", 1)[0]
    games.run_rolling_start_tick(now=_LATE)

    with get_session() as s:
        moved = s.execute(
            select(GameEntryRow).where(GameEntryRow.id == entry.id)
        ).scalar_one()
        assert moved.run_id == entry.run_id
        assert moved.state == "entered"
        assert moved.career_points_delta in (None, 0)
        from app.services import career_ledger
        assert career_ledger.forfeit_count(s, moved.user_id) == 0
        assert career_ledger.career_points_total(s, moved.user_id) == 0


def test_the_successor_counts_the_entrant_it_inherited():
    # Otherwise the rolled player is invisible to the demand gate and the
    # lobby they were moved into would abandon them again 30 days later.
    entry = _fill("quarter", 1)[0]
    games.run_rolling_start_tick(now=_LATE)
    with get_session() as s:
        moved = s.execute(
            select(GameEntryRow).where(GameEntryRow.id == entry.id)
        ).scalar_one()
    assert _field_by_id(moved.field_id).entrant_count == 1


def test_an_abandoned_field_is_never_re_used_as_the_open_lobby():
    _fill("quarter", 1)
    games.run_rolling_start_tick(now=_LATE)
    with get_session() as s:
        field = games.ensure_field(s, "quarter", now=_LATE)
    assert field.state != "abandoned"


def test_a_contest_of_two_is_started_rather_than_abandoned():
    _fill("quarter", 2)
    stats = games.run_rolling_start_tick(now=_LATE)
    assert stats["started"] == 1
    assert stats["abandoned"] == 0


# ── The weekly/monthly cadences are untouched ────────────────────────────


def test_the_tick_never_touches_a_calendar_cadence():
    # §6.6: "the problem is confined to the long cadences; weekly and
    # monthly are calendar-driven, so thinness means a small field, never a
    # stale one." A weekly lobby has nothing to gate.
    with get_session() as s:
        weekly_before = games.ensure_field(s, "week", now=_NOW)
        before = (weekly_before.id, weekly_before.starts_on, weekly_before.ends_on)
    _fill("week", games.ROLLING_MIN_ENTRANTS)
    games.run_rolling_start_tick(now=_LATE)
    with get_session() as s:
        weekly_after = s.execute(
            select(GameFieldRow).where(GameFieldRow.id == before[0])
        ).scalar_one()
    assert (weekly_after.id, weekly_after.starts_on, weekly_after.ends_on) == before
