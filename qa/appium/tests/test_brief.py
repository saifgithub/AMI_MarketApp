"""Brief journey (UAT-BRIEF-016): an unlocked agent's Brief screen opens and its
version history shows the edit limit - no chat turn, no LLM (CR263).

A Brief is only reachable for an UNLOCKED agent, and a fresh account has none:
the app unlocks the Fundamentals Analyst after its five gateway lessons. So the
precondition is earned the way a user earns it - through the same lesson reader
and quiz UAT-LESS-010 drives - rather than seeded. It costs ~5 quizzes on the
first run of an account and nothing after.
"""

from __future__ import annotations

import re
import time

import pytest

from conftest import snap
from helpers import lesson_steps
from helpers.firm_steps import open_your_firm
from helpers.journeys import close_sheet, go_back, settle, tap_button, tap_contains, tap_text, wait_any_text
from helpers.locators import exists_text, exists_text_contains, wait_visible_text, wait_visible_text_contains

pytestmark = [pytest.mark.phase2]

_PASSED_OF = re.compile(r"(\d+)\s*/\s*5 gateway lessons passed")


def _gateway_rows(driver) -> list:
    """The gateway lesson rows in the locked sheet, top to bottom."""
    ns = lesson_steps.nodes(driver)
    start = next((n for n in ns if n.label == "Tap a lesson to start"), None)
    end = next((n for n in ns if n.label == "GO TO LESSONS"), None)
    assert start and end, "the locked sheet does not list its gateway lessons"
    return sorted((n for n in ns if start.y < n.y < end.y and "\n" in n.label), key=lambda n: n.y)


def _passed_count(driver) -> int:
    for n in lesson_steps.nodes(driver):
        m = _PASSED_OF.search(n.label)
        if m:
            return int(m.group(1))
    raise AssertionError("the locked sheet shows no 'N / 5 gateway lessons passed' progress")


def _open_agent(driver, tile: str) -> str:
    """Open the agent's tile; returns 'locked' or 'unlocked'."""
    open_your_firm(driver)
    tap_text(driver, tile)
    seen = wait_any_text(driver, ["HOW TO UNLOCK", "1-ON-1"], timeout_s=10, contains=True)
    return "locked" if seen == "HOW TO UNLOCK" else "unlocked"


def _earn_the_agent(driver, tile: str, run_dir) -> None:
    for _ in range(7):
        if _open_agent(driver, tile) == "unlocked":
            return
        done = _passed_count(driver)
        rows = _gateway_rows(driver)
        assert len(rows) >= 5 and done < 5, f"locked agent with {done}/5 passed and {len(rows)} rows"
        print(f"    [brief] {done}/5 gateway lessons passed - passing {rows[done].label.splitlines()[0]!r}")
        tap_contains(driver, rows[done].label.splitlines()[0])
        time.sleep(3.0)
        lesson_steps.read_to_end(driver)
        lesson_steps.pass_quiz(driver)
        snap(driver, run_dir, "brief_gateway", f"passed_{done + 1}")
        if exists_text(driver, "Later", retry=False):
            tap_button(driver, "Later", timeout_s=5)  # the unlock celebration
        elif exists_text_contains(driver, "BACK TO LESSONS", retry=False):
            tap_button(driver, "BACK TO LESSONS", timeout_s=5)
        else:
            go_back(driver)
        time.sleep(2.0)
    raise AssertionError("the agent did not unlock after seven gateway passes")


@pytest.mark.uat("UAT-BRIEF-016")
def test_brief_screen_opens_and_history_shows_the_edit_limit(driver, run_dir):
    _earn_the_agent(driver, "FUND", run_dir)

    # unlocked: the chooser sheet offers 1-ON-1 and BRIEF
    snap(driver, run_dir, "brief", "chooser")
    tap_contains(driver, "Tell the agent how to think")
    wait_visible_text_contains(driver, "BRIEF FUNDAMENTALS ANALYST", timeout_s=20)
    settle(driver, 2.0)
    snap(driver, run_dir, "brief", "screen")
    assert exists_text_contains(driver, "No overlay yet", retry=False) or exists_text_contains(
        driver, "Overlay v", retry=False
    ), "the Brief header should say whether an overlay is active"

    tap_text(driver, "Version history", timeout_s=8)
    wait_visible_text_contains(driver, "HISTORY", timeout_s=15)
    wait_visible_text_contains(driver, "edits made", timeout_s=15)
    snap(driver, run_dir, "brief", "history")
    text = next(
        (n.label for n in lesson_steps.nodes(driver) if "edits made" in n.label), ""
    )
    assert re.search(r"\d+ edits? made", text) and re.search(r"(\d+ remaining|unlimited)", text), (
        f"the history header must show the edit limit, got {text!r}"
    )
    go_back(driver)
    go_back(driver)
