"""CR287 — sector-aware metrics: say "not applicable", or add context, where a generic figure misleads.

A Room's fact sheet carries the same figures for every company, and for some industries the
accounting makes a generic figure meaningless: a bank's operating cash flow and debt mostly
reflect customer loans and deposits moving, so its free cash flow of -RM15,433M (Maybank) is not
cash the business burns, and the desks argued it as if it were. Measured in
`docs/forward_planning/CR282_bursa_malaysia/bank_fcf_measurement_2026-11-27.md`.

One table, `FAMILY_RULES`: family -> `FamilyRule`. Families come from the sheet's own `industry`
tag (Yahoo's, on US and Bursa sheets alike). A new family is one row here plus a test, added only
after its own measurement. Two kinds of row, never to be confused:

- `not_applicable` (banks): the listed figures are removed from the sheet and one line says why.
- `context` (regulated utilities): every figure stays; one coded line says how to read them.
  Real cash burn must still show, so nothing is removed.

Both kinds skip the CR285 debt-default check ("not applicable: <name>"). Insurers and REITs are
not in the table.

The control is structural, not a prompt (CR038): `apply_to_profile` removes the numbers from the
profile and records each key's `field_state` as `not_applicable`, so the renderer, the coded
money lines, the terminal-question inputs, the debt check, the fact-check and the Risk Officer's
corroboration corpus all lose the figure at once, and the sheet states why in its place. Every
consumer reads the marker `profile["sector_family"]` that `apply_to_profile` writes (never
re-deciding from the switch), so a sheet frozen with the marker is read the same way later.
Behind `ROOM_SECTOR_METRICS_ENABLED` (default off: nothing changes).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

NOT_APPLICABLE_STATE = "not_applicable"
FAMILY_KEY = "sector_family"

KIND_NOT_APPLICABLE = "not_applicable"
KIND_CONTEXT = "context"

BANK = "bank"
REGULATED_UTILITY = "regulated_utility"


@dataclass(frozen=True)
class FamilyRule:
    """How the sheet treats one industry family. `kind` says which of the two it is."""

    family: str
    kind: str
    # The plain name a user reads: "bank", "regulated utility".
    name: str
    # Plural noun for the sheet line ("banks"); not_applicable rows only.
    label: str = ""
    # Short names of the dropped figures, in the order the line lists them (not_applicable only).
    figures: tuple[str, ...] = ()
    # Every profile / field_state key removed and marked (not_applicable only; a context row
    # removes nothing).
    fields: frozenset[str] = frozenset()
    reason: str = ""
    # The whole line, for a context row.
    context: str = ""

    @property
    def line(self) -> str:
        """The one sheet line this family adds."""
        if self.kind == KIND_CONTEXT:
            return self.context
        return f"{', '.join(self.figures)}: not applicable for {self.label} — {self.reason}."

    @property
    def check_reason(self) -> str:
        """The reason the debt check records when it does not run for this family."""
        return f"not applicable: {self.name}"


_BANK_FIELDS = frozenset({
    # 1. Free cash flow and everything derived from it.
    "free_cash_flow", "fcf_yield", "free_cash_flow_ttm", "cashflow_ttm_basis",
    "operating_cash_flow_ttm", "wc_change_ttm", "wc_receivables_ttm", "wc_inventory_ttm",
    "wc_payables_ttm", "fcf_history_years", "fcf_history", "capex_history",
    "fcf_conversion_pct", "capital_return_pct_fcf",
    "sbc", "sbc_ttm", "sbc_period_start", "sbc_period_end",
    # 2. Net debt / net cash, the gross figures it is built from, the debt schedule behind the
    #    debt-default check, and the EV-based multiples.
    "net_cash", "total_debt", "total_cash",
    "debt_maturity", "debt_maturity_labels", "debt_maturity_values", "debt_maturity_period_end",
    "debt_maturity_beyond_5y", "debt_maturity_excluded_st",
    "cost_of_debt", "cost_of_debt_pct", "cost_of_debt_basis", "cost_of_debt_interest",
    "cost_of_debt_gross_debt", "cost_of_debt_period_end",
    "debt_split", "debt_split_state", "debt_split_entity", "debt_split_captive",
    "debt_split_industrial", "debt_split_period",
    "ev_to_ebitda", "historical_ev_ebitda_median", "historical_ev_ebitda_years",
    "historical_ev_ebitda_window", "peer_comparison_median_ev_ebitda",
    "peer_comparison_median_ev_ebitda_n",
    # 3. Interest coverage and its numerator.
    "interest_coverage", "interest_coverage_quarter", "interest_expense_quarter_usd_m",
})

#: The table every consumer reads. Add a family here (and a test), nowhere else.
FAMILY_RULES: dict[str, FamilyRule] = {
    BANK: FamilyRule(
        family=BANK,
        kind=KIND_NOT_APPLICABLE,
        name="bank",
        label="banks",
        figures=("Free cash flow", "net debt", "EV/EBITDA", "interest coverage"),
        fields=_BANK_FIELDS,
        reason="a bank's operating cash flow and debt mostly reflect customer loans and deposits",
    ),
    REGULATED_UTILITY: FamilyRule(
        family=REGULATED_UTILITY,
        kind=KIND_CONTEXT,
        name="regulated utility",
        context=(
            "Context: negative free cash flow from regulated capital spending, and high debt, "
            "are normal for a regulated utility; its returns are set on a regulated asset base."
        ),
    ),
}

_REGULATED_UTILITY_INDUSTRIES = frozenset({
    "utilities - regulated electric",
    "utilities - regulated gas",
    "utilities - regulated water",
})


def _normal_industry(industry: str | None) -> str:
    """Lower-case, with an em or en dash (the Bursa universe file writes "Utilities—Regulated
    Electric") read as the hyphen Yahoo's own tag uses, and spacing around it made uniform."""
    text = re.sub(r"\s*[\u2014\u2013\u2212-]\s*", " - ", (industry or "").strip().lower())
    return re.sub(r"\s+", " ", text)


def family_for(industry: str | None, sector: str | None = None) -> str | None:
    """The family a sheet's industry tag belongs to, or None. `sector` is accepted for the
    families that need it later; Yahoo files every bank under the sector "Financial Services",
    which is no bank signal, so only the industry decides today. Only the three regulated
    utility tags count: Renewable, Diversified and Independent Power Producers are not rows."""
    text = _normal_industry(industry)
    if text.startswith("banks -") or text == "banks":
        return BANK
    if text in _REGULATED_UTILITY_INDUSTRIES:
        return REGULATED_UTILITY
    return None


def _industry_of(profile: Mapping[str, Any] | None) -> tuple[str | None, str | None]:
    p = profile or {}
    state = p.get("field_state") or {}
    industry = p.get("industry") if state.get("industry") == "live" else None
    sector = p.get("sector") if state.get("sector") == "live" else None
    return (
        industry if isinstance(industry, str) else None,
        sector if isinstance(sector, str) else None,
    )


def rule_for(profile: Mapping[str, Any] | None) -> FamilyRule | None:
    """The rule in force on this sheet, of either kind: set by `apply_to_profile` when the sheet
    was built with the switch on and the company is in a listed family. None for every other."""
    family = (profile or {}).get(FAMILY_KEY)
    return FAMILY_RULES.get(family) if isinstance(family, str) else None


def not_applicable(profile: Mapping[str, Any] | None) -> FamilyRule | None:
    """The rule in force when its figures were REMOVED from the sheet (banks); None for a
    context row, whose figures all stay."""
    rule = rule_for(profile)
    return rule if rule is not None and rule.kind == KIND_NOT_APPLICABLE else None


def context_line(profile: Mapping[str, Any] | None) -> str | None:
    """The one context line of a `context` row (regulated utilities), else None."""
    rule = rule_for(profile)
    return rule.line if rule is not None and rule.kind == KIND_CONTEXT else None


def is_not_applicable(field_key: str, profile: Mapping[str, Any] | None) -> bool:
    rule = not_applicable(profile)
    return rule is not None and field_key in rule.fields


def enabled() -> bool:
    from app.core.config import settings

    return bool(settings.room_sector_metrics_enabled)


def apply_to_profile(profile: dict[str, Any]) -> FamilyRule | None:
    """Apply the family rule to a freshly built sheet.

    A `not_applicable` row removes the listed figures and marks their `field_state`; a `context`
    row removes nothing and only records the family. No-op (and None) when the switch is off or
    the company is in no listed family; idempotent when the marker is already there. Mutates
    `profile` in place.
    """
    existing = rule_for(profile)
    if existing is not None:
        return existing
    if not enabled():
        return None
    industry, sector = _industry_of(profile)
    family = family_for(industry, sector)
    rule = FAMILY_RULES.get(family) if family else None
    if rule is None:
        return None
    if rule.kind == KIND_NOT_APPLICABLE:
        state = profile.setdefault("field_state", {})
        for key in rule.fields:
            profile.pop(key, None)
            state[key] = NOT_APPLICABLE_STATE
    profile[FAMILY_KEY] = rule.family
    return rule
