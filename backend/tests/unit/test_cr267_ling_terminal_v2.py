"""CR267 — Ling's tighter terminal-vulnerability question (`term=v2`, `ling_terminal.py`).

No network: the grader's transport is the WP-23 `httpx.MockTransport` wire.

1. Default off: the setting defaults to v1, an unknown value refuses to boot, DeepInfra and the
   default Ling version are byte-identical, `|term=v2` appears only when on.
2. Code enforces the fields: each way a "yes" can fail is recorded as "no" with `terminal_rejected`.
3. Grounding is the documented deterministic matcher.
4. Five phrasings, majority, 3-2 close, winning fields from the lowest validated yes phrasing.
5. The wire: five terminal calls vary only the QUESTION line; the US Room reads the US wording of
   two categories; the other questions are untouched; rejected votes are counted in `extra`.
6. The fields persist on the coded record.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import Settings
from app.services import room_decision_rule as rule
from app.services.room_grader_contract import Answer, QuestionAnswer, QuestionId, RoomTranscript
from app.services.room_graders import deepinfra, ling, ling_terminal as T
from app.services.room_runner import _coded_record
from tests.unit import test_cr267_wp23_ling_grader as ling_test

Q = QuestionId.TERMINAL_VULNERABILITY
HAY = (
    "[bear_researcher]\nInterest coverage is 0.8x and RM 310 million of notes mature on 15 March "
    "2027 with no refinancing named.\n[research_manager]\nCash of RM 40 million does not cover it."
)
GOOD = {
    "answer": "yes",
    "terminal_name": "RM310m of notes mature in March 2027 with no refinancing",
    "terminal_category": "debt_default",
    "terminal_evidence": "Bear: RM 310 million of notes mature on 15 March 2027 with no refinancing named",
    "terminal_open_because": "The Research Manager cited RM40m cash, far short of RM310m",
}


def _vote(payload, i=0, hay=HAY):
    return T.parse_vote(json.dumps(payload), i, hay)


# 1. default off


def test_default_is_v1_and_unknown_values_refuse_to_boot():
    assert Settings(_env_file=None).room_grader_ling_terminal == "v1"
    assert Settings(_env_file=None, room_grader_ling_terminal=" V2 ").room_grader_ling_terminal == "v2"
    with pytest.raises(ValueError, match="ROOM_GRADER_LING_TERMINAL"):
        Settings(_env_file=None, room_grader_ling_terminal="v3")
    with pytest.raises(ValueError, match="ROOM_GRADER_LING_TERMINAL"):
        ling.terminal_variant_from_setting("")


def test_versions_only_gain_the_tag_when_on():
    base = ling.grader_version(ling_test.MODEL)
    assert "term=" not in base
    assert ling.grader_version(ling_test.MODEL, terminal_variant=True) == (
        base + "|term=v2|termchk=d1c1.00"
    )
    assert deepinfra.grader_version("m") == (
        "m|t0|avg5:bear_objection_answered+thesis_material_directional|split2|trade=structure"
    )


def test_default_ling_grader_asks_the_shared_terminal_question():
    wire = ling_test.Wire()
    assert ling_test.make_grader(wire).grade(ling_test.transcript()).error is None
    assert not any("QUESTION:" in b["messages"][-1]["content"] for b in wire.bodies)
    assert len(wire.bodies) == 13


# 2. code enforces the fields


def test_a_complete_grounded_yes_counts():
    v = _vote(GOOD)
    assert v.answer is Answer.YES and v.detail["terminal_rejected"] is None


@pytest.mark.parametrize("field", T.FIELDS)
def test_an_empty_field_turns_a_yes_into_a_counted_no(field):
    for empty in (None, "", "   "):
        v = _vote({**GOOD, field: empty})
        assert v.answer is Answer.NO
        assert v.detail["terminal_rejected"] == f"empty_field:{field}"


def test_a_category_outside_the_seven_is_refused():
    v = _vote({**GOOD, "terminal_category": "weak_earnings"})
    assert v.answer is Answer.NO and v.detail["terminal_rejected"] == "category_not_allowed"


def test_evidence_not_in_the_room_is_refused():
    v = _vote({**GOOD, "terminal_evidence": "Auditor flagged a going concern doubt of 12.7 percent"})
    assert v.answer is Answer.NO and v.detail["terminal_rejected"] == "evidence_not_grounded"


def test_a_no_keeps_no_fields_and_a_non_answer_is_not_computable():
    v = _vote({"answer": "no", "terminal_name": "x"})
    assert v.answer is Answer.NO and v.detail["terminal_name"] is None
    assert T.parse_vote("not json", 0, HAY).answer is Answer.NOT_COMPUTABLE
    assert _vote({"answer": "maybe"}).answer is Answer.NOT_COMPUTABLE


def test_fenced_json_parses():
    assert T.parse_vote("```json\n" + json.dumps(GOOD) + "\n```", 0, HAY).answer is Answer.YES


# 3. grounding


@pytest.mark.parametrize("evidence,ok", [
    ("coverage of 0.8x", True),
    ("RM310 million", True),
    ("RM 310 million", True),
    ("3,100 million", False),
    ("matures 15 March 2027", False),
    ("notes mature on 15 March 2027", True),
    ("year 2027 only", False),
    ("margin fell to 12", False),
    ("notes mature on 15 march", True),
    ("management is confident of growth", False),
    ("with no refinancing named", True),
    ("of the and it", False),
])
def test_is_grounded(evidence, ok):
    assert T.is_grounded(evidence, HAY) is ok


def test_numbers_match_whole_tokens_only():
    assert not T.is_grounded("a 10.85 ratio", "ratio 0.85 here")
    assert T.is_grounded("RM 1,234 million", "borrowings of 1234 million")


# 4. the five votes


def _qa(ans, i, **d):
    return QuestionAnswer(Q, ans, detail={"phrasing": i, **d})


def _yes(i, name="n"):
    return _qa(Answer.YES, i, terminal_name=name, terminal_category="debt_default",
               terminal_evidence=f"e{i}", terminal_open_because="o", terminal_rejected=None)


def _no(i, rejected=None):
    return _qa(Answer.NO, i, terminal_rejected=rejected)


def test_majority_yes_takes_the_lowest_phrasing_and_flags_a_split():
    r = T.tally_votes([_no(0), _yes(1), _yes(2), _no(3), _yes(4)], 2)
    assert r.answer is Answer.YES and r.close
    assert r.detail["terminal_evidence"] == "e1" and r.detail["terminal_chosen_phrasing"] == 1


def test_four_one_is_not_close_and_majority_no_carries_no_fields():
    assert not T.tally_votes([_yes(0), _yes(1), _yes(2), _yes(3), _no(4)], 2).close
    r = T.tally_votes([_yes(0), _no(1), _no(2), _no(3), _no(4)], 2)
    assert r.answer is Answer.NO and not r.close
    assert r.detail["terminal_evidence"] is None and r.detail["terminal_rejected"] is None


def test_rejected_votes_are_summarised_even_when_the_answer_is_no():
    r = T.tally_votes([_no(0, "evidence_not_grounded"), _no(1, "evidence_not_grounded"),
                       _no(2), _no(3, "category_not_allowed"), _no(4)], 2)
    assert r.answer is Answer.NO
    assert r.detail["terminal_rejected"] == (
        "3 of 5 yes votes refused: category_not_allowed x1; evidence_not_grounded x2"
    )
    assert T.rejection_counts([_no(0, "a"), _no(1, "a"), _no(2)]) == {"a": 2}


def test_an_unparsed_vote_makes_the_question_not_computable():
    r = T.tally_votes([_yes(0), _qa(Answer.NOT_COMPUTABLE, 1), _yes(2), _yes(3), _yes(4)], 2)
    assert r.answer is Answer.NOT_COMPUTABLE


# 5. the wire


def _term_wire(payload):
    base = ling_test.Wire(default=("no", 0.95))

    async def call(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "QUESTION:" in body["messages"][-1]["content"]:
            base.bodies.append(body)
            return ling_test._sse("yes", 0.9, content=json.dumps(payload))
        return await base(request)

    call.bodies = base.bodies
    return call


UNCOVERED = {  # $M: 310 due in the first bucket against 40 of cash and no FCF -> the yes stands
    "horizon_days": 42, "ladder": [["Within 1 year", 310.0]], "total_cash": 40.0, "fcf_ttm": 0.0,
}


def _grade(payload, ticker="0020.KL", hay=HAY, inputs=UNCOVERED):
    wire = _term_wire(payload)
    g = ling.LingGrader(
        model=ling_test.MODEL, timeout_s=5.0, terminal_variant=True,
        gateway=ling_test.SlotGateway(wire),
    )
    tr = RoomTranscript(
        room_id="r", ticker=ticker, risk_score=5, horizon="long",
        turns=[{"agent_id": "bear_researcher", "content": hay}],
        proposed_trade={"action": "buy", "size_pct": 2.0}, terminal_inputs=inputs,
    )
    return g, g.grade(tr), wire


def test_five_terminal_calls_vary_only_the_question_line():
    g, res, wire = _grade(GOOD)
    assert res.error is None and g.version.endswith("|think=off|bear=v2|cat=v2|term=v2|termchk=d1c1.00")
    term = [b for b in wire.bodies if "QUESTION:" in b["messages"][-1]["content"]]
    assert len(term) == 5 and len(wire.bodies) == 17
    tails = set()
    for b in term:
        user = b["messages"][-1]["content"]
        _head, block = user.split("\n---\n", 1)
        line, rest = block.split("\n\n", 1)
        assert line.removeprefix("QUESTION: ") in T.PHRASINGS
        tails.add(rest)
        assert b["max_tokens"] == T.MAX_TOKENS
        assert b["chat_template_kwargs"]["enable_thinking"] is False
    assert len(tails) == 1
    ans = res.get(Q)
    assert ans.answer is Answer.YES and not ans.close and ans.detail["terminal_category"] == "debt_default"


def test_us_rooms_read_the_us_wording_and_bursa_rooms_the_original():
    bursa = T.question_block("0020.KL", 0)
    us = T.question_block("AAPL", 0)
    assert "- pn17_gn3: PN17 / GN3 status, or a concrete trigger" in bursa
    assert "continued-listing deficiency" in us and "SEC / DOJ action (US)" in us
    assert "SEC / DOJ" not in bursa
    for cat in T.CATEGORIES:
        assert f"- {cat}:" in bursa and f"- {cat}:" in us
    assert bursa.split("DEFINITION")[1].split("ALLOWED")[0] == us.split("DEFINITION")[1].split("ALLOWED")[0]
    assert bursa.split("NOT TERMINAL")[1] == us.split("NOT TERMINAL")[1]


def test_an_ungrounded_yes_is_counted_in_the_result_and_the_answer_is_no():
    _, res, _ = _grade({**GOOD, "terminal_evidence": "going concern doubt of 12.7 percent"})
    ans = res.get(Q)
    assert ans.answer is Answer.NO
    assert ans.detail["terminal_rejected"] == "5 of 5 yes votes refused: evidence_not_grounded x5"
    assert res.extra["terminal_rejected_votes"] == {"evidence_not_grounded": 5}


def test_the_other_twelve_questions_calls_are_the_shared_ones():
    _, _, wire = _grade(GOOD)
    other = [b for b in wire.bodies if "QUESTION:" not in b["messages"][-1]["content"]]
    assert len(other) == 12


# 6. persistence


def test_the_fields_ride_the_coded_record_and_other_answers_carry_none():
    _, res, _ = _grade(GOOD)
    rec = _coded_record(res, rule.decide(res, 5))
    term = next(a for a in rec.answers if a.question == "terminal_vulnerability")
    assert term.answer == "yes" and term.terminal_category == "debt_default"
    assert term.terminal_evidence == GOOD["terminal_evidence"] and term.terminal_rejected is None
    other = next(a for a in rec.answers if a.question == "event_risk_wait")
    assert other.terminal_name is None and other.terminal_rejected is None
