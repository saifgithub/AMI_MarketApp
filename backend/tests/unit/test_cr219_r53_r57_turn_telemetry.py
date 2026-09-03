"""CR219 R53 + R57 — permanent turn telemetry: DATA GAPS and envelope emission.

Two measurement channels, both riding the existing JSONB `transcript` column
with no migration (`AgentMessage.data_gaps` / `.envelope_parsed`,
`app/schemas/agents.py`), both stripped from the user-visible `content` before
it is ever streamed or committed, both governed by the same rule CR106 B2
already set for the stance envelope: an absence is a MEASURED rate, never
silently coerced into a value that looks like "nothing was wrong".

**R53** institutionalizes the arms experiment's one-off `DATA I LACKED:`
addendum (`docs/forward_planning/CR219_room_prompt_contradictions/evidence/
analysis/aggregate_arms.py` — 21 asks from 9/12 agents, the project's best
data-roadmap evidence) as a permanent `GAPS:` tail on the FOUR analysts only —
the voices whose job is reading a fixed data block and noticing a hole in it.
`None` for the eight other agents (never asked); `None` for an analyst turn
that never emitted the tail (asked and silent — an omission, not a zero);
`[]` for the prompt's own `GAPS: none` opt-out (asked, and nothing was
missing — a DISTINCT positive fact from `None`).

**R57** is the measurement leg of item 11 in `fable/05_further_improvements.md`
— NOT the grammar-forcing candidate that section also raises and explicitly
declines to build yet. Two decisions stay pinned and untouched here:
`test_cr210_room_wiring.py::test_no_prose_agent_is_ever_constrained` (no prose
agent's decode is ever grammar-constrained) and DEF251's own comment (the
envelope is a measurement channel, never a control). `envelope_parsed` records
whether `parse_stance_envelope` located a tail AT ALL — DEF251's own "contains
the string STANCE" signal — independent of whether any of its three FIELDS
went on to parse to a valid value; `STANCE: none` is a fully parsed envelope
even though `.stance` ends up `None`. `None` (not `False`) for a turn nothing
ever asked to read: the PM's JSON verdict, the CR201 Risk-Officer-RENDERED
debator turns (`risk_officer.render_officer_turns` — DEF247/DEF251/DEF257 are
explicitly unreachable there, per that module's own docstring, because there
is no free-text tail to fail to emit), and the non-live scripted demo path.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.schemas import AgentId
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_prompts import GAPS_ITEM_MAX_CHARS, build_room_messages
from app.services.room_runner import (
    PHASES,
    RoomRunner,
    parse_data_gaps,
    parse_stance_envelope,
)
from tests.unit.test_room_runner import _collect

FOUR_ANALYSTS = PHASES[0].agents
_PROSE = "The multiple is defensible.\n\n- **FCF yield 6.2%** vs sector 3.1%"


def test_vacuity_the_four_analysts_are_the_ones_this_suite_thinks_they_are():
    assert set(FOUR_ANALYSTS) == {
        AgentId.FUNDAMENTALS_ANALYST,
        AgentId.MARKET_ANALYST,
        AgentId.NEWS_ANALYST,
        AgentId.SOCIAL_MEDIA_ANALYST,
    }


# ── R53 — the parser ────────────────────────────────────────────────────────


def test_a_well_formed_tail_is_parsed_and_stripped():
    body, gaps = parse_data_gaps(
        _PROSE + "\nGAPS: segment revenue split; 5yr P/E band; peer comps"
    )
    assert gaps == ["segment revenue split", "5yr P/E band", "peer comps"]
    assert body == _PROSE
    assert "GAPS" not in body


def test_the_prompts_own_opt_out_is_an_empty_list_not_a_null():
    """'GAPS: none' is a POSITIVE fact — nothing was missing — and must not
    collapse to the same value an omitted tail produces (the CR106 T-SUM11
    null-vs-neutral discipline, moved one field over)."""
    body, gaps = parse_data_gaps(_PROSE + "\nGAPS: none")
    assert gaps == []
    assert gaps is not None
    assert body == _PROSE


def test_a_missing_tail_yields_none_and_leaves_the_prose_alone():
    body, gaps = parse_data_gaps(_PROSE)
    assert gaps is None
    assert body == _PROSE


def test_none_and_absent_are_distinguishable_states():
    """The load-bearing distinction the whole telemetry design rests on: an
    aggregation script must be able to tell '0 requests, asked and clean' from
    '0 requests, never answered' — the CR040 degrade-loudly rule."""
    _, omitted = parse_data_gaps(_PROSE)
    _, opted_out = parse_data_gaps(_PROSE + "\nGAPS: none")
    assert omitted is None
    assert opted_out == []
    assert omitted != opted_out


@pytest.mark.parametrize("spelling", ["none", "None", "NONE", "no gaps", "n/a", "na"])
def test_every_none_spelling_the_prompt_might_produce_lands_in_the_empty_list(spelling):
    _, gaps = parse_data_gaps(f"{_PROSE}\nGAPS: {spelling}")
    assert gaps == []


def test_case_and_spacing_drift_still_parses():
    _, gaps = parse_data_gaps(_PROSE + "\n gaps:  peer comps ; 5yr multiples ")
    assert gaps == ["peer comps", "5yr multiples"]


def test_bold_emphasis_is_tolerated_the_way_the_stance_envelope_learned_to_be():
    """DEF257's lesson, applied here before it has to be re-learned: the
    envelope parser did not accept markdown emphasis until it was measured
    leaking. GAPS gets the same tolerance from day one."""
    body, gaps = parse_data_gaps(_PROSE + "\n**GAPS: none**")
    assert gaps == []
    assert body == _PROSE
    assert "GAPS" not in body

    body2, gaps2 = parse_data_gaps(_PROSE + "\n**GAPS: segment split**")
    assert gaps2 == ["segment split"]
    assert body2 == _PROSE


def test_an_optional_bracket_is_tolerated_either_way():
    _, bracketed = parse_data_gaps(_PROSE + "\n[GAPS: peer comps]")
    _, bare = parse_data_gaps(_PROSE + "\nGAPS: peer comps")
    assert bracketed == bare == ["peer comps"]


def test_more_than_three_items_is_truncated_to_three():
    _, gaps = parse_data_gaps(
        _PROSE + "\nGAPS: a; b; c; d; e"
    )
    assert gaps == ["a", "b", "c"]


def test_an_over_length_item_is_dropped_not_truncated():
    """Nulled-by-omission, never cut — the same DEF059-class rule
    STANCE_HEADLINE_MAX_CHARS applies: a truncated phrase can name the wrong
    gap, and dropping it costs one item, not the whole tail."""
    long_item = "x" * (GAPS_ITEM_MAX_CHARS + 1)
    _, gaps = parse_data_gaps(f"{_PROSE}\nGAPS: {long_item}; peer comps")
    assert gaps == ["peer comps"]

    at_cap = "y" * GAPS_ITEM_MAX_CHARS
    _, ok = parse_data_gaps(f"{_PROSE}\nGAPS: {at_cap}")
    assert ok == [at_cap]


def test_an_all_over_length_tail_yields_an_empty_list_not_none():
    """Every item dropped is still a FOUND tail — the agent tried to answer
    and every candidate failed the bound. That is closer to 'none' than to
    'never asked', so it stores as `[]`, matching what a human reading the raw
    turn would conclude: the tail was there."""
    long_item = "z" * (GAPS_ITEM_MAX_CHARS + 1)
    _, gaps = parse_data_gaps(f"{_PROSE}\nGAPS: {long_item}")
    assert gaps == []


def test_a_lettered_or_bulleted_item_marker_is_stripped():
    """The arms harness this prompt evolved from used `(a) ... (b) ...`; a
    drifted model reproducing that habit must not manufacture a bogus
    '(unbucketed)' entry in the aggregation over a leftover marker."""
    _, gaps = parse_data_gaps(
        _PROSE + "\nGAPS: (a) segment split; (b) peer comps; - historical FCF"
    )
    assert gaps == ["segment split", "peer comps", "historical FCF"]


def test_a_comma_inside_one_item_does_not_fracture_it():
    """';' is the prompt's own delimiter for exactly this reason — a gap item
    routinely contains a comma ('segment revenue, geographic split')."""
    _, gaps = parse_data_gaps(_PROSE + "\nGAPS: segment revenue, geographic split")
    assert gaps == ["segment revenue, geographic split"]


def test_a_trailing_period_is_stripped_per_item():
    _, gaps = parse_data_gaps(_PROSE + "\nGAPS: peer comps.; historical FCF.")
    assert gaps == ["peer comps", "historical FCF"]


def test_an_empty_tail_is_the_empty_list():
    _, gaps = parse_data_gaps(_PROSE + "\nGAPS:")
    assert gaps == []


def test_the_tail_survives_trailing_whitespace_only():
    _, gaps = parse_data_gaps(_PROSE + "\nGAPS: none  \n\n")
    assert gaps == []


def test_a_gaps_shaped_line_followed_by_more_prose_is_not_the_machine_channel():
    """Unlike STANCE (DEF247 widened its search to any line), GAPS stays
    end-anchored deliberately — see the module comment in room_runner.py. A
    line shaped like the tail that real argument follows is prose discussing
    the concept, not a duplicate machine channel, until the corpus says
    otherwise; only the actual LAST line is ever a candidate."""
    text = (
        "GAPS: an interesting phrase for what follows.\n"
        "And here the analyst goes on to make the actual case at length."
    )
    body, gaps = parse_data_gaps(text)
    assert gaps is None
    assert body == text


def test_a_blank_input_yields_none_not_a_crash():
    body, gaps = parse_data_gaps("")
    assert gaps is None
    assert body == ""
    body2, gaps2 = parse_data_gaps("   \n\n  ")
    assert gaps2 is None


# ── R53 — strip-order composition with the stance envelope ─────────────────


_FULL_TURN = (
    "[STANCE: for | CONVICTION: high | HEADLINE: FCF 6.2% vs 3.1%]\n"
    "The multiple is defensible.\n\n- FCF yield 6.2% vs sector 3.1%\n"
    "GAPS: segment revenue split; 5yr P/E band"
)


def test_stance_then_gaps_strips_both_and_leaves_only_prose():
    body1, env = parse_stance_envelope(_FULL_TURN)
    body2, gaps = parse_data_gaps(body1)
    assert env.stance == "for"
    assert gaps == ["segment revenue split", "5yr P/E band"]
    assert body2 == "The multiple is defensible.\n\n- FCF yield 6.2% vs sector 3.1%"
    assert "STANCE" not in body2 and "GAPS" not in body2


def test_gaps_then_stance_strips_both_and_agrees_byte_for_byte():
    """Composition order must not matter — the WP's own acceptance bar."""
    body1, gaps = parse_data_gaps(_FULL_TURN)
    body2, env = parse_stance_envelope(body1)
    assert env.stance == "for"
    assert gaps == ["segment revenue split", "5yr P/E band"]

    ref_body, ref_env = parse_stance_envelope(_FULL_TURN)
    ref_body2, ref_gaps = parse_data_gaps(ref_body)
    assert body2 == ref_body2
    assert gaps == ref_gaps


def test_absence_of_stance_composes_cleanly():
    text = _PROSE + "\nGAPS: peer comps"
    b1, env = parse_stance_envelope(text)
    b2, gaps = parse_data_gaps(b1)
    assert env.stance is None
    assert gaps == ["peer comps"]
    assert b2 == _PROSE


def test_absence_of_gaps_composes_cleanly():
    text = "[STANCE: for | CONVICTION: high | HEADLINE: h]\n" + _PROSE
    b1, env = parse_stance_envelope(text)
    b2, gaps = parse_data_gaps(b1)
    assert env.stance == "for"
    assert gaps is None
    assert b2 == _PROSE


def test_absence_of_both_composes_cleanly():
    b1, env = parse_stance_envelope(_PROSE)
    b2, gaps = parse_data_gaps(b1)
    assert env.stance is None
    assert gaps is None
    assert b2 == _PROSE


# ── R53 — the prompt asks for it, and only of the four analysts ────────────


def _system_prompt_for(agent_id: AgentId) -> str:
    system_prompt, _ = build_room_messages(
        agent_id=agent_id,
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        user_id=uuid4(),
        ticker="AAPL",
        profile={},
        transcript=[],
    )
    return system_prompt


def test_every_analyst_is_asked_for_gaps_exactly_once():
    """The FORMAT SPEC LINE is the thing that must appear exactly once — like
    STANCE (3 mentions: the bracket spec plus two explanatory bullets), the
    GAPS instruction legitimately names 'GAPS:' twice (the spec line, and the
    'write GAPS: none' bullet), so counting the bare token would fail on a
    correctly-single instruction. The spec line itself is unique text."""
    for agent in FOUR_ANALYSTS:
        prompt = _system_prompt_for(agent)
        assert prompt.count("end the turn with one more line") == 1, agent.value
        assert (
            "GAPS: <up to 3 short items"
            in prompt
        ), agent.value


def test_no_non_analyst_is_ever_asked_for_gaps():
    for agent in AgentId:
        if agent in FOUR_ANALYSTS or agent in (AgentId.CONCIERGE, AgentId.RISK_OFFICER):
            continue
        prompt = _system_prompt_for(agent)
        assert "GAPS:" not in prompt, agent.value


def test_the_gaps_line_trails_after_the_stance_envelope_not_before_it():
    """STANCE leads (DEF147); GAPS trails. Two instructions for two different
    slots — the DEF251 collision was two instructions for ONE slot."""
    prompt = _system_prompt_for(AgentId.FUNDAMENTALS_ANALYST)
    assert prompt.index("VERY FIRST line") < prompt.index("GAPS:")


# ── R53/R57 — storage shape on AgentMessage ──────────────────────────────


class _TelemetryGateway:
    """One scripted answer per agent id, covering every shape this suite
    needs on the transcript: a full envelope+gaps turn, a none-opt-out, a
    silent (no-envelope, no-gaps) turn, and an envelope with no gaps tail."""

    def __init__(self, silent_agent: str | None = None) -> None:
        self._silent = silent_agent

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(
        self, *, system_prompt, messages, model_tier,
        locale="en", max_tokens=1024, audit_agent_id=None, meta=None, **_kw,
    ):
        if audit_agent_id == AgentId.PORTFOLIO_MANAGER.value:
            yield (
                '{"action": "APPROVE", "size_pct": 3.0, "entry": 150, '
                '"stop": 141, "target": 172, "horizon_days": 42, '
                '"narration": "PM: APPROVE."}'
            )
            return
        if audit_agent_id == self._silent:
            yield "I have nothing to add on this name."
            return
        if audit_agent_id == AgentId.FUNDAMENTALS_ANALYST.value:
            yield (
                "[STANCE: for | CONVICTION: high | HEADLINE: FCF 6.2% vs 3.1%]\n"
                "The case holds on **6.2%** free cash flow yield.\n"
                "GAPS: segment revenue split; 5yr P/E band"
            )
            return
        if audit_agent_id == AgentId.MARKET_ANALYST.value:
            yield (
                "[STANCE: neutral | CONVICTION: low | HEADLINE: mixed tape]\n"
                "Mixed technical signals this week.\nGAPS: none"
            )
            return
        yield (
            "[STANCE: neutral | CONVICTION: medium | HEADLINE: no strong view]\n"
            "Nothing decisive to add."
        )


def _run(silent_agent: str | None = None):
    runner = RoomRunner(llm=_TelemetryGateway(silent_agent))  # type: ignore[arg-type]
    events = _collect(runner.run(
        user_id=uuid4(),
        ticker="AAPL",
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        char_delay_min=0.0,
        char_delay_max=0.0,
    ))
    return events, runner.get_run(events[0].run_id)


def test_a_full_turn_stores_the_parsed_list_and_strips_it_from_content():
    _, run = _run()
    fa = next(
        m for m in run.transcript
        if m.agent_id == AgentId.FUNDAMENTALS_ANALYST.value
    )
    assert fa.data_gaps == ["segment revenue split", "5yr P/E band"]
    assert fa.envelope_parsed is True
    assert "GAPS" not in fa.content
    assert "STANCE" not in fa.content


def test_the_none_opt_out_stores_as_an_empty_list_on_the_transcript():
    _, run = _run()
    ma = next(
        m for m in run.transcript if m.agent_id == AgentId.MARKET_ANALYST.value
    )
    assert ma.data_gaps == []
    assert ma.envelope_parsed is True


def test_an_analyst_that_never_emits_gaps_stores_none_not_empty():
    """News/Social above emit a stance but no GAPS tail — asked, but silent
    on this channel. Distinct from Market's explicit 'none'."""
    _, run = _run()
    news = next(
        m for m in run.transcript if m.agent_id == AgentId.NEWS_ANALYST.value
    )
    assert news.data_gaps is None
    assert news.envelope_parsed is True  # it DID emit a stance envelope


def test_a_silent_analyst_is_both_omissions_at_once():
    """No envelope AND no gaps — the two channels degrade independently, and
    both correctly read as 'asked and did not answer' rather than crashing
    or borrowing a value from each other."""
    _, run = _run(silent_agent=AgentId.NEWS_ANALYST.value)
    news = next(
        m for m in run.transcript if m.agent_id == AgentId.NEWS_ANALYST.value
    )
    assert news.envelope_parsed is False
    assert news.data_gaps is None
    assert news.stance is None


def test_no_non_analyst_ever_carries_a_data_gaps_value():
    """The eight non-analyst prose agents were never asked; `parse_data_gaps`
    is never even called for them (room_runner.py gates the call itself, not
    just the prompt) — the eight voices always read None here regardless of
    what their turn happens to contain."""
    _, run = _run()
    non_analysts = [
        m for m in run.transcript
        if AgentId(m.agent_id) not in FOUR_ANALYSTS
        and m.agent_id != AgentId.PORTFOLIO_MANAGER.value
    ]
    assert len(non_analysts) == 7, "vacuity guard — 11 voices minus 4 analysts"
    assert all(m.data_gaps is None for m in non_analysts)


def test_the_pm_carries_neither_telemetry_field():
    """The PM's turn is a JSON verdict via a separate append path — never
    touched by either parser."""
    _, run = _run()
    pm = next(
        m for m in run.transcript
        if m.agent_id == AgentId.PORTFOLIO_MANAGER.value
    )
    assert pm.data_gaps is None
    assert pm.envelope_parsed is None


def test_every_non_pm_non_analyst_voice_still_carries_envelope_parsed():
    """R57 is not scoped to the analysts — every prose voice's stance-envelope
    emission is measured, only R53's gaps channel is analyst-only."""
    _, run = _run()
    voices = [
        m for m in run.transcript
        if m.agent_id != AgentId.PORTFOLIO_MANAGER.value
    ]
    assert len(voices) == 11, "vacuity guard — the comb is 11 voices"
    assert all(m.envelope_parsed is not None for m in voices)


def test_the_scripted_demo_path_carries_neither_field():
    """No LLM ran, so nothing was asked and nothing was measured — the same
    'nothing to report' state the PM's own turn carries, for a different
    reason (CR106's precedent: the scripted path states no stance rather
    than inventing one)."""
    runner = RoomRunner()
    events = _collect(runner.run(
        user_id=uuid4(),
        ticker="AAPL",
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        char_delay_min=0.0,
        char_delay_max=0.0,
    ))
    run = runner.get_run(events[0].run_id)
    assert len(run.transcript) == 12, "vacuity guard"
    assert all(m.data_gaps is None for m in run.transcript)
    assert all(m.envelope_parsed is None for m in run.transcript)


# ── R57 — envelope_parsed tracks EMISSION, independent of field validity ───


class _StanceNoneGateway:
    """Every analyst states STANCE: none (a fully-formed, deliberate opt-out)
    — envelope_parsed must read True even though .stance itself is None."""

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(
        self, *, system_prompt, messages, model_tier,
        locale="en", max_tokens=1024, audit_agent_id=None, meta=None, **_kw,
    ):
        if audit_agent_id == AgentId.PORTFOLIO_MANAGER.value:
            yield (
                '{"action": "PASS", "size_pct": null, "entry": null, '
                '"stop": null, "target": null, "horizon_days": null, '
                '"narration": "PM: PASS."}'
            )
            return
        yield "[STANCE: none | CONVICTION: low | HEADLINE: no view]\nNothing to add."


def test_a_deliberate_none_stance_still_counts_as_a_parsed_envelope():
    runner = RoomRunner(llm=_StanceNoneGateway())  # type: ignore[arg-type]
    events = _collect(runner.run(
        user_id=uuid4(),
        ticker="AAPL",
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        char_delay_min=0.0,
        char_delay_max=0.0,
    ))
    run = runner.get_run(events[0].run_id)
    voices = [m for m in run.transcript if m.agent_id != AgentId.PORTFOLIO_MANAGER.value]
    assert len(voices) == 11, "vacuity guard"
    for m in voices:
        assert m.stance is None, m.agent_id  # the field itself is null
        assert m.envelope_parsed is True, m.agent_id  # but the tail WAS found
