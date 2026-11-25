"""CR267: Ling-only wording for two Room questions (`bear=v2`, `cat=v2`).

Why it exists. The shared questions (`room_questions_q1.json`) were written for and measured on
DeepInfra. On the same 300 WP-20 Rooms Ling answered three of them "yes" far more often than
DeepInfra did (`ling_fit_2026-11-25.md`): `bear_objection_answered` 296 vs 91 and
`catalyst_in_horizon` 272 vs 170. So those questions stopped filtering. (A third,
`thesis_material_directional`, 172 vs 115, was tuned too and not adopted: its stricter wording
agreed better with DeepInfra but made the rule's outcomes diverge, see the fit doc.)

Each variant changes the question's wording and the system prompt (four or five invented worked
examples, a fictional ticker, nothing from any Room) and nothing else. The plan around it is
untouched: five phrasings and the majority for `bear`, one call for `catalyst`,
the shared split rule. DeepInfra never sees this module's text
(`tests/unit/test_cr267_ling_bear_v2.py` and `test_cr267_ling_cat_v2.py` pin that). Each tag
goes into the Ling grader version, so a Room graded with a wording is keyed apart from one graded
with the shared wording.

`bear=v2`. The yes criterion is a rebuttal: a specific figure or fact that counters the Bear's
strongest objection. Acknowledging, restating, accepting it, siding with the Bear, or citing numbers
that do not address it is a no. The system prompt carries four worked examples: a rebuttal with
figures, an accepted objection, an assertion without a figure, and a valuation objection met with
growth figures.
"""

from __future__ import annotations

from app.services.room_grader_contract import QuestionId
from app.services.room_graders.hosted_llm import _SYSTEM_YESNO
from app.services.room_graders.production_plan import QuestionVariant
from app.services.room_graders.questions import Question

BEAR_V2_TAG = "bear=v2"

_TEXT = (
    "Does the Research Manager, or a later turn, rebut the Bear's strongest objection with a "
    "specific figure that directly counters it?"
)
_YES = (
    "the Research Manager or a later turn rebuts the Bear's strongest objection: it names a "
    "specific figure or fact from the data that directly counters that objection, so the "
    "objection is shown to be wrong, smaller than claimed, or already priced in"
)
_NO = (
    "the objection is only acknowledged, restated, or accepted; or the Research Manager sides "
    "with the Bear; or the reply cites numbers that do not address the objection; or it is "
    "answered only by assertion; or no objection was raised"
)
_PHRASINGS = (
    _TEXT,
    "Is the Bear's strongest objection actually refuted by a number or fact from the data, "
    "rather than acknowledged, restated or accepted?",
    "Does any turn after the Bear answer the Bear's top concern head-on with a specific "
    "counter-figure?",
    "Is the Bear's most serious objection countered, with concrete data that cuts against it, "
    "and not simply agreed with or repeated?",
    "Did the Research Manager or a later turn show, with a specific number, that the Bear's "
    "strongest point is wrong or overstated?",
)

_SYSTEM = (
    _SYSTEM_YESNO
    + """

Examples (invented, not from any real debate):
1. Bear: "ZZZ's 0.8x interest coverage cannot service its $400M debt." Research Manager: "Coverage is 0.8x on trailing EBIT, but $310M of the debt is fixed at 2.1% until 2031 and cash of $220M covers the 2027 maturity." -> yes (the Research Manager counters the objection with specific figures).
2. Bear: "ZZZ's 0.8x interest coverage cannot service its $400M debt." Research Manager: "Coverage of 0.8x on $400M of debt is a real risk; avoid." -> no (the objection is accepted and restated).
3. Bear: "ZZZ trades at 38x earnings against a 18x peer median." Research Manager: "ZZZ has strong brand loyalty and a great management team." -> no (assertion, no figure that counters the objection).
4. Bear: "ZZZ trades at 38x earnings against a 18x peer median." Research Manager: "Revenue growth of 22% against a peer 6% and a 5-year EPS CAGR of 19% put the PEG at 1.9x, near the peer's 1.8x." -> yes."""
)

BEAR_V2 = QuestionVariant(
    tag=BEAR_V2_TAG,
    question=Question(
        id=QuestionId.BEAR_OBJECTION_ANSWERED,
        text=_TEXT,
        yes=_YES,
        no=_NO,
        read_from=("bear_researcher", "research_manager"),
        phrasings=_PHRASINGS,
    ),
    system=_SYSTEM,
)


# ── catalyst_in_horizon (`cat=v2`) ──────────────────────────────────────────
# On the 300 WP-20 fit Rooms Ling answered the shared wording "yes" in 272, DeepInfra in 170
# (`ling_fit_2026-11-25.md`): Ling counted a price level, a pullback, a macro meeting (FOMC) or
# "earnings" with no date as a catalyst. The yes criterion here is a named company event with an
# explicit date or count of days inside the horizon, that the decision hinges on. One call per
# Room, as in the shared plan (this question is not averaged).

CATALYST_V2_TAG = "cat=v2"

_CAT_TEXT = (
    "Does the Research Manager or the Execution Desk say that the decision hinges on a named "
    "company event (earnings report, product launch, ruling) that has a stated date or number of "
    "days, inside the horizon?"
)
_CAT_YES = (
    "the Research Manager or the Execution Desk states a named company event with an explicit "
    "date or an explicit count of days or weeks, inside the mandate horizon, and says what "
    "happens when it arrives (enter, add, re-evaluate or exit)"
)
_CAT_NO = (
    "the turns name no company event; or give only price levels, pullbacks or technical "
    "conditions; or mention earnings, macro or index events without an explicit date or count of "
    "days; or say nothing about what the event would change"
)
_CAT_SYSTEM = (
    _SYSTEM_YESNO
    + """

Examples (invented, not from any real debate):
1. Research Manager: "Hold off until the Q3 print on 2027-01-29 (70 days) shows FCF turning positive; then size to the cap." Execution Desk: "WAIT; the print is the trigger." -> yes (a named event with a date, inside the horizon, that the decision turns on).
2. Research Manager: "Buy on a pullback to the 50-day SMA at $341; stop below $332." Execution Desk: "Limit order at $341." -> no (a price level, not a named event).
3. Research Manager: "Valuation is stretched; the next FOMC meeting could move multiples." -> no (a general macro event, not a catalyst specific to this company, and nothing hinges on it).
4. Research Manager: "Earnings are due soon and could surprise either way; I lean long." -> no (no date or timeframe, and the decision does not turn on it).
5. Research Manager: "Entry is justified now. Note the FDA ruling on the lead drug expected within 6 weeks, which the thesis depends on." Execution Desk: "Size 2%, add after the ruling." -> yes."""
)

CATALYST_V2 = QuestionVariant(
    tag=CATALYST_V2_TAG,
    question=Question(
        id=QuestionId.CATALYST_IN_HORIZON,
        text=_CAT_TEXT,
        yes=_CAT_YES,
        no=_CAT_NO,
        read_from=("research_manager", "trader"),
        phrasings=(),
    ),
    system=_CAT_SYSTEM,
)

