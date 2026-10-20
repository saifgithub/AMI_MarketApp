"""Journal tab — Phase 1 smoke coverage. See test_scroll_overflow.py /
test_sheets_navbar.py for the cross-cutting mechanical checks.

Content-depth strings verified against mobile/lib/l10n/app_en.arb (all 7
filter chips: journalFilterAll/Room/Trade/OneOnOne/Brief/Lessons/Unlocks —
"ALL" is the default/always-first chip, hard-asserted; the other six are
logged only, since a narrow screen could wrap/clip the chip row without that
being this test's concern (that's exactly what test_scroll_overflow.py
checks for). journalEmptyTitle = "No entries yet." and journalSearchHint =
"Search entries…" are logged, not asserted — a fresh anonymous session is
the expected empty state, but this test shouldn't assume no prior journal
activity exists on whatever session it runs against.
"""

from __future__ import annotations

import os
import time

import pytest
from selenium.common.exceptions import NoSuchElementException

from conftest import snap
from helpers import sim_steps
from helpers.journeys import scroll_until_text, scroll_up, settle, tap_button
from helpers.locators import wait_visible_text, wait_visible_text_contains
from pages.base_page import open_you_segment, probe_content

pytestmark = [pytest.mark.phase1]

_FILTER_CHIPS = ("ALL", "ROOM", "TRADE", "1-ON-1", "BRIEF", "LESSONS", "UNLOCKS")


def test_journal_renders_heading(driver, run_dir):
    # CR133 moved JOURNAL off the bottom nav into a YOU segment, so
    # `open_tab(driver, "Journal")` asserts out before reaching the device.
    #
    # `DECISION JOURNAL` cannot be the readiness wait any more either: an
    # embedded JournalScreen renders its AmiScreenHeader only `if
    # (!widget.embedded)`, so `journalHeading` is not on screen at all here —
    # the segment button says `JOURNAL`. The `_FilterRow` is the first thing in
    # the embedded pane's own Column, so its default `ALL` chip is what tells
    # us the pane is up.
    open_you_segment(driver, "Journal")
    wait_visible_text(driver, "ALL", timeout_s=10)
    signals = probe_content(
        driver,
        "journal",
        exact=_FILTER_CHIPS,
        contains=("No entries yet.", "Search"),
    )
    assert signals["ALL"], "Journal should always show the default ALL filter chip"
    snap(driver, run_dir, "journal", "default")


@pytest.mark.uat("UAT-JRNL-008")
def test_trade_and_blocked_order_are_journalled(driver, run_dir):
    """The Decision Journal is the user's record of what the desk did. A fill and
    a refusal must both be in it, the refusal with its reason — a journal that
    only remembers the wins would teach the wrong lesson.

    Both entries are the NEWEST, so they are on the first screen: nothing here
    scrolls or waits long, because on iOS the Journal's accessibility tree goes
    dark within seconds of opening (see the xfail finding below)."""
    bought = sim_steps.STATE.get("bought")
    if bought is None:
        pytest.skip(
            "PRECONDITION: no fill was placed earlier in this run (UAT-SIM-028 ran in a "
            "different run, or was skipped on the daily trade cap), so the newest journal "
            "entries are not this test's. Run test_trading.py first."
        )
    try:
        sim_steps.place_refused_order(driver)
    finally:
        sim_steps.cancel_ticket(driver)

    # The tree dies within seconds of opening (finding below), so look quickly, and
    # reopen once on a fresh relaunch if it was already gone when we arrived.
    last = None
    for _attempt in range(3):
        settle(driver, 0.5)  # relaunches if the tree is dark
        open_you_segment(driver, "Journal")
        try:
            wait_visible_text_contains(driver, f"BLOCKED: BUY {sim_steps.REFUSAL_QUANTITY} {sim_steps.REFUSAL_TICKER}", timeout_s=6)
            wait_visible_text_contains(driver, "single-name cap", timeout_s=3)
            wait_visible_text_contains(driver, f"BUY 1 {bought[0]} @", timeout_s=3)
            snap(driver, run_dir, "journal", "trade_and_blocked")
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            snap(driver, run_dir, "journal", f"attempt_{_attempt}")
    raise last


@pytest.mark.uat("UAT-JRNL-008")
@pytest.mark.xfail(
    os.environ.get("AMI_PLATFORM") == "ios",
    strict=False,
    raises=(AssertionError, NoSuchElementException),
    reason=(
        "FINDING: on iOS the Journal's accessibility tree goes dark (1 node) ~5-8s after "
        "You > Journal opens once it holds entries — no interaction needed. A VoiceOver "
        "user loses the screen; every locator misses. Same family as DEF466."
    ),
)
def test_journal_stays_readable_while_open(driver, run_dir):
    from helpers.shell import tree_is_dark

    open_you_segment(driver, "Journal")
    time.sleep(12)
    snap(driver, run_dir, "journal", "after_12s")
    assert not tree_is_dark(driver), "the Journal's accessibility tree collapsed while the screen sat open"
