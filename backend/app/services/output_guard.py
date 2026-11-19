"""CR271 (CR267 WP-13) - deterministic output text guard on user-visible agent text.

AMI is a training simulator and is not licensed to give investment advice. The
agents are told not to, and ignore that instruction often enough (CR038: ~70% on
a comparable "never present this as real" rule) that a prompt cannot be the
control. This module is the structural one: a pure, regex-based check run on the
FINISHED text of each user-visible surface, before it is shown or stored.

Three rules:

  advice     ENFORCING. Personal advice aimed at the user: the second person
             ("you"/"your") plus an action verb, an "I recommend/advise you"
             construction, or a promise of returns ("guaranteed returns", "you
             will make money", "risk-free profit", "can't lose"). The agents'
             normal analytical voice does NOT match: "the desk should buy 2% of
             capital", "I recommend APPROVE" and "the bull case recommends a
             long" have no second person and pass.
  abuse      ENFORCING. A short, conservative list of slurs, direct insults of
             the user and self-harm encouragement. Deliberately short: it
             exists to catch the unambiguous, not to police tone.
  runaway_length
             NOT a withhold. A single user-visible agent turn over
             `Settings.output_guard_max_turn_words` words is a runaway or looping
             generation (WP-13 replay: every one of the old `off_topic` hits was
             one, 1,155 to 15,556 words). In `enforce` mode the caller cuts it at
             a sentence boundary near the cap and appends a visible note; in
             `log` mode it is only logged, with the original word count. It
             replaced the `off_topic` density heuristic, which never caught
             real off-topic text.

Mode (`Settings.output_guard_mode`): `off` runs nothing; `log` (the default)
emits one structured `output_guard_hit` event per hit and changes no text;
`enforce` additionally sets `GuardResult.withhold` when an ENFORCING rule hit and
`GuardResult.trim` when `runaway_length` hit.
The CALLER decides what withholding means on its surface (the Room desk turn
takes the scripted-fallback path, the verdict narrative and 1-on-1 reply become
a labelled AMI sentinel); this module only decides and logs.

Logging never carries the full text: only the surface, rule, mode, agent/run ids
and a matched span truncated to `SPAN_LOG_CHARS`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.core.config import settings
from app.core.logging import logger

GuardMode = Literal["off", "log", "enforce"]

RULE_ADVICE = "advice"
RULE_ABUSE = "abuse"
RULE_RUNAWAY = "runaway_length"

# Rules that withhold in `enforce` mode. `runaway_length` is deliberately absent:
# it trims, it never withholds.
ENFORCING_RULES = frozenset({RULE_ADVICE, RULE_ABUSE})

SPAN_LOG_CHARS = 80

# Appended to a trimmed turn so the cut is never silent.
TRIM_NOTE = "[AMI trimmed an overlong note]"
# A sentence boundary is only used when it lies in the last 30% of the allowed
# words; earlier than that and cutting there would lose too much, so the cut is
# at the word boundary instead.
_TRIM_BOUNDARY_FLOOR = 0.7
_WORD_RE = re.compile(r"\S+")
_SENTENCE_END_RE = re.compile(r"[.!?][\"')\]]*(?=\s|$)")

# The `meta` dict a streaming surface already threads through the gateway
# (DEF125 / RETRO-SECURITY MAJOR-2) doubles as the channel between the
# generator that finalises a reply and the HTTP handler that presents it:
#   META_CONSUMER_BUFFERS  set True by a handler that holds the whole reply
#                          before sending a byte, so a withhold is real;
#   META_SENTINEL          set by the generator when it withheld the reply,
#                          carrying the AMI sentence the handler must show.
META_CONSUMER_BUFFERS = "output_guard_consumer_buffers"
META_SENTINEL = "output_guard_sentinel"

# ── advice ────────────────────────────────────────────────────────────────

# Trade/position actions that make "you should ..." an instruction to the user
# to trade. Narrow on purpose: "you should review the lesson" or "you should
# size the position at 2%" are teaching, not a call to trade.
_ACT = (
    r"(?:buy(?:ing)?|sell(?:ing)?|short(?:ing)?(?![-\w])(?!\s+term)|dump(?:ing)?"
    r"|invest\s+in\s+(?:this|it|that|the\s+(?:stock|shares?|company)|stocks?|shares?|\$[A-Z]{1,5})"
    r"|go\s+(?:long|short)|load\s+up|pile\s+into|bail\s+(?:out|on)"
    r"|take\s+(?:the\s+)?profits?|cut\s+(?:your\s+)?losses|double\s+down"
    r"|put\s+(?:your\s+)?money)"
)
_NO_PRECEDING = r"(?<!\bno\s)(?<!\bnot\s)(?<!\bnever\s)(?<!\bwithout\s)(?<!\bnon-)"

_ADVICE_PATTERNS = [
    # "you should buy", "you shouldn't sell", "you really must go long"
    rf"\byou\s+(?:really\s+|definitely\s+|absolutely\s+)?"
    rf"(?:should(?:n['’]t|\s+not)?|must|ought\s+to|need\s+to|have\s+to|had\s+better"
    rf"|better|['’]d\s+better)\s+(?:\w+\s+){{0,1}}?{_ACT}\b",
    # "you would be wise to sell"
    rf"\byou\s+(?:would\s+|['’]d\s+)?(?:be\s+wise|do\s+well)\s+to\s+(?:\w+\s+){{0,2}}?{_ACT}\b",
    # "I recommend (that) you buy", "we suggest you sell"
    rf"\b(?:I|we)\s+(?:strongly\s+|highly\s+)?(?:recommend|suggest|urge|encourage)\s+"
    rf"(?:that\s+)?you\s+(?:to\s+)?(?:\w+\s+){{0,3}}?{_ACT}\b",
    # "I advise you (to ...)", "I'd advise that you ..."
    r"\b(?:I|we)(?:['’]d|\s+would|\s+strongly|\s+highly)?\s*(?:advise|counsel)\s+(?:that\s+)?you\b",
    # "my advice is to buy", "my recommendation to you is to sell"
    rf"\bmy\s+(?:advice|recommendation)\s+(?:to\s+you\s+)?is\s+(?:for\s+you\s+)?(?:to\s+)?{_ACT}\b",
    # "go ahead and buy"
    rf"\bgo\s+ahead\s+and\s+{_ACT}\b",
    # promises of return
    # CR271 replay: "once guaranteed returns" is a past-tense verb; the
    # regulated-utility term of art is exempted in `check` (_REGULATED_CONTEXT).
    rf"{_NO_PRECEDING}(?<!\bonce\s)(?<!\bformerly\s)(?<!\bpreviously\s)"
    r"\bguaranteed?\s+(?:returns?|profits?|gains?)\b",
    # CR271 replay: "the line the uptrend cannot lose" is a price level, not a
    # promise. A promise has a subject that is the user or the trade itself and
    # ends the clause ("you can't lose.") or names money ("can't lose money").
    r"\b(?:you|it|this|that|trade|bet|position|investment|stock|setup|play|name)\s+"
    r"(?:simply\s+|literally\s+|just\s+|possibly\s+)*(?:can['’]?t|cannot|can\s+not)\s+"
    r"(?:possibly\s+)?lose\b"
    r"(?=\s*(?:[.,;:!)—–]|$)|\s+(?:money|anything|a\s+(?:penny|cent|dime)|at\s+all"
    r"|on\s+(?:this|it|that)|with\s+(?:this|it|that)))",
    r"\brisk[- ]free\s+(?:profits?|gains?|money|trades?|bets?)\b",
    r"\byou(?:['’]ll|\s+will|\s+are\s+(?:going\s+to|sure\s+to|certain\s+to))\s+"
    r"(?:definitely\s+|certainly\s+|surely\s+|easily\s+|absolutely\s+)?"
    r"(?:make\s+(?:money|a\s+profit|profits|gains|a\s+killing)|profit\b|get\s+rich"
    r"|be\s+rich|double\s+your|triple\s+your)",
]

# Rate-regulated utilities have a "guaranteed return on rate base": a term of
# art about an allowed ROE, not a promise to the user. A `guaranteed ...` hit
# with this vocabulary in the same sentence is skipped.
_REGULATED_CONTEXT = re.compile(
    r"rate[\s-]?base|allowed\s+(?:roe|return)|regulated\s+(?:utilit|asset|return)",
    re.IGNORECASE,
)

# ── abuse ─────────────────────────────────────────────────────────────────

_ABUSE_PATTERNS = [
    # Ethnic / racial / homophobic / ableist slurs. Short and unambiguous.
    r"\bn[i1]gg(?:er|a)s?\b",
    r"\bfagg?ots?\b",
    r"\bk[i1]kes?\b",
    r"\bsp[i1]cs?\b",
    r"\bch[i1]nks?\b",
    r"\btrann(?:y|ies)\b",
    r"\bwetbacks?\b",
    r"\bretard(?:ed|s)?\b",
    # Direct insults at the user.
    r"\byou(?:['’]re|\s+are)\s+(?:a\s+|an\s+|such\s+a\s+|such\s+an\s+|so\s+|really\s+|just\s+)?"
    r"(?:stupid|dumb|idiot|moron|imbecile|worthless|pathetic|useless)\b",
    r"\b(?:idiot|moron|imbecile)s?\b",
    # Strong profanity.
    r"\bfuck(?:ing|ed|er|ers|s)?\b",
    r"\bshit(?:ty|head)?\b",
    # Self-harm encouragement.
    r"\b(?:kill|hang)\s+yourself\b",
    r"\bkys\b",
]

# ── compiled rules ────────────────────────────────────────────────────────

_FLAGS = re.IGNORECASE
_COMPILED: dict[str, list[re.Pattern[str]]] = {
    RULE_ADVICE: [re.compile(p, _FLAGS) for p in _ADVICE_PATTERNS],
    RULE_ABUSE: [re.compile(p, _FLAGS) for p in _ABUSE_PATTERNS],
}


@dataclass(frozen=True)
class Hit:
    """One rule hit. `span` is the matched text (never the whole input)."""

    rule: str
    span: str
    start: int
    end: int
    enforcing: bool
    words: int = 0


@dataclass(frozen=True)
class GuardResult:
    """What `check` decided. `withhold` is True only in `enforce` mode with at
    least one ENFORCING hit; the caller turns that into a surface-specific
    withholding. `hits` carries every hit, enforcing or not."""

    mode: str
    surface: str
    hits: tuple[Hit, ...] = ()

    @property
    def enforcing_hits(self) -> tuple[Hit, ...]:
        return tuple(h for h in self.hits if h.enforcing)

    @property
    def withhold(self) -> bool:
        return self.mode == "enforce" and bool(self.enforcing_hits)

    @property
    def trim(self) -> bool:
        """True in `enforce` mode when the text ran past the word cap."""
        return self.mode == "enforce" and any(h.rule == RULE_RUNAWAY for h in self.hits)

    @property
    def rules(self) -> tuple[str, ...]:
        seen: list[str] = []
        for h in self.hits:
            if h.rule not in seen:
                seen.append(h.rule)
        return tuple(seen)


def _is_regulated_term(text: str, m: re.Match[str]) -> bool:
    """True when a `guaranteed ...` hit sits in the same sentence as rate-base
    vocabulary. Same sentence only: a promise one sentence later still hits."""
    if not m.group(0).lower().startswith("guarantee"):
        return False
    start = max(text.rfind(c, 0, m.start()) for c in ".!?\n") + 1
    ends = [i for i in (text.find(c, m.end()) for c in ".!?\n") if i != -1]
    return bool(_REGULATED_CONTEXT.search(text, start, min(ends) if ends else len(text)))


def check(text: str | None, *, surface: str, mode: str | None = None) -> GuardResult:
    """Run the guard on one finished piece of user-visible text. Pure: no
    logging, no I/O. `mode` defaults to `Settings.output_guard_mode`; `off`
    returns an empty result without scanning."""
    mode = mode or settings.output_guard_mode
    if mode == "off" or not text or not text.strip():
        return GuardResult(mode=mode, surface=surface)
    hits: list[Hit] = []
    for rule, patterns in _COMPILED.items():
        for pat in patterns:
            m = next(
                (
                    c for c in pat.finditer(text)
                    if not _is_regulated_term(text, c)
                ),
                None,
            )
            if m:
                hits.append(Hit(rule, m.group(0), m.start(), m.end(), True))
                break
    cap = settings.output_guard_max_turn_words
    if cap > 0:
        n_words = len(text.split())
        if n_words > cap:
            hits.append(
                Hit(RULE_RUNAWAY, text.strip()[:SPAN_LOG_CHARS], 0, 0, False, words=n_words)
            )
    return GuardResult(mode=mode, surface=surface, hits=tuple(hits))


def log_hits(
    result: GuardResult,
    *,
    agent_id: str | None = None,
    run_id: object | None = None,
    already_streamed: bool = False,
) -> None:
    """One `output_guard_hit` event per hit. `already_streamed` is True when the
    text had reached the user before this check could run, i.e. a `withhold`
    result cannot take back what was shown."""
    for h in result.hits:
        logger.warning(
            "output_guard_hit",
            surface=result.surface,
            rule=h.rule,
            mode=result.mode,
            enforcing=h.enforcing,
            withheld=result.withhold and h.enforcing,
            agent_id=agent_id,
            run_id=str(run_id) if run_id is not None else None,
            already_streamed=already_streamed,
            span=h.span[:SPAN_LOG_CHARS],
            words=h.words or None,
            max_words=settings.output_guard_max_turn_words if h.words else None,
        )


def inspect(
    text: str | None,
    *,
    surface: str,
    agent_id: str | None = None,
    run_id: object | None = None,
    already_streamed: bool = False,
) -> GuardResult:
    """`check` + `log_hits`: the call every surface seam makes."""
    result = check(text, surface=surface)
    log_hits(
        result, agent_id=agent_id, run_id=run_id, already_streamed=already_streamed
    )
    return result


def trim_to_cap(text: str, cap: int | None = None) -> str:
    """Cut `text` to at most `cap` words (default the setting) at a sentence
    boundary near the cap, and append `TRIM_NOTE`. Text at or under the cap is
    returned unchanged. Pure."""
    cap = settings.output_guard_max_turn_words if cap is None else cap
    if cap <= 0:
        return text
    words = list(_WORD_RE.finditer(text))
    if len(words) <= cap:
        return text
    limit = words[cap - 1].end()
    floor = words[int(cap * _TRIM_BOUNDARY_FLOOR) - 1].end() if cap > 1 else 0
    cut = limit
    for m in _SENTENCE_END_RE.finditer(text, floor, limit):
        cut = m.end()
    return f"{text[:cut].rstrip()}\n\n{TRIM_NOTE}"


def trim_if_runaway(text: str) -> str:
    """The seam helper: in `enforce` mode only, trim an over-cap turn. `log` and
    `off` return the text untouched. No logging here: `inspect` already logged
    the hit, with the original length."""
    if settings.output_guard_mode != "enforce":
        return text
    return trim_to_cap(text)


def withheld_notice(result: GuardResult, noun: str) -> str:
    """The labelled AMI sentence that replaces withheld text. `noun` is what was
    withheld on this surface ("explanation", "reply")."""
    if RULE_ABUSE in {h.rule for h in result.enforcing_hits} and RULE_ADVICE not in {
        h.rule for h in result.enforcing_hits
    }:
        return (
            f"AMI withheld this {noun} because it contained language AMI does "
            "not allow."
        )
    return (
        f"AMI withheld this {noun} because it read as personal advice. AMI is a "
        "training simulator and does not give investment advice."
    )


def retraction_notice(result: GuardResult) -> str:
    """For a surface that streams live tokens (Brief): the text is already on
    the user's screen and cannot be withheld, so AMI says so in a trailing line
    instead of pretending. Same two causes as `withheld_notice`."""
    if RULE_ADVICE in {h.rule for h in result.enforcing_hits}:
        why = (
            "it read as personal advice, which AMI does not give (AMI is a "
            "training simulator)"
        )
    else:
        why = "it contained language AMI does not allow"
    return f"\n\n— AMI flags the reply above: {why}. Please disregard it."
