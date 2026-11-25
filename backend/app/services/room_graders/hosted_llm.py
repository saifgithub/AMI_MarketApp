"""CR267 WP-22: the hosted-model grader, at temperature 0 with constrained answers.

Asks each q1 question as its own yes/no call through the project's LLM gateway
(never a new HTTP client), pinned to a named provider slot passed by the caller
so no vendor is hardcoded. Token probabilities are requested through the
gateway's per-call `request_overrides`; a provider that returns none gets a
second 1-5 score call instead, and `extra["logprobs"]` records which happened
because the missing probabilities are a minus under "control" in the bake-off.
"""

from __future__ import annotations

import asyncio
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.services.llm_gateway import ChatMessage, OutputConstraint, get_llm_gateway
from app.services.room_grader_contract import (
    QUESTION_SET_VERSION,
    Answer,
    GraderResult,
    QuestionAnswer,
    RoomTranscript,
)
from app.services.room_graders.questions import (
    Question,
    load_question_set,
    render_transcript,
)

AUDIT_FLOW = "room_grader"

_SYSTEM_YESNO = (
    "You grade one finished investment-committee debate. Answer the single "
    "question at the end with yes or no, using only what the debate says. "
    "Reply with JSON only."
)
_SYSTEM_SCORE = (
    "You grade one finished investment-committee debate. Rate how strongly the "
    "debate supports a yes answer to the single question at the end, from 1 "
    "(clearly no) to 5 (clearly yes), using only what the debate says. Reply "
    "with JSON only."
)

_YESNO_CONSTRAINT = OutputConstraint(
    name="room_grader_yesno",
    json_schema={
        "type": "object",
        "properties": {"answer": {"type": "string", "enum": ["yes", "no"]}},
        "required": ["answer"],
        "additionalProperties": False,
    },
)
_SCORE_CONSTRAINT = OutputConstraint(
    name="room_grader_score",
    json_schema={
        "type": "object",
        "properties": {"score": {"type": "integer", "enum": [1, 2, 3, 4, 5]}},
        "required": ["score"],
        "additionalProperties": False,
    },
)


class _CallFailed(RuntimeError):
    pass


_SAME_PHRASING: Any = object()


def _run_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _norm(token: Any) -> str:
    return str(token).strip().strip('"').strip().lower()


def p_yes_from_logprobs(content: Any) -> float | None:
    """P(yes) among {yes, no} at the answer token, from OpenAI-style
    `choices[0].logprobs.content`. None when the answer token or either side's
    probability mass cannot be read."""
    if not isinstance(content, list):
        return None
    for entry in content:
        if not isinstance(entry, dict) or _norm(entry.get("token")) not in ("yes", "no"):
            continue
        mass = {"yes": 0.0, "no": 0.0}
        alts = list(entry.get("top_logprobs") or [])
        if "logprob" in entry:
            alts.append({"token": entry.get("token"), "logprob": entry["logprob"]})
        seen: set[tuple[str, float]] = set()
        for alt in alts:
            if not isinstance(alt, dict):
                continue
            side = _norm(alt.get("token"))
            lp = alt.get("logprob")
            if side not in mass or not isinstance(lp, (int, float)):
                continue
            if (side, float(lp)) in seen:
                continue
            seen.add((side, float(lp)))
            mass[side] += math.exp(float(lp))
        total = mass["yes"] + mass["no"]
        return mass["yes"] / total if total > 0 else None
    return None


def _json_field(text: str, field: str) -> Any:
    body = text.strip()
    if body.startswith("```"):
        body = body.strip("`").removeprefix("json").strip()
    try:
        obj = json.loads(body)
    except ValueError:
        return None
    return obj.get(field) if isinstance(obj, dict) else None


class HostedLLMGrader:
    name = "hosted_llm"

    def __init__(
        self,
        slot: str,
        *,
        version: str | None = None,
        gateway: Any = None,
        close_band: float = 0.2,
        phrasing: int | None = None,
        use_logprobs: bool = True,
        max_tokens: int = 64,
        extra_request_overrides: dict[str, Any] | None = None,
    ) -> None:
        if not slot or not slot.strip():
            raise ValueError("HostedLLMGrader needs an explicit provider slot")
        self.slot = slot.strip()
        self.version = version or f"hosted:{self.slot}"
        self._gateway = gateway
        self._close_band = close_band
        self._phrasing = phrasing
        self._use_logprobs = use_logprobs
        self._max_tokens = max_tokens
        self._extra_overrides = dict(extra_request_overrides or {})

    def _gw(self) -> Any:
        return self._gateway or get_llm_gateway()

    async def _ask(
        self, system: str, user: str, constraint: OutputConstraint, *, logprobs: bool
    ) -> tuple[str, dict[str, Any]]:
        overrides: dict[str, Any] = {"temperature": 0, **self._extra_overrides}
        if logprobs:
            overrides.update({"logprobs": True, "top_logprobs": 5})
        meta: dict[str, Any] = {"request_overrides": overrides}
        chunks: list[str] = []
        async for chunk in self._gw().stream_chat(
            system_prompt=system,
            messages=[ChatMessage(role="user", content=user)],
            model_tier="cheap",
            max_tokens=self._max_tokens,
            audit_flow=AUDIT_FLOW,
            meta=meta,
            constraint=constraint,
            provider_name=self.slot,
        ):
            chunks.append(chunk)
        if meta.get("stream_error"):
            raise _CallFailed(f"provider error: {str(meta['stream_error'])[:200]}")
        if meta.get("finish_reason") == "length":
            raise _CallFailed("reply cut off at max_tokens")
        return "".join(chunks), meta

    def _cost(self, meta: dict[str, Any]) -> float | None:
        try:
            from app.services.llm_spend import compute_cost_usd

            usage = meta.get("usage") or {}
            return compute_cost_usd(
                [meta.get("reported_model"), meta.get("configured_model")],
                usage.get("input_tokens"),
                usage.get("output_tokens"),
            )
        except Exception:  # noqa: BLE001 — cost is evidence, never a failure
            return None

    async def _grade_question(
        self,
        q: Question,
        rendered: str,
        tally: dict[str, Any],
        phrasing: int | None = _SAME_PHRASING,
        system: str | None = None,
    ) -> QuestionAnswer:
        if phrasing is _SAME_PHRASING:
            phrasing = self._phrasing
        prompt = (
            f"{rendered}\n\n---\nQuestion: {q.text_for(phrasing)}\n"
            f"yes means: {q.yes}\nno means: {q.no}"
        )
        text, meta = await self._ask(
            system or _SYSTEM_YESNO, prompt, _YESNO_CONSTRAINT, logprobs=self._use_logprobs
        )
        tally["calls"].append(meta)
        raw = _json_field(text, "answer")
        word = _norm(raw if raw is not None else text)
        if word not in ("yes", "no"):
            tally["unparsed"] += 1
            return QuestionAnswer(
                q.id, Answer.NOT_COMPUTABLE, rationale="reply was not a yes/no answer"
            )
        answer = Answer.YES if word == "yes" else Answer.NO

        p_yes = p_yes_from_logprobs(meta.get("logprobs"))
        if p_yes is None:
            tally["logprobs_missing"] += 1
            p_yes = await self._score_fallback(q, rendered, tally, phrasing)
        if p_yes is None:
            return QuestionAnswer(
                q.id, answer, rationale="no probability or score could be read"
            )
        return QuestionAnswer(
            question=q.id,
            answer=answer,
            confidence=p_yes if answer is Answer.YES else 1.0 - p_yes,
            close=abs(p_yes - 0.5) <= self._close_band,
        )

    async def _score_fallback(
        self,
        q: Question,
        rendered: str,
        tally: dict[str, Any],
        phrasing: int | None,
    ) -> float | None:
        prompt = f"{rendered}\n\n---\nQuestion: {q.text_for(phrasing)}"
        text, meta = await self._ask(
            _SYSTEM_SCORE, prompt, _SCORE_CONSTRAINT, logprobs=False
        )
        tally["calls"].append(meta)
        score = _json_field(text, "score")
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 5:
            tally["score_unparsed"] += 1
            return None
        return (score - 1) / 4

    async def _grade_all(self, transcript: RoomTranscript, tally: dict[str, Any]):
        rendered = render_transcript(transcript)
        answers = []
        for q in load_question_set().questions:
            answers.append(await self._grade_question(q, rendered, tally))
        return tuple(answers)

    def grade(self, transcript: RoomTranscript) -> GraderResult:
        started = time.perf_counter()
        try:
            return _run_sync(self.agrade(transcript))
        except Exception as exc:  # noqa: BLE001 — a grader never raises out
            return GraderResult(
                grader=self.name,
                grader_version=self.version,
                question_set_version=QUESTION_SET_VERSION,
                answers=(),
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=f"{type(exc).__name__}: {str(exc)[:300]}",
            )

    async def agrade(self, transcript: RoomTranscript) -> GraderResult:
        """Async entry for callers already on an event loop. The gateway's
        provider clients are bound to the loop that first used them, so a
        harness running many rooms should await this rather than call `grade`."""
        started = time.perf_counter()
        tally: dict[str, Any] = {
            "calls": [],
            "logprobs_missing": 0,
            "unparsed": 0,
            "score_unparsed": 0,
        }
        try:
            answers = await self._grade_all(transcript, tally)
        except Exception as exc:  # noqa: BLE001 — a grader never raises out
            return GraderResult(
                grader=self.name,
                grader_version=self.version,
                question_set_version=QUESTION_SET_VERSION,
                answers=(),
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=f"{type(exc).__name__}: {str(exc)[:300]}",
            )
        costs = [c for c in (self._cost(m) for m in tally["calls"]) if c is not None]
        served = next(
            (m.get("reported_model") for m in tally["calls"] if m.get("reported_model")),
            None,
        )
        return GraderResult(
            grader=self.name,
            grader_version=self.version,
            question_set_version=QUESTION_SET_VERSION,
            answers=answers,
            latency_ms=int((time.perf_counter() - started) * 1000),
            cost_usd=sum(costs) if costs else None,
            extra={
                "logprobs": tally["logprobs_missing"] == 0,
                "logprobs_missing_questions": tally["logprobs_missing"],
                "unparsed_questions": tally["unparsed"],
                "score_unparsed_questions": tally["score_unparsed"],
                "temperature": 0,
                "slot": self.slot,
                "served_model": served,
                "calls": len(tally["calls"]),
            },
        )
