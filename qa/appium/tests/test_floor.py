"""Floor tab — Phase 1 smoke coverage. Mechanical scroll/navbar checks live
in test_scroll_overflow.py / test_sheets_navbar.py (cross-cutting); this file
confirms the tab's own key content renders — not just the tab loading, but
the specific things a user would expect to see on it.

Content-depth strings verified against mobile/lib/l10n/app_en.arb:
  floorOmniboxHint       = "Type a ticker — or ask AMI anything…" — the
    persistent Concierge access point. It replaced floorConciergeHeading
    ("AMI CONCIERGE"), which is now a dead key: present in all three ARBs
    and in the generated localizations, referenced by no screen.
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
    hint = LOCALES["en"].strings["floor_omnibox_hint"]
    signals = probe_content(driver, "floor", exact=(hint,), contains=("Daily",))
    assert signals[hint], "Floor should always show the persistent Concierge access point"
    snap(driver, run_dir, "floor", "default")
