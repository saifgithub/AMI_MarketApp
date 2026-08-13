"""CR176 — push for CR109's period arc (design §10.1).

Two layers get tested differently on purpose. The **policy** layer is pure and
argument-only, so its every branch is exercised without a database — quiet
hours, the caps, and the one place the implementation reads §10.1 rather than
quoting it (exempt beats bypass the caps but are deferred by quiet hours, not
dropped). The **beats** are exercised against the sqlite fixture, because what
matters about them is which rows they select and that they cannot fire twice.

The guard worth naming: `test_a_settled_run_from_last_month_is_not_pushed`.
`source_ref` makes each close send at most once *ever*, but says nothing about
*when* — without the lookback window the first tick after this ships would
find every historical close and push all of them at once, which is precisely
the channel-burning the reminder rule exists to prevent, delivered by the
feature meant to protect it.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from app.db import get_session
from app.db.models import GameEntryRow, GameFieldRow, NotificationRow, User
from app.services import games_push as push
from app.services import games_service as games

_UTC = timezone.utc


def _at(h: int, *, day: int = 13) -> datetime:
    return datetime(2026, 8, day, h, 0, tzinfo=_UTC)


# ── The policy layer — pure, no database ────────────────────────────────────


def test_quiet_hours_wrap_midnight_at_both_boundaries():
    assert push.in_quiet_hours(_at(21)) is True      # first quiet hour
    assert push.in_quiet_hours(_at(3)) is True       # deep in the night
    assert push.in_quiet_hours(_at(7)) is True       # last quiet hour
    assert push.in_quiet_hours(_at(8)) is False      # first awake hour
    assert push.in_quiet_hours(_at(20)) is False     # last awake hour


def test_a_capped_beat_stops_at_one_a_day():
    assert push.may_send(
        push.TYPE_FINAL_STRETCH, _at(12), sent_today=0, sent_this_week=0,
    ) is True
    assert push.may_send(
        push.TYPE_FINAL_STRETCH, _at(12), sent_today=1, sent_this_week=1,
    ) is False


def test_a_capped_beat_stops_at_four_a_week_even_on_a_fresh_day():
    assert push.may_send(
        push.TYPE_FINAL_STRETCH, _at(12), sent_today=0, sent_this_week=4,
    ) is False


def test_the_close_is_exempt_from_the_caps():
    """§10.1: the Close and a received challenge are exempt from suppression.
    It carries the entire payoff of the period arc — a cap must never be the
    reason it does not arrive."""
    assert push.may_send(
        push.TYPE_SETTLED, _at(12), sent_today=9, sent_this_week=9,
    ) is True
    assert push.may_send(
        push.TYPE_DUEL_CHALLENGED, _at(12), sent_today=9, sent_this_week=9,
    ) is True


def test_even_an_exempt_beat_waits_out_quiet_hours():
    """The one place this reads §10.1 rather than quoting it. Read literally,
    "exempt from suppression" fires a Close at 03:00 local — US settlement
    lands in the small hours across Asia. Deferring is not suppression: the
    sweep is idempotent on a stable source_ref, so it sends on the first tick
    after quiet hours end. It arrives late instead of never."""
    assert push.may_send(
        push.TYPE_SETTLED, _at(3), sent_today=0, sent_this_week=0,
    ) is False


def test_the_wind_up_has_no_beat_at_all():
    """§10.1: "a push telling someone they are losing is cruel." Asserted
    structurally so re-enabling it would mean ADDING a beat, not flipping a
    flag — the CR040 posture that a prompt-level "never do this" is not a
    control."""
    every_type = {
        v for k, v in vars(push).items()
        if k.startswith("TYPE_") and isinstance(v, str)
    }
    assert not any("wind" in t.lower() for t in every_type)


def test_an_unknown_timezone_degrades_to_utc_loudly_not_to_no_quiet_hours():
    """A bad tz string must not take the sweep down, and must not silently
    turn quiet hours OFF for that user — UTC still applies them."""
    assert push._local_now(_at(3), "Not/AZone").hour == 3
    assert push._local_now(_at(3), "Asia/Riyadh").hour == 6


# ── The beats — against the database ────────────────────────────────────────


def _player(tz: str = "UTC", *, desk: bool = False) -> User:
    user_id = uuid4()
    with get_session() as s:
        s.add(User(id=user_id, timezone=tz, is_desk=desk, is_anonymous=True))
    with get_session() as s:
        return s.execute(select(User).where(User.id == user_id)).scalar_one()


def _pushes(user_id, beat_type: str) -> list[NotificationRow]:
    with get_session() as s:
        return list(s.execute(
            select(NotificationRow).where(
                NotificationRow.user_id == user_id,
                NotificationRow.type == beat_type,
            )
        ).scalars().all())


def _entry_for(user: User, *, now: datetime):
    return games.enter_field(user.id, now=now)


def test_the_final_stretch_beat_fires_once_and_only_once():
    """Idempotency is the DB constraint's job, not a check-then-write: two
    overlapping ticks must still produce one push."""
    user = _player()
    entry = _entry_for(user, now=_at(3, day=10))
    with get_session() as s:
        field = s.execute(
            select(GameFieldRow).where(GameFieldRow.starts_on == date(2026, 8, 10))
        ).scalars().first()
        ends_on = field.ends_on

    when = datetime.combine(ends_on - timedelta(days=1), datetime.min.time(),
                            tzinfo=_UTC).replace(hour=12)
    first = push.run_games_push_tick(now=when)
    second = push.run_games_push_tick(now=when)

    assert first["final_stretch"] == 1
    assert second["final_stretch"] == 0
    assert len(_pushes(user.id, push.TYPE_FINAL_STRETCH)) == 1
    assert entry.run_id is not None


def test_both_live_states_get_the_final_stretch_especially_the_untraded_one():
    """`entered` becomes `active` only on the first trade
    (`games_service.py:951`), so a player who entered and never traded stays
    `entered` for the whole run. Filtering on `active` alone — which the first
    cut of this module did — sent the beat to everyone EXCEPT the player with
    a decision still open and the period running out."""
    from app.schemas.trade import Side

    untraded = _player()
    traded = _player()
    e1 = _entry_for(untraded, now=_at(3, day=10))
    e2 = _entry_for(traded, now=_at(3, day=10))
    games.submit_trade(
        traded.id, e2.run_id, ticker="AAPL", side=Side.BUY, quantity=1,
        now=_at(15, day=10),
    )
    with get_session() as s:
        states = {
            r.user_id: r.state
            for r in s.execute(select(GameEntryRow)).scalars().all()
        }
        ends_on = s.execute(
            select(GameFieldRow.ends_on).where(
                GameFieldRow.starts_on == date(2026, 8, 10))
        ).scalars().first()
    assert states[untraded.id] == "entered"
    assert states[traded.id] == "active"

    when = datetime.combine(ends_on - timedelta(days=1), datetime.min.time(),
                            tzinfo=_UTC).replace(hour=12)
    push.run_games_push_tick(now=when)

    assert len(_pushes(untraded.id, push.TYPE_FINAL_STRETCH)) == 1
    assert len(_pushes(traded.id, push.TYPE_FINAL_STRETCH)) == 1
    assert e1.run_id != e2.run_id


def test_a_run_still_mid_period_gets_no_final_stretch_push():
    """The beat is the anticipation engine; firing it early spends the day's
    single slot on a message with nothing to anticipate."""
    user = _player()
    _entry_for(user, now=_at(3, day=10))

    push.run_games_push_tick(now=_at(12, day=10))

    assert _pushes(user.id, push.TYPE_FINAL_STRETCH) == []


def test_quiet_hours_actually_suppress_a_real_beat():
    user = _player(tz="Asia/Riyadh")   # UTC+3 → 02:00 UTC is 05:00 local
    with get_session() as s:
        field = s.execute(select(GameFieldRow)).scalars().first()
    _entry_for(user, now=_at(3, day=10))
    with get_session() as s:
        field = s.execute(
            select(GameFieldRow).where(GameFieldRow.starts_on == date(2026, 8, 10))
        ).scalars().first()
        ends_on = field.ends_on

    at_night = datetime.combine(ends_on - timedelta(days=1),
                                datetime.min.time(), tzinfo=_UTC).replace(hour=2)
    push.run_games_push_tick(now=at_night)

    assert _pushes(user.id, push.TYPE_FINAL_STRETCH) == []


def test_a_settled_run_from_last_month_is_not_pushed():
    """The blast guard. `source_ref` bounds it to once ever, not to once
    RECENTLY — without the lookback the first tick after deploy pushes every
    historical close at once."""
    user = _player()
    entry = _entry_for(user, now=_at(3, day=10))
    with get_session() as s:
        e = s.execute(
            select(GameEntryRow).where(GameEntryRow.run_id == entry.run_id)
        ).scalars().one()
        e.state = "finished"
        field = s.execute(
            select(GameFieldRow).where(GameFieldRow.id == e.field_id)
        ).scalars().one()
        field.ends_on = date(2026, 6, 30)

    push.run_games_push_tick(now=_at(12))

    assert _pushes(user.id, push.TYPE_SETTLED) == []


def test_a_run_that_just_settled_is_pushed_and_ignores_the_daily_cap():
    user = _player()
    entry = _entry_for(user, now=_at(3, day=10))
    with get_session() as s:
        e = s.execute(
            select(GameEntryRow).where(GameEntryRow.run_id == entry.run_id)
        ).scalars().one()
        e.state = "finished"
        field_id = e.field_id
        field = s.execute(
            select(GameFieldRow).where(GameFieldRow.id == field_id)
        ).scalars().one()
        field.ends_on = date(2026, 8, 13)
    # Spend the day's whole allowance on something else first.
    with get_session() as s:
        s.add(NotificationRow(
            id=uuid4(), user_id=user.id, type=push.TYPE_FINAL_STRETCH,
            title="x", body="x", deep_link={}, source_ref="spent",
            created_at=_at(9),
        ))

    stats = push.run_games_push_tick(now=_at(12))

    assert stats["settled"] == 1
    assert len(_pushes(user.id, push.TYPE_SETTLED)) == 1


def test_a_desk_is_never_pushed():
    """Desks are filled by `run_desk_fill_tick`; there is nobody behind them."""
    desk = _player(desk=True)
    _entry_for(desk, now=_at(3, day=10))
    with get_session() as s:
        field = s.execute(
            select(GameFieldRow).where(GameFieldRow.starts_on == date(2026, 8, 10))
        ).scalars().first()
        ends_on = field.ends_on

    when = datetime.combine(ends_on - timedelta(days=1), datetime.min.time(),
                            tzinfo=_UTC).replace(hour=12)
    push.run_games_push_tick(now=when)

    assert _pushes(desk.id, push.TYPE_FINAL_STRETCH) == []


def test_entries_closing_skips_a_player_already_in_that_field():
    """The beat is "you are NOT entered". Sending it to someone who is
    entered is the "only invites watching" side of the reminder rule."""
    user = _player()
    entry = _entry_for(user, now=_at(3, day=10))
    with get_session() as s:
        field = s.execute(
            select(GameEntryRow.field_id).where(
                GameEntryRow.run_id == entry.run_id)
        ).scalar_one()
        locks_at = s.execute(
            select(GameFieldRow.locks_at).where(GameFieldRow.id == field)
        ).scalar_one()

    push.run_games_push_tick(now=locks_at - timedelta(hours=1))

    assert _pushes(user.id, push.TYPE_ENTRIES_CLOSING) == []
