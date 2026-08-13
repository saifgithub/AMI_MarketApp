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


# ── The rank-move beat — the one that needs two observations ────────────────
#
# It was deliberately NOT built in CR176's first cut, and the reason is the
# whole point of these tests: `games_board` ranked as of the latest close and
# took no as-of date, so a single observation could say where a player is and
# never that they moved. Firing on "currently outside the top 10" reports a
# drop that may never have happened — the `?? 0` family, where an unmeasured
# value and a real one get collapsed.


def test_a_player_who_was_never_in_the_top_ten_did_not_drop_out_of_it():
    """Unranked at the earlier close means not measured, not "below". Treating
    absence as a position is how a beat invents a fall out of a first
    appearance."""
    assert push.dropped_out_of_top(None, 14, top_n=10) is False


def test_a_player_with_no_current_rank_is_not_told_they_dropped():
    """No measured position now — "you dropped out" would be asserting one
    from its absence."""
    assert push.dropped_out_of_top(4, None, top_n=10) is False


def test_the_boundary_is_the_event_not_the_direction():
    assert push.dropped_out_of_top(10, 11, top_n=10) is True   # just left it
    assert push.dropped_out_of_top(9, 10, top_n=10) is False   # still inside
    assert push.dropped_out_of_top(11, 14, top_n=10) is False  # already out
    assert push.dropped_out_of_top(14, 3, top_n=10) is False   # climbed in


def _nav(user_id, run_id, day: int, nav: float) -> None:
    from app.db.models import PortfolioNavDailyRow

    with get_session() as s:
        s.add(PortfolioNavDailyRow(
            user_id=user_id, run_id=run_id, as_of_date=date(2026, 8, day),
            nav=nav, cash=nav, price_source="mock",
        ))


def _field_of(n: int, *, now: datetime):
    """`n` players entered into one field, each with their own run."""
    players = [_player() for _ in range(n)]
    entries = [_entry_for(p, now=now) for p in players]
    return players, entries


# The rank-move tests below call `_beat_rank_move` directly rather than the
# whole sweep, and that is deliberate. A weekly field entered on the 10th ends
# on the 14th, so any date with two closes behind it is already inside the
# final stretch — and `run_games_push_tick` would then spend the day's single
# slot on the final-stretch beat before this one is reached. That interaction
# is correct and is asserted on its own in
# `test_the_rank_move_beat_yields_the_daily_slot_to_the_final_stretch`; mixing
# it into every case would leave these passing for the wrong reason.


def test_a_field_of_eight_never_fires_the_beat():
    """In a field of eight nobody can leave a top ten — no rank can exceed the
    field's own size. At alpha field sizes that is every field, so the beat is
    not merely quiet here, it is inapplicable.

    Note what this does and does not pin: it holds because of
    `dropped_out_of_top`'s boundary, not because of the size check in
    `_beat_rank_move`. That check is an early-out that saves computing the
    second board; deleting it leaves every assertion here green (verified by
    mutation), and calling it a guard would have been calling an optimisation a
    control."""
    players, entries = _field_of(8, now=_at(3, day=10))
    for i, (p, e) in enumerate(zip(players, entries)):
        _nav(p.id, e.run_id, 11, 10_000)
        _nav(p.id, e.run_id, 12, 10_000 + i * 100)

    assert push._beat_rank_move(_at(12, day=12)) == 0
    assert all(not _pushes(p.id, push.TYPE_RANK_MOVE) for p in players)
    # The reason, stated rather than implied.
    assert all(
        push.dropped_out_of_top(r, r, top_n=push.RANK_MOVE_TOP_N) is False
        for r in range(1, 9)
    )


def test_one_close_is_not_enough_to_claim_a_move():
    """A change needs two observations. One close is not a quiet day for this
    beat — it is a question that cannot be asked yet."""
    players, entries = _field_of(12, now=_at(3, day=10))
    for i, (p, e) in enumerate(zip(players, entries)):
        _nav(p.id, e.run_id, 11, 10_000 + i)

    assert push._beat_rank_move(_at(12, day=11)) == 0


def test_the_player_who_actually_fell_out_is_the_one_told():
    """Twelve entrants. One sits 1st at the first close and last at the
    second; nobody else crosses the boundary."""
    players, entries = _field_of(12, now=_at(3, day=10))
    faller, faller_entry = players[0], entries[0]

    # Everyone starts at the same NAV, so the first close ranks on the second
    # day's move.
    for p, e in zip(players, entries):
        _nav(p.id, e.run_id, 11, 10_000)

    # Close 1 — the faller leads, the rest trail in order.
    _nav(faller.id, faller_entry.run_id, 12, 12_000)
    for i, (p, e) in enumerate(zip(players[1:], entries[1:])):
        _nav(p.id, e.run_id, 12, 11_000 - i * 10)

    # Close 2 — the faller gives it all back and lands last.
    _nav(faller.id, faller_entry.run_id, 13, 8_000)
    for i, (p, e) in enumerate(zip(players[1:], entries[1:])):
        _nav(p.id, e.run_id, 13, 11_500 - i * 10)

    assert push._beat_rank_move(_at(12, day=13)) == 1
    assert len(_pushes(faller.id, push.TYPE_RANK_MOVE)) == 1
    for p in players[1:]:
        assert not _pushes(p.id, push.TYPE_RANK_MOVE)


def test_the_rank_move_beat_fires_at_most_once_per_run():
    players, entries = _field_of(12, now=_at(3, day=10))
    faller, faller_entry = players[0], entries[0]
    for p, e in zip(players, entries):
        _nav(p.id, e.run_id, 11, 10_000)
    _nav(faller.id, faller_entry.run_id, 12, 12_000)
    for i, (p, e) in enumerate(zip(players[1:], entries[1:])):
        _nav(p.id, e.run_id, 12, 11_000 - i * 10)
    _nav(faller.id, faller_entry.run_id, 13, 8_000)
    for i, (p, e) in enumerate(zip(players[1:], entries[1:])):
        _nav(p.id, e.run_id, 13, 11_500 - i * 10)

    assert push._beat_rank_move(_at(12, day=13)) == 1
    assert push._beat_rank_move(_at(13, day=13)) == 0
    assert len(_pushes(faller.id, push.TYPE_RANK_MOVE)) == 1


def test_the_rank_move_beat_yields_the_daily_slot_to_the_final_stretch():
    """The sweep runs beats in descending order of urgency-to-the-player, and
    the rank move is last. A player told they slipped but never told their run
    was ending has been served exactly backwards — so when the single daily
    slot binds, this is the beat that loses it."""
    players, entries = _field_of(12, now=_at(3, day=10))
    faller, faller_entry = players[0], entries[0]
    for p, e in zip(players, entries):
        _nav(p.id, e.run_id, 11, 10_000)
    _nav(faller.id, faller_entry.run_id, 12, 12_000)
    for i, (p, e) in enumerate(zip(players[1:], entries[1:])):
        _nav(p.id, e.run_id, 12, 11_000 - i * 10)
    _nav(faller.id, faller_entry.run_id, 13, 8_000)
    for i, (p, e) in enumerate(zip(players[1:], entries[1:])):
        _nav(p.id, e.run_id, 13, 11_500 - i * 10)

    # The 13th is one day before ends_on, so the final stretch is due too.
    stats = push.run_games_push_tick(now=_at(12, day=13))
    assert stats["final_stretch"] == 12
    assert stats["rank_move"] == 0
    assert not _pushes(faller.id, push.TYPE_RANK_MOVE)

    # It is not lost, only deferred: the next local day, with the
    # once-per-run final stretch already spent, the slot is free.
    assert push.run_games_push_tick(now=_at(12, day=14))["rank_move"] == 1
    assert len(_pushes(faller.id, push.TYPE_RANK_MOVE)) == 1


def test_a_board_row_never_carries_another_players_identifiers():
    """`ranked_entrants` attaches the run and user so the beat can address
    them; `board_for_run` must strip both. Invariant 2 puts the allowlist at
    the serializer rather than trusting every caller."""
    from app.services import games_board

    players, entries = _field_of(3, now=_at(3, day=10))
    for p, e in zip(players, entries):
        _nav(p.id, e.run_id, 11, 10_000)

    board = games_board.board_for_run(players[0].id, entries[0].run_id)
    for row in board["rows"]:
        assert games_board.RUN_KEY not in row
        assert games_board.USER_KEY not in row
    assert any(r["is_you"] for r in board["rows"])


def test_ranking_as_of_an_earlier_close_ignores_everything_after_it():
    """The as-of read truncates the stored series; it never interpolates. A
    date with no row yields the series up to the last real one, because a NAV
    that was never recorded and a NAV that happened to be flat are different
    facts."""
    from app.services import games_board

    players, entries = _field_of(2, now=_at(3, day=10))
    a, b = players
    ea, eb = entries
    _nav(a.id, ea.run_id, 11, 10_000)
    _nav(b.id, eb.run_id, 11, 10_000)
    _nav(a.id, ea.run_id, 12, 11_000)   # A ahead at close 1
    _nav(b.id, eb.run_id, 12, 10_500)
    _nav(a.id, ea.run_id, 13, 10_100)   # B ahead at close 2
    _nav(b.id, eb.run_id, 13, 12_000)

    with get_session() as s:
        field_id = s.execute(
            select(GameEntryRow.field_id).where(
                GameEntryRow.run_id == ea.run_id)
        ).scalars().first()

    earlier = games_board.ranked_entrants(field_id, as_of=date(2026, 8, 12))
    later = games_board.ranked_entrants(field_id, as_of=date(2026, 8, 13))
    rank_of = lambda rows, run: next(  # noqa: E731
        r["rank"] for r in rows if r[games_board.RUN_KEY] == run)

    assert rank_of(earlier, ea.run_id) == 1
    assert rank_of(later, ea.run_id) == 2
    assert games_board.close_dates_for_field(field_id) == [
        date(2026, 8, 13), date(2026, 8, 12),
    ]
