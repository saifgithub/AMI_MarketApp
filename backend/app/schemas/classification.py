"""Sector/industry classification verdict types (DEF061).

The `no_fossil_fuels` and `no_tobacco_alcohol_gambling` mandate flags are enforced
by a *sourced exclusion set* — the ~503 S&P parent constituents already persisted by
CR075 are classified once a day by their yfinance `sector` / `industry`, and the
derived fossil-fuel set + sin set are held in a snapshot row. This mirrors the CR069
sourced-Sharia-universe architecture exactly: an append-only snapshot, a daily
background refresh (the only socket), a read path that resolves from the stored row
with no network, and a loud pause when the universe can't be refreshed.

It is NOT a real-time revenue-mix screen: it is a static per-ticker sector/industry
tag, the same class of data `fundamentals.py` already reads. The reviewable artifact
is the pinned industry-string map in `app.services.classification_universe`, like
AAOIFI's thresholds are for the halal screen.

Four states, never two (mirrors the CR069/DEF084 lesson — the exclusion set alone
cannot tell "excluded" from "never classified"):
  PERMITTED    — in the classified universe and NOT in this kind's exclusion set.
                 Tradeable.
  EXCLUDED     — in this kind's exclusion set (a fossil-fuel producer, or a
                 tobacco/alcohol/gambling name). A real exclusion — blocked.
  UNKNOWN      — not in the classified universe at all. AMI never classified it, so
                 it is *no ruling either way*. Permitted, with the disclosure
                 attached (mirrors halal G3: permit + disclose). Blocking-on-unknown
                 would reject every unclassified name — the DEF059 inversion trap.
  UNAVAILABLE  — the classification universe could not be refreshed / is stale beyond
                 its window, or is absent (seed). The flag pauses loudly (CR040) —
                 never a silent fall back to an empty set that permits everything.

These are value types only; the classifier, cache and resolver live in
`app.services.classification_universe`.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel


class ClassificationKind(str, Enum):
    """Which mandate exclusion this verdict answers."""

    FOSSIL_FUELS = "fossil_fuels"
    SIN = "sin"  # tobacco / alcohol / gambling — one combined exclusion set
    ESG_LITE = "esg_lite"  # CURATED best-effort proxy (fossil ∪ sin ∪ weapons/defense)


class ClassificationStatus(str, Enum):
    PERMITTED = "permitted"
    EXCLUDED = "excluded"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


_KIND_LABEL: dict[ClassificationKind, str] = {
    ClassificationKind.FOSSIL_FUELS: "fossil-fuel",
    ClassificationKind.SIN: "tobacco / alcohol / gambling",
    ClassificationKind.ESG_LITE: "curated ESG-lite (fossil fuels, sin, weapons/defense)",
}

# The user-facing name of each Settings toggle, so the block message matches the
# label the user actually flipped (shown == enforced).
_FILTER_NAME: dict[ClassificationKind, str] = {
    ClassificationKind.FOSSIL_FUELS: "No fossil fuels",
    ClassificationKind.SIN: "No tobacco / alcohol / gambling",
    ClassificationKind.ESG_LITE: "ESG-lite",
}

# CR040 honesty: esg_lite is a CURATED SECTOR/INDUSTRY PROXY, not a rated ESG score.
# The founder ruled "curate for now; a real rated-ESG feed comes later as a paid
# value-added service" — so every esg_lite message names it as best-effort curation
# and must NOT imply a rating AMI doesn't have (DEF059 confident-false class).
_ESG_LITE_DISCLAIMER = (
    "AMI's curated best-effort ESG proxy (fossil fuels + tobacco/alcohol/gambling + "
    "weapons/defense), NOT a rated ESG score"
)

_SOURCE = "AMI sector/industry classification"


def _as_of_str(as_of: date | None) -> str:
    return as_of.isoformat() if as_of is not None else "unknown"


class ClassificationVerdict(BaseModel):
    """A per-ticker sector/industry-exclusion verdict carrying its provenance.

    Like `ShariaVerdict`, this is NOT a bare boolean: the kind, source and as-of
    date travel with it so every surface (and every agent prompt) can name what
    excluded a ticker and when — and, crucially, so a PERMITTED-but-UNKNOWN trade
    still surfaces "AMI hasn't classified this name". A permitted-unknown that says
    nothing is a silent pass on a values decision, the failure class in the other
    direction.
    """

    status: ClassificationStatus
    ticker: str
    kind: ClassificationKind
    source: str = _SOURCE
    as_of: date | None = None

    @property
    def is_blocking(self) -> bool:
        """EXCLUDED and UNAVAILABLE block a trade; PERMITTED and UNKNOWN permit it.

        UNKNOWN must NOT block — an unclassified ticker is *no ruling*, not a soft
        no. If UNKNOWN ever reaches a violations list the ruling is inverted and the
        filter rejects every name AMI hasn't classified (the DEF059 inversion trap).
        """
        return self.status in (
            ClassificationStatus.EXCLUDED,
            ClassificationStatus.UNAVAILABLE,
        )

    def message(self) -> str:
        """User-facing line, AMI by name (never "the AI").

        For `esg_lite` the provenance phrase is the curated-proxy disclaimer, not a
        bare source string — so no esg_lite verdict can read as a rated ESG score
        (CR040 honesty; the founder's "curate for now, rated feed later" ruling)."""
        t = self.ticker.upper()
        label = _KIND_LABEL[self.kind]
        when = _as_of_str(self.as_of)
        src = (
            _ESG_LITE_DISCLAIMER
            if self.kind is ClassificationKind.ESG_LITE
            else self.source
        )
        if self.status is ClassificationStatus.PERMITTED:
            return f"{t} is classified and clears AMI's {label} filter ({src}, as of {when})."
        if self.status is ClassificationStatus.EXCLUDED:
            return (
                f"{t} is classified under the {label} exclusion, so this mandate's "
                f"'{_FILTER_NAME[self.kind]}' filter won't trade it ({src}, as of {when})."
            )
        if self.status is ClassificationStatus.UNKNOWN:
            return (
                f"AMI hasn't classified {t} for the {label} filter — it isn't in AMI's "
                f"classified universe. That's not a ruling either way; the trade is permitted."
            )
        # UNAVAILABLE
        return (
            f"AMI couldn't refresh its {label} sector/industry classification (last "
            f"updated {when}). The '{_FILTER_NAME[self.kind]}' filter is paused until it can."
        )
