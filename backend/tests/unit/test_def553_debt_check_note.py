"""DEF553 — the verdict states the debt check's numbers itself.

The CIO's narration is an LLM and dropped the horizon, the cover and the minimum even though the
check stood (CR285 acceptance 3). The runner now ends the verdict reason and the Room text with one
AMI note built from the check's fields. Covers: stands and covered wording with the three numbers,
the no-schedule and nothing-due sentences, the desk's horizon wording, no note (and an untouched
reason) when no check ran or it was skipped, once-only when the narration already quoted it, RM on
a Bursa Room, and the grader version tag that keeps Rooms banked without the note from being served.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.services import room_runner
from app.schemas.room import Verdict, VerdictAction
from app.services.room_graders import terminal_materiality as M
from app.services.room_runner import _append_debt_check_note
from tests.unit import test_cr267_wp23_coded_rule as coded
from tests.unit.test_cr285_debt_coverage import _inputs, _yes

Q = coded.Q
coded_on = coded.coded_on

STANDS = _inputs(
    {"ladder": [["Within 1 year", 1569.0]], "total_cash": 62.0, "fcf_ttm": 0.0},
    months=60, minimum=3.0,
)
COVERED = _inputs(
    {"ladder": [["Within 1 year", 100.0]], "total_cash": 154.0, "fcf_ttm": 0.0},
    months=24, minimum=1.0,
)
NO_LADDER = _inputs({"ladder": [], "total_cash": 154.0, "fcf_ttm": 0.0}, months=24, minimum=1.0)
NOTHING_DUE = _inputs(
    {"ladder": [["Year 5", 900.0]], "total_cash": 154.0, "fcf_ttm": 0.0}, months=12, minimum=1.0,
)
DESK = _inputs(
    {"ladder": [["Within 1 year", 1569.0]], "total_cash": 62.0, "fcf_ttm": 0.0},
    desk=1000, months=24, minimum=3.0,
)
SKIPPED = _inputs(
    {"ladder": [["Within 1 year", 1569.0]], "total_cash": 62.0, "fcf_ttm": 0.0},
    desk=None, months=None, minimum=3.0,
)

NARRATION = json.dumps({"action": "PASS", "narration": "CIO: the maturity wall is the problem."})


def _result(inputs, category="debt_default"):
    base = coded.result_for(coded.CLEAR)
    if inputs is None:
        return base
    answers = tuple(a for a in base.answers if a.question is not Q.TERMINAL_VULNERABILITY)
    return replace(base, answers=answers + (M.apply_materiality(_yes(category), inputs),))


class Grader(coded.FakeGrader):
    def __init__(self, inputs, category="debt_default", **kw):
        super().__init__(**kw)
        self._inputs, self._category = inputs, category

    def grade(self, transcript):
        self.seen.append(transcript)
        return _result(self._inputs, self._category)


def _room(inputs, replies=(NARRATION,), category="debt_default"):
    out, _ = coded.convene(list(replies), grader=Grader(inputs, category))
    return out


def _check(inputs):
    return M.debt_default_check(inputs)


def test_a_standing_check_puts_horizon_cover_and_minimum_in_the_verdict(coded_on):
    out = _room(STANDS)
    v = out["verdict"]
    note = (
        "[AMI debt check: $1,569M falls due within your 60-month horizon; cash and cash flow "
        "cover 0.04×, below your minimum of 3.00×, so the debt risk counts against this trade.]"
    )
    assert v.action == "PASS"
    assert v.reason.endswith(f"\n\n{note}") and v.reason.count("AMI debt check") == 1
    assert out["pm_text"].endswith(note) and out["pm_text"].count("AMI debt check") == 1
    assert "debt_default" not in v.reason and "the AI" not in v.reason


def test_a_covered_check_says_covered_with_the_numbers(coded_on):
    v = _room(COVERED, replies=(coded._PM_APPROVE,))["verdict"]
    assert v.action == "APPROVE"
    assert v.reason.endswith(
        "[AMI debt check: $100M falls due within your 24-month horizon; cash and cash flow "
        "cover 1.54×, at or above your minimum of 1.00×, so the debt risk was not counted.]"
    )


def test_no_schedule_and_nothing_due_each_get_one_plain_sentence():
    assert M.verdict_note(_check(NO_LADDER)) == (
        "AMI debt check: no debt-maturity schedule is available for this company, so a "
        "debt-default risk could not be counted."
    )
    assert M.verdict_note(_check(NOTHING_DUE)) == (
        "AMI debt check: no principal falls due within your 12-month horizon, so the debt risk "
        "was not counted."
    )


def test_the_desks_longer_horizon_is_named_as_such():
    note = M.verdict_note(_check(DESK))
    assert "within the desk's 1000-day horizon (longer than your 24-month setting)" in note
    assert "below your minimum of 3.00×" in note


def test_an_offline_check_without_the_users_minimum_says_the_minimum_not_yours():
    note = M.verdict_note(_check({
        "ladder": [["Within 1 year", 100.0]], "total_cash": 154.0, "fcf_ttm": 0.0,
        "horizon_days": 42,
    }))
    assert "the 42-day horizon" in note and "at or above the minimum of 1.00×" in note


@pytest.mark.parametrize("inputs", [None, SKIPPED])
def test_no_check_or_a_skipped_one_adds_no_note_and_leaves_the_reason_alone(
    coded_on, monkeypatch, inputs,
):
    out = _room(inputs, replies=(coded._PM_APPROVE,))
    monkeypatch.setattr(room_runner, "_append_debt_check_note", lambda t, v, r, k: (t, v))
    before = _room(inputs, replies=(coded._PM_APPROVE,))
    assert out["verdict"].reason == before["verdict"].reason
    assert out["pm_text"] == before["pm_text"]
    assert "AMI debt check" not in out["verdict"].reason


def test_a_terminal_answer_in_another_category_adds_no_note(coded_on):
    out = _room(COVERED, replies=(coded._PM_PASS,), category="regulatory")
    assert "AMI debt check" not in out["verdict"].reason


def test_a_note_the_narration_already_quoted_is_not_repeated():
    note = M.verdict_note(_check(STANDS))
    verdict = Verdict(action=VerdictAction.PASS, reason=f"CIO says.\n\n[{note}]")
    text, out = _append_debt_check_note(f"Room.\n\n[{note}]", verdict, _result(STANDS), "AAPL")
    assert out.reason.count("AMI debt check") == 1 and text.count("AMI debt check") == 1


def test_appending_twice_adds_the_note_once():
    verdict = Verdict(action=VerdictAction.PASS, reason="CIO says.")
    text, v1 = _append_debt_check_note("Room.", verdict, _result(STANDS), "AAPL")
    text, v2 = _append_debt_check_note(text, v1, _result(STANDS), "AAPL")
    assert v2.reason.count("AMI debt check") == 1 and text.count("AMI debt check") == 1


def test_a_bursa_rooms_money_is_in_ringgit():
    verdict = Verdict(action=VerdictAction.PASS, reason="CIO says.")
    _, v = _append_debt_check_note("Room.", verdict, _result(STANDS), "1155.KL")
    assert "RM1,569M falls due" in v.reason and "$" not in v.reason


def test_the_check_revision_is_bumped_so_rooms_banked_without_the_note_are_not_served():
    assert M.CHECK_TAG == "termchk=d3"
