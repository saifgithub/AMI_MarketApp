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
CAPEX = ("PaymentsToAcquirePropertyPlantAndEquipment",)
OPERATING_INCOME = ("OperatingIncomeLoss",)
DEPRECIATION_AMORTIZATION = (
    "DepreciationDepletionAndAmortization",
    "DepreciationAndAmortization",
)
DIVIDENDS_PAID_COMMON = (
    "PaymentsOfDividendsCommonStock",
    "PaymentsOfDividends",
)
DILUTED_SHARES = ("WeightedAverageNumberOfDilutedSharesOutstanding",)

# Instant concepts (balance-sheet points) — resolved at latest period_end filed <= as_of.
CASH_ANCHOR = ("CashAndCashEquivalentsAtCarryingValue",)
CASH_OPTIONAL_ADD = ("ShortTermInvestments",)
DEBT_ANCHOR = ("LongTermDebtNoncurrent", "LongTermDebt")
DEBT_OPTIONAL_ADD = ("LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings")

# dei taxonomy — shares outstanding cover-page fact (instant), the market-cap basis.
SHARES_OUTSTANDING_DEI = ("EntityCommonStockSharesOutstanding",)

# Every tag the ingest script persists. Anything else in companyfacts is
# skipped at ingest — the store holds what the resolver can use, nothing more.
INGEST_TAGS_US_GAAP: frozenset[str] = frozenset(
    REVENUE
    + NET_INCOME
    + OPERATING_CASH_FLOW
    + CAPEX
    + OPERATING_INCOME
    + DEPRECIATION_AMORTIZATION
    + DIVIDENDS_PAID_COMMON
    + DILUTED_SHARES
    + CASH_ANCHOR
    + CASH_OPTIONAL_ADD
    + DEBT_ANCHOR
    + DEBT_OPTIONAL_ADD
)
INGEST_TAGS_DEI: frozenset[str] = frozenset(SHARES_OUTSTANDING_DEI)
