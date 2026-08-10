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


# ── DEF147 — the malformed envelope ──────────────────────────────────────
#
# Every fixture above is well-formed, which is exactly why the defect shipped.
# The tail the model actually writes is not the tail the prompt asked for: on
# live Alpha 3 of 11 agents (27%) produced one this parser had rejected, and
# because ONE regex did both the parse and the strip, each of those was a null
# stance AND raw machine syntax on the user's screen at the same time. The two
# jobs are now separate, and these fixtures are the shapes that were measured
# leaking, verbatim.


_UNTERMINATED = "[STANCE: against | CONVICTION: medium | HEADLINE: 6-day binary"
_UNBRACKETED = "STANCE: against | CONVICTION: medium | HEADLINE: 40.2x P/E]"


def test_an_unterminated_envelope_is_stripped_and_still_read():
    """`conservative_debator` on run bd31e46a: cut off before the closing
    bracket. Under the old regex it was neither read nor removed."""
    body, env = parse_stance_envelope(f"{_PROSE}\n{_UNTERMINATED}")
    assert env.stance == "against"
    assert env.conviction == "medium"
    assert env.headline == "6-day binary"
    assert body == _PROSE
    assert "STANCE" not in body


def test_an_unbracketed_envelope_is_stripped_and_still_read():
    """`fundamentals_analyst` on the same run: the opening bracket never came."""
    body, env = parse_stance_envelope(f"{_PROSE}\n{_UNBRACKETED}")
    assert env.stance == "against"
    assert env.headline == "40.2x P/E"
    assert body == _PROSE
    assert "STANCE" not in body


def test_an_envelope_that_parses_to_nothing_is_still_stripped():
    """The decoupling itself, stated as a rule: the user must not read the
    machine channel REGARDLESS of what the parser made of it. A tail this
    mangled yields no stance — that part is honest and unchanged — but it
    still comes off the prose."""
    for mangled in ("[STANCE:", "[STANCE: ", "STANCE: |", "[ stance : ??? |"):
        body, env = parse_stance_envelope(f"{_PROSE}\n{mangled}")
        assert env.stance is None, mangled
        assert body == _PROSE, mangled
        assert "STANCE" not in body.upper(), mangled


def test_one_mangled_field_costs_one_field_not_three():
    """Per-field parsing. A truncation that ate the headline leaves the stance
    standing — the old all-or-nothing match threw away everything the agent
    did manage to say."""
    _, env = parse_stance_envelope(f"{_PROSE}\n[STANCE: for | CONVICTION: hi")
    assert env.stance == "for"
    assert env.conviction is None, "'hi' is not a conviction value"
    assert env.headline is None


# ── DEF147 — the envelope now leads the turn ─────────────────────────────


def test_the_envelope_may_lead_the_turn():
    body, env = parse_stance_envelope(
        f"[STANCE: for | CONVICTION: high | HEADLINE: FCF 6.2%]\n{_PROSE}"
    )
    assert env.stance == "for"
    assert env.headline == "FCF 6.2%"
    assert body == _PROSE


def test_a_leading_envelope_survives_the_truncation_that_used_to_eat_it():
    """The whole point of the move. A length-stopped turn now loses prose —
    which degrades gracefully and DEF125 already marks — instead of the
    structured field the entire Verdict Board is built on."""
    body, env = parse_stance_envelope(
        "[STANCE: against | CONVICTION: high | HEADLINE: Debt/EBITDA 4.1x]\n"
        "The leverage is the whole story and the buyback pace of **3"
    )
    assert env.stance == "against"
    assert env.conviction == "high"
    assert body.endswith("**3")


def test_an_envelope_at_both_ends_is_stripped_at_both_ends():
    """Belt and braces while the prompt change lands: a model that obeys the
    new instruction and then repeats the old habit must not leak the repeat."""
    body, env = parse_stance_envelope(
        "[STANCE: for | CONVICTION: high | HEADLINE: FCF 6.2%]\n"
        f"{_PROSE}\n"
        "[STANCE: against | CONVICTION: low | HEADLINE: elsewhere]"
    )
    assert env.stance == "for", "the instructed slot wins"
    assert env.headline == "FCF 6.2%"
    assert body == _PROSE
    assert "STANCE" not in body


def test_a_stance_line_mid_argument_is_the_machine_channel_after_all():
    """REVERSED by DEF247, and the reversal is the finding.

    This test used to assert the opposite — that the search stays bounded to the
    first and last non-blank lines, because "an agent quoting the format
    mid-paragraph is writing prose about it". That was a hypothesis, and the
    corpus does not support it. Of 11,057 stored agent turns, 57 carry a
    line-anchored `STANCE:` past the first line; 15 of those sit genuinely
    mid-turn, and **all 15 are the machine channel**, every one of them preceded
    by exactly one conversational opener the model wrote despite the prompt:

        I'd argue for wait
        [STANCE: against | CONVICTION: high | HEADLINE: 0% profit margin]

    Not one is an agent discussing the format. So the bound was protecting a
    shape that has never occurred while leaking a shape that occurs at a
    measurable rate — 3 of 9 debator turns on the 2026-08-09 batch, and
    instances back to 2026-07-29, well before DEF243 touched these prompts.

    The concern the old test encoded is real and is not dropped: prose must not
    be eaten. It is now carried by the fixture that actually exercises it —
    `test_only_a_trailing_envelope_is_read` above, and DEF247's own
    `test_a_bracketed_aside_inside_a_sentence_is_still_prose` — because an aside
    inside a sentence is not a line that opens with `STANCE:`, and it is
    `_STANCE_LINE_RE`'s anchor, not the position bound, that always kept it out.
    """
    text = "First.\n[STANCE: for | CONVICTION: high | HEADLINE: quoted]\nLast."
    body, env = parse_stance_envelope(text)
    assert env.stance == "for"
    assert "STANCE" not in body
    assert body == "First.\nLast."


def test_the_prompt_asks_for_the_envelope_first_not_last():
    for agent in [a for a in AgentId if a != AgentId.PORTFOLIO_MANAGER][:11]:
        prompt = _system_prompt_for(agent)
        assert "VERY FIRST line" in prompt, agent.value
        assert "Do not repeat it at the end." in prompt, agent.value
        assert "After your prose, end with" not in prompt, agent.value


# ── DEF147 — end to end, with the shapes that leaked ─────────────────────


class _MalformedStanceGateway:
    """Answers with a LEADING envelope, malformed the way live Alpha's were."""

    def __init__(self, body: str = "The case holds on **6.2%** FCF yield.") -> None:
        self._body = body

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
        yield f"{_UNTERMINATED}\n{self._body}" if self._body else _UNTERMINATED


def _run_malformed(body: str = "The case holds on **6.2%** FCF yield."):
    runner = RoomRunner(llm=_MalformedStanceGateway(body))  # type: ignore[arg-type]
    events = _collect(runner.run(
        user_id=uuid4(),
        ticker="AAPL",
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        char_delay_min=0.0,
        char_delay_max=0.0,
    ))
    return runner.get_run(events[0].run_id)


def test_no_malformed_envelope_reaches_the_transcript_or_the_next_agent():
    """Platinum Anchor's report, as an assertion. The transcript is both what
    the user reads and what the following ten agents reason from, so a leak
    here is a leak twice (DEF095)."""
    run = _run_malformed()
    voices = [
        m for m in run.transcript
        if m.agent_id != AgentId.PORTFOLIO_MANAGER.value
    ]
    assert len(voices) == 11, "vacuity guard — the comb is 11 voices"
    for m in voices:
        assert "STANCE" not in m.content.upper(), m.agent_id
        assert m.stance == "against", m.agent_id
        assert m.headline == "6-day binary", m.agent_id


def test_an_envelope_with_no_prose_after_it_is_never_a_blank_contribution():
    """New edge opened by the move to the front: a generation that stops right
    after the envelope leaves nothing to render. It takes the same fallback an
    empty stream already takes — the stance still parsed, so it is kept."""
    run = _run_malformed(body="")
    voices = [
        m for m in run.transcript
        if m.agent_id != AgentId.PORTFOLIO_MANAGER.value
    ]
    assert len(voices) == 11, "vacuity guard"
    for m in voices:
        assert m.content.strip(), m.agent_id
        assert "STANCE" not in m.content.upper(), m.agent_id
        assert m.stance == "against", m.agent_id
