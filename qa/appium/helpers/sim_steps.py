"""Sim-trading steps shared by the SIM, JRNL and WATCH journeys (CR263).

A trade is an expensive precondition (sheet, ticker, keyboard, submit) and three
journeys need one, so it lives here once. State on the device persists between
runs (`noReset`), so nothing here assumes an empty book: quantities and cash are
read before and compared after.

The refusal order is chosen so the compliance check rejects it WHATEVER the
price is: 100 shares of a ~$70 stock is ~70% of the book, which breaks the
single-name cap (3% on the default mandate) by an order of magnitude. A
1-share AAPL order also trips it today (3.4%) but only because AAPL is above
$300 — a rule that flips with the market is not a UAT oracle.
"""

from __future__ import annotations

import re
import time

from helpers.journeys import (
    on_screen,
    TRADE_TICKET_CANCEL,
    dismiss_keyboard,
    fill_field,
    holding_quantity,
    money_near,
    scroll_down,
    settle,
    tap_button,
    tap_id,
    tap_text,
    wait_any_text,
)
from helpers.locators import _all_by_text_contains, exists_id, exists_text, exists_text_contains, wait_visible_text, wait_visible_text_contains
from pages.base_page import open_tab

#: low-priced names first so a 1-share buy sits well inside the single-name cap
BUY_CANDIDATES = ("NFLX", "KO", "F", "T")
REFUSAL_TICKER = "NFLX"
REFUSAL_QUANTITY = "100"

#: shared across the modules of one pytest run
STATE: dict[str, object] = {}

_FILL_PRICE = re.compile(r"@\s*\\?\$([\d,]+(?:\.\d+)?)")


def open_portfolio(driver) -> None:
    open_tab(driver, "Portfolio")
    wait_visible_text(driver, "TOTAL VALUE", timeout_s=15)
    time.sleep(1.5)


def read_cash(driver) -> float:
    return money_near(driver, "CASH")


def read_holding(driver, ticker: str) -> float:
    qty = holding_quantity(driver, ticker)
    if qty == 0.0:
        scroll_down(driver)
        qty = holding_quantity(driver, ticker)
    return qty


def open_ticket(driver, ticker: str, *, quantity: str | None = None) -> None:
    tap_text(driver, "New trade")
    wait_visible_text(driver, "NEW TRADE", timeout_s=10)
    fill_field(driver, "TICKER", ticker)
    dismiss_keyboard(driver)
    if quantity is not None:
        fill_field(driver, "QUANTITY", quantity)
        # the decimal pad has no Done key: hand focus back to the ticker field,
        # whose pad does
        fill_field(driver, "TICKER", ticker)
        dismiss_keyboard(driver)
    time.sleep(3.0)  # price + compliance preview settle (a stale banner clears)


def cancel_ticket(driver) -> None:
    if exists_id(driver, TRADE_TICKET_CANCEL, retry=False):
        tap_id(driver, TRADE_TICKET_CANCEL)
    else:
        driver.back()
    time.sleep(1.5)


def place_buy_one(driver, run_dir=None) -> tuple[str, float, str]:
    """Buy one share of the first candidate that clears the compliance check.
    Returns (ticker, fill price, the confirmation text). Raises AssertionError if every candidate is
    refused, naming what the ticket said."""
    from conftest import snap

    refusals = []
    for ticker in BUY_CANDIDATES:
        open_portfolio(driver)
        cash_before = read_cash(driver)
        open_ticket(driver, ticker)
        if exists_text(driver, "MOCK", retry=False):
            if run_dir is not None:
                snap(driver, run_dir, "sim_mock_quote", ticker)
            refusals.append(f"{ticker}: the ticket quoted it from the MOCK feed (a mock price is not a fill oracle)")
            cancel_ticket(driver)
            continue
        tap_button(driver, "SUBMIT TRADE", timeout_s=10)
        print(f"    [sim] submitted 1 {ticker}")
        cash_before_fill = cash_before
        toast_text = _catch_fill_toast(driver, timeout_s=25)
        if toast_text is None:
            # the toast is short-lived: judge by state instead of by whether we saw it
            if exists_text_contains(driver, "max trades per day", retry=False):
                cancel_ticket(driver)
                import pytest

                pytest.skip(
                    "PRECONDITION: the mandate's daily trade cap (UTC day) is already used up on this "
                    "device's account - the app refused correctly, so there is nothing to assert about a "
                    "fill. Re-run after 00:00 UTC."
                )
            blocked = exists_text_contains(driver, "TRADE BLOCKED", retry=False) or exists_text(
                driver, "OPEN MY MANDATE", retry=False
            )
            # "NEW TRADE" lingers in the tree after the sheet has gone, so ask whether the
            # sheet's own SUBMIT button is still on screen instead
            ticket_open = on_screen(driver, "SUBMIT TRADE")
            if run_dir is not None:
                snap(driver, run_dir, "sim_no_fill", ticker)
            if ticket_open:
                why = ""
                if blocked:
                    from helpers import lesson_steps

                    why = " | ".join(
                        n.label.replace("\n", " ")[:160]
                        for n in lesson_steps.nodes(driver)
                        if n.y < 700 and any(k in n.label.lower() for k in ("cap", "limit", "exceed", "mandate", "%"))
                    )
                refusals.append(f"{ticker}: {'blocked by the safety floor: ' + why if blocked else 'SUBMIT gave no fill and no refusal'}")
                cancel_ticket(driver)
                continue
            # the ticket closed: it filled and we missed the toast
            now = wait_cash_below(driver, cash_before_fill, timeout_s=15)
            price = round(cash_before_fill - now, 2)
            assert price > 0, f"{ticker}: the ticket closed but cash did not move ({cash_before_fill} -> {now})"
            STATE["bought"] = (ticker, price, None)
            return ticker, price, ""
        if run_dir is not None:
            snap(driver, run_dir, "sim_fill_toast", ticker)
        match = _FILL_PRICE.search(toast_text)
        price = float(match.group(1).replace(",", "")) if match else 0.0
        STATE["bought"] = (ticker, price, toast_text)
        return ticker, price, toast_text
    raise AssertionError("no candidate could be bought: " + "; ".join(refusals))


def _catch_fill_toast(driver, *, timeout_s: float):
    """The fill confirmation is a toast that lives for a few seconds, so poll as fast
    as the driver answers - no sleeping between looks."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        for el in _all_by_text_contains(driver, "Filled:", retry=False):
            try:
                return el.get_attribute("label") or el.text or ""
            except Exception:
                continue
        if exists_text_contains(driver, "TRADE BLOCKED", retry=False) or exists_text_contains(
            driver, "max trades per day", retry=False
        ):
            return None
    return None


def place_refused_order(driver) -> str:
    """Submit the oversized order and return the visible refusal text."""
    open_portfolio(driver)
    open_ticket(driver, REFUSAL_TICKER, quantity=REFUSAL_QUANTITY)
    tap_button(driver, "SUBMIT TRADE", timeout_s=10)
    print(f"    [sim] submitted {REFUSAL_QUANTITY} {REFUSAL_TICKER}")
    try:
        wait_visible_text_contains(driver, "TRADE BLOCKED", timeout_s=60)
    except Exception:
        from helpers import lesson_steps

        print("    [sim] DEBUG labels:", [n.label.replace("\n", " ")[:90] for n in lesson_steps.nodes(driver)][:40])
        raise
    time.sleep(1.0)
    return REFUSAL_TICKER


def wait_cash_below(driver, before: float, *, timeout_s: float = 20.0) -> float:
    deadline = time.monotonic() + timeout_s
    while True:
        open_portfolio(driver)
        now = read_cash(driver)
        if now < before - 0.005 or time.monotonic() >= deadline:
            return now
        settle(driver, 2.0)
