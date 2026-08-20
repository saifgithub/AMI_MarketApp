"""Tests for the mandate overlay generator. Pure-function; runs fast."""


from app.agents.overlay_generator import _max_position_pct, generate_overlay
from app.schemas import AgentId, Mandate


def test_every_trading_agent_produces_an_overlay(
    base_mandate: Mandate, all_agents: tuple[AgentId, ...]
):
    for agent_id in all_agents:
        overlay = generate_overlay(agent_id, base_mandate)
        assert overlay, f"empty overlay for {agent_id}"
        assert "USER MANDATE" in overlay
        assert "Role guidance" in overlay


def test_concierge_gets_a_distinct_overlay(base_mandate: Mandate):
    overlay = generate_overlay(AgentId.CONCIERGE, base_mandate)
    assert "CONCIERGE CONTEXT" in overlay
    assert "DO NOT" in overlay  # Concierge cannot give trading advice


def test_halal_flag_appears_in_overlay(halal_mandate: Mandate):
    overlay = generate_overlay(AgentId.FUNDAMENTALS_ANALYST, halal_mandate)
    assert "HALAL" in overlay or "Sharia" in overlay
    assert "interest-based" in overlay.lower() or "compliance" in overlay.lower()


def test_long_only_flag_changes_bear_framing(base_mandate: Mandate):
    # base_mandate has long_only=True
    overlay = generate_overlay(AgentId.BEAR_RESEARCHER, base_mandate)
    assert "LONG-ONLY" in overlay
    assert "Do NOT propose shorts" in overlay or "avoid" in overlay.lower()


def test_long_only_off_still_does_not_offer_shorts_in_bear(aggressive_mandate: Mandate):
    """CR179 Leg 1 (CR150 Tier C) — INVERTED, because the old assertion was
    false about production.

    It read:

        # aggressive_mandate has long_only=False
        assert "Explicit short recommendations allowed" in overlay or "shorts" in overlay.lower()

    and passed either way, because the substring "shorts" also appears in the
    LONG-ONLY branch's own "Do NOT propose shorts" — so it could not have
    distinguished the two branches even if the copy had been right.

    The copy was not right. `sim_engine`'s SELL path rejects any quantity beyond
    what is held with `blocked_by="long_only"` and **no reference to
    `mandate.compliance.long_only`** (app/services/sim_engine.py:848-856,
    :1346). Shorting is unavailable regardless of the flag. Worse, the branch is
    reachable by accident: `concierge_engine._parse_constraints` leaves
    `long_only` False by OMISSION, so a user who never asked to short could be
    handed a Bear that offers it — advice the engine then refuses, which is
    CR040's degrade-loudly failure aimed at the user instead of the operator.
    """
    overlay = generate_overlay(AgentId.BEAR_RESEARCHER, aggressive_mandate)
    assert "Shorting is not available in this simulator" in overlay
    assert "Explicit short recommendations allowed" not in overlay


def test_max_drawdown_appears_in_aggressive_overlay(base_mandate: Mandate):
    overlay = generate_overlay(AgentId.AGGRESSIVE_DEBATOR, base_mandate)
    assert f"{base_mandate.max_drawdown_pct}%" in overlay


def test_trader_position_size_scales_with_risk_score(
    conservative_mandate: Mandate, aggressive_mandate: Mandate
):
    conservative = generate_overlay(AgentId.TRADER, conservative_mandate)
    aggressive = generate_overlay(AgentId.TRADER, aggressive_mandate)
    # CR046 M03: the Trader is told exactly the per-risk-tier cap the PM enforces,
    # and the cap still scales with risk (risk 1 → 1.5%, risk 5 → 4.5%).
    lo = _max_position_pct(conservative_mandate)
    hi = _max_position_pct(aggressive_mandate)
    assert f"{lo}% per name" in conservative
    assert f"{hi}% per name" in aggressive
    assert hi > lo


def test_risk_score_in_overlay(base_mandate: Mandate):
    overlay = generate_overlay(AgentId.PORTFOLIO_MANAGER, base_mandate)
    assert "risk_score=3" in overlay or f"Risk score: {base_mandate.risk_score}" in overlay


def test_ticker_blocklist_propagates(base_mandate: Mandate):
    mandate = base_mandate.model_copy(
        update={"compliance": base_mandate.compliance.model_copy(update={"ticker_blocklist": ["TSLA"]})}
    )
    overlay = generate_overlay(AgentId.FUNDAMENTALS_ANALYST, mandate)
    assert "TSLA" in overlay


def test_overlay_determinism(base_mandate: Mandate):
    """Same mandate + same agent → same overlay every time."""
    a = generate_overlay(AgentId.FUNDAMENTALS_ANALYST, base_mandate)
    b = generate_overlay(AgentId.FUNDAMENTALS_ANALYST, base_mandate)
    assert a == b


def test_overlay_has_no_llm_call(base_mandate: Mandate):
    """Overlay generator must be pure — sanity check on no async/IO."""
    # If this function ever becomes async, this import would fail
    import inspect

    assert not inspect.iscoroutinefunction(generate_overlay)


# ── Social Media / News truthfulness (CR024/CR023, AT:R57) ────────────────


def test_social_block_drops_named_platform_and_fake_precision_claims(
    conservative_mandate: Mandate, aggressive_mandate: Mandate
):
    conservative = generate_overlay(AgentId.SOCIAL_MEDIA_ANALYST, conservative_mandate)
    assert "down-weight retail-noise sources (r/wallstreetbets" not in conservative
    # AT:R57-continued: Reddit is now a real (when configured) source, so
    # the overlay no longer claims a blanket "no live feed" — it names the
    # platforms that still don't exist instead.
    assert "no live twitter/x, stocktwits, google trends, or discord feed" in conservative.lower()

    # Old aggressive-branch claim implied a real measured statistic
    # ("Retail sentiment is a tradable signal. Report extremes (>2σ unusual
    # activity)") — checking for that exact phrase, not a bare "σ" ban,
    # since the (always-present) honesty intro legitimately mentions "a σ
    # score" once while telling the agent not to fabricate one.
    aggressive = generate_overlay(AgentId.SOCIAL_MEDIA_ANALYST, aggressive_mandate)
    assert ">2σ unusual activity" not in aggressive
    assert "illustrative" in aggressive.lower()


def test_social_block_still_produces_role_guidance_header(base_mandate: Mandate):
    overlay = generate_overlay(AgentId.SOCIAL_MEDIA_ANALYST, base_mandate)
    assert "## Role guidance — Flow & Positioning" in overlay


def test_news_block_reinforces_no_macro_feed(base_mandate: Mandate):
    overlay = generate_overlay(AgentId.NEWS_ANALYST, base_mandate)
    assert "no live macro-indicator calendar" in overlay.lower()
