"""Read the filing's column-level facts back for the sheet (CR221 A2 / D1 / D2).

The rows come from `edgar_instance.py` via the dimensional ingest; this is the
render-time side, in `debt_maturity.py`'s shape — pure resolvers over
`_FactView`s, then one store touch — so every figure is point-in-time correct
and reusable on a backtest date.

**Three states for the debt split, and they must not blur** (CR040):

  * the filer has no captive lender → nothing, no key, no line;
  * the registry knows a lender but the store resolves no figure → the sheet
    says UNAVAILABLE and that the gross debt above is the blended total;
  * the captive side resolves and the industrial side does not (PCAR tags
    only the finance column) → the captive figure alone, with the line saying
    the industrial side is not separately tagged. It is never computed as
    consolidated minus captive: on CAT that subtraction crosses tag families
    and gives $3,593M for a filed $10,713M.

**A breakdown is a partition or it is nothing.** A filing tags overlapping
cuts of the same total — CAT carries `country:US` / `NonUsMember` beside the
four regions, and an aggregate segment member beside its four segments. The
member set rendered is the largest subset of the tagged members whose sum
falls within 10% of the same filing's consolidated revenue, so the shares
add up and the residual is stated. No partition within the band → no line,
logged with the best coverage found.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from datetime import date
from typing import Sequence

from app.core.logging import logger
from app.services import edgar_pit, edgar_tags
from app.services.edgar_pit import _FactView

# The rows come from 10-Ks only, so between one annual filing and the next the
# newest figure can be up to ~14 months old (a December year-end filed in
# February, read the following February). 400 days — the instant bound the
# quarterly-fed resolvers use — would refuse that last window.
MAX_ANNUAL_AGE_DAYS = 450

# A member set must cover this band of the consolidated total to be rendered,
# and must have at least two members: PACCAR tags one segment at 92% of
# revenue, and one share is not a breakdown.
_COVERAGE_BAND = (0.90, 1.10)
_MIN_PARTITION_MEMBERS = 2
_MAX_PARTITION_MEMBERS = 12

# Members that are themselves totals of other members. The partition search
# would usually reject them on count, but a filer tagging an aggregate beside
# ONE segment could pass on sum alone.
_AGGREGATE_MEMBER = re.compile(r"Aggregation|AllSegmentsMember$|ReportableSegmentsMember$|TotalMember$")

_SEGMENT_TIERS = (
    ("ext", "external sales by segment"),
    ("ops", "segment sales including intersegment"),
    ("bare", "segment revenue as tagged"),
)


# ── Debt split ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DebtSplit:
    lender: str
    period_end: date
    captive: float                # USD
    industrial: float | None      # USD; None = the filing tags no industrial-side figure


def _first(by_tag: dict[str, float], family: Sequence[str]) -> float | None:
    for tag in family:
        if tag in by_tag:
            return by_tag[tag]
    return None


def _side_total(by_tag: dict[str, float]) -> float | None:
    """One column's total debt from whichever concepts it tags — see
    `edgar_tags.DEBT_FAMILY_*` for why `DebtCurrent` displaces the short-term
    family rather than adding to it."""
    combined = _first(by_tag, edgar_tags.DEBT_FAMILY_COMBINED)
    if combined is not None:
        return combined
    noncurrent = _first(by_tag, edgar_tags.DEBT_FAMILY_NONCURRENT)
    if noncurrent is None:
        return None
    current_all = _first(by_tag, edgar_tags.DEBT_FAMILY_CURRENT_ALL)
    if current_all is not None:
        return noncurrent + current_all
    return (
        noncurrent
        + (_first(by_tag, edgar_tags.DEBT_FAMILY_CURRENT_LTD) or 0.0)
        + (_first(by_tag, edgar_tags.DEBT_FAMILY_SHORT) or 0.0)
    )


def _debt_role(tag: str) -> tuple[str, str] | None:
    for prefix, role in (
        (edgar_tags.CAPTIVE_DEBT_TAG + ":", "captive"),
        (edgar_tags.INDUSTRIAL_DEBT_TAG + ":", "industrial"),
    ):
        if tag.startswith(prefix):
            return role, tag[len(prefix):]
    return None


def resolve_debt_split(
    facts: Sequence[_FactView], lender: str, as_of: date,
    *, max_age_days: int = MAX_ANNUAL_AGE_DAYS,
) -> DebtSplit | None:
    """The newest instant at which the captive column resolves; the industrial
    column at that same instant if it does. Newest `filed` wins per concept
    and instant, so an amendment supersedes without special handling."""
    best: dict[tuple[str, str, date], _FactView] = {}
    for f in facts:
        role_source = _debt_role(f.tag)
        if role_source is None:
            continue
        role, source = role_source
        key = (role, source, f.period_end)
        if key not in best or f.filed > best[key].filed:
            best[key] = f
    by_period: dict[date, dict[str, dict[str, float]]] = {}
    for (role, source, end), f in best.items():
        by_period.setdefault(end, {}).setdefault(role, {})[source] = f.value
    for end in sorted(by_period, reverse=True):
        captive = _side_total(by_period[end].get("captive", {}))
        if captive is None:
            continue
        if (as_of - end).days > max_age_days:
            return None
        industrial = _side_total(by_period[end].get("industrial", {}))
        return DebtSplit(lender=lender, period_end=end, captive=captive, industrial=industrial)
    return None


# ── Revenue breakdowns ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class RevenueBreakdown:
    period_end: date
    labels: tuple[str, ...]
    values: tuple[float, ...]   # USD, descending
    total: float                # the same filing's consolidated revenue, USD
    basis: str

    @property
    def coverage_pct(self) -> float:
        return round(100.0 * sum(self.values) / self.total, 1)


def select_partition(members: dict[str, float], total: float) -> tuple[str, ...] | None:
    """The largest subset of `members` whose sum lies within `_COVERAGE_BAND`
    of `total`; ties broken by closeness. Brute force over at most twelve
    members — four thousand sums, and a filing never tags more."""
    if total <= 0 or not members:
        return None
    names = sorted(members, key=lambda n: -members[n])[:_MAX_PARTITION_MEMBERS]
    lo, hi = _COVERAGE_BAND
    for size in range(len(names), _MIN_PARTITION_MEMBERS - 1, -1):
        best: tuple[float, tuple[str, ...]] | None = None
        for combo in itertools.combinations(names, size):
            total_of = sum(members[n] for n in combo)
            if lo <= total_of / total <= hi:
                gap = abs(total_of - total)
                if best is None or gap < best[0]:
                    best = (gap, combo)
        if best is not None:
            return best[1]
    return None


_COUNTRY_NAMES = {
    "US": "United States", "CA": "Canada", "GB": "United Kingdom", "DE": "Germany",
    "JP": "Japan", "CN": "China", "MX": "Mexico", "BR": "Brazil", "IN": "India",
    "AU": "Australia", "FR": "France", "IT": "Italy", "KR": "South Korea",
    "NL": "Netherlands", "CH": "Switzerland", "IE": "Ireland", "SG": "Singapore",
    "ES": "Spain", "TW": "Taiwan", "SE": "Sweden", "HK": "Hong Kong", "IL": "Israel",
}
_SPECIAL_LABELS = {
    "NonUs": "Non-US", "UnitedStates": "United States", "US": "United States",
    "EMEA": "EMEA", "APAC": "APAC", "MachineryPowerEnergy": "Machinery, Power & Energy",
}
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def member_label(qname: str) -> str:
    """`cat:ConstructionIndustriesMember` → `Construction Industries`;
    `country:US` → `United States`; `srt:NorthAmericaMember` → `North America`."""
    prefix, _, local = str(qname).rpartition(":")
    if prefix == "country":
        return _COUNTRY_NAMES.get(local, local)
    local = re.sub(r"Member$", "", local)
    local = re.sub(r"Segment$", "", local)
    if local in _SPECIAL_LABELS:
        return _SPECIAL_LABELS[local]
    words = _CAMEL.sub(" ", local).split()
    return " ".join("and" if w == "And" else w for w in words)


def _newest(facts: Sequence[_FactView]) -> dict[str, _FactView]:
    """Per tag, the newest `period_end`, ties to the newest `filed`."""
    out: dict[str, _FactView] = {}
    for f in facts:
        held = out.get(f.tag)
        if held is None or (f.period_end, f.filed) > (held.period_end, held.filed):
            out[f.tag] = f
    return out


def _consolidated_revenue(facts: Sequence[_FactView], as_of: date, max_age_days: int) -> tuple[float, date] | None:
    prefix = edgar_tags.CONSOLIDATED_REVENUE_TAG + ":"
    candidates = [f for f in _newest(facts).values() if f.tag.startswith(prefix)]
    if not candidates:
        return None
    newest_end = max(f.period_end for f in candidates)
    if (as_of - newest_end).days > max_age_days:
        return None
    at_end = [f for f in candidates if f.period_end == newest_end]
    at_end.sort(key=lambda f: edgar_tags.REVENUE_TAGS.index(f.tag[len(prefix):])
                if f.tag[len(prefix):] in edgar_tags.REVENUE_TAGS else 99)
    return at_end[0].value, newest_end


def _members_at(facts: Sequence[_FactView], prefix: str, end: date) -> dict[str, float]:
    best: dict[str, _FactView] = {}
    for f in facts:
        if not f.tag.startswith(prefix) or f.period_end != end:
            continue
        member = f.tag[len(prefix):]
        if _AGGREGATE_MEMBER.search(member):
            continue
        held = best.get(member)
        if held is None or f.filed > held.filed:
            best[member] = f
    return {member: f.value for member, f in best.items()}


def _breakdown(members: dict[str, float], total: float, end: date, basis: str) -> RevenueBreakdown | None:
    chosen = select_partition(members, total)
    if not chosen:
        return None
    ordered = sorted(chosen, key=lambda m: -members[m])
    return RevenueBreakdown(
        period_end=end,
        labels=tuple(member_label(m) for m in ordered),
        values=tuple(members[m] for m in ordered),
        total=total,
        basis=basis,
    )


def resolve_segment_revenue(
    facts: Sequence[_FactView], as_of: date, *, max_age_days: int = MAX_ANNUAL_AGE_DAYS,
) -> RevenueBreakdown | None:
    consolidated = _consolidated_revenue(facts, as_of, max_age_days)
    if consolidated is None:
        return None
    total, end = consolidated
    for tier, basis in _SEGMENT_TIERS:
        members = _members_at(facts, f"{edgar_tags.SEGMENT_REVENUE_TAG}:{tier}:", end)
        found = _breakdown(members, total, end, basis)
        if found is not None:
            return found
    return None


def resolve_geographic_revenue(
    facts: Sequence[_FactView], as_of: date, *, max_age_days: int = MAX_ANNUAL_AGE_DAYS,
) -> RevenueBreakdown | None:
    consolidated = _consolidated_revenue(facts, as_of, max_age_days)
    if consolidated is None:
        return None
    total, end = consolidated
    members = _members_at(facts, edgar_tags.GEOGRAPHIC_REVENUE_TAG + ":", end)
    return _breakdown(members, total, end, "revenue by region as tagged")


# ── The store touch ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FilingDimensions:
    lender: str | None            # registry hit, whether or not the split resolved
    debt_split: DebtSplit | None
    segments: RevenueBreakdown | None
    geography: RevenueBreakdown | None


def fetch_filing_dimensions(ticker: str, as_of: date) -> FilingDimensions:
    """One query for a ticker's derived rows, three resolutions. Raises on a
    store failure — the caller decides what a missing store costs."""
    lender = edgar_tags.captive_finance_lender(ticker)
    facts = edgar_pit.load_facts_by_prefix(ticker, edgar_tags.DIMENSIONAL_TAXONOMY + ":", as_of)
    split = resolve_debt_split(facts, lender, as_of) if lender else None
    segments = resolve_segment_revenue(facts, as_of)
    geography = resolve_geographic_revenue(facts, as_of)
    if facts and segments is None:
        logger.info(
            "filing_segment_revenue_no_partition", ticker=ticker.upper(),
            rows=sum(1 for f in facts if f.tag.startswith(edgar_tags.SEGMENT_REVENUE_TAG)),
        )
    return FilingDimensions(lender=lender, debt_split=split, segments=segments, geography=geography)
