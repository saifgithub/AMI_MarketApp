"""CR217 — the GLM provider must be reachable for a head-to-head, and invisible otherwise.

GLM-5.3-Flash-NVFP4 is a candidate Room model being scored against the incumbent
vLLM model on the same as-of pairs. Two things have to hold at once, and they pull
in opposite directions:

  * **It must serve traffic when forced**, or the comparison measures nothing.
  * **It must not serve traffic otherwise**, or registering a candidate silently
    swaps the model under live Alpha users.

The failure this file mainly exists to prevent is neither of those, though. It is
the third one: `_active_provider_name` falls through to normal preference when a
forced provider is not registered, *deliberately* and silently, so that a typo'd
test env var can never 500 a live flow. That kindness is a trap for a benchmark —
`LLM_FORCE_PROVIDER=glm` with no `GLM_BASE_URL` runs the **incumbent**, and the
head-to-head then scores ami-llm against itself and reports a null that looks
exactly like a real one. These tests pin the wiring; the run-time check that the
right model actually answered is `llm_audit.provider`, which is NOT NULL and
written per call.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.services import llm_gateway
from app.services.llm_gateway import LLMGateway, OpenAICompatibleProvider
from app.services.room_runner import _AGENT_LLM_TIMEOUT_S


@pytest.fixture
def gateway(monkeypatch):
    """Build gateways against a retuned copy of the live Settings object.

    Every field this file touches is set explicitly per case, so the test does
    not depend on which keys happen to be in the developer's env.
    """

    def _build(**overrides):
        base = {
            "glm_base_url": "",
            "glm_api_key": "",
            "glm_max_tokens_floor": 0,
            "vllm_base_url": "",
            "anthropic_api_key": "",
            "kimi_api_key": "",
            "deepseek_api_key": "",
            "dashscope_api_key": "",
            "google_ai_api_key": "",
            "llm_force_provider": "",
        }
        base.update(overrides)
        for k, v in base.items():
            monkeypatch.setattr(settings, k, v)
        return LLMGateway()

    return _build


def test_a_v1_suffixed_base_url_doubles_the_path():
    """Characterizes the trap, because the endpoint is published WITH the /v1.

    `OpenAICompatibleProvider` appends `/v1/chat/completions` itself and only
    strips a trailing slash, so the published form
    `http://100.94.223.38:8008/v1/` becomes `/v1/v1/chat/completions` and 404s.
    A 404 for every call mid-sweep is a DEF059 fail-safe PASS, i.e. it reads as
    the model declining every single trade rather than as a misconfiguration —
    which is precisely the shape a benchmark cannot afford to misread.

    This asserts the doubling HAPPENS. It is not the desired behaviour; it is
    the reason `glm_base_url` must be stored without the `/v1`.
    """
    def final_url(base: str) -> str:
        p = OpenAICompatibleProvider(
            name="glm", base_url=base, model_name="m", api_key=None,
        )
        return str(p._client.build_request("POST", "/v1/chat/completions").url)

    assert final_url("http://host:8008/v1/") == "http://host:8008/v1/v1/chat/completions"
    assert final_url("http://host:8008") == "http://host:8008/v1/chat/completions"


def test_registering_glm_does_not_change_who_serves_live_traffic(gateway):
    """A candidate model must be inert until explicitly forced."""
    gw = gateway(glm_base_url="http://host:8008", vllm_base_url="http://lan:8048")
    assert "glm" in gw._providers, "GLM_BASE_URL set ⇒ registered"
    assert gw._active_provider_name() == "vllm", "a candidate must not swap the live model"
    assert "glm" not in LLMGateway._PREFERENCE, (
        "GLM in _PREFERENCE would make it a live fallback, not a candidate"
    )


def test_forcing_glm_actually_reaches_glm(gateway):
    """The other half: the benchmark's own selection mechanism has to work."""
    gw = gateway(
        glm_base_url="http://host:8008",
        vllm_base_url="http://lan:8048",
        llm_force_provider="glm",
    )
    assert gw._active_provider_name() == "glm"
    assert gw.status()["active_provider"] == "glm"


def test_forcing_glm_without_a_url_runs_the_incumbent_instead(gateway):
    """Pins the trap this file exists for, so it is a known shape and not a surprise.

    This asserts the CURRENT, deliberate fallthrough rather than a desired one: it
    protects live flows and should not be removed for a benchmark's convenience.
    It is pinned here so anyone reading the head-to-head knows that a missing env
    var yields incumbent-vs-incumbent, and knows to verify a run against
    `llm_audit.provider` rather than against the value they believe they set.
    """
    gw = gateway(vllm_base_url="http://lan:8048", llm_force_provider="glm")
    assert "glm" not in gw._providers
    assert gw._active_provider_name() == "vllm"


def test_every_tier_resolves_to_the_one_hosted_glm_model(gateway):
    """It serves a single model; reporting tier aliases it never heard of is a lie."""
    gw = gateway(glm_base_url="http://host:8008", llm_force_provider="glm")
    assert set(gw.status()["tier_to_model"].values()) == {settings.glm_model}


def test_glm_gets_a_transport_budget_outside_the_rooms_own_guard(gateway):
    """DEF392/DEF394's derived default must actually land on this new provider.

    Not a re-test of DEF394: it checks that CR217 did not opt out of it by passing
    an explicit timeout. If the transport budget sat inside the Room's
    `asyncio.wait_for`, the guard could never fire and a slow call would become a
    fail-safe PASS — which in a benchmark reads as the model refusing to trade.
    """
    gw = gateway(glm_base_url="http://host:8008")
    transport = gw._providers["glm"]._client.timeout.read
    assert transport > _AGENT_LLM_TIMEOUT_S, (
        f"transport {transport}s must exceed the Room guard {_AGENT_LLM_TIMEOUT_S}s"
    )


def test_no_token_floor_is_imposed_on_glm(gateway):
    """Kimi needs a floor because reasoning eats its budget; GLM measurably does not.

    Measured 2026-09-01 on a 3,311-token PM-shaped prompt: `reasoning_content` was
    empty and the answer arrived in 284-333 visible tokens. Silently raising
    max_tokens for one arm of a head-to-head would change what is being compared.
    """
    gw = gateway(glm_base_url="http://host:8008")
    assert gw._providers["glm"]._max_tokens_floor is None
