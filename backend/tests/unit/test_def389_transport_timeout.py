"""DEF389 — the transport timeout must sit OUTSIDE the Room's own guard.

The Room wraps every agent call in a 90s `asyncio.wait_for`
(`room_runner._AGENT_LLM_TIMEOUT_S`) and logs `room_agent_timeout` /
`room_pm_timeout` when it trips. That guard was unreachable: the httpx client
underneath carried a hardcoded 60s read timeout, so a slow completion always
died in transport first. The exception it raises, `httpx.ReadTimeout()`, has an
EMPTY `str()`, so the failure surfaced as `room_pm_llm_failed error=""` — and
the Room then fell back to its DEF059 fail-safe PASS, a completed run carrying
a verdict that no downstream consumer can tell apart from a decision.

These tests pin the ordering and the wiring, not the numbers: raising either
budget is fine, inverting them is not.
"""

from __future__ import annotations

import inspect

import httpx
import pytest

from app.core.config import settings
from app.services import llm_gateway
from app.services.room_runner import _AGENT_LLM_TIMEOUT_S


def test_transport_budget_exceeds_the_orchestration_budget():
    """The outer guard must be the one that fires, so its log line is the signal."""
    assert settings.vllm_request_timeout_s > _AGENT_LLM_TIMEOUT_S, (
        f"transport {settings.vllm_request_timeout_s}s <= agent "
        f"{_AGENT_LLM_TIMEOUT_S}s — the Room's timeout guard is dead code and "
        "slow completions will surface as fail-safe PASS verdicts"
    )


def test_the_setting_actually_reaches_the_provider():
    """DEF038/DEF063 class: a setting that exists and never reaches the client.

    The provider previously took the 60.0 default because nothing passed the
    value in, which is precisely how this stayed invisible.
    """
    src = inspect.getsource(llm_gateway.LLMGateway.__init__)
    assert "timeout_seconds=settings.vllm_request_timeout_s" in src, (
        "VLLMProvider is constructed without the configured timeout, so it "
        "silently falls back to the hardcoded default"
    )


def test_a_bare_read_timeout_stringifies_to_nothing():
    """The premise of the logging fix — asserted, not assumed."""
    assert str(httpx.ReadTimeout("")) == ""


@pytest.mark.parametrize(
    "exc", [httpx.ReadTimeout(""), httpx.ConnectTimeout(""), httpx.PoolTimeout("")]
)
def test_the_log_expression_always_names_the_failure(exc):
    """`str(exc) or repr(exc)` is what both call sites now use."""
    rendered = (str(exc) or repr(exc))[:200]
    assert rendered, "the error field would be blank"
    assert type(exc).__name__ in rendered


def test_both_call_sites_use_the_fallback_expression():
    import app.services.room_runner as rr

    src = inspect.getsource(rr)
    assert src.count("(str(exc) or repr(exc))[:200]") == 2, (
        "room_agent_llm_failed and room_pm_llm_failed must both name the "
        "exception type when str() is empty"
    )


def test_the_configured_budget_covers_the_measured_five_way_fan_out():
    """Measured 2026-08-31 on an idle server: 45.9s for the slowest of 5 draws.

    `pm_self_consistency_samples` issues them concurrently, so that is the
    figure the budget has to clear — with room for a second convene and live
    users on the same box.
    """
    measured_worst_case_s = 45.9
    assert settings.vllm_request_timeout_s >= 2 * measured_worst_case_s
