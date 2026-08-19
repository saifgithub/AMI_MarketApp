"""CR197 — the RISK debators declare the size they actually endorse.

Why a fourth envelope field, when the debate spread already exists in code:
`risk_debator_sizes()` computes trader+2 / trader−1.5 / trader and hands each
debator the figure its role must argue. That spread is a constant — 3.5 pt, every
run, by construction — so CR143's M4 ("the sizes aggressive/conservative/neutral
propose; zero spread means that phase is costume") was never going to measure
anything the code did not already determine. The quantity that carries information
is the DELTA: given the numbers in front of it, does the agent endorse the figure
it was handed, or move off it?

What this is not: a control. It is a prompt-level instruction, and P2 is explicit
that those measure ~30% compliance; DEF251 measured 20% of debator turns emitting no
envelope at all. So every assertion here is about the channel being *available and
correctly read when present* — never about it being reliably filled. Nothing
downstream may assume the field exists, which is why the optional-field and
key-presence behaviours below are pinned as hard as the parsing is.
"""

from __future__ import annotations

import pytest

from app.schemas.agents import AgentId, AgentMessage
from app.services import room_prompts
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_prompts import build_room_messages
from app.services.room_runner import parse_stance_envelope

_DEBATORS = (
    AgentId.AGGRESSIVE_DEBATOR,
    AgentId.CONSERVATIVE_DEBATOR,
    AgentId.NEUTRAL_DEBATOR,
)
_NON_DEBATOR_PROSE_AGENTS = (
    AgentId.BULL_RESEARCHER,
    AgentId.BEAR_RESEARCHER,
    AgentId.TRADER,
    AgentId.RESEARCH_MANAGER,
    AgentId.MARKET_ANALYST,
)


def _prompt(agent_id: AgentId) -> str:
    system, _ = build_room_messages(
        agent_id=agent_id,
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        user_id=None,
        ticker="MSFT",
        profile={"base_price": 100.0},
        transcript=[],
        trade_proposal={"size_pct": 3.0, "entry": 100.0, "stop": 94.0},
        agent_size_pct=3.0,
    )
    return system


# ── the contract reaches exactly the three agents that argue a size ───────────


@pytest.mark.parametrize("agent_id", _DEBATORS)
def test_each_debator_is_asked_for_a_size(agent_id):
    prompt = _prompt(agent_id)
    assert "SIZE: <n.n>%" in prompt
    assert "- SIZE:" in prompt


@pytest.mark.parametrize("agent_id", _NON_DEBATOR_PROSE_AGENTS)
def test_no_other_prose_agent_is_asked_for_one(agent_id):
    """Scope asserted, not assumed. A ninth agent growing a SIZE field would put a
    number into a channel whose only reader interprets it as a debator's endorsed
    position size."""
    assert "SIZE: <n.n>%" not in _prompt(agent_id)


def test_the_pm_still_gets_no_stance_envelope_at_all():
    """The PM emits a JSON verdict; a trailing envelope line corrupts it (CR106 B2).
    Splitting the envelope contract must not have handed it one by accident."""
    prompt = _prompt(AgentId.PORTFOLIO_MANAGER)
    assert "[STANCE:" not in prompt
    assert "SIZE: <n.n>%" not in prompt


@pytest.mark.parametrize("agent_id", _DEBATORS)
def test_the_size_ask_does_not_disturb_the_first_line_contract(agent_id):
    """DEF243/DEF251: `_STANCE_FORMAT` owns line 1, and the displacement rate got
    WORSE the last time this prompt region was reworded. Adding a field inside the
    envelope must leave the line-1 demand and the stance shape untouched."""
    prompt = _prompt(agent_id)
    assert "your VERY FIRST line must be this one line" in prompt
    assert "[STANCE: for|against|neutral" in prompt
    assert "Never guess a side" in prompt


# ── parsing ──────────────────────────────────────────────────────────────────


def _turn(envelope: str) -> str:
    return f"{envelope}\nThe thesis sentence.\n- a bullet"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("4.5%", 4.5),
        ("4.5", 4.5),
        ("  6 % ", 6.0),
        ("0.5%", 0.5),
        ("100%", 100.0),
        # Out of bounds or non-numeric: a misread field, not a position size.
        ("0%", None),
        ("101%", None),
        ("-3%", None),
        ("n/a", None),
        ("", None),
    ],
)
def test_size_field_parses_or_declines(raw, expected):
    text = _turn(
        f"[STANCE: for | CONVICTION: high | SIZE: {raw} | HEADLINE: 12% FCF yield]"
    )
    _body, env = parse_stance_envelope(text)
    assert env.size_pct == expected


def test_a_missing_size_costs_only_the_size():
    """The parser reads fields independently by design. An envelope with no SIZE is
    the eight-agent norm and must not degrade the other three fields."""
    text = _turn("[STANCE: against | CONVICTION: medium | HEADLINE: stop is 6% away]")
    _body, env = parse_stance_envelope(text)
    assert env.size_pct is None
    assert (env.stance, env.conviction, env.headline) == (
        "against",
        "medium",
        "stop is 6% away",
    )


def test_a_mangled_size_costs_only_the_size():
    text = _turn(
        "[STANCE: for | CONVICTION: high | SIZE: about a third | HEADLINE: 12% yield]"
    )
    _body, env = parse_stance_envelope(text)
    assert env.size_pct is None
    assert env.stance == "for" and env.conviction == "high"


def test_the_envelope_is_still_stripped_from_the_prose():
    """The whole line comes off the rendered turn whether or not every field parsed —
    a SIZE field must not leave the machine channel visible to the reader."""
    text = _turn("[STANCE: for | CONVICTION: high | SIZE: 4.5% | HEADLINE: cheap]")
    body, _env = parse_stance_envelope(text)
    assert "SIZE:" not in body
    assert "[STANCE:" not in body
    assert body.startswith("The thesis sentence.")


def test_a_size_survives_a_stance_the_parser_rejected():
    """Deliberate asymmetry with conviction, which IS nulled without a stance. A
    stated size is a measurement worth keeping even when the agent fumbled the field
    next to it; a conviction without a stance is 'strongly, about nothing'."""
    text = _turn("[STANCE: bullish | CONVICTION: high | SIZE: 4.5% | HEADLINE: cheap]")
    _body, env = parse_stance_envelope(text)
    assert env.stance is None and env.conviction is None
    assert env.size_pct == 4.5


def test_a_headline_mentioning_oversize_is_not_read_as_the_field():
    text = _turn(
        "[STANCE: against | CONVICTION: high | HEADLINE: OVERSIZE: 9% of book]"
    )
    _body, env = parse_stance_envelope(text)
    assert env.size_pct is None


def test_the_legacy_tail_form_with_a_size_is_still_stripped():
    """DEF247's inline/tail variant. If the tail regex had not learned the optional
    SIZE segment, a debator's tail-form envelope would stop being recognised and
    would render to the user as prose."""
    text = (
        "The thesis sentence.\n- a bullet\n"
        "[STANCE: for | CONVICTION: low | SIZE: 2.0% | HEADLINE: thin volume]"
    )
    body, env = parse_stance_envelope(text)
    assert "[STANCE:" not in body
    assert env.stance == "for" and env.size_pct == 2.0


# ── it survives the trip to the client and the journal ───────────────────────


def test_agent_message_defaults_the_field_for_older_transcripts():
    """Every transcript recorded before CR197 deserialises with the field absent.
    Optional-with-default, so a replay of an old run is not an error."""
    msg = AgentMessage.model_validate(
        {
            "agent_id": "neutral_debator",
            "content": "…",
            "timestamp": "2026-08-07T00:00:00Z",
            "stance": "for",
        }
    )
    assert msg.argued_size_pct is None


def test_the_field_round_trips_when_present():
    msg = AgentMessage.model_validate(
        {
            "agent_id": "neutral_debator",
            "content": "…",
            "timestamp": "2026-08-19T00:00:00Z",
            "stance": "neutral",
            "argued_size_pct": 3.5,
        }
    )
    assert msg.argued_size_pct == 3.5
    assert msg.model_dump()["argued_size_pct"] == 3.5


def test_the_two_format_constants_have_not_collapsed():
    """If the RISK variant ever equals the base one, every test above still passes
    while the SIZE field has silently stopped being asked for."""
    assert room_prompts._STANCE_FORMAT_RISK != room_prompts._STANCE_FORMAT
    assert "SIZE:" in room_prompts._STANCE_FORMAT_RISK
    assert "SIZE:" not in room_prompts._STANCE_FORMAT
