"""CR271 (CR267 WP-13) - deterministic output text guard on user-visible agent text.

AMI is a training simulator and is not licensed to give investment advice. The
agents are told not to, and ignore that instruction often enough (CR038: ~70% on
a comparable "never present this as real" rule) that a prompt cannot be the
control. This module is the structural one: a pure, regex-based check run on the
FINISHED text of each user-visible surface, before it is shown or stored.

Four rules:

  advice     ENFORCING. Personal advice aimed at the user: the second person
             ("you"/"your") plus an action verb, an "I recommend/advise you"
             construction, or a promise of returns ("guaranteed returns", "you
             will make money", "risk-free profit", "can't lose"). The agents'
             normal analytical voice does NOT match: "the desk should buy 2% of
             capital", "I recommend APPROVE" and "the bull case recommends a
             long" have no second person and pass.
  personal_advice
             ENFORCING (WP-13c). A ticket or directive in the reply to a user
             message that asks for advice about their own situation. Needs the
             user's message (`user_message=`); never fires on Room text or on
             sim-framed questions. Rule and sim disambiguation: see below.
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
RULE_PERSONAL_ADVICE = "personal_advice"

# Rules that withhold in `enforce` mode. `runaway_length` is deliberately absent:
# it trims, it never withholds.
ENFORCING_RULES = frozenset({RULE_ADVICE, RULE_ABUSE, RULE_PERSONAL_ADVICE})

# Rules whose withholding reads as "personal advice" to the user.
_ADVICE_LIKE = frozenset({RULE_ADVICE, RULE_PERSONAL_ADVICE})

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
    r"|put\s+(?:your\s+)?money"
    # WP-13b: "You should hold." / "hold this stock". Narrow: a bare "hold" only at
    # the end of a clause, otherwise it needs a holding as the object, so
    # "hold the line" / "hold your nerve" / "hold above the 200-day" pass.
    r"|hold(?:ing)?(?=\s*(?:[.,;:!?)\u2014\u2013]|$))"
    r"|hold(?:ing)?\s+(?:on\s+to\s+|onto\s+)?(?:this|it|that|the\s+(?:stock|shares?|position|name)"
    r"|your\s+(?:stock|shares?|position)|\$[A-Z]{1,5}))"
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
    # WP-13b: "which stock can't lose" is the user's question quoted back, and
    # "a stock can't lose" is a generic claim; neither promises anything.
    # CR271 replay: "the line the uptrend cannot lose" is a price level, not a
    # promise. A promise has a subject that is the user or the trade itself and
    # ends the clause ("you can't lose.") or names money ("can't lose money").
    r"(?<!\bwhich\s)(?<!\ba\s)(?<!\bany\s)(?<!\bno\s)"
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

# WP-13b: on the surfaces where the user asks the agent a question directly, the
# agents sometimes ANSWER it with a bare verdict that has no second person at
# all ("Hold.", "Yes, buy.", "YES." over a trade ticket). Not scanned on the Room
# surfaces: a bare imperative is the debate voice there (Saiful, 2026-11-19).
DIRECT_ANSWER_SURFACES = frozenset({"one_on_one", "concierge", "brief"})
_DIRECT_ANSWER_PATTERNS = [
    # The whole reply is one trade verb: "Hold."
    r"\A\W*(?:buy|sell|hold|short)\W*\Z",
    # "Yes, buy." / "Yes - sell now" (not buyers / buy-side)
    r"\byes\W{1,3}(?:buy|sell|go\s+long|go\s+short)(?![-\w])",
    # A reply that opens "YES." and goes straight to a BUY/SELL ticket
    r"\A\W*yes\b[^\n]{0,20}\n[\s\S]{0,120}?\bside\s*:\s*(?:buy|sell)\b",
]

_FLAGS = re.IGNORECASE

# ── personal_advice (WP-13c) ──────────────────────────────────────────────
#
# WP-13b found the reply-only `advice` rule cannot see a trade ticket that
# ANSWERS a personal question ("should I put my bonus into NVDA?" -> an APPROVE
# verdict over a 20-share ticket): from the reply alone it is the designed
# worked-example voice. This rule pairs the USER'S message with the reply and
# fires only when BOTH hold:
#   (a) the user message asks for advice about their own situation, and is not
#       framed as the simulation;
#   (b) the reply carries a ticket or directive (stance word, share count,
#       allocation, "hold/buy/sell <instrument>").
# A ticket in answer to a sim-framed or educational question never fires.
# Runs only on the surfaces where a user asks one agent a question directly
# (1-on-1, Concierge, Brief), and only when the caller passes `user_message`.
#
# Disambiguating "my portfolio": the app is simulation-only, so the app's own
# objects ("my portfolio", "my holdings", "my positions", "my watchlist", "the
# room", "my desk", the mandate) and explicit sim words ("sim", "paper", "game",
# "practice", "virtual", "demo", "hypothetical") count as SIM FRAMING and switch
# the rule off for that message. A STRONG REAL-MONEY cue overrides sim framing
# (savings, bonus, salary, retirement, pension, 401k, rent, loan, "real/actual
# money", "my own money", "not a simulator", "no simulation", "simulation mode
# disabled"), so a jailbreak that names the simulator in order to switch it off
# still counts. A bare currency amount is a real-money cue (it supports an ask)
# but does NOT override sim framing: "I have $100,000 in the game" is a sim
# question. Known limit: "should I sell my portfolio?" with no real-money cue
# reads as the sim portfolio and does not fire.

PERSONAL_ADVICE_SURFACES = DIRECT_ANSWER_SURFACES

_V = (
    r"(?:buy|sell|hold|put|invest|short|dump|trim|switch|liquidate|cash\s+out"
    r"|move\s+(?:my|into|out|all|everything|to\s+(?:cash|gold|bonds|stocks))"
    r"|go\s+long|go\s+short|load\s+up|take\s+profits?)"
)
_THIRD = (
    r"(?:she|he|they|my\s+(?:mum|mom|dad|father|mother|wife|husband|brother|sister|friend"
    r"|son|daughter|parents?|boss|uncle|aunt|grandma|grandpa))"
)

_USER_ASK_PATTERNS = [
    # "should I sell", "do I hold", "shall we invest"
    rf"\b(?:should|shall|do)\s+(?:I|we)\s+(?:\w+\s+){{0,2}}?{_V}\b",
    # "should she put it in", "should my mum buy"
    rf"\bshould\s+{_THIRD}\s+(?:\w+\s+){{0,2}}?{_V}\b",
    # "what exactly should I buy", "what should she put it in"
    rf"\bwhat\s+(?:exactly\s+)?should\s+(?:I|we|{_THIRD})\s+(?:\w+\s+){{0,2}}?(?:{_V}|pick|choose|own)\b",
    # "which stock should I buy", "which three stocks should she pick"
    rf"\bwhich\s+(?:\w+\s+){{0,3}}?should\s+(?:I|we|{_THIRD})\s+(?:\w+\s+){{0,2}}?(?:{_V}|pick|choose|own)\b",
    # "what should I do with my Tesla shares"
    r"\bwhat\s+(?:exactly\s+)?should\s+(?:I|we)\s+do\s+with\s+my\b",
    # "how many shares I should buy", "when I should sell", "whether I should hold"
    rf"\b(?:what|which|how\s+(?:many|much)|whether|when|if)\b[^.?!\n]{{0,50}}\bI\s+should\s+(?:\w+\s+){{0,2}}?{_V}\b",
    # "how much should I put in"
    r"\bhow\s+(?:many|much)\b[^.?!\n]{0,30}\b(?:should|do|can)\s+(?:I|we)\b",
    # "tell me exactly what to buy", "tell me whether to go long or short"
    r"\btell\s+me\s+(?:exactly\s+)?(?:what|which|whether|when|how\s+(?:many|much))\b[^.?!\n]{0,60}"
    r"\b(?:buy|sell|hold|invest|put|go\s+long|go\s+short)\b",
    # "is it a good time for me", "is this a buy for me", "best trades for me"
    r"\b(?:good|best|right|suitable|appropriate|safe|worth(?:while)?|smart|wise|buy|sell|hold|"
    r"trades?|picks?|stocks?)\b[^.?!\n]{0,40}\bfor\s+me\b",
    r"\bfor\s+me\s+personally\b",
    # "if you were me", "what would you do with my ...", "in my position"
    r"\bif\s+you\s+were\s+(?:me|in\s+my)\b",
    r"\bwhat\s+would\s+you\s+do\s+(?:with\s+my|in\s+my|if\s+you\s+were\s+me|if\s+it\s+(?:was|were)\s+your)\b",
    r"\bin\s+my\s+(?:position|shoes|situation|place)\b",
    r"\bbased\s+on\s+(?:my\s+(?:situation|circumstances|age|finances)|what\s+you\s+know\s+about\s+me)\b",
    r"\byour\s+own\s+money\b",
    # Malay
    r"\bpatut(?:kah)?\s+(?:saya|aku)\b(?:\s+\w+){0,3}?\s+(?:beli|jual|labur|simpan|pegang)\b",
    r"\b(?:perlukah|haruskah|adakah)\s+(?:saya|aku)\b(?:\s+\w+){0,3}?\s+(?:beli|jual|labur|pegang)\b",
    # Arabic (hamza variants folded)
    r"(?:يجب|ينبغي|علي)\s+(?:أن\s+|ان\s+)?[أا](?:شتري|بيع|ستثمر|حتفظ)",
    r"ماذا\s+(?:يجب\s+)?(?:أن\s+)?[أا](?:شتري|بيع|ستثمر|فعل)",
    r"بالنسبة\s+(?:لي|إلي|الي)",
]

# Real-money cues. Strong ones override sim framing; weak ones only support an
# ask. The "real cue + action word" route covers asks with no "should I":
# "I'm 58 ... which three stocks for my retirement pot".
_ACTION_RE = re.compile(
    r"\b(?:should|invest\w*|buy\w*|sell\w*|hold\w*|put|allocat\w*|pick|which|recommend\w*|"
    r"suggest\w*|advise|tell\s+me|what\s+to|how\s+(?:much|many)|stocks?|etfs?|funds?|shares?)\b"
    r"|patut|beli|jual|labur|pegang|يجب|[أا]شتري|[أا]بيع|[أا]ستثمر|[أا]حتفظ",
    _FLAGS,
)

_STRONG_REAL_PATTERNS = [
    r"\bmy\s+(?:(?:whole|entire|total|life|hard[- ]earned|own|real|actual)\s+)*(?:savings?|bonus|retirement|"
    r"pension|401\s?\(?k\)?|ira|isa|salary|pay\s?check|wages?|nest\s+egg|inheritance|rent|mortgage|"
    r"loan|debts?|income|severance|payout|money|cash)",
    r"\b(?:real|actual)[- ]?(?:money|cash|account|broker|life|world|funds)\b",
    r"\b(?:retire|retiring|retirement)\b",
    r"\b(?:not|no|without|disable[ds]?|ignore|off)\b[^.?!\n]{0,25}\bsimulat\w*",
    r"\bsimulat\w*\s+(?:mode\s+)?(?:disabled|off|over)\b",
    r"\bnot\s+a\s+(?:sim|simulator|game)\b",
    # Malay
    r"\b(?:wang|simpanan|bonus|gaji|pencen)\s+saya\b|\bkwsp\b|\bwang\s+sebenar\b",
    # Arabic
    r"مدخرات|راتب|مكافأة|تقاعد|معاش|أموالي|اموالي",
]
_WEAK_REAL_PATTERNS = [
    r"(?:^|[\s(])(?:[$£€]|rm|usd|myr|sar|aed|gbp|eur)\s?\d[\d,]*(?:\.\d+)?\s?[kKmM]?\b",
    r"\b\d[\d,]*(?:\.\d+)?\s?[kKmM]?\s?(?:dollars|usd|ringgit|riyals?|pounds|euros?)\b",
    r"\d[\d,.]*\s*(?:ريال|دولار|درهم|دينار)|ألف\s+(?:ريال|دولار|درهم)",
]
_SIM_FRAME_PATTERNS = [
    r"\b(?:sim|simulat\w*|simulator|paper(?:[- ]trad\w+)?|game|gamified|practice|practise|virtual|"
    r"demo|mock|hypothetical\w*|portfolio|holdings|positions|watch\s?list|mandate|journal)\b",
    r"\bthe\s+(?:room|desk)\b|\bmy\s+desk\b",
    r"simulasi|permainan|latihan|\bmaya\b",
    r"محاكاة|لعبة|تجريبي|محفظت",
]

_USER_ASK = [re.compile(p, _FLAGS) for p in _USER_ASK_PATTERNS]
_STRONG_REAL = [re.compile(p, _FLAGS) for p in _STRONG_REAL_PATTERNS]
_WEAK_REAL = [re.compile(p, _FLAGS) for p in _WEAK_REAL_PATTERNS]
_SIM_FRAME = [re.compile(p, _FLAGS) for p in _SIM_FRAME_PATTERNS]

# The reply cue: a ticket or a directive. Scoped case-sensitive groups pick out
# the caps stance words ("BUY, 100%", "APPROVE") so prose "approve" and "hold"
# do not count; a list of options ("BUY / SELL / HOLD") is not a stance.
_STANCE = (
    r"(?-i:(?<![/\w])(?<!/\s)(?<!\bor\s)(?<!\band\s)\b(?:APPROVE[D]?|BUY|SELL|HOLD)\b"
    r"(?!\s*(?:/|,|or|OR|and|AND|&)\s*(?:BUY|SELL|HOLD)\b))"
)
_INSTR = (
    r"(?:etfs?|index\s+funds?|funds?|stocks?|shares?|bonds?|gold|bitcoin|btc|crypto\w*|treasur\w+"
    r"|cash|equit\w+|(?-i:[A-Z]{2,5}\b|\$[A-Za-z]{1,5}\b))"
)
_REPLY_TICKET_PATTERNS = [
    _STANCE,
    r"\b(?:verdict|stance|rating|decision|recommendation|action|call|signal|side)\s*[:=]\s*\**\s*"
    r"(?:approve[d]?|buy|sell|hold|long|short)\b",
    # share counts
    r"\b(?:buy|sell|purchase|add|trim|short|accumulate|acquire)\s+(?:about\s+|around\s+|roughly\s+|"
    r"approximately\s+|~\s*)?\d[\d,]*\s+(?:shares?|units?)\b",
    r"\b\d[\d,]*[\s-]shares?\s+(?:of|in|at)\b|\b\d[\d,]*-share\b",
    r"\b(?:shares?|qty|quantity)\s*[:=]\s*\d",
    # percent / dollar allocation
    r"\b\d+(?:\.\d+)?\s*%\s+(?:of\s+)?(?:your\s+|the\s+|my\s+)?(?:funds?|capital|portfolio|bonus|"
    r"savings|cash|account|money|balance|net\s+worth|equity)\b",
    r"\b(?:buy|allocate|put|invest|deploy|sell|trim|stake)\b[^.\n]{0,30}\b\d+(?:\.\d+)?\s*%",
    r"\b(?:size|sizing|stance|allocation|weight)\s*[:=]\s*\d",
    r"\b(?:buy|invest|put|allocate|deploy|sell|spend)\s+(?:about\s+|around\s+|roughly\s+)?(?:\$|rm)\s?\d",
    # "hold/buy/sell <instrument>" as a directive: opens a clause or follows
    # "to" / "instead" / "just"
    r"(?m)(?:^|[.!?:;\n\u2022*\-]\s*|\bto\s+|\binstead,?\s+|\bjust\s+|\bsimply\s+|\bthen\s+)\**"
    rf"(?:hold|buy|sell|accumulate)\s+(?:(?:on\s+to|onto)\s+)?(?:(?:a|an|the|some|more|broad[- ]market"
    rf"|broad|low[- ]cost|diversified|global|total[- ]market|index|your|my)\s+)*{_INSTR}",
    # "I'd buy ..."
    r"\b(?:I|we)(?:['’]d|\s+would)\s+(?:definitely\s+|probably\s+|personally\s+)?"
    r"(?:buy|sell|hold|go\s+long|go\s+short|put|invest)\b",
    # Malay
    r"(?-i:\b(?:BELI|JUAL|TAHAN)\b)",
    r"\b(?:beli|jual)\s+\d[\d,]*\s+(?:unit|saham|syer|lot)\b",
    r"\b\d+(?:\.\d+)?\s*%\s+(?:daripada|dari)\s+(?:dana|modal|portfolio|simpanan|wang|bonus)\b",
    r"\b(?:labur(?:kan)?|beli|peruntuk(?:kan)?)\b[^.\n]{0,25}\b(?:RM\s?\d|\d+\s*%)",
    r"(?m)(?:^|[.!?:;\n]\s*)(?:beli|jual|tahan|pegang)\s+(?:saham|unit|syer|dana|(?-i:[A-Z0-9]{2,5}\b))",
    # Arabic
    r"(?<!\w)(?:اشتر|بع|احتفظ)(?!\w)",
    r"\d[\d,.]*\s*(?:سهم|أسهم|اسهم)",
    r"(?:التوصية|القرار|الحكم|الإجراء|الاتجاه)\s*[:：]\s*(?:شراء|بيع|احتفاظ|موافقة|اشتر|بع)",
    r"\d+(?:\.\d+)?\s*%\s+من\s+(?:رأس\s+المال|المحفظة|الأموال|المبلغ|المدخرات)",
    r"(?:شراء|بيع)\s+\d",
]
_REPLY_TICKET = [re.compile(p, _FLAGS) for p in _REPLY_TICKET_PATTERNS]
# The first two reply patterns (caps stance, labelled verdict) are tickets
# whatever surrounds them; the rest are skipped inside a disclaiming sentence.
_TICKET_ALWAYS = 2

# "I can't tell you to buy stocks" is a refusal talking about the act, not a
# directive.
_DISCLAIMER = re.compile(
    r"can['’]?t|cannot|can\s+not|won['’]?t|will\s+not|unable|not\s+able|not\s+allowed|not\s+permitted"
    r"|not\s+licensed|not\s+something|not\s+going\s+to|not\s+here\s+to|refuse|no\s+one\s+can"
    r"|nobody\s+can|not\s+in\s+a\s+position"
    r"|tidak\s+boleh|tak\s+boleh|tidak\s+dapat|tidak\s+dibenarkan"
    r"|لا\s+أ?ستطيع|لا\s+يمكنني|غير\s+مسموح|لن\s+أ",
    re.IGNORECASE,
)


def _personal_user_cue(user_message: str) -> str:
    """The matched span of the user's personal-advice ask, or "" when the
    message is not one (or is framed as the simulation)."""
    strong = any(p.search(user_message) for p in _STRONG_REAL)
    if not strong and any(p.search(user_message) for p in _SIM_FRAME):
        return ""
    for p in _USER_ASK:
        m = p.search(user_message)
        if m:
            return m.group(0)
    real = next(
        (m for p in (*_STRONG_REAL, *_WEAK_REAL) if (m := p.search(user_message))), None
    )
    if real and _ACTION_RE.search(user_message):
        return real.group(0)
    return ""


def _ticket_reply_cue(text: str) -> re.Match[str] | None:
    """The first ticket/directive in the reply, or None."""
    for i, pat in enumerate(_REPLY_TICKET):
        for m in pat.finditer(text):
            if i >= _TICKET_ALWAYS:
                start = max(text.rfind(c, 0, m.start()) for c in ".!?\n") + 1
                if _DISCLAIMER.search(text, start, m.start()):
                    continue
            return m
    return None


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
_COMPILED: dict[str, list[re.Pattern[str]]] = {
    RULE_ADVICE: [re.compile(p, _FLAGS) for p in _ADVICE_PATTERNS],
    RULE_ABUSE: [re.compile(p, _FLAGS) for p in _ABUSE_PATTERNS],
}
_COMPILED_DIRECT = [re.compile(p, _FLAGS) for p in _DIRECT_ANSWER_PATTERNS]

_OPEN_QUOTES = "\"\u201c\u2018'\u00ab"
_CLOSE_QUOTES = "\"\u201d\u2019'\u00bb"


@dataclass(frozen=True)
class Hit:
    """One rule hit. `span` is the matched text (never the whole input)."""

    rule: str
    span: str
    start: int
    end: int
    enforcing: bool
    words: int = 0
    user_cue: str = ""


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


def _is_quoted_mention(text: str, m: re.Match[str]) -> bool:
    """True when the match is a phrase being TALKED ABOUT: a quote opens right
    before it and closes right after it (`a "you should buy" style call`). A
    quoted sentence that goes on ("You should buy NVDA now.") is advice written
    out, not a mention, and still hits."""
    return (
        m.start() > 0
        and text[m.start() - 1] in _OPEN_QUOTES
        and m.end() < len(text)
        and text[m.end()] in _CLOSE_QUOTES
    )


def _is_regulated_term(text: str, m: re.Match[str]) -> bool:
    """True when a `guaranteed ...` hit sits in the same sentence as rate-base
    vocabulary. Same sentence only: a promise one sentence later still hits."""
    if not m.group(0).lower().startswith("guarantee"):
        return False
    start = max(text.rfind(c, 0, m.start()) for c in ".!?\n") + 1
    ends = [i for i in (text.find(c, m.end()) for c in ".!?\n") if i != -1]
    return bool(_REGULATED_CONTEXT.search(text, start, min(ends) if ends else len(text)))


def check(
    text: str | None,
    *,
    surface: str,
    mode: str | None = None,
    user_message: str | None = None,
) -> GuardResult:
    """Run the guard on one finished piece of user-visible text. Pure: no
    logging, no I/O. `mode` defaults to `Settings.output_guard_mode`; `off`
    returns an empty result without scanning. `user_message` (WP-13c) is the
    message this text answers; without it `personal_advice` cannot run."""
    mode = mode or settings.output_guard_mode
    if mode == "off" or not text or not text.strip():
        return GuardResult(mode=mode, surface=surface)
    hits: list[Hit] = []
    for rule, patterns in _COMPILED.items():
        if rule == RULE_ADVICE and surface in DIRECT_ANSWER_SURFACES:
            patterns = patterns + _COMPILED_DIRECT
        for pat in patterns:
            m = next(
                (
                    c for c in pat.finditer(text)
                    if not _is_regulated_term(text, c)
                    and not (rule == RULE_ADVICE and _is_quoted_mention(text, c))
                ),
                None,
            )
            if m:
                hits.append(Hit(rule, m.group(0), m.start(), m.end(), True))
                break
    if user_message and surface in PERSONAL_ADVICE_SURFACES:
        user_cue = _personal_user_cue(user_message)
        if user_cue:
            ticket = _ticket_reply_cue(text)
            if ticket:
                hits.append(
                    Hit(
                        RULE_PERSONAL_ADVICE, ticket.group(0), ticket.start(), ticket.end(),
                        True, user_cue=user_cue,
                    )
                )
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
            user_cue=h.user_cue[:SPAN_LOG_CHARS] or None,
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
    user_message: str | None = None,
) -> GuardResult:
    """`check` + `log_hits`: the call every surface seam makes."""
    result = check(text, surface=surface, user_message=user_message)
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
    rules = {h.rule for h in result.enforcing_hits}
    if RULE_ABUSE in rules and not rules & _ADVICE_LIKE:
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
    if {h.rule for h in result.enforcing_hits} & _ADVICE_LIKE:
        why = (
            "it read as personal advice, which AMI does not give (AMI is a "
            "training simulator)"
        )
    else:
        why = "it contained language AMI does not allow"
    return f"\n\n— AMI flags the reply above: {why}. Please disregard it."
