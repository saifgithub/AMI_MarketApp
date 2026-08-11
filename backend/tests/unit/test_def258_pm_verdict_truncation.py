"""DEF258 — the PM hits its decode ceiling and the whole verdict is discarded.

`max_tokens` is a ceiling, and the Portfolio Manager reaches it. In the
2026-08-11 post-promotion batch, 2 of 14 PM calls stopped at exactly 1100
output tokens, mid-string, inside the long trailing `narration`. There is no
closing quote and no closing brace, so `extract_json_object` returned None,
`_parse_pm_verdict` returned `llm_verdict=None`, and the caller failed safe to
PASS (DEF059) — while the raw half-written JSON went to the transcript as the
PM's turn. What the SLB run actually published to the Room:

    { "action": "PASS", "narrational": "REJECT: Trade violates hard mandate…

…cut off mid-word. Two separate losses in one turn: the decision the model had
already committed to in its first field, and any readable rationale at all.

The order of the fields is what makes repair honest rather than a guess. The PM
emits `action`, `size_pct` and the levels BEFORE the narration — in all 14
samples the JSON began at character 1 with `action`. A clip therefore truncates
the explanation, never the decision. Closing the open string and the open brace
recovers a complete verdict with a short rationale; discarding it recovers
nothing.

Raising the budget was the other candidate and was rejected on the numbers: the
two clipped samples are CENSORED — their true length is unknown — so they cannot
size a cap (failure_patterns P16), and the other 12 finished under 425 tokens
against a 1100 ceiling. The tail is not a budget problem, so a bigger budget
would not be a fix, only a wider net.

Repair is opt-in and second: `brief_engine.py` and `portfolio_finding.py` share
`extract_json_object` and keep the strict behaviour byte-for-byte, and even on
the PM path the strict read runs first. A repaired object is a PARTIAL read, so
CR040 applies — it announces itself in the `[AMI …]` voice the client
amber-marks, rather than reading as a decision the PM explained briefly.
"""

from __future__ import annotations

import pytest

from app.schemas.mandate import Mandate
from app.schemas.room import VerdictAction
from app.services.coach_engine import hydrate_coach_mandate
from app.services.llm_json import extract_json_object
from app.services.room_runner import (
    _PM_TRUNCATED_NARRATION,
    _RoomContext,
    _parse_pm_verdict,
)


def _ctx(mandate: Mandate | None = None) -> _RoomContext:
    return _RoomContext(
        ticker="SLB",
        mandate=mandate or hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        halal_universe=None,
        classification_universe=None,
        locale_allowed_universe=None,
    )


# An APPROVE that ran out of budget mid-narration. Every decision field is
# already on the wire; only the explanation is cut.
_TRUNCATED_APPROVE = (
    '{"action": "APPROVE", "size_pct": 2.5, "entry": 53.20, "stop": 50.01, '
    '"target": 61.40, "horizon_days": 42, "narration": "Approving at reduced '
    "size.\\n- The Conservative's stop at $50.01 sits below the 50-day, not at "
    'a round number\\n- Open risk stays under the tier ceiling even at 2.5%'
)

# The shape live Alpha actually published on 2026-08-11 (SLB), typo key and all.
# The `narrational` misspelling is DEF239's territory and is NOT fixed here —
# this test pins only that the raw JSON stops reaching the transcript.
_LIVE_SLB_TRUNCATED = (
    '{\n"action": "PASS",\n"narrational": "REJECT: Trade violates hard mandate '
    "enforcement. The safety floor caps single-name position size at 3.0% of "
    "portfolio (CR101) and restricts total open-risk to a max of 10.5%.\\nThe "
    "Trader's proposal is for 3.0% size, which is the MAXIMUM allowed.\\n"
    "However, the Stop"
)


def test_a_truncated_approve_keeps_its_decision_instead_of_failing_safe_to_pass():
    """RED before: `_parse_pm_verdict` returned (raw_text, None) here, and the
    caller minted a PASS out of a decided APPROVE."""
    display, verdict = _parse_pm_verdict(_TRUNCATED_APPROVE, _ctx())
    assert verdict is not None
    assert verdict.action == VerdictAction.APPROVE
    assert verdict.size_pct == 2.5


def test_the_levels_survive_the_clip_verbatim():
    """The repair must not mint or round a level — the PM's own numbers were
    all on the wire before the truncation point."""
    _display, verdict = _parse_pm_verdict(_TRUNCATED_APPROVE, _ctx())
    assert verdict is not None
    assert verdict.entry == 53.20
    assert verdict.stop == 50.01
    assert verdict.target == 61.40


def test_a_repaired_verdict_says_it_was_cut_short():
    """CR040 — a partial read announces itself. Without this the user reads a
    sentence that stops mid-clause and has no way to know why."""
    display, _verdict = _parse_pm_verdict(_TRUNCATED_APPROVE, _ctx())
    assert _PM_TRUNCATED_NARRATION.strip() in display
    assert "[AMI" in display


def test_an_intact_verdict_carries_no_truncation_notice():
    """The disclosure must fire on the repair path ONLY — a PM that finished its
    sentence must never be captioned as having been cut off."""
    intact = (
        '{"action": "APPROVE", "size_pct": 2.5, "entry": 53.20, "stop": 50.01, '
        '"target": 61.40, "horizon_days": 42, "narration": "Approving at '
        'reduced size; the stop sits below the 50-day."}'
    )
    display, verdict = _parse_pm_verdict(intact, _ctx())
    assert verdict is not None
    assert _PM_TRUNCATED_NARRATION.strip() not in display
    assert "[AMI" not in display


def test_the_raw_half_written_json_no_longer_reaches_the_transcript():
    """The live SLB regression. The turn the user read began `{ "action":
    "PASS", "narrational": "REJECT:` — JSON source rendered as an analyst's
    contribution."""
    display, _verdict = _parse_pm_verdict(_LIVE_SLB_TRUNCATED, _ctx())
    assert not display.lstrip().startswith("{")
    assert '"narrational"' not in display


def test_the_live_slb_shape_still_yields_its_action():
    """`narrational` is a DEF239 problem (no readable narration), not a DEF258
    one. The decision itself is recoverable and must be recovered."""
    _display, verdict = _parse_pm_verdict(_LIVE_SLB_TRUNCATED, _ctx())
    assert verdict is not None
    assert verdict.action == VerdictAction.PASS


def test_repair_is_opt_in_so_the_other_two_callers_are_unchanged():
    """`brief_engine.py:311` and `portfolio_finding.py:1174` share this helper.
    Truncated input must stay a rejection for them — nothing about a proposal or
    a finding argues for reading half of one."""
    assert extract_json_object(_TRUNCATED_APPROVE) is None
    assert extract_json_object(_TRUNCATED_APPROVE, repair_truncated=True) is not None


def test_a_clip_mid_number_drops_the_partial_number():
    """`2.` is not a size. Cutting back to the last completed member is what
    keeps the repair from inventing one."""
    parsed = extract_json_object(
        '{"action": "APPROVE", "entry": 53.20, "size_pct": 2.',
        repair_truncated=True,
    )
    assert parsed is not None
    assert parsed["entry"] == 53.20
    assert "size_pct" not in parsed


def test_a_clip_right_after_a_key_drops_the_valueless_key():
    parsed = extract_json_object(
        '{"action": "PASS", "narration":', repair_truncated=True
    )
    assert parsed is not None
    assert parsed["action"] == "PASS"
    assert "narration" not in parsed


def test_a_clip_on_a_dangling_escape_does_not_swallow_the_closing_quote():
    """A trailing backslash would escape the quote the repair appends, leaving
    the string open and the object unparseable — the exact failure again."""
    parsed = extract_json_object(
        '{"action": "PASS", "narration": "Stop below the 50-day\\',
        repair_truncated=True,
    )
    assert parsed is not None
    assert parsed["action"] == "PASS"


def test_a_nested_object_is_closed_at_every_open_level():
    parsed = extract_json_object(
        '{"action": "APPROVE", "levels": {"stop": 50.01, "target": 61.40, '
        '"note": "below the 50-day',
        repair_truncated=True,
    )
    assert parsed is not None
    assert parsed["levels"]["stop"] == 50.01


def test_malformed_is_still_rejected_even_with_repair_on():
    """The fix must not become 'accept anything'. A fabricated verdict is worse
    than a lost one — that is why DEF059 fails safe on purpose."""
    assert extract_json_object("{'action': 'APPROVE'}", repair_truncated=True) is None
    assert extract_json_object("not json at all", repair_truncated=True) is None
    assert extract_json_object("", repair_truncated=True) is None


def test_a_balanced_object_that_fails_for_another_reason_is_not_salvaged():
    """Trailing commas parse nowhere and are not truncation. Repair must decline
    them rather than reach for a second interpretation of malformed input."""
    assert (
        extract_json_object('{"action": "APPROVE", }', repair_truncated=True) is None
    )


def test_an_approve_clipped_before_its_size_is_not_promoted_to_a_sized_trade():
    """`_parse_pm_verdict` already refuses an APPROVE with no `size_pct` (line
    ~1064). Repair must not route around that floor: recovering a decision is
    allowed, minting a position size for it is not."""
    clipped_early = '{"action": "APPROVE", "narration": "Approving because'
    _display, verdict = _parse_pm_verdict(clipped_early, _ctx())
    assert verdict is None


# ── DEF261 — the disclosure the clip itself removed ──────────────────────────
#
# Found by the R68-BATCH4 auditor (round 1, MAJOR 1). DEF258 appended its
# truncation notice only `if truncated and narration`, which reads as harmless
# and is not: the clip that removes the rationale is exactly the clip that
# removes the condition. A verdict cut at `"narration": ` fell through to
# `_PM_NO_RATIONALE` and published "it wrote no rationale for the call …
# nothing was said to defend it" over a decision whose rationale WE truncated.
#
# Worse than the bug it replaced: before DEF258's repair those same bytes
# produced a loud and TRUE "did not return a machine-readable verdict". The
# repair made the output readable and the caption false.


def _ctx_def261():
    from app.services.coach_engine import hydrate_coach_mandate
    from app.services.room_runner import _RoomContext

    return _RoomContext(
        ticker="SLB",
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        halal_universe=None,
        classification_universe=None,
        locale_allowed_universe=None,
    )


@pytest.mark.parametrize(
    "raw",
    [
        # The clip lands after the key and before its value.
        '{"action": "APPROVE", "size_pct": 2.5, "entry": 100.0, "stop": 94.0, "narration": ',
        # The clip lands inside the key itself, so not even the key survives.
        '{"action": "PASS", "size_pct": null, "narr',
        # A PASS whose whole tail is gone.
        '{"action": "PASS", "narration": ',
    ],
)
def test_a_clip_that_takes_the_whole_rationale_is_never_called_a_missing_one(raw):
    """The accusation and the transmission failure are different facts about
    different actors, and only one of them is the user's business to judge the
    PM on."""
    from app.services.room_runner import (
        _PM_NO_RATIONALE,
        _PM_TRUNCATED_NO_NARRATION,
        _parse_pm_verdict,
    )

    display, verdict = _parse_pm_verdict(raw, _ctx_def261())
    if verdict is None:
        # No readable action — the raw text path, which never claimed anything
        # about the PM's conduct in the first place.
        assert _PM_NO_RATIONALE not in display
        return
    assert _PM_NO_RATIONALE not in display, (
        "published 'it wrote no rationale' over a rationale WE cut off"
    )
    assert _PM_TRUNCATED_NO_NARRATION in display
    # The Verdict Board reason CONTAINS the disclosure rather than equalling it:
    # an APPROVE legitimately appends its own provenance notes (the audit-F6
    # defaulted-stop/target line, the risk-tier sizing note). What must hold is
    # that the false accusation never reaches the field CR106 renders as the
    # justification.
    assert _PM_TRUNCATED_NO_NARRATION in verdict.reason
    assert _PM_NO_RATIONALE not in verdict.reason


def test_the_two_absence_sentences_blame_different_actors():
    """If these ever converge the distinction is gone and this file is
    decoration. `_PM_NO_RATIONALE` is a statement about the PM's conduct;
    `_PM_TRUNCATED_NO_NARRATION` is a statement about ours."""
    from app.services.room_runner import _PM_NO_RATIONALE, _PM_TRUNCATED_NO_NARRATION

    assert _PM_NO_RATIONALE != _PM_TRUNCATED_NO_NARRATION
    assert "it wrote no rationale" in _PM_NO_RATIONALE
    assert "not withheld" in _PM_TRUNCATED_NO_NARRATION
    # Both stay in the [AMI …] voice the client amber-marks (CR106 §3.3).
    assert _PM_TRUNCATED_NO_NARRATION.startswith("[AMI")


def test_an_untruncated_silent_pm_still_gets_the_real_accusation():
    """DEF232's disclosure must survive. A PM that had the room to explain and
    did not use it is exactly what `_PM_NO_RATIONALE` is for, and widening the
    truncation sentence to cover it would destroy the signal."""
    from app.services.room_runner import (
        _PM_NO_RATIONALE,
        _PM_TRUNCATED_NO_NARRATION,
        _parse_pm_verdict,
    )

    for raw in (
        '{"action": "PASS", "ticker": "SLB"}',
        '{"action": "APPROVE", "size_pct": 2.0, "entry": 100.0, "ticker": "SLB"}',
    ):
        display, verdict = _parse_pm_verdict(raw, _ctx_def261())
        assert verdict is not None
        assert _PM_NO_RATIONALE in display
        assert _PM_TRUNCATED_NO_NARRATION not in display


def test_a_surviving_rationale_still_gets_the_cut_short_suffix_not_the_replacement():
    """The two truncation paths must not collapse into each other either: prose
    that partly arrived is appended to, prose that never arrived is replaced."""
    from app.services.room_runner import (
        _PM_TRUNCATED_NARRATION,
        _PM_TRUNCATED_NO_NARRATION,
        _parse_pm_verdict,
    )

    display, verdict = _parse_pm_verdict(
        '{"action": "APPROVE", "size_pct": 2.5, "narration": "The synthesis holds at redu',
        _ctx_def261(),
    )
    assert verdict is not None
    assert "The synthesis holds at redu" in display
    assert _PM_TRUNCATED_NARRATION.strip() in display
    assert _PM_TRUNCATED_NO_NARRATION not in display
