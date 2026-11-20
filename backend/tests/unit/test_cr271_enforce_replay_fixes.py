"""CR271 (CR267 WP-13, enforce replay 2026-11-20) - rule fixes found by replaying
every stored agent reply on Alpha through the guard.

Each negative is a synthetic paraphrase of a false-positive pattern read in the
replay (no stored text is quoted); each positive pins that the tuning did not
loosen the rule it touched.
"""

from __future__ import annotations

import pytest

from app.services.output_guard import check

NEGATIVE_ADVICE = [
    # promise vocabulary used in a negation or a quoted mention
    "This is a calculated risk, not a guaranteed return.",
    "That is not a guaranteed profit; the setup can fail.",
    "A dividend isn't a guaranteed gain either.",
    'You are asking for "guaranteed returns," which no simulation can offer.',
    # a generic hypothetical, not an instruction to the reader
    "And if you must buy before confirmation, do it at 2.5%, not the cap.",
    "Unless you should sell into strength, the thesis stands.",
]

POSITIVE_ADVICE = [
    "This setup gives guaranteed returns.",
    "Trust me, this trade has guaranteed profits.",
    "You should buy this before the print.",
    "Honestly you must sell now.",
]


@pytest.mark.parametrize("text", NEGATIVE_ADVICE)
def test_advice_false_positive_patterns_pass(text):
    assert not check(text, surface="room_turn", mode="enforce").hits, text


@pytest.mark.parametrize("text", POSITIVE_ADVICE)
def test_advice_tuning_did_not_loosen_the_rule(text):
    assert "advice" in check(text, surface="room_turn", mode="enforce").rules, text


@pytest.mark.parametrize(
    "text",
    [
        "There is no near-term catalyst to accelerate or retard the thesis.",
        "Tariffs could retard growth through the next two quarters.",
        "Margins were retarded by freight costs.",
    ],
)
def test_retard_as_a_verb_or_participle_is_not_abuse(text):
    assert not check(text, surface="room_turn", mode="enforce").hits, text


@pytest.mark.parametrize(
    "text",
    [
        "That is a retarded take.",
        "You absolute retard.",
        "Only a retard would hold this.",
        "Shut up, you retard!",
    ],
)
def test_retard_aimed_at_a_person_is_still_abuse(text):
    assert "abuse" in check(text, surface="room_turn", mode="enforce").rules, text


ASK = "Should I put my bonus into this stock?"


@pytest.mark.parametrize(
    "reply",
    [
        # a mandate-cap drawdown figure is not an allocation
        "Horizon matters: a 30% portfolio drawdown on one name needs years to recover.",
        # options being described, not a verdict (English, Malay, Arabic)
        "To rule on a ticket I need inputs: either APPROVE or PASS depends on the stop.",
        "Anda mahu jawapan: **BUY** atau **HOLD/WAIT** bergantung pada saiz.",
        "لكي أستطيع تقديم حكم (إما **APPROVE** أو **PASS**) أحتاج المدخلات.",
        # a quoted example of what the user could type
        'Give me the side, for example: "Suggest BUY for the name", and the stop.',
    ],
)
def test_ticket_cue_ignores_option_lists_quotes_and_risk_figures(reply):
    r = check(reply, surface="one_on_one", mode="enforce", user_message=ASK)
    assert "personal_advice" not in r.rules, reply


@pytest.mark.parametrize(
    "reply",
    [
        "STANCE: BUY MSFT SIZE: 1.5%",
        "Put 20% of your bonus into it.",
        "Verdict: APPROVE. Buy 20 shares.",
        "**BUY**, 100% of the funds.",
    ],
)
def test_ticket_cue_still_fires_on_a_real_ticket(reply):
    r = check(reply, surface="one_on_one", mode="enforce", user_message=ASK)
    assert "personal_advice" in r.rules, reply
