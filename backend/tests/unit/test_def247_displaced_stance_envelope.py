"""DEF247 — the stance envelope is stripped wherever it sits, not only at the ends.

DEF147 split one regex into two jobs so that a malformed envelope could fail at
one of them alone: FIND-and-STRIP is loose (a line that merely begins with
`STANCE:` comes off, parsed or not), PARSE is per-field and nullable. What it
left behind was a second coupling, through *position*: both jobs hung off the
same two candidate lines, `filled[0]` and `filled[-1]`. So the two failures came
back together the moment the model wrote one conversational line ahead of the
envelope —

    I'd argue for smaller sizing

    [STANCE: against | CONVICTION: medium | HEADLINE: 0.09pt portfolio-drawdown ...]

    - **Size Cap:** Restrict entry to **1.5%** of portfolio ...

— which displaces it off the front while real prose runs past it off the back.
Neither end matched; `_STANCE_TAIL_RE` is `\\Z`-anchored and did not either; the
turn came back untouched. The user read raw machine syntax mid-argument AND the
comb drew that agent in the "did not state a view" gutter, at the same time.

Measured 3 of 9 debator turns on the 2026-08-09 post-promotion batch
(`cr143-postpromo-smoke-20260809`). Those nine turns are frozen verbatim in
`fixtures/def247_debator_turns.json` and drive the regression below — the three
that leaked and the six that did not, because a fix that strips more must not
start stripping what was already correct.

The fix is to stop bounding the strip by position. `_STANCE_LINE_RE` is anchored
at the start of a line, so it was never the position bound that protected a
bracketed aside mid-sentence — the anchor was. Widening costs that protection
nothing, which `test_a_bracketed_aside_inside_a_sentence_is_still_prose` holds.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import structlog

from app.services.room_runner import parse_stance_envelope

FIXTURE = Path(__file__).parent / "fixtures" / "def247_debator_turns.json"


def _turns() -> list[dict]:
    return json.loads(FIXTURE.read_text())


# ── the shape that leaked, reduced ───────────────────────────────────────


DISPLACED = (
    "I'd push for full mandate-allowed sizing\n"
    "\n"
    "[STANCE: for | CONVICTION: high | HEADLINE: 0.30pt drawdown cost]\n"
    "\n"
    "The mandate-computed drawdown contribution of **0.30 pt** against the\n"
    "**30%** portfolio cap is negligible."
)


def test_an_envelope_behind_an_opener_is_stripped_and_read():
    body, env = parse_stance_envelope(DISPLACED)
    assert "STANCE" not in body
    assert (env.stance, env.conviction) == ("for", "high")
    assert env.headline == "0.30pt drawdown cost"


def test_the_opener_and_the_argument_both_survive_the_strip():
    """Only the envelope line comes off. The turn either side of it is the
    user's whole read of that agent, and a strip that ate the argument would be
    a worse defect than the one it fixed."""
    body, _ = parse_stance_envelope(DISPLACED)
    assert body.startswith("I'd push for full mandate-allowed sizing")
    assert "negligible." in body
    assert "0.30 pt" in body


def test_the_hole_left_by_the_removed_line_is_closed():
    """The envelope was flanked by blank lines; removing it puts them back to
    back and the user reads the gap as a missing paragraph."""
    body, _ = parse_stance_envelope(DISPLACED)
    assert "\n\n\n" not in body


def test_an_envelope_deep_in_the_turn_is_still_the_machine_channel():
    """Nothing about the fix is specific to line two. The prompt asks for the
    front; every other position is drift, and drift is what this must survive."""
    body, env = parse_stance_envelope(
        "Opening line.\n\nA second paragraph of argument.\n\n"
        "[STANCE: against | CONVICTION: low | HEADLINE: thin volume]\n\n"
        "A closing paragraph."
    )
    assert "STANCE" not in body
    assert env.stance == "against"
    assert body.endswith("A closing paragraph.")


def test_every_envelope_comes_off_when_the_model_writes_several():
    """The prompt says write it once. When the model writes it three times, all
    three are machine channel; the front one is what the user is shown."""
    body, env = parse_stance_envelope(
        "[STANCE: for | CONVICTION: high | HEADLINE: first]\n"
        "prose\n"
        "[STANCE: against | CONVICTION: low | HEADLINE: middle]\n"
        "more prose\n"
        "[STANCE: neutral | CONVICTION: medium | HEADLINE: last]"
    )
    assert "STANCE" not in body
    assert body == "prose\nmore prose"
    assert env.stance == "for"
    assert env.headline == "first"


# ── the failure stays counted after it stops hurting ─────────────────────


def test_a_displaced_envelope_is_still_reported():
    """The fix makes this shape harmless to the user, which is exactly how a
    ~30% instruction-following rate stops being visible. DEF147 decoupled these
    jobs so a failure could be absorbed at one layer and still counted at
    another; the count is this log line, and it is what CR143's model arm is
    measured on."""
    with structlog.testing.capture_logs() as captured:
        parse_stance_envelope(DISPLACED)
    displaced = [e for e in captured if e["event"] == "room_stance_envelope_displaced"]
    assert len(displaced) == 1, captured
    assert displaced[0]["opener"] == "I'd push for full mandate-allowed sizing"


def test_an_obedient_turn_is_not_reported_as_displaced():
    """Precision on the counter itself. If the instructed shape logged too, the
    rate would read 100% and mean nothing."""
    with structlog.testing.capture_logs() as captured:
        parse_stance_envelope(
            "[STANCE: for | CONVICTION: high | HEADLINE: 17x forward]\n\nThe case."
        )
    assert not [
        e for e in captured if e["event"] == "room_stance_envelope_displaced"
    ], captured


# ── what the widening must NOT break ─────────────────────────────────────


def test_a_bracketed_aside_inside_a_sentence_is_still_prose():
    """The load-bearing claim of the fix. The old bound was justified as the
    thing keeping a mid-paragraph aside out of the machine channel; it was not.
    `_STANCE_LINE_RE` is anchored at the start of a line, so an aside inside a
    sentence was never a candidate at any position, and still is not."""
    text = (
        "As noted [STANCE: for | CONVICTION: high | HEADLINE: not this one] the "
        "multiple is defensible."
    )
    body, env = parse_stance_envelope(text)
    assert env.stance is None
    assert body == text


def test_the_inline_tail_form_still_parses():
    """`_STANCE_TAIL_RE` is untouched: an envelope sharing its line with the
    prose before it, at the very end, is the legacy shape DEF147 kept accepting
    on read. Widening the line-anchored search does not reach it, so the
    fallback must still be there."""
    body, env = parse_stance_envelope(
        "The multiple is defensible. [STANCE: for | CONVICTION: high | "
        "HEADLINE: 17x forward]"
    )
    assert "STANCE" not in body
    assert env.stance == "for"


def test_a_turn_with_no_envelope_is_returned_byte_identical():
    text = "No machine channel here.\n\nJust two paragraphs of argument."
    body, env = parse_stance_envelope(text)
    assert body == text
    assert (env.stance, env.conviction, env.headline) == (None, None, None)


def test_the_opt_out_still_lands_in_the_gutter_from_a_displaced_position():
    """`STANCE: none` is the prompt's own opt-out and must reach the gutter
    rather than being coerced — including when it is not on the first line."""
    body, env = parse_stance_envelope(
        "A preamble.\n\nSTANCE: none\n\nThe argument.")
    assert "STANCE" not in body
    assert env.stance is None
    assert env.conviction is None


# ── the real corpus ──────────────────────────────────────────────────────


def test_the_fixture_still_contains_the_defect_it_was_frozen_for():
    """P16: a corpus test that would pass on an empty file proves nothing. Three
    of these nine turns must still be the displaced shape — if a future edit
    trims the fixture to the easy cases, this fails first."""
    turns = _turns()
    assert len(turns) == 9
    displaced = [
        t for t in turns
        if "STANCE" in t["text"]
        and not t["text"].lstrip().splitlines()[0].lstrip().startswith(("[STANCE", "STANCE"))
    ]
    assert len(displaced) == 3, [t["agent"] for t in displaced]


@pytest.mark.parametrize("turn", _turns(), ids=lambda t: f"{t['agent']}@{t['created_at'][11:19]}")
def test_no_real_turn_leaves_machine_syntax_in_the_prose(turn):
    """The invariant this module's header states and DEF247 broke: anything
    shaped like the machine channel is REMOVED whether or not it parses."""
    body, _ = parse_stance_envelope(turn["text"])
    assert "STANCE" not in body
    assert "CONVICTION" not in body


def test_every_real_turn_that_wrote_an_envelope_now_yields_its_stance():
    """The other half of the pair. Stripping without reading would still leave
    the agent in the gutter having stated a view — DEF147's original lie."""
    for turn in _turns():
        if "STANCE" not in turn["text"]:
            continue
        _, env = parse_stance_envelope(turn["text"])
        assert env.stance is not None, turn["agent"]
        assert env.conviction is not None, turn["agent"]


def test_the_six_turns_that_were_already_correct_are_unchanged():
    """A fix that strips more must not start stripping what was already right.
    These six parsed and stripped correctly before DEF247 and must be
    byte-identical after it."""
    for turn in _turns():
        first = turn["text"].lstrip().splitlines()[0].lstrip()
        if not first.startswith(("[STANCE", "STANCE")):
            continue
        body, env = parse_stance_envelope(turn["text"])
        assert env.stance in {"for", "against", "neutral"}
        assert body.strip() == "\n".join(
            turn["text"].strip().splitlines()[1:]
        ).strip().replace("\n\n\n", "\n\n")
