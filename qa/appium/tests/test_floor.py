"""Floor tab — Phase 1 smoke coverage. Mechanical scroll/navbar checks live
in test_scroll_overflow.py / test_sheets_navbar.py (cross-cutting); this file
confirms the tab's own key content renders — not just the tab loading, but
the specific things a user would expect to see on it.

Content-depth strings verified against mobile/lib/l10n/app_en.arb:
  floorOmniboxCaption = "A ticker convenes your team, or open Company Review first. Anything else, AMI
    answers." — the omnibox's own caption, and the stable proof that the
    persistent Concierge access point is on screen. It stands in for
    floorConciergeHeading ("AMI CONCIERGE"), now a dead key: present in all
    three ARBs and in the generated localizations, referenced by no screen.
    NOT floorOmniboxHint — that is a TextField placeholder, and Android does
    not surface hint text in the accessibility tree, so asserting it would be
    unsatisfiable for a second, subtler reason. Dumped the live tree to pick
    this rather than guessing again.
  floorConveneCta        = "CONVENE THE ROOM"
The daily-challenge card's heading isn't a static string — it's a literal
'Daily · ${date}' built in daily_challenge_card.dart — so that check is
textContains("Daily") and logged only, not hard-asserted: the card doesn't
always render (no challenge available is a legitimate empty state, not a
usability bug).
"""

from __future__ import annotations

import pytest

from conftest import snap
from helpers.locators import wait_visible_text
from config.locales import LOCALES
from pages.base_page import open_tab, probe_content

pytestmark = [pytest.mark.phase1]


def test_floor_renders_convene_cta(driver, run_dir):
    open_tab(driver, "Floor")
    wait_visible_text(driver, "CONVENE THE ROOM", timeout_s=10)
    # The persistent Concierge access point is the omnibox now, not a heading.
    # `AMI CONCIERGE` (floorConciergeHeading) was what this asserted, and that
    # key is dead: it is still in all three ARBs and in the generated
    # localizations, but no screen references it — so the assertion could not
    # pass no matter how healthy the app was. Caught by a live run, not by a
    # test, which is the DEF250 pattern a second time; the mechanical dead-key
    # check now lives in tests_offline/test_locales_match_arb.py.
    caption = LOCALES["en"].strings["floor_omnibox_caption"]
    signals = probe_content(driver, "floor", exact=(caption,), contains=("Daily",))
    assert signals[caption], "Floor should always show the persistent Concierge access point"
    snap(driver, run_dir, "floor", "default")


# --------------------------------------------------------------------------
# CR263 journeys
# --------------------------------------------------------------------------

import time  # noqa: E402

from helpers.journeys import (  # noqa: E402
    close_sheet,
    go_back,
    scroll_up,
    scroll_until_text,
    tap_contains,
    tap_text,
    wait_any_text,
)
from helpers.locators import (  # noqa: E402
    _all_by_text,
    _all_by_text_contains,
    exists_id,
    exists_text,
    exists_text_contains,
    wait_visible_text_contains,
)
from config.semantics_ids import NAV_IDS  # noqa: E402

# the firm wall shows each trading agent under its CR160 title
_FIRM_TITLES = (
    "Chief Investment Officer",
    "Risk Officer — Balanced",
    "Execution Desk",
    "Technical Strategist",
    "Flow & Positioning",
    "Macro & Events",
    "Fundamentals Analyst",
)
_TILES = ("FUND", "TECH", "MACRO", "FLOW", "BULL", "BEAR", "RES-M", "AGG", "CON", "BAL", "EXEC")


from helpers.firm_steps import open_your_firm  # noqa: E402


@pytest.mark.uat("UAT-FLOOR-007")
def test_your_firm_lists_twelve_agents_and_a_locked_one_opens_its_unlock_sheet(driver, run_dir):
    open_your_firm(driver)
    snap(driver, run_dir, "your_firm", "wall")
    wait_visible_text_contains(driver, "seats filled", timeout_s=5)
    missing = [t for t in _FIRM_TITLES if not exists_text(driver, t)]
    assert not missing, f"the firm wall is missing agents: {missing}"

    # open locked agents until one shows the unlock sheet (an agent a previous run
    # unlocked opens the 1-ON-1 / BRIEF chooser instead, which is not what is under test)
    opened = None
    for tile in _TILES:
        if not exists_text(driver, tile, retry=False):
            continue
        tap_text(driver, tile)
        seen = wait_any_text(driver, ["HOW TO UNLOCK", "1-ON-1"], timeout_s=8, contains=True)
        if seen == "HOW TO UNLOCK":
            opened = tile
            break
        close_sheet(driver)
        time.sleep(0.5)
    assert opened, "every agent is unlocked on this account - there is no locked agent to open"
    snap(driver, run_dir, "your_firm", "locked_sheet")
    wait_visible_text_contains(driver, "gateway lessons passed", timeout_s=5)
    wait_visible_text(driver, "GO TO LESSONS", timeout_s=5)
    assert exists_text_contains(driver, "Pass these", retry=False), "the sheet must list the gateway lessons to pass"
    close_sheet(driver)
    wait_visible_text_contains(driver, "unlocked. Tap a locked hex", timeout_s=5)
    go_back(driver)


@pytest.mark.uat("UAT-FLOOR-008")
def test_inbox_bell_opens_inbox_with_the_bottom_bar_still_visible(driver, run_dir):
    open_tab(driver, "Floor")
    wait_visible_text(driver, "CONVENE THE ROOM", timeout_s=15)
    scroll_up(driver, times=2)
    bell = None
    deadline = time.monotonic() + 15
    while bell is None and time.monotonic() < deadline:
        found = _all_by_text(driver, "Messages", retry=False) or _all_by_text_contains(
            driver, "unread message", retry=False
        )
        bell = found[0] if found else None
        if bell is None:
            time.sleep(0.5)
    assert bell is not None, "the Floor header has no inbox bell (labelled 'Messages' / 'N unread messages')"
    bell.click()
    wait_visible_text(driver, "MESSAGES", timeout_s=15)
    snap(driver, run_dir, "inbox", "opened")
    # DEF457: the inbox lives inside the tab navigator, so the bar is still there
    for tab in ("Floor", "Portfolio", "Lessons", "You"):
        assert exists_id(driver, NAV_IDS[tab], retry=False), f"bottom-bar tab {tab} is hidden behind the inbox (DEF457)"
    go_back(driver)
    wait_visible_text(driver, "CONVENE THE ROOM", timeout_s=10)
