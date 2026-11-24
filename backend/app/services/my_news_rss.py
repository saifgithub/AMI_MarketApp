"""Malay Mail Money RSS as a Bursa (`.KL`) Room's second news source (CR282 lane E2).

Yahoo's per-stock headlines for Bursa names are thin. Malay Mail's public Money
feed (`https://www.malaymail.com/feed/rss/money`, ~50 items) is not, so a `.KL`
News Analyst gets the items that name the Room's company, plus up to two
market-wide items (Bursa Malaysia, the FBM KLCI, the ringgit) labelled as market
context rather than company news.

Terms (read before widening what this does). Bernama's copyright terms bar
reproduction or transmission without express consent and Malay Mail asserts
copyright, so permission is being requested before testers. Two consequences are
structural here, not promised in prose: only headline + link + date ever leave
this module (the feed's `<content:encoded>` full text is never read), and the
whole source sits behind `MY_NEWS_RSS_ENABLED`, default off.

Degrade loudly (CR040): a failed fetch is never cached and never an empty list.
`fetch_feed` returns the reason, `status()` reports "off" / "live" /
"unavailable", and the Room's News note names whichever it is.
"""

from __future__ import annotations

import re
import time
from datetime import timezone
from email.utils import parsedate_to_datetime
from threading import RLock
from typing import Any, NamedTuple
from xml.etree import ElementTree as ET

import httpx

from app.core.config import settings
from app.core.logging import logger

FEED_URL = "https://www.malaymail.com/feed/rss/money"

#: `LiveHeadline.source` for every item from this feed.
SOURCE_LABEL = "malaymail_rss"

#: How the desk is told where an item came from.
ATTRIBUTION = "Malay Mail"
MARKET_ATTRIBUTION = "Malay Mail (market-wide, not company news)"

_USER_AGENT = "Mozilla/5.0"
_TIMEOUT_S = 4.0
_MAX_BODY_BYTES = 5_000_000
_CACHE_TTL_S = 15 * 60

#: At most this many market-wide items are added beside the company's own.
MAX_MARKET_ITEMS = 2

_MARKET_RE = re.compile(r"\b(?:bursa\s+malaysia|fbm\s+klci|ringgit)\b", re.IGNORECASE)

# Corporate-form words dropped from a registered name before it is matched.
_SUFFIX_WORDS = frozenset({
    "berhad", "bhd", "holdings", "holding", "group", "corporation", "corp",
    "company", "co", "ltd", "limited", "plc", "sdn", "inc",
})

# A name that reduces to ONE of these is an industry or a country, not an issuer;
# matching it would attribute any banking or Malaysian article to the company.
_GENERIC_SINGLE_WORDS = frozenset({
    "bank", "banking", "capital", "malaysia", "malaysian", "malayan", "public",
    "national", "united", "global", "first", "energy", "power", "gas", "oil",
    "land", "properties", "property", "resources", "industries", "international",
    "technology", "technologies", "telecommunications", "plantation", "plantations",
    "insurance", "steel", "metal", "asia", "asian", "pacific",
})

# Three letters or fewer is a ticker-style acronym (IOI, KPJ, TNB) or an ordinary
# word. An acronym is matched upper-case and whole-word only; these never match.
_COMMON_SHORT_WORDS = frozenset({
    "all", "one", "top", "new", "big", "sun", "gas", "oil", "air", "sky", "sea",
    "can", "may", "key", "own", "now", "set", "fix",
})

# Yahoo names a few Bursa issuers by a registered name the press no longer uses.
# Kept deliberately tiny and dated; add an entry only against a real headline.
_ALIASES: dict[str, tuple[str, ...]] = {
    "5099.KL": ("AirAsia",),  # Capital A Berhad (2022 rename); press still says AirAsia
    "1155.KL": ("Maybank",),  # Malayan Banking Berhad
}


class FeedItem(NamedTuple):
    """One feed item, reduced to what is allowed to travel: headline, link, date."""

    title: str
    link: str
    published_at: int  # Unix epoch seconds, 0 if unknown


class FeedRead(NamedTuple):
    """`items` is None exactly when the feed could not be read, and `reason` says why."""

    items: tuple[FeedItem, ...] | None
    reason: str | None


class MyNews(NamedTuple):
    """Items for one Room: the company's own, and the market-wide context items."""

    company: tuple[FeedItem, ...]
    market: tuple[FeedItem, ...]


_lock = RLock()
_feed_cache: tuple[float, tuple[FeedItem, ...]] | None = None
_name_cache: dict[str, tuple[float, tuple[str, ...]]] = {}
_NAME_TTL_S = 24 * 3600


def reset_cache() -> None:
    global _feed_cache
    with _lock:
        _feed_cache = None
        _name_cache.clear()


def parse_feed(body: bytes) -> list[FeedItem]:
    """Parse RSS bytes into items. Raises ValueError on anything that is not a feed.

    Only `title`, `link` and `pubDate` are read; `<content:encoded>` and
    `<description>` are never touched. A DOCTYPE or entity declaration is refused
    outright: a news feed has no use for one and stdlib XML expands entities.
    """
    upper = body.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("feed carries a DOCTYPE/ENTITY declaration")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ValueError(f"feed is not well-formed XML: {exc}") from exc
    out: list[FeedItem] = []
    for item in root.iter("item"):
        title = " ".join((item.findtext("title") or "").split())
        link = (item.findtext("link") or "").strip()
        if not title or not link.lower().startswith(("http://", "https://")):
            continue
        out.append(FeedItem(title=title, link=link, published_at=_epoch(item.findtext("pubDate"))))
    return out


def _epoch(raw: str | None) -> int:
    if not raw:
        return 0
    try:
        dt = parsedate_to_datetime(raw.strip())
    except (TypeError, ValueError):
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _download() -> bytes:
    with httpx.Client(
        timeout=_TIMEOUT_S, follow_redirects=True, headers={"User-Agent": _USER_AGENT},
    ) as client:
        resp = client.get(FEED_URL)
    if resp.status_code != 200:
        raise ValueError(f"http_{resp.status_code}")
    body = resp.content
    if len(body) > _MAX_BODY_BYTES:
        raise ValueError(f"feed body over {_MAX_BODY_BYTES} bytes")
    return body


def fetch_feed(*, now: float | None = None) -> FeedRead:
    """The parsed feed, cached 15 minutes. A failure is reported, never cached.

    Does not check the switch: callers gate on `settings.my_news_rss_enabled`.
    """
    global _feed_cache
    t = time.time() if now is None else now
    with _lock:
        if _feed_cache is not None and t - _feed_cache[0] < _CACHE_TTL_S:
            return FeedRead(_feed_cache[1], None)
    try:
        items = tuple(parse_feed(_download()))
        if not items:
            raise ValueError("feed parsed to zero items")
    except Exception as exc:  # noqa: BLE001 — degrade loudly, never fabricate
        reason = f"{type(exc).__name__}: {str(exc)[:160]}"
        logger.warn("my_news_rss_unavailable", reason=reason)
        return FeedRead(None, reason)
    with _lock:
        _feed_cache = (t, items)
    return FeedRead(items, None)


def status() -> str:
    """"off" when the switch is off, else "live" or "unavailable" for this call."""
    if not settings.my_news_rss_enabled:
        return "off"
    return "live" if fetch_feed().items is not None else "unavailable"


# ── matching ────────────────────────────────────────────────────────────────


def _fetch_names(ticker: str) -> tuple[str, ...]:
    """Yahoo's shortName and longName for a ticker; empty on any failure."""
    try:
        import yfinance as yf

        info: dict[str, Any] = yf.Ticker(ticker.upper()).info or {}
    except Exception as exc:  # noqa: BLE001
        logger.warn("my_news_rss_names_error", ticker=ticker, error=str(exc)[:200])
        return ()
    return tuple(str(info[k]) for k in ("shortName", "longName") if info.get(k))


def names_for(ticker: str) -> tuple[str, ...]:
    """The company's names, cached a day on success only (an empty read is retried)."""
    sym = ticker.upper().strip()
    now = time.time()
    with _lock:
        hit = _name_cache.get(sym)
        if hit is not None and now - hit[0] < _NAME_TTL_S:
            return hit[1]
    names = _fetch_names(sym)
    if names:
        with _lock:
            _name_cache[sym] = (now, names)
    return names


def _phrase_tokens(name: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9]+", name)
    return [w for w in words if w.lower() not in _SUFFIX_WORDS]


def name_patterns(ticker: str, names: tuple[str, ...]) -> list[re.Pattern[str]]:
    """Whole-word patterns for each way the press would name this company.

    Each registered name has its corporate-form words stripped ("CIMB Group
    Holdings Berhad" -> "CIMB"; "Malayan Banking Berhad" -> "Malayan Banking").
    Three guards keep a short or generic name from manufacturing a false match:
    a name that reduces to one generic word is dropped; a name of three letters or
    fewer matches only in upper case ("TNB" yes, "tnb" and "One" no); and every
    pattern needs a non-alphanumeric boundary on both sides.
    """
    seen: set[str] = set()
    patterns: list[re.Pattern[str]] = []
    for raw in (*names, *_ALIASES.get(ticker.upper().strip(), ())):
        tokens = _phrase_tokens(raw)
        if not tokens:
            continue
        key = " ".join(tokens).lower()
        if key in seen:
            continue
        seen.add(key)
        if len(tokens) == 1:
            word = tokens[0]
            if word.lower() in _GENERIC_SINGLE_WORDS:
                continue
            if len(word) <= 3:
                if word.lower() in _COMMON_SHORT_WORDS:
                    continue
                body, flags = re.escape(word.upper()), 0
            else:
                body, flags = re.escape(word), re.IGNORECASE
        else:
            body, flags = r"\s+".join(re.escape(t) for t in tokens), re.IGNORECASE
        patterns.append(re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", flags))
    return patterns


def match_items(
    items: tuple[FeedItem, ...], ticker: str, names: tuple[str, ...],
) -> MyNews:
    """Split feed items into the company's own and up to two market-wide ones."""
    patterns = name_patterns(ticker, names)
    ordered = sorted(items, key=lambda i: i.published_at, reverse=True)
    company = tuple(i for i in ordered if any(p.search(i.title) for p in patterns))
    taken = {i.link for i in company}
    market = tuple(
        i for i in ordered if i.link not in taken and _MARKET_RE.search(i.title)
    )[:MAX_MARKET_ITEMS]
    return MyNews(company=company, market=market)


def items_for(ticker: str) -> MyNews | None:
    """This Room's Malay Mail items, or None when the feed is off or unreadable.

    Distinguish the two with `status()`; both leave the desk without the source and
    the Room's News note says which.
    """
    if not settings.my_news_rss_enabled:
        return None
    feed = fetch_feed()
    if feed.items is None:
        return None
    return match_items(feed.items, ticker, names_for(ticker))
