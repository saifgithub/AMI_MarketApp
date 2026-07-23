"""Settings tab — Phase 1 smoke coverage. See test_scroll_overflow.py /
test_sheets_navbar.py for the cross-cutting mechanical checks.

Sign-in and Alpaca-connect flows are Phase 2 — they need real credentials
Saiful must supply (see test_data/README.md), never fabricated here.
"""

from __future__ import annotations

import pytest

from conftest import snap
from helpers.locators import wait_visible_text
from pages.base_page import open_tab

pytestmark = [pytest.mark.phase1]


def test_settings_renders_heading(driver, run_dir):
    open_tab(driver, "Settings")
    wait_visible_text(driver, "SETTINGS", timeout_s=10)
    snap(driver, run_dir, "settings", "default")


@pytest.mark.phase2
@pytest.mark.skip(reason="needs a test-email inbox for the sign-in email-code path — see test_data/README.md")
def test_sign_in_email_code_flow():
    ...


@pytest.mark.phase2
@pytest.mark.skip(reason="needs a real Alpaca paper-trading API key/secret — see test_data/README.md")
def test_alpaca_connect_flow():
    ...
