"""CR267 WP-22/WP-23: the shared contract between Room graders and the coded decision rule.

WP-22 builds graders (Jev, the hosted model at temperature 0, plain code over CR266
typed cards) that answer a fixed set of narrow questions about a finished debate.
WP-23 combines those answers with a rule written in advance into Approve / Pass /
Contested. Both sides import this module and nothing else from each other, so the
two lanes can be built in parallel and a grader can be swapped without touching
the rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, Sequence

QUESTION_SET_VERSION = "q1"


class QuestionId(str, Enum):
    BEAR_OBJECTION_ANSWERED = "bear_objection_answered"
    CATALYST_IN_HORIZON = "catalyst_in_horizon"
    TERMINAL_VULNERABILITY = "terminal_vulnerability"
    EVENT_RISK_WAIT = "event_risk_wait"
    THESIS_MATERIAL_DIRECTIONAL = "thesis_material_directional"
    TRADE_PROPOSED = "trade_proposed"


class Answer(str, Enum):
    YES = "yes"
    NO = "no"
    NOT_COMPUTABLE = "not_computable"


@dataclass(frozen=True)
class QuestionAnswer:
    question: QuestionId
    answer: Answer
    confidence: float | None = None
    """P(answer) in [0, 1] from token probabilities, or a 1–5 score mapped to [0, 1];
    None when the grader has neither (the code grader)."""
    close: bool = False
    """True when the grader's own evidence sits near the yes/no boundary. The rule's
    Contested band reads this; graders set it from fitted cut-offs, never from consensus."""
    rationale: str = ""


@dataclass(frozen=True)
class GraderResult:
    grader: str
    grader_version: str
    question_set_version: str
    answers: Sequence[QuestionAnswer]
    latency_ms: int
    error: str | None = None
    """Set when the grader failed. A failed result never yields a verdict: the Room
    ends in "decision unavailable" (WP-23 §4, degrade loudly)."""
    cost_usd: float | None = None
    extra: dict = field(default_factory=dict)

    def get(self, q: QuestionId) -> QuestionAnswer | None:
        for a in self.answers:
            if a.question == q:
                return a
        return None


@dataclass(frozen=True)
class RoomTranscript:
    """What every grader reads: the finished debate, before any CIO verdict."""

    room_id: str
    ticker: str
    risk_score: int
    horizon: str | None
    turns: Sequence[dict]
    """Ordered desk turns: {"agent_id": str, "content": str}."""
    cards: dict | None = None
    """CR266 typed cards when the Room ran with cards on; None otherwise."""
    proposed_trade: dict | None = None


class Grader(Protocol):
    name: str
    version: str

    def grade(self, transcript: RoomTranscript) -> GraderResult: ...
