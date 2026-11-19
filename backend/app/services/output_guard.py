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
  off_topic  LOG ONLY, in every mode. "Is this text about markets?" is a
             heuristic (market/finance-term density over a minimum length), so
             a false positive withholding a good answer would cost more than the
             rule buys. It only ever produces an `output_guard_hit` line.

Mode (`Settings.output_guard_mode`): `off` runs nothing; `log` (the default)
emits one structured `output_guard_hit` event per hit and changes no text;
`enforce` additionally sets `GuardResult.withhold` when an ENFORCING rule hit.
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
RULE_OFF_TOPIC = "off_topic"

# Rules that withhold in `enforce` mode. `off_topic` is deliberately absent and
# nothing may add it without a new decision: it is a density heuristic.
ENFORCING_RULES = frozenset({RULE_ADVICE, RULE_ABUSE})

SPAN_LOG_CHARS = 80

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

# ── off_topic (log only) ──────────────────────────────────────────────────

# Below MARKET_MIN_WORDS there is not enough text for a density to mean
# anything; a short reply is never flagged.
MARKET_MIN_WORDS = 40
# Share of word tokens that are market/finance terms (or carry a % / $) below
# which the text is flagged. Real analyst prose measures several times this; a
# recipe or a poem measures near zero. Starting value, tuned from the replay
# tool (scripts/output_guard_replay.py) on real traffic before anyone relies on it.
MARKET_MIN_DENSITY = 0.03

_MARKET_TERMS = frozenset("""
stock stocks share shares equity equities etf etfs index indices market markets
price prices pricing trade trades trader trading buy sell hold short long bull
bullish bear bearish rally selloff sell-off breakout breakdown trend trends
support resistance volume volatility vol implied momentum rsi macd sma ema
atr bollinger candle chart technical technicals fundamental fundamentals
earnings revenue revenues profit profits margin margins eps guidance forecast
valuation multiple multiples p/e pe peg dividend dividends yield yields buyback
cash debt leverage liquidity balance sheet cashflow cap capital portfolio
position positions size sizing allocation exposure concentration drawdown risk
risks hedge stop stoploss target entry exit reward ratio sector sectors
industry fed fomc rates rate inflation cpi gdp macro economy economic
recession treasury bond bonds credit spread analyst analysts upgrade downgrade
rating ratings headline headlines news filing filings sentiment options call
calls put puts strike expiry premium delta gamma theta vega mandate verdict
approve pass cio desk conviction thesis catalyst catalysts benchmark return
returns alpha beta sharpe correlation float ipo split guidance outlook
quarter quarterly annual fiscal ticker tickers nasdaq nyse s&p dow
""".split())

_TOKEN_RE = re.compile(r"[a-z][a-z'&/\-]*|\$\w+|\d[\d,.]*%?")


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
    def rules(self) -> tuple[str, ...]:
        seen: list[str] = []
        for h in self.hits:
            if h.rule not in seen:
                seen.append(h.rule)
        return tuple(seen)


def _market_density(text: str) -> tuple[int, float]:
    """(word count, share of words that are market terms)."""
    tokens = _TOKEN_RE.findall(text.lower())
    words = [t for t in tokens if t[0].isalpha() or t[0] == "$"]
    if not words:
        return 0, 0.0
    hits = sum(
        1 for t in tokens
        if t in _MARKET_TERMS or t.startswith("$") or t.endswith("%")
    )
    return len(words), hits / len(words)


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
    words, density = _market_density(text)
    if words >= MARKET_MIN_WORDS and density < MARKET_MIN_DENSITY:
        hits.append(Hit(RULE_OFF_TOPIC, text.strip()[:SPAN_LOG_CHARS], 0, 0, False))
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
