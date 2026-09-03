"""EDGAR us-gaap tag preferences per fundamental concept (CR164).

Pure data. Companies tag the same economic fact under different us-gaap
concepts (revenue alone has three common spellings), so each concept carries
an ORDERED preference list — the PIT resolver takes the first tag that
resolves at the as-of date and never mixes values across tags in one figure.
A concept none of whose tags resolve is ABSENT, never estimated — absence
flows to the CR104 UNAVAILABLE rendering.

Additive concepts (`CASH_PLUS_STI`, `DEBT_COMPONENTS`) list components that
are SUMMED when present; the resolver requires the anchor component (first
entry) before adding optional ones, so "debt" can never resolve to just a
working-capital stub.
"""

from __future__ import annotations

# Duration concepts (quarterly/annual flows) — resolved via quarterly series + TTM.
REVENUE = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)
NET_INCOME = ("NetIncomeLoss",)
OPERATING_CASH_FLOW = ("NetCashProvidedByUsedInOperatingActivities",)
CAPEX = (
    "PaymentsToAcquirePropertyPlantAndEquipment",
    # Same tag-variant lesson DEPRECIATION_AMORTIZATION already learned on the
    # pilot corpus: a concept absent under one spelling is usually present
    # under another, and every capex miss costs both fcf_yield and free_cash_flow.
    "PaymentsToAcquireProductiveAssets",
    "PaymentsToAcquireOtherPropertyPlantAndEquipment",
)
GROSS_PROFIT = ("GrossProfit",)
# Fallback route to gross profit when GrossProfit itself is not tagged:
# revenue − cost of revenue. Filers vary on which spelling they use.
COST_OF_REVENUE = (
    "CostOfGoodsAndServicesSold",
    "CostOfRevenue",
    "CostOfGoodsSold",
)
BUYBACKS = (
    "PaymentsForRepurchaseOfCommonStock",
    "PaymentsForRepurchaseOfEquity",
)
OPERATING_INCOME = ("OperatingIncomeLoss",)
DEPRECIATION_AMORTIZATION = (
    "DepreciationDepletionAndAmortization",
    "DepreciationAndAmortization",
    # Measured on the CR164 pilot corpus: 7 of 18 EV/EBITDA gaps were a D&A
    # tag variant, not a missing disclosure.
    "DepreciationAmortizationAndAccretionNet",
    "DepreciationDepletionAndAmortizationIncludingDiscontinuedOperations",
    "DepreciationNonproduction",
)
DIVIDENDS_PAID_COMMON = (
    "PaymentsOfDividendsCommonStock",
    "PaymentsOfDividends",
)
DILUTED_SHARES = ("WeightedAverageNumberOfDilutedSharesOutstanding",)

# Instant concepts (balance-sheet points) — resolved at latest period_end filed <= as_of.
CASH_ANCHOR = ("CashAndCashEquivalentsAtCarryingValue",)
CASH_OPTIONAL_ADD = ("ShortTermInvestments",)
# Named because two consumers need THIS tag specifically, not "whichever debt
# tag resolves first": the maturity ladder's beyond-year-five residual is only
# arithmetic against noncurrent debt (`LongTermDebt` includes the current
# portion and would double-count year one), and the ladder's basis note names
# the short-term borrowings it excludes.
LONG_TERM_DEBT_NONCURRENT = "LongTermDebtNoncurrent"
SHORT_TERM_BORROWINGS = "ShortTermBorrowings"
DEBT_ANCHOR = (LONG_TERM_DEBT_NONCURRENT, "LongTermDebt")
DEBT_OPTIONAL_ADD = ("LongTermDebtCurrent", "DebtCurrent", SHORT_TERM_BORROWINGS)
EQUITY = (
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
)
ASSETS = ("Assets",)
# Current assets/liabilities exist only on a CLASSIFIED balance sheet. Banks
# and insurers do not present one, so these resolve to nothing for them — that
# is a real absence, not a tag gap, and the ratios must stay absent rather
# than fall back to something that looks like a number.
CURRENT_ASSETS = ("AssetsCurrent",)
CURRENT_LIABILITIES = ("LiabilitiesCurrent",)
INVENTORY = ("InventoryNet",)

# CR221 A3 / DEF399 — interest expense, on two irreconcilable bases kept apart
# on purpose. `INTEREST_ACCRUAL` is the income-statement concept;
# `INTEREST_CASH` is the cash-flow supplemental. They usually agree within a
# few percent, and where they DISAGREE it is a signal, not noise: on
# Harley-Davidson the accrual tag reads $31M against $331M paid, because the
# accrual line excludes the finance arm. `interest_cost.py` refuses rather than
# picks when they diverge — see DEF399 for why picking is how the shipped
# `interest_coverage` came to overstate Caterpillar's by 5x.
INTEREST_ACCRUAL = ("InterestExpense", "InterestExpenseNonoperating")
INTEREST_CASH = ("InterestPaidNet", "InterestPaid")

# CR221 A1 — the debt maturity ladder (instants, stated at the balance-sheet
# date). NOT a preference list: these are five DISTINCT buckets, so the resolver
# reads them as a set at one common `period_end` and may never substitute one
# for another. Year one is the anchor — a filer disclosing a ladder at all tags
# it — and the (label, tag) pairing lives here so bucket order and bucket
# labelling cannot drift apart in two files.
#
# `...AfterYearFive` exists in us-gaap but is tagged by neither of the two
# filers measured (CAT 18 points on each of the five below, Deere 4), so the
# beyond-five figure is derived from noncurrent debt rather than read.
DEBT_MATURITY_LADDER: tuple[tuple[str, str], ...] = (
    ("Within 1 year", "LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths"),
    ("Year 2", "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo"),
    ("Year 3", "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree"),
    ("Year 4", "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFour"),
    ("Year 5", "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFive"),
)
DEBT_MATURITY_TAGS: tuple[str, ...] = tuple(tag for _, tag in DEBT_MATURITY_LADDER)

# dei taxonomy — shares outstanding cover-page fact (instant), the market-cap basis.
SHARES_OUTSTANDING_DEI = ("EntityCommonStockSharesOutstanding",)

# Every tag the ingest script persists. Anything else in companyfacts is
# skipped at ingest — the store holds what the resolver can use, nothing more.
INGEST_TAGS_US_GAAP: frozenset[str] = frozenset(
    REVENUE
    + NET_INCOME
    + OPERATING_CASH_FLOW
    + CAPEX
    + GROSS_PROFIT
    + COST_OF_REVENUE
    + BUYBACKS
    + OPERATING_INCOME
    + DEPRECIATION_AMORTIZATION
    + DIVIDENDS_PAID_COMMON
    + DILUTED_SHARES
    + CASH_ANCHOR
    + CASH_OPTIONAL_ADD
    + DEBT_ANCHOR
    + DEBT_OPTIONAL_ADD
    + EQUITY
    + ASSETS
    + CURRENT_ASSETS
    + CURRENT_LIABILITIES
    + INVENTORY
    + DEBT_MATURITY_TAGS
    + INTEREST_ACCRUAL
    + INTEREST_CASH
)
INGEST_TAGS_DEI: frozenset[str] = frozenset(SHARES_OUTSTANDING_DEI)
