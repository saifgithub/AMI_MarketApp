"""CR267 WP-23 gate S3 — the DeepInfra grader the coded rule runs.

No network: the grader's own OpenAI-compatible client is pointed at an
`httpx.MockTransport`, so the real request body, headers and SSE parsing are exercised.

1. Registered under `ROOM_GRADER=deepinfra`; a missing key / unpinned model refuses to
   build (loud), and boot refuses the rule-on + no-key combination.
2. The request: temperature 0, the pinned model, JSON-schema constraint, bearer key,
   token probabilities; `trade_proposed` is never asked of the model.
3. `trade_proposed` comes from the structured trade.
4. The two fragile questions are asked over five phrasings: majority wins, any split is
   `close`, so the rule rates it Contested when the flip would change the decision.
5. An HTTP error or a timeout fails the grade, and the Room ends "decision unavailable".
6. The desks' provider allow-list and the gateway are untouched; the policy version
   names the model and the averaging.
"""

from __future__ import annotations

import asyncio
import json
import math

import httpx
import pytest

from app.core.config import Settings, settings
from app.services import llm_gateway, room_bank
from app.services import room_decision_rule as rule
from app.services.llm_gateway import VLLMProvider
from app.services.room_grader_contract import (
    Answer,
    QuestionAnswer,
    QuestionId,
    RoomTranscript,
)
from app.services.room_grader_registry import (
    register_grader,
    registered_graders,
    resolve_grader,
    unregister_grader,
)
from app.services.room_graders.deepinfra import (
    AVERAGED_QUESTIONS,
    PHRASING_COUNT,
    DeepInfraGrader,
    average_votes,
    grader_version,
)
from app.services.room_graders.questions import load_question_set

Q = QuestionId
MODEL = "deepseek-ai/DeepSeek-V4-Flash"
BASE = "https://api.deepinfra.com/v1/openai"
KEY = "test-key-not-real"

_TEXT_TO_QUESTION: dict[str, tuple[Q, int | None]] = {}
for _q in load_question_set().questions:
    _TEXT_TO_QUESTION[_q.text] = (_q.id, None)
    for _i, _p in enumerate(_q.phrasings):
        _TEXT_TO_QUESTION[_p] = (_q.id, _i)


def _asked(body: dict) -> tuple[Q, int | None]:
    user = body["messages"][-1]["content"]
    line = next(x for x in user.splitlines() if x.startswith("Question: "))
    return _TEXT_TO_QUESTION[line[len("Question: "):]]


def _sse(answer: str, p: float, model: str = MODEL) -> httpx.Response:
    lp = [{
        "token": answer, "logprob": math.log(p),
        "top_logprobs": [
            {"token": answer, "logprob": math.log(p)},
            {"token": "no" if answer == "yes" else "yes", "logprob": math.log(1 - p)},
        ],
    }]
    frames = [
        {"model": model, "choices": [{
            "delta": {"content": json.dumps({"answer": answer})},
            "logprobs": {"content": lp}, "finish_reason": None,
        }]},
        {"model": model, "choices": [{"delta": {}, "finish_reason": "stop"}]},
        {"model": model, "choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 5}},
    ]
    body = "".join(f"data: {json.dumps(f)}\n\n" for f in frames) + "data: [DONE]\n\n"
    return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})


class Wire:
    """A scripted DeepInfra: `answers[(question, phrasing)]` or `answers[question]`."""

    def __init__(self, answers=None, *, status=200, delay=0.0, default=("no", 0.95)):
        self.answers = answers or {}
        self.status, self.delay, self.default = status, delay, default
        self.requests: list[httpx.Request] = []
        self.bodies: list[dict] = []

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        body = json.loads(request.content)
        self.bodies.append(body)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.status != 200:
            return httpx.Response(self.status, text="upstream broke")
        qid, phrasing = _asked(body)
        answer, p = self.answers.get((qid, phrasing), self.answers.get(qid, self.default))
        return _sse(answer, p)

    def asked(self) -> list[tuple[Q, int | None]]:
        return [_asked(b) for b in self.bodies]


def make_grader(wire: Wire, *, timeout_s=5.0, model=MODEL) -> DeepInfraGrader:
    def factory():
        provider = VLLMProvider(
            base_url=BASE, model_name=model, api_key=KEY, timeout_seconds=timeout_s,
            kind="openai", name="room_grader_deepinfra",
        )
        provider._client = httpx.AsyncClient(
            base_url="https://api.deepinfra.com", headers=provider._client.headers,
            transport=httpx.MockTransport(wire), timeout=timeout_s,
        )
        return provider

    return DeepInfraGrader(
        base_url=BASE, model=model, api_key=KEY, timeout_s=timeout_s,
        provider_factory=factory,
    )


def transcript(trade=None, risk=3) -> RoomTranscript:
    return RoomTranscript(
        room_id="r1", ticker="AAPL", risk_score=risk, horizon="long",
        turns=[
            {"agent_id": "bull_researcher", "content": "bull case"},
            {"agent_id": "bear_researcher", "content": "bear case"},
        ],
        proposed_trade=trade if trade is not None else {"action": "buy", "size_pct": 2.0},
    )


# ── registration and construction ───────────────────────────────────────────


def test_deepinfra_is_a_registered_grader_name():
    assert "deepinfra" in registered_graders()


def test_resolve_builds_the_grader_from_settings(monkeypatch):
    monkeypatch.setattr(settings, "room_grader_deepinfra_api_key", KEY)
    monkeypatch.setattr(settings, "room_grader_deepinfra_model", MODEL)
    g = resolve_grader("deepinfra")
    assert isinstance(g, DeepInfraGrader)
    assert g.name == "deepinfra" and g.version == grader_version(MODEL)


def test_resolve_with_no_key_refuses_to_build(monkeypatch):
    monkeypatch.setattr(settings, "room_grader_deepinfra_api_key", "")
    with pytest.raises(ValueError, match="no API key"):
        resolve_grader("deepinfra")


@pytest.mark.parametrize("model", ["", "  ", "deepseek-latest", "latest"])
def test_an_unpinned_model_is_refused(model):
    with pytest.raises(ValueError, match="pinned"):
        DeepInfraGrader(base_url=BASE, model=model, api_key=KEY)


def _settings(**kw):
    return Settings(_env_file=None, **kw)


def test_boot_refuses_rule_on_with_deepinfra_and_no_key():
    with pytest.raises(ValueError, match="ROOM_GRADER_DEEPINFRA_API_KEY"):
        _settings(room_coded_rule_enabled=True, room_grader="deepinfra")


def test_boot_accepts_the_key_and_ignores_the_check_when_the_rule_is_off():
    assert _settings(
        room_coded_rule_enabled=True, room_grader="deepinfra",
        room_grader_deepinfra_api_key=KEY,
    ).room_grader == "deepinfra"
    assert _settings(room_coded_rule_enabled=False, room_grader="deepinfra").room_grader == "deepinfra"


# ── the request ─────────────────────────────────────────────────────────────


def test_the_calls_are_pinned_at_temperature_zero_with_a_key_and_a_schema():
    wire = Wire()
    res = make_grader(wire).grade(transcript())
    assert res.error is None
    assert res.grader == "deepinfra" and res.grader_version == grader_version(MODEL)
    assert len(wire.bodies) == 3 + 2 * PHRASING_COUNT
    for req, body in zip(wire.requests, wire.bodies):
        assert req.url.path == "/v1/chat/completions"
        assert req.headers["authorization"] == f"Bearer {KEY}"
        assert body["model"] == MODEL
        assert body["temperature"] == 0
        assert body["logprobs"] is True
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["schema"]["properties"]["answer"]["enum"] == [
            "yes", "no"]
    assert res.extra["served_model"] == MODEL and res.extra["calls"] == len(wire.bodies)


def test_the_grader_is_an_answer_for_every_question_in_set_order():
    res = make_grader(Wire()).grade(transcript())
    assert [a.question for a in res.answers] == [q.id for q in load_question_set().questions]


def test_the_model_is_never_asked_trade_proposed():
    wire = Wire()
    make_grader(wire).grade(transcript())
    asked = {q for q, _ in wire.asked()}
    assert Q.TRADE_PROPOSED not in asked
    assert asked == set(Q) - {Q.TRADE_PROPOSED}


# ── trade_proposed from the structured trade ────────────────────────────────


@pytest.mark.parametrize(
    "trade, expected",
    [
        ({"action": "buy", "size_pct": 2.0}, Answer.YES),
        ({"action": "hold", "size_pct": 0.0}, Answer.NO),
        ({"action": "wait", "size_pct": 0.0}, Answer.NO),
        ({"size_pct": 2.0, "entry": 1.0}, Answer.NOT_COMPUTABLE),
    ],
)
def test_trade_proposed_comes_from_the_structure_even_if_the_model_says_otherwise(trade, expected):
    wire = Wire(default=("yes", 0.99))
    res = make_grader(wire).grade(transcript(trade=trade))
    assert res.error is None
    assert res.get(Q.TRADE_PROPOSED).answer is expected


def test_a_trade_the_model_would_deny_is_still_proposed():
    wire = Wire({Q.TRADE_PROPOSED: ("no", 0.99)}, default=("no", 0.95))
    res = make_grader(wire).grade(transcript(trade={"action": "buy"}))
    assert res.get(Q.TRADE_PROPOSED).answer is Answer.YES


def test_a_trade_with_no_stated_action_leaves_the_room_unavailable_not_guessed():
    wire = Wire({Q.TERMINAL_VULNERABILITY: ("no", 0.95)}, default=("yes", 0.95))
    res = make_grader(wire).grade(transcript(trade={"size_pct": 2.0}))
    assert rule.decide(res, 5).outcome is rule.Outcome.UNAVAILABLE


# ── phrasing averaging ──────────────────────────────────────────────────────


def test_each_fragile_question_is_asked_over_all_five_phrasings_and_the_rest_once():
    wire = Wire()
    make_grader(wire).grade(transcript())
    asked = wire.asked()
    for q in AVERAGED_QUESTIONS:
        assert sorted(p for qq, p in asked if qq == q) == list(range(PHRASING_COUNT))
    for q in set(Q) - set(AVERAGED_QUESTIONS) - {Q.TRADE_PROPOSED}:
        assert [p for qq, p in asked if qq == q] == [None]


def test_the_majority_wins_and_a_split_is_close():
    split = {(Q.THESIS_MATERIAL_DIRECTIONAL, i): ("yes" if i < 3 else "no", 0.95) for i in range(5)}
    res = make_grader(Wire(split)).grade(transcript())
    a = res.get(Q.THESIS_MATERIAL_DIRECTIONAL)
    assert a.answer is Answer.YES and a.close is True
    assert "3/5" in a.rationale and "split" in a.rationale


def test_a_minority_for_yes_gives_no_and_close():
    split = {(Q.BEAR_OBJECTION_ANSWERED, i): ("yes" if i < 2 else "no", 0.95) for i in range(5)}
    a = make_grader(Wire(split)).grade(transcript()).get(Q.BEAR_OBJECTION_ANSWERED)
    assert a.answer is Answer.NO and a.close is True


def test_a_unanimous_sharp_answer_is_not_close():
    wire = Wire({Q.BEAR_OBJECTION_ANSWERED: ("yes", 0.97)}, default=("no", 0.97))
    a = make_grader(wire).grade(transcript()).get(Q.BEAR_OBJECTION_ANSWERED)
    assert a.answer is Answer.YES and a.close is False
    assert a.confidence == pytest.approx(0.97)


def test_a_split_on_a_deciding_question_makes_the_rule_contested():
    answers = {
        Q.BEAR_OBJECTION_ANSWERED: ("yes", 0.97), Q.CATALYST_IN_HORIZON: ("yes", 0.97),
        Q.TERMINAL_VULNERABILITY: ("no", 0.97), Q.EVENT_RISK_WAIT: ("no", 0.97),
    }
    answers.update({(Q.THESIS_MATERIAL_DIRECTIONAL, i): ("yes" if i < 3 else "no", 0.97)
                    for i in range(5)})
    res = make_grader(Wire(answers)).grade(transcript())
    d = rule.decide(res, 3)
    assert d.outcome is rule.Outcome.CONTESTED
    assert d.close_questions == (Q.THESIS_MATERIAL_DIRECTIONAL,)


def test_a_split_that_cannot_change_the_decision_does_not_contest_it():
    split = {(Q.THESIS_MATERIAL_DIRECTIONAL, i): ("yes" if i < 3 else "no", 0.97) for i in range(5)}
    res = make_grader(Wire(split, default=("no", 0.97))).grade(transcript())
    assert rule.decide(res, 5).outcome is rule.Outcome.APPROVE


def test_average_votes_edges():
    def v(ans, c):
        return QuestionAnswer(Q.BEAR_OBJECTION_ANSWERED, ans, confidence=c)

    unparsed = QuestionAnswer(Q.BEAR_OBJECTION_ANSWERED, Answer.NOT_COMPUTABLE)
    assert average_votes(Q.BEAR_OBJECTION_ANSWERED, []).answer is Answer.NOT_COMPUTABLE
    assert average_votes(
        Q.BEAR_OBJECTION_ANSWERED, [v(Answer.YES, 0.9)] * 4 + [unparsed],
    ).answer is Answer.NOT_COMPUTABLE
    near = average_votes(Q.BEAR_OBJECTION_ANSWERED, [v(Answer.YES, 0.6)] * 5)
    assert near.answer is Answer.YES and near.close is True
    nop = average_votes(Q.BEAR_OBJECTION_ANSWERED, [v(Answer.NO, None)] * 5)
    assert nop.confidence is None and nop.close is False


# ── failure is visible ──────────────────────────────────────────────────────


def test_an_http_error_fails_the_grade_and_the_rule_is_unavailable():
    res = make_grader(Wire(status=500)).grade(transcript())
    assert res.error and "500" in res.error
    assert res.answers == ()
    assert rule.decide(res, 3).outcome is rule.Outcome.UNAVAILABLE


def test_a_slow_call_times_out_into_an_error_not_a_verdict():
    res = make_grader(Wire(delay=2.0), timeout_s=0.2).grade(transcript())
    assert res.error
    assert rule.decide(res, 3).outcome is rule.Outcome.UNAVAILABLE


def test_one_failing_phrasing_fails_the_whole_grade():
    class OneBad(Wire):
        async def __call__(self, request):
            body = json.loads(request.content)
            if _asked(body) == (Q.THESIS_MATERIAL_DIRECTIONAL, 3):
                return httpx.Response(503, text="busy")
            return await super().__call__(request)

    res = make_grader(OneBad()).grade(transcript())
    assert res.error and rule.decide(res, 3).outcome is rule.Outcome.UNAVAILABLE


# ── the runner, the allow-list and the policy version ───────────────────────


def test_a_runner_with_a_failing_grader_ends_the_room_decision_unavailable(monkeypatch):
    from tests.unit import test_cr267_wp23_coded_rule as w

    monkeypatch.setattr(settings, "room_coded_rule_enabled", True)
    monkeypatch.setattr(settings, "room_grader", "deepinfra")
    monkeypatch.setattr(settings, "pm_self_consistency_samples", 1)
    monkeypatch.setattr(settings, "room_veto_review_enabled", False)
    monkeypatch.setattr(settings, "room_resurrection_review_enabled", False)
    register_grader("deepinfra", lambda: make_grader(Wire(status=500)))
    try:
        ctx, mandate, profile = w._ctx()
        gateway = w.Gateway([w._PM_APPROVE])
        out = w.drain(gateway, ctx, mandate, profile)
    finally:
        from app.services.room_grader_registry import _build_deepinfra
        register_grader("deepinfra", _build_deepinfra)
    w._assert_decision_unavailable(out, gateway)
    assert "500" in out["verdict"].coded_decision.error


def test_a_runner_with_no_key_ends_the_room_decision_unavailable_and_says_why(monkeypatch):
    from tests.unit import test_cr267_wp23_coded_rule as w

    monkeypatch.setattr(settings, "room_coded_rule_enabled", True)
    monkeypatch.setattr(settings, "room_grader", "deepinfra")
    monkeypatch.setattr(settings, "room_grader_deepinfra_api_key", "")
    monkeypatch.setattr(settings, "pm_self_consistency_samples", 1)
    monkeypatch.setattr(settings, "room_veto_review_enabled", False)
    monkeypatch.setattr(settings, "room_resurrection_review_enabled", False)
    logged: list[str] = []
    monkeypatch.setattr(w.room_runner.logger, "error", lambda event, **kw: logged.append(event))
    ctx, mandate, profile = w._ctx()
    gateway = w.Gateway([w._PM_APPROVE])
    out = w.drain(gateway, ctx, mandate, profile)
    w._assert_decision_unavailable(out, gateway)
    assert "room_grader_unconfigured" in logged


def test_grading_never_touches_the_gateway_or_the_desk_allow_list(monkeypatch):
    def boom():
        raise AssertionError("the grader must not go through the LLM gateway")

    monkeypatch.setattr(llm_gateway, "get_llm_gateway", boom)
    monkeypatch.setattr(settings, "llm_provider_allowlist", ["vllm"])
    res = make_grader(Wire()).grade(transcript())
    assert res.error is None
    assert settings.llm_provider_allowlist == ["vllm"]
    from app.core.llm_allowlist import KNOWN_SLOTS
    assert "deepinfra" not in KNOWN_SLOTS and "room_grader_deepinfra" not in KNOWN_SLOTS


def test_the_policy_version_names_the_model_and_the_averaging(monkeypatch):
    monkeypatch.setattr(settings, "room_coded_rule_enabled", True)
    monkeypatch.setattr(settings, "room_grader", "deepinfra")
    monkeypatch.setattr(settings, "room_grader_deepinfra_api_key", KEY)
    monkeypatch.setattr(settings, "room_grader_deepinfra_model", MODEL)
    one = room_bank.coded_rule_identity()["policy"]
    assert one.startswith(f"deepinfra@{MODEL}|t0|avg5:")
    for q in AVERAGED_QUESTIONS:
        assert q.value in one
    assert "trade=structure" in one
    monkeypatch.setattr(settings, "room_grader_deepinfra_model", "deepseek-ai/DeepSeek-V5")
    assert room_bank.coded_rule_identity()["policy"] != one


def test_flag_off_policy_version_ignores_the_grader_settings(monkeypatch):
    monkeypatch.setattr(settings, "room_coded_rule_enabled", False)
    before = room_bank.policy_version()
    monkeypatch.setattr(settings, "room_grader_deepinfra_model", "deepseek-ai/DeepSeek-V5")
    monkeypatch.setattr(settings, "room_grader_deepinfra_api_key", KEY)
    assert room_bank.policy_version() == before
