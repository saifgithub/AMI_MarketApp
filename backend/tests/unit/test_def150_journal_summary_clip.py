"""DEF150 (backend half) — the Journal's stored summary was cut mid-word.

`build_journal_entry_for_run` wrote `summary[:240]`, so the permanent record of
a decision ended `"…the 3.05 PEG and the potential fo"` — no ellipsis, no
marker, a severed word in the durable copy.

Two readers consume this field and both were served a fragment:

- the user, on the Journal detail screen;
- **Bull and Bear**, via `journal_context.format_journal_entry`, which renders
  `summary:` into a later run's decision-lookback block (DEF098). A model
  reasoning from a sentence that stops mid-word cannot tell a deliberate
  ending from a cut one — that is DEF125's class arriving through a different
  door.

The load-bearing assertion is not "it is shorter". It is that a clipped
summary is **marked as clipped**, so neither reader mistakes a fragment for
the whole thought, and that the untruncated `verdict.reason` in the payload —
which is what the board actually renders — is never touched.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.room_runner import (
    JOURNAL_SUMMARY_MAX,
    _clip_summary,
    build_journal_entry_for_run,
)


class _Verdict:
    def __init__(self, action: str, reason: str) -> None:
        self.action = action
        self.reason = reason

    def model_dump(self, mode: str = "json") -> dict:
        return {"action": self.action, "reason": self.reason}


class _Run:
    def __init__(self, reason: str) -> None:
        self.id = uuid4()
        self.ticker = "NVDA"
        self.verdict = _Verdict("PASS", reason)
        self.status = "completed"
        self.transcript = []
        self.error_message = None
        self.model_tier = "mid"
        self.mandate_version = 7


# The reported string, reconstructed at the length that produced the cut.
_REPORTED = (
    "The Research Manager and Trader correctly identify a binary risk event "
    "inside the horizon, and the mandate's drawdown cap leaves no room to sit "
    "through it. The bull case rests on a re-rating that the multiple does not "
    "yet support given the 3.05 PEG and the potential for a guide-down at the "
    "next print."
)


def test_the_reported_string_is_actually_long_enough_to_clip() -> None:
    """Vacuity guard. If this fixture were under the cap the whole file would
    pass while proving nothing about clipping."""
    assert len(f"PASS — {_REPORTED}") > JOURNAL_SUMMARY_MAX


def test_a_clipped_summary_says_it_is_clipped() -> None:
    entry = build_journal_entry_for_run(_Run(_REPORTED), uuid4())
    assert entry.summary.endswith("…"), (
        "a clip without a marker asserts that this is the whole thought — "
        "this is the DEF150 line the user photographed"
    )


def test_the_clip_lands_on_a_word_boundary() -> None:
    entry = build_journal_entry_for_run(_Run(_REPORTED), uuid4())
    body = entry.summary.rstrip("…")
    assert body == body.rstrip(), "no dangling space before the ellipsis"
    # The final token must be a word the source actually contains in full.
    assert body.rsplit(" ", 1)[-1] in f"PASS — {_REPORTED}".split()


def test_the_reported_severed_word_cannot_recur() -> None:
    """`"the potential fo"` was the actual cut. Pin it."""
    entry = build_journal_entry_for_run(_Run(_REPORTED), uuid4())
    assert "potential fo…" not in entry.summary
    assert not entry.summary.endswith("fo…")


def test_it_still_respects_the_budget() -> None:
    entry = build_journal_entry_for_run(_Run(_REPORTED), uuid4())
    assert len(entry.summary) <= JOURNAL_SUMMARY_MAX


def test_a_summary_that_fits_is_left_exactly_alone() -> None:
    """No ellipsis on a complete sentence — the marker has to *mean* something
    or it teaches both readers to ignore it."""
    short = "The room split and the PM declined."
    entry = build_journal_entry_for_run(_Run(short), uuid4())
    assert entry.summary == f"PASS — {short}"
    assert "…" not in entry.summary


def test_the_payload_reason_is_never_clipped() -> None:
    """The board renders `verdict.reason` from the payload, not the summary.
    That copy is the full one and must stay full — clipping it would take the
    fix backwards and break the Room/Journal parity the board depends on."""
    entry = build_journal_entry_for_run(_Run(_REPORTED), uuid4())
    assert entry.payload["verdict"]["reason"] == _REPORTED
    assert len(entry.payload["verdict"]["reason"]) > len(entry.summary)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "one",
        "x" * (JOURNAL_SUMMARY_MAX - 1),
        "x" * JOURNAL_SUMMARY_MAX,
        "x" * (JOURNAL_SUMMARY_MAX + 1),  # no space anywhere to break on
        "word " * 200,
    ],
)
def test_the_clip_is_total_over_its_input(text: str) -> None:
    """Including the no-spaces case, where there is no word boundary to find
    and the function must still return something inside the budget rather than
    raise or hand back the whole string."""
    out = _clip_summary(text)
    assert len(out) <= JOURNAL_SUMMARY_MAX
    if len(text) <= JOURNAL_SUMMARY_MAX:
        assert out == text


def test_a_cut_landing_on_punctuation_before_a_space_leaves_no_trailing_space() -> None:
    """DEF163: the original guard's single fixture (`_REPORTED`) has no cut
    point that lands on punctuation-then-space, so it could not catch this.
    `cut.rstrip().rstrip(',;:')` strips the space first — a cut landing on
    `"… ,"` then has its punctuation removed and the space it was hiding
    exposed, leaving `" …"` in text the user reads on the Journal detail
    screen. `('ab , cd ' * 40)` is the row's own reproduction (DEF163)."""
    out = _clip_summary("ab , cd " * 40)
    assert not out.endswith(" …"), "punctuation strip exposed a trailing space"
    assert out.endswith("…")
