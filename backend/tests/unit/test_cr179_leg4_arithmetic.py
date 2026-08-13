"""CR179 Leg 4 — the derived figures the Room still left an agent to work out.

Three defects, one class. DEF066 was the formula, DEF235 the parser feeding it a
wrong input, DEF241 the agent doing it in prose, CR166 Tier D the agent that
slipped DEF241's guard. This leg is the fifth and sixth doors into the same room,
both found by running the real code over the committed 2026-08-13 epoch rather
than by reading it:

- **The remainder.** `_risk_state_block` states the headroom BEFORE the trade and
  `_drawdown_snapshot_line` states the position's contribution. The number an
  agent argues from is the difference, and nothing supplied it. Of 92 epoch turns
  stating a pt-or-cap figure, 7 state that subtraction or a rescaling of it, and
  one is wrong: a Conservative arguing 1.5% wrote *"a 5.0% size … leaves 29.82 pt
  of headroom"*, which is `30 − 0.18` — the REFERENCE line's figure, attached to
  the Aggressive's size, while its own line said 0.09.
- **DEF292.** Both contribution lines rendered `~{share:.0f}% of it`. On a 30 pt
  cap that format has two reachable outputs. 40 of 240 lines said `(~0% of it)`
  for a nonzero contribution; 40 of the 160 prompts carrying the line printed two
  DIFFERENT pt figures under the SAME `~1%`.
- **DEF293 / DEF288.** `_PM_RR_KEYWORD` had no word boundary, so the "rr" inside
  *current* matched and *"current **122.6x** trailing P/E"* became a narrated
  reward multiple of 122.6 (19 of 482 turns); `_RR_CLAIM_RE` had no allowance for
  the `**` that `_PROSE_FORMAT` asks for, so bolded ratios were never rewritten
  while the annotation still claimed they had been.

Every assertion here is on a VALUE or a relationship, never on a label. A
substring check for "contribution" is what let DEF235 ship 11.32 pt for a true
0.18 pt, and a helper-only test is what let CR179 Leg 3b's threading sit unproven
until an end-to-end case was added.
"""

from __future__ import annotations

import pytest

from app.schemas.agents import AgentId
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_prompts import (
    _drawdown_snapshot_line,
    _share_of_cap_phrase,
    build_room_messages,
)
from app.services.room_runner import (
    _annotate_rr_against_levels,
    _extract_stated_rr,
    _RR_CLAIM_RE,
)
from app.trading_math.risk import drawdown_contribution

_PROPOSAL = {"size_pct": 3.0, "entry": 100.0, "stop": 94.0}


def _mandate():
    return hydrate_coach_mandate({"plan": "trader", "risk_score": 3})


def _room_prompt(agent_id: AgentId, *, size: float | None, spent: float | None) -> str:
    """The REAL assembled prompt. `_drawdown_snapshot_line` is reachable from a
    helper test, but what CR179 Leg 3b learned the hard way is that a helper
    passing says nothing about whether the argument arrives — DEF238 was an
    argument that never reached its call site for the entire life of a feature."""
    system, _msgs = build_room_messages(
        agent_id=agent_id,
        mandate=_mandate(),
        user_id=None,
        ticker="MSFT",
        profile={"base_price": 100.0},
        transcript=[],
        trade_proposal=_PROPOSAL,
        agent_size_pct=size,
        current_drawdown_pct=spent,
    )
    return system


# ── DEF292 — two contributions must not read as the same share ────────────────


def test_def292_a_nonzero_contribution_never_renders_as_zero():
    """`(~0% of it)` for a real 0.09 pt is DEF053's rule broken in the loud
    direction: the Aggressive debator that read it opened with "the risk budget
    is effectively empty and ours to fill"."""
    phrase = _share_of_cap_phrase(0.09, 30.0)
    assert "0.3%" in phrase
    assert "0%" not in phrase.replace("0.3%", "")


def test_def292_a_share_below_a_tenth_of_a_percent_says_so_rather_than_zero():
    assert _share_of_cap_phrase(0.01, 100.0) == " (<0.1% of it)"


def test_def292_a_zero_contribution_is_still_allowed_to_read_as_zero():
    """The floor is for NONZERO quantities. A genuine zero must stay a zero —
    replacing it with "<0.1%" would be the fabrication pointed the other way."""
    assert _share_of_cap_phrase(0.0, 30.0) == " (0.0% of it)"


def test_def292_the_reference_and_the_agents_own_share_are_distinguishable():
    """The whole point of DEF241's second line is that YOUR position is not the
    reference one. Rounding both onto `~1%` said they were, in 40 of the 160
    epoch prompts that carried the line."""
    line = _drawdown_snapshot_line(_mandate(), _PROPOSAL, 5.0, current_drawdown_pct=0.0)
    ref = drawdown_contribution(3.0, 100.0, 94.0)
    own = drawdown_contribution(5.0, 100.0, 94.0)
    assert ref is not None and own is not None
    ref_share = _share_of_cap_phrase(ref.contribution_pts, 30.0)
    own_share = _share_of_cap_phrase(own.contribution_pts, 30.0)
    assert ref_share != own_share, "two different pt figures must not print one share"
    assert ref_share in line and own_share in line


def test_def292_the_share_moves_with_the_contribution():
    """Pins the computation, not a constant — the mutation that survived DEF235's
    first pass was a test that would have passed on a hard-coded string."""
    assert _share_of_cap_phrase(0.30, 30.0) != _share_of_cap_phrase(0.18, 30.0)
    assert _share_of_cap_phrase(0.30, 30.0) != _share_of_cap_phrase(0.30, 50.0)


# ── the remainder, precomputed ────────────────────────────────────────────────


@pytest.mark.parametrize("spent,expected", [(0.0, "29.70"), (12.4, "17.30"), (29.5, "0.20")])
def test_the_cap_left_after_this_position_is_handed_over_not_left_as_a_subtraction(
    spent, expected
):
    """cap − already-spent − this position's contribution. 5.0% at a 6.0% stop
    is 0.30 pt, so on a 30 pt cap the answers are 29.70 / 17.30 / 0.20."""
    line = _drawdown_snapshot_line(_mandate(), _PROPOSAL, 5.0, current_drawdown_pct=spent)
    assert f"leaves {expected} pt" in line


def test_the_remainder_is_absent_when_what_was_already_spent_is_unknown():
    """CR040 / DEF053. Assuming a flat book would manufacture exactly the
    "effectively empty" reading DEF292 found — a fabricated remainder is worse
    than none, because the agent cannot tell it was invented."""
    line = _drawdown_snapshot_line(_mandate(), _PROPOSAL, 5.0, current_drawdown_pct=None)
    assert "leaves" not in line
    assert "already spent" not in line


def test_the_remainder_is_stated_once_and_for_one_position():
    """Two remainders in one prompt — one off the reference size, one off the
    role's — is the DEF292 collision rebuilt one clause to the left."""
    line = _drawdown_snapshot_line(_mandate(), _PROPOSAL, 5.0, current_drawdown_pct=0.0)
    assert line.count("of the cap already spent") == 1
    # And it is the AGENT's position that gets it, not the reference one.
    assert "leaves 29.70 pt" in line and "leaves 29.82 pt" not in line


def test_an_agent_with_no_role_size_gets_the_remainder_off_the_reference_position():
    """The Trader and PM argue the reference position itself, so the remainder is
    still theirs to be handed — omitting it because there is no YOUR-line would
    leave the subtraction exactly where it was."""
    line = _drawdown_snapshot_line(_mandate(), _PROPOSAL, None, current_drawdown_pct=0.0)
    assert "YOUR position" not in line
    assert "leaves 29.82 pt" in line  # 30 − 0 − 0.18


@pytest.mark.parametrize(
    "agent_id",
    [AgentId.AGGRESSIVE_DEBATOR, AgentId.CONSERVATIVE_DEBATOR, AgentId.NEUTRAL_DEBATOR],
)
def test_the_remainder_reaches_a_real_assembled_room_prompt(agent_id):
    """End to end through `build_room_messages`, not the helper. Sever
    `current_drawdown_pct` at the `_drawdown_snapshot_line` call and this goes
    red — which is the property the helper tests above cannot check."""
    prompt = _room_prompt(agent_id, size=5.0, spent=4.0)
    assert "With 4.0 pt of the cap already spent" in prompt
    assert "leaves 25.70 pt" in prompt  # 30 − 4.0 − 0.30


def test_the_remainder_tracks_the_spend_end_to_end():
    a = _room_prompt(AgentId.AGGRESSIVE_DEBATOR, size=5.0, spent=0.0)
    b = _room_prompt(AgentId.AGGRESSIVE_DEBATOR, size=5.0, spent=10.0)
    assert "leaves 29.70 pt" in a and "leaves 19.70 pt" in b


# ── DEF293 — "current" is not a reward-to-risk keyword ────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "the current **122.6x** trailing P/E suggests thorough optimism",
        "the Bear correctly notes the **122.6x** trailing multiple",
        "an error — **375.4x** peak earnings is not a floor",
        "no thesis can override the math of a 2.3 turn",
        "revenue is currently suppressed at 0.73x normal volume",
    ],
)
def test_def293_an_rr_inside_an_ordinary_word_is_not_a_narrated_ratio(text):
    """`r[:/\\s-]?r` with no word boundary matched cu-RR-ent, co-RR-ectly,
    e-RR-or and ove-RR-ide. 19 of 482 epoch turns across 8 agents, and 2 of the 3
    PM turns that fed `_pm_rr_coherence_signal` a ratio at all."""
    assert _extract_stated_rr(text) is None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("R:R = 3:1 on this setup", 3.0),
        ("risk/reward of 2.5:1", 2.5),
        ("a 3:1 risk-to-reward", 3.0),
        ("R/R 4x", 4.0),
        ("**R:R**: 2.1:1", 2.1),
        ("R:R: 1:1.6", 1.6),  # risk-first — the reward multiple is 1.6, not 1.0
        ("R:R: 1:1", 1.0),
    ],
)
def test_def293_a_real_narrated_ratio_still_reads(text, expected):
    assert _extract_stated_rr(text) == expected


# ── DEF288 — the rewrite, and an annotation that reports what it did ──────────


@pytest.mark.parametrize(
    "text", ["**R:R**: 1:1.6", "R:R of **1.9:1**", "**R:R**:      2.1:1", "R:R: 1.9:1"]
)
def test_def288_a_bolded_ratio_is_rewritten_in_place(text):
    """`_PROSE_FORMAT` asks every prose agent to bold its metrics and they comply;
    3 of the 16 real narrated ratios in the epoch are bolded, and none of them
    was ever rewritten."""
    out = _RR_CLAIM_RE.sub(lambda m: f"{m.group(1)}9.9:1", text)
    assert out != text and "9.9:1" in out


def test_def288_a_rewrite_cannot_fuse_with_the_remains_of_the_old_ratio():
    """The ratio group ended at a literal `1`, so rewriting `1:1.6` produced
    `9.9:1` plus a stranded `.6` — `9.9:1.6`, a number neither side computed."""
    out = _RR_CLAIM_RE.sub(lambda m: f"{m.group(1)}9.9:1", "R:R: 1:1.6")
    assert out.endswith("9.9:1")
    assert "9.9:1.6" not in out


def _levels():  # entry/stop/target implying R:R 2.0:1
    return dict(entry=100.0, stop=90.0, target=120.0)


def test_def288_the_annotation_claims_a_replacement_only_when_it_replaced_one():
    """The tail asserted "has been replaced" whenever a ratio was EXTRACTED, and
    the extractor matches phrasings the rewriter does not. On the epoch that put
    the claim on 2 of the 36 annotated turns with nothing replaced — printed
    under "These are the figures of record"."""
    text = "Entry 100.00, stop 90.00, target 120.00. A 0.8:1 risk/reward here."
    out, _sig = _annotate_rr_against_levels(text, size=3.0, **_levels())
    assert "0.8:1 risk/reward" in out, "number-first is deliberately not rewritten"
    assert "has been replaced" not in out
    assert "does not rewrite in place" in out


def test_def288_the_annotation_does_claim_a_replacement_when_it_made_one():
    text = "Entry 100.00, stop 90.00, target 120.00. **R:R**: 5.0:1 here."
    out, _sig = _annotate_rr_against_levels(text, size=3.0, **_levels())
    assert "2.0:1" in out and "5.0:1" not in out
    assert "has been replaced" in out


def test_def288_an_unverifiable_ratio_is_marked_even_when_it_cannot_be_struck():
    """The refusal branch's own docstring says silence would leave the agent's
    claim standing unmarked. When the inline strike does not fire — the
    number-first phrasing again — the note is appended instead."""
    text = "Entry 100.00, stop 110.00, target 105.00. A 3:1 risk/reward."
    out, sig = _annotate_rr_against_levels(text, size=3.0, entry=100.0, stop=110.0, target=105.0)
    assert sig is not None and sig["implied_rr"] == -1.0
    assert out != text
    assert "could not verify" in out or "unverifiable" in out
