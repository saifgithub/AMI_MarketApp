"""CR141 — provider_policy.pick_provider (CR017 §4 routing layer) + the
LLMGateway._pick_provider fallback guarantee (acceptance 4).

Two things under test:
  1. `pick_provider` itself, table-driven across every (plan, agent-band)
     pair (acceptance 6) — a pure function, no gateway involved.
  2. `LLMGateway._pick_provider`'s consumption of it: when the routed
     provider is unconfigured (or the mapping has no opinion), the gateway
     must fall back to EXACTLY the provider today's fixed preference order
     would choose — proven by asserting the with-routing and without-routing
     calls agree (acceptance 4), not just by re-deriving the expected name.
"""

from __future__ import annotations

import pytest

from app.schemas import AgentId
from app.schemas.mandate import Plan
from app.services.llm_gateway import LLMGateway
from app.services.provider_policy import pick_provider


# ── pick_provider: table-driven across every (plan, agent-band) pair ──────

# One representative agent per CR017 §4.1 band; agent_id doesn't affect
# routing today (see provider_policy's module docstring), but every band is
# exercised via a real agent from that band, not a synthetic tier string, so
# this stays honest about what tier_policy.pick_tier would actually hand in.
_CHEAP_BAND_AGENT = AgentId.MARKET_ANALYST       # Analysts & Debators
_MID_BAND_AGENT = AgentId.RESEARCH_MANAGER       # Synthesis / RM / Trader
_PREMIUM_BAND_AGENT = AgentId.PORTFOLIO_MANAGER  # PM / Verdict


@pytest.mark.parametrize("plan,agent,tier,expected", [
    # free (FLOOR_PASS) — every band routes to the on-prem GPU.
    (Plan.FLOOR_PASS, _CHEAP_BAND_AGENT, "cheap", "vllm"),
    (Plan.FLOOR_PASS, _MID_BAND_AGENT, "mid", "vllm"),
    (Plan.FLOOR_PASS, _PREMIUM_BAND_AGENT, "premium", "vllm"),
    # pro (TRADER) — DeepSeek for analysts, Gemini for the rest.
    (Plan.TRADER, _CHEAP_BAND_AGENT, "cheap", "deepseek"),
    (Plan.TRADER, _MID_BAND_AGENT, "mid", "gemini"),
    (Plan.TRADER, _PREMIUM_BAND_AGENT, "premium", "gemini"),
    # pro (TRIAL_TRADER) — mapped identically to TRADER (see module docstring).
    (Plan.TRIAL_TRADER, _CHEAP_BAND_AGENT, "cheap", "deepseek"),
    (Plan.TRIAL_TRADER, _MID_BAND_AGENT, "mid", "gemini"),
    (Plan.TRIAL_TRADER, _PREMIUM_BAND_AGENT, "premium", "gemini"),
    # max (FLOOR_MANAGER) — Gemini for analysts, Anthropic for the rest.
    (Plan.FLOOR_MANAGER, _CHEAP_BAND_AGENT, "cheap", "gemini"),
    (Plan.FLOOR_MANAGER, _MID_BAND_AGENT, "mid", "anthropic"),
    (Plan.FLOOR_MANAGER, _PREMIUM_BAND_AGENT, "premium", "anthropic"),
])
def test_pick_provider_routing_matrix(plan, agent, tier, expected):
    assert pick_provider(plan, agent, tier) == expected


def test_pick_provider_returns_none_for_an_unmapped_plan():
    """No `ultra` SKU exists (CR141 scope note) — a hypothetical plan the
    mapping doesn't cover must return None (defer to the gateway fallback),
    never raise or guess."""

    class _FuturePlan:
        pass

    assert pick_provider(_FuturePlan(), AgentId.TRADER, "cheap") is None  # type: ignore[arg-type]


# ── LLMGateway._pick_provider: unconfigured-provider fallback (acceptance 4) ──


def test_pick_provider_fallback_matches_todays_order_when_routed_is_unregistered(monkeypatch):
    """pro/mid routes to "gemini" (unconfigured here) — the gateway must
    choose EXACTLY what `_active_provider_name()` alone would choose, proven
    by comparing the two calls directly rather than hard-coding "vllm"."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "vllm_base_url", "http://lan:8000")
    gw = LLMGateway()
    without_routing = gw._pick_provider("en", "mid")
    with_routing = gw._pick_provider(
        "en", "mid", plan=Plan.TRADER, agent_id=AgentId.RESEARCH_MANAGER,
    )
    assert with_routing is without_routing
    assert with_routing.name == "vllm"


def test_pick_provider_fallback_matches_todays_order_on_a_bare_unkeyed_gateway():
    """The exact 'Alpha today' scenario the CR names explicitly: nothing
    configured at all except (implicitly) mock. Routing must not change
    which provider an unkeyed deployment ends up on."""
    gw = LLMGateway()
    without_routing = gw._pick_provider("en", "premium")
    with_routing = gw._pick_provider(
        "en", "premium", plan=Plan.FLOOR_MANAGER, agent_id=AgentId.PORTFOLIO_MANAGER,
    )
    assert with_routing is without_routing
    assert with_routing.name == "mock"


def test_pick_provider_uses_routed_provider_over_default_preference_when_registered(monkeypatch):
    """The positive case: when the routed provider is registered, the
    gateway must prefer IT over `_active_provider_name()`'s default order —
    proving the routing layer has a real effect, not just a fallback path.
    vLLM is ALSO registered here (and would win by default preference), so
    this can only pass if routing genuinely overrides the default."""
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "vllm_base_url", "http://lan:8000")
    monkeypatch.setattr(cfg.settings, "anthropic_api_key", "sk-ant-fake")
    gw = LLMGateway()
    assert gw._pick_provider("en", "mid").name == "vllm"  # sanity: default preference

    chosen = gw._pick_provider(
        "en", "mid", plan=Plan.FLOOR_MANAGER, agent_id=AgentId.RESEARCH_MANAGER,
    )
    assert chosen.name == "anthropic"


def test_stream_chat_without_plan_or_agent_id_is_unaffected_by_routing():
    """No existing call site passes plan/agent_id (CR141 scope) — confirm the
    keyword-argument defaults alone reproduce the pre-CR141 selection."""
    gw = LLMGateway()
    assert gw._pick_provider("en", "cheap").name == "mock"
