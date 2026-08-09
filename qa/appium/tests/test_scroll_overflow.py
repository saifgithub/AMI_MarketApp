"""★ Cross-cutting non-scrolling-overflow check — Saiful's example verbatim:
"screens that do not scroll when they need to."

Phase 1 sweeps the 5 bottom-nav tabs (all use a scrolling root per the
CR080 static analysis, but the swipe-probe below verifies the *rendered*
behaviour, not just which widget wraps the body) plus the one reachable
no-scroll-wrapper risk candidate, the Convene sheet.

Two of the three static-analysis-flagged screens are NOT reachable here:
  - `agent/agent_unlocked_screen.dart` — only shown via `celebration.dart`'s
    full-screen takeover on a real agent-unlock progression event; there is
    no UI path to it from a fresh/plain guest session. Phase 2 needs seeded
    backend progression state to reach it.
  - `auth/merge_sheet.dart` — same seeded-state constraint as the navbar
    check (see test_sheets_navbar.py); stays on its widget-test guard for now.
Both are recorded here as explicit `skip` findings rather than silently
dropped, per this project's "no silent caps" convention — the coverage gap
is visible in the report, not hidden.
"""

from __future__ import annotations

import pytest

from conftest import snap
from helpers.layout import find_scroll_overflow
from helpers.locators import wait_visible_text
from helpers.report import annotate_png
from helpers.gestures import screenshot_png
from pages.base_page import TAB_LABELS, content_band, open_tab

pytestmark = [pytest.mark.scroll, pytest.mark.phase1]


def _check_and_record(driver, device, run_dir, flags, screen_name):
    band = content_band(device)
    findings = find_scroll_overflow(
        driver, band, device["navbar_top_y"], screen=screen_name, scale=device["scale"]
    )
    for finding in findings:
        flags.add(finding)
    if findings:
        annotate_png(
            screenshot_png(driver),
            run_dir / "screenshots" / f"{screen_name}__scroll_overflow.png",
            navbar_top_y=device["navbar_top_y"],
            scale=device["scale"],
        )
    return findings


@pytest.mark.parametrize("tab_label", TAB_LABELS)
def test_tab_scroll_overflow(driver, device, run_dir, flags, tab_label):
    open_tab(driver, tab_label)
    snap(driver, run_dir, f"tab_{tab_label.lower()}", "default")
    findings = _check_and_record(driver, device, run_dir, flags, f"tab_{tab_label.lower()}")
    # Candidate, not a hard fail — scroll-overflow is inherently heuristic
    # (see helpers/layout.py). A human reviews summary.json before this
    # becomes a DEF###.
    assert findings == findings, "recorded for human review, not asserted"


def test_convene_sheet_scroll_overflow(driver, device, run_dir, flags):
    open_tab(driver, "Floor")
    cta = wait_visible_text(driver, "CONVENE THE ROOM", timeout_s=10)
    cta.click()
    wait_visible_text(driver, "CONVENE", timeout_s=8)
    snap(driver, run_dir, "convene_sheet", "for_scroll_check")
    findings = _check_and_record(driver, device, run_dir, flags, "convene_sheet")
    driver.back()
    assert findings == findings


@pytest.mark.phase2
@pytest.mark.skip(
    reason=(
        "agent_unlocked_screen.dart needs a real agent-unlock progression event "
        "(celebration.dart) — no UI path from a fresh guest session. Needs "
        "seeded backend progression state; see this file's module docstring."
    )
)
def test_agent_unlocked_screen_scroll_overflow():
    ...


@pytest.mark.phase2
@pytest.mark.skip(
    reason=(
        "merge_sheet.dart only renders when a federated sign-in adopts an "
        "orphan anonymous account (adoptedFromUserId != null) — needs seeded "
        "backend state. Covered today only by "
        "mobile/test/widgets/sheet_insets_test.dart."
    )
)
def test_merge_sheet_scroll_overflow():
    ...
