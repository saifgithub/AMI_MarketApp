"""CR109 slice 5 — the period arc's live beats (design §10).

Three properties, and each is a rule from the design rather than a preference:

1. **Attribution sums to the run.** A game run has exactly one capital event
   (its own open), so per-ticker contribution plus cash drag must reconstruct
   the headline return exactly. A beat that narrates a number the Close then
   contradicts is worse than no beat.
2. **The near-miss points up only.** §10 permits *"2nd is 1.1% ahead"* and
   forbids the downward twin. Enforced structurally — the payload has no
   field for the entrant below you — so the assertion here is about an absent
   KEY, not about copy.
3. **Standing moves once per close; your own attribution is live.** The two
   clocks are different on purpose (`games_arc`'s docstring), so the payload
   has to say which is which.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import GameFieldRow, PortfolioNavDailyRow
from app.schemas.trade import Side
from app.services import games_arc
from app.services import games_service as games
from app.services.games_scoring import TradeLeg, contribution_by_ticker, trade_fee

_ENTRY_OPEN_CLOSED_MARKET = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)
_MARKET_OPEN = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)
_STARTS_ON = date(2026, 8, 10)
_ENDS_ON = date(2026, 8, 14)


# ── The attribution identity ─────────────────────────────────────────────


def _leg(ticker, side, qty, price, day=_STARTS_ON):
    return TradeLeg(ticker=ticker, side=side, quantity=qty, price=price, opened_at=day)


def test_contribution_reconstructs_the_run_return_exactly():
    """The identity the module rests on: with one capital event, per-ticker
    contribution plus untouched cash IS the run's simple return."""
    stake = 10_000.0
    legs = [_leg("AAPL", "buy", 10, 200.0), _leg("NVDA", "buy", 5, 100.0)]
    marks = {"AAPL": 220.0, "NVDA": 90.0}

    contributions = contribution_by_ticker(legs, marks, stake)

    spent = 10 * 200.0 + trade_fee(2000.0) + 5 * 100.0 + trade_fee(500.0)
    final_nav = (stake - spent) + 10 * 220.0 + 5 * 90.0
    expected_pct = (final_nav / stake - 1.0) * 100
    assert sum(c.pct_points for c in contributions) == pytest.approx(expected_pct, abs=0.02)


def test_the_fee_lands_inside_the_ticker_that_paid_it():
    """§1.1 — the fee is the lab's price signal. Reported away from the
    decision it priced it teaches nothing, so a round trip at an unchanged
    price must show as a LOSS on that name, not as a separate cost line."""
    legs = [_leg("AAPL", "buy", 10, 200.0), _leg("AAPL", "sell", 10, 200.0)]

    (aapl,) = contribution_by_ticker(legs, {"AAPL": 200.0}, 10_000.0)

    assert aapl.pnl == pytest.approx(-2 * trade_fee(2000.0), abs=0.01)
    assert aapl.pct_points < 0


def test_a_short_attributes_the_other_way():
    """Amendment G — a short profits when the mark FALLS. The sign has to
    come out of the same walk the Close scores on, not a special case."""
    legs = [_leg("TSLA", "sell", 10, 300.0)]

    (tsla,) = contribution_by_ticker(legs, {"TSLA": 250.0}, 10_000.0)

    assert tsla.pct_points > 0
    assert tsla.open_quantity == -10


def test_a_missing_mark_is_priced_at_cost_not_at_zero():
    """The `?? 0` refusal. An unpriced holding means "we could not price
    this"; valuing it at zero reports a wipeout the player did not take."""
    legs = [_leg("XYZ", "buy", 10, 100.0)]

    (xyz,) = contribution_by_ticker(legs, {}, 10_000.0)

    assert xyz.pnl == pytest.approx(-trade_fee(1000.0), abs=0.01)


def test_no_trades_attributes_nothing():
    assert contribution_by_ticker([], {"AAPL": 1.0}, 10_000.0) == []


def test_biggest_absolute_mover_leads_even_when_it_is_a_loss():
    """The beat names what DROVE the run — a −4% name outranks a +1% one.
    Sorting on signed contribution would bury every blowup's own cause."""
    legs = [_leg("WIN", "buy", 1, 100.0), _leg("LOSS", "buy", 10, 100.0)]
    marks = {"WIN": 200.0, "LOSS": 60.0}

    ranked = contribution_by_ticker(legs, marks, 10_000.0)

    assert ranked[0].ticker == "LOSS"
    assert ranked[0].pct_points < 0


# ── The phase machine ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "field_state,entry_state,days_left,expected",
    [
        ("entry_open", "entered", 7, games_arc.PHASE_ENTRY_OPEN),
        ("announced", "entered", 7, games_arc.PHASE_ENTRY_OPEN),
        ("locked", "entered", 7, games_arc.PHASE_BELL),
        ("live", "active", 7, games_arc.PHASE_LIVE),
        ("live", "active", 2, games_arc.PHASE_FINAL_STRETCH),
        ("settling", "active", 0, games_arc.PHASE_SETTLING),
        ("closed", "finished", 0, games_arc.PHASE_CLOSED),
        ("archived", "finished", 0, games_arc.PHASE_CLOSED),
    ],
)
def test_phase_machine(field_state, entry_state, days_left, expected):
    assert games_arc.phase_for(field_state, entry_state, "week", days_left) == expected


def test_a_finished_entry_is_closed_even_in_a_live_field():
    """A forfeit ends YOUR run while the field keeps running. The beat has to
    follow the entry, not the field, or a forfeited player is told they are
    in the final stretch of a contest they left."""
    assert games_arc.phase_for("live", "forfeited", "week", 3) == games_arc.PHASE_CLOSED


def test_final_stretch_is_per_cadence_not_a_fixed_number():
    """Two days left in a week is the final stretch; two days left in a year
    is not the same event, and a shared constant would call them the same."""
    assert games_arc.phase_for("live", "active", "week", 3) == games_arc.PHASE_LIVE
    assert games_arc.phase_for("live", "active", "year", 3) == games_arc.PHASE_FINAL_STRETCH
    assert games_arc.phase_for("live", "active", "year", 21) == games_arc.PHASE_LIVE


def test_an_unknown_cadence_falls_to_the_shortest_window():
    """Same posture as `cadence_weight`: an unknown cadence degrades to the
    weekly value rather than raising. A beat is not worth a 500."""
    assert games_arc.phase_for("live", "active", "fortnight", 2) == (
        games_arc.PHASE_FINAL_STRETCH
    )


# ── The near-miss fence ──────────────────────────────────────────────────


def _row(rank, twr, *, is_you=False, handle="x"):
    return {"rank": rank, "twr_pct": twr, "is_you": is_you, "handle": handle}


def test_gap_is_measured_to_the_entrant_immediately_above():
    rows = [_row(1, 5.0), _row(2, 3.0), _row(3, 1.0, is_you=True)]

    gap, rank = games_arc._gap_to_next(rows, 3)

    assert (gap, rank) == (2.0, 2)


def test_the_leader_has_no_gap_and_is_not_given_a_zero():
    rows = [_row(1, 5.0, is_you=True), _row(2, 3.0)]

    assert games_arc._gap_to_next(rows, 1) == (None, None)


def test_an_unranked_entrant_has_no_gap():
    """Day one: no close has happened, so there is no TWR to measure against.
    `standings_open` is False and the gap is absent, never 0.00."""
    rows = [_row(None, None, is_you=True)]

    assert games_arc._gap_to_next(rows, None) == (None, None)


def test_a_tie_produces_a_zero_gap_not_a_missing_one():
    """Standard competition ranking puts two entrants at rank 1; the third is
    rank 3, genuinely 0.0 behind rank 1. That zero is a measurement."""
    rows = [_row(1, 5.0), _row(1, 5.0), _row(3, 5.0, is_you=True)]

    gap, rank = games_arc._gap_to_next(rows, 3)

    assert (gap, rank) == (0.0, 1)


# ── The payload ──────────────────────────────────────────────────────────


def _live_run():
    user_id = uuid4()
    entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=1,
        now=_MARKET_OPEN,
    )
    with get_session() as s:
        s.add(PortfolioNavDailyRow(
            user_id=user_id, run_id=entry.run_id, as_of_date=_STARTS_ON,
            nav=10_000.0, cash=10_000.0, price_source="live", capital_event="open",
        ))
        for field in s.execute(select(GameFieldRow)).scalars().all():
            if field.state in ("entry_open", "locked"):
                field.state = "live"
    return user_id, entry.run_id


def test_the_payload_carries_no_downward_gap_field():
    """The fence is the ABSENCE of the number. A copy change cannot write
    "you are 0.3% from dropping a place" because nothing supplies it."""
    user_id, run_id = _live_run()

    arc = games_arc.arc_for_run(user_id, run_id)

    assert "gap_to_next_pct" in arc
    assert not [k for k in arc if "below" in k or "behind" in k or "drop" in k]


def test_the_payload_says_which_clock_each_number_runs_on():
    user_id, run_id = _live_run()

    arc = games_arc.arc_for_run(user_id, run_id)

    assert arc["standings_update"] == "daily_close"
    assert arc["phase"] in (
        games_arc.PHASE_ENTRY_OPEN, games_arc.PHASE_BELL, games_arc.PHASE_LIVE,
        games_arc.PHASE_FINAL_STRETCH, games_arc.PHASE_SETTLING,
        games_arc.PHASE_CLOSED,
    )
    assert arc["locks_at"] and arc["ends_on"]


def test_day_one_reports_standings_closed_rather_than_a_field_of_zeroes():
    user_id, run_id = _live_run()

    arc = games_arc.arc_for_run(user_id, run_id)

    assert arc["standings_open"] is False
    assert arc["your_twr_pct"] is None
    assert arc["gap_to_next_pct"] is None


def test_attribution_names_the_run_s_biggest_mover():
    user_id, run_id = _live_run()

    arc = games_arc.arc_for_run(user_id, run_id)

    assert arc["attribution"] is not None
    assert arc["attribution"]["ticker"] == "AAPL"
    assert arc["attribution"]["still_held"] is True
    assert arc["attribution"]["price_source"]


def test_a_run_that_never_traded_attributes_nothing():
    user_id = uuid4()
    entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)

    arc = games_arc.arc_for_run(user_id, entry.run_id)

    assert arc["attribution"] is None


def test_someone_else_s_run_is_not_readable():
    _owner, run_id = _live_run()

    with pytest.raises(games_arc.ArcNotAvailable):
        games_arc.arc_for_run(uuid4(), run_id)


def test_live_runs_carry_their_phase_without_a_board_scan():
    """The home screen renders one line per cadence. If the phase cost a
    field rank per line, five live runs would cost five board scans."""
    user_id, _run_id = _live_run()

    (row,) = games.list_live_runs(user_id)

    assert row["phase"] in (games_arc.PHASE_LIVE, games_arc.PHASE_FINAL_STRETCH)
    assert row["locks_at"]
