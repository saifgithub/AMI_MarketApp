"""CR244 Part 2 — the float and liquidity block for the Execution Desk and the
Conservative Risk Officer.

Why it exists: a stop on a thin float gaps through its level and a position
that is large against the day's dollar volume cannot be exited at the planned
price. The sheet already states shares outstanding, float and a share-count
average volume to every full-sheet agent, but never the two figures that settle
fill risk: the float as a share of the shares outstanding, and the average daily
DOLLAR volume (a 5M-share day on a $2 stock and on a $200 stock are different
liquidity). Both are AMI-computed here, in code, from two sources already read
by the Room (the Company Review's cached ownership figures and the OHLCV bars
`compute_technicals` fetches) — the LLM never computes one.

State discipline (CR040): the payload is built only when at least one component
resolved; each component that did not carries its own reason and renders as
"not available: <reason>", never imputed. A whole-feed failure is a reason
string the runner records beside `field_state["float_liquidity"]`.
"""

from __future__ import annotations

from typing import Any

FEED_LABEL = "Float & liquidity"
FEED_SOURCE = "yfinance"
ADV_WINDOW_LABEL = "mean of close x volume"


def _fmt_shares(value: float) -> str:
    if value >= 1e9:
        return f"{value / 1e9:,.2f}B"
    if value >= 1e6:
        return f"{value / 1e6:,.2f}M"
    return f"{value:,.0f}"


def _fmt_dollars(value: float) -> str:
    if value >= 1e9:
        return f"${value / 1e9:,.2f}B"
    if value >= 1e6:
        return f"${value / 1e6:,.2f}M"
    return f"${value:,.0f}"


def build_float_liquidity(
    *,
    ownership: Any,
    snapshot_date: str | None,
    adv_dollar: float | None,
    adv_window: int,
    adv_as_of: str | None,
    adv_missing_reason: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """`(payload, None)` when at least one component resolved, else
    `(None, reason)`.

    `ownership` is the Company Review's `OwnershipSection` (duck-typed: only
    `state`, `reason`, `shares_outstanding`, `float_shares` are read), or None
    when no cached profile exists. `snapshot_date` is the date that profile was
    built; it dates the share figures.
    """
    out: dict[str, Any] = {}

    shares_out = float_sh = None
    share_reason = "no company profile is cached for this symbol"
    if ownership is not None:
        shares_out = ownership.shares_outstanding
        float_sh = ownership.float_shares
        share_reason = (
            ownership.reason
            or "yfinance returned no share-count fields for this symbol"
        )
    if shares_out is not None and shares_out <= 0:
        shares_out = None
    if float_sh is not None and float_sh <= 0:
        float_sh = None

    if float_sh is not None:
        out["float_shares"] = float_sh
        out["float_as_of"] = snapshot_date
    else:
        out["float_reason"] = f"float shares missing — {share_reason}"
    if shares_out is not None:
        out["shares_outstanding"] = shares_out
    if float_sh is not None and shares_out is not None:
        if float_sh > shares_out:
            out["float_pct_reason"] = "the source's float exceeds its shares outstanding"
        else:
            out["float_pct"] = round(float_sh / shares_out * 100, 1)
    else:
        missing = "float shares" if float_sh is None else "shares outstanding"
        out["float_pct_reason"] = f"{missing} missing"

    if adv_dollar is not None and adv_window > 0 and adv_as_of:
        out["adv_dollar"] = adv_dollar
        out["adv_window"] = adv_window
        out["adv_as_of"] = adv_as_of
    else:
        out["adv_reason"] = adv_missing_reason

    if not any(k in out for k in ("float_shares", "shares_outstanding", "adv_dollar")):
        return None, f"{share_reason}; {adv_missing_reason}"
    return out, None


def float_liquidity_line(data: dict[str, Any]) -> str:
    """The body line. Facts and their dates only — no instruction rides here;
    what to do with it lives in the desks' personas."""
    parts: list[str] = []
    if "float_shares" in data:
        parts.append(
            f"float {_fmt_shares(data['float_shares'])} sh "
            f"[{FEED_SOURCE}, as of {data.get('float_as_of') or 'unknown date'}]"
        )
    else:
        parts.append(f"float: not available: {data['float_reason']}")
    if "float_pct" in data:
        parts.append(
            f"float is {data['float_pct']:.1f}% of "
            f"{_fmt_shares(data['shares_outstanding'])} sh outstanding "
            f"[{FEED_SOURCE}, as of {data.get('float_as_of') or 'unknown date'}]"
        )
    else:
        so = (
            f"{_fmt_shares(data['shares_outstanding'])} sh outstanding; "
            if "shares_outstanding" in data else ""
        )
        parts.append(f"{so}float % of shares outstanding: not available: {data['float_pct_reason']}")
    if "adv_dollar" in data:
        parts.append(
            f"average daily dollar volume {_fmt_dollars(data['adv_dollar'])} "
            f"[{data['adv_window']}-session {ADV_WINDOW_LABEL}, {FEED_SOURCE} "
            f"daily bars to {data['adv_as_of']}]"
        )
    else:
        parts.append(f"average daily dollar volume: not available: {data['adv_reason']}")
    return f"{FEED_LABEL}: " + " · ".join(parts)


def float_liquidity_unavailable_line(reason: str) -> str:
    return (
        f"{FEED_LABEL}: not available: {reason}. Do not estimate float, share "
        "count or dollar volume from memory."
    )
