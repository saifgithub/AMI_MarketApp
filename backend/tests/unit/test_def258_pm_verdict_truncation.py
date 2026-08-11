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
