"""Watchlist + price-alert journeys (UAT-WATCH-013, UAT-WATCH-014) — what the user
sees after adding a ticker to the watchlist and after setting a price alert (CR263).

Both clean up after themselves: the account is persistent, and a watchlist or an
alert list that only ever grows would make the next run's "it appears" assertion
pass on yesterday's leftovers.
"""

from __future__ import annotations

import time

import pytest

from conftest import snap
from helpers import lesson_steps
from helpers.gestures import tap_xy
from helpers.journeys import (
    close_sheet,
    dismiss_keyboard,
    drag,
    fill_field,
    go_back,
    hdrag,
    on_screen,
    scroll_down,
    scroll_until_text,
    settle,
    tap_button,
    tap_contains,
    tap_text,
)
from helpers.locators import (
    _all_by_text_contains,
    exists_text,
    exists_text_contains,
    wait_visible_text,
    wait_visible_text_contains,
)
from helpers.sim_steps import open_portfolio

pytestmark = [pytest.mark.phase2]

_WATCH_CANDIDATES = ("GOOGL", "AMZN", "META", "AMD", "MSFT", "KO", "T")


def _watch_rows(driver) -> dict[str, "lesson_steps.Node"]:
    """Watchlist rows on screen: ticker -> node (a row is a wide card labelled 'TICKER\\n$price...')."""
    rows = {}
    for n in lesson_steps.nodes(driver):
        head = n.label.split("\n")[0]
        if n.w >= 300 and n.h >= 40 and head.isalpha() and head.isupper() and len(head) <= 5 and "$" in n.label:
            rows[head] = n
    return rows


def _wait_snackbar_gone(driver) -> None:
    """The 'Removed from watchlist - UNDO' snackbar outlives the swipe by ~10s and
    sits where a sheet's primary button will be: a tap there presses UNDO."""
    deadline = time.monotonic() + 20
    while exists_text_contains(driver, "Removed from watchlist", retry=False) and time.monotonic() < deadline:
        time.sleep(1.0)
    if exists_text_contains(driver, "Removed from watchlist", retry=False):
        drag(driver, 0.5, 0.78, 0.98)  # with accessibility on, the snackbar stays until swiped away
        time.sleep(1.0)


def _open_watchlist(driver) -> None:
    settle(driver, 0.5)  # relaunches if the accessibility tree has gone dark
    open_portfolio(driver)
    tap_contains(driver, "HISTORY")
    time.sleep(2.0)
    scroll_until_text(driver, "WATCHLIST", max_scrolls=10)
    wait_visible_text(driver, "WATCHLIST", timeout_s=5)
    scroll_down(driver)  # the header sits on the fold: bring the rows above it
    scroll_down(driver)
    time.sleep(1.0)


@pytest.mark.uat("UAT-WATCH-013")
def test_adding_a_ticker_lists_it_in_the_watchlist_and_removing_takes_it_off(driver, run_dir):
    _open_watchlist(driver)
    present = _watch_rows(driver)
    ticker = next((t for t in _WATCH_CANDIDATES if t not in present), None)
    assert ticker, f"all watch candidates are already on the list: {sorted(present)}"

    tap_button(driver, "ADD", timeout_s=8)
    wait_visible_text(driver, "ADD TO WATCHLIST", timeout_s=8)
    fill_field(driver, "Ticker", ticker)
    # the keyboard's Done key submits the dialog (the ADD button does the same)
    dismiss_keyboard(driver)
    deadline = time.monotonic() + 25
    while exists_text(driver, "ADD TO WATCHLIST", retry=False) and time.monotonic() < deadline:
        time.sleep(1.0)  # the dialog validates the ticker with the backend, then closes
    if exists_text(driver, "ADD TO WATCHLIST", retry=False):
        tap_button(driver, "ADD", timeout_s=5, topmost=True)  # Done did not submit: press ADD itself
        deadline = time.monotonic() + 25
        while exists_text(driver, "ADD TO WATCHLIST", retry=False) and time.monotonic() < deadline:
            time.sleep(1.0)
    assert not exists_text(driver, "ADD TO WATCHLIST", retry=False), (
        f"the add dialog never closed for {ticker} (validation did not complete or was refused)"
    )
    time.sleep(1.5)
    settle(driver, 1.0)
    _open_watchlist(driver)
    snap(driver, run_dir, "watchlist", "after_add")
    rows = _watch_rows(driver)
    assert ticker in rows, f"{ticker} was added but is not on the watchlist: {sorted(rows)}"

    # remove it by swiping the row away
    hdrag(driver, rows[ticker].cy, 0.9, 0.1)
    time.sleep(2.0)
    snap(driver, run_dir, "watchlist", "after_remove")
    gone = False
    for _ in range(6):
        if ticker not in _watch_rows(driver):
            gone = True
            break
        time.sleep(1.0)
    assert gone, f"{ticker} is still on the watchlist after being swiped away"
    _wait_snackbar_gone(driver)


@pytest.mark.uat("UAT-WATCH-014")
def test_price_alert_appears_on_the_ticker_and_can_be_cancelled(driver, run_dir):
    _wait_snackbar_gone(driver)
    open_portfolio(driver)
    tap_contains(driver, "POSITIONS")  # the tab the last visit left selected may be HISTORY
    time.sleep(2.0)
    if not exists_text(driver, "PER-LOT DETAIL", retry=False):
        rows = [n for n in lesson_steps.nodes(driver) if " sh · " in n.label and n.h > 0]
        for _ in range(4):
            if rows:
                break
            scroll_down(driver)
            time.sleep(1.0)
            rows = [n for n in lesson_steps.nodes(driver) if " sh · " in n.label and n.h > 0]
        assert rows, "the account holds nothing - there is no ticker detail to open (run UAT-SIM-028 first)"
        first = min(rows, key=lambda n: n.y)
        tap_xy(driver, first.x + first.w // 2, first.cy)
        time.sleep(2.5)
    scroll_until_text(driver, "PER-LOT DETAIL", max_scrolls=8)
    time.sleep(1.0)
    tap_text(driver, "PER-LOT DETAIL", timeout_s=8)
    time.sleep(3.0)
    drag(driver, 0.5, 0.75, 0.30)
    time.sleep(1.2)
    tap_text(driver, "ALERT", timeout_s=10)
    wait_visible_text_contains(driver, "Set price alert", timeout_s=10)
    tap_button(driver, "Price falls below", timeout_s=5)
    # a price no earlier alert can share, so "it is gone" cannot be satisfied by a leftover twin
    price = f"{0.11 + (int(time.time()) % 80) / 100:.2f}"
    label = f"Price falls below ${price}"
    fill_field(driver, "Price", price)
    snap(driver, run_dir, "price_alert", "sheet_filled")
    for attempt in range(3):
        tap_button(driver, "Create alert", timeout_s=8)
        time.sleep(4.0)
        if not exists_text_contains(driver, "Couldn't create that price alert", retry=False):
            break
        print(f"    [alert] create attempt {attempt + 1} failed: the app said the connection was too slow")
        snap(driver, run_dir, "price_alert", f"create_failed_{attempt + 1}")

    for _ in range(4):
        if exists_text_contains(driver, "Price falls below $", retry=False):
            break
        scroll_down(driver)
        time.sleep(1.0)
    snap(driver, run_dir, "price_alert", "listed")
    wait_visible_text_contains(driver, label, timeout_s=8)

    scroll_until_text(driver, "Cancel this alert", contains=True, max_scrolls=6)
    tap_contains(driver, "Cancel this alert")
    time.sleep(2.5)
    gone = False
    for _ in range(10):
        # a removed row can linger as a zero-sized node: ask whether the user can still see it
        if not on_screen(driver, label, contains=True):
            gone = True
            break
        time.sleep(1.0)
    snap(driver, run_dir, "price_alert", "cancelled")
    assert gone, "the alert is still listed after Cancel this alert"
    go_back(driver)
