"""DEF241 + DEF243 — the two defects the three RISK debators shared, fixed together.

They ship as one change because they touch the same three prompts, and a prompt
edit whose effect is not re-measured on the same promotion is the CR105
Amendment-1 trap.

DEF241 — every debator was told to argue a position size it was never given, and
then asked to quantify what that position does to the drawdown cap. Measured over
the 2026-08-07 epoch the Conservative stated a cap-consumption figure in 9 of 18
turns and 4 were wrong; the Bull stated 33 pt where the truth was 48.3 of a 50 pt
cap and closed with "stays within the safety floor". Nothing checks any of it:
`_verify_and_annotate_geometry` needs a full entry/stop/target triple and fires
0/18 on these agents. `failure_patterns` P5, and DEF066's third appearance.

DEF243 — `_STANCE_FORMAT` demands the envelope on the VERY FIRST line while each
debator's base prompt said "Open with: …". The model obeyed both, the envelope
landed on line 2, and `parse_stance_envelope` (which by design inspects only the
first and last non-blank line) neither read nor stripped it: 10 of 54 debator
turns lost their stance against 0 of 144 for the eight prose agents with no such
line.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas.agents import AgentId
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_prompts import build_room_messages
from app.trading_math.risk import drawdown_contribution

_CONTENT = Path(__file__).resolve().parents[3] / "content" / "agents"
_DEBATORS = (
    (AgentId.AGGRESSIVE_DEBATOR, "aggressive_debator.md"),
    (AgentId.CONSERVATIVE_DEBATOR, "conservative_debator.md"),
    (AgentId.NEUTRAL_DEBATOR, "neutral_debator.md"),
)
# The reference proposal the RISK phase carries: 3.0% at the risk-tier ceiling.
_PROPOSAL = {"size_pct": 3.0, "entry": 100.0, "stop": 94.0}


def _prompt(agent_id: AgentId, *, size: float | None) -> str:
    system, _msgs = build_room_messages(
        agent_id=agent_id,
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        user_id=None,
        ticker="MSFT",
        profile={"base_price": 100.0},
        transcript=[],
        trade_proposal=_PROPOSAL,
        agent_size_pct=size,
    )
    return system


# ── DEF241 ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("agent_id,_f", _DEBATORS)
def test_def241_a_debator_is_handed_its_own_positions_drawdown(agent_id, _f):
    """The figure must be for the size THIS role argues, computed by AMI.

    Asserting the VALUE, not the label: a substring check for "contribution" is
    what let DEF235 ship 11.32 pt for a true 0.18 pt.
    """
    # 5.0% at a 6.0% stop distance (100 → 94) = 0.30 pt.
    prompt = _prompt(agent_id, size=5.0)
    expected = drawdown_contribution(5.0, 100.0, 94.0)
    assert expected is not None and round(expected.contribution_pts, 2) == 0.30
    assert "YOUR position — the size YOUR role argues for (5.0%)" in prompt
    assert "contribution ≈ 0.30 pt" in prompt
    assert "AMI computed this" in prompt


def test_def241_the_figure_tracks_the_size_it_is_given():
    """A second size must move the number — otherwise the test pins a constant
    rather than the computation (the mutation that survived DEF235's first pass).
    """
    assert "contribution ≈ 0.09 pt" in _prompt(AgentId.CONSERVATIVE_DEBATOR, size=1.5)
    assert "contribution ≈ 0.30 pt" in _prompt(AgentId.AGGRESSIVE_DEBATOR, size=5.0)


def test_cr166_own_figure_is_given_even_when_the_size_equals_the_reference():
    """CR166 Tier D — RETIRES the DEF241 carve-out this test used to assert.

    The original assertion, and its reasoning, kept verbatim because the
    tradeoff it names is real and a future reader may want to reverse this:

        "The reference position already states 3.0%; repeating it as 'YOUR
        position' is noise, and noise in a mandate snapshot is how agents learn
        to skim it."

    What killed it was evidence, not taste. On the AAPL run of 2026-08-11 10:46
    UTC the Aggressive debator argued the 3.0% ceiling with a 6.0% stop and
    stated a "0.30 pt" drawdown contribution; the reference line in its own
    prompt said 0.18, and the Conservative (1.5%, off-ceiling, so it DID get the
    YOUR-position line) and the Neutral both quoted 0.18 correctly. That is
    DEF066's class a fourth time — DEF066 the formula, DEF235 the parser feeding
    it, DEF241 the agent doing it in prose, this the agent the DEF241 guard
    deliberately skipped.

    Reading a figure off a line addressed to "the reference position" is not the
    same act as reading one addressed to YOU. The cost is one redundant line for
    whichever agent sits at the ceiling; the benefit is that no agent is left to
    infer that the reference figure is also its own.
    """
    prompt = _prompt(AgentId.NEUTRAL_DEBATOR, size=3.0)
    # Match the rendered SNAPSHOT line, not the phrase — the role-guidance block
    # legitimately says "YOUR position" too, and asserting the bare phrase would
    # pass or fail for the wrong reason.
    assert "the size YOUR role argues for (3.0%)" in prompt
    assert "Reference position" in prompt
    # And it must carry AMI's own figure with the quote-don't-recompute
    # instruction — the half that makes the line different from the reference.
    assert "AMI computed this. Quote it" in prompt


def test_def241_a_non_debator_is_unaffected():
    """Only the three debators have a size of their own. Everyone else must see
    exactly what they saw before — this change must not widen the snapshot.

    The PM is the control rather than the Trader: it is a VERDICT-phase agent, so
    it DOES receive the reference position, which makes "reference yes, own-size
    no" a real assertion. The Trader is EXECUTION phase and gets no proposal line
    at all, so it would pass this vacuously."""
    prompt = _prompt(AgentId.PORTFOLIO_MANAGER, size=None)
    assert "the size YOUR role argues for" not in prompt
    assert "Reference position" in prompt


@pytest.mark.parametrize("_a,filename", _DEBATORS)
def test_def241_no_debator_prompt_still_hands_out_the_formula(_a, filename):
    """The base prompts and role blocks must stop teaching `size% × stop-distance%`
    as a thing the agent computes. The formula still appears ONCE, in the mandate
    snapshot's own explanation of what the cap means — that is a definition, not a
    work instruction, and it is not in these files."""
    text = (_CONTENT / filename).read_text(encoding="utf-8")
    assert "size% × stop-distance%" not in text
    assert "size% x stop-distance%" not in text


# ── DEF243 ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("_a,filename", _DEBATORS)
def test_def251_no_debator_dictates_its_own_first_line(_a, filename):
    """`_STANCE_FORMAT` owns line 1, and nothing in the base prompt may compete
    for it — including an instruction that competes while POINTING OUT that it
    competes.

    This assertion used to require the opposite. DEF243 rewrote `- Open with:`
    into `- Open your PROSE with: "…" — the stance line comes first, on its own
    line above it (see the format block)`, on the theory that naming the
    precedence resolves the tie, and this test pinned that wording in place.
    DEF251 then measured the theory on the next epoch: displacement went 28.9%
    → 33.3%, and 20% of debator turns emitted no envelope at all — a class the
    DEF247 parser fix cannot recover, because there is nothing to strip. That is
    `failure_patterns` P2 in one line: the instruction was never a control.

    So the bullet is deleted rather than reworded a second time, the role
    framing it carried moves into a plain "make the case" bullet that says
    nothing about line 1, and what owns the slot is stated where the file states
    its other prohibitions.

    RED before: each file contained `- Open your PROSE with: "…"`.
    """
    text = (_CONTENT / filename).read_text(encoding="utf-8")
    assert "- Open with:" not in text, (
        "this instruction competes with _STANCE_FORMAT for the first line"
    )
    assert "Open your PROSE with:" not in text, (
        "DEF243's rewording — measured ineffective by DEF251, deleted not reworded"
    )
    assert "Write anything above the stance line" in text, (
        "deleting the opener without naming what owns the slot leaves it unclaimed"
    )


@pytest.mark.parametrize("agent_id,_f", _DEBATORS)
def test_def243_the_stance_format_still_demands_the_first_line(agent_id, _f):
    """The other half of the contract. If the format block ever stops asking for
    line 1, the prompt-side wording above becomes wrong in the opposite direction
    and this pair of assertions is what notices."""
    prompt = _prompt(agent_id, size=5.0)
    assert "your VERY FIRST line must be this one line" in prompt
    assert "[STANCE: for|against|neutral" in prompt


def test_def243_is_scoped_to_the_three_agents_that_had_the_conflict():
    """Exactly 3 of the 12 base prompts carried an `Open with:` line, and they are
    exactly the 3 that lost their stance (10/54 vs 0/144). If a fourth file grows
    one, it inherits the defect silently — so the scope is asserted, not assumed."""
    offenders = sorted(
        p.name for p in _CONTENT.glob("*.md")
        if any(
            marker in p.read_text(encoding="utf-8")
            # Both spellings: the original, and DEF243's rewrite of it. A file
            # that grows either one inherits the defect, and DEF251 proved the
            # second spelling is not the safer of the two.
            for marker in ("- Open with:", "Open your PROSE with:")
        )
    )
    assert offenders == [], (
        f"{offenders} compete with _STANCE_FORMAT for the first line — see DEF243"
    )


# ── DEF241, the call site ─────────────────────────────────────────────────────


def test_def241_the_runner_actually_hands_each_debator_its_own_size():
    """Every test above calls `build_room_messages` DIRECTLY and passes
    `agent_size_pct` itself — which proves the builder and says nothing about the
    caller. That is precisely the blind spot that let DEF238 ship: CR026's sector
    line was tested the same way for its whole life while `_stream_pm_response`
    never passed the argument, and the feature never worked once in production.

    So this drives the real `RoomRunner.run()` and asserts the three debators
    receive three DIFFERENT figures, computed from `risk_debator_sizes`.

    RED without the runner change: no debator prompt contains "the size YOUR role
    argues for" at all.
    """
    from app.services.room_runner import RoomRunner

    captured: dict[str, str] = {}

    class _Gateway:
        def has_real_provider(self) -> bool:
            return True

        async def stream_chat(self, *, system_prompt, messages, model_tier,
                              locale="en", max_tokens=1024, **_audit):
            captured[_audit.get("audit_agent_id") or "?"] = system_prompt
            text = (
                '{"action": "PASS", "narration": "PM: hold."}'
                if "speak as the chief investment officer" in system_prompt.lower()
                else "[STANCE: neutral | CONVICTION: low | HEADLINE: x]\nA reply."
            )
            yield text

    import asyncio
    from uuid import uuid4

    async def _drain():
        async for _ev in RoomRunner(llm=_Gateway()).run(  # type: ignore[arg-type]
            user_id=uuid4(), ticker="MSFT",
            mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
            char_delay_min=0.0, char_delay_max=0.0,
        ):
            pass

    asyncio.run(_drain())

    figures = {}
    for agent_id in ("aggressive_debator", "conservative_debator", "neutral_debator"):
        prompt = captured.get(agent_id)
        assert prompt, f"{agent_id} never spoke"
        marker = "the size YOUR role argues for ("
        if marker in prompt:
            figures[agent_id] = prompt.split(marker, 1)[1].split(")", 1)[0]

    # CR166 Tier D — ALL THREE now carry their own figure. This used to expect
    # only two: the neutral debator's size is the risk-tier ceiling here, and
    # DEF241 suppressed its line as a duplicate of the reference. That carve-out
    # is what the Aggressive debator fell through on the AAPL run of 2026-08-11
    # (stated 0.30 pt against a supplied 0.18) — see
    # `test_cr166_own_figure_is_given_even_when_the_size_equals_the_reference`.
    assert set(figures) == {
        "aggressive_debator", "conservative_debator", "neutral_debator"
    }, f"the runner did not hand every debator its own size: {figures}"
    assert figures["aggressive_debator"] != figures["conservative_debator"], (
        f"both debators got the same size — the per-agent table is not "
        f"discriminating: {figures}"
    )
