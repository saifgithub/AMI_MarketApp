"""CR267 WP-22 steps 1-2 — the q1 question set and the three Room graders.

Fakes and mocks only: no Jev, no hosted model, no vLLM. What is pinned here is
the contract the bake-off and WP-23 rely on: six questions with five phrasings
each; Jev refuses an unpinned version; the hosted grader reads token
probabilities when it gets them and falls back to a 1-5 score when it does not,
saying so in `extra["logprobs"]`; the code grader marks a missing card cell
not-computable instead of imputing, and answers `trade_proposed` without cards;
and every grader turns any failure into an `error` with zero answers rather than
raising or defaulting.
"""

from __future__ import annotations

import io
import json
import math
import urllib.error
from pathlib import Path

import pytest

from app.schemas import AgentId
from app.services.llm_gateway import _call_request_overrides
from app.services.room_grader_contract import (
    QUESTION_SET_VERSION,
    Answer,
    QuestionId,
    RoomTranscript,
)
from app.services.room_graders import CodeCardsGrader, HostedLLMGrader, JevGrader
from app.services.room_graders.hosted_llm import p_yes_from_logprobs
from app.services.room_graders.questions import QUESTIONS_PATH, load_question_set

PIN = "jev-1.13.0"
SERVICES = Path(__file__).resolve().parents[2] / "app" / "services"


def _transcript(**kw) -> RoomTranscript:
    base = dict(
        room_id="r1",
        ticker="AAPL",
        risk_score=3,
        horizon="3 months",
        turns=[
            {"agent_id": "bear_researcher", "content": "Debt wall in 2027."},
            {"agent_id": "research_manager", "content": "Coverage is 9.4x."},
        ],
        cards=None,
        proposed_trade={"action": "buy", "size_pct": 2},
    )
    base.update(kw)
    return RoomTranscript(**base)


def _card(item, direction="support", grade="well", nums="1.2B"):
    return {
        "item": item, "direction": direction, "grade": grade,
        "data": "yes", "claim": f"{item} claim", "nums": nums,
    }


_ITEMS = ("eq", "vc", "vh", "bs", "moat")
_DESKS = ("fundamentals_analyst", "bull_researcher", "bear_researcher", "research_manager")
_LIVE = {
    f: "live"
    for f in (
        "free_cash_flow", "roic", "pe", "total_debt", "gross_margin",
    )
}


def _cards(*, drop=None, bear_obj=None, bear_dirs=None):
    by_desk = {}
    for desk in _DESKS:
        cards = []
        for item in _ITEMS:
            if drop == (desk, item):
                continue
            direction = "support"
            if desk == "bear_researcher" and item == "bs":
                direction = "oppose"
            cards.append(_card(item, direction))
        by_desk[desk] = {"cards": cards, "objections": []}
    if bear_obj is not None:
        by_desk["bear_researcher"]["objections"] = [bear_obj]
    return {"cards_by_desk": by_desk, "field_state": dict(_LIVE)}


# ── question set ──────────────────────────────────────────────────────────


def test_question_file_has_six_questions_five_phrasings_each():
    raw = json.loads(QUESTIONS_PATH.read_text())
    assert raw["version"] == QUESTION_SET_VERSION == "q1"
    qs = load_question_set()
    assert {q.id for q in qs.questions} == set(QuestionId)
    assert len(qs.questions) == 6
    agent_ids = {a.value for a in AgentId}
    for q in qs.questions:
        assert len(q.phrasings) == 5
        assert len(set(q.phrasings)) == 5 and q.text not in q.phrasings
        assert q.yes and q.no
        assert set(q.read_from) <= agent_ids


def test_room_runner_does_not_import_graders():
    for name in ("room_runner.py", "room_bank.py"):
        assert "room_graders" not in (SERVICES / name).read_text()


# ── Jev ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("bad", ["latest", "jev-latest", "JEV-LATEST", "", "  "])
def test_jev_refuses_unpinned_version(bad):
    with pytest.raises(ValueError):
        JevGrader(bad)


def _jev_response(overrides=None, model=PIN):
    answers = {
        q.value: {"choice": "yes", "probabilities": {"yes": 0.9, "no": 0.1}}
        for q in QuestionId
    }
    answers.update(overrides or {})
    return {"answers": answers, "model": model, "usage": {"input_tokens": 100}}


def test_jev_sends_pinned_model_and_parses_answers():
    seen = {}

    def transport(url, headers, body, timeout):
        seen["body"] = json.loads(body)
        seen["headers"] = headers
        return _jev_response(
            {"event_risk_wait": {"choice": "no", "probabilities": {"yes": 0.45, "no": 0.55}}}
        )

    g = JevGrader(PIN, api_key="sekret", transport=transport)
    res = g.grade(_transcript())
    assert res.error is None
    assert seen["body"]["model"] == PIN
    assert set(seen["body"]["questions"]) == {q.value for q in QuestionId}
    assert res.grader == "jev" and res.grader_version == PIN
    assert res.question_set_version == "q1"
    yes = res.get(QuestionId.TRADE_PROPOSED)
    assert yes.answer is Answer.YES and yes.confidence == pytest.approx(0.9)
    assert yes.close is False
    wait = res.get(QuestionId.EVENT_RISK_WAIT)
    assert wait.answer is Answer.NO and wait.confidence == pytest.approx(0.55)
    assert wait.close is True
    assert res.extra["model_matches_pin"] is True
    assert "sekret" not in repr(res)


def test_jev_flags_a_response_model_that_is_not_the_pin():
    g = JevGrader(
        PIN, api_key="k", transport=lambda *a: _jev_response(model="jev-1.14.0")
    )
    res = g.grade(_transcript())
    assert res.error is None
    assert res.extra["model_matches_pin"] is False
    assert res.extra["response_model"] == "jev-1.14.0"


def test_jev_unrecognised_choice_is_not_computable_not_a_default():
    g = JevGrader(
        PIN,
        api_key="k",
        transport=lambda *a: _jev_response({"trade_proposed": {"choice": "maybe"}}),
    )
    res = g.grade(_transcript())
    assert res.get(QuestionId.TRADE_PROPOSED).answer is Answer.NOT_COMPUTABLE


def test_jev_retries_429_then_succeeds():
    calls = []

    def transport(url, headers, body, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.HTTPError(url, 429, "slow", {}, io.BytesIO(b""))
        return _jev_response()

    g = JevGrader(PIN, api_key="k", transport=transport, sleep=lambda s: None)
    assert g.grade(_transcript()).error is None
    assert len(calls) == 2


def test_jev_missing_key_is_an_error_not_a_call(monkeypatch):
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    called = []
    g = JevGrader(PIN, transport=lambda *a: called.append(1))
    res = g.grade(_transcript())
    assert res.error and not res.answers and not called


# ── hosted LLM ────────────────────────────────────────────────────────────


def _lp(answer, p):
    return [
        {"token": "{", "logprob": -0.0, "top_logprobs": []},
        {"token": '"answer"', "logprob": -0.0, "top_logprobs": []},
        {
            "token": answer,
            "logprob": math.log(p),
            "top_logprobs": [
                {"token": answer, "logprob": math.log(p)},
                {"token": "no" if answer == "yes" else "yes", "logprob": math.log(1 - p)},
            ],
        },
    ]


class FakeGateway:
    def __init__(self, script):
        self.script = script
        self.calls = []

    async def stream_chat(self, **kw):
        self.calls.append(kw)
        text, extra = self.script(kw)
        kw["meta"].update(extra)
        yield text


def _yesno_script(answer="yes", p=0.9, logprobs=True, score=4):
    def script(kw):
        if kw["constraint"].name == "room_grader_score":
            return json.dumps({"score": score}), {}
        extra = {"reported_model": "m-x"}
        if logprobs:
            extra["logprobs"] = _lp(answer, p)
        return json.dumps({"answer": answer}), extra

    return script


def test_hosted_reads_logprobs_at_temperature_zero_on_the_named_slot():
    gw = FakeGateway(_yesno_script("yes", 0.9))
    g = HostedLLMGrader("deepinfra_judge", gateway=gw)
    res = g.grade(_transcript())
    assert res.error is None and len(res.answers) == 6
    assert len(gw.calls) == 6
    for c in gw.calls:
        assert c["provider_name"] == "deepinfra_judge"
        assert c["meta"]["request_overrides"]["temperature"] == 0
        assert c["meta"]["request_overrides"]["logprobs"] is True
        assert c["constraint"].json_schema["properties"]["answer"]["enum"] == ["yes", "no"]
    a = res.get(QuestionId.TRADE_PROPOSED)
    assert a.answer is Answer.YES and a.confidence == pytest.approx(0.9)
    assert a.close is False
    assert res.extra["logprobs"] is True
    assert res.extra["served_model"] == "m-x"


def test_hosted_close_when_probability_is_near_half():
    gw = FakeGateway(_yesno_script("no", 0.55))
    res = HostedLLMGrader("s", gateway=gw).grade(_transcript())
    a = res.get(QuestionId.CATALYST_IN_HORIZON)
    assert a.answer is Answer.NO and a.confidence == pytest.approx(0.55)
    assert a.close is True


def test_hosted_falls_back_to_one_to_five_score_without_logprobs():
    gw = FakeGateway(_yesno_script("yes", logprobs=False, score=5))
    res = HostedLLMGrader("s", gateway=gw).grade(_transcript())
    assert res.error is None
    assert res.extra["logprobs"] is False
    assert res.extra["logprobs_missing_questions"] == 6
    assert len(gw.calls) == 12
    a = res.get(QuestionId.BEAR_OBJECTION_ANSWERED)
    assert a.answer is Answer.YES and a.confidence == pytest.approx(1.0)
    assert a.close is False


def test_hosted_score_three_is_close():
    gw = FakeGateway(_yesno_script("no", logprobs=False, score=3))
    res = HostedLLMGrader("s", gateway=gw).grade(_transcript())
    a = res.get(QuestionId.TERMINAL_VULNERABILITY)
    assert a.answer is Answer.NO and a.confidence == pytest.approx(0.5)
    assert a.close is True


def test_hosted_unparseable_reply_is_not_computable():
    def script(kw):
        return "I think so", {}

    res = HostedLLMGrader("s", gateway=FakeGateway(script)).grade(_transcript())
    assert res.error is None
    assert all(a.answer is Answer.NOT_COMPUTABLE for a in res.answers)
    assert res.extra["unparsed_questions"] == 6


def test_hosted_refuses_a_missing_slot():
    with pytest.raises(ValueError):
        HostedLLMGrader("  ")


def test_p_yes_from_logprobs_reads_the_answer_token():
    assert p_yes_from_logprobs(_lp("yes", 0.8)) == pytest.approx(0.8)
    assert p_yes_from_logprobs(_lp("no", 0.8)) == pytest.approx(0.2)
    assert p_yes_from_logprobs(None) is None
    assert p_yes_from_logprobs([{"token": "x", "logprob": -1}]) is None


def test_gateway_request_overrides_are_whitelisted_and_opt_in():
    assert _call_request_overrides({}) == {}
    assert _call_request_overrides(
        {"request_overrides": {"temperature": 0, "logprobs": True, "model": "evil"}}
    ) == {"temperature": 0, "logprobs": True}


# ── plain code over cards ─────────────────────────────────────────────────


def test_code_grader_answers_what_complete_cards_carry():
    obj = {"target": "bs", "severity": "high", "objection": "2027 debt wall"}
    res = CodeCardsGrader().grade(_transcript(cards=_cards(bear_obj=obj)))
    assert res.error is None
    assert res.get(QuestionId.TRADE_PROPOSED).answer is Answer.YES
    assert res.get(QuestionId.THESIS_MATERIAL_DIRECTIONAL).answer is Answer.YES
    assert res.get(QuestionId.CATALYST_IN_HORIZON).answer is Answer.NOT_COMPUTABLE
    assert res.get(QuestionId.EVENT_RISK_WAIT).answer is Answer.NOT_COMPUTABLE
    assert res.get(QuestionId.BEAR_OBJECTION_ANSWERED).answer is Answer.YES
    assert res.get(QuestionId.TERMINAL_VULNERABILITY).answer is Answer.NO
    assert res.cost_usd == 0.0


def test_code_grader_missing_card_cell_is_not_computable_never_imputed():
    res = CodeCardsGrader().grade(
        _transcript(cards=_cards(drop=("research_manager", "bs")))
    )
    assert res.error is None
    for q in (
        QuestionId.THESIS_MATERIAL_DIRECTIONAL,
        QuestionId.TERMINAL_VULNERABILITY,
        QuestionId.BEAR_OBJECTION_ANSWERED,
    ):
        a = res.get(q)
        assert a.answer is Answer.NOT_COMPUTABLE, q
        assert a.confidence is None
    assert res.get(QuestionId.TRADE_PROPOSED).answer is Answer.YES


def test_code_grader_missing_registry_is_not_computable():
    cards = _cards()
    cards["field_state"] = {}
    res = CodeCardsGrader().grade(_transcript(cards=cards))
    assert res.get(QuestionId.THESIS_MATERIAL_DIRECTIONAL).answer is Answer.NOT_COMPUTABLE
    assert res.get(QuestionId.TERMINAL_VULNERABILITY).answer is Answer.NOT_COMPUTABLE


def test_code_grader_unanswered_high_bs_objection_is_a_terminal_vulnerability():
    cards = _cards(bear_obj={"target": "bs", "severity": "high", "objection": "wall"})
    for desk in _DESKS:
        for c in cards["cards_by_desk"][desk]["cards"]:
            if c["item"] == "bs":
                c["direction"] = "oppose"
    res = CodeCardsGrader().grade(_transcript(cards=cards))
    assert res.get(QuestionId.TERMINAL_VULNERABILITY).answer is Answer.YES
    assert res.get(QuestionId.BEAR_OBJECTION_ANSWERED).answer is Answer.NO


def test_code_grader_card_without_item_is_a_missing_cell_not_a_crash():
    res = CodeCardsGrader().grade(
        _transcript(cards={"cards_by_desk": {"bear_researcher": {"cards": [{"bad": 1}]}}})
    )
    assert res.error is None
    assert res.get(QuestionId.THESIS_MATERIAL_DIRECTIONAL).answer is Answer.NOT_COMPUTABLE


def test_code_grader_trade_proposed_needs_no_cards():
    g = CodeCardsGrader()
    yes = g.grade(_transcript(cards=None, proposed_trade={"action": "short"}))
    assert yes.get(QuestionId.TRADE_PROPOSED).answer is Answer.YES
    for other in QuestionId:
        if other is not QuestionId.TRADE_PROPOSED:
            assert yes.get(other).answer is Answer.NOT_COMPUTABLE
    for trade in (None, {}, {"action": "hold"}, {"action": "PASS"}):
        r = g.grade(_transcript(cards=None, proposed_trade=trade))
        assert r.get(QuestionId.TRADE_PROPOSED).answer is Answer.NO, trade
    odd = g.grade(_transcript(cards=None, proposed_trade={"qty": 3}))
    assert odd.get(QuestionId.TRADE_PROPOSED).answer is Answer.NOT_COMPUTABLE


# ── failure handling, every grader ────────────────────────────────────────


def _boom_transport(*a):
    raise urllib.error.URLError("down")


def _http_500(*a):
    raise urllib.error.HTTPError("u", 500, "boom", {}, io.BytesIO(b""))


class _RaisingGateway:
    async def stream_chat(self, **kw):
        raise RuntimeError("provider exploded")
        yield ""


class _StreamErrorGateway:
    async def stream_chat(self, **kw):
        kw["meta"]["stream_error"] = "HTTP 503"
        yield "[AMI error]"


class _TruncatedGateway:
    async def stream_chat(self, **kw):
        kw["meta"]["finish_reason"] = "length"
        yield '{"answer": "ye'


@pytest.mark.parametrize(
    "grader,transcript",
    [
        (JevGrader(PIN, api_key="k", transport=_boom_transport), _transcript()),
        (JevGrader(PIN, api_key="k", transport=_http_500), _transcript()),
        (JevGrader(PIN, api_key="k", transport=lambda *a: {"nope": 1}), _transcript()),
        (HostedLLMGrader("s", gateway=_RaisingGateway()), _transcript()),
        (HostedLLMGrader("s", gateway=_StreamErrorGateway()), _transcript()),
        (HostedLLMGrader("s", gateway=_TruncatedGateway()), _transcript()),
        (CodeCardsGrader(), _transcript(cards={"cards_by_desk": "garbage"})),
        (CodeCardsGrader(), _transcript(cards={"cards_by_desk": {"bear_researcher": [1]}})),
        (CodeCardsGrader(), _transcript(cards={"cards_by_desk": {"x": {"cards": [7]}}})),
    ],
)
def test_every_grader_turns_a_failure_into_error_with_no_answers(grader, transcript):
    res = grader.grade(transcript)
    assert res.error
    assert len(res.answers) == 0
    assert res.question_set_version == "q1"


def test_hosted_grade_inside_a_running_loop_does_not_raise():
    import asyncio

    async def go():
        return HostedLLMGrader("s", gateway=FakeGateway(_yesno_script())).grade(
            _transcript()
        )

    res = asyncio.run(go())
    assert res.error is None and len(res.answers) == 6
