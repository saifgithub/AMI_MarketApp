"""CR284 — minimum reward to risk as a mandate setting.

Covers the acceptance list: the default per risk level, a user override, an
APPROVE below the floor becoming REJECT with both numbers named, exactly at the
floor passing, missing levels untouched, US and Bursa alike, the Room bank key
following the effective floor, and the Bursa 200 batch's 24 approvals re-scored
at the risk-5 default.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.agents.safety_floor import check_mandate_compliance, enforce_safety_floor
from app.schemas.mandate import Mandate
from app.schemas.room import Verdict, VerdictAction
from app.schemas.trade import OrderType, ProposedTrade, Side
from app.services import room_bank
from app.services.coach_engine import hydrate_coach_mandate
from app.services.mandate_store import MandateStore
from app.trading_math.risk_limits import (
    DEFAULT_MIN_REWARD_RISK,
    format_reward_risk,
    min_reward_risk_source,
    resolved_min_reward_risk,
    reward_risk_ratio,
)

_BATCH = (
    Path(__file__).resolve().parents[3]
    / "docs/forward_planning/CR282_bursa_malaysia/bursa_batch/runs_bursa282-2026-11-25.jsonl"
)


def _mandate(risk: int = 3, **kw) -> Mandate:
    return hydrate_coach_mandate({
        "plan": "trader", "risk_score": risk, "single_name_cap_pct": 100.0,
        "sector_cap_pct": 100.0, **kw,
    })


def _check(mandate: Mandate, ticker: str, entry, stop, target):
    proposed = ProposedTrade(
        ticker=ticker, side=Side.BUY, order_type=OrderType.LIMIT,
        quantity=1.0, limit_price=entry,
    )
    return check_mandate_compliance(
        proposed, portfolio_value=1_000_000.0, current_drawdown_pct=0.0,
        mandate=mandate, holdings=[], quotes={ticker: entry},
        last_loss_closed_at=None, trade_open_timestamps=[],
        existing_open_risk_pct=0.0, proposed_stop=stop,
        proposed_target=target, proposed_entry=entry,
    )


def _rr_violations(result) -> list[str]:
    return [v for v in result.violations if "reward to risk" in v]


@pytest.mark.parametrize("risk,expected", [(1, 2.0), (2, 2.0), (3, 1.5), (4, 1.5), (5, 1.0)])
def test_default_floor_follows_the_risk_score(risk, expected):
    assert resolved_min_reward_risk(risk) == expected
    assert DEFAULT_MIN_REWARD_RISK[risk] == expected
    assert min_reward_risk_source(None) == "default"


def test_a_user_value_wins_and_zero_is_a_real_off():
    assert resolved_min_reward_risk(5, 2.5) == 2.5
    assert resolved_min_reward_risk(1, 0.0) == 0.0
    assert min_reward_risk_source(0.0) == "user"
    result = _check(_mandate(1, min_reward_risk=0.0), "AAPL", 100.0, 90.0, 101.0)
    assert not _rr_violations(result)
    # Off means off, even for a target on the wrong side of entry.
    assert not _rr_violations(_check(_mandate(1, min_reward_risk=0.0), "AAPL", 100.0, 90.0, 95.0))


def test_below_the_floor_is_blocked_with_both_numbers_named():
    # Risk 5 default 1.0; SD Guthrie's real levels from the Bursa batch.
    result = _check(_mandate(5), "5285.KL", 6.00, 5.64, 6.155)
    assert not result.passed and result.blocked_by == "reward_risk"
    assert _rr_violations(result) == [
        "reward to risk 0.43 is below your mandate minimum of 1.0"
    ]


def test_exactly_at_the_floor_passes():
    assert not _rr_violations(_check(_mandate(3), "AAPL", 100.0, 90.0, 115.0))
    assert _rr_violations(_check(_mandate(3), "AAPL", 100.0, 90.0, 114.9))


def test_a_user_floor_overrides_the_risk_default():
    # 1.2:1 clears the risk-5 default of 1.0 but not a user's 1.5.
    assert not _rr_violations(_check(_mandate(5), "AAPL", 100.0, 90.0, 112.0))
    assert _rr_violations(_check(_mandate(5, min_reward_risk=1.5), "AAPL", 100.0, 90.0, 112.0))


def test_a_ratio_that_prints_like_the_floor_still_tells_them_apart():
    text = _rr_violations(_check(_mandate(3), "AAPL", 100.0, 90.0, 114.99))[0]
    assert "1.499 is below" in text and "minimum of 1.5" in text


def test_missing_levels_are_untouched():
    mandate = _mandate(5)
    proposed = ProposedTrade(
        ticker="AAPL", side=Side.BUY, order_type=OrderType.LIMIT, quantity=1.0, limit_price=100.0,
    )
    base = dict(
        portfolio_value=1_000_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=[], quotes={"AAPL": 100.0}, last_loss_closed_at=None,
        trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )
    # A manual ticket: a stop, no target.
    manual = check_mandate_compliance(proposed, proposed_stop=90.0, **base)
    assert manual.passed and not manual.not_evaluated
    # A target without a stop cannot define a ratio: said, never silently passed.
    no_stop = check_mandate_compliance(proposed, proposed_target=120.0, **base)
    assert no_stop.passed and any("reward to risk" in n for n in no_stop.not_evaluated)


def test_a_stop_on_the_wrong_side_is_not_evaluated_not_blocked():
    result = _check(_mandate(5), "AAPL", 100.0, 105.0, 120.0)
    assert not _rr_violations(result)
    assert any("reward to risk" in n for n in result.not_evaluated)


def test_short_geometry_mirrors_the_distances():
    assert reward_risk_ratio(100.0, 110.0, 80.0, short=True) == pytest.approx(2.0)
    assert reward_risk_ratio(100.0, 90.0, 80.0, short=True) is None
    assert reward_risk_ratio(100.0, 90.0, 120.0) == pytest.approx(2.0)


def test_floor_override_turns_an_llm_approve_into_a_named_reject():
    approve = Verdict(
        action=VerdictAction.APPROVE, size_pct=1.0, entry=6.00, stop=5.64, target=6.155,
        time_horizon_days=30, reason="x",
    )
    proposed = ProposedTrade(
        ticker="5285.KL", side=Side.BUY, order_type=OrderType.LIMIT, quantity=1.0, limit_price=6.00,
    )
    out = enforce_safety_floor(
        approve, proposed, portfolio_value=1_000_000.0, current_drawdown_pct=0.0,
        mandate=_mandate(5), holdings=[], quotes={"5285.KL": 6.0},
        last_loss_closed_at=None, trade_open_timestamps=[], existing_open_risk_pct=0.0,
        proposed_stop=5.64, proposed_target=6.155, proposed_entry=6.00,
    )
    assert out.action == VerdictAction.REJECT and out.overridden_from_llm
    assert "reward to risk 0.43 is below your mandate minimum of 1.0" in out.violations


def test_us_and_bursa_rooms_are_judged_alike():
    for ticker in ("AAPL", "5285.KL"):
        assert _rr_violations(_check(_mandate(1), ticker, 10.0, 9.0, 11.0))  # 1.0 < 2.0
        assert not _rr_violations(_check(_mandate(1), ticker, 10.0, 9.0, 12.0))  # 2.0


def test_the_bursa_batch_rescored_at_the_risk_five_default_rejects_exactly_two():
    rows = [json.loads(line) for line in _BATCH.read_text().splitlines() if line.strip()]
    approvals = [r for r in rows if (r.get("verdict") or {}).get("action") == "APPROVE"]
    assert len(approvals) == 24
    rejected = []
    for r in approvals:
        v = r["verdict"]
        assert r["risk_score"] == 5
        result = _check(_mandate(5), r["ticker"], v["entry"], v["stop"], v["target"])
        if _rr_violations(result):
            rejected.append(r["ticker"])
    assert sorted(rejected) == ["4006.KL", "5285.KL"]


def test_a_changed_floor_never_serves_a_stale_room():
    m = _mandate(3)
    assert room_bank.mandate_digest(m) != room_bank.mandate_digest(
        m.model_copy(update={"min_reward_risk": 2.0})
    )
    # An unset floor follows the risk score through the table.
    assert room_bank.mandate_digest(m) != room_bank.mandate_digest(
        m.model_copy(update={"risk_score": 5})
    )


def test_a_retuned_default_table_rekeys_unset_mandates(monkeypatch):
    m = _mandate(3)
    before = room_bank.mandate_digest(m)
    monkeypatch.setitem(DEFAULT_MIN_REWARD_RISK, 3, 1.75)
    assert room_bank.mandate_digest(m) != before


def test_the_violation_text_formatting():
    assert format_reward_risk(1.0) == "1.0"
    assert format_reward_risk(1.5) == "1.5"
    assert format_reward_risk(2.0) == "2.0"
    assert format_reward_risk(0.4306) == "0.43"
    assert format_reward_risk(1.25) == "1.25"


@pytest.mark.parametrize("risk,floor", [(1, "2.0"), (3, "1.5"), (5, "1.0")])
def test_the_onboarding_readback_names_the_default_floor(risk, floor):
    from app.services.concierge_engine import _readback_text

    text = _readback_text({
        "primary_goal": "long_term_wealth", "horizon": "long", "risk_score": risk,
        "max_drawdown_pct": 20, "compliance": {"long_only": True},
    })
    assert f"Reward to risk: at least {floor}:1" in text
    assert "change this in Settings" in text


def test_the_mandate_read_says_where_the_floor_came_from():
    from app.api.mandate import _with_plan_state
    from app.db import get_session
    from app.db.models import User
    from app.services.auth_service import AuthService

    user, _, _ = AuthService().ensure_anonymous(device_user_id=None)
    with get_session() as s:
        row = s.get(User, user.id)
        default = _with_plan_state(_mandate(5), row).resolved
        user_set = _with_plan_state(_mandate(5, min_reward_risk=2.5), row).resolved
    assert (default.min_reward_risk, default.min_reward_risk_source) == (1.0, "default")
    assert (user_set.min_reward_risk, user_set.min_reward_risk_source) == (2.5, "user")


def test_the_store_round_trips_and_rejects_a_nonsense_floor():
    store = MandateStore()
    uid = uuid4()
    assert store.patch(uid, {"min_reward_risk": 2.5}).min_reward_risk == 2.5
    assert store.patch(uid, {"min_reward_risk": None}).min_reward_risk is None
    with pytest.raises(Exception):
        store.patch(uid, {"min_reward_risk": -1})
