"""DEF232 — the Room shipped a verdict whose stated justification was written
by nobody.

The PM can return a well-formed decision with an empty `narration`. The two
fallbacks filled that silence with a claim: an APPROVE shipped
`reason: "Synthesis defended."` and a PASS shipped `"No trade — debate did not
support entry."`. Neither is true when the PM wrote nothing — it defended no
synthesis, and the debate's conclusion was never stated. `reason` is the string
CR106 renders on the Verdict Board as the decision's justification.

Measured on live Alpha 2026-08-07 (`room_runs`, 1016 stored verdicts):

  * 3 runs have a zero-length `portfolio_manager` transcript turn — one human
    (`84bb2cf9`, 2026-08-07 19:17Z, mid tier, a sized/stopped/targeted APPROVE)
    and two room-benchmark PASSes on 07-18.
  * 1 verdict carries a reason under 40 characters: that same APPROVE.

The row's original "23 of 965" was wrong and is corrected there: 22 of that 23
are rows from 2026-05-13→07-20 whose `verdict` column has no `action` key at
all — an older, unrelated shape, not an unnarrated verdict.

The decision still ships. A missing DECISION fails safe to PASS (DEF059); a
missing SENTENCE is not the same thing — the levels are the PM's own and the
safety floor still validates them. What the fix changes is that the silence is
stated rather than papered over, on both the verdict reason and the transcript
turn (which was otherwise a blank row).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.schemas import AgentId
from app.schemas.mandate import Mandate
from app.schemas.room import VerdictAction
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import _PM_NO_RATIONALE, _RoomContext, _parse_pm_verdict


def _ctx(mandate: Mandate | None = None) -> _RoomContext:
    return _RoomContext(
        ticker="GRAB",
        mandate=mandate or hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        halal_universe=None,
        classification_universe=None,
        locale_allowed_universe=None,
    )


_APPROVE_NO_NARRATION = (
    '{"action": "APPROVE", "size_pct": 3.0, "entry": 3.67, "stop": 3.45, '
    '"target": 4.15, "horizon_days": 42, "narration": ""}'
)
_PASS_NO_NARRATION = '{"action": "PASS", "narration": ""}'


# ── the fabricated defences are gone ──────────────────────────────────────────


def test_an_unnarrated_approve_no_longer_claims_a_synthesis_was_defended():
    display, verdict = _parse_pm_verdict(_APPROVE_NO_NARRATION, _ctx())
    assert verdict is not None
    assert verdict.action == VerdictAction.APPROVE
    assert "Synthesis defended" not in verdict.reason
    assert _PM_NO_RATIONALE in verdict.reason


def test_an_unnarrated_pass_no_longer_claims_what_the_debate_concluded():
    display, verdict = _parse_pm_verdict(_PASS_NO_NARRATION, _ctx())
    assert verdict is not None
    assert verdict.action == VerdictAction.PASS
    assert "debate did not support entry" not in verdict.reason
    assert verdict.reason == _PM_NO_RATIONALE


@pytest.mark.parametrize("raw", [_APPROVE_NO_NARRATION, _PASS_NO_NARRATION])
def test_the_transcript_turn_is_marked_rather_than_left_blank(raw):
    """The other half of the live instance: a zero-length PM row in the Room.
    The `[AMI` prefix is what the client already amber-marks (CR106 §3.3), so
    the turn is flagged with no client change."""
    display, verdict = _parse_pm_verdict(raw, _ctx())
    assert display.startswith("[AMI")
    assert display == _PM_NO_RATIONALE


def test_the_note_says_the_decision_is_unexplained_not_that_it_is_wrong():
    """AMI states what is missing. It does not editorialise about the call
    itself — the safety floor, not this note, is what judges a decision."""
    assert "no rationale" in _PM_NO_RATIONALE
    assert "unexplained decision" in _PM_NO_RATIONALE


# ── the decision itself is untouched ──────────────────────────────────────────


def test_an_unnarrated_approve_keeps_every_level_the_pm_stated():
    """A missing sentence is not a missing decision (DEF059's line): the
    levels are the PM's own and still ship, with their provenance intact."""
    _, verdict = _parse_pm_verdict(_APPROVE_NO_NARRATION, _ctx())
    assert verdict.size_pct == 3.0
    assert (verdict.entry, verdict.stop, verdict.target) == (3.67, 3.45, 4.15)
    assert verdict.level_provenance == {"entry": "pm", "stop": "pm", "target": "pm"}
    assert verdict.overridden_from_llm is False


def test_the_disclosure_suffixes_still_append_to_the_note():
    """A PM that stated neither stop nor target gets the DEF-audit-F6 minted-
    level disclosure appended after the no-rationale note, not instead of it."""
    raw = '{"action": "APPROVE", "size_pct": 3.0, "entry": 100.0, "narration": ""}'
    _, verdict = _parse_pm_verdict(raw, _ctx())
    assert _PM_NO_RATIONALE in verdict.reason
    assert "not stated by the PM" in verdict.reason
    assert verdict.level_provenance["stop"] == "ami_default"


def test_a_sized_down_approve_still_says_so_after_the_note():
    raw = (
        '{"action": "APPROVE", "size_pct": 20.0, "entry": 100.0, "stop": 94.0, '
        '"target": 113.0, "narration": ""}'
    )
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 1})  # 1.5% ceiling
    _, verdict = _parse_pm_verdict(raw, _ctx(mandate))
    assert verdict.size_pct == 1.5
    assert _PM_NO_RATIONALE in verdict.reason
    assert "mandate risk-tier ceiling" in verdict.reason


# ── a narrated verdict is untouched ───────────────────────────────────────────


@pytest.mark.parametrize("narration", [
    "PM: APPROVE — the fundamentals case survived the bear's cross-examination.",
    "PM: PASS — the multiple leaves no margin for a guide reset.",
])
def test_a_pm_that_wrote_something_is_left_completely_alone(narration):
    """Non-vacuity in the other direction: the note must appear ONLY on silence.
    A verdict that carries real prose must not gain an AMI annotation."""
    raw = (
        '{"action": "%s", "size_pct": 3.0, "entry": 100.0, "stop": 94.0, '
        '"target": 113.0, "narration": "%s"}'
        % ("APPROVE" if "APPROVE" in narration else "PASS", narration)
    )
    display, verdict = _parse_pm_verdict(raw, _ctx())
    assert display == narration
    assert verdict.reason.startswith(narration)
    assert "[AMI" not in verdict.reason


def test_whitespace_only_narration_counts_as_silence():
    raw = '{"action": "PASS", "narration": "   \\n  "}'
    display, verdict = _parse_pm_verdict(raw, _ctx())
    assert verdict.reason == _PM_NO_RATIONALE
    assert display == _PM_NO_RATIONALE


def test_the_note_is_long_enough_to_not_be_the_defect_again():
    """The live instance was 19 characters on the surface CR106 renders as the
    justification. Whatever the wording becomes, it must actually say what
    happened."""
    assert len(_PM_NO_RATIONALE) > 100
