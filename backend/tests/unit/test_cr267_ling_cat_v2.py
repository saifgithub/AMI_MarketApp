"""CR267 — Ling's own wording for `catalyst_in_horizon` (`cat=v2`), in `ling_variants.py`.
Sibling of the `bear=v2` tests. (`thesis_material_directional` was tuned too and not adopted; a
test pins that Ling still asks it in the shared wording.)

No network: both graders' transports are `httpx.MockTransport`, reusing the WP-23 test wires.

1. DeepInfra is unchanged: catalyst goes out in the question file's wording with the shared
   system prompt, and its version string is byte-identical.
2. The Ling variant is selected: one call in the v2 wording with the v2 system prompt.
3. The Ling version carries `|cat=v2` after `|bear=v2`; the wording can be switched back to the
   shared one and is then keyed apart.
4. The plan around the variant is the shared one: 13 calls, catalyst stays a single call.
5. The reply is still the plain yes/no JSON.
6. The worked examples are invented, and a catalyst variant (not averaged) needs no phrasings.
"""

from __future__ import annotations

from app.services.room_grader_contract import Answer, QuestionId
from app.services.room_graders import deepinfra, ling, production_plan
from app.services.room_graders.hosted_llm import _SYSTEM_YESNO
from app.services.room_graders.ling_variants import BEAR_V2, CATALYST_V2, CATALYST_V2_TAG
from app.services.room_graders.questions import load_question_set
from tests.unit import test_cr267_wp23_deepinfra_grader as di_test
from tests.unit import test_cr267_wp23_ling_grader as ling_test

Q = QuestionId
CAT, TH = Q.CATALYST_IN_HORIZON, Q.THESIS_MATERIAL_DIRECTIONAL
SHARED = load_question_set()


def _user_lines(body: dict) -> list[str]:
    return body["messages"][-1]["content"].splitlines()


def _system(body: dict) -> str:
    return next(m["content"] for m in body["messages"] if m["role"] == "system")


def _bodies(wire, qid) -> list[dict]:
    return [b for b in wire.bodies if ling_test._asked(b)[0] is qid]


# ── 1. DeepInfra is unchanged ───────────────────────────────────────────────


def test_deepinfra_asks_catalyst_once_in_the_question_files_wording():
    wire = di_test.Wire()
    assert di_test.make_grader(wire).grade(di_test.transcript()).error is None
    q = SHARED.get(CAT)
    bodies = [b for b in wire.bodies if di_test._asked(b)[0] is CAT]
    assert len(bodies) == 1
    lines = _user_lines(bodies[0])
    assert f"Question: {q.text}" in lines
    assert f"yes means: {q.yes}" in lines and f"no means: {q.no}" in lines
    assert "Examples (invented" not in _system(bodies[0]) and _SYSTEM_YESNO in _system(bodies[0])


def test_the_deepinfra_version_and_the_question_file_wording_are_unchanged():
    assert deepinfra.grader_version("m") == (
        "m|t0|avg5:bear_objection_answered+thesis_material_directional|split2|trade=structure"
    )
    assert di_test.make_grader(di_test.Wire())._variants == {}
    assert SHARED.get(CAT).text == (
        "Does the debate name a specific catalyst that is expected to occur inside the mandate horizon?"
    )
    assert CATALYST_V2.question.text != SHARED.get(CAT).text
    assert CATALYST_V2.question is not SHARED.get(CAT)


# ── 2. the Ling variant is selected ─────────────────────────────────────────


def test_ling_asks_catalyst_once_in_the_v2_wording_with_the_v2_system_prompt():
    wire = ling_test.Wire()
    assert ling_test.make_grader(wire).grade(ling_test.transcript()).error is None
    cat = _bodies(wire, CAT)
    assert len(cat) == 1
    lines = _user_lines(cat[0])
    assert f"Question: {CATALYST_V2.question.text}" in lines
    assert f"yes means: {CATALYST_V2.question.yes}" in lines
    assert f"no means: {CATALYST_V2.question.no}" in lines
    assert _system(cat[0]).count("Examples (invented") == 1 and _SYSTEM_YESNO in _system(cat[0])
    assert cat[0]["max_tokens"] == 64
    assert cat[0]["response_format"]["json_schema"]["schema"]["properties"]["answer"]["enum"] == ["yes", "no"]


def test_the_variant_keeps_the_question_identity_and_has_its_own_system_prompt():
    assert CATALYST_V2.question.id is CAT
    assert CATALYST_V2.question.read_from == SHARED.get(CAT).read_from
    assert CATALYST_V2.tag == CATALYST_V2_TAG == "cat=v2"
    assert CATALYST_V2.system != BEAR_V2.system


def test_the_other_questions_keep_the_shared_wording_and_thesis_was_not_adopted():
    wire = ling_test.Wire()
    assert ling_test.make_grader(wire).grade(ling_test.transcript()).error is None
    for qid in (Q.TERMINAL_VULNERABILITY, Q.EVENT_RISK_WAIT):
        (b,) = _bodies(wire, qid)
        assert f"Question: {SHARED.get(qid).text}" in _user_lines(b)
        assert "Examples (invented" not in _system(b)
    th = _bodies(wire, TH)
    assert sorted(ling_test._asked(b)[1] for b in th) == [0, 1, 2, 3, 4]
    th_q = SHARED.get(TH)
    for b in th:
        _q, i = ling_test._asked(b)
        assert f"Question: {th_q.phrasings[i]}" in _user_lines(b)
        assert "Examples (invented" not in _system(b)
    assert TH not in ling.LingGrader(model=ling_test.MODEL)._variants


# ── 3. version string ───────────────────────────────────────────────────────


def test_the_ling_version_carries_both_tags_in_order():
    full = ling.grader_version(ling_test.MODEL)
    assert full.endswith("|think=off|bear=v2|cat=v2")
    assert ling.LingGrader(model=ling_test.MODEL).version == full


def test_the_catalyst_wording_can_be_switched_back_and_is_keyed_apart():
    base = ling.grader_version(ling_test.MODEL, bear_variant=False, catalyst_variant=False)
    only_cat = ling.grader_version(ling_test.MODEL, bear_variant=False)
    assert only_cat == base + "|cat=v2"
    g = ling.LingGrader(model=ling_test.MODEL, bear_variant=False)
    assert g.version == only_cat and set(g._variants) == {CAT}
    off = ling.LingGrader(model=ling_test.MODEL, catalyst_variant=False)
    assert CAT not in off._variants and off.version.endswith("|think=off|bear=v2")
    assert len({base, only_cat, ling.grader_version(ling_test.MODEL)}) == 3


# ── 4. the plan around the variant ──────────────────────────────────────────


def test_ling_still_asks_thirteen_calls_with_catalyst_a_single_call():
    wire = ling_test.Wire()
    assert ling_test.make_grader(wire).grade(ling_test.transcript()).error is None
    assert len(wire.bodies) == 13
    asked = wire.asked()
    assert [p for q, p in asked if q is CAT] == [None]
    for qid in production_plan.AVERAGED_QUESTIONS:
        assert sorted(p for q, p in asked if q is qid) == [0, 1, 2, 3, 4]


def test_the_catalyst_answer_is_the_single_calls_answer():
    res = ling_test.make_grader(ling_test.Wire({CAT: ("yes", 0.9)})).grade(ling_test.transcript())
    assert res.get(CAT).answer is Answer.YES and res.get(CAT).close is False
    res = ling_test.make_grader(ling_test.Wire({CAT: ("no", 0.9)})).grade(ling_test.transcript())
    assert res.get(CAT).answer is Answer.NO


# ── 5. reply shape ──────────────────────────────────────────────────────────


def test_a_non_yes_no_reply_is_unparsed_and_not_computable():
    wire = ling_test.Wire(content='{"event": "x", "answer_is": "yes"}')
    res = ling_test.make_grader(wire).grade(ling_test.transcript())
    assert res.extra["unparsed_questions"] > 0
    assert res.get(CAT).answer is Answer.NOT_COMPUTABLE


# ── 6. examples and validation ──────────────────────────────────────────────


def test_the_examples_are_invented_not_taken_from_a_room():
    assert "invented, not from any real debate" in CATALYST_V2.system
    assert "-> yes" in CATALYST_V2.system and "-> no" in CATALYST_V2.system


def test_a_catalyst_variant_needs_no_phrasings_because_the_question_is_not_averaged():
    assert CAT not in production_plan.AVERAGED_QUESTIONS
    assert CATALYST_V2.question.phrasings == ()
    production_plan.ProductionPlanGrader("vllm_fallback", timeout_s=5.0, variants=[CATALYST_V2])
