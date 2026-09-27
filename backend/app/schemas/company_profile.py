"""CR244 — response models for `GET /v1/sim/company-profile/{ticker}` and
`GET /v1/sim/insider/{ticker}`.

Binding API contract: field names and shapes here match
`docs/forward_planning/CR244_edgar_company_data_display_and_agent_feeds/CR244.md`
verbatim (`## API contract`) — mobile is built against that doc in parallel,
so nothing here may rename or reshape a field.

Every section carries its own `state`/`reason`/`sources` (CR040 degrade
loudly): one source failing produces that section's own `not_available` or
`partial` state with a user-readable reason, never a blanked screen and
never a fabricated number in place of a missing one.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SectionState = Literal["live", "partial", "not_available"]


class OverviewSection(BaseModel):
    state: SectionState
    reason: str | None = None
    sources: list[str] = []
    legal_name: str | None = None
    display_name: str | None = None
    description: str | None = None
    sector: str | None = None
    industry: str | None = None
    sic: str | None = None
    sic_description: str | None = None
    exchange: str | None = None
    employees: int | None = None
    website: str | None = None
    address: str | None = None
    phone: str | None = None


class FinancialsSection(BaseModel):
    state: SectionState
    reason: str | None = None
    sources: list[str] = []
    currency: str | None = None
    market_cap: float | None = None
    revenue_ttm: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    eps_ttm: float | None = None
    debt_to_equity: float | None = None
    free_cash_flow: float | None = None
    dividend_yield: float | None = None


class FilingItem(BaseModel):
    form: str
    description: str
    filed_date: str
    report_date: str | None = None
    accession_number: str
    url: str


class FilingsSection(BaseModel):
    state: SectionState
    reason: str | None = None
    sources: list[str] = []
    items: list[FilingItem] = []


class HolderItem(BaseModel):
    name: str
    kind: Literal["institution", "mutual_fund"]
    pct_held: float | None = None
    shares: float | None = None
    date_reported: str | None = None


class OwnershipSection(BaseModel):
    state: SectionState
    reason: str | None = None
    sources: list[str] = []
    shares_outstanding: float | None = None
    float_shares: float | None = None
    pct_institutions: float | None = None
    pct_insiders: float | None = None
    holders: list[HolderItem] = []


class CompanyProfileResponse(BaseModel):
    ticker: str
    as_of: str
    cik: str | None = None
    overview: OverviewSection
    financials: FinancialsSection
    filings: FilingsSection
    ownership: OwnershipSection


# ── Insider (Form 3/4/5) ─────────────────────────────────────────────────────

TransactionDirection = Literal["buy", "sell", "other"]
NetDirection = Literal["buying", "selling", "mixed", "none"]
PlanType = Literal["scheduled_10b5-1", "discretionary", "unstated"]


class InsiderTransaction(BaseModel):
    form: str
    filed_date: str
    transaction_date: str | None = None
    insider_name: str
    role: str | None = None
    code: str
    code_label: str
    direction: TransactionDirection
    shares: float | None = None
    price: float | None = None
    plan_type: PlanType = Field(
        description=(
            "M5: a FILING-LEVEL Rule 10b5-1 checkbox (`aff10b5One`), not a "
            "per-transaction fact — carried on P/S rows only; every other row "
            "is `unstated`. `scheduled_10b5-1` = box ticked, "
            "`discretionary` = box present and unticked, `unstated` = the "
            "element is absent (pre-April-2023 filings) or unrecognised."
        ),
    )
    url: str


class InsiderSummary(BaseModel):
    buys: int
    sells: int
    other: int
    net_direction: NetDirection


class InsiderResponse(BaseModel):
    ticker: str
    as_of: str
    cik: str | None = None
    state: SectionState
    reason: str | None = None
    sources: list[str] = []
    window_days: int
    summary: InsiderSummary
    transactions: list[InsiderTransaction] = []
