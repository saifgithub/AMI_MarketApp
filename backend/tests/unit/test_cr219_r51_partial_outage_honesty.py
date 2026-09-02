"""CR219 R51 — a Room that ran thin says so, and past a threshold stops deciding.

DEF059 fixed the TOTAL outage: provider unreachable -> PASS with an honest
reason, never a confident fake APPROVE. The PARTIAL case was silent, and silent
in the worst direction. `_compute_agent_text` substitutes a scripted
`_TEMPLATES` sentence per agent on timeout / error / empty response — a
complete, confident sentence populated with real computed figures and carrying
no mark — so a convene where most desks never answered still produced a full
transcript, a real verdict, and `status=COMPLETED`. DEF397 measured exactly
that: 6 of 10 agent calls returning 0 chars while the run banked clean.

**The counter-absence was re-verified at HEAD before this was written** (the WP
brief's instruction, and it held): `_scripted_for` had six call sites and no
caller counted them; `_pm_outage` covers only the CIO's OWN total outage
(DEF384); `is_llm_outage_verdict` is a CIO-liveness test keyed on
`PM_LLM_UNAVAILABLE_REASON`, which is set at exactly one site reached only when
the CIO's own stream is empty — so it answers nothing about the other eleven
desks, which is the seam DEF397 documents.

Three parts, tested at 0 / 2 / 4 scripted turns:

  1. COUNT   — `Verdict.scripted_turns` / `scripted_agents`.
  2. DISCLOSE — the user-visible sentence, naming AMI (house rule).
  3. CAP     — at/above `settings.room_max_scripted_turns` the verdict degrades
               to NO_VERDICT rather than standing as a confident call.

The end-to-end driver matters here and is not decoration: DEF241's mutation
proof showed that call-site bugs die only under a real `RoomRunner.run()`,
because a test that calls the builder directly proves the builder while saying
nothing about the caller — which is how DEF238 shipped a feature that never
worked once in production.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.core.config import settings as real_settings
from app.schemas.room import VerdictAction
from app.services import room_runner as room_runner_mod
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import (
    PM_ROOM_INCOMPLETE_REASON,
    RoomRunner,
    room_verdict_is_incomplete,
)

PM_JSON = (
    '{"action": "APPROVE", "size_pct": 3.0, "entry": 150, "stop": 141, '
    '"target": 172, "horizon_days": 42, '
    '"narration": "Synthesis defended; the mandate clears at this size."}'
)


class _PartialOutageGateway:
    """Answers the CIO properly and starves the first `fail_n` other desks.

    Starves by yielding NOTHING — the empty-stream path, which is the shape
    DEF397 measured in production (0-char responses at the timeout guard).
    """

    def __init__(self, fail_n: int):
        self.fail_n = fail_n
        self.failed = 0

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        if "speak as the chief investment officer" in system_prompt.lower():
            yield PM_JSON
            return
        if self.failed < self.fail_n:
            self.failed += 1
            return  # empty stream -> scripted fallback
        yield "AMI agent live reply with a real contribution."


def _run(fail_n, monkeypatch, cap=None):
    if cap is not None:
        monkeypatch.setattr(real_settings, "room_max_scripted_turns", cap)
        monkeypatch.setattr(room_runner_mod.settings, "room_max_scripted_turns", cap)
    gateway = _PartialOutageGateway(fail_n)
    runner = RoomRunner(llm=gateway)  # type: ignore[arg-type]

    async def go():
        return [ev async for ev in runner.run(
            user_id=uuid4(), ticker="AAPL",
            mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
            char_delay_min=0.0, char_delay_max=0.0,
        )]

    events = asyncio.run(go())
    verdicts = [ev for ev in events if ev.kind == "verdict"]
    assert len(verdicts) == 1
    return verdicts[0].verdict


# ── 0 scripted turns: the baseline is untouched ──────────────────────────────


def test_a_full_room_is_counted_as_zero_and_says_nothing(monkeypatch):
    """The no-op proof. A healthy convene must be byte-stable in its reason —
    a disclosure that fires on every run is noise the user learns to skip."""
    verdict = _run(0, monkeypatch, cap=4)
    assert verdict.scripted_turns == 0
    assert verdict.scripted_agents == []
    assert "desks responded" not in verdict.reason
    assert not room_verdict_is_incomplete(verdict.model_dump())
    assert verdict.action == VerdictAction.APPROVE


def test_zero_is_a_real_value_and_not_an_absence(monkeypatch):
    """CR040: `None` means "this run predates the field or was the scripted demo
    path"; a live run where every desk answered records `0`. Collapsing the two
    is how a fleet-wide outage would read as "no data on outages"."""
    verdict = _run(0, monkeypatch, cap=4)
    assert verdict.scripted_turns == 0
    assert verdict.scripted_turns is not None


# ── 2 scripted turns: disclosed, but the call still stands ───────────────────


def test_two_scripted_desks_are_counted_and_disclosed(monkeypatch):
    verdict = _run(2, monkeypatch, cap=4)
    assert verdict.scripted_turns == 2
    assert len(verdict.scripted_agents) == 2
    assert "desks responded" in verdict.reason
    assert "AMI filled the rest with standing guidance" in verdict.reason


def test_below_the_threshold_the_verdict_still_decides(monkeypatch):
    """Disclosure is not degradation. Two thin desks is worth telling the user
    about and is not, on its own, grounds to throw away a call the CIO made
    from nine live ones."""
    verdict = _run(2, monkeypatch, cap=4)
    assert verdict.action == VerdictAction.APPROVE
    assert verdict.size_pct == 3.0
    assert not room_verdict_is_incomplete(verdict.model_dump())


def test_the_disclosure_names_the_desks_that_did_not_answer(monkeypatch):
    """WHICH desk changes what the count means — a scripted Execution Desk makes
    the proposal the rest of the Room argued over itself canned. The names must
    travel with the verdict, not live only in container logs."""
    verdict = _run(2, monkeypatch, cap=4)
    for agent in verdict.scripted_agents:
        assert agent in ("fundamentals_analyst", "market_analyst",
                         "news_analyst", "social_media_analyst",
                         "bull_researcher", "bear_researcher",
                         "research_manager", "trader",
                         "aggressive_debator", "conservative_debator",
                         "neutral_debator"), agent
    # and at least one of them is named in the sentence the user reads
    assert verdict.reason.count("(") >= 1


def test_the_denominator_is_stated_so_the_count_can_be_judged(monkeypatch):
    """"3 desks were unavailable" gives the user nothing to weigh it against."""
    verdict = _run(2, monkeypatch, cap=4)
    assert " of " in verdict.reason.split("desks responded")[0]


# ── 4 scripted turns: at the threshold, the verdict degrades ─────────────────


def test_at_the_threshold_the_verdict_degrades_to_an_explicit_incomplete(monkeypatch):
    """DEF059's rule, extended from "no AMI" to "not enough AMI"."""
    verdict = _run(4, monkeypatch, cap=4)
    assert verdict.action == VerdictAction.NO_VERDICT
    assert verdict.reason.startswith(PM_ROOM_INCOMPLETE_REASON)
    assert room_verdict_is_incomplete(verdict.model_dump())
    assert verdict.overridden_from_llm is True


def test_the_degraded_verdict_carries_no_levels(monkeypatch):
    """A verdict AMI will not stand behind must not leave prices on the card for
    a to-scale risk/reward ribbon to draw."""
    verdict = _run(4, monkeypatch, cap=4)
    assert verdict.size_pct is None
    assert verdict.entry is None
    assert verdict.stop is None
    assert verdict.target is None
    assert verdict.time_horizon_days is None


def test_the_degrade_discards_the_call_rather_than_annotating_it(monkeypatch):
    """The gateway emitted a well-formed APPROVE. Leaving it in place with a
    caveat appended is exactly the confident-prose-plus-disclaimer shape CR040
    forbids, so the decision is thrown away, not footnoted."""
    verdict = _run(4, monkeypatch, cap=4)
    assert verdict.action != VerdictAction.APPROVE
    assert "desks responded" in verdict.reason  # still discloses why


def test_the_degraded_state_is_detectable_without_matching_prose(monkeypatch):
    """DEF336's lesson: an inline literal meant the only way to detect an
    outage verdict was to match prose, and a CR164 sweep recorded 450
    consecutive outage PASSes as a completed batch because nothing could."""
    thin = _run(4, monkeypatch, cap=4)
    healthy = _run(0, monkeypatch, cap=4)
    assert room_verdict_is_incomplete(thin.model_dump())
    assert not room_verdict_is_incomplete(healthy.model_dump())
    assert not room_verdict_is_incomplete(None)
    assert not room_verdict_is_incomplete({})


def test_it_stays_distinguishable_from_cr098s_withheld_no_verdict(monkeypatch):
    """NO_VERDICT is also the tenure-pull-back state. Two different things that
    render the same action must not become one thing."""
    thin = _run(4, monkeypatch, cap=4)
    assert thin.action == VerdictAction.NO_VERDICT
    assert room_verdict_is_incomplete(thin.model_dump())
    # A CR098 withheld verdict carries the pull-back reason, not this sentinel.
    assert not room_verdict_is_incomplete(
        {"action": "NO_VERDICT", "reason": "Market analyst withheld this run."}
    )


# ── the threshold is a knob, and 0 turns the degrade off ─────────────────────


def test_the_threshold_is_read_from_config_not_hardcoded(monkeypatch):
    """At cap=2 the same two-desk run that stood above now degrades."""
    verdict = _run(2, monkeypatch, cap=2)
    assert verdict.action == VerdictAction.NO_VERDICT
    assert room_verdict_is_incomplete(verdict.model_dump())


def test_a_zero_threshold_disables_the_degrade_but_never_the_disclosure(monkeypatch):
    """Counting and telling the user are not the part that needs an off switch."""
    verdict = _run(4, monkeypatch, cap=0)
    assert verdict.action == VerdictAction.APPROVE
    assert verdict.scripted_turns == 4
    assert "desks responded" in verdict.reason


def test_the_default_threshold_is_the_wp_proposal():
    assert real_settings.room_max_scripted_turns == 4


# ── house rules ──────────────────────────────────────────────────────────────


def test_the_user_visible_copy_says_ami_and_never_the_llm(monkeypatch):
    for fail_n in (2, 4):
        reason = _run(fail_n, monkeypatch, cap=4).reason
        assert "AMI" in reason
        for banned in ("the LLM", "the AI", "the model", "LLM"):
            assert banned not in reason, (fail_n, banned)


def test_the_scripted_demo_path_is_not_reported_as_an_outage():
    """Every turn is scripted there by design and nothing degraded. Reporting it
    would fire "N of 12 desks did not respond" on a run with no provider
    configured at all — a different, already-disclosed state."""
    runner = RoomRunner()  # no real provider

    async def go():
        return [ev async for ev in runner.run(
            user_id=uuid4(), ticker="AAPL",
            mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
            char_delay_min=0.0, char_delay_max=0.0,
        )]

    verdict = [ev for ev in asyncio.run(go()) if ev.kind == "verdict"][0].verdict
    assert verdict.scripted_turns is None
    assert verdict.scripted_agents == []
    assert "desks responded" not in verdict.reason
