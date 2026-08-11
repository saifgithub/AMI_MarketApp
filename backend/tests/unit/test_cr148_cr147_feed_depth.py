"""CR148 Tier A/B · CR147 Tier B.1 · DEF063 residue — the two paid feeds.

Batch 9 of the CR143 prompt + data-feed remediation programme. Neither feed is
short of a provider; both are short of the half of the payload we already pay
for, and short of an honest freshness label on the half we render.

**CR148 Tier A** — six dimensions arrived on every Adanos call since CR024 and
were dropped in `_to_sentiment`. The costly one is the per-community split:
12 of 18 turns named a subreddit and **9 of 18 attached a sentiment quantity,
tone or trend to a named one**, against the agent's own prohibition. CR143's
novel-number metric scored this agent 0.0% because every *number* was real — it
is the *attribution* that was invented, and the fix is to supply the split so
there is nothing left to invent. The neutral residue is the same shape: it is
the MAJORITY class (42–71% of the sample, median 52.5%) and 2 of 18 turns
noticed it existed.

**CR148 Tier B** — "as of this call" was false for most turns. Measured on Alpha
2026-08-08: 175 cached rows, mean age **20.2 days**, **162 of 175 (93%) older
than 7 days**. Saiful set the TTL to 7 days on 2026-08-11.

**DEF063 residue** — `ADANOS_API_KEY_SECONDARY` was wired into `config.py` and
`docker-compose.yml` by Batch 4 and **never sent by the fetch path**, so
`config-check` reported it `configured: true` while the effective quota stayed
at 250. Forwarded, and still dark: the DEF063 failure one layer further in. The
7-day TTL arithmetic was taken against 500, so this has to be true and not
merely wired.

**CR147 Tier B.1** — probed live across 8 tickers, yfinance returned 10 articles
for 7 of them; SNOA got 3 and its NEWEST was **354 days old**, rendered under a
header stating the catalyst was real "as of this call".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
import pytest

from app.core.config import settings
from app.db import get_session
from app.db.models import User
from app.schemas import AgentId
from app.services import news_context, room_runner as room_runner_mod
from app.services.auth_service import AuthService
from app.services.coach_engine import hydrate_coach_mandate
from app.services.credit_service import balance_for
from app.services.news_context import (
    LiveDataState,
    LiveHeadline,
    _NEWS_RECENCY_FLOOR_DAYS,
    _within_recency_floor,
    fetch_live_news,
    resolve_news_feed,
)
from app.services.room_prompts import _format_profile, build_room_messages
from app.services.social_context import (
    _MIN_MENTIONS_FOR_A_PERCENTAGE,
    _AdanosSource,
    SocialSentiment,
    SubredditStat,
    build_social_context_block,
    format_community_read,
    format_engagement,
    format_fetched_age,
    format_sample_size_caveat,
    format_sentiment_split,
    format_sentiment_tone,
    format_subreddit_split,
)

# The real captured Adanos response (AT:R57, 2026-07-13), trimmed — the same
# fixture `test_social_context.py` verifies the fetch against, so these tests
# assert on a shape the provider really sends rather than one we invented.
REAL_AAPL = {
    "ticker": "AAPL", "found": True, "buzz_score": 80.11, "mentions": 1993,
    "sentiment_score": 0.002, "positive_count": 435, "negative_count": 407,
    "neutral_count": 1151, "total_upvotes": 38369, "unique_posts": 410,
    "subreddit_count": 41, "trend": "falling", "bullish_pct": 22,
    "bearish_pct": 20, "period_days": 7,
    "top_subreddits": [
        {"subreddit": "wallstreetbets", "mentions": 904, "sentiment_score": -0.053,
         "buzz_score": 73.3, "count": 904},
        {"subreddit": "stocks", "mentions": 255, "sentiment_score": 0.014,
         "buzz_score": 64.5, "count": 255},
        {"subreddit": "mauerstrassenwetten", "mentions": 175, "sentiment_score": 0.0,
         "buzz_score": 34.9, "count": 175},
        {"subreddit": "stockmarket", "mentions": 163, "sentiment_score": 0.051,
         "buzz_score": 62.0, "count": 163},
    ],
    "top_mentions": [{"text_snippet": "Apple sues OpenAI", "upvotes": 16862}],
}


def _sentiment(**overrides) -> SocialSentiment:
    base = dict(
        ticker="AAPL", buzz_score=80.0, sentiment_score=0.002, mentions=1993,
        bullish_pct=22, bearish_pct=20, trend="falling", period_days=7,
        top_subreddits=("wallstreetbets",), sample_snippets=(),
        positive_count=435, negative_count=407, neutral_count=1151,
        total_upvotes=38369, unique_posts=410, subreddit_count=41,
        subreddit_stats=(SubredditStat("wallstreetbets", 904, -0.053, 73.3),),
        fetched_at=int(datetime.now(timezone.utc).timestamp()),
    )
    base.update(overrides)
    return SocialSentiment(**base)


# ── CR148 Tier A — the payload we were already paying for ───────────────────


def test_every_discarded_dimension_survives_the_parse():
    """Field-by-field against the real response. Each of these was on the wire
    for the entire life of CR024 and reached no prompt."""
    s = _AdanosSource._to_sentiment("AAPL", REAL_AAPL)
    assert (s.positive_count, s.negative_count, s.neutral_count) == (435, 407, 1151)
    assert (s.total_upvotes, s.unique_posts) == (38369, 410)
    assert s.subreddit_count == 41


def test_the_breadth_is_the_payloads_count_not_the_length_of_the_list_we_kept():
    """41 subreddits in the sample; we name 3. `len(top_subreddits)` would have
    reported 3 of 3 — a full-coverage claim, from a truncation."""
    s = _AdanosSource._to_sentiment("AAPL", REAL_AAPL)
    assert s.subreddit_count == 41
    assert len(s.top_subreddits) == 3
    assert "3 of 41 subreddits" in format_community_read(s)


def test_the_name_list_and_the_stat_list_cover_the_same_communities():
    """A per-community stat block naming different subreddits than the
    'most active in' line would be worse than neither — both slice by the same
    `_TOP_SUBREDDIT_LIMIT`."""
    s = _AdanosSource._to_sentiment("AAPL", REAL_AAPL)
    assert tuple(c.subreddit for c in s.subreddit_stats) == s.top_subreddits


def test_the_per_community_split_carries_the_numbers_the_agent_was_inventing():
    s = _AdanosSource._to_sentiment("AAPL", REAL_AAPL)
    lines = format_subreddit_split(s)
    assert lines[0] == "r/wallstreetbets: 904 mentions, sentiment -0.05, buzz 73/100"
    assert len(lines) == 3


def test_a_community_row_with_no_name_is_dropped():
    """A stat attributed to no community is the exact fabrication F3 measured."""
    stats = _AdanosSource._subreddit_stats([
        {"subreddit": "", "mentions": 99}, {"mentions": 5}, {"subreddit": "stocks", "mentions": 7},
    ])
    assert [c.subreddit for c in stats] == ["stocks"]


def test_the_neutral_residue_is_stated_and_it_is_the_majority():
    """AAPL: 22% bullish, 20% bearish — and 58% of 1,993 mentions said neither.
    A reader given only the first two numbers cannot see the third."""
    s = _AdanosSource._to_sentiment("AAPL", REAL_AAPL)
    line = format_sentiment_split(s)
    assert "435 positive / 407 negative / 1,151 neutral" in line
    assert "neutral is 58% of the classified sample" in line
    # The residue really is what the two percentages leave unexplained.
    assert 100 - s.bullish_pct - s.bearish_pct == pytest.approx(58, abs=1)


def test_a_payload_with_no_classified_counts_renders_nothing_rather_than_zeroes():
    """Absent ≠ zero (CR040). '0 positive / 0 negative / 0 neutral' asserts the
    sample was classified and found empty, which is a different — and false —
    claim from 'the provider did not send the split'."""
    assert format_sentiment_split(_sentiment(
        positive_count=0, negative_count=0, neutral_count=0)) == ""
    assert format_engagement(_sentiment(total_upvotes=0, unique_posts=0)) == ""
    assert format_subreddit_split(_sentiment(subreddit_stats=())) == ()


def test_engagement_separates_intensity_from_reach():
    """100 mentions across 12 posts with 40,000 upvotes is not the same event as
    100 mentions across 95 posts with 200 — `buzz_score` alone cannot say which."""
    assert format_engagement(_sentiment()) == "410 distinct posts, 38,369 total upvotes"


# ── CR148 Tier A — sample size ──────────────────────────────────────────────


def test_the_small_sample_threshold_is_derived_from_this_modules_own_classifier():
    """NOT a chosen number. `format_sentiment_tone` calls a tone on a 5-point
    bull/bear gap; the standard error of a proportion at p≈0.5 is 5.0pp exactly
    when n = 100. Below that, the gap the classifier uses is inside one standard
    error of the sample."""
    assert _MIN_MENTIONS_FOR_A_PERCENTAGE == 100
    se_at_threshold = (0.5 * 0.5 / _MIN_MENTIONS_FOR_A_PERCENTAGE) ** 0.5 * 100
    assert se_at_threshold == pytest.approx(5.0, abs=0.01)
    # And 5 is really the gap the classifier uses, not a coincidence.
    assert format_sentiment_tone(_sentiment(bullish_pct=30, bearish_pct=25)) == "mixed"
    assert format_sentiment_tone(_sentiment(bullish_pct=31, bearish_pct=25)) == "bullish"


def test_the_caveat_restates_the_percentages_as_the_post_counts_they_are():
    """GRAB's real n=10: 'bullish 30% / bearish 10%' is 3 posts against 1. The
    caveat states the ARITHMETIC rather than instructing the model to be careful
    — a prompt line telling a model to discount a number is the control P2 says
    does not hold (CR038 measured ~30%)."""
    note = format_sample_size_caveat(_sentiment(mentions=10, bullish_pct=30, bearish_pct=10))
    assert "SMALL SAMPLE — 10 mentions" in note
    assert "~3 post(s) against ~1" in note
    assert "unresolved rather than weak" in note


def test_the_caveat_is_silent_on_a_sample_that_can_carry_a_percentage():
    assert format_sample_size_caveat(_sentiment(mentions=1993)) == ""
    assert format_sample_size_caveat(_sentiment(mentions=100)) == ""
    assert format_sample_size_caveat(_sentiment(mentions=99)) != ""
    # Zero mentions is not a small sample, it is no sample — the mention line
    # already says so and a "~0 against ~0" caveat would add nothing.
    assert format_sample_size_caveat(_sentiment(mentions=0)) == ""


# ── CR148 Tier B — the freshness claim ──────────────────────────────────────


def test_the_ttl_is_seven_days():
    """Saiful's call, 2026-08-11: 30 → 7. At 30 the cache served rows averaging
    20.2 days old under a header saying 'as of this call'."""
    assert settings.social_cache_ttl_days == 7


def test_the_snapshot_renders_its_real_date_and_age():
    fetched = int((datetime.now(timezone.utc) - timedelta(days=21)).timestamp())
    line = format_fetched_age(_sentiment(fetched_at=fetched))
    assert "21d ago" in line
    assert datetime.fromtimestamp(fetched, tz=timezone.utc).strftime("%Y-%m-%d") in line


def test_an_unrecorded_fetch_time_says_so_rather_than_implying_now():
    """A cache row written before CR148 has no stored timestamp. Rendering
    'fetched today' for it would be the silent fallback the whole tier exists to
    remove (CR040)."""
    assert format_fetched_age(_sentiment(fetched_at=0)) == "fetch time not recorded"


def test_no_prompt_layer_still_claims_the_sentiment_is_as_of_this_call():
    sp, _ = build_room_messages(
        agent_id=AgentId.SOCIAL_MEDIA_ANALYST,
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        user_id=None, ticker="AAPL",
        profile={"field_state": {"social": "live"}}, transcript=[],
    )
    assert "aggregate data as of this call" not in sp
    assert "read it as of THAT date, not as of now" in sp


def test_the_row_timestamp_wins_over_the_payload_copy():
    """A payload written before CR148 has no `fetched_at` at all, and one
    written after carries the write-time copy — but the ROW is what staleness is
    judged against, so it is what the age must be rendered from."""
    row_time = int((datetime.now(timezone.utc) - timedelta(days=5)).timestamp())
    s = _AdanosSource._from_payload("AAPL", {"mentions": 12}, fetched_at=row_time)
    assert s.fetched_at == row_time
    stale_payload = {"mentions": 12, "fetched_at": row_time - 900_000}
    assert _AdanosSource._from_payload("AAPL", stale_payload, fetched_at=row_time).fetched_at == row_time


def test_a_cache_payload_written_before_this_change_still_loads():
    """Every CR148 field carries a default precisely so the 175 rows already in
    Postgres do not raise on read. They degrade to today's render — no
    per-community block — rather than taking the feed down."""
    old = {
        "buzz_score": 80.11, "sentiment_score": 0.002, "mentions": 1993,
        "bullish_pct": 22, "bearish_pct": 20, "trend": "falling",
        "period_days": 7, "top_subreddits": ["wallstreetbets"], "sample_snippets": [],
    }
    s = _AdanosSource._from_payload("AAPL", old, fetched_at=1_700_000_000)
    assert s.mentions == 1993
    assert s.subreddit_stats == ()
    assert format_subreddit_split(s) == ()
    assert s.fetched_at == 1_700_000_000


def test_the_new_fields_survive_a_json_cache_round_trip():
    """`subreddit_stats` is a tuple of NamedTuples, which JSON-encodes as a bare
    array — read back positionally, a future field reorder would silently
    transpose mentions and buzz. Stored as dicts, and this is what proves it."""
    import json

    s = _AdanosSource._to_sentiment("AAPL", REAL_AAPL)
    payload = dict(s._asdict())
    payload["top_subreddits"] = list(payload["top_subreddits"])
    payload["sample_snippets"] = list(payload["sample_snippets"])
    payload["subreddit_stats"] = [dict(c._asdict()) for c in payload["subreddit_stats"]]
    restored = _AdanosSource._from_payload("AAPL", json.loads(json.dumps(payload)))
    assert restored.subreddit_stats == s.subreddit_stats
    assert restored.subreddit_stats[0].mentions == 904
    assert restored.subreddit_stats[0].buzz_score == 73.3


# ── DEF063 residue — the secondary key is actually sent ─────────────────────


class _FakeResponse:
    def __init__(self, status_code=200, remaining=None, body=None):
        self.status_code = status_code
        self.headers = {} if remaining is None else {"x-ratelimit-remaining-monthly": remaining}
        self._body = body if body is not None else REAL_AAPL

    def json(self):
        return self._body


class _KeyRecordingClient:
    """Records the API key of every call and replays a scripted response list."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.keys_used: list[str] = []

    def get(self, url, headers=None):
        self.keys_used.append((headers or {}).get("X-API-Key"))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _source_with(responses, monkeypatch, *, primary="KEY1", secondary="KEY2"):
    monkeypatch.setattr(settings, "adanos_api_key", primary)
    monkeypatch.setattr(settings, "adanos_api_key_secondary", secondary)
    src = _AdanosSource()
    client = _KeyRecordingClient(responses)
    src._client = client
    return src, client


def test_a_healthy_primary_never_spends_the_secondary_budget(monkeypatch):
    src, client = _source_with([_FakeResponse(remaining="180")], monkeypatch)
    assert src._get_with_failover("AAPL").status_code == 200
    assert client.keys_used == ["KEY1"]


def test_a_429_on_the_primary_retries_on_the_secondary(monkeypatch):
    src, client = _source_with([_FakeResponse(429), _FakeResponse(remaining="249")], monkeypatch)
    resp = src._get_with_failover("AAPL")
    assert client.keys_used == ["KEY1", "KEY2"]
    assert resp.status_code == 200


def test_a_spent_monthly_budget_retries_even_on_a_200(monkeypatch):
    """Adanos answers the call that exhausts the budget; the NEXT one 429s. The
    header is the earlier signal and the one that avoids a wasted round trip."""
    src, client = _source_with([_FakeResponse(remaining="0"), _FakeResponse(remaining="250")],
                               monkeypatch)
    src._get_with_failover("AAPL")
    assert client.keys_used == ["KEY1", "KEY2"]


def test_a_network_error_is_not_retried_on_the_second_key():
    """A second key does not fix a network. Retrying would burn the reserve
    budget on an outage that has nothing to do with quota."""
    import pytest as _pytest

    monkeypatch = _pytest.MonkeyPatch()
    try:
        src, client = _source_with([httpx.ConnectError("boom"), _FakeResponse()], monkeypatch)
        assert src._get_with_failover("AAPL") is None
        assert client.keys_used == ["KEY1"]
    finally:
        monkeypatch.undo()


def test_no_secondary_configured_means_no_retry(monkeypatch):
    src, client = _source_with([_FakeResponse(429)], monkeypatch, secondary="")
    assert src._get_with_failover("AAPL").status_code == 429
    assert client.keys_used == ["KEY1"]


def test_an_unparseable_remaining_header_is_not_read_as_exhaustion(monkeypatch):
    """Guessing would spend the reserve key on the primary's bad header."""
    src, client = _source_with([_FakeResponse(remaining="unknown")], monkeypatch)
    src._get_with_failover("AAPL")
    assert client.keys_used == ["KEY1"]


# ── CR147 Tier B.1 — the news recency floor ─────────────────────────────────


def _headline(days_old: float, title="H") -> LiveHeadline:
    published = 0 if days_old is None else int(
        (datetime.now(timezone.utc) - timedelta(days=days_old)).timestamp()
    )
    return LiveHeadline(title=title, link="l", publisher="p", published_at=published,
                        sentiment=None, source="yfinance")


def test_the_floor_is_the_threshold_cr147_was_accepted_against():
    """Not a chosen number: CR147's acceptance criterion is '>7d must be 0, or
    the run must be UNAVAILABLE'."""
    assert _NEWS_RECENCY_FLOOR_DAYS == 7


def test_an_article_past_the_floor_is_not_recent():
    now = datetime.now(timezone.utc).timestamp()
    assert _within_recency_floor(_headline(1), now=now)
    assert _within_recency_floor(_headline(6.9), now=now)
    assert not _within_recency_floor(_headline(7.1), now=now)
    # SNOA's real newest article.
    assert not _within_recency_floor(_headline(354), now=now)


def test_an_article_of_unknown_date_cannot_be_certified_recent():
    """`published_at == 0` renders 'date unknown'. Passing it through is exactly
    what the floor exists to stop — a headline of unknown vintage under a
    live-as-of-this-call header (CR040)."""
    now = datetime.now(timezone.utc).timestamp()
    assert not _within_recency_floor(_headline(None), now=now)


class _FakeYfSource:
    items: list[LiveHeadline] = []

    def fetch(self, ticker, limit):
        return list(self.items)


@pytest.fixture
def _news_source(monkeypatch):
    monkeypatch.setattr(settings, "alpha_vantage_api_key", "")
    monkeypatch.setattr(news_context, "_YfinanceSource", _FakeYfSource)
    return _FakeYfSource


def test_stale_items_are_dropped_and_fresh_ones_kept(_news_source):
    _news_source.items = [_headline(1, "FRESH"), _headline(400, "ANCIENT")]
    kept = fetch_live_news("AAPL")
    assert [h.title for h in kept] == ["FRESH"]


def test_an_all_stale_feed_becomes_unavailable_not_a_year_old_catalyst(_news_source):
    """The SNOA case: 3 articles, newest 354 days old. More headlines was never
    the fix — refusing to call a year-old article recent is."""
    _news_source.items = [_headline(354), _headline(400), _headline(500)]
    assert fetch_live_news("AAPL") is None
    assert resolve_news_feed("AAPL", entitled=True).state is LiveDataState.UNAVAILABLE


def test_the_floor_covers_the_one_on_one_surface_too(_news_source):
    """Filtering in `resolve_news_feed` would have left `build_news_context_block`
    rendering year-old headlines under the same live header — so the floor sits
    at the choke point BOTH surfaces share."""
    monkey_settings = settings
    _news_source.items = [_headline(354)]
    original = monkey_settings.use_real_market_data
    monkey_settings.use_real_market_data = True
    try:
        assert news_context.build_news_context_block("AAPL") is None
    finally:
        monkey_settings.use_real_market_data = original


def test_the_header_no_longer_asserts_a_freshness_the_feed_never_checked():
    sp, _ = build_room_messages(
        agent_id=AgentId.NEWS_ANALYST,
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        user_id=None, ticker="AAPL",
        profile={"field_state": {"news": "live"}, "catalyst": "X"}, transcript=[],
    )
    assert "real news as of this call" not in sp
    assert "published within the last 7 days" in sp


def test_a_refused_feed_stops_charging_the_surcharge_for_it(_news_source, monkeypatch):
    """The honest place to stop charging. This falls out of the existing
    mechanism rather than needing a second debit site: an UNAVAILABLE feed is
    not counted in `n_available`, so `live_data_surcharge` shrinks by itself."""
    auth = AuthService()
    user, _, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        s.get(User, user.id).plan = "trader"
    balance_for(user.id)
    with get_session() as s:
        s.get(User, user.id).credit_balance = 500

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(
        room_runner_mod, "resolve_social_feed",
        lambda ticker, *, entitled: room_runner_mod.SocialFeed(LiveDataState.UNAVAILABLE, None),
    )

    _news_source.items = [_headline(1)]
    before = balance_for(user.id)[0]
    feed_fresh, _, charged_fresh = room_runner_mod.RoomRunner()._resolve_and_charge_feeds(
        user.id, "AAPL", withheld=frozenset(),
    )
    assert feed_fresh.state is LiveDataState.LIVE

    _news_source.items = [_headline(354)]
    with get_session() as s:
        s.get(User, user.id).credit_balance = before
    feed_stale, _, charged_stale = room_runner_mod.RoomRunner()._resolve_and_charge_feeds(
        user.id, "AAPL", withheld=frozenset(),
    )
    assert feed_stale.state is LiveDataState.UNAVAILABLE
    assert charged_stale < charged_fresh


# ── The call site, not just the builder (the DEF238 blind spot) ─────────────


def test_the_room_fact_sheet_actually_carries_the_new_social_depth():
    """Every test above proves the FORMATTERS. DEF238 shipped a PM-only feature
    that never worked once in production while its tests passed for the feature's
    entire life, because they all proved the builder and none proved the caller.
    This drives the real profile→prompt render."""
    s = _sentiment()
    profile = {
        "field_state": {"social": "live"},
        "sentiment_tone": "mixed",
        "sentiment_score": "+0.00 (live Reddit sentiment, Adanos)",
        "mention_trend": "1,993 Reddit mentions over 7d, trend: falling",
        "pattern": "buzz score 80/100, bullish 22% / bearish 20%",
        "influencer_take": format_community_read(s),
        "sentiment_split": format_sentiment_split(s),
        "social_engagement": format_engagement(s),
        "social_fetched_age": format_fetched_age(s),
        "subreddit_split": list(format_subreddit_split(s)),
    }
    sheet = _format_profile(profile, agent_id=AgentId.SOCIAL_MEDIA_ANALYST)
    assert "Snapshot: fetched" in sheet
    assert "1,151 neutral" in sheet
    assert "410 distinct posts" in sheet
    assert "r/wallstreetbets: 904 mentions" in sheet
    assert "Do not attribute a figure, tone or trend to one that is not listed" in sheet


def test_the_freshness_label_is_rendered_above_everything_it_qualifies():
    """Ordering is load-bearing: every number under the snapshot line is only as
    true as its date, and a date printed after them reads as a footnote."""
    s = _sentiment()
    sheet = _format_profile(
        {
            "field_state": {"social": "live"},
            "sentiment_tone": "mixed", "sentiment_score": "+0.00",
            "social_fetched_age": format_fetched_age(s),
            "sentiment_split": format_sentiment_split(s),
        },
        agent_id=AgentId.SOCIAL_MEDIA_ANALYST,
    )
    assert sheet.index("Snapshot: fetched") < sheet.index("1,151 neutral")


def test_the_one_on_one_block_carries_the_same_depth(monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(settings, "adanos_api_key", "KEY")
    import app.services.social_context as sc

    monkeypatch.setattr(sc, "fetch_live_sentiment", lambda t: _sentiment())
    block = build_social_context_block("AAPL")
    assert "1,151 neutral" in block
    assert "410 distinct posts" in block
    assert "r/wallstreetbets: 904 mentions" in block
    assert "fetched " in block


def test_nothing_social_renders_when_the_feed_is_not_live():
    """The synthetic path surfaces none of it — the disclosure header already
    declares social not-live, and a fabricated per-community split would be the
    worst possible version of the bug this batch is fixing."""
    sheet = _format_profile(
        {
            "field_state": {"social": "unavailable"},
            "sentiment_split": "4 positive / 4 negative / 4 neutral",
            "subreddit_split": ["r/leak: 1 mentions"],
            "social_fetched_age": "fetched 2026-01-01 (200d ago)",
        },
        agent_id=AgentId.SOCIAL_MEDIA_ANALYST,
    )
    assert "r/leak" not in sheet
    assert "positive" not in sheet
    assert "Snapshot" not in sheet
