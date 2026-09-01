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
import re

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


def test_every_pm_path_call_site_uses_the_fallback_expression():
    """DEF390: this pin said 2, and there were 3.

    DEF389 fixed `room_agent_llm_failed` and `room_pm_llm_failed` and described them as "both log
    sites". `room_pm_reformat_failed` is a third handler on the same PM path, catching the same bare
    transport timeout, and it kept `str(exc)[:200]` — so the reformat recovery call still logged
    `error=""` into the same DEF059 fail-safe PASS. An `== 2` pin does not merely miss the third
    site, it actively locks it out: fixing it would have failed this test.

    Counting every `except Exception as exc` handler is what makes the pin grow with the file
    instead of pinning it to the day it was written (failure_patterns P6 — a guard on growing data
    is a floor, not a pin).
    """
    import app.services.room_runner as rr

    src = inspect.getsource(rr)
    guarded = re.findall(r"error=\(str\(exc\) or repr\(exc\)\)\[:200\]", src)
    assert len(guarded) >= 3, (
        f"expected at least 3 guarded PM-path call sites, found {len(guarded)}"
    )
    for name in ("room_agent_llm_failed", "room_pm_llm_failed", "room_pm_reformat_failed"):
        idx = src.index(name)
        # Anchor on that event's own `error=` kwarg, however far the intervening comments push it,
        # rather than on a fixed-width window that a later comment would silently slide out of.
        err = src.index("error=", idx)
        rendered = src[err:err + 60]
        assert "(str(exc) or repr(exc))" in rendered, (
            f"{name} must name the exception type when str() is empty; "
            f"a bare httpx.ReadTimeout has an empty str(). Found: {rendered.splitlines()[0]!r}"
        )
    # Scope note: room_runner has other `error=str(exc)[:200]` handlers (earnings, sector context,
    # option menu...). They are not in scope here — they do not wrap a streaming LLM call, so the
    # empty-str() transport exception this pin exists for cannot reach them. Widen the tuple above
    # if one ever does.


def test_the_configured_budget_covers_the_measured_five_way_fan_out():
    """Measured 2026-08-31 on an idle server: 45.9s for the slowest of 5 draws.

    `pm_self_consistency_samples` issues them concurrently, so that is the
    figure the budget has to clear — with room for a second convene and live
    users on the same box.
    """
    measured_worst_case_s = 45.9
    assert settings.vllm_request_timeout_s >= 2 * measured_worst_case_s


def test_the_agent_budget_clears_the_measured_pm_tail():
    """DEF390 — sized from llm_audit, not from a round number.

    290 real portfolio_manager calls on qwen3.8-flash-next: mean 42.4s, mode
    35-40s, tail visible to 85s. The old 90s cap sat at ~2.3x the mode and
    clipped ~7% of calls into a fail-safe PASS.
    """
    observed_pm_mean_s = 42.4
    assert settings.room_agent_timeout_s >= 4 * observed_pm_mean_s / 1.5, (
        "the agent budget is back inside the measured PM tail"
    )


def test_the_agent_budget_is_configurable_not_hardcoded():
    """The whole DEF389/DEF390 class: a latency constant nobody revisits.

    Both budgets were module-level literals when the served model changed under
    them (CR211), and neither was re-checked because neither was a setting.
    """
    import app.services.room_runner as rr

    assert rr._AGENT_LLM_TIMEOUT_S == settings.room_agent_timeout_s

    src = inspect.getsource(rr)
    assert "_AGENT_LLM_TIMEOUT_S = settings.room_agent_timeout_s" in src, (
        "the Room's agent budget is hardcoded again"
    )
