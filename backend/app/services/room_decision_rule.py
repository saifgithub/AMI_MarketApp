"""CR267 WP-23: the coded decision rule that turns grader answers into a Room decision.

A grader (WP-22) answers narrow typed questions about a finished debate; this module
combines those answers with a rule written in advance into Approve / Pass / Contested /
Unavailable. It is a pure function of (grader result, risk score, policy), so the same
answers always give the same decision, and it never defaults: a failed grader or an
answer that cannot be computed is Unavailable, not a verdict.

The structure of the rule is fixed in code (terminal vulnerability and no trade proposed
always Pass; strictness is nested so a conservative level can never approve what a
lenient one rejects). Only the per-level gates beyond those two and the Contested
cut-off live in the versioned policy JSON, in the same per-identity R1..R5 shape as
`room_evidence_gate_thresholds_json`. Nothing here is fitted to consensus.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from app.services.room_grader_contract import (
    QUESTION_SET_VERSION,
    Answer,
    GraderResult,
    QuestionId,
)

RULE_VERSION = "r1"

RISK_LEVELS: tuple[str, ...] = ("R1", "R2", "R3", "R4", "R5")

ALWAYS_PASS_IF_YES: frozenset[QuestionId] = frozenset({QuestionId.TERMINAL_VULNERABILITY})
ALWAYS_REQUIRED_YES: frozenset[QuestionId] = frozenset({QuestionId.TRADE_PROPOSED})

QUESTION_LABELS: dict[QuestionId, str] = {
    QuestionId.BEAR_OBJECTION_ANSWERED: "whether the bear's strongest objection was answered with numbers",
    QuestionId.CATALYST_IN_HORIZON: "whether a named catalyst falls inside the mandate horizon",
    QuestionId.TERMINAL_VULNERABILITY: "whether an unresolved terminal vulnerability remains",
    QuestionId.EVENT_RISK_WAIT: "whether event risk argues for waiting",
    QuestionId.THESIS_MATERIAL_DIRECTIONAL: "whether the thesis support is material and directional",
    QuestionId.TRADE_PROPOSED: "whether the desk proposed a trade",
}


class Outcome(str, Enum):
    APPROVE = "APPROVE"
    PASS = "PASS"
    CONTESTED = "CONTESTED"
    UNAVAILABLE = "UNAVAILABLE"


class PolicyConfigError(ValueError):
    pass


@dataclass(frozen=True)
class LevelPolicy:
    required_yes: frozenset[QuestionId]
    blocking_yes: frozenset[QuestionId]

    @property
    def deciding(self) -> frozenset[QuestionId]:
        return (
            self.required_yes | self.blocking_yes
            | ALWAYS_PASS_IF_YES | ALWAYS_REQUIRED_YES
        )


@dataclass(frozen=True)
class RulePolicy:
    levels: Mapping[str, LevelPolicy]
    close_below_confidence: float
    source: str

    def digest(self) -> str:
        payload = {
            "close_below_confidence": self.close_below_confidence,
            "levels": {
                level: {
                    "required_yes": sorted(q.value for q in lp.required_yes),
                    "blocking_yes": sorted(q.value for q in lp.blocking_yes),
                }
                for level, lp in sorted(self.levels.items())
            },
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


# The written-in-advance ladder. R1 is the most conservative mandate. Each level
# requires and blocks a superset of the next, so strictness is monotone by
# construction. The conservative levels (R1, R2) are the ones where an unanswered
# bear objection is a Pass.
_Q = QuestionId
DEFAULT_LEVELS: dict[str, LevelPolicy] = {
    "R1": LevelPolicy(
        required_yes=frozenset({_Q.BEAR_OBJECTION_ANSWERED, _Q.THESIS_MATERIAL_DIRECTIONAL, _Q.CATALYST_IN_HORIZON}),
        blocking_yes=frozenset({_Q.EVENT_RISK_WAIT}),
    ),
    "R2": LevelPolicy(
        required_yes=frozenset({_Q.BEAR_OBJECTION_ANSWERED, _Q.THESIS_MATERIAL_DIRECTIONAL, _Q.CATALYST_IN_HORIZON}),
        blocking_yes=frozenset(),
    ),
    "R3": LevelPolicy(required_yes=frozenset({_Q.THESIS_MATERIAL_DIRECTIONAL}), blocking_yes=frozenset()),
    "R4": LevelPolicy(required_yes=frozenset({_Q.THESIS_MATERIAL_DIRECTIONAL}), blocking_yes=frozenset()),
    "R5": LevelPolicy(required_yes=frozenset(), blocking_yes=frozenset()),
}

# Placeholder: 0.0 means only the grader's own `close` flag opens the Contested band.
# To be fitted on WP-20 rooms against rep agreement and the known-answer input tests,
# never against consensus.
DEFAULT_CLOSE_BELOW_CONFIDENCE = 0.0

DEFAULT_POLICY = RulePolicy(
    levels=DEFAULT_LEVELS,
    close_below_confidence=DEFAULT_CLOSE_BELOW_CONFIDENCE,
    source="default",
)

_CONF_KEY = "close_below_confidence"


def _question_set(raw: object, where: str) -> frozenset[QuestionId]:
    if not isinstance(raw, list):
        raise PolicyConfigError(f"{where}: must be a list of question ids")
    out: set[QuestionId] = set()
    for item in raw:
        try:
            out.add(QuestionId(item))
        except ValueError as exc:
            raise PolicyConfigError(f"{where}: unknown question {item!r}") from exc
    return frozenset(out)


def parse_policy_json(raw: str) -> dict[str, RulePolicy]:
    """Parse and loudly validate `ROOM_CODED_RULE_POLICY_JSON`.

    Shape: {"<grader name or *>": {"close_below_confidence": 0.0,
    "R1": {"required_yes": [...], "blocking_yes": [...]}, ..., "R5": {...}}}.
    Each level must carry exactly R1..R5; a stricter level must require and block a
    superset of the next (strictness monotone in risk level); the always-on gates
    (terminal vulnerability, trade proposed) are applied in code and need not appear.
    Anything else raises PolicyConfigError: a malformed rule fails at boot, never guesses.
    """
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise PolicyConfigError(f"not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise PolicyConfigError("top level must be an object keyed by grader name")
    out: dict[str, RulePolicy] = {}
    for grader, body in parsed.items():
        if not isinstance(grader, str) or not grader.strip():
            raise PolicyConfigError("grader names must be non-empty strings")
        if not isinstance(body, dict):
            raise PolicyConfigError(f"{grader!r}: must be an object")
        extra = set(body) - set(RISK_LEVELS) - {_CONF_KEY}
        missing = set(RISK_LEVELS) - set(body)
        if extra or missing:
            raise PolicyConfigError(
                f"{grader!r}: need exactly {list(RISK_LEVELS)} (+ optional {_CONF_KEY}); "
                f"missing {sorted(missing)}, unexpected {sorted(extra)}"
            )
        conf = body.get(_CONF_KEY, DEFAULT_CLOSE_BELOW_CONFIDENCE)
        if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0.0 <= float(conf) <= 1.0:
            raise PolicyConfigError(f"{grader!r}/{_CONF_KEY}: must be a number in [0, 1]")
        levels: dict[str, LevelPolicy] = {}
        for level in RISK_LEVELS:
            lvl = body[level]
            if not isinstance(lvl, dict) or set(lvl) != {"required_yes", "blocking_yes"}:
                raise PolicyConfigError(
                    f"{grader!r}/{level}: need exactly required_yes and blocking_yes"
                )
            levels[level] = LevelPolicy(
                required_yes=_question_set(lvl["required_yes"], f"{grader!r}/{level}/required_yes"),
                blocking_yes=_question_set(lvl["blocking_yes"], f"{grader!r}/{level}/blocking_yes"),
            )
        for stricter, lenient in zip(RISK_LEVELS, RISK_LEVELS[1:], strict=False):
            s, l = levels[stricter], levels[lenient]
            if not (l.required_yes <= s.required_yes and l.blocking_yes <= s.blocking_yes):
                raise PolicyConfigError(
                    f"{grader!r}: {stricter} must require and block a superset of {lenient} "
                    "(strictness is monotone in risk level)"
                )
        out[grader.strip()] = RulePolicy(
            levels=levels, close_below_confidence=float(conf), source="json",
        )
    return out


def policy_for(raw_json: str, grader_name: str | None) -> RulePolicy:
    """The policy for this grader: its own entry, else `*`, else the built-in ladder."""
    table = parse_policy_json(raw_json)
    if grader_name and grader_name in table:
        return table[grader_name]
    return table.get("*", DEFAULT_POLICY)


def policy_version(grader: str, grader_version: str, policy: RulePolicy) -> str:
    return (
        f"{grader}@{grader_version}|rule={RULE_VERSION}"
        f"|qs={QUESTION_SET_VERSION}|ladder={policy.digest()}"
    )


def risk_level(risk_score: int) -> str:
    return f"R{max(1, min(5, int(risk_score)))}"


@dataclass(frozen=True)
class RuleDecision:
    outcome: Outcome
    close_questions: tuple[QuestionId, ...]
    reasons: tuple[str, ...]
    rule_version: str
    policy_version: str
    risk_level: str


def _evaluate(
    answers: Mapping[QuestionId, Answer], level: LevelPolicy,
) -> tuple[Outcome, tuple[str, ...]]:
    blocking = level.blocking_yes | ALWAYS_PASS_IF_YES
    required = level.required_yes | ALWAYS_REQUIRED_YES
    reasons: list[str] = []
    for q in sorted(blocking, key=lambda x: x.value):
        if answers.get(q) == Answer.YES:
            reasons.append(f"{QUESTION_LABELS[q]}: yes")
    for q in sorted(required, key=lambda x: x.value):
        if answers.get(q) == Answer.NO:
            reasons.append(f"{QUESTION_LABELS[q]}: no")
    if reasons:
        return Outcome.PASS, tuple(reasons)
    unknown = [
        q for q in sorted(level.deciding, key=lambda x: x.value)
        if answers.get(q) in (None, Answer.NOT_COMPUTABLE)
    ]
    if unknown:
        return Outcome.UNAVAILABLE, tuple(
            f"{QUESTION_LABELS[q]} could not be computed" for q in unknown
        )
    return Outcome.APPROVE, ()


def decide(result: GraderResult, risk_score: int, policy: RulePolicy | None = None) -> RuleDecision:
    policy = policy or DEFAULT_POLICY
    level_name = risk_level(risk_score)
    level = policy.levels[level_name]
    version = policy_version(result.grader, result.grader_version, policy)

    def unavailable(reason: str) -> RuleDecision:
        return RuleDecision(Outcome.UNAVAILABLE, (), (reason,), RULE_VERSION, version, level_name)

    if result.error:
        return unavailable(f"the grader failed: {result.error}")
    if result.question_set_version != QUESTION_SET_VERSION:
        return unavailable(
            f"the grader answered question set {result.question_set_version!r}, "
            f"the rule is written for {QUESTION_SET_VERSION!r}"
        )

    answers: dict[QuestionId, Answer] = {}
    close: set[QuestionId] = set()
    for a in result.answers:
        answers[a.question] = a.answer
        low_conf = (
            a.confidence is not None and a.confidence < policy.close_below_confidence
        )
        if a.close or low_conf:
            close.add(a.question)

    base, reasons = _evaluate(answers, level)
    if base == Outcome.UNAVAILABLE:
        return RuleDecision(base, (), reasons, RULE_VERSION, version, level_name)

    sensitive: list[QuestionId] = []
    for q in sorted(close & level.deciding, key=lambda x: x.value):
        if answers.get(q) not in (Answer.YES, Answer.NO):
            continue
        flipped = dict(answers)
        flipped[q] = Answer.NO if answers[q] == Answer.YES else Answer.YES
        if _evaluate(flipped, level)[0] != base:
            sensitive.append(q)
    if sensitive:
        return RuleDecision(
            Outcome.CONTESTED, tuple(sensitive),
            tuple(f"{QUESTION_LABELS[q]} was too close to call" for q in sensitive),
            RULE_VERSION, version, level_name,
        )
    if base == Outcome.APPROVE:
        reasons = ("every deciding question cleared this mandate's bar",)
    return RuleDecision(base, (), reasons, RULE_VERSION, version, level_name)
