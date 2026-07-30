"""DEF169 — the single-name concentration cap is skipped in silence when
`portfolio_value <= 0`.

`safety_floor.py` guards the cap with `portfolio_value > 0` and, when that fails,
simply never applies the cap — no log, no flag, no disclosure. The caller's
`ComplianceResult` reads `passed=True`, indistinguishable from a trade that was
actually checked and cleared. Exactly the class DEF153's commit message criticised,
reproduced at the single-name cap: a rule that declines to run and reports nothing.

Fix: the skip is logged, and the absence is visible in the verdict itself via a new
`ComplianceResult.not_evaluated` list — a reader can no longer confuse "checked and
clear" with "could not check".
"""

from __future__ import annotations

from unittest.mock import patch

from app.agents.safety_floor import check_mandate_compliance
from app.schemas.trade import OrderType, ProposedTrade, Side
from app.services.coach_engine import hydrate_coach_mandate


def _check(*, portfolio_value: float, quantity: float = 90.0):
    proposed = ProposedTrade(
        ticker="AAPL", side=Side.BUY, quantity=quantity,
        order_type=OrderType.LIMIT, limit_price=100.0,
    )
    return check_mandate_compliance(
        proposed,
        portfolio_value=portfolio_value,
        current_drawdown_pct=0.0,
        mandate=hydrate_coach_mandate({"plan": "trader"}),
        holdings=[], quotes={"AAPL": 100.0},
        # CR129: the five BE2 limits are always-active now; this file is about
        # the single-name cap, not these — harmless real context.
        last_loss_closed_at=None, trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )


def test_a_priced_buy_with_zero_portfolio_value_is_not_silently_passed():
    """$9,000 against a $0 portfolio_value cannot be measured as a percentage of
    anything — pre-fix this read `passed=True` with an empty `violations` list,
    identical to a trade that was actually checked."""
    result = _check(portfolio_value=0.0)
    assert result.passed, "not evaluated must not become a block"
    assert result.not_evaluated == [
        "single-name cap not evaluated — portfolio_value is not positive"
    ]


def test_a_negative_portfolio_value_is_also_unevaluated_not_passed_clean():
    result = _check(portfolio_value=-100.0)
    assert result.not_evaluated == [
        "single-name cap not evaluated — portfolio_value is not positive"
    ]


def test_the_skip_is_logged():
    with patch("app.agents.safety_floor.logger") as log:
        _check(portfolio_value=0.0)
    assert log.warning.call_count >= 1
    events = [c.args[0] for c in log.warning.call_args_list]
    assert "safety_floor_single_name_cap_unevaluated" in events


def test_a_normal_priced_buy_has_an_empty_not_evaluated_list():
    """Vacuity guard: `not_evaluated` is not populated on the ordinary path."""
    result = _check(portfolio_value=10_000.0)
    assert result.not_evaluated == []


def test_a_genuine_breach_is_still_caught_when_portfolio_value_is_positive():
    """The fix must not weaken the cap on the path where it CAN run."""
    result = _check(portfolio_value=10_000.0, quantity=90.0)
    assert not result.passed
    assert result.not_evaluated == []
