"""CR207 — the settled push names where the player finished.

Two layers, tested the way CR176 tests its own: the **resolver** is pure and
argument-only, so every branch is exercised without a database; the **beat**
goes against the sqlite fixture, because what matters there is which rows it
selects, which numbers reach the copy, and that changing the copy did not
change the dedupe key.

The guards worth naming:

  * `test_no_input_can_make_a_thin_field_assert_a_position` and its siblings
    are the DEF059 fence — the three non-asserting kinds are proven
    non-asserting over a swept input space, not on one hand-picked example.
    A message that says "you came 2nd of 3" for a run scored against the
    index describes a contest the scoring did not run.
  * `test_the_new_copy_does_not_re_notify_an_already_notified_player` is the
    one that would have caught the obvious way to ship this wrong. The body
    changed; `source_ref` did not. Had it been re-keyed on anything the copy
    depends on, every player already told would be told again.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.db import get_session
from app.db.models import GameEntryRow, GameFieldRow, NotificationRow, User
from app.services import games_placement as placement
from app.services import games_push as push
from app.services import games_service as games

_UTC = timezone.utc


def _at(h: int, *, day: int = 13) -> datetime:
    return datetime(2026, 8, day, h, 0, tzinfo=_UTC)


def _r(**kw):
    base = dict(state="finished", scoring_basis="placement", final_rank=3,
                scored_entrant_count=8, entrant_count=8)
    base.update(kw)
    return placement.resolve(**base)


# ── The resolver — pure ─────────────────────────────────────────────────────


def test_a_clean_position_is_named_with_the_field_it_was_taken_over():
    assert placement.push_copy(_r(), cadence="week")[1] == "You finished 3rd of 8."


def test_winning_reads_differently_from_placing():
    """Rank 1 and rank 3 are not the same event and must not share a sentence
    — that sameness is what the old "results are ready" copy did to every
    outcome at once."""
    champ_title, champ_body = placement.push_copy(_r(final_rank=1), cadence="week")
    mid_title, mid_body = placement.push_copy(_r(final_rank=3), cadence="week")
    assert champ_title != mid_title
    assert champ_body != mid_body
    assert _r(final_rank=1).kind == "champion"


def test_a_shared_rank_is_told_as_a_tie_not_as_a_clean_position():
    """The live 2026-08-14 field has two entrants at rank 3 of 4. Standard
    competition ranking (1, 1, 3) is what games_scoring_pass writes, so this
    is a reachable state, and "you finished 3rd" hides from the player that
    someone else finished there too."""
    tied = _r(final_rank=3, scored_entrant_count=4, entrant_count=4, tie_count=2)
    assert tied.kind == "tied"
    assert placement.push_copy(tied, cadence="week")[1] == "You finished joint 3rd of 4."


def test_a_shared_first_is_a_co_champion_not_a_champion():
    co = _r(final_rank=1, tie_count=2)
    assert co.kind == "co_champion"
    assert "joint 1st" in placement.push_copy(co, cadence="week")[1]


def test_the_field_size_is_the_scored_count_never_the_raw_entrant_count():
    """"3rd of 9" in a field where two runs voided is a sentence about a
    contest that did not happen. The scored count is the n the rank was
    actually taken over."""
    p = _r(scored_entrant_count=7, entrant_count=9)
    assert p.field_size == 7
    assert "of 7" in placement.push_copy(p, cadence="week")[1]


def test_with_no_usable_count_the_size_is_dropped_rather_than_rendered_as_zero():
    """"1st of 0" is the one rendering worse than showing no denominator."""
    p = _r(final_rank=2, scored_entrant_count=0, entrant_count=0)
    assert p.field_size is None
    assert placement.push_copy(p, cadence="week")[1] == "You finished 2nd."


def test_ordinals_survive_the_teens():
    for rank, want in ((11, "11th"), (12, "12th"), (13, "13th"), (21, "21st"),
                       (22, "22nd"), (23, "23rd"), (101, "101st"), (111, "111th")):
        assert placement._ordinal(rank) == want


# ── The DEF059 fence: what must NEVER assert a position ─────────────────────


def test_a_void_run_is_not_last_place():
    p = _r(state="void", final_rank=None)
    assert p.kind == "void"
    assert p.asserts_position is False
    title, body = placement.push_copy(p, cadence="week")
    assert "finished" not in body


def test_an_unmeasured_rank_is_not_a_measured_one():
    """`final_rank IS NULL` is the absence of a measurement, not rank 0 —
    the `?? 0` family that DEF059 exists to keep out of user-facing copy."""
    p = _r(final_rank=None)
    assert p.kind == "unmeasured"
    assert p.asserts_position is False


def test_a_thin_field_never_announces_a_placement_even_for_the_winner():
    """A rank exists, but the field was too thin for placement to be the
    scoring basis. Winning a field too small to be scored as a field is not
    a win to announce — so thin_field outranks champion deliberately."""
    p = _r(scoring_basis="benchmark", final_rank=1, scored_entrant_count=2,
           entrant_count=2)
    assert p.kind == "thin_field"
    assert p.asserts_position is False
    assert "1st" not in placement.push_copy(p, cadence="week")[1]


def test_no_input_can_make_a_non_asserting_kind_produce_a_position():
    """Swept rather than sampled: for every combination that must not assert
    a position, no ordinal may appear in the body."""
    ordinals = {placement._ordinal(n) for n in range(1, 40)}
    checked = 0
    for state, basis, rank in (
        ("void", "placement", None), ("void", "placement", 1),
        ("void", "benchmark", 3), ("finished", "placement", None),
        ("finished", "benchmark", 1), ("finished", "benchmark", 5),
    ):
        for ties in (1, 2, 3):
            for scored, entrants in ((0, 0), (3, 9), (8, 8)):
                p = placement.resolve(
                    state=state, scoring_basis=basis, final_rank=rank,
                    scored_entrant_count=scored, entrant_count=entrants,
                    tie_count=ties,
                )
                assert p.asserts_position is False, p
                body = placement.push_copy(p, cadence="week")[1]
                assert not any(o in body for o in ordinals), (p, body)
                checked += 1
    assert checked == 54


# ── The beat — against the database ─────────────────────────────────────────


def _player(tz: str = "UTC", *, desk: bool = False) -> User:
    user_id = uuid4()
    with get_session() as s:
        s.add(User(id=user_id, timezone=tz, is_desk=desk, is_anonymous=True))
    with get_session() as s:
        return s.execute(select(User).where(User.id == user_id)).scalar_one()


def _settled(user_id) -> list[NotificationRow]:
    with get_session() as s:
        return list(s.execute(
            select(NotificationRow).where(
                NotificationRow.user_id == user_id,
                NotificationRow.type == push.TYPE_SETTLED,
            )
        ).scalars().all())


def _close_run(user, *, rank, basis="placement", scored=4, state="finished"):
    entry = games.enter_field(user.id, now=_at(3, day=10))
    with get_session() as s:
        e = s.execute(
            select(GameEntryRow).where(GameEntryRow.run_id == entry.run_id)
        ).scalars().one()
        e.state = state
        e.final_rank = rank
        e.scored_entrant_count = scored
        field = s.execute(
            select(GameFieldRow).where(GameFieldRow.id == e.field_id)
        ).scalars().one()
        field.ends_on = date(2026, 8, 13)
        field.scoring_basis = basis
        field.entrant_count = scored
    return entry


def test_the_settled_push_now_carries_the_placement():
    user = _player()
    _close_run(user, rank=3, scored=8)
    push.run_games_push_tick(now=_at(12))
    rows = _settled(user.id)
    assert len(rows) == 1
    assert rows[0].body == "You finished 3rd of 8."
    assert "results are ready" not in rows[0].body


def test_the_winner_gets_the_winning_message():
    user = _player()
    _close_run(user, rank=1, scored=8)
    push.run_games_push_tick(now=_at(12))
    assert _settled(user.id)[0].title == "You won your field"


def test_a_voided_run_is_pushed_and_asserts_nothing():
    """A voided run is still a closed run whose player is owed the ceremony.
    Before CR207 the beat selected only `finished`, so the one player whose
    run could not be scored was the one player told nothing at all."""
    user = _player()
    _close_run(user, rank=None, state="void")
    push.run_games_push_tick(now=_at(12))
    rows = _settled(user.id)
    assert len(rows) == 1
    assert "finished" not in rows[0].body


def test_the_new_copy_does_not_re_notify_an_already_notified_player():
    """`source_ref` is the dedupe key and stays the run id. Re-keying it on
    anything the copy depends on would re-notify every player already told —
    the obvious way to ship this change wrong."""
    user = _player()
    entry = _close_run(user, rank=2, scored=5)
    push.run_games_push_tick(now=_at(12))
    push.run_games_push_tick(now=_at(13))
    rows = _settled(user.id)
    assert len(rows) == 1
    assert rows[0].source_ref == str(entry.run_id)


def test_a_desk_is_still_never_pushed():
    user = _player(desk=True)
    _close_run(user, rank=1, scored=8)
    push.run_games_push_tick(now=_at(12))
    assert _settled(user.id) == []


def test_two_players_sharing_a_rank_are_both_told_it_was_a_tie():
    """The resolver's tie branch is only as good as the count feeding it, and
    that count is a GROUP BY in the beat rather than a column on the row.
    Two entries at the same rank in the same field must both read "joint"."""
    a, b = _player(), _player()
    _close_run(a, rank=2, scored=4)
    _close_run(b, rank=2, scored=4)
    # Put both entries in ONE field, which is what makes them tied at all.
    with get_session() as s:
        entries = s.execute(
            select(GameEntryRow).where(
                GameEntryRow.user_id.in_([a.id, b.id])
            )
        ).scalars().all()
        field_id = entries[0].field_id
        for e in entries:
            e.field_id = field_id

    push.run_games_push_tick(now=_at(12))

    for user in (a, b):
        rows = _settled(user.id)
        assert len(rows) == 1
        assert rows[0].body == "You finished joint 2nd of 4.", rows[0].body
