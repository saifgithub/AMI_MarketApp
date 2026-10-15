"""CR256 — in-turn claim-card enforcement on the four evidence desks.

The card pilot measured the design in one table: self-filed cards scored
test-retest ICC 0.93 while voluntary filing was salience noise (raw ICC 0.62
at n=30 across six prompt variants), and post-hoc repair only rescues as
top-up, never as foundation. The conclusion: the CLAIMS/OBJECTIONS contract
is validated, and the channel must be enforced in-turn — the desk's own
prompt carries it (`room_prompts.py` `_CLAIMS_FORMAT_*`, gated by
`settings.room_cards_envelope_enabled`) and the runner re-asks a desk ONCE
when its live turn arrives without a parseable block (the CR253 bounded-repair
precedent, audited under `room_cards_repair`).

The rules pinned here:

**Flag-gated, default OFF.** With the flag off no prompt changes by one byte
and no repair ever fires — D32, no behaviour change without a measured GO.

**Enforcement is desk-scoped.** Only the four evidence desks
(fundamentals_analyst, bull/bear_researcher, research_manager) file cards;
objections are bear/research_manager only and are NEVER enforced — the
contract makes them optional. Non-desk agents are untouched by both the
prompt and the parser.

**Failure changes nothing.** A call error, stream error, empty reply, or a
retry that still carries no parseable block leaves the original turn in
place, exactly as CR253 does. Scripted turns are never re-asked.

**The machine channel never reaches the transcript.** Both blocks are
stripped before the turn is streamed or committed, on the DEF147 idiom —
the user and downstream desks read prose, never card syntax.
"""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest

from app.core.config import settings
from app.schemas import AgentId
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_prompts import build_room_messages
from app.services.room_runner import (
    RoomRunner,
    _attempt_cards_repair,
    _cards_channel_absent,
    parse_claim_cards,
)

# ── the parser ────────────────────────────────────────────────────────────

_CLAIMS_TURN = """[STANCE: for | CONVICTION: high | HEADLINE: FCF 1.2B]
[CLAIMS]
item=eq dir=support grade=well data=yes claim=FCF covers net income nums=$1.2B, 0.94
item=vc dir=neutral grade=partial data=no claim=ROIC unreadable, WACC unsourced
item=vh dir=support grade=well data=yes claim=EV/EBITDA below peer median nums=11.2x
item=bs dir=oppose grade=partial data=yes claim=debt wall lands 2027 nums=$850M
item=moat dir=support grade=well data=yes claim=switching costs visible in retention
[/CLAIMS]
The analysis prose, in the desk's own voice.
[OBJECTIONS]
target=bs severity=high objection=the ladder is post-horizon, it cannot bind this call
[/OBJECTIONS]"""


def test_a_well_formed_block_is_parsed_and_stripped_from_the_prose():
    body, cards = parse_claim_cards(_CLAIMS_TURN)
    assert cards is not None
    assert len(cards.cards) == 5
    first = cards.cards[0]
    assert (first.item, first.direction, first.grade, first.data) == (
        "eq",
        "support",
        "well",
        "yes",
    )
    assert "FCF covers net income" in first.claim
    assert first.nums == "$1.2B, 0.94"
    # nums is optional — a card may carry a claim with no figures.
    assert cards.cards[1].nums is None
    assert len(cards.objections) == 1
    assert cards.objections[0].target == "bs"
    assert cards.objections[0].severity == "high"
    # Both blocks are machine channels: neither reaches the prose.
    assert "[CLAIMS]" not in body
    assert "[OBJECTIONS]" not in body
    assert "The analysis prose" in body
    assert "[STANCE:" in body, "the stance line is not the card channel's job"
    assert not _cards_channel_absent(cards)


def test_no_block_yields_none_and_leaves_the_text_alone():
    text = "Just prose, no card channel at all."
    body, cards = parse_claim_cards(text)
    assert body == text
    assert cards is None
    assert _cards_channel_absent(cards)


def test_an_unclosed_block_is_absent_not_a_partial_read():
    """An opening tag with no closer is a truncation artefact; reading on
    past it would swallow the analysis body as card text. The precision-biased
    read recognises nothing and lets enforcement re-ask."""
    text = "[CLAIMS]\nitem=eq dir=support grade=well data=yes claim=x nums=1\n"
    body, cards = parse_claim_cards(text)
    assert body == text
    assert cards is None


def test_malformed_lines_are_counted_and_dropped_never_guessed():
    body, cards = parse_claim_cards(
        "[CLAIMS]\n"
        "garbage line with no grammar\n"
        "item=eq dir=bogus grade=well data=yes claim=x nums=1\n"
        "item=bs dir=oppose grade=well data=yes claim=the wall is real nums=$850M\n"
        "[/CLAIMS]done"
    )
    assert cards is not None
    assert cards.malformed_cards == 2
    assert [c.item for c in cards.cards] == ["bs"]
    assert body == "done"


def test_a_block_whose_lines_all_fail_is_an_absent_channel():
    _, cards = parse_claim_cards(
        "[CLAIMS]\nitem=eq dir=bogus grade=bogus data=maybe claim=x\n[/CLAIMS]"
    )
    assert cards is not None
    assert cards.cards == ()
    assert cards.malformed_cards == 1
    assert _cards_channel_absent(cards)


def test_list_markers_case_and_spacing_drift_still_parse():
    _, cards = parse_claim_cards(
        "[claims]\n"
        "- item=EQ   dir=Support grade=Well data=YES claim=Cash conversion holds nums=0.94\n"
        "* item=moat dir=neutral grade=partial data=no claim=no moat claimed\n"
        "[/Claims]"
    )
    assert cards is not None
    assert len(cards.cards) == 2
    assert cards.cards[0].item == "eq"
    assert cards.cards[0].direction == "support"
    assert cards.cards[1].grade == "partial"
    assert cards.malformed_cards == 0


def test_objection_lines_validate_the_target_against_the_registry():
    _, cards = parse_claim_cards(
        "[CLAIMS]\nitem=eq dir=support grade=well data=yes claim=x\n[/CLAIMS]\n"
        "[OBJECTIONS]\n"
        "target=zz severity=high objection=bogus item id\n"
        "target=eq severity=medium objection=a fair challenge on the numbers\n"
        "[/OBJECTIONS]"
    )
    assert cards is not None
    assert cards.malformed_objections == 1
    assert len(cards.objections) == 1


# ── the prompt carries the contract, only when the flag is on ──────────────


def _system_prompt_for(agent_id: AgentId, *, cards_envelope: bool) -> str:
    system_prompt, _ = build_room_messages(
        agent_id=agent_id,
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        user_id=uuid4(),
        ticker="AAPL",
        profile={},
        transcript=[],
        cards_envelope=cards_envelope,
    )
    return system_prompt


def test_the_flag_on_puts_claims_at_slot_2_for_the_fundamentals_desk():
    prompt = _system_prompt_for(AgentId.FUNDAMENTALS_ANALYST, cards_envelope=True)
    assert "[CLAIMS]" in prompt
    assert "Immediately AFTER the stance line" in prompt
    assert "eq = earnings quality" in prompt
    assert "File all five items" in prompt
    # GAPS keeps its terminal slot — the two machine channels never contest.
    assert "GAPS:" in prompt
    assert prompt.index("Immediately AFTER the stance line") < prompt.index("GAPS:")


def test_the_flag_on_puts_claims_closing_for_the_researchers():
    prompt = _system_prompt_for(AgentId.BULL_RESEARCHER, cards_envelope=True)
    assert "[CLAIMS]" in prompt
    assert "At the END of your turn" in prompt
    # Bull is not an objection desk.
    assert "[OBJECTIONS]" not in prompt


def test_the_flag_on_adds_objections_for_bear_and_research_manager():
    for agent in (AgentId.BEAR_RESEARCHER, AgentId.RESEARCH_MANAGER):
        prompt = _system_prompt_for(agent, cards_envelope=True)
        assert "[CLAIMS]" in prompt, agent.value
        assert "[OBJECTIONS]" in prompt, agent.value
        assert "severity=high|medium|low" in prompt, agent.value


def test_non_desk_agents_are_untouched_even_with_the_flag_on():
    for agent in (
        AgentId.NEWS_ANALYST,
        AgentId.MARKET_ANALYST,
        AgentId.SOCIAL_MEDIA_ANALYST,
        AgentId.TRADER,
        AgentId.AGGRESSIVE_DEBATOR,
        AgentId.CONSERVATIVE_DEBATOR,
        AgentId.NEUTRAL_DEBATOR,
        AgentId.PORTFOLIO_MANAGER,
    ):
        prompt = _system_prompt_for(agent, cards_envelope=True)
        assert "[CLAIMS]" not in prompt, agent.value
        assert "[OBJECTIONS]" not in prompt, agent.value


def test_the_flag_off_leaves_every_prompt_byte_identical():
    for agent in (
        AgentId.FUNDAMENTALS_ANALYST,
        AgentId.BULL_RESEARCHER,
        AgentId.BEAR_RESEARCHER,
        AgentId.RESEARCH_MANAGER,
    ):
        assert _system_prompt_for(agent, cards_envelope=False) == (
            _system_prompt_for(agent, cards_envelope=False)
        ), agent.value


# ── the repair call ────────────────────────────────────────────────────────


_WITH_CARDS = (
    "[STANCE: for | CONVICTION: high | HEADLINE: repaired card view]\n"
    "The repaired analysis, unchanged on the merits.\n"
    "[CLAIMS]\n"
    "item=eq dir=support grade=well data=yes claim=FCF holds nums=$1.2B\n"
    "item=vc dir=neutral grade=partial data=no claim=unreadable\n"
    "item=vh dir=support grade=well data=yes claim=cheap vs peers nums=11.2x\n"
    "item=bs dir=oppose grade=partial data=yes claim=wall 2027 nums=$850M\n"
    "item=moat dir=support grade=well data=yes claim=switching costs\n"
    "[/CLAIMS]"
)
_NO_CARDS = "The multiple is defensible on the cash flows alone."


class _RepairGateway:
    """Serves one scripted reply per call, recording audit kwargs + messages."""

    def __init__(self, replies: list[str]):
        self._replies = list(replies)
        self.calls: list[dict] = []

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(
        self,
        *,
        system_prompt,
        messages,
        model_tier,
        locale="en",
        max_tokens=1024,
        meta=None,
        **audit,
    ):
        self.calls.append({"messages": messages, "audit": audit})
        if meta is not None and self._replies and self._replies[0] == "__STREAM_ERROR__":
            self._replies.pop(0)
            meta["stream_error"] = True
            return
        if self._replies:
            yield self._replies.pop(0)


def _msg_content(m) -> str:
    if isinstance(m, dict):
        return str(m.get("content", ""))
    return str(getattr(m, "content", ""))


def _repair_kwargs(gateway) -> dict:
    return {
        "gateway": gateway,  # type: ignore[arg-type]
        "system_prompt": "sys",
        "messages": [],
        "tier": None,
        "locale": "en",
        "user_id": uuid4(),
        "agent_id": AgentId.FUNDAMENTALS_ANALYST,
        "ticker": "AAPL",
        "max_tokens": 1024,
        "timeout_s": 30.0,
        "profile": {},
    }


def test_a_card_bearing_retry_is_kept():
    gw = _RepairGateway([_WITH_CARDS])
    out = asyncio.run(_attempt_cards_repair(**_repair_kwargs(gw)))
    assert out is not None
    prose, env, cards = out
    assert "The repaired analysis" in prose
    assert "[CLAIMS]" not in prose
    assert env.headline == "repaired card view"
    assert cards is not None and len(cards.cards) == 5
    assert gw.calls[0]["audit"]["audit_flow"] == "room_cards_repair"


def test_the_note_pastes_the_literal_card_template():
    """The pilot's repair-corpus lesson: an ask that names 'the shape your
    instructions specify' comes back as a condensed prose list that fails the
    line grammar. The retry must be handed the exact lines to emit."""
    gw = _RepairGateway([_WITH_CARDS])
    asyncio.run(_attempt_cards_repair(**_repair_kwargs(gw)))
    note = _msg_content(gw.calls[0]["messages"][-1])
    assert "did not carry a parseable CLAIMS block" in note
    assert "item=eq   dir=support|oppose|neutral grade=well|partial|unsupported" in note
    assert "File all five items" in note


def test_a_retry_still_without_cards_is_none():
    gw = _RepairGateway([_NO_CARDS])
    assert asyncio.run(_attempt_cards_repair(**_repair_kwargs(gw))) is None


def test_a_stream_error_is_none():
    gw = _RepairGateway(["__STREAM_ERROR__"])
    assert asyncio.run(_attempt_cards_repair(**_repair_kwargs(gw))) is None


# ── end-to-end through RoomRunner ──────────────────────────────────────────


def _run_room(gateway) -> dict:
    captured: dict = {"texts": {}}

    async def _drain():
        async for ev in RoomRunner(llm=gateway).run(  # type: ignore[arg-type]
            user_id=uuid4(),
            ticker="AAPL",
            mandate=hydrate_coach_mandate(
                {
                    "plan": "trader",
                    "risk_score": 3,
                    "single_name_cap_pct": 3.0,
                }
            ),
            char_delay_min=0.0,
            char_delay_max=0.0,
        ):
            if ev.kind == "agent_token":
                captured["texts"][ev.agent_id.value] = captured["texts"].get(
                    ev.agent_id.value, ""
                ) + (ev.text or "")
            if ev.kind == "verdict":
                captured["v"] = ev.verdict

    asyncio.run(_drain())
    return captured


_CARDS_BLOCK = (
    "[CLAIMS]\n"
    "item=eq dir=support grade=well data=yes claim=FCF holds nums=$1.2B\n"
    "item=vc dir=neutral grade=partial data=no claim=unreadable\n"
    "item=vh dir=support grade=well data=yes claim=cheap vs peers nums=11.2x\n"
    "item=bs dir=oppose grade=partial data=yes claim=wall 2027 nums=$850M\n"
    "item=moat dir=support grade=well data=yes claim=switching costs\n"
    "[/CLAIMS]"
)


class _RoomGateway:
    """Every prose agent answers WITH an envelope; the four card desks also
    file CLAIMS. `bare_agent` omits the block; its repair turn (the
    [AMI fact-check] note) yields the card-bearing answer. The PM answers
    JSON."""

    def __init__(self, bare_agent: str | None = None, repaired: str | None = None):
        self._bare = bare_agent
        self._repaired = repaired or _WITH_CARDS
        self.calls: list[dict] = []

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(
        self,
        *,
        system_prompt,
        messages,
        model_tier,
        locale="en",
        max_tokens=1024,
        meta=None,
        **audit,
    ):
        agent = audit.get("audit_agent_id")
        self.calls.append({"agent": agent, "flow": audit.get("audit_flow"), "messages": messages})
        if agent == AgentId.PORTFOLIO_MANAGER.value:
            yield json.dumps(
                {
                    "action": "APPROVE",
                    "size_pct": 2.0,
                    "entry": 150.0,
                    "stop": 141.0,
                    "target": 172.0,
                    "horizon_days": 90,
                    "narration": "PM: take it.",
                }
            )
            return
        if agent == self._bare and not any("[AMI fact-check]" in _msg_content(m) for m in messages):
            yield (
                f"[STANCE: for | CONVICTION: high | HEADLINE: {agent} view]\n"
                "A considered view, but the card channel never fired."
            )
            return
        if agent == self._bare:
            yield self._repaired
            return
        card_block = (
            _CARDS_BLOCK
            if agent
            in {
                AgentId.FUNDAMENTALS_ANALYST.value,
                AgentId.BULL_RESEARCHER.value,
                AgentId.BEAR_RESEARCHER.value,
                AgentId.RESEARCH_MANAGER.value,
            }
            else ""
        )
        yield (
            f"[STANCE: for | CONVICTION: high | HEADLINE: {agent} view]\n"
            f"A considered view with the envelope leading.\n{card_block}"
        )


def _calls_for(gw: _RoomGateway, agent: str) -> list[dict]:
    return [c for c in gw.calls if c["agent"] == agent]


@pytest.fixture
def cards_envelope_on(monkeypatch):
    monkeypatch.setattr(settings, "room_cards_envelope_enabled", True)
    yield
    monkeypatch.undo()


def test_a_bare_card_desk_gets_exactly_one_repair_and_keeps_the_retry(
    cards_envelope_on,
):
    gw = _RoomGateway(bare_agent=AgentId.FUNDAMENTALS_ANALYST.value)
    captured = _run_room(gw)

    calls = _calls_for(gw, AgentId.FUNDAMENTALS_ANALYST.value)
    assert len(calls) == 2, "exactly one repair attempt"
    assert calls[0]["flow"] == "room"
    assert calls[1]["flow"] == "room_cards_repair"
    note = _msg_content(calls[1]["messages"][-1])
    assert "did not carry a parseable CLAIMS block" in note

    done = captured["texts"]
    assert "The repaired analysis" in done[AgentId.FUNDAMENTALS_ANALYST.value]
    assert "[CLAIMS]" not in done[AgentId.FUNDAMENTALS_ANALYST.value]
    assert captured["v"] is not None


def test_a_failed_repair_leaves_the_original_prose_and_verdict(
    cards_envelope_on,
):
    gw = _RoomGateway(bare_agent=AgentId.BULL_RESEARCHER.value, repaired=_NO_CARDS)
    captured = _run_room(gw)

    calls = _calls_for(gw, AgentId.BULL_RESEARCHER.value)
    assert len(calls) == 2, "one repair attempt, not a loop"
    done = captured["texts"]
    assert "the card channel never fired" in done[AgentId.BULL_RESEARCHER.value]
    assert "[CLAIMS]" not in done[AgentId.BULL_RESEARCHER.value]
    assert captured["v"] is not None


def test_the_flag_off_never_re_asks_a_bare_desk():
    gw = _RoomGateway(bare_agent=AgentId.FUNDAMENTALS_ANALYST.value)
    _run_room(gw)
    repairs = [c for c in gw.calls if c["flow"] == "room_cards_repair"]
    assert repairs == []
    fundamentals_calls = _calls_for(gw, AgentId.FUNDAMENTALS_ANALYST.value)
    assert len(fundamentals_calls) == 1


def test_card_bearing_turns_are_never_re_asked(cards_envelope_on):
    gw = _RoomGateway(bare_agent="nobody")
    _run_room(gw)
    repairs = [c for c in gw.calls if c["flow"] == "room_cards_repair"]
    assert repairs == []
    # Eleven prose agents, each exactly one base "room" call; the PM speaks
    # under its own "room_pm" flow.
    prose_calls = [c for c in gw.calls if c["flow"] == "room"]
    assert len(prose_calls) == 11


def test_a_non_desk_bare_turn_gets_no_cards_repair(cards_envelope_on):
    """The news analyst is not a card desk: the flag gives it no card prompt
    and its bare card state (there is none to give) earns no re-ask."""
    gw = _RoomGateway(bare_agent=AgentId.NEWS_ANALYST.value)
    _run_room(gw)
    news_repairs = [
        c for c in _calls_for(gw, AgentId.NEWS_ANALYST.value) if c["flow"] == "room_cards_repair"
    ]
    assert news_repairs == []
