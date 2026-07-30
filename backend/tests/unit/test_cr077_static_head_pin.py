"""Auditor pin (CR077-CONCIERGE) — adversarial: no per-user token may appear
in the cached static head, and the head must be byte-identical across three
wildly different mandates. Stronger than the architect's 2-user byte test:
it also asserts the ABSENCE of user-specific strings in the head, catching a
future personalised-line regression that a same-value fixture could miss.

DEF141: this pin now LIVES on the auto-run path (`backend/tests/unit/`) instead of
being copied there by hand. It sat in `orchestration/audit/regression/` for months,
outside every collection path this project runs, and therefore protected nothing.
DEF168: the `DailyBriefing` import was deleted by CR114/DEF129 — dropped here.
Verified: PASS at f297196, RED at pre-fix ordering (d99502f~1)."""
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from app.schemas import (Compliance, Mandate, Horizon, Path, PrimaryGoal,
                         RiskComponents, LearningStyle, Plan)
from app.schemas.journal import EntryType, JournalEntry
from app.services.concierge_prompts import build_concierge_messages
from app.services.lessons_service import get_lessons_service

_HEAD_CHARS = 2 * 2096 * 4  # 2 whole vLLM blocks' worth


def _m(uid, name, goal, horizon, path, risk, dd, comp, locale, tz):
    return Mandate(
        user_id=uid, version=1, display_name=name, locale=locale, timezone=tz,
        primary_goal=goal, horizon=horizon, target_outcome=None, path=path,
        risk_score=risk,
        risk_components=RiskComponents(drawdown_response=risk, regret_asymmetry=0, concentration_tolerance=3),
        risk_quotes=[], max_drawdown_pct=dd, compliance=comp,
        learning_style=LearningStyle.QUICK,
        plan=Plan.TRADER, trial_expires_at=None, credit_balance=150,
        created_at=datetime(2026, 5, 11), updated_at=datetime(2026, 5, 11),
    )


def _head(m, msg, journal, unlocked):
    sp, _ = build_concierge_messages(
        mandate=m, user_id=m.user_id, user_message=msg, history=[],
        recent_journal=journal, unlocked_agents=unlocked,
        available_lessons=get_lessons_service().all_meta(),
    )
    return sp


def test_head_identical_and_leakfree_across_three_users():
    m1 = _m(UUID(int=1), "Zaphod Beeblebrox", PrimaryGoal.LONG_TERM_WEALTH, Horizon.LONG,
            Path.LONG_HORIZON, 3, 30, Compliance(long_only=True, liquid_only=True), "en", "UTC")
    m2 = _m(UUID(int=2), "Trillian Astra", PrimaryGoal.INCOME_NOW, Horizon.SHORT,
            Path.ACTIVE, 5, 10, Compliance(halal=True, long_only=False), "ar", "Asia/Riyadh")
    m3 = _m(UUID(int=3), "Ford Prefect", PrimaryGoal.RETIREMENT, Horizon.MEDIUM,
            Path.LONG_HORIZON, 1, 20, Compliance(long_only=True, liquid_only=False, halal=True), "ms", "Asia/Kuala_Lumpur")
    p1 = _head(m1, "hi", [], set())
    p2 = _head(m2, "route me", [JournalEntry(user_id=m2.user_id, entry_type=EntryType.SIM_TRADE, title="Bought TSLA", ticker="TSLA")], {"technical_analyst"})
    p3 = _head(m3, "what next", [JournalEntry(user_id=m3.user_id, entry_type=EntryType.SIM_TRADE, title="Sold AAPL", ticker="AAPL")], {"macro_analyst", "risk_manager"})

    assert len(p1) >= _HEAD_CHARS
    assert p1[:_HEAD_CHARS] == p2[:_HEAD_CHARS] == p3[:_HEAD_CHARS]

    # Adversarial: no per-user token may appear anywhere in the cached head.
    leaks = ["Zaphod", "Trillian", "Ford Prefect", "TSLA", "AAPL", "Asia/Riyadh",
             "Kuala_Lumpur", "Someone Else", "halal", "Mandate snapshot"]
    for tok in leaks:
        assert tok not in p1[:_HEAD_CHARS], f"per-user token {tok!r} leaked into cached head"
