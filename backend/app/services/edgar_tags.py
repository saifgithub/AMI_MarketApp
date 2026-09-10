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

from dataclasses import dataclass

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

# ── CR221 slot 4 (A2 / D1 / D2) — what the filing carries only in its columns ──
#
# `companyfacts` serves one non-dimensional value per concept; the captive-
# finance debt split, revenue by segment and revenue by geography live in the
# filing's dimensional contexts and are read from its XBRL instance instead
# (`edgar_instance.py`, `scripts/ingest_edgar_dimensional.py`). The derived
# rows carry their own taxonomy string and an `ami:` prefix so they can never
# collide with a real us-gaap tag name here — the PIT resolver asks for
# us-gaap/dei tags by name and must never read a member's figure as the whole
# company's.
DIMENSIONAL_TAXONOMY = "ami"
CAPTIVE_DEBT_TAG = "ami:CaptiveFinanceDebt"         # + ":<source us-gaap tag>"
INDUSTRIAL_DEBT_TAG = "ami:IndustrialDebt"          # + ":<source us-gaap tag>"
SEGMENT_REVENUE_TAG = "ami:SegmentRevenue"          # + ":<tier>:<member qname>"
GEOGRAPHIC_REVENUE_TAG = "ami:GeographicRevenue"    # + ":<member qname>"
CONSOLIDATED_REVENUE_TAG = "ami:ConsolidatedRevenue"  # + ":<source us-gaap tag>"

# The debt concepts a consolidating column can carry, by family. A side's
# total is the combined concept when the filer tags one (F, PCAR), else
# noncurrent plus the current family: `DebtCurrent` already includes
# short-term borrowings, so it is never added to them (F's Ford Credit column:
# $89,665M noncurrent + $51,752M `DebtCurrent` = the $141,417M combined figure
# it also tags). Order within a family is preference, first present wins.
DEBT_FAMILY_COMBINED = ("DebtLongtermAndShorttermCombinedAmount", "DebtAndCapitalLeaseObligations")
DEBT_FAMILY_NONCURRENT = ("LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations")
DEBT_FAMILY_CURRENT_ALL = ("DebtCurrent",)
DEBT_FAMILY_CURRENT_LTD = ("LongTermDebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent")
DEBT_FAMILY_SHORT = ("ShortTermBorrowings", "CommercialPaper")
DEBT_SPLIT_SOURCE_TAGS: frozenset[str] = frozenset(
    DEBT_FAMILY_COMBINED + DEBT_FAMILY_NONCURRENT + DEBT_FAMILY_CURRENT_ALL
    + DEBT_FAMILY_CURRENT_LTD + DEBT_FAMILY_SHORT
)

# Axis LOCAL names (the prefix is the filer's to choose) on which a
# consolidating column may appear. CAT uses ProductOrService, F uses
# StatementBusinessSegments; the two entity axes are the textbook placement
# and were seen on neither, but cost nothing to admit.
DEBT_SPLIT_AXES = (
    "ProductOrServiceAxis", "StatementBusinessSegmentsAxis",
    "LegalEntityAxis", "ConsolidatedEntitiesAxis",
)

# Revenue concepts, broadest first — where a filer tags two for one cell the
# first wins, so `Revenues` (which includes finance income) beats the
# contract-revenue concept that excludes it.
REVENUE_TAGS = (
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
)


@dataclass(frozen=True)
class CaptiveFinance:
    """One filer's in-house lender: its name for the sheet, and the normalised
    member names its filing uses for the two consolidating columns."""

    lender: str
    captive: tuple[str, ...]
    industrial: tuple[str, ...]


# Matching is EXACT on the normalised member name, not by substring: Ford's
# industrial column is `CompanyExcludingFordCreditMember`, and a substring rule
# for "fordcredit" would file the industrial figure under the lender. Names
# were read off each filer's latest 10-K instance on 2026-09-10; a filer that
# renames a member stops resolving and the sheet says so, which is the correct
# failure. Manual by design — a name-similarity heuristic would eventually
# match an operating segment that is not a lending book, and a wrong split is
# worse than no split.
CAPTIVE_FINANCE: dict[str, CaptiveFinance] = {
    "CAT": CaptiveFinance(
        lender="Caterpillar Financial Services",
        captive=("financialproducts",),
        industrial=("machinerypowerenergy", "machineryenergytransportation"),
    ),
    "DE": CaptiveFinance(
        lender="John Deere Capital",
        captive=("financialservices", "johndeerecapital"),
        industrial=("equipmentoperations",),
    ),
    "F": CaptiveFinance(
        lender="Ford Credit",
        captive=("fordcredit",),
        industrial=("companyexcludingfordcredit",),
    ),
    "PCAR": CaptiveFinance(
        lender="PACCAR Financial",
        captive=("financialservices", "paccarfinancial"),
        industrial=("truckpartsandother",),
    ),
}


def normalize_member_name(qname: str) -> str:
    """`cat:FinancialProductsSegmentMember` → `financialproducts`.

    Prefix dropped, lowercase alphanumerics only, then the `Member` and
    `Segment` suffixes stripped — CAT tags the same column as both
    `FinancialProductsMember` and `FinancialProductsSegmentMember`.
    """
    local = str(qname).rsplit(":", 1)[-1]
    text = "".join(ch for ch in local.lower() if ch.isalnum())
    if text.endswith("member"):
        text = text[: -len("member")]
    if text.endswith("segment"):
        text = text[: -len("segment")]
    return text


def captive_finance_lender(ticker: str) -> str | None:
    entry = CAPTIVE_FINANCE.get(str(ticker).upper().strip())
    return entry.lender if entry else None


def captive_finance_role(ticker: str, member_qname: str) -> str | None:
    """`"captive"`, `"industrial"`, or None when the member is neither — which
    is every member of every filer not in the registry."""
    entry = CAPTIVE_FINANCE.get(str(ticker).upper().strip())
    if entry is None:
        return None
    name = normalize_member_name(member_qname)
    if not name:
        return None
    if name in entry.captive:
        return "captive"
    if name in entry.industrial:
        return "industrial"
    return None


def captive_finance_tickers() -> tuple[str, ...]:
    return tuple(sorted(CAPTIVE_FINANCE))


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
