"""CR109 — the field board, and the three things it must never do.

Saiful, playing the shipped build: *"How do I see my current standing against
the rest of the field in the weekly game?"* This is that surface. The tests
here are weighted toward the invariants rather than the happy path, because
every one of them is a rule the design wrote down *because* the obvious
implementation breaks it:

1. **Rank on % TWR, never money.** §6.1 states this as an invariant "to be
   written down and tested" — the moment a board ranks absolute AMI Cash,
   capital tier becomes pay-to-win and the "no purchase necessary" position in
   `competition_rules.md` collapses. Tested by scanning the whole payload for
   currency-shaped keys rather than by checking the one field we remembered.

2. **A board never renders a mirror.** The two counterfactual lines are private
   measurement (§10.4) and the fence says assert it at the serializer.

3. **Unmeasured is not zero.** A run with no completed close has no TWR.
   Reporting it as 0.00% would put an unmeasured entrant in the middle of the
   pack looking flat — the `?? 0` defect class this feature has already hit
   nine times.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import GameEntryRow, PortfolioNavDailyRow, User
from app.services import games_board as board
from app.services import games_service as games

_ENTRY_OPEN = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)


def _nav(user_id, run_id, day: date, nav: float, capital_event: str | None = None) -> None:
    """`capital_event` is a nullable STRING ("open" / "restart" / "topup"), not
    a bool — a truthy value there resets the TWR chain at that point, which is
    exactly what it is for. `run_game_nav_snapshot_tick` writes "open" on a
    run's first row and NULL afterwards, so that is what this fixture writes."""
    with get_session() as s:
        s.add(PortfolioNavDailyRow(
            user_id=user_id, run_id=run_id, as_of_date=day,
            nav=nav, cash=0.0, price_source="yfinance",
            capital_event=capital_event,
        ))


def _player(handle: str, *, is_desk: bool = False, desk_key: str | None = None):
    user_id = uuid4()
    with get_session() as s:
        s.add(User(
            id=user_id, handle=handle, is_anonymous=not is_desk,
            is_desk=is_desk, desk_key=desk_key,
        ))
    entry = games.enter_field(user_id, now=_ENTRY_OPEN)
    return user_id, entry.run_id


def _curve(user_id, run_id, *navs: float) -> None:
    for i, nav in enumerate(navs):
        _nav(user_id, run_id, date(2026, 8, 10 + i), nav, "open" if i == 0 else None)


# ══ Ranking ═════════════════════════════════════════════════════════════════


def test_the_board_ranks_on_twr_and_names_the_field():
    me, my_run = _player("careful-vector")
    rival, rival_run = _player("bold-lattice")
    third, third_run = _player("steady-prism")

    _curve(me, my_run, 10_000, 10_200)      # +2.00%
    _curve(rival, rival_run, 10_000, 10_500)  # +5.00%
    _curve(third, third_run, 10_000, 9_900)   # -1.00%

    payload = board.board_for_run(me, my_run)

    assert payload["entrant_count"] == 3
    assert payload["standings_open"] is True
    assert [r["handle"] for r in payload["rows"]] == [
        "bold-lattice", "careful-vector", "steady-prism",
    ]
    assert [r["rank"] for r in payload["rows"]] == [1, 2, 3]
    assert payload["your_rank"] == 2
    assert payload["your_twr_pct"] == 2.0
    assert [r["is_you"] for r in payload["rows"]] == [False, True, False]


def test_a_bigger_book_does_not_outrank_a_better_percentage():
    """§6.1's invariant, stated as a scenario: the entrant who made more MONEY
    must lose to the entrant who made a better PERCENTAGE. If this ever
    inverts, capital tier has become pay-to-win."""
    small, small_run = _player("small-book")
    big, big_run = _player("big-book")

    _curve(small, small_run, 1_000, 1_100)    # +10.0%, made $100
    _curve(big, big_run, 100_000, 105_000)    # +5.0%, made $5,000

    payload = board.board_for_run(small, small_run)
    assert payload["rows"][0]["handle"] == "small-book"
    assert payload["your_rank"] == 1


def test_no_currency_amount_appears_anywhere_in_the_payload():
    """Scanned rather than spot-checked: a field added later that happens to
    carry money must fail this test, not slip past a check that only knew
    about the fields present when it was written."""
    me, my_run = _player("careful-vector")
    _curve(me, my_run, 10_000, 10_200)

    payload = board.board_for_run(me, my_run)
    money_words = ("cash", "nav", "value", "balance", "capital", "notional", "fees", "amount")
    for row in payload["rows"]:
        for key in row:
            assert not any(w in key.lower() for w in money_words), (
                f"board row exposes {key!r} — boards rank on % TWR only (§6.1)"
            )
    for key in payload:
        assert not any(w in key.lower() for w in money_words), key


def test_no_mirror_reaches_the_board():
    """§10.4's private measurement, fenced at the serializer rather than the
    widget — the design says so explicitly."""
    me, my_run = _player("careful-vector")
    _curve(me, my_run, 10_000, 10_200)

    payload = board.board_for_run(me, my_run)
    blob = str(payload)
    assert "counterfactual" not in blob
    for row in payload["rows"]:
        assert "counterfactual_hold_index_pct" not in row
        assert "counterfactual_hold_first_picks_pct" not in row


def test_ties_share_a_rank():
    a, a_run = _player("alpha-desk-a")
    b, b_run = _player("beta-desk-b")
    c, c_run = _player("gamma-desk-c")
    _curve(a, a_run, 10_000, 10_100)
    _curve(b, b_run, 10_000, 10_100)
    _curve(c, c_run, 10_000, 10_000)

    payload = board.board_for_run(a, a_run)
    ranks = {r["handle"]: r["rank"] for r in payload["rows"]}
    assert ranks["alpha-desk-a"] == ranks["beta-desk-b"] == 1
    assert ranks["gamma-desk-c"] == 3


# ══ Unmeasured is not zero ══════════════════════════════════════════════════


def test_a_run_with_no_close_yet_is_unranked_not_flat():
    me, my_run = _player("day-one")
    payload = board.board_for_run(me, my_run)

    row = payload["rows"][0]
    assert row["twr_pct"] is None, "an unmeasured run is not a 0.00% run"
    assert row["rank"] is None, "and it is not tied for last either"
    assert row["closes_counted"] == 0
    assert payload["standings_open"] is False
    assert payload["your_rank"] is None
    assert payload["your_twr_pct"] is None


def test_measured_entrants_rank_above_unmeasured_ones():
    me, my_run = _player("measured")
    other, other_run = _player("not-yet")
    _curve(me, my_run, 10_000, 9_000)  # -10%, still ranked

    payload = board.board_for_run(me, my_run)
    assert [r["handle"] for r in payload["rows"]] == ["measured", "not-yet"]
    assert payload["rows"][0]["rank"] == 1
    assert payload["rows"][1]["rank"] is None


def test_the_board_says_how_often_it_moves():
    """§10: one rank beat per close, never per tick. A player watching an
    unchanged number all afternoon must be told why, or they conclude the
    feature is broken (CR040 — degrade loudly covers staleness too)."""
    me, my_run = _player("careful-vector")
    payload = board.board_for_run(me, my_run)
    assert payload["updates"] == "daily_close"


# ══ Disclosure + access ═════════════════════════════════════════════════════


def test_a_desk_is_marked_as_a_desk_with_its_rule():
    me, my_run = _player("careful-vector")
    _desk, desk_run = _player("Momentum Desk", is_desk=True, desk_key="momentum")
    _curve(me, my_run, 10_000, 10_100)

    payload = board.board_for_run(me, my_run)
    desk_row = next(r for r in payload["rows"] if r["handle"] == "Momentum Desk")
    assert desk_row["is_desk"] is True
    assert desk_row["desk_key"] == "momentum"
    assert desk_row["desk_rule"], "a desk on a board without its rule is an undisclosed bot"
    assert payload["desk_count"] == 1

    human_row = next(r for r in payload["rows"] if r["handle"] == "careful-vector")
    assert human_row["is_desk"] is False
    assert human_row["desk_rule"] is None


def test_a_run_id_alone_does_not_open_someone_elses_field():
    """The board is the one payload that names other entrants, so ownership is
    checked against the caller's own entry rather than the run id."""
    me, my_run = _player("careful-vector")
    stranger = uuid4()
    with pytest.raises(board.BoardNotAvailable):
        board.board_for_run(stranger, my_run)


def test_a_forfeited_entry_leaves_the_board():
    me, my_run = _player("careful-vector")
    other, other_run = _player("gone-fishing")
    _curve(me, my_run, 10_000, 10_100)
    _curve(other, other_run, 10_000, 10_900)

    with get_session() as s:
        row = s.execute(
            select(GameEntryRow).where(GameEntryRow.run_id == other_run)
        ).scalar_one()
        row.state = "forfeit"

    payload = board.board_for_run(me, my_run)
    assert [r["handle"] for r in payload["rows"]] == ["careful-vector"]
    assert payload["your_rank"] == 1
