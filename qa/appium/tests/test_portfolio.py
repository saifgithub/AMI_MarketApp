"""Portfolio tab — Phase 1 smoke coverage. See test_scroll_overflow.py /
test_sheets_navbar.py for the cross-cutting mechanical checks.

Content-depth strings verified against mobile/lib/l10n/app_en.arb:
  portfolioTotalValue = "TOTAL VALUE"
  portfolioCash        = "CASH"
Both live in the summary header (portfolio_screen.dart _Header/summary,
rendered above the scrollable body) — unconditional, hard-asserted.
  portfolioDrawdown = "Drawdown: {pct}%" — only meaningful once there's
trade history, so it's logged via probe_content, not asserted: a new/empty
portfolio legitimately won't show it.
"""

from __future__ import annotations

import pytest

from conftest import snap
from helpers.locators import wait_visible_text
from pages.base_page import open_tab, probe_content

pytestmark = [pytest.mark.phase1]


def test_portfolio_renders_heading(driver, run_dir):
    # Wait on the pane's own content, NOT on "PORTFOLIO".
    #
    # That string is the bottom-nav tab's label as well as the screen heading,
    # so the wait was satisfied by the tab the moment it was tapped — before
    # the screen behind it had rendered a single frame. The probes underneath
    # then ran against the previous tab and reported TOTAL VALUE and CASH
    # missing, which reads exactly like an app defect. Measured on the rig
    # device: with a 2.5s pause after `open_tab`, both strings are present and
    # exact-match. Nothing was wrong with the app.
    #
    # A locator that can be satisfied by the control you used to navigate is
    # not a readiness signal. `TOTAL VALUE` appears only on this screen.
    open_tab(driver, "Portfolio")
    wait_visible_text(driver, "TOTAL VALUE", timeout_s=10)
    signals = probe_content(driver, "portfolio", exact=("TOTAL VALUE", "CASH"), contains=("Drawdown",))
    assert signals["TOTAL VALUE"], "Portfolio summary header should always show TOTAL VALUE"
    assert signals["CASH"], "Portfolio summary header should always show CASH"
    snap(driver, run_dir, "portfolio", "default")
