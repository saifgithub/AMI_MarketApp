"""CR109 slice 3 — the Close, the Record, the PR board, and the public/
private serializer fence (`games_record_service.py`).

Covers implementation_plan.md §9 test matrix items 20, 33, 34, 47 and this
brief's own tests 9 and 10.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import GameEntryRow, GameFieldRow, PortfolioNavDailyRow
from app.schemas.trade import Side
from app.services import games_record_service as record_service
from app.services import games_scoring_pass as pass_module
from app.services import games_service as games

_ENTRY_OPEN_CLOSED_MARKET = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)
_MARKET_OPEN = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)
_STARTS_ON = date(2026, 8, 10)
_ENDS_ON = date(2026, 8, 14)
_AFTER_CLOSE = datetime(2026, 8, 17, 15, 0, tzinfo=timezone.utc)


def _closed_run(user_id) -> GameEntryRow:
    entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)
    with get_session() as s:
        field = s.execute(
            select(GameFieldRow).where(GameFieldRow.id == entry.field_id)
        ).scalar_one()
        field.state = "live"
    games.submit_trade(
        user_id, entry.run_id, ticker="AAPL", side=Side.BUY, quantity=5, now=_MARKET_OPEN,
    )
    with get_session() as s:
        s.add(PortfolioNavDailyRow(
            user_id=user_id, run_id=entry.run_id, as_of_date=_STARTS_ON,
            nav=10_000.0, cash=10_000.0, price_source="live", capital_event="open",
        ))
        s.add(PortfolioNavDailyRow(
            user_id=user_id, run_id=entry.run_id, as_of_date=_ENDS_ON,
            nav=10_150.0, cash=10_000.0, price_source="live", capital_event=None,
        ))
    pass_module.run_scoring_pass(now=_AFTER_CLOSE)
    with get_session() as s:
        return s.execute(
            select(GameEntryRow).where(GameEntryRow.user_id == user_id)
        ).scalar_one()


# ── The Close ──────────────────────────────────────────────────────────


def test_free_users_close_contains_rank_delta_curve_and_both_counterfactuals():
    user_id = uuid4()
    entry = _closed_run(user_id)

    payload = record_service.get_close_payload(user_id, entry.run_id, now=_AFTER_CLOSE)

    # No entitlement anywhere in this call — implementation_plan.md §6: the
    # free Close is complete on its own.
    assert "rank" in payload
    # Slice 4: the field is ranked even when it is too thin to be PLACED —
    # "1st of 1" is a fact, and `entrant_count` travels with it so the Close
    # can name the basis (§6.6's "Field of 3. Scored against the S&P 500").
    assert payload["rank"] == 1
    assert "career_points_delta" in payload
    assert payload["career_points_delta"] is not None
    assert isinstance(payload["curve"], list)
    assert len(payload["curve"]) >= 2
    assert payload["counterfactual_hold_index_pct"] is not None
    # First-picks counterfactual: present because a real trade was made.
    assert payload["counterfactual_hold_first_picks_pct"] is not None
    assert payload["beats"]["result"]["rank"] == 1
    assert payload["beats"]["insight"]["kind"] == "counterfactual"
    assert payload["beats"]["re_entry"] is not None
    assert payload["beats"]["re_entry"]["cadence"] == "week"
    # No post-mortem field anywhere — it's a later slice, not built here.
    assert "post_mortem" not in payload
    assert "post_mortem" not in payload["debrief"]


def test_close_404_for_unknown_run_409_for_a_run_not_yet_closed():
    user_id = uuid4()
    with pytest.raises(record_service.RunNotFoundError):
        record_service.get_close_payload(user_id, uuid4())

    live_entry = games.enter_field(user_id, now=_ENTRY_OPEN_CLOSED_MARKET)
    with pytest.raises(record_service.RunNotClosedError):
        record_service.get_close_payload(user_id, live_entry.run_id)


# ── The Record ─────────────────────────────────────────────────────────


def test_record_renders_for_a_user_with_zero_finished_runs():
    user_id = uuid4()
    record = record_service.get_record(user_id)
    assert record["career_points_net"] == 0
    assert record["forfeit_count"] == 0
    assert record["finished_count"] == 0
    assert record["void_count"] == 0
    assert record["run_count"] == 0
    assert record["run_history"] == []


def test_record_reflects_a_finished_run():
    user_id = uuid4()
    entry = _closed_run(user_id)
    record = record_service.get_record(user_id)
    assert record["finished_count"] == 1
    assert record["run_count"] == 1
    assert record["run_history"][0]["run_id"] == str(entry.run_id)
    assert record["career_points_net"] >= 0  # clamped at write — never negative


# ── The PR board — works at n=1 ───────────────────────────────────────


def test_pr_board_works_at_n_1():
    user_id = uuid4()
    entry = _closed_run(user_id)

    prs = record_service.get_personal_records(user_id)

    assert prs["has_any_finished_runs"] is True
    assert prs["best_weekly_twr"]["entry_id"] == str(entry.id)
    assert prs["best_alpha"]["entry_id"] == str(entry.id)
    assert prs["best_drawdown_control"]["entry_id"] == str(entry.id)
    assert prs["longest_hold_days"]["entry_id"] == str(entry.id)
    assert prs["longest_finish_streak"] == {"count": 1, "entry_id": str(entry.id)}


def test_pr_board_empty_for_a_user_with_no_runs():
    user_id = uuid4()
    prs = record_service.get_personal_records(user_id)
    assert prs["has_any_finished_runs"] is False
    assert prs["best_weekly_twr"] is None
    assert prs["best_alpha"] is None
    assert prs["best_drawdown_control"] is None
    assert prs["longest_hold_days"] is None
    assert prs["longest_finish_streak"] is None


# ── The serializer fence — private mirrors never leak into a public/board
# payload (assert at the serializer, not the widget) ─────────────────────


def test_public_serializer_excludes_every_private_mirror_key():
    user_id = uuid4()
    entry_row = _closed_run(user_id)
    with get_session() as s:
        entry = s.execute(
            select(GameEntryRow).where(GameEntryRow.id == entry_row.id)
        ).scalar_one()
        field = s.execute(
            select(GameFieldRow).where(GameFieldRow.id == entry.field_id)
        ).scalar_one()
        public = record_service._entry_public_fields(entry, field)
        private = record_service._entry_private_fields(entry)

    assert set(public.keys()).isdisjoint(record_service.PRIVATE_MIRROR_KEYS)
    # Sanity — the private-field function DOES carry them (so the fence is
    # testing an actual exclusion, not an accidentally-empty set).
    assert set(private.keys()) == record_service.PRIVATE_MIRROR_KEYS
    assert public["final_twr_pct"] is not None
    assert public["scoring_basis"] == "benchmark"


def test_close_payload_carries_the_mirrors_but_public_fields_never_would():
    """The Close IS self-facing, so it legitimately carries every private
    mirror — this just cross-checks that what the Close shows is exactly
    what `_entry_private_fields` promises, keeping the two in lockstep."""
    user_id = uuid4()
    entry = _closed_run(user_id)
    payload = record_service.get_close_payload(user_id, entry.run_id, now=_AFTER_CLOSE)
    for key in record_service.PRIVATE_MIRROR_KEYS:
        assert key in payload
