"""CR267 WP-23 gate S3: the Room grader that production runs, DeepInfra DeepSeek-V4-Flash.

Saiful's pick (2026-11-23) from the WP-22 bake-off: the hosted model at temperature 0,
for the GRADER ONLY. This is `HostedLLMGrader` (the class the bake-off scored) with the
three changes the bake-off's own findings called for, and nothing else:

1. It calls the hosted endpoint directly with its own OpenAI-compatible client, not
   through the LLM gateway, so Alpha's desks stay on-prem and `LLM_PROVIDER_ALLOWLIST`
   is not widened. It is the same `VLLMProvider(kind="openai")` and the same grounding
   directive the bake-off's gateway slot used, so what was measured is what runs.
2. `trade_proposed` is never asked of the model: the structured trade owns it
   (`room_grader_contract.trade_proposed_answer`; a trade block that cannot say what
   was proposed is not computable, never guessed).
3. The two wording-fragile deciding questions (`bear_objection_answered` 90%,
   `thesis_material_directional` 70% in the bake-off) are asked over all five q1
   phrasings, concurrently with a bounded per-call timeout, and the majority wins. Any
   split marks the question `close`, which feeds the rule's Contested band.

A failed or timed-out call fails the whole grade (a `GraderResult` with `error`), which
the rule turns into "decision unavailable". The grader version names the model and the
averaging, so changing either re-keys the policy version. Change 3 and the retry rule live
in `production_plan.ProductionPlanGrader`, shared with `LingGrader`; this module is the
DeepInfra transport only.
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import Any, AsyncIterator, Callable

from app.services.llm_gateway import (
    ChatMessage,
    OutputConstraint,
    VLLMProvider,
    prepend_grounding_directive,
)
from app.services.room_grader_contract import RoomTranscript
from app.services.room_graders.production_plan import (  # noqa: F401 — re-exported: tests and the fit tool read them here
    AVERAGED_QUESTIONS,
    CLOSE_BAND,
    MAX_CONCURRENT_CALLS,
    OVERLOAD_RETRIES,
    PHRASING_COUNT,
    SPLIT_CLOSE_MIN_MINORITY,
    ProductionPlanGrader,
    average_votes,
    is_overload,
    plan_version_suffix,
)

GRADER_NAME = "deepinfra"

_PROVIDER_NAME = "room_grader_deepinfra"
_ACTIVE_GATEWAY: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "room_grader_deepinfra_gateway", default=None
)


def grader_version(model: str) -> str:
    """Everything that changes what this grader answers, in the string the policy
    version hashes: the pinned model plus the shared production plan (temperature,
    the averaged questions, the split rule, the structured trade)."""
    return f"{model}{plan_version_suffix()}"


class _DirectGateway:
    """The slice of the gateway's `stream_chat` the hosted grader uses, over one
    private provider. Applies the grounding directive the gateway would have."""

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    async def stream_chat(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        model_tier: str = "cheap",
        max_tokens: int = 1024,
        meta: dict[str, Any] | None = None,
        constraint: OutputConstraint | None = None,
        **_ignored: Any,
    ) -> AsyncIterator[str]:
        async for chunk in self._provider.stream_chat(
            system_prompt=prepend_grounding_directive(system_prompt),
            messages=messages,
            model_tier=model_tier,
            max_tokens=max_tokens,
            meta=meta,
            constraint=constraint,
        ):
            yield chunk


class DeepInfraGrader(ProductionPlanGrader):
    name = GRADER_NAME

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        timeout_s: float = 30.0,
        provider_factory: Callable[[], Any] | None = None,
    ) -> None:
        model = (model or "").strip()
        if not model or model.lower().endswith("latest"):
            raise ValueError("the DeepInfra grader needs a pinned model id, never empty or 'latest'")
        if not (api_key or "").strip():
            raise ValueError("the DeepInfra grader has no API key")
        if not (base_url or "").strip():
            raise ValueError("the DeepInfra grader has no base URL")
        super().__init__(_PROVIDER_NAME, timeout_s=timeout_s, version=grader_version(model))
        self._model = model
        self._provider_factory = provider_factory or (
            lambda: VLLMProvider(
                base_url=base_url,
                model_name=model,
                api_key=api_key,
                timeout_seconds=self._timeout_s,
                kind="openai",
                name=_PROVIDER_NAME,
                max_retries=0,
            )
        )

    def _gw(self) -> Any:
        gateway = _ACTIVE_GATEWAY.get()
        if gateway is None:
            raise RuntimeError("DeepInfraGrader must be run through grade()/agrade()")
        return gateway

    async def agrade(self, transcript: RoomTranscript):
        provider = self._provider_factory()
        token = _ACTIVE_GATEWAY.set(_DirectGateway(provider))
        try:
            return await super().agrade(transcript)
        finally:
            _ACTIVE_GATEWAY.reset(token)
            close = getattr(provider, "aclose", None)
            if close is not None:
                with contextlib.suppress(Exception):
                    await close()


def build_from_settings() -> DeepInfraGrader:
    from app.core.config import settings

    return DeepInfraGrader(
        base_url=settings.room_grader_deepinfra_base_url,
        model=settings.room_grader_deepinfra_model,
        api_key=settings.room_grader_deepinfra_api_key,
        timeout_s=settings.room_grader_deepinfra_timeout_s,
    )
