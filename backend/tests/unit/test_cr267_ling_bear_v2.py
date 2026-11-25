"""CR267 — Ling's own wording for `bear_objection_answered` (`bear=v2`, `ling_variants.py`).

No network: both graders' transports are `httpx.MockTransport`, reusing the WP-23 test wires.

1. DeepInfra is unchanged: it carries no variant, asks the question file's five phrasings with
   the shared system prompt, and its version string is byte-identical.
2. The Ling variant is selected: the bear question goes out in the v2 wording and system prompt,
   the other four questions and `thesis_material_directional` stay on the shared wording.
3. The version string carries `|bear=v2`, and the shared-wording Ling is still buildable and keyed apart.
4. The plan around the variant is the shared one: five phrasings, majority, the 3-2 split rule.
5. The reply is still the plain yes/no JSON, so a v2 reply parses exactly as before and a
   non-yes/no reply is still counted unparsed.
6. A variant that cannot supply five phrasings is refused.
"""

from __future__ import annotations

import json

import pytest

from app.core.config import settings
from app.services import room_bank
from app.services.room_grader_contract import Answer, QuestionId
from app.services.room_graders import deepinfra, ling, production_plan
from app.services.room_graders.hosted_llm import _SYSTEM_YESNO
from app.services.room_graders.ling_variants import BEAR_V2, BEAR_V2_TAG
from app.services.room_graders.production_plan import QuestionVariant
from app.services.room_graders.questions import load_question_set
from tests.unit import test_cr267_wp23_deepinfra_grader as di_test
from tests.unit import test_cr267_wp23_ling_grader as ling_test

Q = QuestionId
BEAR = Q.BEAR_OBJECTION_ANSWERED
SHARED = load_question_set().get(BEAR)


def _user_lines(body: dict) -> list[str]:
    return body["messages"][-1]["content"].splitlines()


def _system(body: dict) -> str:
    return next(m["content"] for m in body["messages"] if m["role"] == "system")


def _bear_bodies(wire) -> list[dict]:
    return [b for b in wire.bodies if ling_test._asked(b)[0] is BEAR]


# ── 1. DeepInfra is unchanged ───────────────────────────────────────────────


def test_deepinfra_has_no_variant_and_the_same_version():
    g = di_test.make_grader(di_test.Wire())
    assert g._variants == {}
    assert deepinfra.grader_version("m") == (
        "m|t0|avg5:bear_objection_answered+thesis_material_directional|split2|trade=structure"
    )


def test_deepinfra_asks_the_question_files_bear_wording_and_the_shared_system_prompt():
    wire = di_test.Wire()
    assert di_test.make_grader(wire).grade(di_test.transcript()).error is None
    bear = [b for b in wire.bodies if di_test._asked(b)[0] is BEAR]
    assert sorted(di_test._asked(b)[1] for b in bear) == [0, 1, 2, 3, 4]
    for b in bear:
        _qid, i = di_test._asked(b)
        lines = _user_lines(b)
        assert f"Question: {SHARED.phrasings[i]}" in lines
        assert f"yes means: {SHARED.yes}" in lines and f"no means: {SHARED.no}" in lines
        assert "Examples (invented" not in _system(b)
        assert _SYSTEM_YESNO in _system(b)


def test_the_question_file_still_holds_the_wording_deepinfra_was_measured_on():
    assert SHARED.text == (
        "Does the Research Manager's reply, or any later turn, answer the Bear's strongest "
        "objection with specific numbers drawn from the data?"
    )
    assert SHARED.phrasings[0] == "Is the Bear's strongest objection answered with numbers?"
    assert BEAR_V2.question.text not in (SHARED.text, *SHARED.phrasings)


def test_the_shared_plan_object_is_untouched_by_the_variant():
    assert production_plan.ProductionPlanGrader._grade_all is ling.LingGrader._grade_all
    assert ling.LingGrader._grade_all is deepinfra.DeepInfraGrader._grade_all
    assert load_question_set().get(BEAR) is SHARED


# ── 2. the Ling variant is selected ─────────────────────────────────────────


def test_ling_asks_the_bear_question_in_the_v2_wording_with_the_v2_system_prompt():
    wire = ling_test.Wire()
    assert ling_test.make_grader(wire).grade(ling_test.transcript()).error is None
    bear = _bear_bodies(wire)
    assert sorted(ling_test._asked(b)[1] for b in bear) == [0, 1, 2, 3, 4]
    for b in bear:
        _qid, i = ling_test._asked(b)
        lines = _user_lines(b)
        assert f"Question: {BEAR_V2.question.phrasings[i]}" in lines
        assert f"yes means: {BEAR_V2.question.yes}" in lines
        assert f"no means: {BEAR_V2.question.no}" in lines
        assert "Examples (invented" in _system(b) and _SYSTEM_YESNO in _system(b)
        assert b["response_format"]["json_schema"]["schema"]["properties"]["answer"]["enum"] == ["yes", "no"]
        assert b["max_tokens"] == 64


def test_every_other_ling_question_keeps_the_shared_wording_and_system_prompt():
    wire = ling_test.Wire()
    assert ling_test.make_grader(wire).grade(ling_test.transcript()).error is None
    shared = load_question_set()
    others = [b for b in wire.bodies if ling_test._asked(b)[0] is not BEAR]
    assert len(others) == 8
    for b in others:
        qid, i = ling_test._asked(b)
        q = shared.get(qid)
        assert f"Question: {q.text_for(i)}" in _user_lines(b)
        assert "Examples (invented" not in _system(b)


def test_the_variant_is_ling_only_and_keeps_the_question_identity():
    q = BEAR_V2.question
    assert (q.id, q.read_from) == (SHARED.id, SHARED.read_from)
    assert len(q.phrasings) == production_plan.PHRASING_COUNT == 5
    assert BEAR_V2.tag == BEAR_V2_TAG == "bear=v2"
    assert set(ling.LingGrader(model=ling_test.MODEL)._variants) == {BEAR}


def test_the_examples_are_invented_not_taken_from_a_room():
    system = BEAR_V2.system
    assert "ZZZ" in system and "invented, not from any real debate" in system
    assert "yes" in system and "-> no" in system


# ── 3. version string ───────────────────────────────────────────────────────


def test_the_ling_version_ends_with_the_bear_tag_and_the_shared_wording_is_keyed_apart():
    v2 = ling.grader_version(ling_test.MODEL)
    shared = ling.grader_version(ling_test.MODEL, bear_variant=False)
    assert v2 == shared + "|bear=v2"
    assert shared == (
        "ling:ling-3.0-flash-fin-fp4|t0|avg5:bear_objection_answered+thesis_material_directional"
        "|split2|trade=structure|think=off"
    )
    g = ling.LingGrader(model=ling_test.MODEL, bear_variant=False)
    assert g.version == shared and g._variants == {}
    assert ling.LingGrader(model=ling_test.MODEL).version == v2


def test_the_ling_result_and_the_policy_key_carry_the_tag(monkeypatch):
    res = ling_test.make_grader(ling_test.Wire()).grade(ling_test.transcript())
    assert res.grader_version.endswith("|bear=v2")
    monkeypatch.setattr(settings, "room_coded_rule_enabled", True)
    monkeypatch.setattr(settings, "room_grader", "ling")
    monkeypatch.setattr(settings, "vllm_fallback_base_url", ling_test.BASE)
    monkeypatch.setattr(settings, "vllm_fallback_model", ling_test.MODEL)
    assert "|think=off|bear=v2|" in room_bank.coded_rule_identity()["policy"]


# ── 4. the plan around the variant ──────────────────────────────────────────


def test_a_three_two_split_on_the_variant_is_close_and_a_four_one_is_not():
    three_two = {(BEAR, i): ("yes" if i < 3 else "no", 0.95) for i in range(5)}
    res = ling_test.make_grader(ling_test.Wire(three_two)).grade(ling_test.transcript())
    bear = res.get(BEAR)
    assert bear.answer is Answer.YES and bear.close is True and "3/5 phrasings yes (split)" in bear.rationale
    four_one = {(BEAR, i): ("yes" if i < 4 else "no", 0.95) for i in range(5)}
    res = ling_test.make_grader(ling_test.Wire(four_one)).grade(ling_test.transcript())
    assert res.get(BEAR).answer is Answer.YES and res.get(BEAR).close is False
    one_four = {(BEAR, i): ("yes" if i < 1 else "no", 0.95) for i in range(5)}
    res = ling_test.make_grader(ling_test.Wire(one_four)).grade(ling_test.transcript())
    assert res.get(BEAR).answer is Answer.NO


def test_a_ling_run_still_asks_thirteen_calls_five_per_fragile_question():
    wire = ling_test.Wire()
    assert ling_test.make_grader(wire).grade(ling_test.transcript()).error is None
    assert len(wire.bodies) == 13
    asked = wire.asked()
    for qid in production_plan.AVERAGED_QUESTIONS:
        assert sorted(p for q, p in asked if q is qid) == [0, 1, 2, 3, 4]


# ── 5. reply shape ──────────────────────────────────────────────────────────


def test_the_v2_reply_is_the_plain_yes_no_json():
    wire = ling_test.Wire({BEAR: ("yes", 0.9)})
    res = ling_test.make_grader(wire).grade(ling_test.transcript())
    assert res.error is None and res.extra["unparsed_questions"] == 0
    assert res.get(BEAR).answer is Answer.YES
    schema = _bear_bodies(wire)[0]["response_format"]["json_schema"]["schema"]
    assert list(schema["properties"]) == ["answer"] and schema["required"] == ["answer"]


def test_a_non_yes_no_bear_reply_is_unparsed_and_not_computable():
    wire = ling_test.Wire(content=json.dumps({"objection": "x", "answered": "yes"}))
    res = ling_test.make_grader(wire).grade(ling_test.transcript())
    assert res.extra["unparsed_questions"] > 0
    assert res.get(BEAR).answer is Answer.NOT_COMPUTABLE


# ── 6. variant validation ───────────────────────────────────────────────────


def test_a_variant_without_five_phrasings_is_refused():
    short = QuestionVariant(
        tag="bear=short",
        question=type(BEAR_V2.question)(
            id=BEAR, text="t", yes="y", no="n", read_from=(), phrasings=("a", "b"),
        ),
    )
    with pytest.raises(ValueError, match="5 phrasings"):
        production_plan.ProductionPlanGrader("vllm_fallback", timeout_s=5.0, variants=[short])
