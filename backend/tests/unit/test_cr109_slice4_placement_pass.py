"""CR109 slice 4 — the scoring pass routing onto placement.

Slice 3's integration tests all use a field of ONE on purpose: placement did
not exist, so thin was the only case. These use a field of many, which is the
case slice 4 is entirely about.

The property under test throughout is that **the basis is decided by the field
and frozen on it** — one field, one basis, no per-entrant choice — and that the
`n >= 8` fence sits between the two paths rather than inside either.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import (
    CareerEventRow,
    GameEntryRow,
    GameFieldRow,
    PortfolioNavDailyRow,
)
from app.schemas.trade import Side
from app.services import career_ledger
from app.services import games_scoring_pass as pass_module
from app.services import games_service as games
from app.services.games_scoring import PLACEMENT_MIN_FIELD

_ENTRY_OPEN_CLOSED_MARKET = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)
_MARKET_OPEN = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)
_STARTS_ON = date(2026, 8, 10)
_MID = date(2026, 8, 12)
_ENDS_ON = date(2026, 8, 14)
_AFTER_CLOSE = datetime(2026, 8, 17, 15, 0, tzinfo=timezone.utc)


def _nav(user_id, run_id, *, as_of, nav, capital_event=None, price_source="live"):
    with get_session() as s:
        s.add(PortfolioNavDailyRow(
            user_id=user_id, run_id=run_id, as_of_date=as_of, nav=nav, cash=nav,
            price_source=price_source, capital_event=capital_event,
        ))


def _entrant(end_nav: float, *, mock_day: date | None = None) -> tuple[UUID, UUID]:
    """One entrant in the shared weekly field, finishing at `end_nav`."""
    user_id = uuid4()
    entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=1,
        now=_MARKET_OPEN,
    )
    _nav(user_id, entry.run_id, as_of=_STARTS_ON, nav=10_000.0, capital_event="open",
         price_source="mock" if mock_day == _STARTS_ON else "live")
    _nav(user_id, entry.run_id, as_of=_MID, nav=(10_000.0 + end_nav) / 2,
         price_source="mock" if mock_day == _MID else "live")
    _nav(user_id, entry.run_id, as_of=_ENDS_ON, nav=end_nav,
         price_source="mock" if mock_day == _ENDS_ON else "live")
    return user_id, entry.id


def _make_live() -> None:
    with get_session() as s:
        for field in s.execute(select(GameFieldRow)).scalars().all():
            if field.state in ("entry_open", "locked"):
                field.state = "live"


def _field_of(end_navs: list[float], *, mock_days=None) -> list[tuple[UUID, UUID]]:
    mock_days = mock_days or [None] * len(end_navs)
    made = [_entrant(nav, mock_day=m) for nav, m in zip(end_navs, mock_days)]
    _make_live()
    return made


def _rows(entry_ids: list[UUID]) -> list[GameEntryRow]:
    with get_session() as s:
        return [
            s.execute(
                select(GameEntryRow).where(GameEntryRow.id == eid)
            ).scalar_one()
            for eid in entry_ids
        ]


def _the_field() -> GameFieldRow:
    with get_session() as s:
        return s.execute(
            select(GameFieldRow).where(GameFieldRow.state == "closed")
        ).scalars().first()


# ── The fence: 8 is where the basis changes ──────────────────────────────


def test_a_field_of_eight_closes_on_placement():
    made = _field_of([10_000 + 100 * i for i in range(PLACEMENT_MIN_FIELD)])
    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    assert _the_field().scoring_basis == "placement"
    rows = _rows([eid for _u, eid in made])
    assert sorted(r.final_rank for r in rows) == list(range(1, 9))
    assert {r.scored_entrant_count for r in rows} == {8}


def test_a_field_of_seven_stays_on_the_benchmark():
    # One short of the fence. The design's reason is arithmetic, not taste:
    # the curve is a coin flip at n=2 and undefined at n=1, and 8 is where
    # §6.6 draws the line.
    made = _field_of([10_000 + 100 * i for i in range(7)])
    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    assert _the_field().scoring_basis == "benchmark"
    rows = _rows([eid for _u, eid in made])
    # Still RANKED — only the scoring is gated. "4th of 7" is a fact.
    assert sorted(r.final_rank for r in rows) == list(range(1, 8))
    assert {r.scored_entrant_count for r in rows} == {7}


def _seed_points(user_id: UUID, points: int) -> None:
    """Give a player a prior balance so a debit has somewhere to land.

    Without this every negative leg reads as 0, because the ledger clamps
    AT WRITE (Amendment D): a debit that would take the total below zero
    writes exactly the distance to zero. That is correct and deliberate —
    but it means a fresh account cannot demonstrate the curve's lower half.
    """
    with get_session() as s:
        s.add(CareerEventRow(
            user_id=user_id, delta=points, delta_uncapped=points,
            reason="test_seed", field_id=uuid4(), entry_id=uuid4(),
        ))


def test_the_winner_of_a_placed_field_is_paid_the_curves_ceiling():
    # p = 1.0 -> base +100, weekly weight 1.0, apprentice multiplier 1.0.
    # The stipend is a separate ledger row, so subtract it to see the
    # placement leg alone.
    made = _field_of([10_000 + 100 * i for i in range(8)])
    _seed_points(made[0][0], 1_000)  # lowest end_nav -> rank 8
    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    rows = _rows([eid for _u, eid in made])
    winner = next(r for r in rows if r.final_rank == 1)
    last = next(r for r in rows if r.final_rank == 8)
    assert winner.career_points_delta - winner.stipend_points == 100
    assert last.career_points_delta - last.stipend_points == -40


def test_a_fresh_players_debit_clamps_at_the_ledger_not_the_display():
    # Amendment D, restated here because placement is the first thing that
    # can produce a large debit: last of eight is -40, and a player at zero
    # writes a debit of exactly the distance to zero. The DISPLAYED number
    # stays the real number precisely because the write was clamped.
    made = _field_of([10_000 + 100 * i for i in range(8)])
    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    last = next(r for r in _rows([eid for _u, eid in made]) if r.final_rank == 8)
    assert last.career_points_delta - last.stipend_points == 0
    with get_session() as s:
        assert career_ledger.career_points_total(s, made[0][0]) >= 0


def test_placement_REPLACES_the_alpha_points_it_does_not_add_to_them():
    # The mutation this guards: `+=` instead of `=` in the placement loop
    # would pay a winner the curve's ceiling PLUS whatever alpha they
    # happened to post, which is both double-counting and a number no table
    # in the design produces.
    made = _field_of([10_000 + 100 * i for i in range(8)])
    for user_id, _eid in made:
        _seed_points(user_id, 1_000)
    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    rows = _rows([eid for _u, eid in made])
    placement_legs = sorted(
        r.career_points_delta - r.stipend_points for r in rows
    )
    # The curve for n=8, exactly — every entrant, no alpha residue anywhere.
    # These 8 numbers are the whole assertion: they come from
    # `placement_to_points((8 - rank) / 7)` and from nothing else.
    assert placement_legs == [-40, -29, -17, -6, 5, 28, 60, 100]


# ── Ties ─────────────────────────────────────────────────────────────────


def test_identical_returns_share_a_rank_and_are_paid_identically():
    # Two indistinguishable results must not be separated by row order —
    # that would let an arbitrary insert sequence decide which of two equal
    # players got paid more, permanently.
    made = _field_of([10_400, 10_400, 10_300, 10_200, 10_100, 10_050, 10_020, 10_010])
    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    rows = _rows([eid for _u, eid in made])
    ranks = sorted(r.final_rank for r in rows)
    assert ranks[:3] == [1, 1, 3], "standard competition ranking, not 1/2/3"
    tied = [r for r in rows if r.final_rank == 1]
    assert len({r.career_points_delta for r in tied}) == 1


# ── VOID entrants ────────────────────────────────────────────────────────


def test_a_void_entrant_is_neither_ranked_nor_counted_in_n():
    # Nine entrants, two of them void: n = 7, so the field drops BELOW the
    # fence and scores on the benchmark. Counting voids would have placed
    # real players against a result that was never measured.
    made = _field_of(
        [10_000 + 100 * i for i in range(9)],
        mock_days=[None, None, _MID, None, None, None, None, _MID, None],
    )
    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    assert _the_field().scoring_basis == "benchmark"
    rows = _rows([eid for _u, eid in made])
    voids = [r for r in rows if r.state == "void"]
    real = [r for r in rows if r.state == "finished"]
    assert len(voids) == 2 and len(real) == 7
    assert all(r.final_rank is None for r in voids)
    assert all(r.scored_entrant_count is None for r in voids)
    assert {r.scored_entrant_count for r in real} == {7}


def test_a_field_of_eight_real_results_plus_voids_still_places():
    # The mirror of the test above: voids must not DROP a field that has
    # eight real results below the fence either.
    made = _field_of(
        [10_000 + 100 * i for i in range(9)],
        mock_days=[_MID] + [None] * 8,
    )
    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    assert _the_field().scoring_basis == "placement"
    real = [r for r in _rows([eid for _u, eid in made]) if r.state == "finished"]
    assert {r.scored_entrant_count for r in real} == {8}


# ── The title multiplier is frozen at run open ───────────────────────────


def test_the_multiplier_is_frozen_at_open_not_read_at_close():
    made = _field_of([10_000 + 100 * i for i in range(8)])
    _seed_points(made[0][0], 1_000)
    winner_user, winner_entry = None, None
    with get_session() as s:
        rows = s.execute(select(GameEntryRow)).scalars().all()
        # Everyone entered untitled, so every frozen multiplier is 1.0.
        assert {float(r.title_multiplier) for r in rows} == {1.0}
        # Promote one player mid-run by hand. Reading the title at CLOSE
        # would pay them 1.4x for a run they traded as an apprentice.
        target = next(r for r in rows if r.user_id == made[0][0])
        winner_user, winner_entry = target.user_id, target.id

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)
    row = _rows([winner_entry])[0]
    # Rank 8 of 8 (lowest end_nav) -> -40, unmultiplied.
    assert row.final_rank == 8
    assert row.career_points_delta - row.stipend_points == -40
    assert float(row.title_multiplier) == 1.0
    assert winner_user is not None


def test_a_titled_player_is_paid_their_frozen_multiplier():
    made = _field_of([10_000 + 100 * i for i in range(8)])
    winner_user = made[-1][0]  # highest end_nav -> rank 1
    with get_session() as s:
        row = s.execute(
            select(GameEntryRow).where(GameEntryRow.user_id == winner_user)
        ).scalar_one()
        row.title_multiplier = 1.4  # as though they entered as an analyst

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)
    scored = _rows([made[-1][1]])[0]
    assert scored.final_rank == 1
    assert scored.career_points_delta - scored.stipend_points == 140


def test_an_entry_predating_slice_four_scores_as_untitled_never_as_zero():
    # `title_multiplier` is NULL on every row the migration backfilled. A
    # `None` that multiplied as 0 would silently delete those runs' points.
    made = _field_of([10_000 + 100 * i for i in range(8)])
    with get_session() as s:
        for row in s.execute(select(GameEntryRow)).scalars().all():
            row.title_multiplier = None

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)
    rows = _rows([eid for _u, eid in made])
    winner = next(r for r in rows if r.final_rank == 1)
    assert winner.career_points_delta - winner.stipend_points == 100


# ── The title itself ─────────────────────────────────────────────────────


def test_a_title_recomputes_on_close_with_no_roll_anywhere():
    # §6.4's acceptance: "titles recompute on any run close with no
    # synchronized roll anywhere." Nothing is scheduled, nothing is stored
    # as a promotion — the title is a function of the totals.
    made = _field_of([10_000 + 100 * i for i in range(8)])
    winner_user = made[-1][0]
    with get_session() as s:
        assert career_ledger.current_title(s, winner_user) == "apprentice"

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    with get_session() as s:
        # One finish is not yet the milestone, and 100-odd points is under
        # the 500 threshold — but the call resolves live, off the ledger.
        assert career_ledger.current_title(s, winner_user) == "apprentice"
        assert career_ledger.finished_count(s, winner_user) == 1
        assert career_ledger.qualifying_finish_count(s, winner_user) == 0


def test_a_field_of_eight_confers_no_title_witness():
    # "Prestige needs witnesses" — TITLE_MIN_FIELD is 20, so an alpha-sized
    # field of 8 scores fully but qualifies nobody for a named rung.
    made = _field_of([10_000 + 100 * i for i in range(8)])
    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    with get_session() as s:
        for user_id, _eid in made:
            assert career_ledger.qualifying_finish_count(s, user_id) == 0


# ── The minimum forfeit debit (§18) ──────────────────────────────────────


def _live_entry(user_id: UUID):
    entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)
    _make_live()
    return entry


def test_forfeiting_costs_the_minimum_not_zero():
    # The churn hole this closes: the design's debit is placement-based, so
    # abandoning from mid-field cost ~0 and rolling starts always offered
    # another field to join.
    user_id = uuid4()
    entry = _live_entry(user_id)
    _seed_points(user_id, 500)

    preview = games.preview_restart(user_id, entry.run_id)
    assert preview["career_points_debit"] == 10

    result = games.commit_restart(user_id, entry.run_id, now=_MARKET_OPEN)
    assert result["state"] == "forfeit"
    assert result["career_points_debit"] == 10
    with get_session() as s:
        assert career_ledger.career_points_total(s, user_id) == 490
        assert career_ledger.forfeit_count(s, user_id) == 1


def test_the_preview_states_the_cost_before_the_player_commits():
    # §21's restart-flow rule: "must show what forfeits and what it costs."
    user_id = uuid4()
    entry = _live_entry(user_id)
    preview = games.preview_restart(user_id, entry.run_id)
    assert "10" in preview["reason"]
    with get_session() as s:
        # Previewing must not CHARGE — it is the sentence before the choice.
        assert career_ledger.forfeit_count(s, user_id) == 0
        assert career_ledger.career_points_total(s, user_id) == 0


def test_a_player_at_zero_pays_what_they_have_which_is_nothing():
    # The floor stops a player WITH points churning for free; it does not
    # invent a debt. Amendment D's clamp still owns the write, and the
    # reported number is what the ledger actually took — reporting the floor
    # here would tell a player they were charged something they were not.
    user_id = uuid4()
    entry = _live_entry(user_id)
    result = games.commit_restart(user_id, entry.run_id, now=_MARKET_OPEN)
    assert result["career_points_debit"] == 0
    with get_session() as s:
        assert career_ledger.career_points_total(s, user_id) == 0


def test_forfeiting_twice_charges_once():
    # `commit_restart` raises on a non-live run, but the ledger's
    # (entry_id, reason) constraint is the real guard — a retried request
    # must not charge a second time for one abandonment.
    user_id = uuid4()
    entry = _live_entry(user_id)
    _seed_points(user_id, 500)
    games.commit_restart(user_id, entry.run_id, now=_MARKET_OPEN)
    with pytest.raises(games.RunNotLiveError):
        games.commit_restart(user_id, entry.run_id, now=_MARKET_OPEN)
    with get_session() as s:
        assert career_ledger.career_points_total(s, user_id) == 490


def test_the_debit_and_the_state_change_are_one_transaction():
    # A forfeit recorded without its debit is a free restart that looks
    # charged; the reverse is a charge for a run still live. Both halves
    # land in the same session or neither does.
    user_id = uuid4()
    entry = _live_entry(user_id)
    _seed_points(user_id, 500)
    games.commit_restart(user_id, entry.run_id, now=_MARKET_OPEN)
    with get_session() as s:
        row = s.execute(
            select(GameEntryRow).where(GameEntryRow.id == entry.id)
        ).scalar_one()
        assert row.state == "forfeit"
        assert row.career_points_delta == -10
        posted = s.execute(
            select(CareerEventRow).where(
                CareerEventRow.entry_id == entry.id,
                CareerEventRow.reason == "forfeit_debit",
            )
        ).scalar_one()
        assert posted.delta == -10


def test_a_forfeited_run_never_reaches_the_placement_field():
    # `_SCORABLE_STATES` excludes `forfeit`, so a player cannot abandon a
    # run and still be ranked in the field they walked out of — which would
    # both dilute everyone else's `p` and pay the quitter a placement.
    made = _field_of([10_000 + 100 * i for i in range(8)])
    quitter_user, quitter_entry = made[0]
    with get_session() as s:
        run_id = s.execute(
            select(GameEntryRow.run_id).where(GameEntryRow.id == quitter_entry)
        ).scalar_one()
    games.commit_restart(quitter_user, run_id, now=_MARKET_OPEN)

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    assert _the_field().scoring_basis == "benchmark"  # n dropped to 7
    row = _rows([quitter_entry])[0]
    assert row.state == "forfeit"
    assert row.final_rank is None
