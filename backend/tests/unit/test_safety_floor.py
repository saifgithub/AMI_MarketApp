"""Tests for the safety floor — both prompt-level and deterministic check."""

from app.agents.safety_floor import (
    SAFETY_FLOOR_BLOCK,
    SINGLE_NAME_CAP_PCT,
    append_safety_floor,
    check_mandate_compliance,
    enforce_safety_floor,
)
from app.schemas import AgentId, Mandate, Verdict, VerdictAction
from app.schemas.trade import ComplianceResult, OrderType, ProposedTrade, Side


def test_safety_floor_only_on_portfolio_manager():
    base = "BASE PROMPT"
    for agent_id in AgentId:
        result = append_safety_floor(base, agent_id)
        if agent_id == AgentId.PORTFOLIO_MANAGER:
            assert SAFETY_FLOOR_BLOCK in result
        else:
            assert result == base


def test_safety_floor_appended_at_end():
    """Safety floor must come AFTER any prior instruction (including user overlay)."""
    prompt_with_overlay = "BASE\n\nUSER OVERLAY"
    result = append_safety_floor(prompt_with_overlay, AgentId.PORTFOLIO_MANAGER)
    overlay_idx = result.index("USER OVERLAY")
    floor_idx = result.index("SAFETY FLOOR")
    assert overlay_idx < floor_idx


def test_safety_floor_carries_classroom_framing():
    """Regulatory: financial advice cannot be delegated to an LLM. The floor
    block must frame every verdict as a classroom worked example and mandate
    the exact user-visible tag line. Guards against a future edit silently
    dropping the regulatory text.
    """
    assert "CLASSROOM FRAMING — ALSO MANDATORY" in SAFETY_FLOOR_BLOCK
    assert "simulation-only classroom exercise" in SAFETY_FLOOR_BLOCK
    assert (
        "Worked example — classroom simulation, not financial advice."
        in SAFETY_FLOOR_BLOCK
    )


def test_compliance_passes_clean_trade(
    base_mandate: Mandate, proposed_buy_nvda: ProposedTrade
):
    result = check_mandate_compliance(
        proposed_buy_nvda,
        portfolio_value=10_000,
        current_drawdown_pct=0,
        mandate=base_mandate,
    )
    assert result.passed
    assert result.violations == []
    assert result.blocked_by is None


def test_compliance_rejects_blocklist_ticker(
    base_mandate: Mandate, proposed_buy_nvda: ProposedTrade
):
    mandate = base_mandate.model_copy(
        update={
            "compliance": base_mandate.compliance.model_copy(update={"ticker_blocklist": ["NVDA"]})
        }
    )
    result = check_mandate_compliance(
        proposed_buy_nvda,
        portfolio_value=10_000,
        current_drawdown_pct=0,
        mandate=mandate,
    )
    assert not result.passed
    assert "NVDA" in result.violations[0]
    assert result.blocked_by == "blocklist"


def test_compliance_rejects_non_allowlist_ticker(
    base_mandate: Mandate, proposed_buy_nvda: ProposedTrade
):
    mandate = base_mandate.model_copy(
        update={
            "compliance": base_mandate.compliance.model_copy(update={"ticker_allowlist": ["AAPL"]})
        }
    )
    result = check_mandate_compliance(
        proposed_buy_nvda,
        portfolio_value=10_000,
        current_drawdown_pct=0,
        mandate=mandate,
    )
    assert not result.passed
    assert result.blocked_by == "allowlist"


def test_compliance_halal_requires_universe(
    halal_mandate: Mandate, proposed_buy_nvda: ProposedTrade
):
    """Halal flag with no universe provided → conservative reject."""
    result = check_mandate_compliance(
        proposed_buy_nvda,
        portfolio_value=10_000,
        current_drawdown_pct=0,
        mandate=halal_mandate,
        halal_universe=None,
    )
    assert not result.passed
    assert result.blocked_by == "compliance"


def test_compliance_halal_with_passing_universe(
    halal_mandate: Mandate, proposed_buy_nvda: ProposedTrade
):
    result = check_mandate_compliance(
        proposed_buy_nvda,
        portfolio_value=10_000,
        current_drawdown_pct=0,
        mandate=halal_mandate,
        halal_universe={"NVDA", "AAPL", "MSFT"},
    )
    assert result.passed


def test_compliance_halal_with_excluded_ticker(
    halal_mandate: Mandate, proposed_buy_nvda: ProposedTrade
):
    result = check_mandate_compliance(
        proposed_buy_nvda,
        portfolio_value=10_000,
        current_drawdown_pct=0,
        mandate=halal_mandate,
        halal_universe={"AAPL", "MSFT"},  # NVDA not in halal universe
    )
    assert not result.passed
    assert "Sharia" in result.violations[0]
    assert result.blocked_by == "compliance"


def test_compliance_rejects_oversized_position(
    base_mandate: Mandate, proposed_buy_nvda: ProposedTrade
):
    # quantity 10 × $152 = $1,520. portfolio_value $1,000 → 152% position → exceeds 50% cap
    result = check_mandate_compliance(
        proposed_buy_nvda,
        portfolio_value=1_000,
        current_drawdown_pct=0,
        mandate=base_mandate,
    )
    assert not result.passed
    assert "single-name cap" in result.violations[0]
    assert result.blocked_by == "concentration"


def test_compliance_rejects_when_at_drawdown_cap(
    base_mandate: Mandate, proposed_buy_nvda: ProposedTrade
):
    # base_mandate.max_drawdown_pct = 30
    result = check_mandate_compliance(
        proposed_buy_nvda,
        portfolio_value=10_000,
        current_drawdown_pct=30.0,
        mandate=base_mandate,
    )
    assert not result.passed
    assert result.blocked_by == "drawdown"


def test_enforce_safety_floor_overrides_approve_on_violation(
    base_mandate: Mandate, proposed_buy_nvda: ProposedTrade
):
    """LLM said APPROVE but trade violates blocklist → safety floor flips to REJECT."""
    mandate = base_mandate.model_copy(
        update={
            "compliance": base_mandate.compliance.model_copy(update={"ticker_blocklist": ["NVDA"]})
        }
    )
    llm_verdict = Verdict(action=VerdictAction.APPROVE, reason="Looks fine", size_pct=3.0)
    final = enforce_safety_floor(
        llm_verdict,
        proposed_buy_nvda,
        portfolio_value=10_000,
        current_drawdown_pct=0,
        mandate=mandate,
    )
    assert final.action == VerdictAction.REJECT
    assert final.overridden_from_llm is True
    assert "blocklist" in " ".join(final.violations).lower() or "NVDA" in " ".join(final.violations)


def test_enforce_safety_floor_passes_clean_approve(
    base_mandate: Mandate, proposed_buy_nvda: ProposedTrade
):
    """LLM said APPROVE, trade is clean → unchanged."""
    llm_verdict = Verdict(action=VerdictAction.APPROVE, reason="Looks fine", size_pct=3.0)
    final = enforce_safety_floor(
        llm_verdict,
        proposed_buy_nvda,
        portfolio_value=100_000,
        current_drawdown_pct=2.0,
        mandate=base_mandate,
    )
    assert final.action == VerdictAction.APPROVE
    assert final.overridden_from_llm is False


def test_enforce_safety_floor_does_not_touch_rejects(
    base_mandate: Mandate, proposed_buy_nvda: ProposedTrade
):
    """LLM said REJECT → safety floor passes through unchanged."""
    llm_verdict = Verdict(action=VerdictAction.REJECT, reason="Bull case is weak", size_pct=None)
    final = enforce_safety_floor(
        llm_verdict,
        proposed_buy_nvda,
        portfolio_value=10_000,
        current_drawdown_pct=0,
        mandate=base_mandate,
    )
    assert final.action == VerdictAction.REJECT
    assert final.overridden_from_llm is False


def test_single_name_cap_value():
    """Sanity check the cap is the documented 50%."""
    assert SINGLE_NAME_CAP_PCT == 50.0
