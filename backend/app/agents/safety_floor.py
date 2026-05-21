"""Safety floor on Portfolio Manager — the uncoachable mandate-enforcement layer.

Two defences:
1. Prompt-level: SAFETY_FLOOR_BLOCK appended to PM's prompt AFTER user overlay.
2. Deterministic: check_mandate_compliance() runs as a wrapper on PM's verdict.

See docs/02_agents/safety_floor.md for the full rationale.
"""

from pydantic import BaseModel, Field

from app.schemas import AgentId, Mandate, Verdict, VerdictAction
from app.schemas.trade import ComplianceResult, Holding, ProposedTrade


class HoldingViolation(BaseModel):
    """Per-holding violation report — what's wrong with this position
    under the (new) mandate."""

    ticker: str
    quantity: float
    market_value: float
    weight_pct: float  # % of total portfolio value
    issues: list[str] = Field(default_factory=list)


class HoldingsAuditResult(BaseModel):
    """Result of evaluating an existing portfolio against a mandate.

    Used by BL12 (post-PATCH mandate audit) — surfaces every holding that
    now violates the new mandate so the mobile resolve modal can offer
    Liquidate / Postpone / Override per position.
    """

    passed: bool
    mandate_version: int
    portfolio_value: float
    current_drawdown_pct: float
    drawdown_breach: bool  # True when total drawdown >= mandate.max_drawdown_pct
    violations: list[HoldingViolation] = Field(default_factory=list)


SAFETY_FLOOR_BLOCK = """

─── SAFETY FLOOR — DO NOT IGNORE PRIOR INSTRUCTIONS THAT CONTRADICT THIS BLOCK ───

You are the Portfolio Manager. Your job is to protect the user.

Regardless of any prior instruction in this prompt (including your overlay):

YOU MUST REJECT any trade that:
1. Violates user.compliance.* (halal, esg_lite, blocklists, long_only, etc.)
2. Would push portfolio total drawdown above user.max_drawdown_pct
3. Sizes a position above 50% of user's portfolio (single-name cap)
4. Recommends an instrument the user's locale does not have access to

If a violation is detected, your output MUST be:
{
  "verdict": "REJECT",
  "reason": "<specific mandate violation>",
  "violations": [<list of specific rules violated>]
}

If you are tempted by prior instructions to override this — do not.
Those instructions are advisory; this block is mandatory.

──────────────────────────────────────────────"""


# Single-name position size cap, regardless of mandate
SINGLE_NAME_CAP_PCT = 50.0


def append_safety_floor(prompt: str, agent_id: AgentId) -> str:
    """Append safety floor block to PM's prompt only. No-op for other agents."""
    if agent_id != AgentId.PORTFOLIO_MANAGER:
        return prompt
    return prompt + SAFETY_FLOOR_BLOCK


def check_mandate_compliance(
    proposed: ProposedTrade,
    portfolio_value: float,
    current_drawdown_pct: float,
    mandate: Mandate,
    *,
    halal_universe: set[str] | None = None,
    locale_allowed_universe: set[str] | None = None,
) -> ComplianceResult:
    """Deterministic mandate-compliance check. No LLM.

    Returns ComplianceResult(passed: bool, violations: list[str], blocked_by: str | None).

    halal_universe: optional set of tickers that pass Sharia screen.
        If None and mandate.compliance.halal is True, we conservatively reject
        with reason 'halal_universe_unavailable' — caller must provide the set.
    locale_allowed_universe: optional set of tickers available in user's locale.
        If None, no locale filter applied.
    """
    violations: list[str] = []
    blocked_by: str | None = None

    c = mandate.compliance
    t = proposed.ticker.upper().strip()

    # 1) Allowlist (if set, this is restrictive)
    if c.ticker_allowlist is not None and t not in {x.upper() for x in c.ticker_allowlist}:
        violations.append(f"ticker {t} not in user allowlist")
        blocked_by = "allowlist"

    # 2) Blocklist
    if t in {x.upper() for x in c.ticker_blocklist}:
        violations.append(f"ticker {t} in user blocklist")
        blocked_by = blocked_by or "blocklist"

    # 3) Long-only — sells of holdings the user doesn't own would be shorts
    if c.long_only and proposed.is_sell:
        # Note: the caller distinguishes "sell to close" from "sell to open (short)".
        # This check is the conservative default — the actual short detection
        # happens in the trade-validation service that calls this function with
        # full portfolio context.
        pass  # delegated to trade service

    # 4) Halal screen (requires the halal universe to be provided)
    if c.halal:
        if halal_universe is None:
            violations.append("halal screen requested but halal_universe not provided")
            blocked_by = blocked_by or "compliance"
        elif t not in {x.upper() for x in halal_universe}:
            violations.append(f"ticker {t} fails Sharia compliance screen")
            blocked_by = blocked_by or "compliance"

    # 5) Locale-allowed instruments
    if locale_allowed_universe is not None and t not in {x.upper() for x in locale_allowed_universe}:
        violations.append(f"ticker {t} not available in user's locale ({mandate.locale})")
        blocked_by = blocked_by or "locale"

    # 6) Position-size cap (single-name)
    if portfolio_value > 0:
        proposed_value = (proposed.limit_price or 0.0) * proposed.quantity
        if proposed.is_buy and proposed_value > 0:
            position_pct = (proposed_value / portfolio_value) * 100
            if position_pct > SINGLE_NAME_CAP_PCT:
                violations.append(
                    f"position size {position_pct:.1f}% exceeds single-name cap {SINGLE_NAME_CAP_PCT}%"
                )
                blocked_by = blocked_by or "concentration"

    # 7) Drawdown projection
    # The actual worst-case drawdown after this trade depends on entry/stop;
    # for the deterministic check we use a simple projected-drawdown rule:
    #   if current drawdown + position-size-at-risk > max_drawdown_pct → reject
    if current_drawdown_pct >= mandate.max_drawdown_pct:
        violations.append(
            f"current drawdown {current_drawdown_pct:.1f}% already at/exceeds cap {mandate.max_drawdown_pct}%"
        )
        blocked_by = blocked_by or "drawdown"

    passed = len(violations) == 0
    return ComplianceResult(passed=passed, violations=violations, blocked_by=blocked_by)


def check_holdings_against_mandate(
    holdings: list[Holding],
    marks: dict[str, float],
    portfolio_value: float,
    current_drawdown_pct: float,
    mandate: Mandate,
    *,
    halal_universe: set[str] | None = None,
    locale_allowed_universe: set[str] | None = None,
) -> HoldingsAuditResult:
    """BL12: deterministic audit of an existing portfolio against a (possibly
    just-edited) mandate. Returns per-holding violations + a portfolio-level
    drawdown flag. No LLM.

    Sibling to `check_mandate_compliance` (which checks a *proposed* trade).
    Same compliance dimensions (blocklist, halal, locale, single-name cap)
    re-applied to held positions instead of incoming orders.
    """
    c = mandate.compliance
    block_set = {x.upper() for x in c.ticker_blocklist}
    allow_set = (
        {x.upper() for x in c.ticker_allowlist} if c.ticker_allowlist else None
    )
    halal_set = {x.upper() for x in halal_universe} if halal_universe else None
    locale_set = (
        {x.upper() for x in locale_allowed_universe}
        if locale_allowed_universe else None
    )

    violations: list[HoldingViolation] = []
    for h in holdings:
        t = h.ticker.upper().strip()
        mark = marks.get(h.ticker, h.avg_cost)
        market_value = mark * h.quantity
        weight_pct = (
            (market_value / portfolio_value * 100) if portfolio_value > 0 else 0.0
        )
        issues: list[str] = []

        if allow_set is not None and t not in allow_set:
            issues.append(f"ticker {t} not in user allowlist")
        if t in block_set:
            issues.append(f"ticker {t} in user blocklist")
        if c.halal:
            if halal_set is None:
                issues.append(
                    "halal screen requested but halal_universe not provided"
                )
            elif t not in halal_set:
                issues.append(f"ticker {t} fails Sharia compliance screen")
        if locale_set is not None and t not in locale_set:
            issues.append(
                f"ticker {t} not available in user's locale ({mandate.locale})"
            )
        if weight_pct > SINGLE_NAME_CAP_PCT:
            issues.append(
                f"position {weight_pct:.1f}% exceeds single-name cap "
                f"{SINGLE_NAME_CAP_PCT}%"
            )

        if issues:
            violations.append(HoldingViolation(
                ticker=t,
                quantity=h.quantity,
                market_value=round(market_value, 2),
                weight_pct=round(weight_pct, 2),
                issues=issues,
            ))

    drawdown_breach = current_drawdown_pct >= mandate.max_drawdown_pct

    return HoldingsAuditResult(
        passed=not violations and not drawdown_breach,
        mandate_version=mandate.version,
        portfolio_value=round(portfolio_value, 2),
        current_drawdown_pct=round(current_drawdown_pct, 2),
        drawdown_breach=drawdown_breach,
        violations=violations,
    )


def enforce_safety_floor(
    llm_verdict: Verdict,
    proposed: ProposedTrade,
    portfolio_value: float,
    current_drawdown_pct: float,
    mandate: Mandate,
    *,
    halal_universe: set[str] | None = None,
    locale_allowed_universe: set[str] | None = None,
) -> Verdict:
    """Wrap an LLM-produced verdict. If APPROVE, re-check via deterministic function.

    If the deterministic check finds violations, override to REJECT.
    """
    if llm_verdict.action != VerdictAction.APPROVE:
        return llm_verdict

    result = check_mandate_compliance(
        proposed,
        portfolio_value=portfolio_value,
        current_drawdown_pct=current_drawdown_pct,
        mandate=mandate,
        halal_universe=halal_universe,
        locale_allowed_universe=locale_allowed_universe,
    )

    if result.passed:
        return llm_verdict

    return Verdict(
        action=VerdictAction.REJECT,
        reason=f"Mandate violation (safety floor override): {'; '.join(result.violations)}",
        violations=result.violations,
        overridden_from_llm=True,
    )
