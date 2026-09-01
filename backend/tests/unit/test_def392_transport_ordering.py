"""DEF392 — the transport-vs-guard ordering must hold for EVERY provider, and at boot.

DEF389 fixed the ordering for one provider and pinned it with a test. Both halves
were narrower than the defect:

* `OpenAICompatibleProvider.__init__` defaulted `timeout_seconds` to a literal
  `60.0`. Only the vLLM registration passed a value, so kimi, deepseek, qwen and
  gemini — which pass nothing — each carried a 60s httpx client INSIDE the 180s
  `room_agent_timeout_s` guard. When one of those is selected (via
  `provider_policy.pick_provider` or `LLM_FORCE_PROVIDER`), every slow call dies
  in transport first, `httpx.ReadTimeout` stringifies to the empty string, and the
  Room falls back to its DEF059 fail-safe PASS: a completed run carrying a verdict
  indistinguishable from a decision.
* The invariant was enforced by this lane's predecessor test only — nothing
  checked the pair on a real boot, so `ROOM_AGENT_TIMEOUT_S=800` with
  `VLLM_REQUEST_TIMEOUT_S=45` started the container with the ordering inverted.

So the fix is derivation (the default comes from the guard, so it cannot be left
behind when the guard moves) plus a boot-time `model_validator`. These tests
assert both by reading the objects that actually exist, not by restating numbers.
"""

from __future__ import annotations

import inspect
import re

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.services import llm_gateway
from app.services.llm_gateway import (
    LLMGateway,
    OpenAICompatibleProvider,
    VLLMProvider,
)


def _register_every_provider(monkeypatch) -> LLMGateway:
    """A gateway with all five OpenAI-compatible registrations live.

    Each registration is gated on the presence of its key (CR040: presence turns
    the feature on), so on a test box with no keys the providers dict holds only
    `mock` and an assertion over it would pass vacuously.
    """
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "vllm_base_url", "http://192.0.2.1:8000")
    monkeypatch.setattr(cfg.settings, "kimi_api_key", "kimi-fake")
    monkeypatch.setattr(cfg.settings, "deepseek_api_key", "deepseek-fake")
    monkeypatch.setattr(cfg.settings, "dashscope_api_key", "qwen-fake")
    monkeypatch.setattr(cfg.settings, "google_ai_api_key", "gemini-fake")
    return LLMGateway()


def test_every_registered_openai_compatible_provider_sits_outside_the_guard(
    monkeypatch,
):
    """The DEF389 pin read one setting; this reads every client that exists.

    `vllm_request_timeout_s` exceeding the guard says nothing about the four
    providers that never receive that setting — which is precisely how DEF389
    came to be a one-provider fix.
    """
    gateway = _register_every_provider(monkeypatch)
    compat = {
        name: prov
        for name, prov in gateway._providers.items()
        if isinstance(prov, OpenAICompatibleProvider)
    }
    assert {"vllm", "kimi", "deepseek", "qwen", "gemini"} <= set(compat), (
        f"expected all five OpenAI-compatible registrations, got {sorted(compat)}"
    )
    for name, prov in compat.items():
        transport_s = prov._client.timeout.read
        assert transport_s > settings.room_agent_timeout_s, (
            f"{name}: transport {transport_s}s <= guard "
            f"{settings.room_agent_timeout_s}s — the Room's timeout guard is "
            "unreachable on this provider and slow calls will surface as "
            "empty-string errors feeding a fail-safe PASS"
        )


def test_a_bare_provider_derives_its_budget_from_the_guard(monkeypatch):
    """Not merely "is bigger", but "tracks the guard".

    A second magic literal would satisfy a single `> 180` assertion forever. Move
    the guard and a derived default moves with it; a constant does not.
    """
    from app.core import config as cfg

    bare = OpenAICompatibleProvider(
        name="bare", base_url="http://192.0.2.1:8000", model_name="m"
    )
    assert bare._client.timeout.read > settings.room_agent_timeout_s

    for guard in (15.0, settings.room_agent_timeout_s, 900.0):
        monkeypatch.setattr(cfg.settings, "room_agent_timeout_s", guard)
        moved = OpenAICompatibleProvider(
            name="bare", base_url="http://192.0.2.1:8000", model_name="m"
        )
        assert moved._client.timeout.read > guard, (
            f"a guard of {guard}s produced a transport budget of "
            f"{moved._client.timeout.read}s — the default is not derived from "
            "the guard, it is a literal that happens to clear today's value"
        )


def test_explicit_timeout_still_wins(monkeypatch):
    """`None` means "derive it", not "ignore the caller".

    The vLLM registration passes `settings.vllm_request_timeout_s` explicitly and
    DEF389's own pin depends on that path staying intact; a derivation that
    overrode an explicit value would silently replace one hardcoded budget with
    another.
    """
    explicit = OpenAICompatibleProvider(
        name="explicit",
        base_url="http://192.0.2.1:8000",
        model_name="m",
        timeout_seconds=1234.5,
    )
    assert explicit._client.timeout.read == 1234.5


def test_the_config_validator_refuses_an_inverted_pair():
    """Each field is in bounds; the PAIR is what is wrong, so field bounds cannot catch it."""
    with pytest.raises(ValidationError, match="room_agent_timeout_s"):
        Settings(vllm_request_timeout_s=45.0, room_agent_timeout_s=800.0)
    # `<=`, not `<`: an equal pair is the same failure — the guard still cannot
    # win the race, it just ties.
    with pytest.raises(ValidationError):
        Settings(vllm_request_timeout_s=180.0, room_agent_timeout_s=180.0)


def test_the_config_validator_accepts_the_shipped_defaults():
    """A validator that rejects its own defaults is a broken deploy, not a guard."""
    live = Settings()
    assert live.vllm_request_timeout_s > live.room_agent_timeout_s
    assert Settings(vllm_request_timeout_s=200.0, room_agent_timeout_s=120.0)


def test_no_timeout_literal_is_left_in_the_provider_constructors():
    """The defect's shape was a default value, so the shape itself is banned.

    `inspect.signature` catches the live default; the source scan catches a
    re-hardcoded default in either constructor before a future reader has to
    instantiate anything to notice it.
    """
    for cls in (OpenAICompatibleProvider, VLLMProvider):
        param = inspect.signature(cls.__init__).parameters["timeout_seconds"]
        assert param.default is None, (
            f"{cls.__name__}.timeout_seconds defaults to {param.default!r}; "
            "DEF392 requires the default to be derived from the guard, i.e. None"
        )
    # Anchored to the START of a stripped line so the scan reads DECLARATIONS
    # only. An unanchored search matches this module's own prose: the comment in
    # `llm_gateway` that explains the defect quotes the banned literal verbatim,
    # and the first version of this guard failed on that quote — the guard
    # catching its own explanation rather than a regression.
    stray = [
        line.strip()
        for line in inspect.getsource(llm_gateway).splitlines()
        if re.match(r"timeout_seconds:\s*float(?! \| None)", line.strip())
    ]
    assert not stray, f"non-derived timeout default(s) reintroduced: {stray}"
