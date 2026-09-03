"""CR201 — the structured Risk Officer replaces the three-call risk debate.

One internal `risk_officer` LLM call emits JSON sized options; the three risk
debator AgentIds still render — from that payload, in code, with no further LLM
calls. Measured equivalent (CR197 arm v8): 22 approvals vs the debate's 22,
net 0 verdicts changed, p=1.0 over 136 replayed convenes.

What this file pins, per flag state:

  * **Flag OFF (default)** — the debate path is untouched: three sequential
    debator LLM calls, stance envelopes asked for and parsed, no officer prompt
    ever built. The DEF251-class regression check.
  * **Flag ON** — the three rendered turns reach the transcript, the SSE
    stream and the comb channels (stance / conviction / argued_size_pct traced
    to the payload), every FIGURE comes from the `risk_debator_sizes` ladder
    and never from the payload (an invented size is dropped, a skipped rung
    says "did not assess"), the one call is attributable
    (`flow="room_risk_officer"`), and failure degrades to the ladder alone
    WITH an `[AMI …]` transcript mark (CR040) — the measured 11.8% floor, not
    a silent outage.
  * **Identity** — `risk_officer` is the 14th internal id, outside
    `TWELVE_AGENT_IDS` and every display map (D-012's twelve roles untouched,
    the CONCIERGE precedent); `agent_display_name()` raises on it, and it
    never surfaces in an event or a transcript entry.

The call-count/ordering invariant itself ("exactly one officer call, before
any turn is appended") lives with the guard it re-authors, in
`test_cr077_phase_parallelism.py`.
"""

from __future__ import annotations

import asyncio
import json
import re
from uuid import uuid4

import pytest

from app.schemas import (
    AGENT_DISPLAY_NAMES,
    AGENT_FAMILIES,
    AGENT_ROLE_COLORS,
    TWELVE_AGENT_IDS,
    AgentId,
    agent_display_name,
)
from app.schemas.mandate import Plan
from app.services import room_runner as rr_mod
from app.services.coach_engine import hydrate_coach_mandate
from app.services.risk_officer import (
    RISK_TURN_ORDER,
    render_officer_turns,
)
from app.services.room_prompts import (
    STANCE_HEADLINE_MAX_CHARS,
    build_risk_officer_messages,
    max_tokens_for,
)
from app.services.room_runner import RoomRunner
from app.services.tier_policy import pick_tier
from app.trading_math.option_ladder import build_option_ladder

_RISK_VOICES = (
    AgentId.AGGRESSIVE_DEBATOR,
    AgentId.CONSERVATIVE_DEBATOR,
    AgentId.NEUTRAL_DEBATOR,
)


# ── Renderer: three turns from one payload, ladder figures only ──────────────


@pytest.fixture
def rows():
    # reference 3.0 → rungs 1.5 (trim) / 3.0 (reference) / 5.0 (press)
    return build_option_ladder(
        reference_size_pct=3.0, entry=100.0, stop=94.0, target=113.0,
        cap_pts=30.0, current_drawdown_pct=0.0,
    )


def _payload(sizes=(1.5, 3.0, 5.0), **kw):
    p = {
        "options": [
            {
                "size_pct": s,
                "case_for": f"for-{s}",
                "case_against": f"against-{s}",
                "key_number": f"kn-{s}",
            }
            for s in sizes
        ],
        "recommended": 3.0,
        "confidence": "medium",
        # CR219 R59-F2: a genuine quotation, not a placeholder.
        # `render_officer_turns` now checks `key_number`/`decisive_number`
        # against the sheet/ladder before rendering them — "0.18" is the
        # reference rung's OWN `contribution_pts` for this fixture's ladder
        # (reference_size_pct 3.0, entry 100/stop 94/target 113, cap_pts
        # 30.0), so it is a figure the officer is actually entitled to cite,
        # not an unquotable one that would now render struck and demoted from
        # the headline slot.
        "decisive_number": "0.18",
    }
    p.update(kw)
    return p


def _render(payload, rows, fallback_reason=None):
    return render_officer_turns(
        payload, rows,
        headline_max_chars=STANCE_HEADLINE_MAX_CHARS,
        fallback_reason=fallback_reason,
    )


def test_three_turns_in_phase_order_one_rung_each(rows):
    turns = _render(_payload(), rows)
    assert [t.agent_id for t in turns] == list(RISK_TURN_ORDER)
    by_id = {t.agent_id: t for t in turns}
    # Each voice keeps its historical meaning: Aggressive presents the press
    # rung, Conservative the trim, Balanced the reference.
    assert by_id[AgentId.AGGRESSIVE_DEBATOR].argued_size_pct == 5.0
    assert by_id[AgentId.CONSERVATIVE_DEBATOR].argued_size_pct == 1.5
    assert by_id[AgentId.NEUTRAL_DEBATOR].argued_size_pct == 3.0
    for t in turns:
        assert f"{t.argued_size_pct:.1f}%" in t.text


def test_stance_and_conviction_trace_to_the_payload(rows):
    """The interim CR201 §2.3 mapping, measured-as-built (no `lean` — that is
    unmeasured and deliberately not shipped): the recommended rung's voice
    carries the officer's endorsement, the others neutral, conviction from
    `confidence` on all assessed voices."""
    turns = {t.agent_id: t for t in _render(_payload(), rows)}
    assert turns[AgentId.NEUTRAL_DEBATOR].stance == "for"
    assert turns[AgentId.AGGRESSIVE_DEBATOR].stance == "neutral"
    assert turns[AgentId.CONSERVATIVE_DEBATOR].stance == "neutral"
    assert all(t.conviction == "medium" for t in turns.values())


def test_figures_come_from_the_ladder_never_the_payload(rows):
    """CR201's structural closure of the DEF066→DEF235→DEF241→CR166-Tier-D
    class: a wrong contribution in the payload must be unrenderable."""
    payload = _payload()
    payload["options"][1]["contribution_pts"] = 99.9
    payload["options"][1]["headroom_after_pts"] = 77.7
    for t in _render(payload, rows):
        assert "99.9" not in t.text
        assert "77.7" not in t.text
    neu = next(t for t in _render(payload, rows)
               if t.agent_id is AgentId.NEUTRAL_DEBATOR)
    assert "0.18 pt of drawdown" in neu.text  # the ladder's own figure


def test_an_invented_size_is_dropped(rows):
    """A size nobody offered has no rung, so it has no voice, no text and no
    argued_size_pct — the unpriced-option smuggle is structurally closed."""
    turns = _render(_payload(sizes=(1.5, 3.0, 5.0, 12.0)), rows)
    assert len(turns) == 3
    for t in turns:
        assert "12.0" not in t.text
        assert t.argued_size_pct != 12.0


def test_a_skipped_rung_renders_did_not_assess_not_silence(rows):
    """Silence about a rung must read as silence. The voice still exists (the
    comb needs three), its figures still render from the ladder, and its stance
    is None — the gutter, never neutral."""
    turns = {t.agent_id: t for t in _render(_payload(sizes=(1.5, 3.0)), rows)}
    press = turns[AgentId.AGGRESSIVE_DEBATOR]
    assert "did not assess this size" in press.text
    assert "5.0%" in press.text
    assert press.stance is None and press.conviction is None
    assert press.argued_size_pct is None


def test_a_recommendation_off_the_ladder_earns_no_endorsement(rows):
    turns = _render(_payload(recommended=4.0), rows)
    assert all(t.stance != "for" for t in turns)
    assert all("4.0%" not in t.text for t in turns)


def test_the_balanced_voice_carries_the_call_and_the_open_menu_line(rows):
    neu = next(t for t in _render(_payload(), rows)
               if t.agent_id is AgentId.NEUTRAL_DEBATOR)
    assert "Risk Officer's call: **3.0%**" in neu.text
    assert "confidence medium" in neu.text
    assert "decided by 0.18" in neu.text
    assert "These are options, not instructions" in neu.text
    assert "safety floor" in neu.text


def test_headlines_are_capped_by_nulling_never_truncation(rows):
    payload = _payload()
    payload["options"][0]["key_number"] = "x" * (STANCE_HEADLINE_MAX_CHARS + 1)
    turns = {t.agent_id: t for t in _render(payload, rows)}
    assert turns[AgentId.CONSERVATIVE_DEBATOR].headline is None
    assert turns[AgentId.AGGRESSIVE_DEBATOR].headline == "kn-5.0"
    # The recommended rung's headline is the decisive number.
    assert turns[AgentId.NEUTRAL_DEBATOR].headline == "0.18"


def test_fallback_renders_the_ladder_alone_and_marks_every_turn(rows):
    """The designed degradation (measured floor 11.8% vs 7.4% for nothing):
    rung figures still render, nothing borrows a stance, and the transcript
    says out loud that the officer's reasoning is absent (CR040)."""
    turns = _render(None, rows, fallback_reason="no reply within 30s")
    assert len(turns) == 3
    for t in turns:
        assert "[AMI:" in t.text
        assert "no reply within 30s" in t.text
        assert (t.stance, t.conviction, t.headline, t.argued_size_pct) == (
            None, None, None, None,
        )
    assert "5.0%" in turns[0].text  # the ladder's sizes survive the degrade


def test_a_ladder_missing_a_voice_fails_loudly(rows):
    """Two voices where clients expect three is DEF084's shape — a ladder that
    stopped producing all three labelled rungs must raise, not render around."""
    with pytest.raises(ValueError, match="every voice"):
        _render(_payload(), rows[:2])


# ── Identity: the 14th id never reaches a user surface ───────────────────────


def test_risk_officer_is_outside_every_display_set():
    assert AgentId.RISK_OFFICER not in TWELVE_AGENT_IDS
    assert AgentId.RISK_OFFICER not in AGENT_DISPLAY_NAMES
    assert AgentId.RISK_OFFICER not in AGENT_FAMILIES
    assert AgentId.RISK_OFFICER not in AGENT_ROLE_COLORS
    assert len(TWELVE_AGENT_IDS) == 12  # D-012, untouched


def test_display_name_lookup_raises_loudly_on_the_internal_id():
    with pytest.raises(KeyError):
        agent_display_name(AgentId.RISK_OFFICER)


def test_tier_route_and_decode_budget_are_explicit():
    """The officer does the work of three agents and its output is PARSED, so
    it gets the Trader's routing, stated per plan; the budget is the CR179
    derivation in `room_prompts._AGENT_MAX_TOKENS` (censored 1200-token v8
    observation × 1.5)."""
    assert pick_tier(Plan.FLOOR_PASS, AgentId.RISK_OFFICER) == "cheap"
    assert pick_tier(Plan.TRIAL_TRADER, AgentId.RISK_OFFICER) == "mid"
    assert pick_tier(Plan.TRADER, AgentId.RISK_OFFICER) == "mid"
    assert pick_tier(Plan.FLOOR_MANAGER, AgentId.RISK_OFFICER) == "premium"
    assert max_tokens_for(AgentId.RISK_OFFICER) == 1800


# ── The prompt builder ───────────────────────────────────────────────────────


def _officer_prompt(**overrides):
    kwargs = dict(
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        ticker="MSFT",
        profile={"base_price": 100.0},
        transcript=[],
        trade_proposal={"size_pct": 3.0, "entry": 100.0, "stop": 94.0,
                        "target": 113.0},
        current_drawdown_pct=0.0,
    )
    kwargs.update(overrides)
    return build_risk_officer_messages(**kwargs)


def test_officer_prompt_carries_persona_ladder_and_json_contract():
    system, messages, rows = _officer_prompt()
    assert "one officer, not an advocate" in system
    assert "Sized options — AMI computed every figure below" in system
    assert "for these sizes and no others: 1.5, 3.0, 5.0" in system
    assert "Transcript so far:" in system
    # The three-debator machinery must NOT leak into the one-call contract.
    assert "[STANCE:" not in system
    assert "Speak as the" not in system
    assert [r.size_pct for r in rows] == [1.5, 3.0, 5.0]
    assert messages[0].content == "Assess risk on MSFT."


def test_officer_prompt_refuses_an_incoherent_reference_triple():
    """Degrade loudly (CR040): a ladder priced off stop ≥ entry would be a
    fabricated menu; the caller's designed fallback handles the refusal."""
    with pytest.raises(ValueError, match="coherent reference proposal"):
        _officer_prompt(trade_proposal={"size_pct": 3.0, "entry": 100.0,
                                        "stop": 105.0})


# ── The Room, end to end, both flag states ───────────────────────────────────


_CANNED = {
    "fundamentals_analyst": "FA: P/E reasonable, growth steady.",
    "market_analyst": "MA: trend consolidating, RSI 58.",
    "news_analyst": "NA: recent catalyst noted.",
    "social_media_analyst": "SMA: retail sentiment mixed.",
    "bull_researcher": "Bull: thesis defended, 4% size.",
    "bear_researcher": "Bear: compression risk capped at 2%.",
    "research_manager": "RM: lean constructive, 3% start.",
    "trader": "Trader: BUY 3% at $150, stop $141, target $172.",
    "aggressive_debator": "Push to 4.5%.",
    "conservative_debator": "Cap at 2%.",
    "neutral_debator": "Hold at 3%.",
    "portfolio_manager": (
        '{"action": "APPROVE", "size_pct": 3.0, "entry": 150, "stop": 141, '
        '"target": 172, "horizon_days": 42, '
        '"narration": "PM: APPROVE; synthesis defended; mandate clears."}'
    ),
}


def _echo_officer_reply(system_prompt: str) -> str:
    sizes = re.search(r"no others: ([0-9., ]+)\.", system_prompt)
    assert sizes, "officer prompt did not fix the candidate sizes"
    rungs = [float(s) for s in sizes.group(1).split(",")]
    return json.dumps({
        "options": [
            {"size_pct": s, "case_for": f"for-{s}",
             "case_against": f"against-{s}", "key_number": f"kn-{s}"}
            for s in rungs
        ],
        "recommended": rungs[1],
        "confidence": "high",
        "decisive_number": "RSI 58",
    })


class _Gateway:
    """Canned gateway: officer reply configurable, everything else canned."""

    def __init__(self, officer_reply=None, officer_delay_s: float = 0.0):
        self.officer_reply = officer_reply  # None → echo the prompt's rungs
        self.officer_delay_s = officer_delay_s
        self.officer_audits: list[dict] = []

    def has_real_provider(self) -> bool:
        return True

    def _match(self, system_prompt: str) -> str:
        low = system_prompt.lower()
        if "one officer, not an advocate" in low:
            return "risk_officer"
        for key in _CANNED:
            if f"speak as the {agent_display_name(key).lower()}" in low:
                return key
        return "portfolio_manager" if "single json object" in low else "default"

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **audit):
        key = self._match(system_prompt)
        if key == "risk_officer":
            self.officer_audits.append(dict(audit, max_tokens=max_tokens))
            if self.officer_delay_s:
                await asyncio.sleep(self.officer_delay_s)
            yield (self.officer_reply if self.officer_reply is not None
                   else _echo_officer_reply(system_prompt))
            return
        yield _CANNED.get(key, "AMI agent live reply.")


def _run_room(gw, monkeypatch=None, flag_on=True, **kw):
    if flag_on:
        assert monkeypatch is not None
        monkeypatch.setattr(rr_mod.settings, "room_risk_officer_enabled", True)
    runner = RoomRunner(llm=gw)  # type: ignore[arg-type]
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})

    async def go():
        out = []
        async for ev in runner.run(
            user_id=uuid4(), ticker="AAPL", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0, **kw,
        ):
            out.append(ev)
        return out, runner

    return asyncio.run(go())


def _risk_turns(runner, events):
    run = runner.get_run(events[0].run_id)
    return [m for m in run.transcript if AgentId(m.agent_id) in _RISK_VOICES]


def test_flag_on_the_three_voices_reach_transcript_stream_and_comb(monkeypatch):
    gw = _Gateway()
    events, runner = _run_room(gw, monkeypatch)

    # The one call is attributable next to the three it replaces.
    assert len(gw.officer_audits) == 1
    audit = gw.officer_audits[0]
    assert audit["audit_flow"] == "room_risk_officer"
    assert audit["audit_agent_id"] == "risk_officer"
    assert audit["max_tokens"] == max_tokens_for(AgentId.RISK_OFFICER)

    # Transcript: three turns, payload-traced comb channels, ladder sizes.
    turns = {AgentId(m.agent_id): m for m in _risk_turns(runner, events)}
    assert set(turns) == set(_RISK_VOICES)
    sizes = sorted(m.argued_size_pct for m in turns.values())
    assert sizes[0] < sizes[1] < sizes[2]  # trim < reference < press
    neu = turns[AgentId.NEUTRAL_DEBATOR]
    assert neu.stance == "for" and neu.conviction == "high"
    assert turns[AgentId.AGGRESSIVE_DEBATOR].stance == "neutral"
    assert "From the Risk Officer's structured assessment" in neu.content

    # SSE: agent_done still carries the comb fields for all three voices.
    done = {e.agent_id: e for e in events
            if e.kind == "agent_done" and e.agent_id in _RISK_VOICES}
    assert set(done) == set(_RISK_VOICES)
    for aid, ev in done.items():
        assert ev.argued_size_pct == turns[aid].argued_size_pct
        assert ev.stance == turns[aid].stance

    # A verdict still lands after the rendered debate.
    assert any(e.kind == "verdict" for e in events)


def test_flag_on_an_unparseable_officer_degrades_to_the_marked_ladder(monkeypatch):
    gw = _Gateway(officer_reply="I would rather write prose about risk.")
    events, runner = _run_room(gw, monkeypatch)
    turns = _risk_turns(runner, events)
    assert len(turns) == 3
    for m in turns:
        assert "[AMI:" in m.content and "could not be parsed" in m.content
        assert m.stance is None and m.argued_size_pct is None


def test_flag_on_a_timed_out_officer_degrades_to_the_marked_ladder(monkeypatch):
    gw = _Gateway(officer_delay_s=0.5)
    events, runner = _run_room(gw, monkeypatch, agent_timeout_s=0.05)
    turns = _risk_turns(runner, events)
    assert len(turns) == 3
    for m in turns:
        assert "[AMI:" in m.content and "no reply within" in m.content
        assert m.stance is None


def test_flag_on_an_invented_size_never_reaches_the_transcript(monkeypatch):
    def _with_invention(prompt):
        payload = json.loads(_echo_officer_reply(prompt))
        payload["options"].append({
            "size_pct": 12.0, "case_for": "for-12.0",
            "case_against": "against-12.0", "key_number": "kn-12.0",
        })
        return json.dumps(payload)

    gw = _Gateway()
    gw.officer_reply = None
    orig = _Gateway.stream_chat

    async def patched(self, *, system_prompt, **kw):
        if self._match(system_prompt) == "risk_officer":
            self.officer_reply = _with_invention(system_prompt)
        async for chunk in orig(self, system_prompt=system_prompt, **kw):
            yield chunk

    gw.stream_chat = patched.__get__(gw)
    events, runner = _run_room(gw, monkeypatch)
    turns = _risk_turns(runner, events)
    assert len(turns) == 3
    for m in turns:
        assert "12.0" not in m.content
        assert m.argued_size_pct != 12.0


def test_flag_on_risk_officer_never_surfaces(monkeypatch):
    gw = _Gateway()
    events, runner = _run_room(gw, monkeypatch)
    assert all(
        e.agent_id is not AgentId.RISK_OFFICER for e in events
    )
    run = runner.get_run(events[0].run_id)
    assert all(m.agent_id != "risk_officer" for m in run.transcript)


def test_flag_off_the_debate_path_is_todays_byte_for_byte():
    """The DEF251-class regression pin. With the flag at its default the officer
    branch is dead code by construction (`elif` on the flag): the three debators
    are each ASKED to speak (the "Speak as the …" turn line and the RISK stance
    envelope with its SIZE slot — today's prompt contract), their LLM text is
    what reaches the transcript, and no officer prompt is ever built. The
    call-order half of this pin lives in test_cr077_phase_parallelism."""
    prompts: dict[str, str] = {}
    gw = _Gateway()
    orig = _Gateway.stream_chat

    async def recording(self, *, system_prompt, **kw):
        prompts[self._match(system_prompt)] = system_prompt
        async for chunk in orig(self, system_prompt=system_prompt, **kw):
            yield chunk

    gw.stream_chat = recording.__get__(gw)
    events, runner = _run_room(gw, flag_on=False)

    assert "risk_officer" not in prompts
    for voice in _RISK_VOICES:
        prompt = prompts[voice.value]
        assert f"Speak as the {agent_display_name(voice)}" in prompt
        assert "SIZE: <n.n>%" in prompt  # today's envelope ask, untouched
    turns = {AgentId(m.agent_id): m for m in _risk_turns(runner, events)}
    assert turns[AgentId.AGGRESSIVE_DEBATOR].content == "Push to 4.5%."
    assert turns[AgentId.CONSERVATIVE_DEBATOR].content == "Cap at 2%."
    assert turns[AgentId.NEUTRAL_DEBATOR].content == "Hold at 3%."
