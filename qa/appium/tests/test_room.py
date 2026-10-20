"""Room journey (UAT-ROOM-016): convene the Room on AAPL and watch it stream to a
verdict card with a decision (CR263).

ONE real Room run per suite run — it spends the account's Room credits and the
on-prem LLM. A fresh account (see test_onboarding.py) has 13 credits against an
8-credit Room, so a second run on the same account would hit the paywall; the
test says so in those words instead of reporting a Room failure.

What "worked" means to a user, and so what is asserted: the sheet states the
price and the balance BEFORE anything is charged; the Room opens on the ticker;
it ends on a verdict card whose hero line carries a decision (approved / passed /
blocked by the mandate) - not on an error card, an offline notice or "no verdict".
"""

from __future__ import annotations

import re
import time

import pytest
from _pytest.outcomes import Failed

from conftest import snap
from helpers.journeys import go_back, settle, tap_button
from helpers.locators import exists_id, exists_text, exists_text_contains, wait_visible_text, wait_visible_text_contains
from helpers.shell import shell_is_up
from config.locales import LOCALES
from config.semantics_ids import NAV_BACK
from pages.base_page import open_tab

pytestmark = [pytest.mark.phase2]

_PRICE_LINE = re.compile(r"Room:\s*(\d+)\s*credits?\s*\W+\s*you have\s*(\d+)")
_DECISIONS = ("THE ROOM APPROVED", "THE ROOM PASSED", "BLOCKED BY YOUR MANDATE")
_FAILURES = (
    "THE ROOM DID NOT FINISH",
    "NO VERDICT ISSUED",
    "Room ended without a verdict",
    "briefly offline",
    "Out of Room credits",
    "Reconnect timed out",
)
_BUDGET_S = 600


def _leave_room(driver) -> None:
    floor = LOCALES["en"].tab_labels["Floor"]
    for _ in range(6):
        if shell_is_up(driver, floor):
            return
        if exists_text(driver, "CLOSE", retry=False):
            tap_button(driver, "CLOSE", timeout_s=3)
        elif exists_id(driver, NAV_BACK, retry=False):
            go_back(driver)
        else:
            driver.back()
        time.sleep(1.5)


@pytest.mark.uat("UAT-ROOM-016")
@pytest.mark.llm
@pytest.mark.xfail(
    strict=False,
    raises=(AssertionError, Failed),
    reason=(
        "FINDING: the Room screen gives up mid-run - 'Reconnect timed out. The run is still saved - "
        "check Journal.' - after ~6-10 minutes while the server is still running it (2 of 2 runs on "
        "2026-10-20: 0/4 analysts reported in one, 4/4 then 0/3 researchers in the other; run 1 was "
        "refunded as a NO_VERDICT outage). DEF467 family: long silent stream, no keepalive/resume. "
        "The shared on-prem vLLM was also slow (every 180s agent timeout fell back to scripted)."
    ),
)
def test_convene_aapl_streams_to_a_verdict_card_with_a_decision(driver, run_dir):
    open_tab(driver, "Floor")
    wait_visible_text(driver, "CONVENE THE ROOM", timeout_s=15)
    tap_button(driver, "CONVENE THE ROOM", timeout_s=10)
    wait_visible_text(driver, "OR PICK ONE", timeout_s=15)
    snap(driver, run_dir, "room", "convene_sheet")

    # the price and the balance are stated before anything is charged
    line = wait_visible_text_contains(driver, "Room:", timeout_s=10)
    text = line.get_attribute("label") or line.text or ""
    match = _PRICE_LINE.search(text)
    assert match, f"the Convene sheet must state the Room price and the credit balance, got {text!r}"
    price, have = int(match.group(1)), int(match.group(2))
    print(f"    [room] price {price} credits, balance {have}")
    if have < price:
        pytest.fail(
            f"PRECONDITION: the account has {have} credits and a Room costs {price}; this is the "
            "paywall, not a Room failure. A fresh account (test_onboarding.py runs first) has 13."
        )

    tap_button(driver, "AAPL", timeout_s=8)
    tap_button(driver, "CONVENE", timeout_s=8)
    started = time.monotonic()

    try:
        outcome = None
        deadline = started + _BUDGET_S
        while time.monotonic() < deadline:
            for marker in _FAILURES:
                if exists_text_contains(driver, marker, retry=False):
                    snap(driver, run_dir, "room", "failed")
                    pytest.fail(f"the Room ended without a verdict: {marker!r} after {time.monotonic() - started:.0f}s")
            for marker in _DECISIONS:
                if exists_text_contains(driver, marker, retry=False):
                    outcome = marker
                    break
            if outcome:
                break
            time.sleep(4.0)
        snap(driver, run_dir, "room", "verdict" if outcome else "timeout")
        assert outcome, f"no verdict card with a decision within {_BUDGET_S}s"
        print(f"    [room] verdict after {time.monotonic() - started:.0f}s: {outcome}")
        assert exists_text_contains(driver, "AAPL", retry=False), "the verdict should be about AAPL"
        assert exists_text_contains(driver, "CHIEF INVESTMENT OFFICER", retry=False) or exists_text_contains(
            driver, "CIO", retry=False
        ), "the verdict card should be the CIO's"
        # the cost line states what the Room cost (or that it was not charged)
        settle(driver, 1.0)
        assert exists_text_contains(driver, "This Room used", retry=False) or exists_text_contains(
            driver, "Not charged", retry=False
        ), "the Room must say what it cost"
    finally:
        _leave_room(driver)
