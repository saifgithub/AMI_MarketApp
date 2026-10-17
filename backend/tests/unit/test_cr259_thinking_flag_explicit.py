"""CR259 amendment — the vLLM provider sends `enable_thinking` EXPLICITLY.

The original knob sent `{"chat_template_kwargs": {"enable_thinking": True}}
` only when the setting was on, and sent nothing when off. That made
"thinking off" mean "the server's default" — correct for `ami-llm` (server
defaults OFF) but silently wrong for `kolibri-1`, whose vLLM server defaults
thinking ON (measured 2026-10-17: 686 of 850 completion tokens were reasoning
with no kwarg; an explicit `enable_thinking: false` took reasoning to zero).

These tests pin the amended contract: the kwarg always rides the request,
carrying the setting's value, so "off" is off on every server.
"""

from __future__ import annotations

from app.services.llm_gateway import VLLMProvider


def _provider(enable_thinking: bool) -> VLLMProvider:
    return VLLMProvider(
        base_url="http://example:8000/v1",
        model_name="any",
        enable_thinking=enable_thinking,
    )


def test_thinking_off_sends_explicit_false():
    provider = _provider(enable_thinking=False)
    assert provider._extra_body == {
        "chat_template_kwargs": {"enable_thinking": False}
    }


def test_thinking_on_sends_explicit_true():
    provider = _provider(enable_thinking=True)
    assert provider._extra_body == {
        "chat_template_kwargs": {"enable_thinking": True}
    }
