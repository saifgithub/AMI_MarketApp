"""DEF528 — the coded rule hands graders the shapes they document.

`room_runner._coded_transcript` once built `cards` as `{desk: {...}}` and a
`proposed_trade` with no action, so `CodeCardsGrader` errored on every cards-on
Room and could never compute `trade_proposed`. These tests run the runner's own
output through the real code grader and the hosted grader's renderer, with
fixtures only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.schemas import AgentId
from app.schemas.agents import AgentMessage
from app.schemas.room import RoomRun
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_grader_contract import (
    Answer,
    QuestionId,
    build_cards_payload,
    build_proposed_trade,
)
from app.services.room_graders import CodeCardsGrader
from app.services.room_graders.questions import render_transcript
from app.services.room_runner import (
    _ClaimCard,
    _ClaimCards,
    _coded_transcript,
    _Objection,
    _RoomContext,
)

ITEMS = ("eq", "vc", "vh", "bs", "moat")
DESKS = (
    AgentId.FUNDAMENTALS_ANALYST,
    AgentId.BULL_RESEARCHER,
    AgentId.BEAR_RESEARCHER,
    AgentId.RESEARCH_MANAGER,
)
LIVE = {f: "live" for f in ("free_cash_flow", "roic", "pe", "total_debt", "gross_margin")}


def _channel(desk: AgentId) -> _ClaimCards:
    cards = tuple(
        _ClaimCard(
            item=i,
            direction="oppose" if i == "bs" else "support",
            grade="well", data="yes", claim=f"{i} claim", nums="1.2B",
        )
        for i in ITEMS
    )
    objections = ()
    if desk is AgentId.BEAR_RESEARCHER:
        objections = (_Objection(target="bs", severity="high", objection="debt wall 2027"),)
    return _ClaimCards(cards=cards, objections=objections)


def _ctx(*, cards_on: bool, scripted=()) -> _RoomContext:
    mandate = hydrate_coach_mandate(
        {"plan": "trader", "risk_score": 3, "single_name_cap_pct": 3.0}
    )
    ctx = _RoomContext(
        ticker="AAPL", mandate=mandate, portfolio_value=100_000.0,
        current_drawdown_pct=0.0, halal_universe=set(),
        classification_universe=None, locale_allowed_universe=None,
        user_id=uuid4(), sector_holdings=[], sector_marks={},
        risk_last_loss_closed_at=None, risk_trade_open_timestamps=[],
        risk_existing_open_risk_pct=0.0, profile={"field_state": dict(LIVE)},
    )
    ctx.trader_entry, ctx.trader_stop, ctx.trader_target, ctx.trader_size_pct = (
        200.0, 188.0, 226.0, 3.0,
    )
    ctx.scripted_turns = list(scripted)
    if cards_on:
        ctx.claim_cards = {d: _channel(d) for d in DESKS}
    return ctx


def _run(trader_text: str = "Side: BUY\nSize: 3.00% of portfolio\nEntry: $200.00") -> RoomRun:
    now = datetime.now(UTC)
    turns = [
        (AgentId.BEAR_RESEARCHER, "Debt wall in 2027."),
        (AgentId.RESEARCH_MANAGER, "Coverage is 9.4x."),
        (AgentId.TRADER, trader_text),
    ]
    return RoomRun(
        id=uuid4(), user_id=uuid4(), ticker="AAPL", triggered_at=now,
        mandate_version=1, model_tier="mid", credit_cost=1,
        transcript=[
            AgentMessage(agent_id=a, role="agent", content=c, timestamp=now)
            for a, c in turns
        ],
    )


def test_cards_on_room_is_graded_by_the_code_grader():
    ctx, run = _ctx(cards_on=True), _run()
    tr = _coded_transcript(uuid4(), ctx, run)

    assert set(tr.cards) == {"cards_by_desk", "field_state"}
    assert set(tr.cards["cards_by_desk"]) == {d.value for d in DESKS}
    bear = tr.cards["cards_by_desk"]["bear_researcher"]
    assert len(bear["cards"]) == 5 and bear["objections"][0]["target"] == "bs"
    assert tr.cards["field_state"] == LIVE
    assert tr.proposed_trade == {
        "action": "buy", "size_pct": 3.0, "entry": 200.0, "stop": 188.0, "target": 226.0,
    }

    res = CodeCardsGrader().grade(tr)
    assert res.error is None
    by_q = {a.question: a for a in res.answers}
    assert by_q[QuestionId.TERMINAL_VULNERABILITY].answer is Answer.YES
    assert by_q[QuestionId.THESIS_MATERIAL_DIRECTIONAL].answer is Answer.YES
    assert by_q[QuestionId.TRADE_PROPOSED].answer is Answer.YES


def test_cards_off_room_gives_none_and_code_grader_answers_only_the_trade():
    tr = _coded_transcript(uuid4(), _ctx(cards_on=False), _run())
    assert tr.cards is None
    res = CodeCardsGrader().grade(tr)
    assert res.error is None
    by_q = {a.question: a for a in res.answers}
    assert by_q[QuestionId.TRADE_PROPOSED].answer is Answer.YES
    for q in (
        QuestionId.TERMINAL_VULNERABILITY,
        QuestionId.THESIS_MATERIAL_DIRECTIONAL,
        QuestionId.BEAR_OBJECTION_ANSWERED,
    ):
        assert by_q[q].answer is Answer.NOT_COMPUTABLE


@pytest.mark.parametrize("side", ["HOLD", "WAIT"])
def test_no_position_side_is_no_trade_and_carries_no_levels(side):
    run = _run(f"Side: {side}\nSize: 0.00% of portfolio")
    tr = _coded_transcript(uuid4(), _ctx(cards_on=False), run)
    assert tr.proposed_trade == {"action": side.lower(), "size_pct": 0.0}
    ans = CodeCardsGrader().grade(tr).get(QuestionId.TRADE_PROPOSED)
    assert ans.answer is Answer.NO


def test_scripted_execution_desk_is_a_buy():
    run = _run("Translating the synthesis: BUY AAPL at $200.")
    ctx = _ctx(cards_on=False, scripted=[AgentId.TRADER])
    assert _coded_transcript(uuid4(), ctx, run).proposed_trade["action"] == "buy"


def test_unstated_side_is_not_guessed():
    tr = _coded_transcript(uuid4(), _ctx(cards_on=False), _run("I like it here."))
    assert "action" not in tr.proposed_trade
    ans = CodeCardsGrader().grade(tr).get(QuestionId.TRADE_PROPOSED)
    assert ans.answer is Answer.NOT_COMPUTABLE


def test_hosted_renderer_shows_the_same_desk_turns_and_no_cio_turn():
    run = _run()
    tr = _coded_transcript(uuid4(), _ctx(cards_on=True), run)
    assert [t["agent_id"] for t in tr.turns] == [m.agent_id.value for m in run.transcript]
    text = render_transcript(tr)
    for m in run.transcript:
        assert f"[{m.agent_id.value}]\n{m.content}" in text
    assert "portfolio_manager" not in text
    assert '"action": "buy"' in text


def test_contract_builders_accept_dicts_and_drop_empty_desks():
    cards = build_cards_payload(
        {
            "a": {"cards": [{"item": "eq"}], "objections": [{"target": "bs"}]},
            "b": {"cards": [], "objections": []},
            "c": None,
        },
        None,
    )
    assert cards == {
        "cards_by_desk": {"a": {"cards": [{"item": "eq"}], "objections": [{"target": "bs"}]}},
        "field_state": {},
    }
    assert build_cards_payload({"b": {"cards": []}}, LIVE) is None
    assert build_proposed_trade(action=None, size_pct=2) == {"size_pct": 2}
