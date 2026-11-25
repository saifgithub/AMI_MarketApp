"""CR267 WP-23 — the on-prem Ling Room grader (`ROOM_GRADER=ling`).

No network: the grader's calls reach a real `VLLMProvider(kind="vllm", name="vllm_fallback")`
whose HTTP client is an `httpx.MockTransport`, so the request body the Ling host would see
(thinking switch, temperature, schema, model) and the SSE parsing are the real ones.

1. Registry and factory: "ling" is registered, builds from the `vllm_fallback` slot settings,
   and refuses to build without the slot or with an unpinned model.
2. Version string: names the pinned model, the plan and the thinking switch; the DeepInfra
   version is byte-identical to before the plan was shared.
3. Boot refuses `ROOM_GRADER=ling` with the rule on and no usable `vllm_fallback` slot.
4. The question plan is the same object as DeepInfra's: same questions, phrasings, split rule,
   retry rule; a run of each asks the same (question, phrasing) calls.
5. The wire: pinned to the slot, temperature 0, thinking off even when the slot's own
   `enable_thinking` is on, the response model id recorded.
"""

from __future__ import annotations

import json
import math

import httpx
import pytest

from app.core.config import Settings, settings
from app.services import llm_gateway, room_bank
from app.services import room_decision_rule as rule
from app.services.llm_gateway import VLLMProvider, _apply_call_overrides
from app.services.room_grader_contract import Answer, QuestionId, RoomTranscript
from app.services.room_grader_registry import registered_graders, resolve_grader
from app.services.room_graders import deepinfra, ling, production_plan
from app.services.room_graders.ling_variants import BEAR_V2
from app.services.room_graders.questions import load_question_set

Q = QuestionId
MODEL = "ling-3.0-flash-fin-fp4"
BASE = "http://ling.test:8004"

_TEXT_TO_QUESTION: dict[str, tuple[Q, int | None]] = {}
for _q in load_question_set().questions:
    _TEXT_TO_QUESTION[_q.text] = (_q.id, None)
    for _i, _p in enumerate(_q.phrasings):
        _TEXT_TO_QUESTION[_p] = (_q.id, _i)
for _i, _p in enumerate(BEAR_V2.question.phrasings):
    _TEXT_TO_QUESTION[_p] = (BEAR_V2.question.id, _i)


def _asked(body: dict) -> tuple[Q, int | None]:
    user = body["messages"][-1]["content"]
    line = next(x for x in user.splitlines() if x.startswith("Question: "))
    return _TEXT_TO_QUESTION[line[len("Question: "):]]


def _sse(answer: str, p: float, model: str = MODEL, content: str | None = None) -> httpx.Response:
    lp = [{
        "token": answer, "logprob": math.log(p),
        "top_logprobs": [
            {"token": answer, "logprob": math.log(p)},
            {"token": "no" if answer == "yes" else "yes", "logprob": math.log(1 - p)},
        ],
    }]
    frames = [
        {"model": model, "choices": [{
            "delta": {"content": content if content is not None else json.dumps({"answer": answer})},
            "logprobs": {"content": lp}, "finish_reason": None,
        }]},
        {"model": model, "choices": [{"delta": {}, "finish_reason": "stop"}]},
        {"model": model, "choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 5}},
    ]
    body = "".join(f"data: {json.dumps(f)}\n\n" for f in frames) + "data: [DONE]\n\n"
    return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})


class Wire:
    """A scripted Ling host: `answers[(question, phrasing)]` or `answers[question]`."""

    def __init__(self, answers=None, *, status=200, default=("no", 0.95), content=None, model=MODEL):
        self.answers = answers or {}
        self.status, self.default, self.content, self.model = status, default, content, model
        self.bodies: list[dict] = []

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.bodies.append(body)
        if self.status != 200:
            return httpx.Response(self.status, text="upstream broke")
        qid, phrasing = _asked(body)
        answer, p = self.answers.get((qid, phrasing), self.answers.get(qid, self.default))
        return _sse(answer, p, model=self.model, content=self.content)

    def asked(self) -> list[tuple[Q, int | None]]:
        return [_asked(b) for b in self.bodies]


class SlotGateway:
    """The gateway's `stream_chat` over one real `vllm_fallback` provider: records the slot
    the grader pinned and applies the grounding directive as the gateway does."""

    def __init__(self, wire: Wire, *, slot_thinking: bool = True) -> None:
        self.pinned: list[str | None] = []
        provider = VLLMProvider(
            base_url=BASE, model_name=MODEL, kind="vllm", name="vllm_fallback",
            enable_thinking=slot_thinking, timeout_seconds=5.0,
        )
        provider._client = httpx.AsyncClient(
            base_url=BASE, transport=httpx.MockTransport(wire), timeout=5.0,
        )
        self.provider = provider

    async def stream_chat(self, *, provider_name=None, system_prompt, messages, **kw):
        self.pinned.append(provider_name)
        assert provider_name == "vllm_fallback"
        async for chunk in self.provider.stream_chat(
            system_prompt=llm_gateway.prepend_grounding_directive(system_prompt),
            messages=messages,
            model_tier=kw.get("model_tier", "cheap"),
            max_tokens=kw.get("max_tokens", 64),
            meta=kw.get("meta"),
            constraint=kw.get("constraint"),
        ):
            yield chunk


def make_grader(wire: Wire, *, timeout_s=5.0, slot_thinking=True) -> ling.LingGrader:
    return ling.LingGrader(
        model=MODEL, timeout_s=timeout_s, gateway=SlotGateway(wire, slot_thinking=slot_thinking),
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


# ── 1. registry and factory ─────────────────────────────────────────────────


def test_ling_is_a_registered_grader_name_beside_deepinfra():
    assert {"ling", "deepinfra"} <= set(registered_graders())


def test_resolve_builds_the_grader_from_the_fallback_slot_settings(monkeypatch):
    monkeypatch.setattr(settings, "vllm_fallback_base_url", BASE)
    monkeypatch.setattr(settings, "vllm_fallback_model", MODEL)
    monkeypatch.setattr(settings, "room_grader_ling_timeout_s", 45.0)
    g = resolve_grader("ling")
    assert isinstance(g, ling.LingGrader)
    assert g.name == "ling" and g.slot == "vllm_fallback"
    assert g.version == ling.grader_version(MODEL)
    assert g._timeout_s == 45.0


def test_resolve_without_the_slot_refuses_to_build(monkeypatch):
    monkeypatch.setattr(settings, "vllm_fallback_base_url", "")
    with pytest.raises(ValueError, match="VLLM_FALLBACK_BASE_URL"):
        resolve_grader("ling")


@pytest.mark.parametrize("model", ["", "  ", "ling-latest", "latest"])
def test_an_unpinned_model_is_refused(model):
    with pytest.raises(ValueError, match="pinned"):
        ling.LingGrader(model=model)


def test_resolve_does_not_change_the_default_grader():
    assert Settings(_env_file=None).room_grader == ""


# ── 2. version string ───────────────────────────────────────────────────────


def test_the_version_names_the_model_the_plan_and_the_thinking_switch():
    v = ling.grader_version(MODEL)
    assert v == (
        "ling:ling-3.0-flash-fin-fp4|t0|avg5:bear_objection_answered+thesis_material_directional"
        "|split2|trade=structure|think=off|bear=v2"
    )
    assert ling.grader_version("other-model") != v


def test_the_deepinfra_version_is_unchanged_by_sharing_the_plan():
    assert deepinfra.grader_version("m") == (
        "m|t0|avg5:bear_objection_answered+thesis_material_directional|split2|trade=structure"
    )


def test_the_policy_version_rekeys_when_the_slot_model_changes(monkeypatch):
    monkeypatch.setattr(settings, "room_coded_rule_enabled", True)
    monkeypatch.setattr(settings, "room_grader", "ling")
    monkeypatch.setattr(settings, "vllm_fallback_base_url", BASE)
    monkeypatch.setattr(settings, "vllm_fallback_model", MODEL)
    one = room_bank.coded_rule_identity()["policy"]
    assert one.startswith(f"ling@ling:{MODEL}|t0|avg5:")
    assert "|split2|" in one and "think=off" in one
    monkeypatch.setattr(settings, "vllm_fallback_model", "ling-3.1-flash-fin-fp4")
    assert room_bank.coded_rule_identity()["policy"] != one


# ── 3. config refusal ───────────────────────────────────────────────────────


def _settings(**kw):
    return Settings(_env_file=None, **kw)


_SLOT = dict(vllm_fallback_base_url=BASE, vllm_fallback_model=MODEL, vllm_fallback_kind="vllm")


def test_boot_refuses_rule_on_with_ling_and_no_slot():
    with pytest.raises(ValueError, match="VLLM_FALLBACK_BASE_URL"):
        _settings(room_coded_rule_enabled=True, room_grader="ling")


def test_boot_refuses_a_slot_that_is_not_a_vllm_kind():
    with pytest.raises(ValueError, match="VLLM_FALLBACK_KIND"):
        _settings(
            room_coded_rule_enabled=True, room_grader="ling",
            **{**_SLOT, "vllm_fallback_kind": "openai"},
        )


def test_boot_refuses_a_slot_the_allow_list_blocks():
    with pytest.raises(ValueError, match="LLM_PROVIDER_ALLOWLIST"):
        _settings(
            room_coded_rule_enabled=True, room_grader="ling",
            llm_provider_allowlist=["vllm"], **_SLOT,
        )


def test_boot_refuses_a_latest_model_alias():
    with pytest.raises(ValueError, match="pinned"):
        _settings(
            room_coded_rule_enabled=True, room_grader="ling",
            **{**_SLOT, "vllm_fallback_model": "ling-latest"},
        )


def test_boot_accepts_a_complete_slot_and_ignores_the_check_when_the_rule_is_off():
    assert _settings(
        room_coded_rule_enabled=True, room_grader="ling",
        llm_provider_allowlist=["vllm", "vllm_fallback"], **_SLOT,
    ).room_grader == "ling"
    assert _settings(room_coded_rule_enabled=False, room_grader="ling").room_grader == "ling"
    assert _settings(room_coded_rule_enabled=True, room_grader="deepinfra",
                     room_grader_deepinfra_api_key="k").room_grader == "deepinfra"


# ── 4. the plan is DeepInfra's plan ─────────────────────────────────────────


def test_both_graders_run_the_one_shared_plan():
    assert issubclass(ling.LingGrader, production_plan.ProductionPlanGrader)
    assert issubclass(deepinfra.DeepInfraGrader, production_plan.ProductionPlanGrader)
    assert ling.LingGrader._grade_all is deepinfra.DeepInfraGrader._grade_all
    assert deepinfra.average_votes is production_plan.average_votes
    assert deepinfra.AVERAGED_QUESTIONS is production_plan.AVERAGED_QUESTIONS
    assert deepinfra.SPLIT_CLOSE_MIN_MINORITY == production_plan.SPLIT_CLOSE_MIN_MINORITY == 2
    assert deepinfra.PHRASING_COUNT == production_plan.PHRASING_COUNT == 5
    assert deepinfra.OVERLOAD_RETRIES == production_plan.OVERLOAD_RETRIES


def test_a_ling_run_asks_exactly_the_calls_a_deepinfra_run_asks():
    from tests.unit import test_cr267_wp23_deepinfra_grader as di_test

    ling_wire = Wire()
    assert make_grader(ling_wire).grade(transcript()).error is None
    di_wire = di_test.Wire()
    assert di_test.make_grader(di_wire).grade(di_test.transcript()).error is None
    assert sorted(ling_wire.asked(), key=str) == sorted(di_wire.asked(), key=str)
    assert len(ling_wire.asked()) == 13


def test_the_fragile_questions_get_five_phrasings_and_trade_proposed_is_never_asked():
    wire = Wire()
    res = make_grader(wire).grade(transcript())
    asked = wire.asked()
    assert Q.TRADE_PROPOSED not in {q for q, _ in asked}
    for qid in production_plan.AVERAGED_QUESTIONS:
        assert sorted(p for q, p in asked if q is qid) == [0, 1, 2, 3, 4]
    others = [q for q, _ in asked if q not in production_plan.AVERAGED_QUESTIONS]
    assert len(others) == len(set(others)) == 3
    assert len(res.answers) == len(load_question_set().questions)
    assert res.get(Q.TRADE_PROPOSED).answer is Answer.YES


def test_the_split_rule_is_the_shared_one():
    three_two = {(Q.BEAR_OBJECTION_ANSWERED, i): ("yes" if i < 3 else "no", 0.95) for i in range(5)}
    four_one = {(Q.THESIS_MATERIAL_DIRECTIONAL, i): ("yes" if i < 4 else "no", 0.95) for i in range(5)}
    res = make_grader(Wire({**three_two, **four_one})).grade(transcript())
    bear = res.get(Q.BEAR_OBJECTION_ANSWERED)
    thesis = res.get(Q.THESIS_MATERIAL_DIRECTIONAL)
    assert bear.answer is Answer.YES and bear.close is True and "(split)" in bear.rationale
    assert thesis.answer is Answer.YES and thesis.close is False


def test_an_overload_is_retried_like_deepinfra(monkeypatch):
    monkeypatch.setattr(production_plan, "OVERLOAD_BACKOFF_S", 0.0)

    class BusyOnce(Wire):
        hit = False

        async def __call__(self, request):
            body = json.loads(request.content)
            if _asked(body) == (Q.BEAR_OBJECTION_ANSWERED, 2) and not BusyOnce.hit:
                BusyOnce.hit = True
                self.bodies.append(body)
                return httpx.Response(429, text="Model busy, retry later")
            return await super().__call__(request)

    wire = BusyOnce()
    res = make_grader(wire).grade(transcript())
    assert res.error is None
    assert wire.asked().count((Q.BEAR_OBJECTION_ANSWERED, 2)) == 2


def test_an_http_error_fails_the_grade_and_the_rule_is_unavailable():
    res = make_grader(Wire(status=500)).grade(transcript())
    assert res.error and rule.decide(res, 3).outcome is rule.Outcome.UNAVAILABLE


# ── 5. the wire (network mocked) ────────────────────────────────────────────


def test_every_call_is_pinned_to_the_slot_at_temperature_zero_with_thinking_off():
    wire = Wire()
    gw = SlotGateway(wire, slot_thinking=True)
    g = ling.LingGrader(model=MODEL, timeout_s=5.0, gateway=gw)
    res = g.grade(transcript())
    assert res.error is None
    assert set(gw.pinned) == {"vllm_fallback"} and len(gw.pinned) == 13
    for body in wire.bodies:
        assert body["model"] == MODEL
        assert body["temperature"] == 0
        assert body["chat_template_kwargs"] == {"enable_thinking": False}
        assert body["logprobs"] is True
        assert body["response_format"]["json_schema"]["schema"]["properties"]["answer"]["enum"] == [
            "yes", "no"]
        assert body["max_tokens"] == 64


def test_the_served_model_id_is_recorded_on_the_result():
    res = make_grader(Wire(model="served-ling-id")).grade(transcript())
    assert res.extra["served_model"] == "served-ling-id"
    assert res.extra["slot"] == "vllm_fallback" and res.extra["temperature"] == 0
    assert res.grader == "ling" and res.grader_version == ling.grader_version(MODEL)


def test_a_reply_that_is_not_yes_or_no_leaves_the_question_not_computable_and_is_counted():
    res = make_grader(Wire(content="The bull answered the objection, although briefly.")).grade(transcript())
    assert res.error is None
    assert res.extra["unparsed_questions"] > 0
    assert all(a.answer is Answer.NOT_COMPUTABLE
               for a in res.answers if a.question is not Q.TRADE_PROPOSED)


def test_a_fenced_json_reply_still_parses():
    res = make_grader(Wire(content='```json\n{"answer": "yes"}\n```')).grade(transcript())
    assert res.extra["unparsed_questions"] == 0


def test_the_thinking_override_merges_into_the_slots_own_kwargs_and_nothing_else_changes():
    body = {"chat_template_kwargs": {"enable_thinking": True, "keep": 1}, "temperature": 0.7}
    _apply_call_overrides(body, {"request_overrides": {
        "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}, "model": "evil"}})
    assert body == {"chat_template_kwargs": {"enable_thinking": False, "keep": 1}, "temperature": 0}
    plain = {"temperature": 0.7}
    _apply_call_overrides(plain, {})
    assert plain == {"temperature": 0.7}


def test_a_gateway_with_no_vllm_fallback_slot_fails_the_grade_loudly():
    gw = llm_gateway.LLMGateway.__new__(llm_gateway.LLMGateway)
    gw._providers = {"mock": llm_gateway.MockProvider()}
    gw._blocked = set()
    g = ling.LingGrader(model=MODEL, gateway=gw)
    res = g.grade(transcript())
    assert res.error and "vllm_fallback" in res.error
    assert rule.decide(res, 3).outcome is rule.Outcome.UNAVAILABLE
