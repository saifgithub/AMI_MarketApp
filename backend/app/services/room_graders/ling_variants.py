"""CR267: Ling-only wording for the `bear_objection_answered` question (`bear=v2`).

Why it exists. The shared question (`room_questions_q1.json`) was written for and measured on
DeepInfra. On the same 300 WP-20 Rooms Ling answered it "yes" in 296 and DeepInfra in 91, and
the two agreed on 95 (`ling_fit_2026-11-25.md`): Ling counted a Research Manager who merely
cites numbers, or who sides with the Bear and repeats the Bear's own figures, as having
"answered" the objection. So the question stopped filtering.

What changed, and only for Ling:

1. The yes criterion is a rebuttal: a specific figure or fact that counters the Bear's
   strongest objection. Acknowledging, restating, accepting it, siding with the Bear, or
   citing numbers that do not address it is a no.
2. The system prompt carries four invented worked examples (a fictional ticker, nothing from
   any Room) showing a rebuttal with figures, an accepted objection, an assertion without a
   figure, and a valuation objection met with growth figures.

The plan around it is untouched: five phrasings, the majority, the shared split rule. DeepInfra
never sees this module's text (`tests/unit/test_cr267_ling_bear_v2.py` pins that). The tag below
goes into the Ling grader version, so a Room graded with this wording is keyed apart from one
graded with the shared wording.
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
