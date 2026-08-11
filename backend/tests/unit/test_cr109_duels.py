"""CR109 slice 3b — duels. Design §11.1.

Saiful: *"I really like the Dual….. how can we bring it back?"*

The invariants, in the order they matter:

1. **A duel never routes through the placement formula.** At `n = 2`,
   placement `p` is exactly 1.0 or 0.0, so it would pay the winner the
   maximum in the game and debit the loser the maximum, for beating one
   person. This is the assertion that a future refactor folding duel scoring
   into `_apply_score` would fail.
2. **The delta is symmetric** at the ledger's `delta_uncapped` — what the
   winner is credited, the loser is debited. That is what makes a duel
   running alongside an open-field run EV-neutral, and what lets §4.1's
   one-per-cadence cap be about attention rather than integrity. It is NOT
   symmetric in collected points at the floor: Amendment D clamps debits so a
   career total cannot go below zero, so a loser at zero pays nothing. That
   consequence has its own test rather than being left to be rediscovered.
3. **A first run is always paired against the Index Desk**, and the desk can
   hold that role for every beginner in the field at once.
4. **Void beats everything.** A duel with a voided side pays nobody.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import GameDuelRow, GameEntryRow, GameFieldRow, User
from app.services import career_ledger, games_duels
from app.services.games_scoring import DUEL_POINTS, CADENCE_GAIN_WEIGHT, duel_points

_NOW = datetime(2026, 8, 11, 13, 0, tzinfo=timezone.utc)


def _field(cadence: str = "week", *, starts_on: date | None = None) -> UUID:
    starts_on = starts_on or date(2026, 8, 10)
    field_id = uuid4()
    with get_session() as s:
        s.add(GameFieldRow(
            id=field_id,
            cadence=cadence,
            starts_on=starts_on,
            ends_on=starts_on + timedelta(days=4),
            entry_opens_at=_NOW - timedelta(days=3),
            locks_at=_NOW - timedelta(hours=1),
            state="locked",
        ))
    return field_id


def _user(*, is_desk: bool = False, desk_key: str | None = None, handle: str = "") -> UUID:
    user_id = uuid4()
    with get_session() as s:
        s.add(User(
            id=user_id,
            handle=handle or f"P{str(user_id)[:6]}",
            is_desk=is_desk,
            desk_key=desk_key,
        ))
    return user_id


def _enter(field_id: UUID, user_id: UUID, *, entered_at: datetime | None = None) -> UUID:
    run_id = uuid4()
    with get_session() as s:
        s.add(GameEntryRow(
            id=uuid4(),
            field_id=field_id,
            user_id=user_id,
            run_id=run_id,
            state="entered",
            entered_at=entered_at or _NOW,
            fees_paid=0,
            trade_count=0,
        ))
    return run_id


def _finish(run_id: UUID, twr_pct: float, *, state: str = "finished") -> None:
    with get_session() as s:
        entry = s.execute(
            select(GameEntryRow).where(GameEntryRow.run_id == run_id)
        ).scalars().one()
        entry.state = state
        entry.final_twr_pct = twr_pct
        entry.scored_at = _NOW


def _duels(field_id: UUID) -> list[GameDuelRow]:
    with get_session() as s:
        return list(s.execute(
            select(GameDuelRow).where(GameDuelRow.field_id == field_id)
            .order_by(GameDuelRow.created_at.asc())
        ).scalars().all())


# ── The delta ───────────────────────────────────────────────────────────


def test_duel_points_are_modest_monotonic_and_far_below_placement():
    """§21 left this number open; these are the first values, and the SHAPE
    is what the tests pin. A weekly duel pays 10 against placement's ~100
    ceiling — a format that paid more than the open board would teach players
    to avoid the board this game is about."""
    assert DUEL_POINTS["week"] == 10
    values = [DUEL_POINTS[c] for c in ("week", "month", "quarter", "half", "year")]
    assert values == sorted(values), "must not decrease with committed time"
    assert max(values) <= 100, "a duel must never approach a placement payout"


def test_duel_points_grow_far_more_slowly_than_the_gain_row():
    """`CADENCE_GAIN_WEIGHT` runs 1 -> 52. Applying that scale here would pay
    520 for one annual duel — five times the maximum in the game. A duel is
    one comparison against one opponent no matter how long it ran."""
    duel_ratio = DUEL_POINTS["year"] / DUEL_POINTS["week"]
    gain_ratio = CADENCE_GAIN_WEIGHT["year"] / CADENCE_GAIN_WEIGHT["week"]
    assert duel_ratio < gain_ratio / 5


def test_an_unknown_cadence_falls_to_the_weekly_value_not_to_zero():
    """A duel that silently scored zero because of an unrecognised string
    would be a no-op on a result the player watched happen."""
    assert duel_points("fortnight") == DUEL_POINTS["week"]


# ── Pairing ─────────────────────────────────────────────────────────────


def test_a_first_ever_run_is_paired_against_the_index_desk():
    field_id = _field()
    desk = _user(is_desk=True, desk_key="index", handle="INDEX_DESK")
    _enter(field_id, desk)
    newbie = _user()
    run = _enter(field_id, newbie)

    stats = games_duels.pair_field(field_id, now=_NOW)

    assert stats["first_run"] == 1
    (duel,) = _duels(field_id)
    assert duel.kind == "first_run"
    assert duel.user_a_id == newbie and duel.run_a_id == run
    assert duel.user_b_id == desk


def test_one_index_desk_is_the_opponent_of_every_beginner_at_once():
    """The guarantee is "a guaranteed opponent at n=1 real players". A unique
    constraint on side B would silently cap the field at one beginner — which
    is why that index is scoped to `auto` duels."""
    field_id = _field()
    desk = _user(is_desk=True, desk_key="index")
    _enter(field_id, desk)
    for _ in range(3):
        _enter(field_id, _user())

    stats = games_duels.pair_field(field_id, now=_NOW)

    assert stats["first_run"] == 3
    assert stats["auto"] == 0
    assert all(d.user_b_id == desk for d in _duels(field_id))


def test_a_returning_player_is_matched_against_another_human_not_the_desk():
    field_id = _field()
    desk = _user(is_desk=True, desk_key="index")
    _enter(field_id, desk)

    a, b = _user(), _user()
    # Both have a prior FINISHED run, so neither is on their first.
    old_field = _field(starts_on=date(2026, 8, 3))
    for u in (a, b):
        _finish(_enter(old_field, u), 1.0)

    _enter(field_id, a, entered_at=_NOW - timedelta(hours=5))
    _enter(field_id, b, entered_at=_NOW - timedelta(hours=4))

    stats = games_duels.pair_field(field_id, now=_NOW)

    assert stats["first_run"] == 0
    assert stats["auto"] == 1
    (duel,) = _duels(field_id)
    assert duel.kind == "auto"
    assert {duel.user_a_id, duel.user_b_id} == {a, b}


def test_a_forfeited_prior_run_still_counts_as_never_having_finished():
    """"First run" is defined by FINISHED runs. A player who entered and
    forfeited has still never had a Close, and the first-Close narrative is
    the whole point — spending their guaranteed opponent on a run nobody saw
    the end of would waste it."""
    field_id = _field()
    desk = _user(is_desk=True, desk_key="index")
    _enter(field_id, desk)

    u = _user()
    old_field = _field(starts_on=date(2026, 8, 3))
    _finish(_enter(old_field, u), 0.0, state="forfeited")
    _enter(field_id, u)

    stats = games_duels.pair_field(field_id, now=_NOW)
    assert stats["first_run"] == 1


def test_an_odd_human_out_is_simply_unpaired_not_an_error():
    field_id = _field()
    old_field = _field(starts_on=date(2026, 8, 3))
    for _ in range(3):
        u = _user()
        _finish(_enter(old_field, u), 1.0)
        _enter(field_id, u)

    stats = games_duels.pair_field(field_id, now=_NOW)

    assert stats["auto"] == 1
    assert stats["unpaired"] == 1


def test_pairing_is_idempotent():
    """The lock-window sweep runs every few minutes. A restart mid-sweep must
    resume, never double-pair."""
    field_id = _field()
    desk = _user(is_desk=True, desk_key="index")
    _enter(field_id, desk)
    _enter(field_id, _user())

    first = games_duels.pair_field(field_id, now=_NOW)
    second = games_duels.pair_field(field_id, now=_NOW)

    assert first["first_run"] == 1
    assert second["first_run"] == 0
    assert len(_duels(field_id)) == 1


def test_a_field_with_no_index_desk_pairs_humans_and_leaves_beginners_unpaired():
    """The desk abstains when it cannot build a real basket (§11.2's
    integrity fence). A beginner then has no first-run duel — which is
    honest. It must not fall through to a human opponent, because the
    bounded-difficulty guarantee is the point of the first-run pairing."""
    field_id = _field()
    newbie = _user()
    _enter(field_id, newbie)

    stats = games_duels.pair_field(field_id, now=_NOW)

    assert stats["first_run"] == 0
    assert stats["auto"] == 0
    assert _duels(field_id) == []


# ── Settlement ──────────────────────────────────────────────────────────


def _settle(field_id: UUID) -> None:
    with get_session() as s:
        games_duels.settle_field_duels(s, field_id, now=_NOW)


def test_the_higher_twr_wins_and_the_delta_is_symmetric():
    field_id = _field()
    a, b = _user(), _user()
    old_field = _field(starts_on=date(2026, 8, 3))
    for u in (a, b):
        _finish(_enter(old_field, u), 1.0)
    run_a = _enter(field_id, a, entered_at=_NOW - timedelta(hours=5))
    run_b = _enter(field_id, b, entered_at=_NOW - timedelta(hours=4))
    games_duels.pair_field(field_id, now=_NOW)

    _finish(run_a, 3.5)
    _finish(run_b, 1.2)
    _settle(field_id)

    (duel,) = _duels(field_id)
    assert duel.state == "settled"
    assert duel.winner_user_id == a
    assert duel.points_delta == DUEL_POINTS["week"]

    # THE invariant, asserted where it actually lives: `delta_uncapped` is
    # the symmetric number. What the winner is credited, the loser is
    # debited, exactly.
    with get_session() as s:
        posted = {
            r.user_id: r for r in s.execute(
                select(career_ledger.CareerEventRow).where(
                    career_ledger.CareerEventRow.reason == "duel_result"
                )
            ).scalars().all()
        }
        a_pts = career_ledger.career_points_total(s, a)
    assert posted[a].delta_uncapped == DUEL_POINTS["week"]
    assert posted[b].delta_uncapped == -DUEL_POINTS["week"]
    assert posted[a].delta_uncapped + posted[b].delta_uncapped == 0
    assert a_pts == DUEL_POINTS["week"]


def test_a_loser_at_zero_points_pays_nothing_and_that_is_amendment_d_not_a_bug():
    """Amendment D clamps DEBITS at write so a career total can never go
    below zero — it exists to prevent invisible debt, where a player earns
    points and the screen does not move until they have dug out of a hole.

    A duel loser already at zero therefore pays nothing while the winner
    still collects, so the pair is not zero-sum AT THE FLOOR. Asserted here
    so it is a recorded consequence rather than something found later and
    mistaken for a symmetry bug. The farm this would otherwise open is
    already closed structurally by auto-matching: you cannot choose to duel
    your own alt."""
    field_id = _field()
    a, b = _user(), _user()
    old_field = _field(starts_on=date(2026, 8, 3))
    for u in (a, b):
        _finish(_enter(old_field, u), 1.0)
    run_a = _enter(field_id, a, entered_at=_NOW - timedelta(hours=5))
    run_b = _enter(field_id, b, entered_at=_NOW - timedelta(hours=4))
    games_duels.pair_field(field_id, now=_NOW)
    _finish(run_a, 3.0)
    _finish(run_b, 1.0)
    _settle(field_id)

    with get_session() as s:
        loser_row = s.execute(
            select(career_ledger.CareerEventRow).where(
                career_ledger.CareerEventRow.user_id == b,
                career_ledger.CareerEventRow.reason == "duel_result",
            )
        ).scalars().one()
        # The RAW cost is on the row; the COLLECTED amount is clamped to the
        # balance available. Both numbers survive, which is the point of
        # keeping `delta_uncapped`.
        assert loser_row.delta_uncapped == -DUEL_POINTS["week"]
        assert loser_row.delta == 0
        assert career_ledger.career_points_total(s, b) == 0


def test_a_tie_is_a_real_outcome_that_pays_nobody():
    field_id = _field()
    a, b = _user(), _user()
    old_field = _field(starts_on=date(2026, 8, 3))
    for u in (a, b):
        _finish(_enter(old_field, u), 1.0)
    run_a = _enter(field_id, a, entered_at=_NOW - timedelta(hours=5))
    run_b = _enter(field_id, b, entered_at=_NOW - timedelta(hours=4))
    games_duels.pair_field(field_id, now=_NOW)

    _finish(run_a, 2.0)
    _finish(run_b, 2.0)
    _settle(field_id)

    (duel,) = _duels(field_id)
    # `settled`, not `void` — a player who drew deserves to be told they drew.
    assert duel.state == "settled"
    assert duel.winner_user_id is None
    assert duel.points_delta == 0


def test_a_voided_side_voids_the_whole_duel_and_pays_nobody():
    """A run whose NAV series was built on fabricated marks is voided by the
    scoring pass. Comparing a real return against a mock-walk one is not a
    result, and paying it out would be the DEF059 shape on a number the
    player will remember."""
    field_id = _field()
    a, b = _user(), _user()
    old_field = _field(starts_on=date(2026, 8, 3))
    for u in (a, b):
        _finish(_enter(old_field, u), 1.0)
    run_a = _enter(field_id, a, entered_at=_NOW - timedelta(hours=5))
    run_b = _enter(field_id, b, entered_at=_NOW - timedelta(hours=4))
    games_duels.pair_field(field_id, now=_NOW)

    _finish(run_a, 5.0)
    _finish(run_b, 1.0, state="void")
    _settle(field_id)

    (duel,) = _duels(field_id)
    assert duel.state == "void"
    assert duel.winner_user_id is None
    assert duel.points_delta == 0
    with get_session() as s:
        assert career_ledger.career_points_total(s, a) == 0
        assert career_ledger.career_points_total(s, b) == 0


def test_a_forfeited_side_voids_the_duel_rather_than_losing_it():
    """Forfeiting is already debited by §6.7's own rule. Taking a duel loss
    on top would charge the same act twice."""
    field_id = _field()
    a, b = _user(), _user()
    old_field = _field(starts_on=date(2026, 8, 3))
    for u in (a, b):
        _finish(_enter(old_field, u), 1.0)
    run_a = _enter(field_id, a, entered_at=_NOW - timedelta(hours=5))
    run_b = _enter(field_id, b, entered_at=_NOW - timedelta(hours=4))
    games_duels.pair_field(field_id, now=_NOW)

    _finish(run_a, 5.0)
    _finish(run_b, 0.0, state="forfeited")
    _settle(field_id)

    (duel,) = _duels(field_id)
    assert duel.state == "void"
    with get_session() as s:
        assert career_ledger.career_points_total(s, a) == 0


def test_settling_twice_does_not_double_post():
    field_id = _field()
    a, b = _user(), _user()
    old_field = _field(starts_on=date(2026, 8, 3))
    for u in (a, b):
        _finish(_enter(old_field, u), 1.0)
    run_a = _enter(field_id, a, entered_at=_NOW - timedelta(hours=5))
    run_b = _enter(field_id, b, entered_at=_NOW - timedelta(hours=4))
    games_duels.pair_field(field_id, now=_NOW)
    _finish(run_a, 3.0)
    _finish(run_b, 1.0)

    _settle(field_id)
    _settle(field_id)

    with get_session() as s:
        assert career_ledger.career_points_total(s, a) == DUEL_POINTS["week"]


def test_the_delta_never_routes_through_the_placement_formula():
    """The structural assertion. At n=2 placement pays 1.0 or 0.0, i.e. the
    maximum in the game either way. A duel's delta must be the DUEL constant
    and nothing else — this is what a refactor folding duel scoring into
    `_apply_score` would fail."""
    field_id = _field()
    a, b = _user(), _user()
    old_field = _field(starts_on=date(2026, 8, 3))
    for u in (a, b):
        _finish(_enter(old_field, u), 1.0)
    run_a = _enter(field_id, a, entered_at=_NOW - timedelta(hours=5))
    run_b = _enter(field_id, b, entered_at=_NOW - timedelta(hours=4))
    games_duels.pair_field(field_id, now=_NOW)

    # A blowout: 40% against −20%. Under placement this pays the maximum.
    _finish(run_a, 40.0)
    _finish(run_b, -20.0)
    _settle(field_id)

    with get_session() as s:
        rows = s.execute(
            select(career_ledger.CareerEventRow).where(
                career_ledger.CareerEventRow.user_id == a
            )
        ).scalars().all()
    assert [r.reason for r in rows] == ["duel_result"]
    assert [r.delta for r in rows] == [DUEL_POINTS["week"]]


def test_the_margin_of_victory_does_not_change_the_payout():
    """A duel is a binary comparison. Winning by 0.01% pays exactly what
    winning by 40 points pays — which is why the format is safe to run
    alongside an open-field run."""
    payouts = []
    for margin in (0.01, 40.0):
        field_id = _field()
        a, b = _user(), _user()
        old_field = _field(starts_on=date(2026, 8, 3))
        for u in (a, b):
            _finish(_enter(old_field, u), 1.0)
        run_a = _enter(field_id, a, entered_at=_NOW - timedelta(hours=5))
        run_b = _enter(field_id, b, entered_at=_NOW - timedelta(hours=4))
        games_duels.pair_field(field_id, now=_NOW)
        _finish(run_a, 1.0 + margin)
        _finish(run_b, 1.0)
        _settle(field_id)
        with get_session() as s:
            payouts.append(career_ledger.career_points_total(s, a))
    assert payouts[0] == payouts[1]


# ── The record and the card ─────────────────────────────────────────────


def test_the_record_counts_wins_losses_and_never_a_void_as_a_loss():
    field_id = _field()
    a, b = _user(), _user()
    old_field = _field(starts_on=date(2026, 8, 3))
    for u in (a, b):
        _finish(_enter(old_field, u), 1.0)
    run_a = _enter(field_id, a, entered_at=_NOW - timedelta(hours=5))
    run_b = _enter(field_id, b, entered_at=_NOW - timedelta(hours=4))
    games_duels.pair_field(field_id, now=_NOW)
    _finish(run_a, 3.0)
    _finish(run_b, 1.0)
    _settle(field_id)

    with get_session() as s:
        rec_a = games_duels.duel_record(s, a)
        rec_b = games_duels.duel_record(s, b)
    assert (rec_a["wins"], rec_a["losses"], rec_a["voids"]) == (1, 0, 0)
    assert (rec_b["wins"], rec_b["losses"], rec_b["voids"]) == (0, 1, 0)


def test_the_run_card_signs_the_lead_from_this_players_side():
    """Both TWRs are on the wire, so a client could subtract them — and one
    that got the sign backwards would tell a losing player they were ahead.
    One subtraction, one place."""
    field_id = _field()
    a, b = _user(), _user()
    old_field = _field(starts_on=date(2026, 8, 3))
    for u in (a, b):
        _finish(_enter(old_field, u), 1.0)
    run_a = _enter(field_id, a, entered_at=_NOW - timedelta(hours=5))
    run_b = _enter(field_id, b, entered_at=_NOW - timedelta(hours=4))
    games_duels.pair_field(field_id, now=_NOW)

    card_a = games_duels.duel_view_for_run(a, run_a)
    card_b = games_duels.duel_view_for_run(b, run_b)
    assert card_a is not None and card_b is not None
    assert card_a["opponent"]["handle"] == card_b["opponent"]["handle"].replace(
        card_b["opponent"]["handle"], card_a["opponent"]["handle"]
    )
    assert card_a["state"] == "live"
    assert card_a["points_at_stake"] == DUEL_POINTS["week"]
    # Neither has a measured close yet: the gap is UNKNOWN, not level. `0.0`
    # would draw a dead heat on a duel that has not started.
    assert card_a["lead_pct"] is None


def test_a_run_with_no_duel_returns_none_rather_than_an_empty_card():
    field_id = _field()
    u = _user()
    run = _enter(field_id, u)
    assert games_duels.duel_view_for_run(u, run) is None


def test_the_card_discloses_a_desk_opponent_as_one():
    """The first-run duel is "beat the Index Desk". A player who did not know
    their opponent was the benchmark would be reading a different result than
    the one they got."""
    field_id = _field()
    desk = _user(is_desk=True, desk_key="index", handle="INDEX_DESK")
    _enter(field_id, desk)
    newbie = _user()
    run = _enter(field_id, newbie)
    games_duels.pair_field(field_id, now=_NOW)

    card = games_duels.duel_view_for_run(newbie, run)
    assert card is not None
    assert card["kind"] == "first_run"
    assert card["opponent"]["is_desk"] is True
    assert card["opponent"]["desk_key"] == "index"
    assert card["opponent"]["desk_rule"]


def test_the_card_carries_no_currency_figure_for_anyone():
    """§6.1's invariant, applied to the duel surface as well as the board:
    percentages only, never AMI Cash — not the opponent's, and not the
    player's own, on a surface built to compare them."""
    field_id = _field()
    desk = _user(is_desk=True, desk_key="index")
    _enter(field_id, desk)
    newbie = _user()
    run = _enter(field_id, newbie)
    games_duels.pair_field(field_id, now=_NOW)

    card = games_duels.duel_view_for_run(newbie, run)
    # Checked against the KEY SET, not a repr substring: `points_at_stake` is
    # a points figure and contains the word "stake", and a substring check
    # that flagged it would be the kind of noisy guard someone disables.
    keys = set(card) | set(card["opponent"])
    for banned in ("cash", "current_cash", "total_value", "nav", "ami_cash",
                   "starting_capital", "stake"):
        assert banned not in keys, f"{banned} leaked onto the duel card"


# ── The Close's beat 2 (§10.2) ──────────────────────────────────────────


def _closed_duel(*, void_side: bool = False, tie: bool = False):
    """A field with one settled duel and both entries closed, ready for the
    Close payload."""
    from app.services import games_record_service

    field_id = _field()
    desk = _user(is_desk=True, desk_key="index", handle="INDEX_DESK")
    desk_run = _enter(field_id, desk)
    newbie = _user()
    run = _enter(field_id, newbie)
    games_duels.pair_field(field_id, now=_NOW)

    _finish(run, 1.0 if tie else 4.0)
    _finish(desk_run, 1.0, state="void" if void_side else "finished")
    with get_session() as s:
        games_duels.settle_field_duels(s, field_id, now=_NOW)
    # The Close needs a scored field.
    with get_session() as s:
        f = s.execute(select(GameFieldRow).where(GameFieldRow.id == field_id)).scalars().one()
        f.state = "closed"
        f.scoring_basis = "benchmark"
    return games_record_service, newbie, run


def test_a_settled_duel_takes_beat_two_over_the_counterfactual():
    """§10.2's priority order. A duel is a RESULT against a named opponent;
    the counterfactual is an analysis of a road not taken. On a first run the
    duel is the whole narrative — *you beat the market* or *the market beat
    you* — and both are stories where the counterfactual is a footnote."""
    svc, user_id, run_id = _closed_duel()
    payload = svc.get_close_payload(user_id, run_id, now=_NOW)

    insight = payload["beats"]["insight"]
    assert insight["kind"] == "duel"
    assert insight["outcome"] == "won"
    assert insight["opponent_is_desk"] is True
    assert insight["margin_pct"] == pytest.approx(3.0)
    assert insight["points_delta"] == DUEL_POINTS["week"]


def test_only_one_insight_is_ever_returned():
    """The three-beat budget is the whole point of the surface — the Close
    had become "a report with confetti". Two insights stacked is the
    regression this guards."""
    svc, user_id, run_id = _closed_duel()
    insight = svc.get_close_payload(user_id, run_id, now=_NOW)["beats"]["insight"]
    assert isinstance(insight, dict)
    assert insight["kind"] == "duel"
    # The counterfactual's own keys must NOT also be present on the chosen
    # insight — it lives in the debrief panel instead.
    assert "hold_index_pct" not in insight


def test_the_counterfactual_still_lives_in_the_debrief_when_the_duel_wins_beat_two():
    """Losing the beat is not losing the data. Everything else moves one tap
    deeper — "a ceremony with an appendix"."""
    svc, user_id, run_id = _closed_duel()
    payload = svc.get_close_payload(user_id, run_id, now=_NOW)
    assert "counterfactual_hold_index_pct" in payload["debrief"]


def test_a_void_duel_does_not_take_beat_two():
    """A void duel has nothing to say — one side was unmeasurable — so the
    counterfactual, which is still true, is the better use of the one insight
    the player gets."""
    svc, user_id, run_id = _closed_duel(void_side=True)
    insight = svc.get_close_payload(user_id, run_id, now=_NOW)["beats"]["insight"]
    assert insight["kind"] == "counterfactual"


def test_a_run_with_no_duel_still_gets_the_counterfactual():
    """The mutation guard: wiring the duel in must not have removed the
    fallback for the majority of runs, which have no duel at all."""
    from app.services import games_record_service

    field_id = _field()
    u = _user()
    run = _enter(field_id, u)
    _finish(run, 2.0)
    with get_session() as s:
        f = s.execute(select(GameFieldRow).where(GameFieldRow.id == field_id)).scalars().one()
        f.state = "closed"
        f.scoring_basis = "benchmark"

    insight = games_record_service.get_close_payload(u, run, now=_NOW)["beats"]["insight"]
    assert insight["kind"] == "counterfactual"


def test_a_drawn_duel_still_takes_beat_two():
    """A draw is a real outcome against a named opponent — it outranks the
    counterfactual for the same reason a win does."""
    svc, user_id, run_id = _closed_duel(tie=True)
    insight = svc.get_close_payload(user_id, run_id, now=_NOW)["beats"]["insight"]
    assert insight["kind"] == "duel"
    assert insight["outcome"] == "draw"
    assert insight["points_delta"] == 0
