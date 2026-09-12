"""The Room's distinct data demand — 49 items, not 127 asks (CR221 §2).

`inventory.py` prints the raw corpus: 127 request lines, which is how LOUD the
demand is. This prints how MUCH data is missing, which is a different number.
One ticker run through seven convenes by twelve agents repeats itself heavily —
the debt maturity ladder alone is 14 of those lines from 6 agents — so the
count of asks overstates the count of things.

Granularity rule, applied uniformly: **one item = one distinct thing an agent
asked for.** MACD, moving-average crossovers and stochastic divergence are three
items even though one sourcing decision serves all three, because an agent asked
for them separately and each is its own render. The CR pairs this register with
the 14 sourcing decisions the open items collapse into, so neither reading is
hidden behind the other.

A request line may claim MORE THAN ONE item, and that is the ask, not a bug:
"Debt maturity schedule and interest coverage ratio (EBIT/Interest Expense)"
is demand for two things. So the per-item line counts do not sum to 127.

What this asserts, and fails loudly on (CR040):
  * every one of the 127 lines claims at least one item — an unclaimed line
    means the register is incomplete, which is the failure that matters;
  * every BUILT item names a Settings flag that EXISTS in
    `backend/app/core/config.py` — the check that makes this register track the
    code rather than track itself. A slot that merges a producer and forgets the
    register now fails here, instead of reading "open" forever;
  * no OPEN item names a flag, since OPEN means no code exists;
  * the register's own totals match what is declared below, so the doc and the
    data cannot drift apart.

Read-only. Runs from any working directory:

    backend/.venv/bin/python docs/forward_planning/CR221_room_data_demand_sourcing/evidence/items.py
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inventory import load_requests  # noqa: E402

DELIVERED = "delivered"   # on the sheet today, no flag gates it
BUILT = "built"           # producer + render merged, behind a flag that is OFF
CLOSED = "closed"         # ruled out, or no free source exists
OPEN = "open"             # no code exists


@dataclass(frozen=True)
class Item:
    id: str
    group: str
    label: str
    status: str
    note: str
    pattern: str
    flag: str = ""
    """The Settings flag gating this item's render — required for BUILT, and
    asserted to EXIST in `backend/app/core/config.py`.

    That assertion is the whole reason the state exists. The register used to
    carry three states, and everything CR221 actually built landed in none of
    them: a merged producer behind a flag defaulting False is not on the sheet,
    so it is not `delivered`, and its code exists, so calling it `open` says
    something false. Slots 1 through 5 all sat at `open` while their code was on
    main, and the guard could not notice, because `EXPECTED` was a hardcoded
    dict compared against totals derived from the same hardcoded list. A guard
    that validates its own constant validates nothing.

    `OPEN` now means what it says: no code exists.
    """


# Ordered by id. `pattern` claims a request line for this item; a line may be
# claimed by several. Patterns are written against the raw request text as
# `inventory.load_requests` returns it.
ITEMS: tuple[Item, ...] = (
    # --- A. Debt & capital structure -------------------------------------
    Item("A1", "Debt & capital structure", "Debt maturity ladder, repayments by year", BUILT,
         "5 us-gaap tags already in the companyfacts payload we pull",
         r"maturity",
         flag="room_debt_maturity_enabled"),
    Item("A2", "Debt & capital structure", "Industrial vs. captive-finance debt split", BUILT,
         "not in companyfacts (§5); in the filing's own reports",
         r"captive|cat financial|caterpillar financial|financial services|financial products|"
         r"industrial (corporate |manufacturing )?debt|core industrial|industrial manufacturing|"
         r"standard corporate debt|corporate industrial debt",
         flag="room_debt_split_enabled"),
    Item("A3", "Debt & capital structure", "Average interest rate / cost of debt", BUILT,
         "derive: the Interest Expense R33 already reads / average debt",
         r"average interest rate|interest rate (or|/)|cost of debt|average interest|"
         r"debt terms|interest burden",
         flag="room_cost_of_debt_enabled"),
    Item("A4", "Debt & capital structure", "Fixed vs. floating rate mix", CLOSED,
         "closed 2026-09-11 (slot 4): no fixed/floating fact in the XBRL instance, only "
         "per-instrument stated rates on DebtInstrumentAxis — a list of notes, not a mix",
         r"fixed.{0,12}floating|floating"),
    Item("A5", "Debt & capital structure", "Interest coverage ratio", DELIVERED,
         "CR219 R33, commit ab9decb2",
         r"interest coverage"),

    # --- B. Valuation history & comparables ------------------------------
    Item("B1", "Valuation history", "Historical price-based P/E + EV/EBITDA series (5-10y)", OPEN,
         "R37 ships a narrower figure: today's price vs. past FYs' own fundamentals",
         r"(histor|median|baseline|percentile|multi.year|full cycle|10.year|5.year|5–10|5-10|"
         r"5 to 10|cycle trough|business cycle)[^.]{0,80}(multiple|p/e|ev/ebitda|valuation)|"
         r"(multiple|p/e|ev/ebitda|valuation)[^.]{0,60}(histor|median|percentile|baseline|"
         r"multi.year|past 5|past 10|full cycle|cycle trough)"),
    Item("B2", "Valuation history", "Cycle-median ROE", BUILT,
         "same statement history as B1's fundamentals leg",
         r"median roe",
         flag="room_roe_history_enabled"),
    Item("B3", "Valuation history", "Peer-basket valuation multiples", OPEN,
         "cohort exists in classification_universe; needs per-peer fundamentals",
         r"(multiple|p/e|ev/ebitda|valuation)[^.]{0,40}(peer|deere|agco)|"
         r"(peer|deere|agco)[^.]{0,40}(multiple|p/e|ev/ebitda|valuation)"),
    Item("B4", "Valuation history", "Peer/sector median balance-sheet ratios (D/E, quick ratio)", OPEN,
         "same cohort as B3",
         r"sector median|median quick rati|median.{0,20}debt.to.equity"),
    Item("B5", "Valuation history", "Own-history multiples vs. past FYs' fundamentals", DELIVERED,
         "CR219 R37, commit d3943aa5 — answers less than B1 asks",
         r"(?!x)x"),  # never claims a line; B1 carries the demand it partly answers

    # --- C. Cash flow & capital allocation -------------------------------
    Item("C1", "Cash flow & capital allocation", "Explicit capex line", DELIVERED,
         "CR219 R34, commit a841ac13 — trailing four quarters only, so the "
         "history and projection halves of the ask stay open (C2, C9)",
         r"capital expenditure|capex"),
    Item("C2", "Cash flow & capital allocation", "Multi-year capex / FCF averages", BUILT,
         "quarterly statements already pulled; only the last four survive",
         r"(histor|multi.year|past 5|over time)[^.]{0,60}(capital expenditure|capex|"
         r"free cash flow|fcf)|(capital expenditure|capex|free cash flow|fcf)"
         r"[^.]{0,50}(histor|multi.year|averages|over time|past 5)",
         flag="room_fcf_history_enabled"),
    Item("C3", "Cash flow & capital allocation", "Operating cash flow line + OCF-to-FCF bridge", BUILT,
         "same discarded quarterly cash-flow statement",
         r"operating cash flow|cash flow statement|cash-flow statement|\bcfo\b(?!.{0,30}transition)|"
         r"cash flow reconciliation|free cash flow reconciliation|cash flow bridge|"
         r"capital expenditures \(capex\) breakdown",
         flag="room_cashflow_bridge_enabled"),
    Item("C4", "Cash flow & capital allocation", "Working-capital change detail", BUILT,
         "same statement",
         r"working capital",
         flag="room_cashflow_bridge_enabled"),
    Item("C5", "Cash flow & capital allocation", "FCF conversion history (FCF / net income)", BUILT,
         "same statement",
         r"conversion rate|cash flow conversion|fcf as a percentage of net income|"
         r"free cash flow conversion",
         flag="room_fcf_conversion_enabled"),
    Item("C6", "Cash flow & capital allocation", "Buyback pacing over the trailing quarters", DELIVERED,
         "CR219 R35, commit c7c40213",
         r"timeline/pacing|pacing of the"),
    Item("C7", "Cash flow & capital allocation", "Buyback average execution price", BUILT,
         "TreasuryStockSharesAcquired / R35's repurchase dollars",
         r"repurchase average execution|average execution price",
         flag="room_buyback_price_enabled"),
    Item("C8", "Cash flow & capital allocation", "Historical dividend growth CAGR", BUILT,
         "DividendPayment history already fetched (CR206)",
         r"historical dividend growth",
         flag="room_dividend_growth_enabled"),
    Item("C9", "Cash flow & capital allocation", "Projected dividend growth / forward payout target", OPEN,
         "yfinance growth_estimates / eps_trend — the provider we already call",
         r"projected dividend growth|forward payout"),

    # --- D. Segment & geography ------------------------------------------
    Item("D1", "Segment & geography", "Revenue by business segment", BUILT,
         "same filing-report route as A2 (§5)",
         r"(revenue|sales)[^.]{0,40}(segment|end.market|breakdown by segment)|"
         r"segment revenue|revenue segmentation|revenue breakdown by segment|"
         r"revenue exposure breakdown|"
         r"segment[- ]?(level|wise)?[^.]{0,30}"
         r"(revenue|sales|ebitda|operating profit|profit|contribution)|"
         # `inventory.py`'s Segment CLUSTER already claims "revenue mix"; the
         # item pattern was transcribed without it, so every "power-gen revenue
         # mix percentage" fell through to no item at all.
         r"revenue mix|(revenue|sales) (share|contribution)|"
         r"(share|percentage|%) of total (revenue|sales)",
         flag="room_segment_revenue_enabled"),
    Item("D2", "Segment & geography", "Revenue by geography", BUILT,
         "same route",
         r"geograph",
         flag="room_geographic_revenue_enabled"),

    # --- E. Earnings expectations ----------------------------------------
    Item("E1", "Earnings expectations", "Consensus estimate revisions", DELIVERED,
         "CR219 R21-DATA, commit ecb8f199",
         r"revision"),
    Item("E2", "Earnings expectations", "Earnings surprise history", DELIVERED,
         "CR219 R21-DATA, commit ecb8f199",
         r"surprise"),
    Item("E3", "Earnings expectations", "Management guidance", CLOSED,
         "ruled out by CR219 R22; the sheet's disclaimer stands",
         r"guidance"),
    Item("E4", "Earnings expectations", "Long-term (3-5y) forward EPS growth estimates", OPEN,
         "yfinance growth_estimates carries an LTG row (NaN for CAT: absent state)",
         r"forward eps growth|eps growth estimate"),

    # --- F. Price series & technicals ------------------------------------
    Item("F1", "Price series & technicals", "Raw OHLC bar series / chart patterns", OPEN,
         "the Room profile is pinned to a 3-month daily window",
         r"time.series price bars|price bars|chart pattern"),
    Item("F2", "Price series & technicals", "Weekly & monthly timeframe indicators", OPEN,
         "_PERIOD_MAP already defines 1y weekly and 5y monthly",
         r"weekly or monthly|weekly/monthly|weekly and monthly"),
    Item("F3", "Price series & technicals", "MACD", OPEN,
         "computable from bars; the sheet currently denies it outright",
         r"macd"),
    Item("F4", "Price series & technicals", "Moving-average crossover signals", OPEN,
         "same",
         r"crossover"),
    Item("F5", "Price series & technicals", "Stochastic / momentum divergence", OPEN,
         "same",
         r"stochastic|momentum divergence"),
    Item("F6", "Price series & technicals", "Volume-at-price / volume profile / point-of-control", OPEN,
         "needs the bar series, not a new provider",
         r"volume.by.price|volume.at.price|volume profile|point.of.control"),
    Item("F7", "Price series & technicals", "Historical support & resistance levels", OPEN,
         "needs a longer window than 65 bars",
         r"support and resistance|support levels|historic support|resistance levels"),
    Item("F8", "Price series & technicals", "Candlestick pattern recognition", OPEN,
         "needs OHLC, which the profile already fetches but does not expose",
         r"candlestick"),
    Item("F9", "Price series & technicals", "RSI history (troughs, multi-year trend, rolling baseline)", OPEN,
         "needs a longer window",
         r"rsi troughs|past rsi|trend of the rsi|weekly or monthly rsi"),
    Item("F10", "Price series & technicals", "ATR(14)", DELIVERED,
         "CR219 R36, commit a4459b01",
         r"\batr\b|average true range"),
    Item("F11", "Price series & technicals", "Historical gap-down / overnight slippage statistics", OPEN,
         "derivable from a longer daily series",
         r"gap.down|slippage|overnight gap"),

    # --- G. Options & order flow -----------------------------------------
    Item("G1", "Options & order flow", "Implied volatility level / expected move", OPEN,
         "OptionQuote.implied_vol already fetched (CR172 §4); needs sanity gating",
         r"implied volatility|\biv\b"),
    Item("G2", "Options & order flow", "IV skew", OPEN,
         "same chain",
         r"\bskew\b"),
    Item("G3", "Options & order flow", "Open interest & options volume", OPEN,
         "OptionQuote.open_interest / .volume already fetched",
         r"open interest|options volume"),
    Item("G4", "Options & order flow", "Level 2 order-book depth / bid density", CLOSED,
         "no consumer-reachable source; declare the absence",
         r"level 2|order book|bid density"),
    Item("G5", "Options & order flow", "Dark-pool prints & institutional flow", CLOSED,
         "same",
         r"dark pool|institutional flow"),

    # --- H. Macro ---------------------------------------------------------
    Item("H1", "Macro", "Macro prints: CPI, PPI, PMI/ISM", OPEN,
         "FRED fredgraph.csv, keyless: CPIAUCSL, PPIACO. ISM PMI is proprietary — "
         "substitutes CFNAI/IPMAN/DGORDER are free",
         r"\bcpi\b|\bppi\b|\bpmi\b|\bism\b"),
    Item("H2", "Macro", "Fed path / rate-cut probability", OPEN,
         "the one item with no verified free source — see CR221 §4",
         r"rate (cut|hike|path|expectation|decision)|fed funds|fed rate|"
         r"rate cut|expected fed rate|interest rate path|fomc rate decision"),
    Item("H3", "Macro", "End-market macro: construction spending, housing starts, mining capex", OPEN,
         "FRED fredgraph.csv, keyless: TTLCONS, HOUST",
         r"construction spending|macro construction|housing starts|infrastructure spending|"
         r"dodge momentum|mining capex"),

    # --- I. News depth ----------------------------------------------------
    Item("I1", "News depth", "Executive-change detail (identity, background, circumstance)", BUILT,
         "SEC EDGAR 8-K Item 5.02 — free, already-called host; verified on CAT",
         r"\bcfo\b.{0,60}(background|track record|mandate|transition|departure|successor|"
         r"new executive|names|retiring|ousted|resignation)|"
         r"(incoming|outgoing) (cfo|executive)|cfo (transition|departure)",
         flag="room_executive_change_enabled"),
    Item("I2", "News depth", "Catalyst magnitude (the % move a headline caused)", OPEN,
         "derive from the daily bars and the headline's own date — no source needed",
         r"magnitude of the (cfo.driven )?rally|magnitude of the rally"),

    # --- J. Social --------------------------------------------------------
    Item("J1", "Social", "Raw bullish/bearish split, buzz score, mention counts", DELIVERED,
         "on the sheet before CR219",
         r"bullish.{0,10}bearish|buzz score|mention volume|mention counts|reddit mention"),
    Item("J2", "Social", "Sentiment history / rolling baseline", CLOSED,
         "structurally absent: the cache keeps one row and overwrites it, by design",
         r"rolling average of sentiment|historical baseline data|"
         r"historical sentiment|sentiment (history|trend)"),

    # --- K. User context --------------------------------------------------
    Item("K1", "User context", "Decision Journal history for this ticker", DELIVERED,
         "DEF054/DEF055 wired it; the arm ask is a harness artifact (empty journal)",
         r"decision journal"),
)

# Not a data item: a prompt-clarity question that belongs to CR219's
# instruction-collision class. Declared so it does not read as an unmapped line.
NON_DATA = (r"cooldown", "cooldown-rule scope clarification (CR219's surface, not a source)")

EXPECTED = {"total": 49, DELIVERED: 9, BUILT: 13, CLOSED: 5, OPEN: 22}

# The guard reads this file to prove every BUILT item's flag is real. Resolved
# from this script's own location so it works from any working directory — the
# same property `inventory.py` already guarantees.
CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))),
    "backend", "app", "core", "config.py",
)


def claims(text: str) -> list[Item]:
    return [i for i in ITEMS if re.search(i.pattern, text, re.I)]


def main() -> int:
    rows = load_requests()
    counts: dict[str, int] = {i.id: 0 for i in ITEMS}
    agents: dict[str, set[str]] = {i.id: set() for i in ITEMS}
    unmapped: list[tuple[str, str, str]] = []

    for source, agent, text in rows:
        hits = claims(text)
        if not hits:
            if not re.search(NON_DATA[0], text, re.I):
                unmapped.append((source, agent, text))
            continue
        for item in hits:
            counts[item.id] += 1
            agents[item.id].add(agent)

    by_status = {DELIVERED: 0, BUILT: 0, CLOSED: 0, OPEN: 0}
    group = None
    print(f"THE ROOM'S DISTINCT DATA DEMAND — {len(ITEMS)} items, from {len(rows)} request lines")
    print("=" * 100)
    for item in ITEMS:
        by_status[item.status] += 1
        if item.group != group:
            group = item.group
            print(f"\n{group}")
            print("-" * 100)
        mark = {DELIVERED: "DONE", BUILT: "DARK",
                CLOSED: "SHUT", OPEN: "open"}[item.status]
        n, a = counts[item.id], len(agents[item.id])
        demand = f"{n:>3} lines / {a} agents" if n else "  — (answered before the corpus)"
        print(f"  {item.id:<4} {mark}  {item.label:<62} {demand}")
        print(f"       {item.note}")

    print("\n" + "=" * 100)
    print(f"  {by_status[DELIVERED]:>3} delivered   — on the sheet today, no flag gates it")
    print(f"  {by_status[BUILT]:>3} DARK        — producer + render merged, flag OFF, no user has seen it")
    print(f"  {by_status[CLOSED]:>3} closed      — ruled out, or no free source exists")
    print(f"  {by_status[OPEN]:>3} OPEN        — no code exists; what CR221 has left to source")
    print(f"  {len(ITEMS):>3} distinct data items, against {len(rows)} request lines")

    ok = True
    if unmapped:
        ok = False
        print(f"\n!! {len(unmapped)} request lines claim NO item — the register is incomplete:")
        for source, agent, text in unmapped:
            print(f"   [{source:12s}][{agent}] {text[:110]}")
    actual = {"total": len(ITEMS), DELIVERED: by_status[DELIVERED],
              BUILT: by_status[BUILT], CLOSED: by_status[CLOSED], OPEN: by_status[OPEN]}
    if actual != EXPECTED:
        ok = False
        print(f"\n!! register totals drifted from the CR: expected {EXPECTED}, got {actual}")

    # The check that reads the CODE. Totals compared against a constant in this
    # same file cannot catch a slot that shipped a producer and left its item at
    # `open` — which is exactly how thirteen items went stale (CR221 §7.13).
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            config_src = fh.read()
    except OSError as exc:
        ok = False
        print(f"\n!! cannot read {CONFIG} to verify BUILT flags: {exc}")
        config_src = None

    if config_src is not None:
        for item in ITEMS:
            if item.status == BUILT:
                if not item.flag:
                    ok = False
                    print(f"\n!! {item.id} is BUILT but names no flag — BUILT means "
                          "'merged behind a flag', so the flag is the evidence")
                elif f"{item.flag}:" not in config_src:
                    ok = False
                    print(f"\n!! {item.id} claims flag `{item.flag}`, which is NOT in "
                          f"{os.path.relpath(CONFIG)} — either the register is ahead "
                          "of the code or the flag was renamed")
            elif item.flag:
                ok = False
                print(f"\n!! {item.id} is {item.status} but names flag `{item.flag}` — "
                      "only BUILT items carry one (OPEN means no code exists)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
