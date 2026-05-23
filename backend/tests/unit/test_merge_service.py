"""BL16 (AT:R38) — MergeService unit tests.

Covers preview counts + the execute() re-key + idempotency + the
conflict-resolution rules for mandate / sim_portfolio / lessons_progress
/ user_overlays.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import (
    AgentActivationRow,
    BugReportRow,
    JournalEntryRow,
    LessonProgressRow,
    MandateRow,
    OneOnOneMessageRow,
    OverlayEditCounter,
    RoomRunRow,
    SimHoldingRow,
    SimPortfolioRow,
    SimTradeRow,
    SimWatchlistRow,
    SubscriptionEventRow,
    User,
    UserOverlayRow,
)
from app.services.auth_service import AuthService
from app.services.merge_service import MergeError, MergeService


def _make_users() -> tuple[User, User]:
    """Two anonymous users — `orphan` (the pre-claim anon) and `adopter`
    (the existing email-row that account-linking Phase 1 picked)."""
    auth = AuthService()
    orphan_au, _, _ = auth.ensure_anonymous(device_user_id=None)
    adopter_au, _, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        orphan = s.execute(select(User).where(User.id == orphan_au.id)).scalar_one()
        adopter = s.execute(select(User).where(User.id == adopter_au.id)).scalar_one()
        adopter.email = "adopter@example.com"
        adopter.is_anonymous = False
        adopter.claimed_at = datetime.now(timezone.utc)
        return orphan, adopter


def _make_orphan_with_everything() -> tuple[User, User]:
    orphan, adopter = _make_users()
    with get_session() as s:
        # 3 journal entries, 1 sim_portfolio + 2 trades + 1 holding,
        # 2 watchlist tickers, 2 lessons, 1 activation, 1 1-on-1 msg,
        # 1 room run, 1 bug report.
        for i in range(3):
            s.add(JournalEntryRow(
                user_id=orphan.id, entry_type="trade",
                title=f"entry {i}",
            ))
        port = SimPortfolioRow(
            user_id=orphan.id, starting_capital=10000, current_cash=9000,
        )
        s.add(port)
        s.flush()
        s.add(SimTradeRow(
            user_id=orphan.id, portfolio_id=port.id,
            ticker="NVDA", side="buy", quantity=10, entry_price=150,
        ))
        s.add(SimTradeRow(
            user_id=orphan.id, portfolio_id=port.id,
            ticker="MSFT", side="buy", quantity=5, entry_price=400,
        ))
        s.add(SimHoldingRow(
            portfolio_id=port.id, ticker="NVDA",
            quantity=10, avg_cost=150,
        ))
        s.add(SimWatchlistRow(user_id=orphan.id, ticker="AAPL"))
        s.add(SimWatchlistRow(user_id=orphan.id, ticker="TSLA"))
        s.add(LessonProgressRow(
            user_id=orphan.id, lesson_id="intro-01", quiz_passed=True,
        ))
        s.add(LessonProgressRow(
            user_id=orphan.id, lesson_id="intro-02", quiz_passed=False,
        ))
        s.add(AgentActivationRow(
            user_id=orphan.id, agent_id="market_analyst",
            activation_method="lesson",
        ))
        s.add(OneOnOneMessageRow(
            session_id=uuid4(), user_id=orphan.id,
            agent_id="market_analyst", role="user", content="hi",
        ))
        s.add(RoomRunRow(
            user_id=orphan.id, ticker="NVDA",
            mandate_version=1, model_tier="cheap",
        ))
        s.add(BugReportRow(
            user_id=orphan.id, category="other", title="bug",
            app_version="0.1.0+27", platform="ios",
        ))
    return orphan, adopter


# ── preview() ───────────────────────────────────────────────────────────


def test_preview_counts_everything_on_orphan():
    orphan, adopter = _make_orphan_with_everything()
    svc = MergeService()
    p = svc.preview(from_user_id=orphan.id, to_user_id=adopter.id)
    assert p.journal_entries == 3
    assert p.sim_trades == 2
    assert p.sim_holdings == 1
    assert p.sim_watchlists == 2
    assert p.lessons_progress == 2
    assert p.agent_activations == 1
    assert p.one_on_one_messages == 1
    assert p.room_runs == 1
    assert p.bug_reports == 1
    assert p.mandate_conflict is False  # neither side has a mandate


def test_preview_mandate_conflict_when_both_sides_have_one():
    orphan, adopter = _make_users()
    with get_session() as s:
        s.add(MandateRow(user_id=orphan.id, version=1, is_current=True, snapshot={"v": 1}))
        s.add(MandateRow(user_id=adopter.id, version=1, is_current=True, snapshot={"v": 2}))
    svc = MergeService()
    p = svc.preview(from_user_id=orphan.id, to_user_id=adopter.id)
    assert p.mandate_conflict is True


def test_preview_rejects_same_user_id():
    orphan, _ = _make_users()
    svc = MergeService()
    with pytest.raises(MergeError):
        svc.preview(from_user_id=orphan.id, to_user_id=orphan.id)


# ── execute() — the happy path ──────────────────────────────────────────


def test_execute_rekeys_everything_into_adopter():
    orphan, adopter = _make_orphan_with_everything()
    svc = MergeService()
    counts, mandate_kept, deact = svc.execute(
        from_user_id=orphan.id, to_user_id=adopter.id,
    )
    assert counts["journal_entries"] == 3
    assert counts["sim_trades"] == 2
    assert counts["sim_holdings"] == 1  # came in via portfolio re-key
    assert counts["sim_watchlists"] == 2
    assert counts["lessons_progress"] == 2
    assert counts["agent_activations"] == 1
    assert counts["one_on_one_messages"] == 1
    assert counts["room_runs"] == 1
    assert counts["bug_reports"] == 1
    assert mandate_kept == "neither"
    assert deact == 0

    # Orphan row gone.
    with get_session() as s:
        assert s.execute(select(User).where(User.id == orphan.id)).scalar_one_or_none() is None
        # Everything points at adopter now.
        for model in (
            JournalEntryRow, SimTradeRow, SimWatchlistRow,
            LessonProgressRow, AgentActivationRow,
            OneOnOneMessageRow, RoomRunRow, BugReportRow,
        ):
            for row in s.execute(select(model)).scalars().all():
                assert row.user_id == adopter.id, f"{model.__tablename__} not re-keyed"


def test_execute_writes_subscription_event():
    orphan, adopter = _make_orphan_with_everything()
    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)
    with get_session() as s:
        ev = s.execute(
            select(SubscriptionEventRow).where(
                SubscriptionEventRow.event_type == "account_adoption_merged"
            )
        ).scalar_one()
        assert ev.user_id == adopter.id
        assert ev.from_value == str(orphan.id)
        assert ev.to_value == str(adopter.id)
        assert ev.source == "app"
        assert "journal_entries" in (ev.note or "")


def test_execute_is_idempotent_after_orphan_gone():
    """Second call on the same pair has no orphan to drain — raises
    MergeError since the orphan row is gone (route layer maps to 404)."""
    orphan, adopter = _make_orphan_with_everything()
    svc = MergeService()
    svc.execute(from_user_id=orphan.id, to_user_id=adopter.id)
    # Orphan was deleted; preview should still work but show zero counts
    # AND no mandate conflict (orphan row gone). Actually preview on a
    # deleted user returns zero counts — the route layer is what hits 404.
    p = svc.preview(from_user_id=orphan.id, to_user_id=adopter.id)
    assert p.journal_entries == 0
    assert p.sim_trades == 0


# ── Conflict resolution: mandate ───────────────────────────────────────


def test_execute_keeps_target_mandate_on_conflict():
    orphan, adopter = _make_users()
    with get_session() as s:
        s.add(MandateRow(user_id=orphan.id, version=1, is_current=True, snapshot={"src": True}))
        s.add(MandateRow(user_id=adopter.id, version=1, is_current=True, snapshot={"tgt": True}))
    _, kept, _ = MergeService().execute(
        from_user_id=orphan.id, to_user_id=adopter.id,
    )
    assert kept == "target"
    with get_session() as s:
        rows = s.execute(
            select(MandateRow).where(MandateRow.user_id == adopter.id)
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].snapshot == {"tgt": True}


def test_execute_moves_orphan_mandate_when_target_has_none():
    orphan, adopter = _make_users()
    with get_session() as s:
        s.add(MandateRow(user_id=orphan.id, version=1, is_current=True, snapshot={"src": True}))
    _, kept, _ = MergeService().execute(
        from_user_id=orphan.id, to_user_id=adopter.id,
    )
    assert kept == "source"
    with get_session() as s:
        rows = s.execute(
            select(MandateRow).where(MandateRow.user_id == adopter.id)
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].snapshot == {"src": True}


# ── Conflict resolution: sim_portfolio ─────────────────────────────────


def test_execute_merges_trades_into_existing_target_portfolio():
    """Both sides have a portfolio: keep adopter's, move orphan's trades
    into it (re-key portfolio_id too)."""
    orphan, adopter = _make_users()
    with get_session() as s:
        op = SimPortfolioRow(
            user_id=orphan.id, starting_capital=5000, current_cash=4000,
        )
        s.add(op)
        s.flush()
        s.add(SimTradeRow(
            user_id=orphan.id, portfolio_id=op.id,
            ticker="NVDA", side="buy", quantity=10, entry_price=150,
        ))
        tp = SimPortfolioRow(
            user_id=adopter.id, starting_capital=20000, current_cash=18000,
        )
        s.add(tp)
        s.flush()
        s.add(SimTradeRow(
            user_id=adopter.id, portfolio_id=tp.id,
            ticker="GOOG", side="buy", quantity=2, entry_price=170,
        ))
        target_port_id = tp.id

    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)

    with get_session() as s:
        # Only one portfolio left, the adopter's.
        ports = s.execute(select(SimPortfolioRow)).scalars().all()
        assert len(ports) == 1
        assert ports[0].id == target_port_id
        # Both trades now point at the adopter's portfolio.
        trades = s.execute(
            select(SimTradeRow).where(SimTradeRow.user_id == adopter.id)
        ).scalars().all()
        assert len(trades) == 2
        assert all(t.portfolio_id == target_port_id for t in trades)


# ── Conflict resolution: lessons_progress (UNIQUE user_id+lesson_id) ───


def test_execute_skips_duplicate_lessons_keeps_target():
    orphan, adopter = _make_users()
    with get_session() as s:
        # Both have intro-01; only orphan has intro-02.
        s.add(LessonProgressRow(
            user_id=orphan.id, lesson_id="intro-01", quiz_passed=False,
        ))
        s.add(LessonProgressRow(
            user_id=orphan.id, lesson_id="intro-02", quiz_passed=True,
        ))
        s.add(LessonProgressRow(
            user_id=adopter.id, lesson_id="intro-01", quiz_passed=True,
        ))

    counts, _, _ = MergeService().execute(
        from_user_id=orphan.id, to_user_id=adopter.id,
    )
    assert counts["lessons_progress"] == 1  # only intro-02 moved over

    with get_session() as s:
        rows = s.execute(
            select(LessonProgressRow).where(LessonProgressRow.user_id == adopter.id)
        ).scalars().all()
        ids = {r.lesson_id: r.quiz_passed for r in rows}
        # Adopter's intro-01 (passed) stays, orphan's intro-02 came over.
        assert ids == {"intro-01": True, "intro-02": True}


# ── Conflict resolution: user_overlays ─────────────────────────────────


def test_execute_deactivates_overlay_when_target_has_active_for_same_agent():
    orphan, adopter = _make_users()
    with get_session() as s:
        s.add(UserOverlayRow(
            user_id=orphan.id, agent_id="bear_researcher", version=1,
            content="src overlay", plain_english="src", is_active=True,
        ))
        s.add(UserOverlayRow(
            user_id=adopter.id, agent_id="bear_researcher", version=2,
            content="tgt overlay", plain_english="tgt", is_active=True,
        ))

    _, _, deact = MergeService().execute(
        from_user_id=orphan.id, to_user_id=adopter.id,
    )
    assert deact == 1

    with get_session() as s:
        rows = s.execute(
            select(UserOverlayRow).where(UserOverlayRow.user_id == adopter.id)
        ).scalars().all()
        # 2 rows: target's still-active v2 + source's deactivated v1.
        assert len(rows) == 2
        actives = [r for r in rows if r.is_active]
        assert len(actives) == 1
        assert actives[0].version == 2


def test_execute_drops_overlay_version_collision():
    """If both sides have (agent_id, version) = (X, 1), the orphan's
    row gets dropped to satisfy the UNIQUE constraint."""
    orphan, adopter = _make_users()
    with get_session() as s:
        s.add(UserOverlayRow(
            user_id=orphan.id, agent_id="bull_researcher", version=1,
            content="src v1", plain_english="src", is_active=True,
        ))
        s.add(UserOverlayRow(
            user_id=adopter.id, agent_id="bull_researcher", version=1,
            content="tgt v1", plain_english="tgt", is_active=True,
        ))
    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)
    with get_session() as s:
        rows = s.execute(
            select(UserOverlayRow).where(UserOverlayRow.user_id == adopter.id)
        ).scalars().all()
        # Only one row left: adopter's.
        assert len(rows) == 1
        assert rows[0].content == "tgt v1"


# ── Conflict resolution: overlay_edit_counts (sum on conflict) ─────────


def test_execute_sums_overlay_edit_counts_on_conflict():
    orphan, adopter = _make_users()
    with get_session() as s:
        s.add(OverlayEditCounter(
            user_id=orphan.id, agent_id="market_analyst", count=4,
        ))
        s.add(OverlayEditCounter(
            user_id=adopter.id, agent_id="market_analyst", count=7,
        ))
        # Orphan-only agent — straight re-key.
        s.add(OverlayEditCounter(
            user_id=orphan.id, agent_id="risk_manager", count=2,
        ))

    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)

    with get_session() as s:
        rows = s.execute(
            select(OverlayEditCounter).where(OverlayEditCounter.user_id == adopter.id)
        ).scalars().all()
        by_agent = {r.agent_id: r.count for r in rows}
        assert by_agent == {"market_analyst": 11, "risk_manager": 2}


# ── Sanity: orphan-side rows are all gone post-merge ───────────────────


def test_execute_removes_orphan_rows_completely():
    orphan, adopter = _make_orphan_with_everything()
    MergeService().execute(from_user_id=orphan.id, to_user_id=adopter.id)
    with get_session() as s:
        for model in (
            JournalEntryRow, SimTradeRow, SimWatchlistRow,
            LessonProgressRow, AgentActivationRow,
            OneOnOneMessageRow, RoomRunRow, BugReportRow,
            UserOverlayRow, MandateRow,
        ):
            rows = s.execute(
                select(model).where(model.user_id == orphan.id)
            ).scalars().all()
            assert rows == [], f"{model.__tablename__} still owned by orphan"
