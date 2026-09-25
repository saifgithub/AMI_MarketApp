"""Liquidity verdict types (DEF417).

The `liquid_only` mandate flag ("Liquid only. Avoid microcaps (< $500M market cap)
and illiquid names.") was rendered into every PM-lineage prompt
(`agents/overlay_generator.py`, `services/concierge_engine.py`) but had no
deterministic enforcement — the safety floor's `check_mandate_compliance` had no
`liquid_only` branch at all. Prompt instructions are not controls (CLAUDE.md,
CR038): an abliterated model holds a prompt-only instruction even less reliably
than a well-behaved one.

This mirrors the DEF061 classification architecture exactly, on the SAME sourced
snapshot (`classification_universe.py`'s daily refresh already opens one
`yf.Ticker(t).info` socket per S&P parent constituent — market cap and average
volume are read from that SAME dict, at zero extra network cost, and persisted
alongside `sectors` on `ClassificationUniverseSnapshotRow`). No new provider, no
new socket, no paid feed.

Two independent measures, either one sufficient to exclude a name:
  * **Market cap floor** — $500M (`MICROCAP_FLOOR_USD_M`). Below the SEC's
    "smaller reporting company" public-float threshold ($250M) and inside the
    common industry microcap band (roughly $50M-$300M by Nasdaq/Investopedia
    convention, up to $500M by some broker screens); $500M is the number this
    app already prints in the PM/Trader prompt overlay
    (`overlay_generator.py::_MICROCAP_FLOOR_USD_M`) and in the concierge
    mandate-readback chip ("ONLY liquid names (no microcaps)") — this module
    makes that EXACT, already-user-facing number the enforced one (shown ==
    enforced, CR046 C-a), rather than inventing a second threshold nobody
    reviewed.
  * **Average dollar volume floor** — $1M/day (`ILLIQUID_AVG_DOLLAR_VOLUME_USD`).
    Market cap alone answers "how big is the company", not "can a retail order
    move the tape" — a name can carry a large float-adjusted cap while trading
    thin (low public float, dual-class overhang). $1M/day average dollar volume
    is a conservative floor even for a small simulated account (FINRA/Nasdaq
    commonly cite sub-$1M/day turnover as an illiquidity screen for retail
    execution risk); this account trades in the thousands of dollars, so $1M/day
    of turnover leaves ample headroom before market impact becomes a real
    concern.

Four states, never two (mirrors CR069/DEF084 — an exclusion set alone cannot
tell "excluded" from "never measured"):
  PERMITTED    — market cap AND average dollar volume are both known and both
                 clear their floor. Tradeable.
  EXCLUDED     — market cap or average dollar volume is known and BELOW its
                 floor. A real exclusion — blocked.
  UNKNOWN      — neither figure is available for this ticker (absent from the
                 classified universe, exactly like DEF061's sector tags — most
                 often because it is outside the ~503 S&P parent constituents
                 this snapshot classifies, e.g. a small-cap or recent IPO).
                 AMI never measured it, so this is *no ruling either way*.
                 Permitted, with the disclosure attached (mirrors halal G3).
                 Blocking-on-unknown would reject every unclassified name — the
                 DEF059 inversion trap, and it would be the WRONG direction
                 here specifically: an unmeasured ticker is disproportionately
                 likely to be a smaller name, so blocking-on-unknown would
                 silently over-enforce exactly the tickers `liquid_only` cares
                 about most.
  UNAVAILABLE  — the classification universe (which this rides on) could not be
                 refreshed / is stale beyond its window, or is absent (seed).
                 The flag pauses loudly (CR040) — never a silent fall back to
                 an empty set that permits everything.

These are value types only; the resolver lives on `ClassificationUniverse`
(`app.services.classification_universe`), which already carries the sourced
snapshot this rides on.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel

# $500M — the SAME number already rendered into every PM/Trader prompt overlay
# (`overlay_generator._MICROCAP_FLOOR_USD_M`) and the concierge mandate-readback
# chip. Defined here (the enforcement side) and imported by the prompt-copy side,
# so there is exactly one number, never two that could drift apart (CR046 C-a).
MICROCAP_FLOOR_USD_M = 500

# $1M/day average dollar volume (avg 3-month volume x price). A name can clear
# the market-cap floor on a large float-adjusted cap while trading thin — this
# is the "and illiquid names" half of the mandate flag's own prompt text, which
# market cap alone cannot settle (fundamentals.py's own comment on
# `volume_avg_3m`, CR146 Tier B).
ILLIQUID_AVG_DOLLAR_VOLUME_USD = 1_000_000

_SOURCE = "AMI sector/industry classification snapshot (yfinance market cap + average volume)"

# DEF417 round 2 — the on-demand lookup's own source label, distinct from the
# snapshot's (`_SOURCE`), so a verdict's `source` field always names which read
# actually produced it, exactly as `ClassificationVerdict` already does per kind.
ON_DEMAND_SOURCE = "AMI on-demand liquidity lookup (yfinance, 24h cached)"


class LiquidityStatus(str, Enum):
    PERMITTED = "permitted"
    EXCLUDED = "excluded"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    # DEF417 round 2 — Saiful's ruling: a ticker outside the ~503-name snapshot
    # is looked up ON DEMAND (yfinance, cached 24h) rather than left UNKNOWN.
    # LOOKUP_FAILED is the new, narrower failure mode this creates: the SNAPSHOT
    # is healthy (unlike UNAVAILABLE, where the whole snapshot is stale/absent),
    # but the specific on-demand read for THIS ticker errored or timed out.
    # Same non-blocking treatment as UNAVAILABLE (`is_disclosed_pause`) — "AMI
    # tried to look this name up and couldn't" must never silently become
    # either a block (DEF059 direction) or a silent permit (CR040).
    LOOKUP_FAILED = "lookup_failed"


def _as_of_str(as_of: date | None) -> str:
    return as_of.isoformat() if as_of is not None else "unknown"


class LiquidityVerdict(BaseModel):
    """A per-ticker liquidity verdict carrying its provenance and the measured
    figures, when known — so a message can state the actual market cap / dollar
    volume that failed the floor, not just the fact that it failed.

    Not a bare boolean, same reasoning as `ShariaVerdict`/`ClassificationVerdict`:
    every surface (and every agent prompt) can name why a name was excluded, and
    a PERMITTED-but-UNKNOWN trade still surfaces "AMI has no liquidity data for
    this name" rather than reading as a silent pass on a mandate the user asked
    to be uncoachable.
    """

    status: LiquidityStatus
    ticker: str
    market_cap_usd_m: float | None = None
    avg_dollar_volume_usd: float | None = None
    source: str = _SOURCE
    as_of: date | None = None

    @property
    def is_blocking(self) -> bool:
        """Only EXCLUDED blocks a trade — a REAL, measured microcap/illiquid
        reading. PERMITTED, UNKNOWN and UNAVAILABLE all permit it.

        UNKNOWN must NOT block — an unmeasured ticker is *no ruling*, not a soft
        no. If UNKNOWN ever reached a violations list the ruling would invert and
        the filter would reject every name outside the classified parent set
        (the DEF059 inversion trap — and the wrong direction for THIS flag,
        since an unmeasured name skews smaller, not larger).

        UNAVAILABLE deliberately does NOT block either — this is the one
        divergence from the DEF061 classification seam (`ClassificationVerdict.
        is_blocking`, where UNAVAILABLE DOES block). `no_fossil_fuels` /
        `no_tobacco_alcohol_gambling` / `esg_lite` are opt-IN (default False), so
        a classification-source outage silences enforcement only for the users
        who explicitly turned one on. `liquid_only` defaults True on `Compliance`
        — an opt-OUT flag nearly every mandate carries — so treating the SAME
        snapshot's outage as blocking here would refuse a BUY for essentially
        every user in the app the moment the daily refresh lags or the screen is
        (mis)configured off, which is a materially different, much larger blast
        radius than the flags this pattern was built for. `is_disclosed_pause`
        below is how a caller still surfaces the pause loudly (CR040) without
        that collateral damage — advisory, not violation.
        """
        return self.status is LiquidityStatus.EXCLUDED

    @property
    def is_disclosed_pause(self) -> bool:
        """UNAVAILABLE (whole snapshot stale/absent) or LOOKUP_FAILED (this one
        ticker's on-demand read errored/timed out) — either way the screen
        didn't run for this trade, and that must still reach the user (CR040
        degrade-loudly), as an advisory rather than a block. See `is_blocking`'s
        docstring for why this flag doesn't hard-block on either state."""
        return self.status in (LiquidityStatus.UNAVAILABLE, LiquidityStatus.LOOKUP_FAILED)

    def message(self) -> str:
        """User-facing line, AMI by name (never "the AI")."""
        t = self.ticker.upper()
        when = _as_of_str(self.as_of)
        if self.status is LiquidityStatus.PERMITTED:
            cap = self.market_cap_usd_m
            cap_str = f"${cap:,.0f}M market cap" if cap is not None else "known market cap"
            return (
                f"{t} clears AMI's liquidity filter ({cap_str}, as of {when}) — "
                f"above the ${MICROCAP_FLOOR_USD_M}M microcap floor and trading "
                "actively enough for this account."
            )
        if self.status is LiquidityStatus.EXCLUDED:
            reasons = []
            if self.market_cap_usd_m is not None and self.market_cap_usd_m < MICROCAP_FLOOR_USD_M:
                reasons.append(
                    f"${self.market_cap_usd_m:,.0f}M market cap is below AMI's "
                    f"${MICROCAP_FLOOR_USD_M}M microcap floor"
                )
            if (
                self.avg_dollar_volume_usd is not None
                and self.avg_dollar_volume_usd < ILLIQUID_AVG_DOLLAR_VOLUME_USD
            ):
                reasons.append(
                    f"average daily dollar volume of ${self.avg_dollar_volume_usd:,.0f} is "
                    f"below AMI's ${ILLIQUID_AVG_DOLLAR_VOLUME_USD:,.0f} illiquidity floor"
                )
            reason = "; ".join(reasons) or "it fails AMI's liquidity floor"
            return (
                f"{t} is classified under AMI's liquidity exclusion ({reason}, as of "
                f"{when}), so this mandate's 'Liquid only' filter won't trade it."
            )
        if self.status is LiquidityStatus.UNKNOWN:
            return (
                f"AMI hasn't measured {t}'s market cap or trading volume for the "
                "liquidity filter — it isn't in AMI's classified universe. That's "
                "not a ruling either way; the trade is permitted."
            )
        if self.status is LiquidityStatus.LOOKUP_FAILED:
            # DEF417 round 2 — the snapshot didn't have this ticker, AMI tried an
            # on-demand read and it errored or timed out. Named distinctly from
            # UNAVAILABLE (below) so a user never reads "AMI couldn't refresh its
            # classification" when the classification is fine and only this one
            # ticker's live lookup failed.
            return (
                f"AMI tried to look up {t}'s market cap and trading volume "
                "on demand (it isn't in AMI's classified universe) and couldn't "
                "get an answer in time. That's not a ruling either way; the "
                "trade is permitted."
            )
        # UNAVAILABLE
        return (
            f"AMI couldn't refresh its liquidity classification (last updated "
            f"{when}). The 'Liquid only' filter is paused until it can."
        )
