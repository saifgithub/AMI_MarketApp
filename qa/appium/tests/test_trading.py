"""Sim trading journeys (UAT-SIM-028, UAT-SIM-029) — what the user must see when
an order fills and when the safety floor refuses one (CR263).

The goal under test is not "the ticket renders" but the two promises the sim
makes: a fill moves exactly the fill price out of cash and shows up as a
holding; a refused order says WHY, in the ticket, and moves nothing.
"""

from __future__ import annotations

import pytest

from conftest import snap
from helpers import sim_steps
from helpers.journeys import settle
from helpers.locators import exists_text_contains, wait_visible_text_contains

pytestmark = [pytest.mark.phase2]


@pytest.mark.uat("UAT-SIM-028")
def test_one_share_buy_fills_and_moves_cash(driver, run_dir):
    sim_steps.open_portfolio(driver)
    cash_before = sim_steps.read_cash(driver)

    # which ticker we buy depends on the single-name cap, so find the held
    # quantity for whichever candidate fills, by reading before AND after
    held_before = {t: sim_steps.read_holding(driver, t) for t in sim_steps.BUY_CANDIDATES}

    ticker, price, toast = sim_steps.place_buy_one(driver, run_dir)
    print(f"    [sim] filled 1 {ticker} @ {price}: {toast!r}")
    if toast:  # the toast is short-lived; when it was missed the fill is judged by cash and holdings below
        assert f"BUY 1 {ticker}" in toast, f"the fill confirmation should name the order, got {toast!r}"
    assert price > 0, f"the fill carried no price: {toast!r}"

    cash_after = sim_steps.wait_cash_below(driver, cash_before)
    snap(driver, run_dir, "sim_after_buy", "portfolio")
    spent = round(cash_before - cash_after, 2)
    assert abs(spent - price) <= max(0.02 * price, 0.05), (
        f"cash fell by {spent}, but the order filled at {price} "
        f"(cash {cash_before} -> {cash_after})"
    )

    sim_steps.open_portfolio(driver)
    held_after = sim_steps.read_holding(driver, ticker)
    assert held_after == held_before[ticker] + 1, (
        f"holding of {ticker} should rise by 1: {held_before[ticker]} -> {held_after}"
    )


@pytest.mark.uat("UAT-SIM-029")
def test_oversized_order_is_refused_with_a_reason_and_moves_nothing(driver, run_dir):
    sim_steps.open_portfolio(driver)
    cash_before = sim_steps.read_cash(driver)
    held_before = sim_steps.read_holding(driver, sim_steps.REFUSAL_TICKER)

    try:
        sim_steps.place_refused_order(driver)
        snap(driver, run_dir, "sim_refused", "ticket")
        assert exists_text_contains(driver, "TRADE BLOCKED"), "the ticket must say the trade is blocked"
        # the reason, not just the verdict: the rule that fired must be named
        wait_visible_text_contains(driver, "single-name cap", timeout_s=10)
        assert not exists_text_contains(driver, "Filled:", retry=False)
        sim_steps.STATE["refused"] = True
    finally:
        sim_steps.cancel_ticket(driver)
    settle(driver, 2.0)
    sim_steps.open_portfolio(driver)
    assert sim_steps.read_cash(driver) == cash_before, "a refused order must not move cash"
    assert sim_steps.read_holding(driver, sim_steps.REFUSAL_TICKER) == held_before


@pytest.mark.uat("UAT-SIM-028")
@pytest.mark.xfail(
    strict=False,
    raises=AssertionError,
    reason=(
        "FINDING: the fill confirmation renders a stray backslash — "
        "'Filled: BUY 1 NFLX @ \\$69.85' — because tradeTicketFilled in app_en.arb "
        "is written '\\\\${price}'. Shown to every user on every fill."
    ),
)
def test_fill_confirmation_reads_cleanly(driver, run_dir):
    if "bought" not in sim_steps.STATE:
        sim_steps.place_buy_one(driver, run_dir)
    ticker, price, toast = sim_steps.STATE["bought"]
    if not toast:
        pytest.skip("the fill toast was not observed in this run (it is short-lived); nothing to judge")
    assert "\\" not in toast, f"stray backslash in the fill confirmation: {toast!r}"
    assert f"@ ${price:,.2f}" in toast or f"@ ${price}" in toast, (
        f"the confirmation should read '@ ${price}', got {toast!r}"
    )
