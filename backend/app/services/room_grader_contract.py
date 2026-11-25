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
    detail: Mapping[str, Any] | None = None
    """Structured fields a question's answer carries beyond yes/no (CR267 `term=v2`: the named
    terminal risk, its category, evidence and why it stayed open). None for every other question."""


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
    terminal_inputs: dict | None = None
    """CR267 `term=v2` materiality check: the balance-sheet inputs (in $M) the code needs to decide a
    `debt_default` terminal yes, built by `build_terminal_inputs` from
    the Room's profile. None when the Room has no profile (an offline caller); the check then finds
    no maturity schedule and says so."""


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


def build_terminal_inputs(profile: Mapping[str, Any] | None, horizon_days: int | None) -> dict:
    """The `RoomTranscript.terminal_inputs` shape, in $M, taken from the Room's profile (the data
    behind the fact sheet). A field counts only when `field_state` says it is live, as the sheet
    itself does. Lives here, not in `room_graders`, because the runner may import only this contract."""
    p = profile or {}
    state = p.get("field_state") or {}

    def live(key: str, *, value_key: str | None = None) -> Any:
        return p.get(value_key or key) if state.get(key) == "live" else None

    labels, values = p.get("debt_maturity_labels"), p.get("debt_maturity_values")
    ladder = None
    if state.get("debt_maturity") == "live" and labels and values and len(labels) == len(values):
        ladder = [[str(a), float(b)] for a, b in zip(labels, values)]
    fcf = live("free_cash_flow")
    fcf_source = "free_cash_flow"
    if fcf is None:
        fcf = live("free_cash_flow_ttm")
        fcf_source = "free_cash_flow_ttm"
    return {
        "horizon_days": horizon_days,
        "ladder": ladder,
        "ladder_period_end": p.get("debt_maturity_period_end") if ladder else None,
        "short_term_borrowings": p.get("debt_maturity_excluded_st") if ladder else None,
        "total_cash": live("total_cash"),
        "total_debt": live("total_debt"),
        "net_cash": live("net_cash"),
        "fcf_ttm": fcf,
        "fcf_field": fcf_source if fcf is not None else None,
    }


NO_TRADE_ACTIONS = frozenset(
    {"", "hold", "pass", "none", "no_trade", "no trade", "wait", "skip"}
)


def trade_proposed_answer(trade: Mapping[str, Any] | None) -> QuestionAnswer:
    """`trade_proposed` from the structured trade alone, never from prose or a model.

    No block at all means no trade was proposed. A block that cannot say what the
    Execution Desk proposed (no `action` or `side`) is not computable, never guessed.
    """
    q = QuestionId.TRADE_PROPOSED
    if not trade:
        return QuestionAnswer(q, Answer.NO, rationale="no proposed trade")
    action = trade.get("action", trade.get("side"))
    if action is None:
        return QuestionAnswer(
            q, Answer.NOT_COMPUTABLE, rationale="proposed_trade carries no action or side"
        )
    proposed = str(action).strip().lower() not in NO_TRADE_ACTIONS
    return QuestionAnswer(
        q, Answer.YES if proposed else Answer.NO, rationale=f"action={action}"
    )
