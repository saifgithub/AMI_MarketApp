"""CR077 Phase 2 — parallelise the ANALYSTS phase of the Room. CR201 re-authors
the RISK half of the guard for the officer path.

The spine of this file is the phase-parallelism GUARD (§Guard): the set of
phases marked `parallel=True` must be EXACTLY the phases whose agents do not
read each other's output — today `{ANALYSTS}`. The failure mode it exists to
catch is DEF084's exact shape: someone later marks RISK parallel because it
*looks* like three independent debators, silently deleting the risk debate
while every other test passes and the UI still renders three contributions.

That invariant now holds per flag state (CR201):

  * **Flag OFF (`ROOM_RISK_OFFICER_ENABLED=false`, the default)** — unchanged:
    RISK is a sequential three-call debate, and the static guards below stand
    exactly as CR077 wrote them.
  * **Flag ON** — the RISK phase is one compute step, and "don't silently
    delete the debate" is re-authored to the shape that can now fail silently:
    **the three risk turns are rendered from EXACTLY ONE officer call, and
    that call happens BEFORE any of them is appended.** Zero officer calls
    with three turns still rendering is the new DEF084 shape (the ladder-alone
    fallback running always, silently — a permanent degrade the UI cannot
    see); a turn appended before the call is presentation running ahead of the
    compute it claims to present; per-debator LLM calls reappearing is the old
    three-call debate quietly resurrected under the flag.

Both halves are proven non-vacuous the same way: mutate (a copy of PHASES /
a recorded call-commit sequence) into each regression's shape and assert the
invariant then fails — the "proven red before the fix" the assign requires.
Fix-until-green is forbidden here per CR201's row: this guard is the one thing
standing between "the debate exists" and "the UI renders something debate-like".

Beyond the static guard, this verifies against REAL convene output (GATE: D-5):
the four analyst calls actually run concurrently, and — whichever finishes
first — the emitted event order stays deterministic
(fundamentals → market → news → social), because the mobile client renders them
in a fixed order.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import re
from uuid import uuid4

import pytest

from app.schemas import AgentId, agent_display_name
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import (
    PHASES,
    RoomRunner,
    log_prefix_cache_status,
    parse_prefix_cache_metrics,
)
from app.services import room_runner as rr_mod
from app.services.room_prompts import build_room_messages


# The phases whose agents genuinely do NOT read each other's output. Written out
# here INDEPENDENTLY of the `parallel` flag so the guard is a real cross-check,
# not a tautology: ANALYSTS are four independent lenses on one shared data block
# (CR077 §Evidence); every other phase is a debate where a later turn answers an
# earlier one (RESEARCHERS: bear rebuts bull; RISK: three debators argue each
# other; VERDICT: PM weighs all 11) or is a lone agent that still reads the
# transcript (SYNTHESIS, EXECUTION).
_PHASES_WITH_INDEPENDENT_AGENTS = {"ANALYSTS"}


def _parallel_labels(phases) -> set[str]:
    return {p.label for p in phases if p.parallel}


# ── The guard (the deliverable's spine) ────────────────────────────────────


def test_parallel_phases_are_exactly_the_independent_phases():
    """§Guard: the phases marked parallel are EXACTLY the phases whose agents do
    not read each other's output. If a debate phase is ever marked parallel,
    this fails — the whole point (DEF084 shape: a feature that looks present and
    isn't)."""
    assert _parallel_labels(PHASES) == _PHASES_WITH_INDEPENDENT_AGENTS


def test_debate_phases_are_never_parallel():
    """The explicit half of the guard: name every debate phase and assert none
    is parallel. RESEARCHERS/RISK/VERDICT are the ones a future refactor is most
    likely to mis-mark because they LOOK like independent lists."""
    by_label = {p.label: p for p in PHASES}
    for label in ("RESEARCHERS", "SYNTHESIS", "EXECUTION", "RISK", "VERDICT"):
        assert by_label[label].parallel is False, f"{label} must stay sequential"


def test_guard_is_not_vacuous_marking_a_debate_phase_parallel_fails():
    """Proven-red: mutate a copy of PHASES to mark RISK parallel and assert the
    guard invariant then breaks. This demonstrates the guard actually catches the
    DEF084-shape regression rather than passing no matter what."""
    mutated = tuple(
        dataclasses.replace(p, parallel=True) if p.label == "RISK" else p
        for p in PHASES
    )
    assert _parallel_labels(mutated) != _PHASES_WITH_INDEPENDENT_AGENTS
    assert "RISK" in _parallel_labels(mutated)


# ── Real convene output: concurrency + deterministic order ─────────────────


_ANALYST_ORDER = (
    AgentId.FUNDAMENTALS_ANALYST,
    AgentId.MARKET_ANALYST,
    AgentId.NEWS_ANALYST,
    AgentId.SOCIAL_MEDIA_ANALYST,
)

# Delays chosen so completion order is the REVERSE of the required emit order:
# social (emitted last) finishes first, fundamentals (emitted first) finishes
# last. If emission ever tracked completion, the assertion below would flip.
_AGENT_DELAYS = {
    "fundamentals_analyst": 0.040,
    "market_analyst": 0.030,
    "news_analyst": 0.020,
    "social_media_analyst": 0.010,
}

_REPLIES = {
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


class _ConcurrencyProbeGateway:
    """Fake gateway that records max concurrent in-flight calls, the order calls
    complete in, and the system prompt each agent received. The per-agent sleep
    makes concurrency observable: run serially, max_in_flight would be 1."""

    def __init__(self):
        self.in_flight = 0
        self.max_in_flight = 0
        self.completion_order: list[str] = []
        self.prompts: dict[str, str] = {}

    def has_real_provider(self) -> bool:
        return True

    def _match(self, system_prompt: str) -> str:
        low = system_prompt.lower()
        for k in _REPLIES:
            if f"speak as the {agent_display_name(k).lower()}" in low:
                return k
        return "portfolio_manager" if "single json object" in low else "default"

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        key = self._match(system_prompt)
        self.prompts[key] = system_prompt
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(_AGENT_DELAYS.get(key, 0.0))
            text = _REPLIES.get(key, "AMI agent live reply.")
            mid = len(text) // 2
            yield text[:mid]
            yield text[mid:]
        finally:
            self.completion_order.append(key)
            self.in_flight -= 1


def _run(runner, **kw) -> list:
    async def go():
        out = []
        async for ev in runner.run(**kw):
            out.append(ev)
        return out
    return asyncio.run(go())


def test_analysts_run_concurrently_but_emit_in_fixed_order():
    gw = _ConcurrencyProbeGateway()
    runner = RoomRunner(llm=gw)  # type: ignore[arg-type]
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    events = _run(
        runner, user_id=uuid4(), ticker="AAPL", mandate=mandate,
        char_delay_min=0.0, char_delay_max=0.0,
    )

    # Concurrency actually happened: all four analysts were in-flight at once.
    # (A sequential loop would top out at 1.)
    assert gw.max_in_flight == 4

    # Completion order was the REVERSE of the emit order (social finished first).
    analyst_completions = [k for k in gw.completion_order if k in _AGENT_DELAYS]
    assert analyst_completions[0] == "social_media_analyst"
    assert analyst_completions[-1] == "fundamentals_analyst"

    # Despite that, the emitted agent_done order is the fixed render order.
    analyst_ids = {a for a in _ANALYST_ORDER}
    done_order = [e.agent_id for e in events
                  if e.kind == "agent_done" and e.agent_id in analyst_ids]
    assert done_order == list(_ANALYST_ORDER)

    # And tokens are grouped per agent in that same order — no interleaving
    # across agents within the phase (collect-then-emit-in-order).
    token_owner_sequence: list[AgentId] = []
    for e in events:
        if e.kind == "agent_token" and e.agent_id in analyst_ids:
            if not token_owner_sequence or token_owner_sequence[-1] != e.agent_id:
                token_owner_sequence.append(e.agent_id)
    assert token_owner_sequence == list(_ANALYST_ORDER)


def test_analysts_are_blind_to_each_other_but_downstream_sees_them_all():
    """§Build 4: each concurrent analyst sees the transcript as of phase START
    (empty — ANALYSTS is first), so no analyst's prompt contains another
    analyst's contribution. But after the phase, all four are committed, so the
    Bull Researcher (next phase) sees every one of them."""
    gw = _ConcurrencyProbeGateway()
    runner = RoomRunner(llm=gw)  # type: ignore[arg-type]
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    _run(runner, user_id=uuid4(), ticker="AAPL", mandate=mandate,
         char_delay_min=0.0, char_delay_max=0.0)

    # No analyst's prompt carries another analyst's reply text.
    other_replies = {k: v for k, v in _REPLIES.items() if k in _AGENT_DELAYS}
    for me in _AGENT_DELAYS:
        prompt = gw.prompts[me]
        for other, reply in other_replies.items():
            if other == me:
                continue
            assert reply not in prompt, f"{me} saw {other}'s contribution"

    # The Bull Researcher (RESEARCHERS, next phase) sees ALL four analysts.
    bull_prompt = gw.prompts["bull_researcher"]
    for reply in other_replies.values():
        assert reply in bull_prompt


# ── §Build 5: the "build on the transcript" line is rescoped when parallel ──


def test_parallel_phase_rescopes_the_build_on_transcript_line():
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    profile = {"base_price": 100.0, "pe": "20.0", "rev_growth": 10,
               "profit_margin": 15}

    seq_prompt, _ = build_room_messages(
        agent_id=AgentId.FUNDAMENTALS_ANALYST, mandate=mandate, ticker="AAPL",
        profile=profile, transcript=[], parallel_phase=False,
    )
    par_prompt, _ = build_room_messages(
        agent_id=AgentId.FUNDAMENTALS_ANALYST, mandate=mandate, ticker="AAPL",
        profile=profile, transcript=[], parallel_phase=True,
    )

    # Sequential keeps the load-bearing line; parallel drops it for the honest,
    # own-domain rescope.
    assert "Build on the transcript" in seq_prompt
    assert "Build on the transcript" not in par_prompt
    assert "AT THE SAME TIME" in par_prompt
    assert "own domain" in par_prompt.lower()


# ── CR201: the RISK invariant, re-authored for the flag-ON officer path ──────
#
# "Exactly one officer call, before any risk turn is appended." Checked over a
# recorded sequence of gateway calls and transcript commits, so the invariant is
# a function of what actually happened — not of code structure that a refactor
# can hollow out while every test passes.

_RISK_VOICES = ("aggressive_debator", "conservative_debator", "neutral_debator")


def _officer_risk_invariant(sequence: list[str]) -> bool:
    """True iff the sequence shows the CR201 flag-ON contract held.

    `sequence` entries: `"llm:<agent-key>"` when a gateway call starts,
    `"commit:<agent-id>"` when a turn is committed to the transcript.
    """
    officer_calls = [i for i, s in enumerate(sequence) if s == "llm:risk_officer"]
    debator_calls = [s for s in sequence if s in {f"llm:{v}" for v in _RISK_VOICES}]
    risk_commits = [
        i for i, s in enumerate(sequence) if s in {f"commit:{v}" for v in _RISK_VOICES}
    ]
    return (
        len(officer_calls) == 1
        and not debator_calls
        and len(risk_commits) == 3
        and officer_calls[0] < min(risk_commits)
    )


class _OfficerProbeGateway(_ConcurrencyProbeGateway):
    """The concurrency probe, plus a call/commit sequence log and a structured
    officer reply whose sizes are read from the officer's own prompt — so the
    fake echoes exactly the rungs production offered, whatever the mandate."""

    def __init__(self):
        super().__init__()
        self.sequence: list[str] = []

    def _match(self, system_prompt: str) -> str:
        if "one officer, not an advocate" in system_prompt.lower():
            return "risk_officer"
        return super()._match(system_prompt)

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        key = self._match(system_prompt)
        self.sequence.append(f"llm:{key}")
        if key == "risk_officer":
            self.prompts[key] = system_prompt
            sizes = re.search(r"no others: ([0-9., ]+)\.", system_prompt)
            assert sizes, "officer prompt did not fix the candidate sizes"
            rungs = [float(s) for s in sizes.group(1).split(",")]
            reply = json.dumps({
                "options": [
                    {"size_pct": s, "case_for": f"for-{s}",
                     "case_against": f"against-{s}", "key_number": f"kn-{s}"}
                    for s in rungs
                ],
                "recommended": rungs[1],
                "confidence": "medium",
                "decisive_number": "RSI 43",
            })
            yield reply
            return
        async for chunk in super().stream_chat(
            system_prompt=system_prompt, messages=messages,
            model_tier=model_tier, locale=locale, max_tokens=max_tokens,
        ):
            yield chunk


def _run_flag_on(monkeypatch) -> tuple[_OfficerProbeGateway, list]:
    gw = _OfficerProbeGateway()
    monkeypatch.setattr(rr_mod.settings, "room_risk_officer_enabled", True)
    # Commits observed at the one place every turn passes through on its way
    # into the transcript (`_stream_agent_text` → `_checkpoint_run`).
    real_checkpoint = rr_mod._checkpoint_run

    def _recording_checkpoint(run):
        if run.transcript:
            gw.sequence.append(f"commit:{run.transcript[-1].agent_id.value}")
        return real_checkpoint(run)

    monkeypatch.setattr(rr_mod, "_checkpoint_run", _recording_checkpoint)
    runner = RoomRunner(llm=gw)  # type: ignore[arg-type]
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    events = _run(
        runner, user_id=uuid4(), ticker="AAPL", mandate=mandate,
        char_delay_min=0.0, char_delay_max=0.0,
    )
    return gw, events


def test_flag_on_exactly_one_officer_call_before_any_risk_turn(monkeypatch):
    """The re-authored guard, on real convene output: one `risk_officer` gateway
    call, zero debator calls, three risk turns committed — and the call strictly
    precedes the first of them."""
    gw, events = _run_flag_on(monkeypatch)
    assert _officer_risk_invariant(gw.sequence), gw.sequence

    # The three voices still reach the stream, in the fixed phase order, and
    # the internal identity never surfaces as an event.
    risk_done = [e.agent_id.value for e in events
                 if e.kind == "agent_done" and e.agent_id.value in _RISK_VOICES]
    assert risk_done == list(_RISK_VOICES)
    assert all(
        e.agent_id is None or e.agent_id.value != "risk_officer" for e in events
    ), "risk_officer leaked into the event stream"


def test_flag_on_guard_is_not_vacuous_each_regression_shape_fails():
    """Proven-red, same discipline as the static guard above: take the real
    passing sequence's shape and mutate it into each regression this invariant
    exists to catch. A detector that stays green through any of these is
    vacuous, and per CR201's row that is a hard acceptance failure."""
    good = [
        "llm:trader", "commit:trader",
        "llm:risk_officer",
        "commit:aggressive_debator", "commit:conservative_debator",
        "commit:neutral_debator",
    ]
    assert _officer_risk_invariant(good)

    # (a) Officer call deleted while the turns still render — the fallback
    # running always and silently; the UI cannot tell (DEF084's shape).
    no_call = [s for s in good if s != "llm:risk_officer"]
    assert not _officer_risk_invariant(no_call)

    # (b) A turn appended BEFORE the call — presentation ahead of the compute.
    early_turn = [
        "llm:trader", "commit:trader",
        "commit:aggressive_debator",
        "llm:risk_officer",
        "commit:conservative_debator", "commit:neutral_debator",
    ]
    assert not _officer_risk_invariant(early_turn)

    # (c) The three-call debate quietly resurrected under the flag.
    debate_back = good + ["llm:aggressive_debator"]
    assert not _officer_risk_invariant(debate_back)

    # (d) Two officer calls — "exactly one" is the cost contract.
    double_call = good + ["llm:risk_officer"]
    assert not _officer_risk_invariant(double_call)

    # (e) A voice silently dropped — three turns is the display contract.
    two_turns = [s for s in good if s != "commit:neutral_debator"]
    assert not _officer_risk_invariant(two_turns)


def test_flag_off_risk_phase_is_unchanged_three_debator_calls_no_officer():
    """The OTHER half of the re-authored guard: with the flag at its default,
    the debate path must be exactly today's — three sequential debator LLM
    calls, no officer call, no officer prompt ever built."""
    gw = _OfficerProbeGateway()
    runner = RoomRunner(llm=gw)  # type: ignore[arg-type]
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    _run(runner, user_id=uuid4(), ticker="AAPL", mandate=mandate,
         char_delay_min=0.0, char_delay_max=0.0)
    llm_calls = [s for s in gw.sequence if s.startswith("llm:")]
    assert "llm:risk_officer" not in llm_calls
    assert [s for s in llm_calls if s in {f"llm:{v}" for v in _RISK_VOICES}] == [
        f"llm:{v}" for v in _RISK_VOICES
    ]


# ── Second guard: prefix-cache observability ───────────────────────────────


_METRICS_ON = (
    '# HELP vllm:cache_config_info Cache config\n'
    'vllm:cache_config_info{block_size="2096",enable_prefix_caching="True"} 1.0\n'
    'vllm:prefix_cache_queries_total{model="ami-llm"} 1000.0\n'
    'vllm:prefix_cache_hits_total{model="ami-llm"} 337.0\n'
)

_METRICS_OFF = (
    'vllm:cache_config_info{block_size="2096",enable_prefix_caching="False"} 1.0\n'
    'vllm:prefix_cache_queries_total 10.0\n'
    'vllm:prefix_cache_hits_total 0.0\n'
)


def test_parse_prefix_cache_metrics_on():
    stats = parse_prefix_cache_metrics(_METRICS_ON)
    assert stats["enabled"] is True
    assert stats["hits"] == 337.0
    assert stats["queries"] == 1000.0
    assert abs(stats["hit_rate"] - 0.337) < 1e-6


def test_parse_prefix_cache_metrics_off_is_detected():
    """The guard's teeth: caching switched off is reported as a hard False, which
    log_prefix_cache_status turns into a loud ERROR — nobody silently loses it."""
    stats = parse_prefix_cache_metrics(_METRICS_OFF)
    assert stats["enabled"] is False


def test_parse_prefix_cache_metrics_absent_is_unconfirmed():
    stats = parse_prefix_cache_metrics("vllm:some_other_metric 1.0\n")
    assert stats["enabled"] is None
    assert stats["hit_rate"] is None


def test_log_prefix_cache_status_noops_without_a_host(monkeypatch):
    """On the mock/anthropic path (no vllm_base_url) the probe must do nothing —
    no network, no crash. Unit tests run exactly here."""
    monkeypatch.setattr(rr_mod.settings, "vllm_base_url", "", raising=False)
    monkeypatch.setattr(rr_mod, "_PREFIX_CACHE_STATUS_LOGGED", False, raising=False)
    log_prefix_cache_status()  # must not raise
