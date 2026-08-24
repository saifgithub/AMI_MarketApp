"""DEF368 — claiming an anonymous account must not destroy option positions.

Found by CR205's §11 audit of `merge_service`, not by a report — the CR asked
for the audit precisely because a service with no `occ_symbol` awareness is
invisible to every option test.

`merge_service` moved `SimTradeRow` and the training `SimPortfolioRow` and
never touched `SimOptionLegRow` / `SimOptionTradeRow`. Two branches, two
different failures, and the second is data loss:

  1. **Adopter has no portfolio.** The portfolio row changes owner and equity
     trades are re-keyed; the option rows' own `user_id` was left pointing at
     the orphan. The legs survived (reads go by `portfolio_id`, unchanged) but
     every user-scoped option query was then wrong.

  2. **Both have portfolios.** The orphan portfolio is DELETEd, and
     `sim_option_legs.portfolio_id` is `ondelete="CASCADE"` — so every leg
     went with it. The user consented to a structure, saw it on the portfolio
     card CR172 shipped, claimed their account, and it was gone. No error,
     because a CASCADE is not a failure.

Not reachable today (`derivatives_allowed` is on 0 of 42 mandates), which is
the only reason it was not urgent — and exactly the kind of latent loss that
becomes a live incident on the day the flag is flipped.
"""

from __future__ import annotations

import datetime
from datetime import timezone
from uuid import uuid4

from sqlalchemy import select

from app.db import get_session
from app.db.models import (
    SimOptionLegRow,
    SimOptionTradeRow,
    SimPortfolioRow,
    User,
)
from app.services.auth_service import AuthService
from app.services.merge_service import MergeService
from app.services.sim_engine import SimEngine

_NOW = datetime.datetime(2026, 8, 25, 14, 0, tzinfo=timezone.utc)
_EXP = datetime.date(2026, 12, 18)


def _make_users() -> tuple[User, User]:
    auth = AuthService()
    orphan_au, _, _ = auth.ensure_anonymous(device_user_id=None)
    adopter_au, _, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        orphan = s.execute(select(User).where(User.id == orphan_au.id)).scalar_one()
        adopter = s.execute(select(User).where(User.id == adopter_au.id)).scalar_one()
        adopter.email = "adopter@example.com"
        adopter.is_anonymous = False
        adopter.claimed_at = _NOW
        return orphan, adopter


def _portfolio_id(user_id):
    with get_session() as s:
        row = s.execute(
            select(SimPortfolioRow).where(
                SimPortfolioRow.user_id == user_id,
                SimPortfolioRow.kind == "training",
            )
        ).scalar_one_or_none()
        return row.id if row else None


def _add_option(user_id, occ="AAPL261218C00195000"):
    """One open leg plus its structure row, written directly — the point of
    this test is the merge, not the open path."""
    pid = _portfolio_id(user_id)
    assert pid is not None
    sid = uuid4()
    with get_session() as s:
        s.add(SimOptionTradeRow(
            id=uuid4(), user_id=user_id, portfolio_id=pid, strategy_id=sid,
            underlying="AAPL", strategy_name="long_call",
            net_cost_at_open=910.0, collateral_posted=0.0, opened_at=_NOW,
        ))
        s.add(SimOptionLegRow(
            id=uuid4(), user_id=user_id, portfolio_id=pid, occ_symbol=occ,
            underlying="AAPL", right="call", strike=195.0, expiry=_EXP,
            quantity=1.0, avg_premium=9.10, multiplier=100.0,
            collateral_posted=0.0, strategy_id=sid,
            strategy_name="long_call", opened_at=_NOW, state="open",
        ))
    return sid


def _legs_for(user_id) -> list[SimOptionLegRow]:
    with get_session() as s:
        return list(s.execute(
            select(SimOptionLegRow).where(SimOptionLegRow.user_id == user_id)
        ).scalars().all())


def test_the_adopter_keeps_the_options_when_it_has_no_portfolio_of_its_own():
    """Branch 1. The legs always survived here; what did not was their
    ownership, so a user-scoped query found nothing."""
    orphan, adopter = _make_users()
    SimEngine().ensure_portfolio(orphan.id)
    _add_option(orphan.id)

    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)

    legs = _legs_for(adopter.id)
    assert len(legs) == 1, "the adopter must own the leg after claiming"
    assert legs[0].occ_symbol == "AAPL261218C00195000"
    assert _legs_for(orphan.id) == []


def test_the_adopter_keeps_the_options_when_both_have_portfolios():
    """Branch 2 — the destructive one. The orphan portfolio is deleted, and
    the leg's CASCADE took it with it."""
    orphan, adopter = _make_users()
    sim = SimEngine()
    sim.ensure_portfolio(orphan.id)
    sim.ensure_portfolio(adopter.id)
    target_pid = _portfolio_id(adopter.id)
    _add_option(orphan.id)

    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)

    legs = _legs_for(adopter.id)
    assert len(legs) == 1, "the leg must be adopted, not cascade-deleted"
    assert legs[0].portfolio_id == target_pid, "re-keyed into the surviving portfolio"


def test_the_structure_row_moves_with_its_legs():
    """A leg whose `strategy_id` points at a deleted structure is an orphan of
    a different kind — the card groups by structure."""
    orphan, adopter = _make_users()
    sim = SimEngine()
    sim.ensure_portfolio(orphan.id)
    sim.ensure_portfolio(adopter.id)
    sid = _add_option(orphan.id)

    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)

    with get_session() as s:
        row = s.execute(
            select(SimOptionTradeRow).where(SimOptionTradeRow.strategy_id == sid)
        ).scalar_one()
        assert row.user_id == adopter.id


def test_the_merge_reports_what_it_moved():
    """A merge that names its counts while silently dropping a table is the
    same failure one layer up."""
    orphan, adopter = _make_users()
    sim = SimEngine()
    sim.ensure_portfolio(orphan.id)
    sim.ensure_portfolio(adopter.id)
    _add_option(orphan.id)
    _add_option(orphan.id, occ="AAPL261218P00180000")

    counts, _mandate_kept, _overlays = MergeService().execute(
        from_user_id=orphan.id, to_user_id=adopter.id,
    )
    assert counts["sim_option_legs"] == 2, counts


def test_a_merge_with_no_options_still_reports_zero_not_absent():
    orphan, adopter = _make_users()
    sim = SimEngine()
    sim.ensure_portfolio(orphan.id)
    sim.ensure_portfolio(adopter.id)

    counts, _mandate_kept, _overlays = MergeService().execute(
        from_user_id=orphan.id, to_user_id=adopter.id,
    )
    assert counts["sim_option_legs"] == 0, "reported as zero, not omitted"
