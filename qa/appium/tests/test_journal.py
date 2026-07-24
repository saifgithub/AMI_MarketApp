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

import pytest

from conftest import snap
from helpers.locators import wait_visible_text
from pages.base_page import open_tab, probe_content

pytestmark = [pytest.mark.phase1]

_FILTER_CHIPS = ("ALL", "ROOM", "TRADE", "1-ON-1", "BRIEF", "LESSONS", "UNLOCKS")


def test_journal_renders_heading(driver, run_dir):
    open_tab(driver, "Journal")
    wait_visible_text(driver, "DECISION JOURNAL", timeout_s=10)
    signals = probe_content(
        driver,
        "journal",
        exact=_FILTER_CHIPS,
        contains=("No entries yet.", "Search"),
    )
    assert signals["ALL"], "Journal should always show the default ALL filter chip"
    snap(driver, run_dir, "journal", "default")
