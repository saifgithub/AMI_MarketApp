"""CR281 — per-slot extra request-body JSON, so a model swap stays a config edit.

Some models need a request field the slot's `kind` does not send. The motivating
case (WP-10 scorecard §1b): Ling-3.0-flash on DeepInfra runs with thinking ON
unless the body carries `{"chat_template_kwargs": {"enable_thinking": false}}`,
and the `openai` kind sends no thinking field at all. Rather than a code edit per
model, each slot takes `<SLOT>_EXTRA_BODY_JSON`, merged into every request body
sent to that slot.

Precedence (documented, enforced):
  1. Fields the gateway sets for safety are PROTECTED and can never come from
     this setting: `model`, `messages`, `stream`, `stream_options`, `max_tokens`,
     `temperature`, `response_format` and the decoding-grammar fields. A JSON
     object naming one fails boot (loud) instead of being silently dropped.
  2. Otherwise the operator's JSON wins over the slot kind's own default for the
     same top-level key (e.g. `chat_template_kwargs` on a `vllm`-kind slot).
     The merge is shallow: the operator's value replaces the default's value.
Empty = nothing merged. Invalid JSON, or a non-object, fails boot.

Pure module: `Settings` calls `parse_extra_body` from a validator.
"""

from __future__ import annotations

import json
from typing import Any

PROTECTED_BODY_FIELDS: frozenset[str] = frozenset(
    {
        "model",
        "messages",
        "stream",
        "stream_options",
        "max_tokens",
        "temperature",
        "response_format",
        "structured_outputs",
        "guided_json",
        "guided_regex",
        "guided_choice",
        "guided_grammar",
    }
)


def parse_extra_body(setting_name: str, raw: str) -> dict[str, Any]:
    """The dict `raw` encodes ({} when blank); ValueError naming `setting_name`
    for invalid JSON, a non-object, or a protected field."""
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        value = json.loads(text)
    except ValueError as exc:
        raise ValueError(f"{setting_name} is not valid JSON ({exc.__class__.__name__}).") from None
    if not isinstance(value, dict):
        raise ValueError(f"{setting_name} must be a JSON object, got {type(value).__name__}.")
    clash = sorted(PROTECTED_BODY_FIELDS & set(value))
    if clash:
        raise ValueError(
            f"{setting_name} sets protected request field(s) {clash}: the gateway owns "
            "those (safety/grammar/budget) and they cannot be overridden by config."
        )
    return value
