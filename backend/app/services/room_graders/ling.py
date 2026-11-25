"""CR267 WP-23: the on-prem Room grader, Ling on the gateway's `vllm_fallback` slot.

Saiful 2026-11-25: "Ling, after a fit run". The same grader as `deepinfra` in everything
that is not transport: `ProductionPlanGrader` owns the question set, the five phrasings of
the two fragile questions, the split rule, the structured `trade_proposed` and the
overload retry (`production_plan.py`), so this grader answers the same plan and only
the model behind it differs. Nothing here runs unless `ROOM_GRADER=ling`.

Transport. Calls go through the project's LLM gateway, pinned to the `vllm_fallback`
provider slot (`HostedLLMGrader`'s `provider_name` pin: never failed over, never chosen by
the desks' preference order). Ling is a separate on-prem host and a different model from
the desks (`vllm`/ami-llm), so a Room is graded by a model that did not write it.

Thinking. Ling is a reasoning-capable model. Measured 2026-11-25 on `ling-3.0-flash-fin-fp4`
with no thinking switch and a 64-token budget: the reply was free-text reasoning in
`content` (no reasoning parser), cut at the budget, and the `response_format` json_schema
did not hold. Every grader call therefore carries `chat_template_kwargs.enable_thinking=false`
as a per-call override (`request_overrides`, merged into the slot's own kwargs by the gateway),
so the grade does not depend on how `VLLM_FALLBACK_EXTRA_BODY_JSON` or the desks'
`VLLM_ENABLE_THINKING` happen to be set. A reply that is still not yes/no is counted in
`extra.unparsed_questions` and leaves the question not computable; a reply cut at the budget
fails the grade. Neither becomes a verdict.

Bear question. Ling asks `bear_objection_answered` in its own wording (`ling_variants.BEAR_V2`,
tag `bear=v2`), because on the shared wording it answered yes in 296 of 300 Rooms against
DeepInfra's 91. Only the question's wording and system prompt differ; the plan around it is the
shared one. The tag is part of the grader version, so Rooms graded with it are keyed apart from
Rooms graded with the shared wording.

The grader version names the served model, so changing `VLLM_FALLBACK_MODEL` re-keys the
policy version (and every Room keyed by it). `extra.served_model` records the model id the
server reported on the calls.
"""

from __future__ import annotations

from typing import Any

from app.services.room_graders.ling_variants import BEAR_V2, BEAR_V2_TAG
from app.services.room_graders.production_plan import ProductionPlanGrader, plan_version_suffix

GRADER_NAME = "ling"
SLOT = "vllm_fallback"
THINKING_OFF: dict[str, Any] = {"chat_template_kwargs": {"enable_thinking": False}}


def grader_version(model: str, *, bear_variant: bool = True) -> str:
    """The pinned model, the shared production plan, the thinking switch and the bear wording."""
    base = f"{GRADER_NAME}:{model}{plan_version_suffix()}|think=off"
    return f"{base}|{BEAR_V2_TAG}" if bear_variant else base


class LingGrader(ProductionPlanGrader):
    name = GRADER_NAME

    def __init__(
        self, *, model: str, timeout_s: float = 60.0, gateway: Any = None,
        bear_variant: bool = True,
    ) -> None:
        model = (model or "").strip()
        if not model or model.lower().endswith("latest"):
            raise ValueError("the Ling grader needs a pinned model id, never empty or 'latest'")
        super().__init__(
            SLOT,
            timeout_s=timeout_s,
            version=grader_version(model, bear_variant=bear_variant),
            gateway=gateway,
            extra_request_overrides=THINKING_OFF,
            variants=(BEAR_V2,) if bear_variant else (),
        )
        self._model = model


def build_from_settings() -> LingGrader:
    from app.core.config import settings

    if not settings.vllm_fallback_base_url.strip():
        raise ValueError(
            "ROOM_GRADER=ling needs the vllm_fallback slot: VLLM_FALLBACK_BASE_URL is empty"
        )
    return LingGrader(
        model=settings.vllm_fallback_model,
        timeout_s=settings.room_grader_ling_timeout_s,
    )
