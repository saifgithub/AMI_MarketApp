"""DEF291 — the catalyst slot is an attribution, not a sort order.

`profile["catalyst"]` becomes the *"Catalysts — recent"* line for all twelve
agents. It was `news_items[0]` — the most RECENT headline — and the feed has no
relevance ranking at all: `_merge_headlines` sorts by recency alone.

CR147 measured the consequence: 26 of 54 headlines (48%) are on-ticker, and the
top one is **off-ticker in 9 of 18 convenes (50%)**. AVGO's Room led with *"The
Toughest Questions AMD Faced On Its Latest Call"*.

**Why that is a defect and not merely noise.** An off-ticker article under a
"Catalysts — recent" label is not something the agent can route around: the
label asserts that this is the catalyst for the name under discussion. It is a
fabricated fact at the data layer, which is the class CR179 exists to close —
and it is the one field that reaches every agent identically.

**The direction of error matters, and the tests below pin it.** A false NEGATIVE
labels a real article "not confirmed on-ticker", which is honest and costs a
caveat. A false POSITIVE asserts an attribution that is not there — the exact
defect. So matching is deliberately conservative, and two classes of false
positive found on live data are pinned as regression tests.
"""

from __future__ import annotations

from app.services.news_context import (
    LiveHeadline,
    _issuer_tokens,
    headline_is_on_ticker,
    pick_catalyst,
)


def _h(title: str, summary: str = "", published_at: int = 1_800_000_000) -> LiveHeadline:
    return LiveHeadline(
        title=title, link="", publisher="P", published_at=published_at,
        sentiment=None, source="yfinance", summary=summary,
    )


# ── The two false positives found on live data ───────────────────────────


def test_an_industry_word_is_not_an_issuer():
    """Found live: `Kratos Defense & Security Solutions` matched *"Ondas Wins
    Israeli Defense Tender"* on the word **Defense** — an article about a
    different company in the same industry.

    A first pass took every non-stopword token of the name. A defence company's
    feed is full of "defense", so that pass asserted an attribution on the one
    word guaranteed to appear.
    """
    item = _h("Ondas Wins Israeli Defense Tender for Next-Gen Tactical Attack Drones")
    assert not headline_is_on_ticker(item, "KTOS", "Kratos Defense & Security Solutions")


def test_a_ticker_symbol_is_matched_as_a_word_not_a_substring():
    """Found live: `BAC` matched the word **back**, putting an oil-market
    article under Bank of America's catalyst line.

    A three-letter ticker is a substring of ordinary English often enough that
    substring matching does not add noise — it manufactures the false
    attribution this function exists to prevent.
    """
    item = _h("Oil's Rally Stalls", "Traders pulled back from crude as flows resumed.")
    assert not headline_is_on_ticker(item, "BAC", "Bank of America Corporation")


def test_a_generic_leading_word_needs_the_whole_name():
    """`Bank of America` leads with an ordinary noun. Matching on "Bank" alone
    would fire on any article mentioning a central bank."""
    assert _issuer_tokens("BAC", "Bank of America Corporation") == {"BAC", "BANK OF AMERICA"}
    generic = _h("Central bank holds rates steady", "The bank signalled patience.")
    assert not headline_is_on_ticker(generic, "BAC", "Bank of America Corporation")
    real = _h("Bank of America lifts its target", "")
    assert headline_is_on_ticker(real, "BAC", "Bank of America Corporation")


def test_a_distinctive_leading_word_is_enough():
    """`Kratos`, `NVIDIA`, `Micron` identify the issuer on their own — which is
    how prose actually refers to them, and the ticker often never appears."""
    for ticker, name, title in (
        ("KTOS", "Kratos Defense & Security Solutions",
         "5 Revealing Analyst Questions From Kratos's Q2 Earnings Call"),
        ("NVDA", "NVIDIA Corporation", "SK Group Isn't Worried About Nvidia Dependence"),
        ("MU", "Micron Technology, Inc.", "Micron Faces a New Burry Bet"),
    ):
        assert headline_is_on_ticker(_h(title), ticker, name), title


def test_the_summary_is_searched_as_well_as_the_title():
    """The summary is often where the issuer is named — the same reason CR147
    B.2 carries it onto the sheet at all."""
    item = _h("Chip demand keeps climbing", "Analysts singled out Nvidia's data-centre mix.")
    assert headline_is_on_ticker(item, "NVDA", "NVIDIA Corporation")


# ── The selection itself ─────────────────────────────────────────────────


def test_the_most_recent_on_ticker_headline_wins_the_slot():
    items = [
        _h("Broad market rallies on rate hopes", published_at=1_800_000_300),
        _h("Nvidia lifts guidance", published_at=1_800_000_200),
        _h("Nvidia ships new part", published_at=1_800_000_100),
    ]
    pick, on_ticker = pick_catalyst(items, "NVDA", "NVIDIA Corporation")
    assert on_ticker
    assert pick.title == "Nvidia lifts guidance", "recency must break ties among on-ticker items"


def test_nothing_on_ticker_falls_back_and_says_so():
    """Suppression would be worse than a caveat: a real, recent, sector-relevant
    article is still worth reading, and dropping the feed would trade a
    labelling bug for a data one."""
    items = [_h("Oil rallies on supply fears"), _h("Rates steady into year end")]
    pick, on_ticker = pick_catalyst(items, "NVDA", "NVIDIA Corporation")
    assert pick is items[0]
    assert on_ticker is False


def test_the_off_ticker_caveat_reaches_the_sheet(base_mandate):
    """The label is the fix. Without it the fallback is the original defect."""
    from app.schemas import AgentId
    from app.services.room_prompts import build_room_messages

    profile = {
        "ticker": "NVDA",
        "catalyst": '"Oil rallies on supply fears" (P, 1h ago)',
        "catalyst_on_ticker": False,
        "forward_catalyst": "FOMC in 12 days",
        "field_state": {"news": "live", "run_date": "live"},
    }
    prompt, _ = build_room_messages(
        agent_id=AgentId.NEWS_ANALYST, mandate=base_mandate, user_id=None,
        ticker="NVDA", profile=profile, transcript=[],
    )
    assert "no headline in this feed names this company" in prompt
    assert "NOT a catalyst for this ticker" in prompt


def test_an_on_ticker_catalyst_carries_no_caveat(base_mandate):
    from app.schemas import AgentId
    from app.services.room_prompts import build_room_messages

    profile = {
        "ticker": "NVDA",
        "catalyst": '"Nvidia lifts guidance" (P, 1h ago)',
        "catalyst_on_ticker": True,
        "forward_catalyst": "FOMC in 12 days",
        "field_state": {"news": "live", "run_date": "live"},
    }
    prompt, _ = build_room_messages(
        agent_id=AgentId.NEWS_ANALYST, mandate=base_mandate, user_id=None,
        ticker="NVDA", profile=profile, transcript=[],
    )
    assert "no headline in this feed names this company" not in prompt


def test_an_absent_feed_never_triggers_the_caveat(base_mandate):
    """`False` must come only from a feed that was searched and produced no
    match — never from a missing key, which would put a "we looked and found
    nothing" claim on a sheet where nothing was looked at."""
    from app.schemas import AgentId
    from app.services.room_prompts import build_room_messages

    prompt, _ = build_room_messages(
        agent_id=AgentId.NEWS_ANALYST, mandate=base_mandate, user_id=None,
        ticker="NVDA", profile={"ticker": "NVDA", "field_state": {"run_date": "live"}},
        transcript=[],
    )
    assert "no headline in this feed names this company" not in prompt
