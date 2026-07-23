"""Sharia-compliance verdict types (CR069 Phase 1).

The `halal` mandate flag is enforced by a *sourced allowlist* — the published
constituents of the S&P 500 Sharia Industry Exclusions Index (AAOIFI standard,
screened by S&P Dow Jones), read from the SPUS ETF's daily-transparency holdings
CSV. It is NOT a computed ratio screen: `app.trading_math.screening.sharia_screen`
stays dormant (CR069 constraint 4) until a source supplies real debt / liquid-asset
/ impermissible-income figures.

Three states, never two (CR069 constraint 2 / DEF084):
  PASS         — in the compliant set. Tradeable.
  SCREENED_OUT — in the parent index (S&P 500) but absent from the compliant set.
                 A real exclusion — blocked.
  UNKNOWN      — not in the parent index at all. The standard never looked at it,
                 so it is *no ruling either way*. Permitted, with the disclosure
                 attached (G3 RESOLVED 2026-07-23: permit + disclose).
  UNAVAILABLE  — the source could not be refreshed / is stale beyond its window.
                 The flag pauses loudly (CR069 constraint 3 / CR040) — never a
                 silent fall back to a stale set.

These are value types only; the fetcher, cache and resolver live in
`app.services.sharia_universe` (network belongs in the service layer).
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel


class ShariaStatus(str, Enum):
    PASS = "pass"
    SCREENED_OUT = "screened_out"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


def _as_of_str(as_of: date | None) -> str:
    return as_of.isoformat() if as_of is not None else "unknown"


class ShariaVerdict(BaseModel):
    """A per-ticker Sharia screen verdict carrying its provenance.

    The verdict is NOT a bare boolean by design (CR069 §Acceptance 4): the
    standard, source and as-of date travel with it so every surface that renders
    a trade outcome — and every agent prompt — can name what screened the ticker
    and when. A permitted-unknown trade that says nothing is a silent pass on an
    observance decision, which is this CR's failure class in the other direction.
    """

    status: ShariaStatus
    ticker: str
    standard: str  # e.g. "AAOIFI"
    source: str  # e.g. "S&P 500 Sharia Industry Exclusions Index (via SPUS)"
    as_of: date | None = None

    @property
    def is_blocking(self) -> bool:
        """SCREENED_OUT and UNAVAILABLE block a trade; PASS and UNKNOWN permit it.

        UNKNOWN must NOT block (G3) — an unknown ticker is *no ruling*, not a soft
        no. If UNKNOWN ever reaches a violations list the ruling is inverted.
        """
        return self.status in (ShariaStatus.SCREENED_OUT, ShariaStatus.UNAVAILABLE)

    def message(self) -> str:
        """User-facing line, AMI by name (never "the AI"). Names the standard,
        source and as-of date wherever a verdict is shown (CR069 constraint 1)."""
        t = self.ticker.upper()
        when = _as_of_str(self.as_of)
        if self.status is ShariaStatus.PASS:
            return f"{t} passes the {self.standard} screen ({self.source}, as of {when})."
        if self.status is ShariaStatus.SCREENED_OUT:
            return (
                f"{t} is in the parent index but does not pass the {self.standard} "
                f"screen ({self.source}, as of {when}), so this mandate won't trade it."
            )
        if self.status is ShariaStatus.UNKNOWN:
            return (
                f"{t} isn't in the parent index, so the {self.standard} screen AMI "
                f"uses hasn't reviewed it. That's not a ruling either way — AMI doesn't know."
            )
        # UNAVAILABLE
        return (
            f"AMI couldn't refresh the {self.standard} Sharia screen (last updated "
            f"{when}). The halal filter is paused until it can."
        )
