"""CR267 WP-22/WP-23: the shared contract between Room graders and the coded decision rule.

WP-22 builds graders (Jev, the hosted model at temperature 0, plain code over CR266
typed cards) that answer a fixed set of narrow questions about a finished debate.
WP-23 combines those answers with a rule written in advance into Approve / Pass /
Contested. Both sides import this module and nothing else from each other, so the
two lanes can be built in parallel and a grader can be swapped without touching
the rule.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence

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
    """CR266 typed cards when the Room ran with cards on; None otherwise. Built by
    `build_cards_payload`: {"cards_by_desk": {desk: {"cards": [...], "objections":
    [...]}}, "field_state": {...}}."""
    proposed_trade: dict | None = None
    """Built by `build_proposed_trade`: {"action": ..., "size_pct", "entry", "stop",
    "target"}; `action` is omitted when the Room cannot say what the desk proposed."""


class Grader(Protocol):
    name: str
    version: str

    def grade(self, transcript: RoomTranscript) -> GraderResult: ...


def _channel_dict(channel: Any) -> dict:
    if is_dataclass(channel) and not isinstance(channel, type):
        channel = asdict(channel)
    if not isinstance(channel, Mapping):
        raise TypeError(f"card channel must be a dataclass or mapping, got {type(channel).__name__}")
    return {
        "cards": [dict(c) for c in channel.get("cards") or ()],
        "objections": [dict(o) for o in channel.get("objections") or ()],
    }


def build_cards_payload(
    channels_by_desk: Mapping[str, Any] | None,
    field_state: Mapping[str, Any] | None,
) -> dict | None:
    """The `RoomTranscript.cards` shape. The runner (live `ctx.claim_cards`) and the
    offline WP-22 scorer (cards re-parsed from the audit trail) both build it here.

    A desk with no cards is left out, as the runner leaves it out of `claim_cards`;
    no desk with cards at all gives None (the code grader then answers "room ran
    without cards"). Nothing is filled in.
    """
    out: dict[str, dict] = {}
    for desk, channel in (channels_by_desk or {}).items():
        if channel is None:
            continue
        body = _channel_dict(channel)
        if body["cards"]:
            out[str(getattr(desk, "value", desk))] = body
    if not out:
        return None
    return {"cards_by_desk": out, "field_state": dict(field_state or {})}


def build_proposed_trade(
    *,
    action: str | None,
    size_pct: float | None = None,
    entry: float | None = None,
    stop: float | None = None,
    target: float | None = None,
) -> dict:
    """The `RoomTranscript.proposed_trade` shape. `action` is the Execution Desk's
    side as the Room knows it ("buy", "hold", "wait", ...), lower-cased; None means
    the Room cannot say, so the key is omitted and `trade_proposed` stays
    not-computable rather than guessed. Unset levels are omitted."""
    trade: dict[str, Any] = {}
    if action is not None and str(action).strip():
        trade["action"] = str(action).strip().lower()
    for key, value in (
        ("size_pct", size_pct), ("entry", entry), ("stop", stop), ("target", target),
    ):
        if value is not None:
            trade[key] = value
    return trade
