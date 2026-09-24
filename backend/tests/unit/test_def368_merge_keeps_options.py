"""DEF368 — claiming an anonymous account must not destroy option positions.

Found by CR205's §11 audit of `merge_service`, not by a report — the CR asked
for the audit precisely because a service with no `occ_symbol` awareness is
invisible to every option test.

`merge_service` moved `SimTradeRow` and the training `SimPortfolioRow` and
never touched `SimOptionLegRow` / `SimOptionTradeRow`. Two branches, two
different failures:

  1. **Adopter has no portfolio.** The portfolio row changes owner and equity
     trades are re-keyed; the option rows' own `user_id` was left pointing at
     the orphan. The legs survived (reads go by `portfolio_id`, unchanged) but
     every user-scoped option query was then wrong. Fixed by re-keying
     `user_id` — the whole portfolio (cash, holdings, options) moves as one
     unit here, so there is no invariant to guard.

  2. **Both have portfolios.** The orphan portfolio is DELETEd and
     `sim_option_legs.portfolio_id` is `ondelete="CASCADE"` — so every leg
     went with it. The user consented to a structure, saw it on the portfolio
     card CR172 shipped, claimed their account, and it was gone. No error,
     because a CASCADE is not a failure.

**MAJOR-1 (RETRO-SIM-OPTIONS round 1, U68) — the first fix for branch 2 was
itself wrong.** It re-keyed the option legs into the adopter's surviving
portfolio without their cash or their cover: a leg's collateral and net cost
were paid out of the ORPHAN's `current_cash` at open, and a covered call's
cover is the ORPHAN's `sim_holdings` row — both of which this branch's
existing rule (unchanged since before DEF368) drops along with the orphan
portfolio. Measured by the auditor: adopter total-value rose by the full
collateral with cash unchanged (phantom NAV of +$4,650 on the reproduction
below), and a covered call arrived on the adopter's book with no covering
shares — a naked short call minted by claiming an account, the one position
D3 forbids outright, reached through no floor at all.

**The fix, round 2:** options in the both-portfolios branch now follow the
SAME rule every other per-user singleton in this branch already follows —
mandate, training portfolio, holdings — keep the adopter's, drop the
orphan's. Not a new rule; DEF368's actual complaint was the silence of the
CASCADE, not the fact of the drop, so the drop is counted
(`sim_option_legs_dropped`) and logged rather than happening invisibly.

Not reachable today (`derivatives_allowed` is on 0 of 52 mandates), which is
the only reason this was not urgent — and exactly the kind of latent loss
that becomes a live incident on the day the flag is flipped.
"""

from __future__ import annotations

import datetime
from datetime import timezone
from uuid import uuid4

from sqlalchemy import select

from app.db import get_session
from app.db.models import (
    SimHoldingRow,
    SimOptionLegRow,
    SimOptionTradeRow,
    SimPortfolioRow,
    User,
)
from app.services import sim_options
from app.services.auth_service import AuthService
from app.services.merge_service import MergeService
from app.services.sim_engine import SimEngine
from app.trading_math.option_strategy import option_leg_value

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


def _add_option(
    user_id, occ="AAPL261218C00195000", *,
    quantity=1.0, avg_premium=9.10, collateral_posted=0.0,
    strategy_name="long_call", underlying="AAPL", right="call", strike=195.0,
):
    """One open leg plus its structure row, written directly — the point of
    this test is the merge, not the open path."""
    pid = _portfolio_id(user_id)
    assert pid is not None
    sid = uuid4()
    with get_session() as s:
        s.add(SimOptionTradeRow(
            id=uuid4(), user_id=user_id, portfolio_id=pid, strategy_id=sid,
            underlying=underlying, strategy_name=strategy_name,
            net_cost_at_open=avg_premium * 100.0 * quantity,
            collateral_posted=collateral_posted, opened_at=_NOW,
        ))
        s.add(SimOptionLegRow(
            id=uuid4(), user_id=user_id, portfolio_id=pid, occ_symbol=occ,
            underlying=underlying, right=right, strike=strike, expiry=_EXP,
            quantity=quantity, avg_premium=avg_premium, multiplier=100.0,
            collateral_posted=collateral_posted, strategy_id=sid,
            strategy_name=strategy_name, opened_at=_NOW, state="open",
        ))
    return sid


def _add_holding(user_id, ticker="AAPL", quantity=100.0, avg_cost=150.0):
    pid = _portfolio_id(user_id)
    assert pid is not None
    with get_session() as s:
        s.add(SimHoldingRow(
            id=uuid4(), portfolio_id=pid, ticker=ticker,
            quantity=quantity, avg_cost=avg_cost, opened_at=_NOW,
        ))


def _legs_for(user_id) -> list[SimOptionLegRow]:
    with get_session() as s:
        return list(s.execute(
            select(SimOptionLegRow).where(SimOptionLegRow.user_id == user_id)
        ).scalars().all())


def _nav_at_cost(user_id) -> float:
    """cash + Σ holdings-at-cost + Σ option-legs-at-premium — the same
    continuity the open path holds to (`sim_options.py`'s module docstring:
    opening at the mid does not change `total_value`). No live marks are
    fetched, deliberately: this is a merge-time invariant, not a pricing
    test, and every fixture above books at cost/premium already.
    """
    with get_session() as s:
        p_row = s.execute(
            select(SimPortfolioRow).where(
                SimPortfolioRow.user_id == user_id,
                SimPortfolioRow.kind == "training",
            )
        ).scalar_one_or_none()
        if p_row is None:
            return 0.0
        cash = float(p_row.current_cash)
        holdings_value = sum(
            float(h.quantity) * float(h.avg_cost)
            for h in s.execute(
                select(SimHoldingRow).where(SimHoldingRow.portfolio_id == p_row.id)
            ).scalars().all()
        )
        options_value = sum(
            option_leg_value(
                float(leg.collateral_posted), float(leg.quantity),
                float(leg.multiplier), float(leg.avg_premium),
            )
            for leg in s.execute(
                select(SimOptionLegRow).where(
                    SimOptionLegRow.portfolio_id == p_row.id,
                    SimOptionLegRow.state == "open",
                )
            ).scalars().all()
        )
        return round(cash + holdings_value + options_value, 2)


def _uncovered_short_call_shares(user_id, underlying="AAPL") -> float:
    with get_session() as s:
        p_row = s.execute(
            select(SimPortfolioRow).where(
                SimPortfolioRow.user_id == user_id,
                SimPortfolioRow.kind == "training",
            )
        ).scalar_one_or_none()
        if p_row is None:
            return 0.0
        locked = sim_options.locked_call_cover_shares(s, p_row.id, underlying)
        held = sum(
            float(h.quantity)
            for h in s.execute(
                select(SimHoldingRow).where(
                    SimHoldingRow.portfolio_id == p_row.id,
                    SimHoldingRow.ticker == underlying,
                )
            ).scalars().all()
        )
        return max(0.0, locked - held)


def test_the_adopter_keeps_the_options_when_it_has_no_portfolio_of_its_own():
    """Branch 1. The legs always survived here; what did not was their
    ownership, so a user-scoped query found nothing. The whole portfolio
    (cash, holdings, options) moves as one unit, so no invariant is at risk."""
    orphan, adopter = _make_users()
    SimEngine().ensure_portfolio(orphan.id)
    _add_option(orphan.id)

    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)

    legs = _legs_for(adopter.id)
    assert len(legs) == 1, "the adopter must own the leg after claiming"
    assert legs[0].occ_symbol == "AAPL261218C00195000"
    assert _legs_for(orphan.id) == []


def test_both_have_portfolios_drops_the_orphans_options_like_its_holdings():
    """Branch 2, corrected (MAJOR-1). Re-keying the leg alone — without its
    cash or its cover — was itself the defect; the branch's existing rule
    for holdings (keep adopter's, drop orphan's) now applies to options too."""
    orphan, adopter = _make_users()
    sim = SimEngine()
    sim.ensure_portfolio(orphan.id)
    sim.ensure_portfolio(adopter.id)
    _add_option(orphan.id)

    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)

    assert _legs_for(adopter.id) == [], "must not arrive without its cash/cover"
    assert _legs_for(orphan.id) == [], "orphan row is gone (dropped, not orphaned)"


def test_the_structure_row_is_dropped_with_its_legs_not_left_dangling():
    """A leg dropped without its structure row would be one orphan trading
    for another — the option-card query joins by `strategy_id`."""
    orphan, adopter = _make_users()
    sim = SimEngine()
    sim.ensure_portfolio(orphan.id)
    sim.ensure_portfolio(adopter.id)
    sid = _add_option(orphan.id)

    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)

    with get_session() as s:
        row = s.execute(
            select(SimOptionTradeRow).where(SimOptionTradeRow.strategy_id == sid)
        ).scalar_one_or_none()
        assert row is None, "structure row dropped alongside its legs"


def test_the_merge_reports_what_it_moved_in_branch_one():
    """A merge that names its counts while silently dropping a table is the
    same failure one layer up. Branch 1 (adopter has no portfolio) still
    moves options — this asserts that path still reports correctly."""
    orphan, adopter = _make_users()
    SimEngine().ensure_portfolio(orphan.id)
    _add_option(orphan.id)
    _add_option(orphan.id, occ="AAPL261218P00180000", right="put", strike=180.0)

    counts, _mandate_kept, _overlays = MergeService().execute(
        from_user_id=orphan.id, to_user_id=adopter.id,
    )
    assert counts["sim_option_legs"] == 2, counts
    assert counts.get("sim_option_legs_dropped", 0) == 0


def test_the_merge_reports_what_it_dropped_in_branch_two():
    """MAJOR-1's own fix — DEF368's complaint was the SILENCE of the drop,
    not the drop itself, so this asserts the count is on the record."""
    orphan, adopter = _make_users()
    sim = SimEngine()
    sim.ensure_portfolio(orphan.id)
    sim.ensure_portfolio(adopter.id)
    _add_option(orphan.id)
    _add_option(orphan.id, occ="AAPL261218P00180000", right="put", strike=180.0)

    counts, _mandate_kept, _overlays = MergeService().execute(
        from_user_id=orphan.id, to_user_id=adopter.id,
    )
    assert counts["sim_option_legs_dropped"] == 2, counts
    assert counts["sim_option_legs"] == 0, "nothing moved in this branch"


def test_a_merge_with_no_options_still_reports_zero_not_absent():
    orphan, adopter = _make_users()
    sim = SimEngine()
    sim.ensure_portfolio(orphan.id)
    sim.ensure_portfolio(adopter.id)

    counts, _mandate_kept, _overlays = MergeService().execute(
        from_user_id=orphan.id, to_user_id=adopter.id,
    )
    assert counts["sim_option_legs"] == 0, "reported as zero, not omitted"
    assert counts["sim_option_legs_dropped"] == 0, "reported as zero, not omitted"


def test_merge_never_creates_value_from_nothing_branch_two():
    """The auditor's own reproduction (MAJOR-1): orphan holds 100 AAPL plus a
    covered call, and a cash-secured MSFT put; both users already have a
    portfolio. `NAV(orphan) + NAV(adopter)` before must not be less than
    `NAV(adopter)` after — the branch is allowed to DROP value (that is the
    existing holdings rule, and it is disclosed via the counts) but must
    never MINT it. The auditor measured the old fix minting +$4,650 with
    cash unchanged; this asserts adopter NAV does not rise at all, since
    nothing was contributed by the orphan in this branch any more.
    """
    orphan, adopter = _make_users()
    sim = SimEngine()
    sim.ensure_portfolio(orphan.id)
    sim.ensure_portfolio(adopter.id)

    _add_holding(orphan.id, ticker="AAPL", quantity=100.0, avg_cost=150.0)
    # Covered call against the 100 AAPL shares above.
    _add_option(
        orphan.id, occ="AAPL261218C00195000",
        quantity=-1.0, avg_premium=9.10, collateral_posted=0.0,
        strategy_name="covered_call", underlying="AAPL", right="call", strike=195.0,
    )
    # Cash-secured MSFT put, collateral = strike x multiplier x contracts.
    _add_option(
        orphan.id, occ="MSFT261218P00050000",
        quantity=-1.0, avg_premium=2.0, collateral_posted=5000.0,
        strategy_name="cash_secured_put", underlying="MSFT", right="put", strike=50.0,
    )
    # The collateral for the CSP has to have actually left cash at open, or
    # this reproduction wouldn't match how `open_structure` books it.
    with get_session() as s:
        p_row = s.execute(
            select(SimPortfolioRow).where(
                SimPortfolioRow.user_id == orphan.id,
                SimPortfolioRow.kind == "training",
            )
        ).scalar_one()
        p_row.current_cash = round(float(p_row.current_cash) - 5000.0, 2)

    adopter_nav_before = _nav_at_cost(adopter.id)
    orphan_nav_before = _nav_at_cost(orphan.id)

    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)

    adopter_nav_after = _nav_at_cost(adopter.id)

    assert adopter_nav_after <= adopter_nav_before + 1e-6, (
        f"adopter NAV must not rise from a merge that drops the orphan's "
        f"positions: before={adopter_nav_before} after={adopter_nav_after} "
        f"(orphan carried {orphan_nav_before})"
    )
    # The auditor's own number, byte-for-byte: this reproduction's orphan NAV
    # contribution (100 AAPL @ 150 = 15000, minus the -910 short-call credit
    # netted into cash at open... the fixture writes rows directly rather
    # than through open_structure, so what matters is not the absolute
    # figure but that none of it crossed over) — asserted via the inequality
    # above, which is what actually matters: adopter NAV is untouched.
    assert adopter_nav_after == adopter_nav_before


def test_merge_never_creates_a_naked_short_call_branch_two():
    """The auditor's second finding in the same reproduction: the covered
    call arrived on the adopter's book with no covering shares, because the
    100 AAPL shares that covered it were the orphan's holding and got
    dropped while the short call got re-keyed. `locked_call_cover_shares`
    must never exceed the adopter's own held quantity after a merge — the
    one position D3 forbids outright, and it must not be reachable through
    a merge with no floor at all.
    """
    orphan, adopter = _make_users()
    sim = SimEngine()
    sim.ensure_portfolio(orphan.id)
    sim.ensure_portfolio(adopter.id)

    _add_holding(orphan.id, ticker="AAPL", quantity=100.0, avg_cost=150.0)
    _add_option(
        orphan.id, occ="AAPL261218C00195000",
        quantity=-1.0, avg_premium=9.10, collateral_posted=0.0,
        strategy_name="covered_call", underlying="AAPL", right="call", strike=195.0,
    )

    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)

    assert _uncovered_short_call_shares(adopter.id, "AAPL") == 0.0, (
        "a merge must never mint a naked short call on the adopter's book"
    )
    # Belt-and-braces: no call leg at all should have crossed over uncovered.
    assert _legs_for(adopter.id) == []
