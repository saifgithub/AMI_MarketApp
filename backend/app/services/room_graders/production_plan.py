"""CR267 WP-23: the Room grader's production question plan, shared by every grader that runs it.

The plan is what Saiful's gate S3 pick actually measured, independent of which model
answers: `trade_proposed` comes from the structured trade and is never asked, the two
wording-fragile deciding questions (`bear_objection_answered`, `thesis_material_directional`)
are each asked over all five q1 phrasings concurrently with a bounded per-call timeout and
the majority wins, a 3-2 split (minority >= `SPLIT_CLOSE_MIN_MINORITY`) marks the question
`close`, and every other question is one call. A failed or timed-out call fails the whole
grade, which the rule turns into "decision unavailable". HTTP 429/503 overload is retried
with jittered backoff because one lost call of 13 loses the whole Room.

`ProductionPlanGrader` holds that plan once. `DeepInfraGrader` (own HTTP client) and
`LingGrader` (the gateway's `vllm_fallback` slot) subclass it and differ only in transport,
so the question set, phrasings, split rule and retry rule cannot drift apart. Changing any
plan constant changes `plan_version_suffix()`, which re-keys the policy version of every
grader built on it.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any, Sequence

from app.services.room_grader_contract import (
    Answer,
    QuestionAnswer,
    QuestionId,
    RoomTranscript,
    trade_proposed_answer,
)
from app.services.room_graders import ling_terminal as terminal_v2
from app.services.room_graders.hosted_llm import HostedLLMGrader, _CallFailed
from app.services.room_graders.ling_terminal import tally_votes
from app.services.room_graders.terminal_materiality import apply_materiality
from app.services.room_graders.questions import Question, load_question_set, render_transcript

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

CLOSE_BAND = 0.2

# A split is "close" only when the minority holds at least this many phrasings.
# Saiful 2026-11-24 (WP-23 fit, `wp23_fit_2026-11-24.md`): a 4-1 split is a clear
# answer; only 3-2 is close. Any split (1) gave 22% Contested; 2 gives ~17%.
SPLIT_CLOSE_MIN_MINORITY = 2


@dataclass(frozen=True)
class QuestionVariant:
    """A grader-specific replacement for one question's wording: the question the model is
    asked (text, yes/no meaning, five phrasings) and, optionally, its own system prompt. The
    question's id, and so the plan that averages and splits it, is unchanged. Only a grader
    that is handed a variant uses it; the shared plan's wording stays the question file's."""

    tag: str
    question: Question
    system: str | None = None


def is_overload(exc: BaseException) -> bool:
    text = str(exc)
    return any(m in text for m in _OVERLOAD_MARKERS)


def plan_version_suffix() -> str:
    """The part of a grader version that names the plan: temperature, the averaged
    questions and phrasing count, the split rule and the structured trade."""
    averaged = "+".join(q.value for q in AVERAGED_QUESTIONS)
    return (f"|t0|avg{PHRASING_COUNT}:{averaged}|split{SPLIT_CLOSE_MIN_MINORITY}"
            f"|trade=structure")


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


class ProductionPlanGrader(HostedLLMGrader):
    """`HostedLLMGrader` running the production plan above. Subclasses set `name`,
    pass `timeout_s` and supply the transport (`_gw()` / `agrade`)."""

    def __init__(
        self, slot: str, *, timeout_s: float, variants: Sequence[QuestionVariant] = (),
        terminal_variant: bool = False, **kwargs: Any,
    ) -> None:
        super().__init__(slot, close_band=CLOSE_BAND, **kwargs)
        self._timeout_s = float(timeout_s)
        self._terminal_variant = terminal_variant
        self._variants = {v.question.id: v for v in variants}
        for qid, v in self._variants.items():
            if qid in AVERAGED_QUESTIONS and len(v.question.phrasings) < PHRASING_COUNT:
                raise ValueError(f"variant {v.tag} needs {PHRASING_COUNT} phrasings")

    async def _grade_terminal(
        self, ticker: str, rendered: str, tally: dict[str, Any], phrasing: int,
    ) -> QuestionAnswer:
        """One phrasing of the `term=v2` terminal question (`ling_terminal.py`): the full-field JSON
        reply, checked in code, no token probabilities."""
        text, meta = await self._ask(
            terminal_v2.SYSTEM, f"{rendered}\n\n---\n{terminal_v2.question_block(ticker, phrasing)}",
            terminal_v2.CONSTRAINT, logprobs=False, max_tokens=terminal_v2.MAX_TOKENS,
        )
        tally["calls"].append(meta)
        vote = terminal_v2.parse_vote(text, phrasing, rendered)
        if vote.answer is Answer.NOT_COMPUTABLE:
            tally["unparsed"] += 1
        return vote

    async def _grade_all(self, transcript: RoomTranscript, tally: dict[str, Any]):
        rendered = render_transcript(transcript)
        gate = asyncio.Semaphore(MAX_CONCURRENT_CALLS)

        terminal = self._terminal_variant

        async def vote(q: Question, phrasing: int | None) -> QuestionAnswer:
            variant = self._variants.get(q.id)
            asked, system = (variant.question, variant.system) if variant else (q, None)
            attempt = 0
            while True:
                async with gate:
                    try:
                        call = (
                            self._grade_terminal(transcript.ticker, rendered, tally, phrasing)
                            if terminal and q.id is QuestionId.TERMINAL_VULNERABILITY
                            else self._grade_question(asked, rendered, tally, phrasing, system)
                        )
                        return await asyncio.wait_for(call, self._timeout_s)
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
                list(range(PHRASING_COUNT))
                if q.id in AVERAGED_QUESTIONS or (terminal and q.id is QuestionId.TERMINAL_VULNERABILITY)
                else [None]
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
            if terminal and q.id is QuestionId.TERMINAL_VULNERABILITY:
                by_q[q.id] = tally_votes(votes, SPLIT_CLOSE_MIN_MINORITY)
                counts = terminal_v2.rejection_counts(votes)
                if counts:
                    tally["terminal_rejected"] = counts
                checked = apply_materiality(by_q[q.id], transcript.terminal_inputs)
                check = (checked.detail or {}).get("terminal_check")
                if check is not None:
                    tally["terminal_materiality"] = {
                        "stood": check["stands"], "reason": check["reason"],
                        "coverage": check["coverage"],
                    }
                by_q[q.id] = checked
                continue
            by_q[q.id] = (
                average_votes(q.id, votes, self._close_band)
                if q.id in AVERAGED_QUESTIONS else votes[0]
            )
        by_q[QuestionId.TRADE_PROPOSED] = trade_proposed_answer(transcript.proposed_trade)
        return tuple(by_q[q.id] for q in load_question_set().questions)
