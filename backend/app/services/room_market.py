"""Market-awareness for the Room's fact sheet and prompts (CR282 lane E).

The Room is built for US equities; a Bursa Malaysia (`.KL`) Room differs in its
currency, its benchmark, its macro datum, and which inputs exist at all. Every
difference lives behind `profile["market"]`, a key that only a MY sheet carries,
so a US sheet is byte-identical to what it was before CR282 — the Room bank's
policy version hashes every agent's derived prompt, and any change to US text
would re-key every banked US Room (`test_cr282_room_us_byte_identical.py`).

What lives here: the market of a sheet, the ringgit rendering of dollar-shaped
figures, and the one place that words "not available for this market" for the
inputs that come from SEC EDGAR (no Bursa equivalent is ingested yet).
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas import AgentId
from app.trading_math.markets import Market, market_for, spec_for

#: The one phrase every dark input uses, so a reader (and a test) can find them all.
NOT_AVAILABLE_FOR_MARKET = (
    "not available for this market (Bursa Malaysia filings are not yet ingested)"
)

#: The index a Bursa name's relative strength is measured against (`^KLSE`).
MY_BENCHMARK_NAME = "FBM KLCI"

# `$-15,433M` is how the US formatters write a negative amount; it localises to
# `-RM15,433M`, the sign before the symbol.
_DOLLAR_AMOUNT_RE = re.compile(r"\$(-?)(?=\d)")


# DEF548 — the sign of a negative amount goes BEFORE the currency symbol
# ("-RM14,077M", "-$12.00"), the way every coded line writes it. A desk turn is
# model output and printed "RM-14,077M" once; a prompt cannot hold the form
# (CR038), so every desk turn is rewritten here before it is stored or streamed.
# The symbol must start a token (so "XRM-5" and "CAD$-5" are not touched) and the
# minus must be followed by a digit (so "RM1-2", "$10-$20" and a bare "$-" are not
# a sign). Only an ASCII hyphen or U+2212 minus counts: an en dash is a range.
_SIGN_AFTER_SYMBOL_RE = re.compile(
    r"(?<![A-Za-z0-9])(US\$|S\$|RM|MYR|[$£€])[ ]?([-\u2212])[ ]?(?=\d)"
)


def normalize_money_sign(text: str) -> str:
    """Rewrite `RM-1,234`, `RM -1,234`, `$-12.00` and `US$-5` as `-RM1,234`,
    `-$12.00` and `-US$5`. Market-agnostic (Bursa and US); any other text is
    returned unchanged."""
    if not text or ("-" not in text and "\u2212" not in text):
        return text
    return _SIGN_AFTER_SYMBOL_RE.sub(lambda m: f"{m.group(2)}{m.group(1)}", text)


def market_of_profile(profile: dict[str, Any] | None) -> Market:
    """US unless the sheet says otherwise. Only a MY sheet carries the key."""
    if profile and profile.get("market") == Market.MY.value:
        return Market.MY
    return Market.US


def is_my(profile: dict[str, Any] | None) -> bool:
    return market_of_profile(profile) is Market.MY


def localize_money(text: str, market: Market) -> str:
    """Render the dollar-shaped amounts in `text` in the market's currency.

    A `$` directly before a digit (or before a minus and a digit) is an amount,
    whatever the formatter that wrote it; a `$` anywhere else (a cashtag in a
    headline) is left alone. A negative amount moves its sign in front of the
    symbol. US is returned unchanged — the same object, not a copy.
    """
    if market is Market.US:
        return text
    symbol = spec_for(market).currency_symbol
    return _DOLLAR_AMOUNT_RE.sub(lambda m: f"{m.group(1)}{symbol}", text)


def ticker_market(ticker: str | None) -> Market:
    return market_for(ticker or "")


def na_line(label: str, what: str = "") -> str:
    """One explicit dark-input line, in the sheet's `Label: not available …` shape."""
    extra = f" ({what})" if what else ""
    return (
        f"{label}: {NOT_AVAILABLE_FOR_MARKET}{extra}. Do not supply it from memory."
    )


def my_header_bullet() -> str:
    return (
        "- Market: Bursa Malaysia. Money on this sheet is in ringgit (RM) and the "
        "benchmark is the FBM KLCI. Inputs that come from SEC EDGAR have no Bursa "
        "equivalent ingested yet and are listed below as "
        f"\"{NOT_AVAILABLE_FOR_MARKET}\" — a division of the market, not a data "
        "fault: never supply them from memory, and never cite an SEC form for this issuer."
    )


def my_forward_catalyst_header() -> str:
    return (
        "- Forward catalyst: the Bank Negara Malaysia (BNM) Overnight Policy Rate and "
        "the countdown to the next MPC decision below are REAL, from BNM's published "
        "calendar."
    )


#: The inputs behind the "Filed-statement detail" line, each with the sheet field whose
#: CR287 not-applicable mark removes it from that list (None: always listed). One string
#: joined with ", " is byte-identical to the line's text before CR287.
_FILED_DETAIL_ITEMS: tuple[tuple[str, str | None], ...] = (
    ("debt maturity ladder", "debt_maturity"),
    ("cost of debt", "cost_of_debt"),
    ("debt split", "debt_split"),
    ("segment and geographic revenue", None),
    ("SBC-adjusted free cash flow", "sbc"),
    ("ROIC", None),
    ("buyback average price and dividend growth", None),
)


def my_dark_lines(
    *, news: bool, fundamentals: bool, social: bool, profile: dict[str, Any] | None = None,
) -> list[str]:
    """The SEC-dark inputs a desk with these lanes would otherwise have been shown,
    each named as not available for this market rather than omitted.

    CR287 — `profile` only matters on a sheet whose family marks figures not applicable
    (banks): a figure the sheet says does not apply is not also listed here as unavailable.
    """
    from app.services import sector_metrics

    from app.services.edgar_8k import EXEC_CHANGE_LABEL
    from app.services.edgar_filings_feed import FEED_LABEL as FILINGS_LABEL
    from app.services.edgar_forensics import (
        CLUSTER_BUY_LABEL,
        EIGHT_K_FLAGS_LABEL,
        INSIDER_PLAN_TAG_LABEL,
        INSIDER_RATIO_LABEL,
    )

    out: list[str] = []
    if fundamentals:
        out.append(na_line(
            "Peer comparison", "the same-industry peer basket is built from SEC SIC codes",
        ))
        detail = ", ".join(
            name for name, key in _FILED_DETAIL_ITEMS
            if key is None or not sector_metrics.is_not_applicable(key, profile)
        )
        out.append(na_line(
            "Filed-statement detail", f"{detail} are read from SEC XBRL filings",
        ))
    if news or fundamentals:
        out.append(na_line(FILINGS_LABEL))
    if news:
        out.append(na_line(EXEC_CHANGE_LABEL))
        out.append(na_line(INSIDER_RATIO_LABEL))
        out.append(na_line(INSIDER_PLAN_TAG_LABEL))
        out.append(na_line(CLUSTER_BUY_LABEL))
        out.append(na_line(EIGHT_K_FLAGS_LABEL))
    if social:
        out.append(na_line("Put/call ratio", "Bursa single-stock options do not exist in this app"))
    return out


def my_fundamentals_footer() -> str:
    """The Fundamentals desk's turn names its SEC-dark inputs by construction (DEF533).

    The sheet and the base prompt both name them, but a model is free to leave
    them out of its own text; a prompt instruction is not a control, so the
    runner appends this one line to every Bursa Fundamentals turn.
    """
    return (
        "[AMI note: peer comparison, filed-statement detail and the filings index are "
        f"{NOT_AVAILABLE_FOR_MARKET}; this read does not include them.]"
    )


#: A Bursa options or positioning feed is not ingested, so Flow & Positioning has no
#: put/call read. A data gap, not a filings gap, so it does not use the filings phrase.
NOT_AVAILABLE_NO_BURSA_POSITIONING = (
    "not available for this market (no Bursa options or positioning feed is ingested)"
)


def my_news_rss_note(state: str | None) -> str | None:
    """The Malay Mail feed's line for a Bursa News turn (CR282 lane E2).

    `state` is `profile["my_news_rss"]`, stamped from `my_news_rss.status()`:
    off, unavailable this call, or live. A sheet that carries no state says nothing.
    """
    if state == "off":
        return (
            "[AMI note: the Malay Mail Bursa news feed is not enabled on this "
            "deployment; this read does not include it.]"
        )
    if state == "unavailable":
        return (
            "[AMI note: the Malay Mail Bursa news feed is unavailable this call; "
            "this read does not include it.]"
        )
    if state == "live":
        return (
            "[AMI note: headlines credited to Malay Mail are headline, link and date "
            "only; those marked market-wide are market context, not news about this "
            "company.]"
        )
    return None


def my_desk_footer(agent_id: AgentId, profile: dict[str, Any] | None) -> str | None:
    """The coded AMI note a Bursa desk's turn always ends with (DEF535).

    DEF533 appended one to Fundamentals only; the other desks described the Bursa
    gaps in their own words or left the benchmark unnamed. A prompt instruction is
    not a control (CR038), so each desk that has a Bursa-specific fact gets a line
    appended by code. A desk with nothing market-specific to disclose gets None.
    """
    if not is_my(profile):
        return None
    if agent_id is AgentId.FUNDAMENTALS_ANALYST:
        pn17 = (profile or {}).get("my_pn17_note")
        if pn17:
            return f"{my_fundamentals_footer()}\n\n{pn17}"
        return my_fundamentals_footer()
    if agent_id is AgentId.MARKET_ANALYST:
        state = (profile or {}).get("field_state") or {}
        if state.get("relative_strength_52w_pct") == "live":
            return (
                f"[AMI note: the 52-week relative strength on this sheet is measured against "
                f"the {MY_BENCHMARK_NAME}, Bursa Malaysia's index, not the S&P 500.]"
            )
        return (
            f"[AMI note: 52-week relative strength against the {MY_BENCHMARK_NAME} is not "
            "available this call; this read does not include it.]"
        )
    if agent_id is AgentId.NEWS_ANALYST:
        from app.services.edgar_8k import EXEC_CHANGE_LABEL
        from app.services.edgar_filings_feed import FEED_LABEL as FILINGS_LABEL
        from app.services.edgar_forensics import (
            CLUSTER_BUY_LABEL,
            EIGHT_K_FLAGS_LABEL,
            INSIDER_PLAN_TAG_LABEL,
            INSIDER_RATIO_LABEL,
        )

        labels = (
            FILINGS_LABEL, EXEC_CHANGE_LABEL, INSIDER_RATIO_LABEL,
            INSIDER_PLAN_TAG_LABEL, CLUSTER_BUY_LABEL, EIGHT_K_FLAGS_LABEL,
        )
        note = (
            f"[AMI note: {'; '.join(labels)} are {NOT_AVAILABLE_FOR_MARKET}; "
            "this read does not include them.]"
        )
        parts = [note]
        cpi = (profile or {}).get("macro_cpi_note")
        if cpi:
            parts.append(cpi)
        rss = my_news_rss_note((profile or {}).get("my_news_rss"))
        if rss:
            parts.append(rss)
        return "\n\n".join(parts)
    if agent_id is AgentId.SOCIAL_MEDIA_ANALYST:
        return (
            f"[AMI note: the put/call ratio is {NOT_AVAILABLE_NO_BURSA_POSITIONING}; "
            "this read does not include it.]"
        )
    return None
