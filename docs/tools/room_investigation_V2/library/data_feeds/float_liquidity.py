"""CR244 Part 2 reference implementation — the share float / liquidity feed
for the Trader (Execution Desk) and Conservative Risk Officer Room prompts.

Per CR244's "Part 2 — Room agent feeds" table, this feed extends the
already-open yfinance `.info` read (`backend/app/services/company_profile.py`
and `fundamentals.py` already hold that connection for other fields; no new
integration is introduced). Fields: `shares_outstanding`, `float_shares`,
ADV (`averageVolume`, with `averageVolume10days` as the documented
equivalent when the primary key is absent), `pct_insiders`
(`heldPercentInsiders`), `pct_institutions` (`heldPercentInstitutions`), and
the computed `float_pct_outstanding`. Dependencies: stdlib + yfinance; it
imports nothing from `backend.app`.

Ported behaviours that are load-bearing, not optional:

- **The unknown-ticker trap (B5).** A yfinance `.info` payload for a ticker
  yfinance does NOT know is not empty — it is `{'trailingPegRatio': None}`
  (verified live 2026-09-27), a truthy dict. Only a payload carrying at
  least one identity key (`longName`/`shortName`/`quoteType`/
  `regularMarketPrice`) counts as "yfinance knows this ticker"; anything
  else is `not_available`, never a row of nulls reading as a real company.
- **Percent keys are FRACTIONS.** yfinance returns `heldPercentInsiders` /
  `heldPercentInstitutions` as fractions (0.042, not 4.2) — the same
  convention the CR244 API contract's ownership section documents. They are
  passed through raw; `float_line` does the ×100 at render time only.
- **Real zeros survive.** A `pct_insiders` of 0.0 is data, not absence; no
  field is read through `or`-fallbacks that would collapse 0.0 to None.

**State/provenance discipline (CR040, degrade loudly).** `state` ∈ `live` |
`partial` | `not_available`; `reason` is required whenever
`state != "live"`:

- `live`: every field resolved.
- `partial`: yfinance answered but one or more fields are absent — `reason`
  names exactly which. Available fields are still emitted, never blanked to
  match the missing ones.
- `not_available`: yfinance errored, or the ticker is unknown to it, or it
  returned a payload with no float/liquidity fields at all. Nothing is
  fabricated — every numeric field is None in this state.

`float_line` is the `..._line()` renderer of CR244's 5-point pattern: the
compact body line the Trader and Conservative Risk Officer prompts would
carry — factual, explicit about what is missing, and an explicit
not-available sentence (never a silent blank) when the feed fails.
"""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_IDENTITY_KEYS = ("longName", "shortName", "quoteType", "regularMarketPrice")

_FIELD_LABELS = {
    "shares_outstanding": "shares outstanding",
    "float_shares": "float shares",
    "adv_shares": "average daily volume",
    "pct_insiders": "insider ownership %",
    "pct_institutions": "institutional ownership %",
}


@dataclass(frozen=True)
class FloatLiquidity:
    ticker: str
    state: str  # "live" | "partial" | "not_available"
    reason: str | None
    shares_outstanding: float | None
    float_shares: float | None
    adv_shares: float | None
    pct_insiders: float | None
    pct_institutions: float | None
    float_pct_outstanding: float | None


def _yf_num(d: dict, key: str) -> float | None:
    v = d.get(key)
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _has_identity(info: dict | None) -> bool:
    if not info:
        return False
    return any(info.get(k) is not None for k in _IDENTITY_KEYS)


def _yf_info(ticker: str) -> tuple[dict | None, str | None]:
    """(info, failure_reason). A None info with a None reason means yfinance
    answered but does not know this ticker (the B5 all-None payload) — that
    is a different story from a fetch error and the two must not blur."""
    try:
        import yfinance as yf

        info = yf.Ticker(ticker.upper()).info
    except Exception as exc:  # yfinance raises ad-hoc exception types
        logger.warning("yfinance_float_liquidity_error ticker=%s error=%s", ticker, str(exc)[:200])
        return None, "yfinance data unavailable for this symbol"
    if not _has_identity(info):
        return None, None
    return info, None


def _not_available(sym: str, reason: str) -> FloatLiquidity:
    return FloatLiquidity(
        ticker=sym, state="not_available", reason=reason,
        shares_outstanding=None, float_shares=None, adv_shares=None,
        pct_insiders=None, pct_institutions=None, float_pct_outstanding=None,
    )


async def fetch_float_liquidity(ticker: str) -> FloatLiquidity:
    sym = ticker.upper().strip()
    info, failure = await asyncio.to_thread(_yf_info, sym)
    if info is None:
        return _not_available(sym, failure or "No yfinance data for this symbol")

    shares_outstanding = _yf_num(info, "sharesOutstanding")
    float_shares = _yf_num(info, "floatShares")
    adv_shares = _yf_num(info, "averageVolume")
    if adv_shares is None:
        adv_shares = _yf_num(info, "averageVolume10days")
    pct_insiders = _yf_num(info, "heldPercentInsiders")
    pct_institutions = _yf_num(info, "heldPercentInstitutions")

    float_pct_outstanding = (
        float_shares / shares_outstanding
        if float_shares is not None and shares_outstanding
        else None
    )

    fields = {
        "shares_outstanding": shares_outstanding,
        "float_shares": float_shares,
        "adv_shares": adv_shares,
        "pct_insiders": pct_insiders,
        "pct_institutions": pct_institutions,
    }
    missing = [_FIELD_LABELS[k] for k, v in fields.items() if v is None]
    if len(missing) == len(fields):
        return _not_available(sym, "yfinance returned no float/liquidity fields for this symbol")
    if missing:
        return FloatLiquidity(
            ticker=sym, state="partial",
            reason="Missing from yfinance: " + ", ".join(missing),
            shares_outstanding=shares_outstanding, float_shares=float_shares,
            adv_shares=adv_shares, pct_insiders=pct_insiders,
            pct_institutions=pct_institutions,
            float_pct_outstanding=float_pct_outstanding,
        )
    return FloatLiquidity(
        ticker=sym, state="live", reason=None,
        shares_outstanding=shares_outstanding, float_shares=float_shares,
        adv_shares=adv_shares, pct_insiders=pct_insiders,
        pct_institutions=pct_institutions,
        float_pct_outstanding=float_pct_outstanding,
    )


def _fmt_shares(value: float | None) -> str:
    if value is None:
        return "n/a"
    abs_v = abs(value)
    if abs_v >= 1e9:
        return f"{value / 1e9:,.2f}B"
    if abs_v >= 1e6:
        return f"{value / 1e6:,.1f}M"
    return f"{value:,.0f}"


def _fmt_pct(fraction: float | None) -> str:
    if fraction is None:
        return "n/a"
    return f"{fraction * 100:.1f}%"


def float_line(fl: FloatLiquidity) -> str:
    label = "Float & liquidity (yfinance)"
    if fl.state == "not_available":
        return (
            f"{label}: NOT AVAILABLE — {fl.reason}. Do not estimate float, "
            f"trading volume, or ownership concentration from memory."
        )

    parts: list[str] = []
    if fl.float_shares is not None:
        float_part = f"float {_fmt_shares(fl.float_shares)} sh"
        if fl.float_pct_outstanding is not None and fl.shares_outstanding is not None:
            float_part += (
                f" ({fl.float_pct_outstanding * 100:.1f}% of "
                f"{_fmt_shares(fl.shares_outstanding)} sh outstanding)"
            )
        parts.append(float_part)
    elif fl.shares_outstanding is not None:
        parts.append(f"{_fmt_shares(fl.shares_outstanding)} sh outstanding")
    if fl.adv_shares is not None:
        parts.append(f"ADV {_fmt_shares(fl.adv_shares)} sh/day")
    if fl.pct_insiders is not None:
        parts.append(f"insiders hold {_fmt_pct(fl.pct_insiders)}")
    if fl.pct_institutions is not None:
        parts.append(f"institutions hold {_fmt_pct(fl.pct_institutions)}")

    state_note = f" (partial — {fl.reason})" if fl.state == "partial" else ""
    return f"{label}{state_note}: " + " · ".join(parts)
