"""CR106 B2 — the per-agent stance envelope that the consensus comb is built on.

The comb tints nothing by stance (family colour is sacred) — stance is the BAND
a hex sits in. That makes a wrong band a confident lie about what an agent said,
so the whole design rests on one rule: **`null` survives to the pixel.** A
missing stance goes to a separate gutter, never to `neutral`, because `neutral`
has to mean the agent expressed neutrality and never that the parser gave up
(CR106 T-SUM11 / the DEF059 class).

**Deviation from the CR, recorded:** §4.2 B2 proposed wrapping each turn in a
JSON envelope with the prose in a `body` field. Built as a trailing line
instead. The PM's JSON precedent the CR cites fails to parse in ~22% of runs
(DEF058), and a failed parse there is invisible — the PM's raw output is never
shown. An agent's prose IS the product: one unescaped quote and the user reads
raw JSON. A trailing line fails PARTIALLY (lose the stance, keep the prose) and
lands in the gutter the CR already designed for exactly that case. The wire
contract to the client is unchanged: stance · conviction · headline, nullable.
"""

from __future__ import annotations

from uuid import uuid4

from app.schemas import AgentId
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_prompts import (
    STANCE_HEADLINE_MAX_CHARS,
    build_room_messages,
)
from app.services.room_runner import (
    RoomRunner,
    build_journal_entry_for_run,
    parse_stance_envelope,
)
from tests.unit.test_room_runner import _collect


# ── the parser ───────────────────────────────────────────────────────────


_PROSE = "The multiple is defensible.\n\n- **FCF yield 6.2%** vs sector 3.1%"


def test_a_well_formed_tail_is_parsed_and_stripped_from_the_prose():
    body, env = parse_stance_envelope(
        _PROSE + "\n[STANCE: for | CONVICTION: high | HEADLINE: FCF 6.2% vs 3.1%]"
    )
    assert env.stance == "for"
    assert env.conviction == "high"
    assert env.headline == "FCF 6.2% vs 3.1%"
    # The envelope is a machine channel. It must not reach the user, and it
    # must not reach the next agent's prompt as if it were an argument.
    assert body == _PROSE
    assert "STANCE:" not in body


def test_case_and_spacing_drift_still_parses():
    _, env = parse_stance_envelope(
        "x\n[ stance:AGAINST |CONVICTION:  Low  | headline: Debt/EBITDA 4.1x ]"
    )
    assert env.stance == "against"
    assert env.conviction == "low"
    assert env.headline == "Debt/EBITDA 4.1x"


def test_no_tail_yields_all_nulls_and_leaves_the_prose_alone():
    body, env = parse_stance_envelope(_PROSE)
    assert body == _PROSE
    assert (env.stance, env.conviction, env.headline) == (None, None, None)


def test_the_prompts_own_opt_out_lands_in_the_gutter_not_in_neutral():
    """'STANCE: none' is the instruction's escape hatch for an agent whose role
    this turn is not to take a side. It must not become a neutral vote."""
    _, env = parse_stance_envelope(
        "x\n[STANCE: none | CONVICTION: low | HEADLINE: no view]"
    )
    assert env.stance is None
    assert env.conviction is None, "conviction without a stance is meaningless"


def test_an_unrecognised_stance_is_never_coerced_to_neutral():
    for bogus in ("bullish", "yes", "positive", "for-ish", ""):
        _, env = parse_stance_envelope(
            f"x\n[STANCE: {bogus} | CONVICTION: high | HEADLINE: h]"
        )
        assert env.stance is None, bogus


def test_an_unrecognised_conviction_does_not_take_the_stance_down_with_it():
    _, env = parse_stance_envelope(
        "x\n[STANCE: for | CONVICTION: extremely | HEADLINE: h]"
    )
    assert env.stance == "for"
    assert env.conviction is None


def test_an_over_length_headline_is_nulled_not_truncated():
    """A headline is an assertion; cutting one can invert it. The CR rejected
    first-sentence truncation for the same reason, and the whole point of
    capping in the schema is that the truncation bug does not simply relocate
    somewhere prettier."""
    long = "x" * (STANCE_HEADLINE_MAX_CHARS + 1)
    _, env = parse_stance_envelope(
        f"prose\n[STANCE: for | CONVICTION: high | HEADLINE: {long}]"
    )
    assert env.headline is None
    # The stance itself is unaffected — one bad field is not three.
    assert env.stance == "for"
    # And a headline exactly at the cap is kept.
    at_cap = "y" * STANCE_HEADLINE_MAX_CHARS
    _, ok = parse_stance_envelope(
        f"prose\n[STANCE: for | CONVICTION: high | HEADLINE: {at_cap}]"
    )
    assert ok.headline == at_cap


def test_only_a_trailing_envelope_is_read():
    """A bracketed aside mid-paragraph is prose, not a machine channel."""
    text = (
        "As noted [STANCE: for | CONVICTION: high | HEADLINE: not this one] the "
        "multiple is defensible."
    )
    body, env = parse_stance_envelope(text)
    assert env.stance is None
    assert body == text


def test_the_tail_survives_trailing_whitespace_only():
    _, env = parse_stance_envelope(
        "x\n[STANCE: neutral | CONVICTION: medium | HEADLINE: mixed]  \n\n"
    )
    assert env.stance == "neutral"


def test_a_truncated_turn_has_no_tail_and_so_no_stance():
    """DEF125's failure mode, met head-on: a length-stopped turn is cut off
    before it ever writes the tail. The honest result is the gutter — which is
    what the parser produces without a special case."""
    _, env = parse_stance_envelope(
        "The multiple is defensible and the buyback pace of **3"
    )
    assert env.stance is None


# ── the prompt asks for it, and only of the eleven ───────────────────────


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


def test_every_comb_voice_is_asked_for_a_stance():
    voices = [a for a in AgentId if a != AgentId.PORTFOLIO_MANAGER][:11]
    assert len(voices) == 11, "vacuity guard — the comb is 11 voices"
    for agent in voices:
        prompt = _system_prompt_for(agent)
        assert "[STANCE:" in prompt, agent.value
        assert "Never guess a side" in prompt, agent.value


def test_the_pm_is_never_asked_for_a_stance():
    """The PM is excluded from the comb by design — its position IS the hero
    tile — and a trailing line appended to a JSON verdict would corrupt the
    parse the whole run depends on."""
    prompt = _system_prompt_for(AgentId.PORTFOLIO_MANAGER)
    assert "[STANCE:" not in prompt


# ── end to end through a real run ────────────────────────────────────────


class _StancefulGateway:
    """Every agent answers with prose plus a tail; one deliberately omits it."""

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
        yield (
            "The case holds on **6.2%** free cash flow yield.\n"
            "[STANCE: for | CONVICTION: high | HEADLINE: FCF 6.2% vs 3.1%]"
        )


def _run(silent_agent: str | None = None):
    runner = RoomRunner(llm=_StancefulGateway(silent_agent))  # type: ignore[arg-type]
    events = _collect(runner.run(
        user_id=uuid4(),
        ticker="AAPL",
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        char_delay_min=0.0,
        char_delay_max=0.0,
    ))
    return events, runner.get_run(events[0].run_id)


def test_stances_reach_the_transcript_and_the_agent_done_events():
    events, run = _run()
    fa = next(
        m for m in run.transcript
        if m.agent_id == AgentId.FUNDAMENTALS_ANALYST.value
    )
    assert fa.stance == "for"
    assert fa.conviction == "high"
    assert fa.headline == "FCF 6.2% vs 3.1%"
    # And the user never sees the machine channel.
    assert "STANCE:" not in fa.content

    done = next(
        e for e in events
        if e.kind == "agent_done"
        and e.agent_id == AgentId.FUNDAMENTALS_ANALYST
    )
    assert done.stance == "for"
    assert done.headline == "FCF 6.2% vs 3.1%"


def test_the_pms_own_turn_carries_no_stance():
    _, run = _run()
    pm = next(
        m for m in run.transcript
        if m.agent_id == AgentId.PORTFOLIO_MANAGER.value
    )
    assert pm.stance is None


def test_an_agent_that_stated_nothing_stays_null_while_the_rest_do_not():
    """The band counts are taken over non-null stances only, so the caption can
    read '10 STATED A VIEW' rather than a total that always sums to 11."""
    _, run = _run(silent_agent=AgentId.NEWS_ANALYST.value)
    news = next(
        m for m in run.transcript if m.agent_id == AgentId.NEWS_ANALYST.value
    )
    assert news.stance is None
    assert news.conviction is None
    assert news.headline is None

    voices = [
        m for m in run.transcript
        if m.agent_id != AgentId.PORTFOLIO_MANAGER.value
    ]
    assert len(voices) == 11, "vacuity guard — the comb is 11 voices"
    stated = [m for m in voices if m.stance is not None]
    assert len(stated) == 10


def test_stances_are_frozen_into_the_journal_payload():
    """CR106 §3.4: the Journal board degrades per ENTRY, off this snapshot. A
    field absent from the payload is a comb that says 'not recorded' forever."""
    _, run = _run(silent_agent=AgentId.NEWS_ANALYST.value)
    entry = build_journal_entry_for_run(run, user_id=uuid4())
    rows = {r["agent_id"]: r for r in entry.payload["transcript"]}
    assert rows[AgentId.FUNDAMENTALS_ANALYST.value]["stance"] == "for"
    assert rows[AgentId.FUNDAMENTALS_ANALYST.value]["conviction"] == "high"
    assert rows[AgentId.NEWS_ANALYST.value]["stance"] is None


def test_the_scripted_demo_path_states_no_stance_rather_than_inventing_one():
    """No LLM ran, so nobody took a position. The board must say so."""
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
    assert all(m.stance is None for m in run.transcript)
