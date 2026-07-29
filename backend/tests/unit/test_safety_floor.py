"""Tests for the safety floor — both prompt-level and deterministic check."""

import re

from app.agents.safety_floor import (
    SAFETY_FLOOR_BLOCK,
    append_safety_floor,
    check_mandate_compliance,
    enforce_safety_floor,
    render_safety_floor_block,
    single_name_cap_pct,
)
from app.schemas import AgentId, Mandate, Verdict, VerdictAction
from app.schemas.trade import ComplianceResult, OrderType, ProposedTrade, Side
from app.services.classification_universe import ClassificationUniverse
from app.trading_math.sizing import risk_tier_cap

# DEF061: the halal_mandate fixture also sets no_tobacco_alcohol_gambling, now a
# deterministically-enforced flag. A universe that classifies NVDA as clean lets the
# halal-focused tests below isolate the halal check (without it, the sin flag pauses
# on a None classification universe — the intended loud degrade, covered by DEF061).
_NVDA_CLEAN_UNIVERSE = ClassificationUniverse(classified={"NVDA", "AAPL", "MSFT"})


def test_safety_floor_only_on_portfolio_manager(base_mandate: Mandate):
    base = "BASE PROMPT"
    for agent_id in AgentId:
        result = append_safety_floor(base, agent_id, base_mandate)
        if agent_id == AgentId.PORTFOLIO_MANAGER:
            assert render_safety_floor_block(base_mandate) in result
        else:
            assert result == base


def test_safety_floor_appended_at_end(base_mandate: Mandate):
    """Safety floor must come AFTER any prior instruction (including user overlay)."""
    prompt_with_overlay = "BASE\n\nUSER OVERLAY"
    result = append_safety_floor(prompt_with_overlay, AgentId.PORTFOLIO_MANAGER, base_mandate)
    overlay_idx = result.index("USER OVERLAY")
    floor_idx = result.index("SAFETY FLOOR")
    assert overlay_idx < floor_idx


def test_safety_floor_prose_cap_equals_the_enforced_constant(base_mandate: Mandate):
    """CR046 C-a: the single-name cap the PM is SHOWN in its rendered safety-floor
    block must equal the cap the deterministic check ENFORCES
    (`single_name_cap_pct(mandate)`). CR101-BE1 made this per-mandate — the prose
    used to hardcode the fixed absolute backstop; it now interpolates the mandate's
    actual resolved cap at render time. Parse the shown number and assert
    shown == enforced."""
    rendered = render_safety_floor_block(base_mandate)
    m = re.search(r"above (\d+)% of user's portfolio", rendered)
    assert m is not None, "single-name cap line missing from the rendered safety floor block"
    assert int(m.group(1)) == int(single_name_cap_pct(base_mandate))
    # base_mandate has no explicit override → falls back to the 50% absolute
    # backstop this floor has always enforced (migration-safe; see
    # safety_floor.single_name_cap_pct's docstring for why this is NOT the
    # risk-tier preset).
    assert single_name_cap_pct(base_mandate) == 50.0


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
        classification_universe=_NVDA_CLEAN_UNIVERSE,
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
    # CR069: legacy bare-set path (a plain set, no parent index) blocks on absence
    # with a neutral message. The sourced three-state path (screened-out names the
    # AAOIFI standard) is covered in test_sharia_universe / the CR069 guard.
    assert "outside the configured halal universe" in result.violations[0]
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


def test_single_name_cap_falls_back_to_absolute_backstop(base_mandate: Mandate):
    """CR101-BE1: with no explicit `single_name_cap_pct` override, this floor's
    enforced cap falls back to the fixed 50% absolute backstop — the EXACT
    value it enforced pre-CR101 (migration-safe). NOT the tighter risk-tier
    preset the Trader/PM overlay narrates and the Room's own pre-clamp uses —
    see safety_floor.single_name_cap_pct's docstring for the measured reason
    this floor's default deliberately differs from that preset."""
    assert base_mandate.single_name_cap_pct is None
    assert single_name_cap_pct(base_mandate) == 50.0
    assert single_name_cap_pct(base_mandate) != risk_tier_cap(base_mandate.risk_score)


def test_single_name_cap_honours_explicit_override(base_mandate: Mandate):
    """CR101-BE1 acceptance 3: an explicit `single_name_cap_pct` overrides the preset."""
    m = base_mandate.model_copy(update={"single_name_cap_pct": 12.5})
    assert single_name_cap_pct(m) == 12.5
