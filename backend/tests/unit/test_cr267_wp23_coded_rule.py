"""CR267 WP-23 — the coded decision rule and its wiring into the Room runner.

1. The rule: terminal vulnerability and no-trade always Pass; an unanswered bear
   objection Passes at the conservative levels; strictness is monotone in risk
   level over every answer combination; close deciding answers make it Contested
   and name the questions; an error, a missing answer or a not-computable deciding
   answer is Unavailable, never a default verdict.
2. The policy: versioned per-grader R1..R5 JSON, validated loudly; its version
   carries grader, grader version, rule version and question-set version, and
   feeds the Room bank's policy version.
3. The runner (flag on, fake grader): the action is set from the rule after
   narration, so a narration saying the opposite changes nothing; the mandate
   compliance check still runs last; an unavailable grader ends the Room in the
   outage shape with the CIO never asked; the stored verdict carries every answer,
   the close list and the rule/policy version; flag off leaves the Room untouched.
"""

from __future__ import annotations

import asyncio
import itertools
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.config import settings
from app.schemas import AgentId
from app.schemas.agents import AgentMessage
from app.schemas.room import RoomRun, Verdict
from app.services import room_bank, room_runner
from app.services import room_decision_rule as rule
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_grader_contract import (
    QUESTION_SET_VERSION,
    Answer,
    GraderResult,
    QuestionAnswer,
    QuestionId,
    RoomTranscript,
)
from app.services.room_grader_registry import register_grader, unregister_grader
from app.services.room_runner import (
    PM_DECISION_UNAVAILABLE_REASON,
    _build_pm_formatter,
    _RoomContext,
    _run_cio_step,
    is_llm_outage_verdict,
    is_outage_shaped_verdict,
    run_is_bankable,
)

Q = QuestionId
YES, NO, NC = Answer.YES, Answer.NO, Answer.NOT_COMPUTABLE

# Every deciding question clears at every level.
CLEAR = {
    Q.BEAR_OBJECTION_ANSWERED: YES,
    Q.CATALYST_IN_HORIZON: YES,
    Q.TERMINAL_VULNERABILITY: NO,
    Q.EVENT_RISK_WAIT: NO,
    Q.THESIS_MATERIAL_DIRECTIONAL: YES,
    Q.TRADE_PROPOSED: YES,
}


def result_for(answers: dict, *, close=(), error=None, name="fake", version="1",
               qs=QUESTION_SET_VERSION, confidence=None) -> GraderResult:
    return GraderResult(
        grader=name,
        grader_version=version,
        question_set_version=qs,
        answers=tuple(
            QuestionAnswer(
                question=q, answer=a, close=q in close,
                confidence=confidence, rationale=f"why {q.value}",
            )
            for q, a in answers.items()
        ),
        latency_ms=12,
        error=error,
        cost_usd=0.01,
    )


def decide(answers, risk, **kw):
    close = kw.pop("close", ())
    return rule.decide(result_for(answers, close=close, **kw), risk)


def with_(**changes):
    return {**CLEAR, **{Q(k): v for k, v in changes.items()}}


# ── the rule ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("risk", [1, 2, 3, 4, 5])
def test_all_clear_approves_at_every_level(risk):
    d = decide(CLEAR, risk)
    assert d.outcome == rule.Outcome.APPROVE
    assert d.rule_version == rule.RULE_VERSION


@pytest.mark.parametrize("risk", [1, 2, 3, 4, 5])
def test_terminal_vulnerability_passes_at_every_level(risk):
    d = decide(with_(terminal_vulnerability=YES), risk)
    assert d.outcome == rule.Outcome.PASS
    assert any("terminal vulnerability" in r for r in d.reasons)


@pytest.mark.parametrize("risk", [1, 2, 3, 4, 5])
def test_no_trade_proposed_passes_at_every_level(risk):
    assert decide(with_(trade_proposed=NO), risk).outcome == rule.Outcome.PASS


def test_unanswered_bear_objection_passes_at_the_conservative_levels_only():
    answers = with_(bear_objection_answered=NO)
    assert {r: decide(answers, r).outcome for r in (1, 2, 3, 4, 5)} == {
        1: rule.Outcome.PASS, 2: rule.Outcome.PASS,
        3: rule.Outcome.APPROVE, 4: rule.Outcome.APPROVE, 5: rule.Outcome.APPROVE,
    }


def test_risk_score_outside_the_range_clamps_to_a_real_level():
    assert decide(CLEAR, 0).risk_level == "R1"
    assert decide(CLEAR, 9).risk_level == "R5"


_RANK = {rule.Outcome.PASS: 0, rule.Outcome.CONTESTED: 1, rule.Outcome.APPROVE: 2}


def test_strictness_is_monotone_in_risk_level_over_every_answer_combination():
    qs = list(Q)
    checked = 0
    for combo in itertools.product((YES, NO, NC), repeat=len(qs)):
        answers = dict(zip(qs, combo, strict=True))
        for close_mask in itertools.product((False, True), repeat=len(qs)):
            close = {q for q, c in zip(qs, close_mask, strict=True) if c}
            outcomes = [decide(answers, r, close=close).outcome for r in (1, 2, 3, 4, 5)]
            for stricter, lenient in zip(outcomes, outcomes[1:], strict=False):
                if stricter in _RANK and lenient in _RANK:
                    assert _RANK[stricter] <= _RANK[lenient], (answers, close, outcomes)
                    checked += 1
    assert checked > 100_000


def test_a_conservative_level_never_approves_what_a_lenient_one_passes():
    for combo in itertools.product((YES, NO), repeat=len(Q)):
        answers = dict(zip(list(Q), combo, strict=True))
        outcomes = [decide(answers, r).outcome for r in (1, 2, 3, 4, 5)]
        for stricter, lenient in zip(outcomes, outcomes[1:], strict=False):
            if stricter == rule.Outcome.APPROVE:
                assert lenient == rule.Outcome.APPROVE


# ── the Contested band ──────────────────────────────────────────────────────


def test_a_close_deciding_answer_is_contested_and_named():
    d = decide(with_(bear_objection_answered=NO), 1, close={Q.BEAR_OBJECTION_ANSWERED})
    assert d.outcome == rule.Outcome.CONTESTED
    assert d.close_questions == (Q.BEAR_OBJECTION_ANSWERED,)
    assert any("too close to call" in r for r in d.reasons)


def test_a_close_terminal_vulnerability_is_contested_not_a_confident_pass():
    d = decide(with_(terminal_vulnerability=YES), 3, close={Q.TERMINAL_VULNERABILITY})
    assert d.outcome == rule.Outcome.CONTESTED
    assert d.close_questions == (Q.TERMINAL_VULNERABILITY,)


def test_a_close_answer_that_cannot_change_the_decision_is_not_contested():
    d = decide(with_(terminal_vulnerability=YES, event_risk_wait=NO), 3, close={Q.EVENT_RISK_WAIT})
    assert d.outcome == rule.Outcome.PASS
    d = decide(CLEAR, 5, close={Q.CATALYST_IN_HORIZON})
    assert d.outcome == rule.Outcome.APPROVE


def test_only_the_questions_that_flip_the_decision_are_listed():
    answers = with_(bear_objection_answered=NO, catalyst_in_horizon=NO)
    d = decide(answers, 1, close={Q.BEAR_OBJECTION_ANSWERED, Q.CATALYST_IN_HORIZON, Q.EVENT_RISK_WAIT})
    assert d.outcome == rule.Outcome.PASS
    answers = with_(bear_objection_answered=NO)
    d = decide(answers, 1, close={Q.BEAR_OBJECTION_ANSWERED, Q.EVENT_RISK_WAIT})
    assert d.close_questions == (Q.BEAR_OBJECTION_ANSWERED,)


def test_the_confidence_cutoff_is_a_policy_placeholder_that_defaults_off():
    assert rule.DEFAULT_POLICY.close_below_confidence == 0.0
    r = result_for(with_(bear_objection_answered=NO), confidence=0.4)
    assert rule.decide(r, 1).outcome == rule.Outcome.PASS
    policy = rule.parse_policy_json(_policy_json(close_below_confidence=0.6))["fake"]
    assert rule.decide(r, 1, policy).outcome == rule.Outcome.CONTESTED


# ── Unavailable, never a default verdict ────────────────────────────────────


def test_a_grader_error_is_unavailable():
    d = decide(CLEAR, 3, error="jev 503")
    assert d.outcome == rule.Outcome.UNAVAILABLE
    assert "jev 503" in d.reasons[0]


def test_a_not_computable_deciding_answer_is_unavailable():
    assert decide(with_(thesis_material_directional=NC), 3).outcome == rule.Outcome.UNAVAILABLE
    assert decide(with_(trade_proposed=NC), 5).outcome == rule.Outcome.UNAVAILABLE


def test_a_not_computable_answer_that_does_not_decide_at_this_level_is_ignored():
    assert decide(with_(catalyst_in_horizon=NC), 5).outcome == rule.Outcome.APPROVE
    assert decide(with_(catalyst_in_horizon=NC), 1).outcome == rule.Outcome.UNAVAILABLE


def test_a_missing_deciding_answer_is_unavailable():
    answers = {q: a for q, a in CLEAR.items() if q != Q.TRADE_PROPOSED}
    assert decide(answers, 3).outcome == rule.Outcome.UNAVAILABLE


def test_a_definite_pass_trigger_stands_even_with_another_answer_not_computable():
    assert decide(with_(terminal_vulnerability=YES, catalyst_in_horizon=NC), 1).outcome == rule.Outcome.PASS


def test_an_answer_set_from_another_question_set_is_unavailable():
    d = decide(CLEAR, 3, qs="q0")
    assert d.outcome == rule.Outcome.UNAVAILABLE
    assert "q0" in d.reasons[0]


# ── the versioned policy ────────────────────────────────────────────────────


def _level(req, block=()):
    return {"required_yes": list(req), "blocking_yes": list(block)}


def _policy_json(close_below_confidence=0.0, **overrides):
    levels = {
        "R1": _level(["bear_objection_answered", "thesis_material_directional"], ["event_risk_wait"]),
        "R2": _level(["bear_objection_answered", "thesis_material_directional"]),
        "R3": _level(["thesis_material_directional"]),
        "R4": _level(["thesis_material_directional"]),
        "R5": _level([]),
    }
    levels.update(overrides)
    return json.dumps({"fake": {"close_below_confidence": close_below_confidence, **levels}})


def test_a_well_formed_policy_parses_and_overrides_the_default_ladder():
    policy = rule.policy_for(_policy_json(), "fake")
    assert policy.source == "json"
    # R1 here no longer requires a catalyst, so a missing catalyst approves.
    r = result_for(with_(catalyst_in_horizon=NO))
    assert rule.decide(r, 1, policy).outcome == rule.Outcome.APPROVE
    assert rule.decide(r, 1).outcome == rule.Outcome.PASS


def test_a_grader_without_an_entry_uses_the_star_entry_then_the_default():
    raw = _policy_json().replace('"fake"', '"*"')
    assert rule.policy_for(raw, "anything").source == "json"
    assert rule.policy_for("{}", "anything") is rule.DEFAULT_POLICY


@pytest.mark.parametrize("bad", [
    "not json",
    "[]",
    json.dumps({"g": {"R1": _level([])}}),
    json.dumps({"g": {"close_below_confidence": 2, **{f"R{i}": _level([]) for i in range(1, 6)}}}),
    json.dumps({"g": {f"R{i}": _level(["no_such_question"]) for i in range(1, 6)}}),
    json.dumps({"g": {f"R{i}": {"required_yes": []} for i in range(1, 6)}}),
])
def test_a_malformed_policy_is_rejected_loudly(bad):
    with pytest.raises(rule.PolicyConfigError):
        rule.parse_policy_json(bad)


def test_a_policy_that_is_less_strict_at_a_conservative_level_is_rejected():
    inverted = {f"R{i}": _level([]) for i in range(1, 6)}
    inverted["R5"] = _level(["bear_objection_answered"])
    with pytest.raises(rule.PolicyConfigError, match="monotone"):
        rule.parse_policy_json(json.dumps({"g": inverted}))


def test_the_settings_validator_rejects_a_malformed_policy_at_boot():
    from app.core.config import Settings

    with pytest.raises(ValueError, match="room_coded_rule_policy_json"):
        Settings(room_coded_rule_policy_json="{\"g\": {}}")


def test_policy_version_carries_grader_grader_version_rule_and_question_set():
    d = decide(CLEAR, 3, name="jev", version="v1.2")
    for part in ("jev@v1.2", f"rule={rule.RULE_VERSION}", f"qs={QUESTION_SET_VERSION}"):
        assert part in d.policy_version
    assert decide(CLEAR, 3, name="jev", version="v1.3").policy_version != d.policy_version
    assert decide(CLEAR, 3, name="other", version="v1.2").policy_version != d.policy_version
    ladder = rule.parse_policy_json(_policy_json())["fake"]
    assert (
        rule.policy_version("jev", "v1.2", ladder)
        != rule.policy_version("jev", "v1.2", rule.DEFAULT_POLICY)
    )


# ── the rule feeds the Room bank's policy version ───────────────────────────


class FakeGrader:
    name = "fake"

    def __init__(self, answers=None, *, close=(), error=None, raises=None, version="1"):
        self.version = version
        self._answers, self._close, self._error, self._raises = (
            answers if answers is not None else CLEAR, close, error, raises,
        )
        self.seen: list[RoomTranscript] = []

    def grade(self, transcript):
        self.seen.append(transcript)
        if self._raises:
            raise self._raises
        return result_for(
            self._answers, close=self._close, error=self._error,
            name=self.name, version=self.version,
        )


@pytest.fixture
def coded_on(monkeypatch):
    monkeypatch.setattr(settings, "room_coded_rule_enabled", True)
    monkeypatch.setattr(settings, "room_grader", "fake")
    monkeypatch.setattr(settings, "pm_self_consistency_samples", 1)
    monkeypatch.setattr(settings, "room_veto_review_enabled", False)
    monkeypatch.setattr(settings, "room_resurrection_review_enabled", False)
    yield
    unregister_grader("fake")


def test_a_rule_or_grader_change_rekeys_rooms(coded_on):
    register_grader("fake", lambda: FakeGrader(version="1"))
    v1 = room_bank.policy_version()
    register_grader("fake", lambda: FakeGrader(version="2"))
    assert room_bank.policy_version() != v1


def test_a_policy_json_change_rekeys_rooms(coded_on, monkeypatch):
    register_grader("fake", lambda: FakeGrader())
    before = room_bank.policy_version()
    monkeypatch.setattr(settings, "room_coded_rule_policy_json", _policy_json())
    assert room_bank.policy_version() != before


def test_an_unconfigured_grader_still_keys_the_room(coded_on, monkeypatch):
    monkeypatch.setattr(settings, "room_grader", "")
    assert room_bank.policy_version() is not None


# ── the runner ──────────────────────────────────────────────────────────────

_PM_APPROVE = json.dumps({
    "action": "APPROVE", "size_pct": 2.0, "entry": 150.0, "stop": 141.0,
    "target": 172.0, "horizon_days": 90, "narration": "CIO: take it.",
})
_PM_PASS = json.dumps({"action": "PASS", "narration": "CIO: wait."})


class Gateway:
    def __init__(self, replies):
        self._replies = list(replies)
        self.calls: list[dict] = []

    def has_real_provider(self):
        return True

    def status(self):
        return {"active_provider": "mock"}

    async def stream_chat(self, *, system_prompt, messages, model_tier, locale="en",
                          max_tokens=1024, meta=None, **audit):
        self.calls.append({
            "agent": audit.get("audit_agent_id"),
            "system_prompt": system_prompt,
            "user": messages[0].content,
        })
        if self._replies:
            yield self._replies.pop(0)

    def pm_calls(self):
        return [c for c in self.calls if c["agent"] == AgentId.PORTFOLIO_MANAGER.value]


def _ctx(risk_score=3, drawdown=0.0):
    mandate = hydrate_coach_mandate({
        "plan": "trader", "risk_score": risk_score, "single_name_cap_pct": 3.0,
    })
    profile = {"field_state": {}}
    ctx = _RoomContext(
        ticker="AAPL", mandate=mandate, portfolio_value=100_000.0,
        current_drawdown_pct=drawdown, halal_universe=set(),
        classification_universe=None, locale_allowed_universe=None,
        user_id=uuid4(), sector_holdings=[], sector_marks={},
        risk_last_loss_closed_at=None, risk_trade_open_timestamps=[],
        risk_existing_open_risk_pct=0.0, profile=profile,
    )
    return ctx, mandate, profile


def drain(gateway, ctx, mandate, profile):
    run_id = uuid4()
    run = RoomRun(
        id=run_id, user_id=uuid4(), ticker=ctx.ticker,
        triggered_at=datetime.now(UTC), mandate_version=1, model_tier="mid",
        credit_cost=1,
        transcript=[AgentMessage(
            agent_id=AgentId.BULL_RESEARCHER, role="agent", content="bull case",
            timestamp=datetime.now(UTC),
        )],
    )
    out: dict = {"verdict": None, "pm_text": "", "run": run}

    async def go():
        async for ev in _run_cio_step(
            run_id=run_id, ctx=ctx, profile=profile,
            formatter=_build_pm_formatter(ctx, profile, mandate),
            run=run, mandate=mandate, gateway=gateway, live=True,
            char_delay_min=0.0, char_delay_max=0.0, agent_timeout_s=30.0,
        ):
            if ev.kind == "agent_token" and ev.agent_id == AgentId.PORTFOLIO_MANAGER:
                out["pm_text"] += ev.text or ""
            if ev.kind == "verdict":
                out["verdict"] = ev.verdict

    asyncio.run(go())
    return out


def convene(replies, *, grader, risk=3, drawdown=0.0):
    register_grader("fake", lambda: grader)
    ctx, mandate, profile = _ctx(risk, drawdown)
    gateway = Gateway(replies)
    return drain(gateway, ctx, mandate, profile), gateway


def test_the_grader_reads_the_finished_debate_and_the_desks_proposal(coded_on):
    grader = FakeGrader()
    convene([_PM_APPROVE], grader=grader)
    t = grader.seen[0]
    assert t.ticker == "AAPL" and t.risk_score == 3
    assert t.turns == [{"agent_id": "bull_researcher", "content": "bull case"}]
    assert set(t.proposed_trade) == {"size_pct", "entry", "stop", "target"}


def test_an_approve_decision_ships_with_the_cios_narration_and_levels(coded_on):
    out, gateway = convene([_PM_APPROVE], grader=FakeGrader())
    v = out["verdict"]
    assert v.action == "APPROVE"
    assert v.size_pct == 2.0 and v.entry == 150.0
    assert "CIO: take it." in v.reason
    assert v.coded_decision.outcome == "APPROVE"
    note = gateway.pm_calls()[0]["user"]
    assert "already computed this Room's decision: APPROVE" in note


def test_narration_saying_pass_cannot_stop_a_computed_approve(coded_on):
    out, _ = convene([_PM_PASS], grader=FakeGrader())
    v = out["verdict"]
    assert v.action == "APPROVE"
    assert v.size_pct is not None and v.entry is not None
    assert "CIO: wait." not in v.reason and "CIO: wait." not in out["pm_text"]
    assert v.coded_decision.narration_overridden is True
    assert v.level_provenance["stop"] == "trader"
    assert v.level_provenance["target"] == "trader"


def test_narration_saying_approve_cannot_overturn_a_computed_pass(coded_on):
    answers = with_(terminal_vulnerability=YES)
    out, _ = convene([_PM_APPROVE], grader=FakeGrader(answers))
    v = out["verdict"]
    assert v.action == "PASS"
    assert v.size_pct is None and v.entry is None
    assert "CIO: take it." not in v.reason and "CIO: take it." not in out["pm_text"]
    assert v.coded_decision.outcome == "PASS"
    assert v.coded_decision.narration_overridden is True


def test_an_unparseable_narration_cannot_change_the_action(coded_on):
    out, _ = convene(["I think we should definitely buy!!"], grader=FakeGrader(with_(trade_proposed=NO)))
    assert out["verdict"].action == "PASS"
    out, _ = convene(["{{ nonsense"], grader=FakeGrader())
    assert out["verdict"].action == "APPROVE"


def test_a_missing_narration_still_delivers_the_computed_decision(coded_on):
    out, _ = convene([], grader=FakeGrader(with_(terminal_vulnerability=YES)))
    v = out["verdict"]
    assert v.action == "PASS"
    assert "decision rule passes" in v.reason
    assert not is_outage_shaped_verdict(v.model_dump())


def test_a_contested_decision_is_a_no_trade_that_names_the_close_questions(coded_on):
    grader = FakeGrader(
        with_(bear_objection_answered=NO), close={Q.BEAR_OBJECTION_ANSWERED},
    )
    out, gateway = convene([_PM_PASS], grader=grader, risk=1)
    v = out["verdict"]
    assert v.action == "PASS"
    assert "contested" in v.reason
    assert v.coded_decision.outcome == "CONTESTED"
    assert v.coded_decision.close_questions == ["bear_objection_answered"]
    assert "contested" in gateway.pm_calls()[0]["user"]


def test_the_mandate_compliance_check_still_runs_last_over_a_computed_approve(coded_on):
    out, _ = convene([_PM_APPROVE], grader=FakeGrader(), drawdown=35.0)
    v = out["verdict"]
    assert v.action == "REJECT"
    assert v.violations
    assert "safety floor" in v.reason
    assert v.coded_decision.outcome == "APPROVE"


def test_the_stored_verdict_holds_every_answer_the_close_list_and_the_versions(coded_on):
    grader = FakeGrader(
        with_(bear_objection_answered=NO), close={Q.BEAR_OBJECTION_ANSWERED},
    )
    out, _ = convene([_PM_PASS], grader=grader, risk=1)
    stored = json.loads(out["verdict"].model_dump_json())["coded_decision"]
    assert {a["question"] for a in stored["answers"]} == {q.value for q in Q}
    assert all(a["rationale"].startswith("why ") for a in stored["answers"])
    assert stored["close_questions"] == ["bear_objection_answered"]
    assert stored["rule_version"] == rule.RULE_VERSION
    assert stored["grader"] == "fake" and stored["grader_version"] == "1"
    assert stored["question_set_version"] == QUESTION_SET_VERSION
    for part in ("fake@1", f"rule={rule.RULE_VERSION}", f"qs={QUESTION_SET_VERSION}"):
        assert part in stored["policy_version"]
    assert Verdict.model_validate(stored and json.loads(out["verdict"].model_dump_json())).coded_decision.answers


# ── Unavailable in the runner ───────────────────────────────────────────────


def _assert_decision_unavailable(out, gateway):
    v = out["verdict"]
    assert v.action == "PASS"
    assert v.reason == PM_DECISION_UNAVAILABLE_REASON
    assert v.coded_decision.outcome == "UNAVAILABLE"
    assert gateway.pm_calls() == []
    dumped = v.model_dump()
    assert is_llm_outage_verdict(dumped) and is_outage_shaped_verdict(dumped)
    run = out["run"].model_copy(update={"verdict": v, "status": "completed"})
    assert run_is_bankable(run) is False


def test_a_grader_error_ends_the_room_decision_unavailable(coded_on):
    out, gateway = convene([_PM_APPROVE], grader=FakeGrader(error="jev 503"))
    _assert_decision_unavailable(out, gateway)
    assert out["verdict"].coded_decision.error == "jev 503"


def test_a_grader_that_raises_ends_the_room_decision_unavailable(coded_on):
    out, gateway = convene([_PM_APPROVE], grader=FakeGrader(raises=RuntimeError("boom")))
    _assert_decision_unavailable(out, gateway)
    assert "boom" in out["verdict"].coded_decision.error


def test_a_not_computable_deciding_answer_ends_the_room_decision_unavailable(coded_on):
    out, gateway = convene([_PM_APPROVE], grader=FakeGrader(with_(trade_proposed=NC)))
    _assert_decision_unavailable(out, gateway)


@pytest.mark.parametrize("name", ["", "nonesuch"])
def test_flag_on_with_no_or_unknown_grader_is_unavailable_and_logged_loudly(
    coded_on, monkeypatch, name,
):
    unregister_grader("fake")
    monkeypatch.setattr(settings, "room_grader", name)
    logged: list[str] = []
    monkeypatch.setattr(
        room_runner.logger, "error", lambda event, **kw: logged.append(event),
    )
    ctx, mandate, profile = _ctx()
    gateway = Gateway([_PM_APPROVE])
    out = drain(gateway, ctx, mandate, profile)
    _assert_decision_unavailable(out, gateway)
    assert "room_grader_unconfigured" in logged
    assert "room_decision_unavailable" in logged


# ── flag off: unchanged ─────────────────────────────────────────────────────


def test_flag_off_never_touches_the_grader_and_leaves_the_cios_verdict_its_own(monkeypatch):
    monkeypatch.setattr(settings, "room_coded_rule_enabled", False)
    monkeypatch.setattr(settings, "room_grader", "fake")
    monkeypatch.setattr(settings, "pm_self_consistency_samples", 1)
    monkeypatch.setattr(settings, "room_veto_review_enabled", False)
    monkeypatch.setattr(settings, "room_resurrection_review_enabled", False)
    grader = FakeGrader(with_(terminal_vulnerability=YES))
    try:
        out, gateway = convene([_PM_APPROVE], grader=grader)
    finally:
        unregister_grader("fake")
    v = out["verdict"]
    assert grader.seen == []
    assert v.action == "APPROVE" and v.size_pct == 2.0
    assert v.coded_decision is None
    assert "decision rule" not in gateway.pm_calls()[0]["user"]
    assert "CIO: take it." in v.reason


def test_flag_off_policy_version_ignores_the_rule_identity(monkeypatch):
    monkeypatch.setattr(settings, "room_coded_rule_enabled", False)
    before = room_bank.policy_version()
    register_grader("fake", lambda: FakeGrader(version="9"))
    try:
        assert room_bank.policy_version() == before
    finally:
        unregister_grader("fake")
