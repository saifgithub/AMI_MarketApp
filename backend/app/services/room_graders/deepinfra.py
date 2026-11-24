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
averaging, so changing either re-keys the policy version.
"""

from __future__ import annotations

import asyncio
import random
import contextlib
import contextvars
from typing import Any, AsyncIterator, Callable, Sequence

from app.services.llm_gateway import (
    ChatMessage,
    OutputConstraint,
    VLLMProvider,
    prepend_grounding_directive,
)
from app.services.room_grader_contract import (
    Answer,
    QuestionAnswer,
    QuestionId,
    RoomTranscript,
    trade_proposed_answer,
)
from app.services.room_graders.hosted_llm import HostedLLMGrader, _CallFailed
from app.services.room_graders.questions import Question, load_question_set, render_transcript

GRADER_NAME = "deepinfra"

AVERAGED_QUESTIONS: tuple[QuestionId, ...] = (
    QuestionId.BEAR_OBJECTION_ANSWERED,
    QuestionId.THESIS_MATERIAL_DIRECTIONAL,
)
PHRASING_COUNT = 5
MAX_CONCURRENT_CALLS = 8

# DeepInfra sheds load with HTTP 429 "engine_overloaded" (and 503). Measured on
# the first WP-23 fit run, 2026-11-24: 14 of 50 Rooms lost one of their 13
# calls to it, and one lost call makes the whole Room "decision unavailable".
# Overload is retried with jittered backoff; any other failure is not.
OVERLOAD_RETRIES = 3
OVERLOAD_BACKOFF_S = 1.0
_OVERLOAD_MARKERS = ("HTTP 429", "HTTP 503", "engine_overloaded", "Model busy")


def is_overload(exc: BaseException) -> bool:
    text = str(exc)
    return any(m in text for m in _OVERLOAD_MARKERS)
CLOSE_BAND = 0.2

_PROVIDER_NAME = "room_grader_deepinfra"
_ACTIVE_GATEWAY: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "room_grader_deepinfra_gateway", default=None
)


# A split is "close" only when the minority holds at least this many phrasings.
# Saiful 2026-11-24 (WP-23 fit, `wp23_fit_2026-11-24.md`): a 4-1 split is a clear
# answer; only 3-2 is close. Any split (1) gave 22% Contested; 2 gives ~17%.
SPLIT_CLOSE_MIN_MINORITY = 2


def grader_version(model: str) -> str:
    """Everything that changes what this grader answers, in the string the policy
    version hashes: the pinned model, temperature, the averaged questions and the
    structured trade."""
    averaged = "+".join(q.value for q in AVERAGED_QUESTIONS)
    return (f"{model}|t0|avg{PHRASING_COUNT}:{averaged}|split{SPLIT_CLOSE_MIN_MINORITY}"
            f"|trade=structure")


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


def average_votes(
    qid: QuestionId, votes: Sequence[QuestionAnswer], close_band: float = CLOSE_BAND,
) -> QuestionAnswer:
    """One answer from several phrasings of the same question: the majority, with
    a split marked `close` when the minority holds at least
    `SPLIT_CLOSE_MIN_MINORITY` phrasings (3-2, not 4-1). A vote that is not
    yes/no leaves the question not computable rather than being dropped."""
    if not votes:
        return QuestionAnswer(qid, Answer.NOT_COMPUTABLE, rationale="no phrasing answered")
    if any(v.answer not in (Answer.YES, Answer.NO) for v in votes):
        return QuestionAnswer(
            qid, Answer.NOT_COMPUTABLE,
            rationale="a phrasing returned no yes/no answer",
        )
    yes = sum(v.answer is Answer.YES for v in votes)
    no = len(votes) - yes
    answer = Answer.YES if yes > no else Answer.NO
    split = min(yes, no) >= SPLIT_CLOSE_MIN_MINORITY
    p_yes_votes = [
        (v.confidence if v.answer is Answer.YES else 1.0 - v.confidence)
        for v in votes if v.confidence is not None
    ]
    if p_yes_votes:
        p_yes = sum(p_yes_votes) / len(p_yes_votes)
        confidence = p_yes if answer is Answer.YES else 1.0 - p_yes
        near_half = abs(p_yes - 0.5) <= close_band
    else:
        confidence, near_half = None, False
    return QuestionAnswer(
        question=qid,
        answer=answer,
        confidence=confidence,
        close=split or near_half,
        rationale=f"{yes}/{len(votes)} phrasings yes" + (" (split)" if split else ""),
    )


class DeepInfraGrader(HostedLLMGrader):
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
        super().__init__(_PROVIDER_NAME, version=grader_version(model), close_band=CLOSE_BAND)
        self._model = model
        self._timeout_s = float(timeout_s)
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

    async def _grade_all(self, transcript: RoomTranscript, tally: dict[str, Any]):
        rendered = render_transcript(transcript)
        gate = asyncio.Semaphore(MAX_CONCURRENT_CALLS)

        async def vote(q: Question, phrasing: int | None) -> QuestionAnswer:
            attempt = 0
            while True:
                async with gate:
                    try:
                        return await asyncio.wait_for(
                            self._grade_question(q, rendered, tally, phrasing), self._timeout_s,
                        )
                    except asyncio.TimeoutError:
                        raise _CallFailed(
                            f"{q.id.value}: call timed out after {self._timeout_s:g}s"
                        ) from None
                    except _CallFailed as exc:
                        if attempt >= OVERLOAD_RETRIES or not is_overload(exc):
                            raise
                attempt += 1
                tally["overload_retries"] = tally.get("overload_retries", 0) + 1
                await asyncio.sleep(OVERLOAD_BACKOFF_S * (2 ** (attempt - 1)) * (0.5 + random.random()))

        plan: list[tuple[Question, list[asyncio.Task]]] = []
        tasks: list[asyncio.Task] = []
        for q in load_question_set().questions:
            if q.id is QuestionId.TRADE_PROPOSED:
                continue
            phrasings: list[int | None] = (
                list(range(PHRASING_COUNT)) if q.id in AVERAGED_QUESTIONS else [None]
            )
            mine = [asyncio.ensure_future(vote(q, p)) for p in phrasings]
            tasks.extend(mine)
            plan.append((q, mine))
        try:
            await asyncio.gather(*tasks)
        except BaseException:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

        by_q: dict[QuestionId, QuestionAnswer] = {}
        for q, mine in plan:
            votes = [t.result() for t in mine]
            by_q[q.id] = (
                average_votes(q.id, votes, self._close_band)
                if q.id in AVERAGED_QUESTIONS else votes[0]
            )
        by_q[QuestionId.TRADE_PROPOSED] = trade_proposed_answer(transcript.proposed_trade)
        return tuple(by_q[q.id] for q in load_question_set().questions)


def build_from_settings() -> DeepInfraGrader:
    from app.core.config import settings

    return DeepInfraGrader(
        base_url=settings.room_grader_deepinfra_base_url,
        model=settings.room_grader_deepinfra_model,
        api_key=settings.room_grader_deepinfra_api_key,
        timeout_s=settings.room_grader_deepinfra_timeout_s,
    )
