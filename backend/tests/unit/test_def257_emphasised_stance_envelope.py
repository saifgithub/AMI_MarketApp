"""DEF257 — the stance envelope wearing markdown bold is still the machine channel.

DEF247 made the STRIP non-positional: the envelope is found wherever it sits in
the turn, not only on the first or last non-blank line. That fixed the shape the
corpus had at the time. It did not fix the shape the corpus grew a day later —
the model began emitting the envelope in **bold**:

    Splitting the difference, I'd propose a scaled entry.

    **STANCE: for | CONVICTION: medium | HEADLINE: $1231.94 entry**

    I align with the Aggressive view on the strength of the 48% TTM growth…

`_STANCE_LINE_RE` accepted an optional `[`, never a `**`, so the line was neither
stripped nor read: raw machine syntax on the user's screen and a null stance in
the comb, which is exactly the pair DEF147 split these two jobs to prevent and
DEF247 was supposed to have closed.

Found by measuring my own fix rather than by a report. The DEF247 post-fix batch
should have shown a zero leak; it showed 2 of 142 stored agent messages still
carrying `STANCE`, and those two were bold.

**Rare, and new.** Across every debator turn ever stored: **0 in the first 2,974**,
5 since 2026-08-10. Nothing in the prompt invites emphasis — `_STANCE_FORMAT`
shows the envelope bare and says nothing about formatting — so this is drift in
the model's markdown habits, not a prompt change. That is the standing argument
for why FIND is deliberately loose and PARSE deliberately strict (DEF147): the
set of shapes a model emits is not knowable in advance, so the *strip* must be
generous and only the *read* may be fussy.

The widening is bounded to what has been observed plus its trivial neighbours —
one or two `*`/`_`, either side of the optional bracket. Not "any prefix": that
would start eating prose, and inventing shapes nobody has emitted is the P16
mistake this file is otherwise a record of avoiding.

All five real turns are frozen verbatim in
`fixtures/def257_emphasised_stance_turns.json`, and they carry both shapes the
model actually produced: `**[STANCE: …]**` and `**STANCE: …**`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.services.room_runner import parse_stance_envelope

FIXTURE = Path(__file__).parent / "fixtures" / "def257_emphasised_stance_turns.json"


def _turns() -> list[dict]:
    return json.loads(FIXTURE.read_text())


# ── the shapes the model actually emitted ────────────────────────────────


BOLD_BARE = (
    "Splitting the difference, I'd propose a scaled entry.\n"
    "\n"
    "**STANCE: for | CONVICTION: medium | HEADLINE: $1231.94 entry**\n"
    "\n"
    "I align with the Aggressive view on the **48%** TTM revenue growth."
)

BOLD_BRACKETED = (
    "**[STANCE: against | CONVICTION: high | HEADLINE: RSI 76]**\n"
    "\n"
    "The technical setup is stretched."
)


def test_a_bold_envelope_is_stripped_and_read():
    body, env = parse_stance_envelope(BOLD_BARE)
    assert "STANCE" not in body
    assert (env.stance, env.conviction) == ("for", "medium")


def test_a_bold_bracketed_envelope_is_stripped_and_read():
    body, env = parse_stance_envelope(BOLD_BRACKETED)
    assert "STANCE" not in body
    assert (env.stance, env.conviction) == ("against", "high")
    assert env.headline == "RSI 76"


def test_the_headline_does_not_keep_the_closing_bold():
    """The bit that reaches the pixel. Without trimming the envelope before the
    fields are read, the last field swallows the trailing `**` and the comb
    renders `$1231.94 entry**`."""
    _, env = parse_stance_envelope(BOLD_BARE)
    assert env.headline == "$1231.94 entry"
    assert "*" not in (env.headline or "")


def test_single_asterisk_and_underscore_emphasis_also_come_off():
    for line in (
        "*STANCE: neutral | CONVICTION: low | HEADLINE: mixed*",
        "_STANCE: neutral | CONVICTION: low | HEADLINE: mixed_",
    ):
        body, env = parse_stance_envelope(f"{line}\n\nprose")
        assert "STANCE" not in body, line
        assert env.stance == "neutral", line
        assert env.headline == "mixed", line


def test_the_argument_around_a_bold_envelope_survives():
    body, _ = parse_stance_envelope(BOLD_BARE)
    assert body.startswith("Splitting the difference")
    assert "**48%** TTM revenue growth" in body, "inner emphasis is prose, not syntax"


# ── what the widening must NOT break ─────────────────────────────────────


def test_a_bold_word_that_is_not_the_envelope_is_prose():
    """The widening is a prefix rule, so the thing to prove is that it still
    needs `STANCE:` right after the emphasis — a bolded sentence that merely
    mentions the format is untouched."""
    text = "**Note:** the STANCE: field is described in the format block."
    body, env = parse_stance_envelope(text)
    assert body == text
    assert env.stance is None


def test_the_decoration_boundary_is_a_decision():
    """Pins WHERE the widening stops, because a mutation moving it broke nothing
    — which meant the bound was an accident, not a choice.

    A list-marker or blockquote envelope is NOT currently recognised. That is
    defensible only as conservatism: nothing has emitted one, and everything a
    wider rule would newly catch (`- STANCE: …`, `> STANCE: …`) would arguably be
    the machine channel too, so widening later is cheap and safe. What is not
    acceptable is for the boundary to move by accident during an unrelated edit —
    so it is asserted, and a future widening has to come here and say so.
    """
    for line in (
        "- STANCE: for | CONVICTION: high | HEADLINE: a list item",
        "> STANCE: for | CONVICTION: high | HEADLINE: a blockquote",
        "# STANCE: for | CONVICTION: high | HEADLINE: a heading",
    ):
        body, env = parse_stance_envelope(f"{line}\n\nprose")
        assert "STANCE" in body, f"boundary moved — {line!r} is now stripped"
        assert env.stance is None, line


@pytest.mark.parametrize("n,stripped", [(1, True), (2, True), (3, True), (4, True), (5, False)])
def test_the_repetition_bound_is_a_decision_too(n, stripped):
    """The round-1 MINOR, pinned rather than just corrected in prose.

    `_EMPHASIS` is `[*_]{0,2}` and appears TWICE in the assembled pattern — once
    either side of the optional bracket — so the effective cap on consecutive
    emphasis characters is 4, not the "one or two" the comment claimed. The
    auditor found this by building the mutation my table *described* (unbounded
    repetition) rather than the one I ran, and it survived: nothing anywhere
    exercised 3+ repeated characters.

    It matters because `***STANCE: …***` — bold+italic — is standard markdown and
    arguably the more natural next drift for a model reaching for emphasis than
    plain bold was. It works today by accident of the pattern appearing twice.
    Accidents that happen to be right are still accidents, which is the entire
    argument of `test_the_decoration_boundary_is_a_decision` one level down.
    """
    mark = "*" * n
    body, env = parse_stance_envelope(
        f"{mark}STANCE: for | CONVICTION: high | HEADLINE: x{mark}\n\nprose"
    )
    assert ("STANCE" not in body) is stripped, f"{n} asterisks"
    assert (env.stance == "for") is stripped, f"{n} asterisks"


def test_a_bracketed_aside_inside_a_sentence_is_still_prose():
    """DEF247's load-bearing claim, re-asserted here because DEF257 loosens the
    very regex that was holding it: the anchor is what keeps a mid-sentence aside
    out, and the anchor has not moved."""
    text = (
        "As noted [STANCE: for | CONVICTION: high | HEADLINE: not this one] the "
        "multiple is defensible."
    )
    body, env = parse_stance_envelope(text)
    assert body == text
    assert env.stance is None


def test_a_plain_envelope_still_parses_exactly_as_before():
    body, env = parse_stance_envelope(
        "[STANCE: for | CONVICTION: high | HEADLINE: 17x forward]\n\nThe case."
    )
    assert body == "The case."
    assert (env.stance, env.conviction, env.headline) == ("for", "high", "17x forward")


def test_an_inner_underscore_in_a_headline_survives():
    """The trim is leading/trailing runs only. An underscore inside whatever the
    agent was naming is content."""
    _, env = parse_stance_envelope(
        "[STANCE: for | CONVICTION: high | HEADLINE: free_cash_flow inflect]\n\nx"
    )
    assert env.headline == "free_cash_flow inflect"


# ── the real corpus ──────────────────────────────────────────────────────


def test_the_fixture_holds_every_emphasised_turn_the_corpus_has():
    """P16: a corpus test that would pass on an emptied file proves nothing. Five
    turns, and both shapes must be present — if a later edit keeps only the easy
    bracketed ones, this fails first."""
    turns = _turns()
    assert len(turns) == 5
    lines = [
        next(line for line in t["text"].split("\n") if "STANCE" in line) for t in turns
    ]
    assert any(re.match(r"^\s*\*\*\[", line) for line in lines), "bold+bracket missing"
    assert any(re.match(r"^\s*\*\*STANCE", line) for line in lines), "bold bare missing"


@pytest.mark.parametrize(
    "turn", _turns(), ids=lambda t: f"{t['agent']}@{t['created_at'][:19]}"
)
def test_no_real_emphasised_turn_leaks_or_loses_its_stance(turn):
    body, env = parse_stance_envelope(turn["text"])
    assert "STANCE" not in body
    assert "CONVICTION" not in body
    assert env.stance in {"for", "against", "neutral"}
    assert env.conviction in {"low", "medium", "high"}
    assert env.headline and not env.headline.endswith("*")
