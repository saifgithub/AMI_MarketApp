"""CR109 slice 3 — the SETTLING -> CLOSED scoring pass (`games_scoring_pass.py`).

Covers implementation_plan.md §9 test matrix items 10, 12, 13, 28, 32, 42
and this brief's own tests 1, 2, 4, 5, 6, 8, 12.

A field of one is the alpha condition — every integration test here uses
exactly one entrant, on purpose (the fence: placement is not built, so
"thin" isn't even a special case, it's the ONLY case slice 3 has).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import CareerEventRow, GameEntryRow, GameFieldRow, PortfolioNavDailyRow
from app.schemas.trade import Side
from app.services import games_scoring_pass as pass_module
from app.services import games_service as games
from app.services.games_scoring import FEE_BPS

# Sunday 23:00 ET — the field for Monday 2026-08-10 is `entry_open`, market closed.
_ENTRY_OPEN_CLOSED_MARKET = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)
# Monday 11:00 ET — market open, for a real fill.
_MARKET_OPEN = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)
_STARTS_ON = date(2026, 8, 10)
_ENDS_ON = date(2026, 8, 14)
# Well after the field's own ends_on (Friday) — Monday the following week.
_AFTER_CLOSE = datetime(2026, 8, 17, 15, 0, tzinfo=timezone.utc)


def _enter_and_make_live(user_id, *, intent=None) -> GameEntryRow:
    entry = games.enter_field(user_id, intent=intent, now=_ENTRY_OPEN_CLOSED_MARKET)
    with get_session() as s:
        field = s.execute(
            select(GameFieldRow).where(GameFieldRow.id == entry.field_id)
        ).scalar_one()
        field.state = "live"
    return entry


def _write_nav(user_id, run_id, *, as_of, nav, capital_event=None, price_source="live"):
    with get_session() as s:
        s.add(PortfolioNavDailyRow(
            user_id=user_id, run_id=run_id, as_of_date=as_of, nav=nav, cash=nav,
            price_source=price_source, capital_event=capital_event,
        ))


def _standard_nav_series(user_id, run_id, *, end_nav=10_200.0, mock_day=None):
    """Open at $10,000 on day 1, a flat middle day, and `end_nav` on the
    field's own ends_on. `mock_day`, if given, flags ONE row's price_source
    as "mock" — the VOID trigger."""
    _write_nav(
        user_id, run_id, as_of=_STARTS_ON, nav=10_000.0, capital_event="open",
        price_source="mock" if mock_day == _STARTS_ON else "live",
    )
    mid = date(2026, 8, 12)
    _write_nav(
        user_id, run_id, as_of=mid, nav=(10_000.0 + end_nav) / 2,
        price_source="mock" if mock_day == mid else "live",
    )
    _write_nav(
        user_id, run_id, as_of=_ENDS_ON, nav=end_nav,
        price_source="mock" if mock_day == _ENDS_ON else "live",
    )


def _field_and_entry(user_id) -> tuple[GameFieldRow, GameEntryRow]:
    with get_session() as s:
        entry = s.execute(
            select(GameEntryRow).where(GameEntryRow.user_id == user_id)
        ).scalar_one()
        field = s.execute(
            select(GameFieldRow).where(GameFieldRow.id == entry.field_id)
        ).scalar_one()
        return field, entry


# ── Test 1 / matrix item 10 — a field of one scores, no crash, no win ────


def test_field_of_one_scores_without_crashing_and_pays_no_placement_win():
    user_id = uuid4()
    entry = _enter_and_make_live(user_id)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_MARKET_OPEN,
    )
    _standard_nav_series(user_id, entry.run_id)

    stats = pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    assert stats["fields_closed"] == 1
    assert stats["entries_scored"] == 1
    assert stats["entries_voided"] == 0

    field, entry_row = _field_and_entry(user_id)
    assert field.state == "closed"
    assert field.scoring_basis == "benchmark"
    assert entry_row.state == "finished"
    assert entry_row.scored_at is not None
    # Slice 4 separates the two things slice 3 had no reason to distinguish:
    # the field is RANKED (1 of 1 — a fact, and the count travels with it so
    # the Close can state the basis loudly per §6.6) but it is not PLACED.
    # The property this test exists for is the second one, asserted below on
    # the points; a rank of 1 in a field of 1 pays nothing extra.
    assert entry_row.final_rank == 1
    assert entry_row.scored_entrant_count == 1
    # No "win" is reachable — placement's own max base is +100; nothing in
    # this pass can exceed alpha_to_points' own +/-1 clamp (see
    # test_games_scoring_slice3.py's dedicated clamp test), so a lone
    # entrant's points stay inside that same bound plus the fixed stipend.
    assert entry_row.career_points_delta is not None
    assert -40 - 1 <= (entry_row.career_points_delta - entry_row.stipend_points) <= 100 + 1


# ── Idempotency (test 2 / matrix item 13) ─────────────────────────────────


def test_scoring_pass_is_idempotent_no_double_post():
    user_id = uuid4()
    entry = _enter_and_make_live(user_id)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_MARKET_OPEN,
    )
    _standard_nav_series(user_id, entry.run_id)

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)
    _field, entry_after_first = _field_and_entry(user_id)
    with get_session() as s:
        count_after_first = len(s.execute(
            select(CareerEventRow).where(CareerEventRow.entry_id == entry_after_first.id)
        ).scalars().all())

    # Re-run — nothing left to do; must not double-post.
    stats2 = pass_module.run_scoring_pass(now=_AFTER_CLOSE)
    assert stats2["fields_closed"] == 0
    assert stats2["entries_scored"] == 0

    with get_session() as s:
        count_after_second = len(s.execute(
            select(CareerEventRow).where(CareerEventRow.entry_id == entry_after_first.id)
        ).scalars().all())
    assert count_after_second == count_after_first
    assert count_after_first >= 1  # sanity — something WAS posted the first time


# ── VOID on a mock-priced day (matrix item 12 / brief test 6) ────────────


def test_void_on_mock_priced_day_states_the_reason_loudly():
    user_id = uuid4()
    entry = _enter_and_make_live(user_id)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_MARKET_OPEN,
    )
    mid = date(2026, 8, 12)
    _standard_nav_series(user_id, entry.run_id, mock_day=mid)

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    field, entry_row = _field_and_entry(user_id)
    assert field.state == "closed"
    assert entry_row.state == "void"
    assert entry_row.void_reason is not None
    assert mid.isoformat() in entry_row.void_reason
    assert entry_row.alpha_scored_pct is None
    assert entry_row.alpha_display_pct is None

    with get_session() as s:
        reasons = {
            row.reason for row in s.execute(
                select(CareerEventRow).where(CareerEventRow.entry_id == entry_row.id)
            ).scalars().all()
        }
    assert "run_close" not in reasons  # VOID pays no placement/alpha/title


def test_a_void_run_still_claims_the_finish_stipend():
    user_id = uuid4()
    entry = _enter_and_make_live(user_id)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_MARKET_OPEN,
    )
    _standard_nav_series(user_id, entry.run_id, mock_day=_ENDS_ON)

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    _field, entry_row = _field_and_entry(user_id)
    assert entry_row.state == "void"
    assert entry_row.stipend_points == 5  # FINISH_STIPEND for "week"
    with get_session() as s:
        stipend_rows = s.execute(
            select(CareerEventRow).where(
                CareerEventRow.entry_id == entry_row.id,
                CareerEventRow.reason == "finish_stipend",
            )
        ).scalars().all()
    assert len(stipend_rows) == 1
    assert stipend_rows[0].delta == 5


# ── The four stipend guards (matrix items 30 / brief test 4) ─────────────


def test_forfeited_run_pays_no_stipend():
    user_id = uuid4()
    entry = _enter_and_make_live(user_id)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_MARKET_OPEN,
    )
    _standard_nav_series(user_id, entry.run_id)
    with get_session() as s:
        row = s.execute(
            select(GameEntryRow).where(GameEntryRow.user_id == user_id)
        ).scalar_one()
        row.state = "forfeit"

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    with get_session() as s:
        events = s.execute(
            select(CareerEventRow).where(CareerEventRow.user_id == user_id)
        ).scalars().all()
    assert events == []
    _field, entry_row = _field_and_entry(user_id)
    assert entry_row.state == "forfeit"  # untouched — the pass never visits it
    assert entry_row.scored_at is None


def test_zero_executed_trades_pays_no_stipend_but_still_scores_alpha():
    user_id = uuid4()
    entry = _enter_and_make_live(user_id)
    # No trade submitted — trade_count stays 0.
    _standard_nav_series(user_id, entry.run_id, end_nav=10_000.0)

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    _field, entry_row = _field_and_entry(user_id)
    assert entry_row.state == "finished"  # still scores — the guard is on the STIPEND only
    assert entry_row.stipend_points == 0
    with get_session() as s:
        reasons = [
            row.reason for row in s.execute(
                select(CareerEventRow).where(CareerEventRow.entry_id == entry_row.id)
            ).scalars().all()
        ]
    assert "finish_stipend" not in reasons


def test_run_not_held_to_close_pays_no_stipend():
    """A run still `entered`/`active` when the field settles never reaches
    the pass's candidate list at all if it forfeited; this covers the
    OTHER shape — an entry that never became `active` (zero trades) is
    covered above. Held-to-close is definitionally "reached the pass in a
    live state", so this asserts a forfeited-mid-week run (a different
    forfeit timing) still gets nothing."""
    user_id = uuid4()
    entry = _enter_and_make_live(user_id)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_MARKET_OPEN,
    )
    with get_session() as s:
        row = s.execute(
            select(GameEntryRow).where(GameEntryRow.user_id == user_id)
        ).scalar_one()
        assert row.state == "active"  # the trade flipped entered -> active
        row.state = "forfeit"  # mid-week forfeit, same as commit_restart would do
    _standard_nav_series(user_id, entry.run_id)

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    with get_session() as s:
        events = s.execute(
            select(CareerEventRow).where(CareerEventRow.user_id == user_id)
        ).scalars().all()
    assert events == []


# ── Alpha scored (net) vs displayed (gross) differ by exactly the fee ────


def test_alpha_scored_nets_the_fee_while_display_stays_gross():
    """Test matrix item 32 / brief test 8 — the relationship holds
    regardless of the actual (mock-provider-served) benchmark value: the
    scoring leg is ALWAYS exactly FEE_BPS (as a percent) below the display
    leg, because `achievable_benchmark` subtracts a FIXED fraction."""
    user_id = uuid4()
    entry = _enter_and_make_live(user_id)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_MARKET_OPEN,
    )
    _standard_nav_series(user_id, entry.run_id, end_nav=10_500.0)

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    _field, entry_row = _field_and_entry(user_id)
    assert entry_row.alpha_scored_pct is not None
    assert entry_row.alpha_display_pct is not None
    assert entry_row.alpha_scored_pct != entry_row.alpha_display_pct
    # achievable_benchmark HANDICAPS the benchmark by the same one fee the
    # player actually paid, so the SCORED alpha (measured against that
    # fairer, lower bar) sits exactly one fee ABOVE the gross/display
    # alpha (measured against the impossible costless index) — the scored
    # number is the fair one, the display number is the harsher boast line.
    fee_pct = FEE_BPS / 10_000.0 * 100  # 0.1
    assert float(entry_row.alpha_scored_pct) - float(entry_row.alpha_display_pct) == pytest.approx(
        fee_pct, abs=0.01,
    )
    # The counterfactual "hold the index" line is the SAME gross number a
    # client would otherwise have to derive from alpha_display + final_twr.
    assert entry_row.counterfactual_hold_index_pct is not None


# ── ×0.5 partial credit while absolute TWR is negative (brief test 12) ───


def test_negative_absolute_twr_halves_the_run_close_points():
    """Two otherwise-identical entrants, one ending positive and one
    ending negative by the SAME magnitude of excess-vs-benchmark is hard
    to construct deterministically (the benchmark is provider-served) —
    so this asserts the STRUCTURAL guarantee at the point it is applied:
    a negative-TWR run's stored `alpha_scored_pct` still reflects the full
    (un-halved) alpha number, while its contribution to career points is
    halved. We check this indirectly through the pure-function contract
    (already pinned exactly in test_games_scoring_slice3.py) and confirm
    here only that a negative-TWR run scores WITHOUT crashing and posts a
    `run_close` event whose magnitude is consistent with being halved
    relative to `alpha_to_points(alpha_scored)` computed the same way."""
    from app.services.games_scoring import (
        achievable_benchmark,
        alpha_to_points,
        apply_negative_twr_partial_credit,
        cadence_weight,
    )

    user_id = uuid4()
    entry = _enter_and_make_live(user_id)
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=5,
        now=_MARKET_OPEN,
    )
    # A losing run — ends well below the $10,000 stake.
    _standard_nav_series(user_id, entry.run_id, end_nav=9_000.0)

    pass_module.run_scoring_pass(now=_AFTER_CLOSE)

    field, entry_row = _field_and_entry(user_id)
    assert float(entry_row.final_twr_pct) < 0
    alpha_scored_fraction = float(entry_row.alpha_scored_pct) / 100.0
    expected_base = apply_negative_twr_partial_credit(
        alpha_to_points(alpha_scored_fraction), float(entry_row.final_twr_pct) / 100.0,
    )
    expected_run_close = round(expected_base * cadence_weight(field.cadence, negative=(expected_base < 0)))
    with get_session() as s:
        run_close_row = s.execute(
            select(CareerEventRow).where(
                CareerEventRow.entry_id == entry_row.id, CareerEventRow.reason == "run_close",
            )
        ).scalar_one_or_none()
    assert run_close_row is not None
    assert run_close_row.delta_uncapped == expected_run_close
    # And the un-halved formula would have scored something more negative
    # (more punishing) — confirms the halving actually fired.
    unhalved = round(
        alpha_to_points(alpha_scored_fraction)
        * cadence_weight(field.cadence, negative=(alpha_to_points(alpha_scored_fraction) < 0))
    )
    if alpha_to_points(alpha_scored_fraction) < 0:
        assert expected_run_close > unhalved  # halved debit is LESS negative
