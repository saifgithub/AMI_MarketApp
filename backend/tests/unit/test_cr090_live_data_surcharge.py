"""CR090 (coder.api) — live-data feed surcharge + the 3-state liveness marker.

Two things get pinned here, both acceptance items of CR090:

  1. **The surcharge is additive.** `live_data_surcharge` is the single source
     of the +2/analyst figure, and it stacks on the flat Room/1-on-1 price
     WITHOUT disturbing it — so `ALLOWANCE` / `ROOM_COST_*` / `_ROOM_COST_BY_PLAN`
     are asserted byte-for-byte unchanged.

  2. **The marker is 3-state and structural.** `LiveDataState` distinguishes a
     genuinely-empty feed (`UNAVAILABLE`) from a feed that exists but is gated
     (`WITHHELD_PAID`) — the DEF059 inversion guard: an entitled-but-broke turn
     can never be served the honest "no data" fallback as if that were just how
     the agent behaves, and the paid payload is never leaked to a non-entitled
     turn. The classifier `live_data_state` is pure/total, so this holds by
     construction, not by a prompt string (CR038).

Sources are exercised by monkeypatching the module-level `fetch_live_news` /
`fetch_live_sentiment` (same pattern the existing news/social block tests use)
— no live network calls.
"""

from __future__ import annotations

import time

from app.schemas.mandate import Plan
from app.services import news_context, social_context
from app.services.credit_service import (
    ALLOWANCE,
    LIVE_DATA_SURCHARGE,
    ROOM_COST_BASIC,
    ROOM_COST_PREMIUM,
    _ROOM_COST_BY_PLAN,
    live_data_surcharge,
)
from app.services.news_context import (
    LiveDataState,
    LiveHeadline,
    NewsFeed,
    live_data_state,
    resolve_news_feed,
)
from app.services.social_context import (
    SocialFeed,
    SocialSentiment,
    resolve_social_feed,
)


# ── The surcharge figure ──────────────────────────────────────────────────


def test_live_data_surcharge_scales_with_the_number_of_live_analysts():
    assert live_data_surcharge(0) == 0
    assert live_data_surcharge(1) == 2
    assert live_data_surcharge(2) == 4  # both News + Social live


def test_live_data_surcharge_is_driven_by_the_single_constant():
    assert LIVE_DATA_SURCHARGE == 2
    assert live_data_surcharge(1) == LIVE_DATA_SURCHARGE
    assert live_data_surcharge(3) == 3 * LIVE_DATA_SURCHARGE


def test_live_data_surcharge_never_goes_negative():
    """Defensive — a bad caller passing a negative count must not credit the
    user, it just yields zero surcharge."""
    assert live_data_surcharge(-1) == 0


# ── Existing pricing is byte-unchanged (the surcharge is purely additive) ──


def test_allowance_is_unchanged():
    assert ALLOWANCE == {
        Plan.FLOOR_PASS: 13,
        Plan.TRIAL_TRADER: 150,
        Plan.TRADER: 150,
        Plan.FLOOR_MANAGER: 500,
    }


def test_room_costs_are_unchanged():
    assert ROOM_COST_BASIC == 8
    assert ROOM_COST_PREMIUM == 25
    assert _ROOM_COST_BY_PLAN == {
        Plan.FLOOR_PASS: 8,
        Plan.TRIAL_TRADER: 8,
        Plan.TRADER: 8,
        Plan.FLOOR_MANAGER: 25,
    }


def test_surcharge_illustration_matches_the_spec():
    """credits.md illustration: a Basic Room with both live analysts firing is
    8 + 2 + 2 = 12 — the surcharge stacks on the base, it does not replace it."""
    assert ROOM_COST_BASIC + live_data_surcharge(2) == 12


# ── The pure classifier (the DEF059 inversion is impossible by construction) ─


def test_live_data_state_available_and_entitled_is_live():
    assert live_data_state(available=True, entitled=True) is LiveDataState.LIVE


def test_live_data_state_available_but_not_entitled_is_withheld_not_unavailable():
    state = live_data_state(available=True, entitled=False)
    assert state is LiveDataState.WITHHELD_PAID
    # The whole point of the third state: a gated feed is NEVER reported as
    # "no data" — that inversion is what DEF059 warned about.
    assert state is not LiveDataState.UNAVAILABLE


def test_live_data_state_no_data_is_unavailable_regardless_of_entitlement():
    assert live_data_state(available=False, entitled=True) is LiveDataState.UNAVAILABLE
    assert live_data_state(available=False, entitled=False) is LiveDataState.UNAVAILABLE


def test_live_data_state_is_one_shared_type_across_both_modules():
    """news_context owns the enum; social_context re-imports it, so the ROOM
    lane branches on a single type, not two look-alikes."""
    assert social_context.LiveDataState is news_context.LiveDataState


# ── News feed resolution ──────────────────────────────────────────────────


def _headline(title: str = "Headline") -> LiveHeadline:
    return LiveHeadline(
        title=title, link="https://x", publisher="Reuters",
        published_at=int(time.time()), sentiment=None, source="yfinance",
    )


def test_resolve_news_feed_live_when_available_and_entitled(monkeypatch):
    items = [_headline("Real one"), _headline("Real two")]
    monkeypatch.setattr(news_context, "fetch_live_news", lambda t, limit=3: items)

    feed = resolve_news_feed("AAPL", entitled=True)
    assert isinstance(feed, NewsFeed)
    assert feed.state is LiveDataState.LIVE
    assert [h.title for h in feed.headlines] == ["Real one", "Real two"]


def test_resolve_news_feed_withheld_when_available_but_not_entitled(monkeypatch):
    """The gated path — data exists, user isn't entitled. Loud WITHHELD_PAID,
    empty payload, and provably NOT the silent 'no data' fallback."""
    monkeypatch.setattr(news_context, "fetch_live_news", lambda t, limit=3: [_headline()])

    feed = resolve_news_feed("AAPL", entitled=False)
    assert feed.state is LiveDataState.WITHHELD_PAID
    assert feed.state is not LiveDataState.UNAVAILABLE   # DEF059 inversion guard
    assert feed.headlines == ()                          # paid payload not leaked


def test_resolve_news_feed_unavailable_when_no_data(monkeypatch):
    monkeypatch.setattr(news_context, "fetch_live_news", lambda t, limit=3: None)

    # Even an entitled user gets UNAVAILABLE when there is genuinely no feed.
    feed = resolve_news_feed("XYZQ", entitled=True)
    assert feed.state is LiveDataState.UNAVAILABLE
    assert feed.headlines == ()


def test_resolve_news_feed_does_not_break_the_binary_caller(monkeypatch):
    """Back-compat: the existing binary path (`fetch_live_news`) is untouched —
    the new resolver is additive, callers of the old function still get a list
    or None exactly as before."""
    items = [_headline("Still works")]
    monkeypatch.setattr(news_context, "fetch_live_news", lambda t, limit=3: items)
    assert news_context.fetch_live_news("AAPL") == items


# ── Social feed resolution ────────────────────────────────────────────────


def _sentiment(ticker: str = "AAPL") -> SocialSentiment:
    return SocialSentiment(
        ticker=ticker, buzz_score=80.0, sentiment_score=0.1, mentions=1000,
        bullish_pct=30, bearish_pct=20, trend="rising", period_days=7,
        top_subreddits=("stocks",), sample_snippets=(),
    )


def test_resolve_social_feed_live_when_available_and_entitled(monkeypatch):
    s = _sentiment()
    monkeypatch.setattr(social_context, "fetch_live_sentiment", lambda t: s)

    feed = resolve_social_feed("AAPL", entitled=True)
    assert isinstance(feed, SocialFeed)
    assert feed.state is LiveDataState.LIVE
    assert feed.sentiment is s


def test_resolve_social_feed_withheld_when_available_but_not_entitled(monkeypatch):
    monkeypatch.setattr(social_context, "fetch_live_sentiment", lambda t: _sentiment())

    feed = resolve_social_feed("AAPL", entitled=False)
    assert feed.state is LiveDataState.WITHHELD_PAID
    assert feed.state is not LiveDataState.UNAVAILABLE   # DEF059 inversion guard
    assert feed.sentiment is None                        # paid payload not leaked


def test_resolve_social_feed_unavailable_when_no_data(monkeypatch):
    monkeypatch.setattr(social_context, "fetch_live_sentiment", lambda t: None)

    feed = resolve_social_feed("XYZQ", entitled=True)
    assert feed.state is LiveDataState.UNAVAILABLE
    assert feed.sentiment is None


def test_resolve_social_feed_does_not_break_the_binary_caller(monkeypatch):
    """Back-compat: `fetch_live_sentiment` is untouched — old callers still get
    a SocialSentiment or None."""
    s = _sentiment()
    monkeypatch.setattr(social_context, "fetch_live_sentiment", lambda t: s)
    assert social_context.fetch_live_sentiment("AAPL") is s
