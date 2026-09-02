"""CR219 WP05 (R25, R26, R56) — `primary_goal` wired as weighted guidance, and
the two RiskComponents fields (`drawdown_response`, `regret_asymmetry`) that
were collected at onboarding and used by nothing downstream.

R25/R26 ruling (DECISIONS_2026-09-02.md): `primary_goal` becomes weighted
EMPHASIS, never a hard PM filter gate — the PM keeps holistic gatekeeping.
Mechanism: `_goal_block` in `overlay_generator.py`, an exhaustive `match` over
every `PrimaryGoal` arm with a `case _:` that raises rather than silently
rendering nothing (CR040 — degrade loudly). Because Python cannot prove that
match exhaustive statically for a `str, Enum` subclass, this file supplies the
actual guarantee: iterate the real enum and assert every arm renders.

R56 (Fable's scoping, rides the same WP while it's open): `drawdown_response`
renders as a risk-officer stress-test emphasis line (NOT a floor change) and
`regret_asymmetry` renders as a one-line framing hint in the
researcher/debator overlays. Both are pure text; neither touches
`agents/safety_floor.py` or any enforced cap.
"""

import pytest

from app.agents.overlay_generator import (
    _drawdown_stress_line,
    _goal_block,
    _regret_framing_line,
    generate_overlay,
)
from app.schemas import AgentId, Mandate, PrimaryGoal


# ──────────────────────────────────────────────────────────────────────────────
# R26 — exhaustive match: every PrimaryGoal arm yields a distinct, non-empty
# block. This is the real exhaustiveness guarantee (Python's `match` cannot be
# proven exhaustive statically for a `str, Enum` subclass), and it iterates the
# ACTUAL enum rather than a hand-copied list, so a future arm nobody wires
# fails this test rather than silently rendering nothing.
# ──────────────────────────────────────────────────────────────────────────────


def test_every_primary_goal_enum_arm_yields_a_distinct_non_empty_block(base_mandate: Mandate):
    seen: dict[PrimaryGoal, str] = {}
    for goal in PrimaryGoal:
        mandate = base_mandate.model_copy(update={"primary_goal": goal.value})
        block = _goal_block(mandate)
        assert block.strip(), f"primary_goal={goal.value} produced an empty goal block"
        seen[goal] = block

    values = list(seen.values())
    assert len(set(values)) == len(values), (
        f"two or more PrimaryGoal arms produced the IDENTICAL goal block — "
        f"weighted guidance that reads the same for two different goals is "
        f"finding #17 again, one field over: {seen}"
    )


def test_goal_block_never_reads_as_a_pm_auto_reject(base_mandate: Mandate):
    """R25's ruling: weighted EMPHASIS, never a hard filter gate. None of the
    six lines may use AFFIRMATIVE reject/disqualify/auto-reject language — the
    PM keeps holistic gatekeeping, unchanged by this WP. (A line that says
    'does not disqualify' is the negation of the very thing R25 forbids, so it
    must NOT trip this — the check below matches the affirmative phrasing
    only, never a bare substring.)"""
    forbidden = (
        "does disqualify",
        "will disqualify",
        "auto-reject",
        "auto reject",
        "must reject",
        "hard reject",
        "automatically reject",
    )
    for goal in PrimaryGoal:
        mandate = base_mandate.model_copy(update={"primary_goal": goal.value})
        block = _goal_block(mandate).lower()
        for phrase in forbidden:
            assert phrase not in block, (
                f"primary_goal={goal.value}'s block contains {phrase!r} — R25 rules "
                "this out; the PM's holistic gatekeeping must not be preempted by "
                "goal-emphasis text"
            )
        assert "disqualif" not in block or "does not disqualify" in block, (
            f"primary_goal={goal.value}'s block mentions disqualification in an "
            "unexpected (non-negated) way — re-check it reads as emphasis, not a gate"
        )


def test_goal_block_raises_loudly_on_an_unhandled_value(base_mandate: Mandate):
    """CR040 — degrade loudly. Verified (not assumed): `Mandate.model_copy
    (update=...)` — Pydantic v2's documented behaviour — does NOT re-run
    validation, so a bad `primary_goal` string built that way sails straight
    past the schema and would reach `_goal_block` completely unchecked if
    nothing inside that function caught it. `_goal_block` opens with
    `PrimaryGoal(m.primary_goal)` precisely so this path is covered too — the
    coercion itself is the loud failure here (Python's own `ValueError: ... is
    not a valid PrimaryGoal`), firing BEFORE the `match` even runs. That is
    still CR040-compliant (a loud, unambiguous raise, not a silent fallback);
    this test pins that the raise happens on this exact path, not the exact
    codepoint it happens at."""
    mandate = base_mandate.model_copy(update={"primary_goal": "future_unmapped_goal"})
    assert mandate.primary_goal == "future_unmapped_goal", (
        "model_copy(update=...) no longer skips validation the way Pydantic v2 "
        "documents — re-check this test still reaches _goal_block unchecked "
        "rather than being stopped upstream by Mandate's own schema"
    )
    with pytest.raises(ValueError, match="future_unmapped_goal"):
        _goal_block(mandate)


def test_constructing_a_mandate_directly_does_refuse_an_unknown_primary_goal_value(
    base_mandate: Mandate,
):
    """The OTHER path — normal construction (`Mandate(**kwargs)` /
    `model_validate`, what a real API request deserializes through) DOES
    reject an unmapped `primary_goal` at the schema boundary, before
    `_goal_block` is ever reached. Named explicitly so the two guards (schema
    validation on construction, `_goal_block`'s own match on every path
    including `model_copy`) are not conflated — see the docstring above for
    why `model_copy` needs its own guard rather than relying on this one."""
    payload = {**base_mandate.model_dump(), "primary_goal": "future_unmapped_goal"}
    with pytest.raises(ValueError):
        Mandate(**payload)


def test_goal_block_is_wired_into_the_rendered_overlay(base_mandate: Mandate):
    """The block must actually reach the prompt, not just exist as a callable
    nobody invokes — R26's mechanism is `overlay_generator.py`, checked here
    through the public `generate_overlay` entry point."""
    overlay = generate_overlay(AgentId.PORTFOLIO_MANAGER, base_mandate)
    assert "Goal emphasis (long_term_wealth)" in overlay


# ──────────────────────────────────────────────────────────────────────────────
# Acceptance test from WP05_primary_goal.md: two mandates differing only in
# `primary_goal` produce MATERIALLY DIFFERENT overlay TEXT. Asserted on prompt
# text, never verdicts — verdict differences are noise at single draws (the
# WP's own citation: ~19.7% flip at n=1).
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "agent_id",
    [
        AgentId.FUNDAMENTALS_ANALYST,
        AgentId.PORTFOLIO_MANAGER,
        AgentId.TRADER,
    ],
)
def test_two_convenes_differing_only_in_primary_goal_render_different_overlay_text(
    base_mandate: Mandate, agent_id: AgentId
):
    income_mandate = base_mandate.model_copy(update={"primary_goal": PrimaryGoal.INCOME_NOW.value})
    learning_mandate = base_mandate.model_copy(
        update={"primary_goal": PrimaryGoal.LEARNING_TO_TRADE.value}
    )
    assert income_mandate.model_dump(exclude={"primary_goal"}) == learning_mandate.model_dump(
        exclude={"primary_goal"}
    ), "fixture setup: the two mandates must differ ONLY in primary_goal"

    overlay_income = generate_overlay(agent_id, income_mandate)
    overlay_learning = generate_overlay(agent_id, learning_mandate)

    assert overlay_income != overlay_learning, (
        f"{agent_id.value}'s overlay is IDENTICAL for primary_goal=income_now vs. "
        "learning_to_trade — this is finding #17 (CR219): primary_goal printed but "
        "nothing branches on it"
    )
    assert "Goal emphasis (income_now)" in overlay_income
    assert "Goal emphasis (income_now)" not in overlay_learning
    assert "Goal emphasis (learning_to_trade)" in overlay_learning
    assert "Goal emphasis (learning_to_trade)" not in overlay_income


# ──────────────────────────────────────────────────────────────────────────────
# R56 — drawdown_response: a risk-officer STRESS-TEST emphasis line, not a
# floor change. Wired into the three risk debators only (Aggressive,
# Conservative, Neutral) — the WP's own framing ("how hard the debators stress
# drawdown scenarios").
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "agent_id",
    [AgentId.AGGRESSIVE_DEBATOR, AgentId.CONSERVATIVE_DEBATOR, AgentId.NEUTRAL_DEBATOR],
)
def test_drawdown_response_varies_the_stress_test_line_across_the_three_risk_officers(
    conservative_mandate: Mandate, aggressive_mandate: Mandate, agent_id: AgentId
):
    # conservative_mandate: drawdown_response=1 (panic-lean); aggressive_mandate:
    # drawdown_response=5 (buy-more-lean) — conftest.py's own fixtures.
    low = generate_overlay(agent_id, conservative_mandate)
    high = generate_overlay(agent_id, aggressive_mandate)
    assert "Drawdown-response stress test" in low
    assert "Drawdown-response stress test" in high
    assert "self-reported 1/5" in low
    assert "self-reported 5/5" in high
    # The two lines must differ in substance, not just the echoed number — a
    # line that only swaps the digit is the same bug in miniature.
    low_line = next(ln for ln in low.splitlines() if "Drawdown-response stress test" in ln)
    high_line = next(ln for ln in high.splitlines() if "Drawdown-response stress test" in ln)
    assert low_line != high_line


def test_drawdown_response_line_is_explicitly_not_a_floor_change(
    conservative_mandate: Mandate,
):
    overlay = generate_overlay(AgentId.AGGRESSIVE_DEBATOR, conservative_mandate)
    line = next(ln for ln in overlay.splitlines() if "Drawdown-response stress test" in ln)
    assert "cannot exceed" not in line and "HARD CONSTRAINT" not in line, (
        "the drawdown_response line must read as debate emphasis, not an "
        "enforced cap — the safety floor is the only enforcement mechanism"
    )


def test_drawdown_response_line_absent_from_non_risk_officer_agents(base_mandate: Mandate):
    """Scoped to the three risk debators per the WP text. Confirms this isn't
    accidentally leaking into every agent's overlay."""
    for agent_id in (AgentId.FUNDAMENTALS_ANALYST, AgentId.BULL_RESEARCHER, AgentId.TRADER):
        overlay = generate_overlay(agent_id, base_mandate)
        assert "Drawdown-response stress test" not in overlay


def test_drawdown_stress_line_helper_covers_the_full_1_to_5_range(base_mandate: Mandate):
    """RiskComponents.drawdown_response is `Field(..., ge=1, le=5)` — every
    integer in that closed range must produce a non-empty, distinct-by-tier
    line (no silent gap)."""
    lines = {}
    for value in (1, 2, 3, 4, 5):
        rc = base_mandate.risk_components.model_copy(update={"drawdown_response": value})
        mandate = base_mandate.model_copy(update={"risk_components": rc})
        line = _drawdown_stress_line(mandate)
        assert line.strip()
        assert f"self-reported {value}/5" in line
        lines[value] = line
    # Three tiers by construction (<=2, 3, >=4) — 1&2 share wording, 4&5 share
    # wording, 3 is its own; assert that grouping rather than requiring five
    # distinct strings.
    assert lines[1].split("self-reported 1/5")[1] == lines[2].split("self-reported 2/5")[1]
    assert lines[4].split("self-reported 4/5")[1] == lines[5].split("self-reported 5/5")[1]
    assert lines[3] != lines[1] and lines[3] != lines[4]


# ──────────────────────────────────────────────────────────────────────────────
# R56 — regret_asymmetry: a one-line framing hint in researcher/debator
# overlays (Bull, Bear, and the three risk officers per the WP text).
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "agent_id",
    [
        AgentId.BULL_RESEARCHER,
        AgentId.BEAR_RESEARCHER,
        AgentId.AGGRESSIVE_DEBATOR,
        AgentId.CONSERVATIVE_DEBATOR,
        AgentId.NEUTRAL_DEBATOR,
    ],
)
def test_regret_asymmetry_framing_line_present_in_researcher_and_debator_overlays(
    base_mandate: Mandate, agent_id: AgentId
):
    for value, expect in ((-1, "losing money stings worse"), (0, "has not stated an asymmetry"), (1, "missing upside")):
        rc = base_mandate.risk_components.model_copy(update={"regret_asymmetry": value})
        mandate = base_mandate.model_copy(update={"risk_components": rc})
        overlay = generate_overlay(agent_id, mandate)
        assert "Regret framing:" in overlay
        assert expect in overlay, f"{agent_id.value} regret_asymmetry={value} missing {expect!r}"


def test_regret_asymmetry_absent_from_non_researcher_non_debator_agents(base_mandate: Mandate):
    for agent_id in (
        AgentId.FUNDAMENTALS_ANALYST,
        AgentId.MARKET_ANALYST,
        AgentId.NEWS_ANALYST,
        AgentId.SOCIAL_MEDIA_ANALYST,
        AgentId.RESEARCH_MANAGER,
        AgentId.TRADER,
        AgentId.PORTFOLIO_MANAGER,
    ):
        overlay = generate_overlay(agent_id, base_mandate)
        assert "Regret framing:" not in overlay


def test_regret_framing_line_helper_covers_the_full_range(base_mandate: Mandate):
    """RiskComponents.regret_asymmetry is `Field(..., ge=-1, le=1)` — the three
    legal values must each produce a distinct, non-empty line."""
    lines = {}
    for value in (-1, 0, 1):
        rc = base_mandate.risk_components.model_copy(update={"regret_asymmetry": value})
        mandate = base_mandate.model_copy(update={"risk_components": rc})
        lines[value] = _regret_framing_line(mandate)
        assert lines[value].strip()
    assert len(set(lines.values())) == 3, "the three regret_asymmetry values must not collapse to the same line"


def test_regret_framing_line_never_resizes_a_position(base_mandate: Mandate):
    """One-line FRAMING hint per the WP text — must not carry a numeric size
    or percentage of its own; sizing stays with the deterministic caps."""
    for value in (-1, 0, 1):
        rc = base_mandate.risk_components.model_copy(update={"regret_asymmetry": value})
        mandate = base_mandate.model_copy(update={"risk_components": rc})
        line = _regret_framing_line(mandate)
        assert "%" not in line


# ──────────────────────────────────────────────────────────────────────────────
# Safety floor untouched. `overlay_generator.py`'s pre-existing docstrings
# already discuss `safety_floor.py` descriptively (it is appended separately
# by `safety_floor.append_safety_floor()`) — that is unrelated prose, not this
# WP's concern. What matters is that neither of THIS WP's two new functions
# imports from or calls into `app.agents.safety_floor`; the actual "my commits
# touch no safety_floor.py line" claim is verified at commit time via
# `git diff`, not by a source-text scan here (see the WP05 worker's final
# report for that command's output).
# ──────────────────────────────────────────────────────────────────────────────


def test_new_wp05_helpers_do_not_call_into_safety_floor():
    import inspect

    from app.agents import overlay_generator as og

    for fn in (og._goal_block, og._drawdown_stress_line, og._regret_framing_line):
        src = inspect.getsource(fn)
        assert "safety_floor" not in src, (
            f"{fn.__name__} references safety_floor — R56 is explicit that this WP "
            "must not touch the safety floor or its inputs"
        )
