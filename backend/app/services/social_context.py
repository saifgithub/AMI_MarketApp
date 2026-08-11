"""Live Reddit stock-sentiment for the agent pipeline (Room + 1-on-1) — CR024.

Adanos (`https://api.adanos.org`) is a Reddit-only stock-sentiment aggregator
— presence of `settings.adanos_api_key` turns this on, same convention as
`alpha_vantage_api_key` in news_context.py. It does NOT cover Twitter/X,
StockTwits, Google Trends, or Discord — those remain unconnected, same as
before this CR. Free tier is 250 calls/month (confirmed via response headers
during AT:R57 live verification, and CR148/DEF063 wired a SECOND provisioned
key, so the working budget is 500), so this module caches by ticker rather than
by user/pageview — same reasoning as news_context.py's Alpha Vantage cache.

**The TTL is `settings.social_cache_ttl_days` and nothing else.** This docstring
used to say "24h", `config.py` said 30 days and the prompt said "as of this
call" — three numbers, none of which agreed, and the one that governed was the
config. Measured on Alpha 2026-08-08: 175 cached rows, mean age **20.2 days**,
**162 of 175 (93%) older than 7 days**, rendered under "as of this call".
Saiful set the TTL to **7 days** on 2026-08-11 (CR148 Tier B): at 500 calls/month
and ~4.3 calls per distinct ticker/month that caps at ~116 distinct tickers per
month, against a cache that has accumulated 175 rows over its whole life — so
the ceiling is not close. If you change the TTL, change it in `config.py` and
leave this paragraph pointing at the setting rather than restating a number.

Real post text (`top_mentions[].text_snippet`) is Reddit community content,
not ours to display verbatim — it's exposed ONLY via `format_social_context()`
for the 1-on-1 LLM-prompt block (which the agent synthesizes, never echoes
raw), and deliberately NEVER stored in the Room profile dict, since that
dict also feeds the scripted (non-LLM) fallback template rendered directly
to real users. Aggregate stats (buzz score, sentiment, subreddit names,
mention counts) are safe for both surfaces.

Never raises, returns None on any failure.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import NamedTuple

import httpx

from app.core.config import settings
from app.core.logging import logger
# `_relative_age` is the same concept on both feeds — how old is the artifact we
# just handed the agent — and news_context already owns the renderer this module
# depends on for its liveness markers. A second copy would be one more number
# that can drift, which is the exact class of bug CR148 Tier B is fixing.
from app.services.news_context import LiveDataState, _relative_age, live_data_state

_ADANOS_BASE_URL = "https://api.adanos.org/reddit/stocks/v1/stock"
# L1 in-process TTL. The durable cache is Postgres (CR041) — this only spares
# a DB round-trip inside one process's lifetime, so it stays short.
_L1_TTL = 300.0

# How many communities we keep. Was an inline `[:3]` in two places; naming it
# keeps the name list and the CR148 per-community stat list the same three
# communities, which is the whole point — a stat block covering different
# subreddits than the names would be worse than neither.
_TOP_SUBREDDIT_LIMIT = 3

# CR148 Tier A — below this many mentions a percentage is not a percentage.
#
# DERIVED, not chosen, from this module's own classifier: `format_sentiment_tone`
# calls a tone on a **5-point** bull/bear gap. The standard error of a
# proportion is sqrt(p(1-p)/n), which at p≈0.5 is 5.0pp exactly when n = 100.
# So at n < 100 the gap the classifier uses to decide "bullish" is inside one
# standard error of the sample — the label is noise dressed as a reading.
#
# Measured: mention counts across the epoch ran **10 to 3,990**, 5 of 18 turns
# below 52, and `format_pattern` rendered n=10 in the byte-identical shape it
# uses at n=3,990. At GRAB's n=10 "bullish 30% / bearish 10%" is 3 posts against
# 1. Four of the six small-n turns did not flag it; SNOA (n=12) produced
# "signaling organic momentum" and "extreme euphoria often precedes volatility".
_MIN_MENTIONS_FOR_A_PERCENTAGE = 100


class SubredditStat(NamedTuple):
    """One community's slice of the same Adanos response (CR148 Tier A).

    The payload has carried these since day one and `_to_sentiment` kept only
    `.subreddit`, so the fact sheet named communities while stating nothing
    about any of them. Measured consequence: 12 of 18 turns named a subreddit
    and **9 of 18 attached a sentiment quantity, tone or trend to a named one**
    — against the agent's own prohibition, *"You DO NOT … Speak on behalf of
    any specific community"*. The numbers in those claims were real, which is
    why CR143's novel-number metric scored this agent 0.0%: it is the
    *attribution* that was invented. Supplying the split leaves it nothing to
    invent.
    """

    subreddit: str
    mentions: int
    sentiment_score: float
    buzz_score: float


class SocialSentiment(NamedTuple):
    """Aggregate Reddit sentiment for one ticker over `period_days`."""

    ticker: str
    buzz_score: float
    sentiment_score: float
    mentions: int
    bullish_pct: int
    bearish_pct: int
    trend: str
    period_days: int
    top_subreddits: tuple[str, ...]
    sample_snippets: tuple[str, ...]
    # ── CR148 Tier A — fetched on the same call since CR024, discarded here ──
    # The neutral residue is the MAJORITY class and was never stated: across the
    # 18-turn epoch `100 − bullish_pct − bearish_pct` ran 42%–71%, median 52.5%,
    # and 2 of 18 turns noticed. A reader given "bullish 22% / bearish 20%" and
    # nothing else has no way to see that 58% of the sample said neither.
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    # Engagement/intensity — the dimension `buzz_score` alone cannot carry.
    total_upvotes: int = 0
    unique_posts: int = 0
    # Breadth: AAPL's real response covers 41 subreddits and names 3.
    subreddit_count: int = 0
    subreddit_stats: tuple[SubredditStat, ...] = ()
    # ── CR148 Tier B — when this snapshot was actually taken ────────────────
    # Unix epoch seconds, same representation as `LiveHeadline.published_at`,
    # for the same reason: it survives a JSON cache round-trip and renders as a
    # relative age. 0 means unknown (a payload written before this field).
    fetched_at: int = 0


# Every CR148 field carries a default so a cache row written before this change
# still loads. Those rows have no `subreddit_stats` and no `fetched_at`; they
# degrade to today's render (no per-community block) rather than raising — and
# `_cache_read` supplies the row's OWN timestamp for `fetched_at`, so their age
# is correct even though the payload never stored it.


def _cache_read(sym: str) -> tuple[bool, SocialSentiment | None] | None:
    """(hit, sentiment) from the durable cache, or None when absent/stale.
    A cached `found=False` is a hit returning None — that's the point (it stops
    an uncovered ticker costing a live call on every convene)."""
    from sqlalchemy import select

    from app.db import get_session
    from app.db.models import SocialSentimentCacheRow

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.social_cache_ttl_days)
    try:
        with get_session() as s:
            row = s.execute(
                select(SocialSentimentCacheRow).where(
                    SocialSentimentCacheRow.ticker == sym
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            fetched = row.fetched_at
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=timezone.utc)
            if fetched < cutoff:
                return None
            if not row.found:
                return (True, None)
            # The ROW's timestamp is the authoritative fetch time — the payload
            # copy may predate the field entirely (CR148 Tier B).
            return (True, _AdanosSource._from_payload(
                sym, row.payload or {}, fetched_at=int(fetched.timestamp())
            ))
    except Exception as exc:  # noqa: BLE001 — cache must never break a convene
        logger.warn("social_cache_read_failed", ticker=sym, error=str(exc)[:200])
        return None


def _cache_write(sym: str, sentiment: SocialSentiment | None) -> None:
    from app.db import get_session
    from app.db.models import SocialSentimentCacheRow

    try:
        with get_session() as s:
            row = s.get(SocialSentimentCacheRow, sym)
            payload = dict(sentiment._asdict()) if sentiment is not None else None
            if payload is not None:
                payload["top_subreddits"] = list(payload.get("top_subreddits") or ())
                payload["sample_snippets"] = list(payload.get("sample_snippets") or ())
                # `subreddit_stats` is a tuple of NamedTuples. A NamedTuple
                # JSON-encodes as a bare array, which `_from_payload` would then
                # have to read positionally — so any future field reorder would
                # silently transpose mentions and buzz. Store dicts.
                payload["subreddit_stats"] = [
                    dict(s._asdict()) for s in (payload.get("subreddit_stats") or ())
                ]
            if row is None:
                s.add(SocialSentimentCacheRow(
                    ticker=sym, found=sentiment is not None, payload=payload,
                    fetched_at=datetime.now(timezone.utc),
                ))
            else:
                row.found = sentiment is not None
                row.payload = payload
                row.fetched_at = datetime.now(timezone.utc)
    except Exception as exc:  # noqa: BLE001
        logger.warn("social_cache_write_failed", ticker=sym, error=str(exc)[:200])


def _quota_spent(resp: httpx.Response) -> bool:
    """True when this key's monthly budget is gone — a 429, or a response whose
    remaining-monthly header has reached zero. Anything else (including a
    missing or unparseable header) is NOT quota exhaustion: guessing would burn
    the second key's budget on the first key's unrelated outage."""
    if resp.status_code == 429:
        return True
    remaining = resp.headers.get("x-ratelimit-remaining-monthly")
    if remaining is None:
        return False
    try:
        return int(remaining) <= 0
    except ValueError:
        return False


class _AdanosSource:
    def __init__(self, timeout_seconds: float = 4.0) -> None:
        self._client = httpx.Client(timeout=timeout_seconds)
        self._cache: dict[str, tuple[SocialSentiment | None, float]] = {}
        self._lock = RLock()

    def _get_with_failover(self, sym: str) -> httpx.Response | None:
        """The live call, retried on the SECONDARY key when the primary's
        monthly budget is spent.

        DEF063 wired `ADANOS_API_KEY_SECONDARY` into `config.py` and
        `docker-compose.yml` — and nothing ever sent it. A provisioned second
        250-call budget was invisible to the fetch path, so `config-check`
        reported the key `configured: true` while the effective quota stayed at
        250. That is the DEF063 failure one layer further in: forwarded, and
        still dark. It is also the arithmetic the 7-day TTL decision was taken
        against (2026-08-11), so it has to be true and not merely wired.

        Failover fires on quota exhaustion ONLY — a 429, or a 200 whose
        remaining-monthly header has hit zero. A network error is not retried on
        the second key, because a second key does not fix a network.
        """
        keys = [k for k in (settings.adanos_api_key, settings.adanos_api_key_secondary) if k]
        resp: httpx.Response | None = None
        for index, key in enumerate(keys):
            try:
                resp = self._client.get(
                    f"{_ADANOS_BASE_URL}/{sym}", headers={"X-API-Key": key},
                )
            except httpx.HTTPError as exc:
                logger.warn(
                    "social_context_adanos_network_error",
                    ticker=sym, key_index=index, error=str(exc)[:200],
                )
                return None
            self._log_budget(sym, resp, key_index=index)
            if not _quota_spent(resp) or index == len(keys) - 1:
                return resp
            logger.warn(
                "social_context_adanos_key_failover",
                ticker=sym,
                from_key_index=index,
                status=resp.status_code,
                note="primary monthly budget spent — retrying on the secondary key",
            )
        return resp

    def _log_budget(self, sym: str, resp: httpx.Response, *, key_index: int) -> None:
        # Budget telemetry (CR041): each key's tier is 250/month and the only
        # signal is these headers. Log every live call so exhaustion is visible
        # before the agent silently reverts to inventing sentiment (CR037).
        remaining = resp.headers.get("x-ratelimit-remaining-monthly")
        logger.info(
            "social_context_adanos_call",
            ticker=sym,
            key_index=key_index,
            status=resp.status_code,
            monthly_remaining=remaining,
            monthly_used=resp.headers.get("x-ratelimit-used-monthly"),
            burst_remaining=resp.headers.get("x-ratelimit-remaining-burst"),
        )
        try:
            if remaining is not None and int(remaining) <= 10:
                logger.warn(
                    "social_context_adanos_budget_nearly_exhausted",
                    key_index=key_index,
                    monthly_remaining=remaining,
                    resets=resp.headers.get("x-ratelimit-reset-monthly"),
                    note="Social Analyst reverts to synthetic sentiment at zero (CR037)",
                )
        except ValueError:
            pass

    def fetch(self, ticker: str) -> SocialSentiment | None:
        sym = ticker.upper().strip()
        now = time.time()
        with self._lock:
            hit = self._cache.get(sym)
            if hit is not None and hit[1] > now:
                return hit[0]

        cached = _cache_read(sym)
        if cached is not None:
            with self._lock:
                self._cache[sym] = (cached[1], now + _L1_TTL)
            return cached[1]

        resp = self._get_with_failover(sym)
        if resp is None:
            return None
        if resp.status_code != 200:
            logger.warn("social_context_adanos_bad_status", ticker=sym, status=resp.status_code)
            return None
        try:
            body = resp.json()
        except ValueError as exc:
            logger.warn("social_context_adanos_parse_error", ticker=sym, error=str(exc)[:200])
            return None
        if not body.get("found"):
            # Cache the negative: Adanos has no coverage for this ticker, and
            # re-asking every convene burned one call each time (CR041).
            _cache_write(sym, None)
            with self._lock:
                self._cache[sym] = (None, now + _L1_TTL)
            return None

        sentiment = self._to_sentiment(sym, body)
        _cache_write(sym, sentiment)
        with self._lock:
            self._cache[sym] = (sentiment, now + _L1_TTL)
        return sentiment

    @staticmethod
    def _subreddit_stats(rows: object) -> tuple[SubredditStat, ...]:
        """The per-community slice, from either shape it can arrive in — the
        live Adanos payload (`top_subreddits[]`) or a cached copy of one. Rows
        without a name are skipped: a stat attributed to no community is the
        exact fabrication CR148 F3 measured."""
        out: list[SubredditStat] = []
        for row in list(rows or ())[:_TOP_SUBREDDIT_LIMIT]:
            if not isinstance(row, dict):
                continue
            name = str(row.get("subreddit") or "").strip()
            if not name:
                continue
            out.append(SubredditStat(
                subreddit=name,
                mentions=int(row.get("mentions") or row.get("count") or 0),
                sentiment_score=float(row.get("sentiment_score") or 0.0),
                buzz_score=float(row.get("buzz_score") or 0.0),
            ))
        return tuple(out)

    @staticmethod
    def _from_payload(ticker: str, payload: dict, *, fetched_at: int = 0) -> SocialSentiment:
        return SocialSentiment(
            ticker=ticker,
            buzz_score=float(payload.get("buzz_score") or 0.0),
            sentiment_score=float(payload.get("sentiment_score") or 0.0),
            mentions=int(payload.get("mentions") or 0),
            bullish_pct=int(payload.get("bullish_pct") or 0),
            bearish_pct=int(payload.get("bearish_pct") or 0),
            trend=str(payload.get("trend") or "flat"),
            period_days=int(payload.get("period_days") or 7),
            top_subreddits=tuple(payload.get("top_subreddits") or ()),
            sample_snippets=tuple(payload.get("sample_snippets") or ()),
            positive_count=int(payload.get("positive_count") or 0),
            negative_count=int(payload.get("negative_count") or 0),
            neutral_count=int(payload.get("neutral_count") or 0),
            total_upvotes=int(payload.get("total_upvotes") or 0),
            unique_posts=int(payload.get("unique_posts") or 0),
            subreddit_count=int(payload.get("subreddit_count") or 0),
            subreddit_stats=_AdanosSource._subreddit_stats(payload.get("subreddit_stats")),
            fetched_at=fetched_at or int(payload.get("fetched_at") or 0),
        )

    @staticmethod
    def _to_sentiment(ticker: str, body: dict) -> SocialSentiment:
        raw_subs = body.get("top_subreddits") or []
        top_subreddits = tuple(
            s["subreddit"] for s in raw_subs[:_TOP_SUBREDDIT_LIMIT] if s.get("subreddit")
        )
        sample_snippets = tuple(
            m["text_snippet"] for m in (body.get("top_mentions") or [])[:3] if m.get("text_snippet")
        )
        return SocialSentiment(
            ticker=ticker,
            buzz_score=float(body.get("buzz_score") or 0.0),
            sentiment_score=float(body.get("sentiment_score") or 0.0),
            mentions=int(body.get("mentions") or 0),
            bullish_pct=int(body.get("bullish_pct") or 0),
            bearish_pct=int(body.get("bearish_pct") or 0),
            trend=str(body.get("trend") or "flat"),
            period_days=int(body.get("period_days") or 7),
            top_subreddits=top_subreddits,
            sample_snippets=sample_snippets,
            positive_count=int(body.get("positive_count") or 0),
            negative_count=int(body.get("negative_count") or 0),
            neutral_count=int(body.get("neutral_count") or 0),
            total_upvotes=int(body.get("total_upvotes") or 0),
            unique_posts=int(body.get("unique_posts") or 0),
            # NOT len(top_subreddits) — the payload's own count is the sample's
            # breadth (41 for AAPL); the list is truncated to the top 3.
            subreddit_count=int(body.get("subreddit_count") or 0),
            subreddit_stats=_AdanosSource._subreddit_stats(raw_subs),
            fetched_at=int(time.time()),
        )


_source: _AdanosSource | None = None


def get_adanos_source() -> _AdanosSource:
    """Singleton (holds an httpx.Client + the short L1 cache in front of the
    durable Postgres one). Tests can call `set_adanos_source()` to inject a
    fake."""
    global _source
    if _source is None:
        _source = _AdanosSource()
    return _source


def set_adanos_source(source: _AdanosSource | None) -> None:
    global _source
    _source = source


def fetch_live_sentiment(ticker: str) -> SocialSentiment | None:
    """Real Reddit sentiment for `ticker` via Adanos. Never raises. Returns
    None if `adanos_api_key` is unset — callers gate on that separately
    (mirrors news_context.py's shape) so this stays a pure fetch."""
    if not settings.adanos_api_key:
        return None
    try:
        return get_adanos_source().fetch(ticker)
    except Exception as exc:
        logger.warn("social_context_fetch_error", ticker=ticker, error=str(exc)[:200])
        return None


class SocialFeed(NamedTuple):
    """CR090 — the Social Media Analyst's live feed for one Room/1-on-1 turn,
    tagged with the shared 3-state `LiveDataState` marker. `sentiment` is set
    ONLY when `state is LiveDataState.LIVE`; for WITHHELD_PAID and UNAVAILABLE
    it is None — the paid Reddit payload is never handed to a non-entitled turn,
    and the caller (CR090-ROOM) branches on `state` to disclose the paywall or
    fall back to the honest synthetic block."""

    state: LiveDataState
    sentiment: SocialSentiment | None


def resolve_social_feed(ticker: str, *, entitled: bool) -> SocialFeed:
    """Resolve the Social Analyst's live feed + its 3-state marker for a turn.

    Additive to the existing binary path — `fetch_live_sentiment` and its
    callers are untouched. Mirrors `news_context.resolve_news_feed`: probes the
    (cache-first, quota-metered) Adanos feed to learn whether live sentiment is
    *available*, classifies with the shared `live_data_state`, and returns the
    payload ONLY for a LIVE (available + entitled) turn. A WITHHELD_PAID turn
    gets the marker with `sentiment=None` — never a silent synthetic swap
    (DEF059), and the surcharge charges nothing for it.

    Same quota note as the news resolver: probing availability for a
    non-entitled user still consults the cached feed; if protecting
    Adanos's 250-call/month budget against non-entitled probes matters, the ROOM
    lane can gate this to entitled turns and compose WITHHELD_PAID directly via
    the exposed `live_data_state` classifier.
    """
    s = fetch_live_sentiment(ticker)
    state = live_data_state(available=s is not None, entitled=entitled)
    return SocialFeed(
        state=state,
        sentiment=s if state is LiveDataState.LIVE else None,
    )


def format_sentiment_tone(s: SocialSentiment) -> str:
    if s.bullish_pct > s.bearish_pct + 5:
        return "bullish"
    if s.bearish_pct > s.bullish_pct + 5:
        return "bearish"
    return "mixed"


def format_sentiment_score(s: SocialSentiment) -> str:
    return f"{s.sentiment_score:+.2f} (live Reddit sentiment, Adanos)"


def format_mention_trend(s: SocialSentiment) -> str:
    return f"{s.mentions:,} Reddit mentions over {s.period_days}d, trend: {s.trend}"


def format_community_read(s: SocialSentiment) -> str:
    if not s.top_subreddits:
        return "no dominant community this period"
    line = f"most active in r/{', r/'.join(s.top_subreddits)}"
    # CR148 Tier A — the breadth. "most active in r/wallstreetbets, r/stocks,
    # r/stockmarket" reads as the whole sample; for AAPL it is 3 of 41.
    if s.subreddit_count > len(s.top_subreddits):
        line += f" ({len(s.top_subreddits)} of {s.subreddit_count} subreddits in the sample)"
    return line


def format_pattern(s: SocialSentiment) -> str:
    return f"buzz score {s.buzz_score:.0f}/100, bullish {s.bullish_pct}% / bearish {s.bearish_pct}%"


def format_sentiment_split(s: SocialSentiment) -> str:
    """The neutral residue, stated. `bullish_pct`/`bearish_pct` are two numbers
    that do not sum to 100 and the gap was never named — it ran 42%–71% of the
    sample (median 52.5%) and is usually the LARGEST class. AAPL: 22% bullish,
    20% bearish, and 58% of 1,993 mentions saying neither."""
    if not (s.positive_count or s.negative_count or s.neutral_count):
        return ""
    total = s.positive_count + s.negative_count + s.neutral_count
    line = (
        f"{s.positive_count:,} positive / {s.negative_count:,} negative / "
        f"{s.neutral_count:,} neutral"
    )
    if total > 0 and s.neutral_count:
        line += f" — neutral is {s.neutral_count / total * 100:.0f}% of the classified sample"
    return line


def format_engagement(s: SocialSentiment) -> str:
    """Intensity, which `buzz_score` compresses into one opaque 0–100 number.
    100 mentions across 12 posts with 40,000 upvotes is not the same event as
    100 mentions across 95 posts with 200."""
    parts = []
    if s.unique_posts:
        parts.append(f"{s.unique_posts:,} distinct posts")
    if s.total_upvotes:
        parts.append(f"{s.total_upvotes:,} total upvotes")
    return ", ".join(parts)


def format_subreddit_split(s: SocialSentiment) -> tuple[str, ...]:
    """Per-community mentions + sentiment + buzz — the evidence the agent was
    inventing. One line per community so nothing has to be attributed by
    guesswork (CR148 F3: 9 of 18 turns attached a quantity, tone or trend to a
    named subreddit the sheet carried no per-community data for)."""
    return tuple(
        f"r/{c.subreddit}: {c.mentions:,} mentions, sentiment {c.sentiment_score:+.2f}, "
        f"buzz {c.buzz_score:.0f}/100"
        for c in s.subreddit_stats
    )


def format_sample_size_caveat(s: SocialSentiment) -> str:
    """Fires below `_MIN_MENTIONS_FOR_A_PERCENTAGE`. Deliberately states the
    ARITHMETIC rather than instructing the agent to be careful — a prompt line
    telling a model to discount a number is exactly the control P2 says does not
    hold (CR038 measured such instructions at ~30%). A reader given "3 posts
    against 1" cannot round it up into a market read the way it can round up
    "bullish 30% / bearish 10%"."""
    if s.mentions >= _MIN_MENTIONS_FOR_A_PERCENTAGE or s.mentions <= 0:
        return ""
    bulls = round(s.bullish_pct * s.mentions / 100)
    bears = round(s.bearish_pct * s.mentions / 100)
    return (
        f"SMALL SAMPLE — {s.mentions} mentions. The percentages above are "
        f"~{bulls} post(s) against ~{bears}; below {_MIN_MENTIONS_FOR_A_PERCENTAGE} "
        "mentions the bull/bear gap is inside the sampling error, so treat the "
        "tone as unresolved rather than weak."
    )


def format_fetched_age(s: SocialSentiment) -> str:
    """When this snapshot was actually taken. Replaces "as of this call", which
    was false for most turns: 93% of cached rows were older than 7 days and the
    mean age was 20.2 days when CR148 measured it (2026-08-08)."""
    if not s.fetched_at:
        return "fetch time not recorded"
    stamp = datetime.fromtimestamp(s.fetched_at, tz=timezone.utc).strftime("%Y-%m-%d")
    return f"fetched {stamp} ({_relative_age(s.fetched_at)})"


def build_social_context_block(ticker: str) -> str | None:
    """System-prompt-ready block of real Reddit sentiment — 1-on-1 path,
    Social Media Analyst only. Includes a couple of real post snippets as
    LLM-only synthesis context — the agent must never quote them verbatim
    or attribute to a specific user (enforced in the block's own text and
    in content/agents/social_media_analyst.md).
    """
    if not settings.use_real_market_data or not settings.adanos_api_key:
        return None
    s = fetch_live_sentiment(ticker)
    if s is None:
        return None
    sym = ticker.upper()
    lines = [
        f"─── LIVE SOCIAL SENTIMENT — {sym} (Reddit only, via Adanos, {format_fetched_age(s)}) ───",
        f"{format_mention_trend(s)}. {format_pattern(s)}.",
    ]
    split = format_sentiment_split(s)
    if split:
        lines.append(f"Classified: {split}.")
    engagement = format_engagement(s)
    if engagement:
        lines.append(f"Engagement: {engagement}.")
    lines.append(f"{format_community_read(s)}.")
    community_lines = format_subreddit_split(s)
    if community_lines:
        lines.append("Per community (this is the ONLY per-community data you have — "
                     "do not attribute a figure, tone or trend to a community not listed here):")
        lines += [f"- {line}" for line in community_lines]
    caveat = format_sample_size_caveat(s)
    if caveat:
        lines.append(caveat)
    if s.sample_snippets:
        lines.append("Sample community reactions (context only — do NOT quote verbatim or attribute to a user):")
        lines += [f"- {snippet[:200]}" for snippet in s.sample_snippets]
    lines.append(
        "(Real Reddit-only aggregate for this ticker. No Twitter/X, StockTwits, "
        "Google Trends, or Discord data exists. Synthesize the vibe in your own "
        "words — never echo a snippet verbatim, never imply you read a specific post.)"
    )
    return "\n".join(lines)
