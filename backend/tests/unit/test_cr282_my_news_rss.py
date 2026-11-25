"""CR282 lane E2 — Malay Mail Money RSS as a Bursa Room's second news source.

Network is mocked throughout: the feed is the fixture under tests/fixtures/my_news
(real titles and links from the live feed, full text replaced by canaries).
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.core.config import settings
from app.schemas import AgentId
from app.services import my_news_rss, news_context, room_bank, room_runner
from app.services.market_data import NewsItem, set_market_data_provider
from app.services.news_context import LiveHeadline, fetch_live_news, pick_catalyst
from app.services.room_market import my_desk_footer

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "my_news" / "malaymail_money.xml"
_REPO = Path(__file__).resolve().parents[2].parent
KL = "1155.KL"

MAYBANK = ("MAYBANK", "Malayan Banking Berhad")
AIRASIA = ("CAPITAL A", "Capital A Berhad")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(settings, "alpha_vantage_api_key", "")
    monkeypatch.setattr(settings, "my_news_rss_enabled", False)
    my_news_rss.reset_cache()
    yield
    my_news_rss.reset_cache()


def _fixture_bytes() -> bytes:
    return _FIXTURE.read_bytes()


def _items() -> tuple[my_news_rss.FeedItem, ...]:
    return tuple(my_news_rss.parse_feed(_fixture_bytes()))


def _fresh_items() -> tuple[my_news_rss.FeedItem, ...]:
    """The fixture with its dates shifted so the newest item is one hour old."""
    items = _items()
    shift = int(time.time()) - 3600 - max(i.published_at for i in items)
    return tuple(i._replace(published_at=i.published_at + shift) for i in items)


class _Yahoo:
    name = "fake"

    def __init__(self, items):
        self._items = items

    def news(self, ticker, limit=5):
        return self._items

    def quote(self, ticker):
        return None

    def get_price(self, ticker):
        return None

    def history(self, ticker, period):
        return None

    def earnings(self, ticker):
        return None


def _yahoo_item(title, *, age_s=7200, link="https://finance.example/y"):
    return NewsItem(
        title=title, link=link, publisher="Yahoo Finance",
        published_at=int(time.time()) - age_s, summary="",
    )


def _turn_on(monkeypatch, names=MAYBANK, items=None):
    monkeypatch.setattr(settings, "my_news_rss_enabled", True)
    feed = items if items is not None else _fresh_items()
    monkeypatch.setattr(my_news_rss, "fetch_feed", lambda **_: my_news_rss.FeedRead(feed, None))
    monkeypatch.setattr(my_news_rss, "names_for", lambda t: names)


# ── 1. parsing ───────────────────────────────────────────────────────────────


def test_the_fixture_parses_to_title_link_and_date_only():
    items = _items()
    assert len(items) == 12
    first = next(i for i in items if i.title.startswith("Maybank 3Q"))
    assert first.link.startswith("https://www.malaymail.com/")
    # Mon, 23 Nov 2026 16:30:00 +0800 == 08:30:00 UTC
    assert time.gmtime(first.published_at)[:6] == (2026, 11, 23, 8, 30, 0)
    assert set(my_news_rss.FeedItem._fields) == {"title", "link", "published_at"}
    assert "CANARY" not in repr(items)


def test_content_encoded_full_text_never_reaches_a_headline(monkeypatch):
    _turn_on(monkeypatch)
    set_market_data_provider(_Yahoo(None))
    out = fetch_live_news(KL) or []
    assert out
    assert "CANARY" not in repr(out)
    assert all(h.summary == "" for h in out)


@pytest.mark.parametrize("body", [
    b"not xml at all",
    b'<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY a "x">]><rss><channel><item><title>t</title><link>https://a.b/c</link></item></channel></rss>',
])
def test_a_malformed_or_entity_bearing_feed_is_refused(body):
    with pytest.raises(ValueError):
        my_news_rss.parse_feed(body)


def test_an_item_without_a_title_or_an_http_link_is_skipped_and_a_bad_date_is_zero():
    body = (
        b"<rss><channel>"
        b"<item><title>No link</title></item>"
        b"<item><title>Bad scheme</title><link>javascript:alert(1)</link></item>"
        b"<item><title>Bad date</title><link>https://a.b/c</link><pubDate>yesterday-ish</pubDate></item>"
        b"</channel></rss>"
    )
    got = my_news_rss.parse_feed(body)
    assert [(i.title, i.published_at) for i in got] == [("Bad date", 0)]


# ── 2. name matching ─────────────────────────────────────────────────────────


def _titles(match: my_news_rss.MyNews) -> list[str]:
    return [i.title for i in match.company]


def test_maybank_matches_by_short_name_in_a_headline():
    m = my_news_rss.match_items(_items(), KL, MAYBANK)
    assert _titles(m) == ["Maybank 3Q net profit rises to RM2.74b despite lower revenue"]


def test_capital_a_matches_the_press_name_airasia_through_the_alias():
    m = my_news_rss.match_items(_items(), "5099.KL", AIRASIA)
    assert _titles(m) == ["AirAsia halves Q3 losses to RM381m as higher fares cushion fuel costs"]
    # Without the alias the registered names alone find nothing: no guessing.
    assert my_news_rss.match_items(_items(), "9999.KL", AIRASIA).company == ()


def test_a_long_name_is_stripped_of_corporate_suffixes_before_matching():
    m = my_news_rss.match_items(_items(), "6742.KL", ("YTL POWER", "YTL Power International Berhad"))
    assert _titles(m) == ["YTL Power says Johor data centres unaffected by latest US chip controls"]
    cimb = my_news_rss.match_items(_items(), "1023.KL", ("CIMB GROUP", "CIMB Group Holdings Berhad"))
    assert _titles(cimb) == [
        "Malaysia’s vehicle sales forecast to rise 2.2pc to 815,000 units in 2026, says CIMB Securities"
    ]


def _t(title):
    return my_news_rss.FeedItem(title=title, link=f"https://x.test/{abs(hash(title))}", published_at=1)


def _hits(titles, names, ticker="9999.KL"):
    return [i.title for i in my_news_rss.match_items(tuple(_t(x) for x in titles), ticker, names).company]


def test_short_and_generic_names_do_not_manufacture_matches():
    titles = [
        "One in three firms plan to hire", "Gas prices rise on all fronts", "Sun sets on the old index",
        "Sunway opens a new mall", "Bank Negara keeps rates", "Public sector wages rise",
        "Capital Adequacy rules tighten", "Banks to the rescue", "Top stocks to watch",
        "Malaysia exports climb", "Malayan tigers return",
    ]
    for names in [("ONE", "One Holdings Bhd"), ("GAS", "Gas Bhd"), ("SUN", "Sun Group Berhad"),
                  ("BANK", "Bank Berhad"), ("PUBLIC", "Public Berhad"), ("MALAYSIA", "Malaysia Berhad"),
                  ("CAPITAL", "Capital Berhad"), ("CAPITAL A", "Capital A Berhad"), ("TOP", "Top Bhd")]:
        assert _hits(titles, names) == [], names


def test_a_three_letter_acronym_matches_upper_case_whole_word_only():
    names = ("IOI CORP", "IOI Corporation Berhad")
    assert _hits(["IOI posts record profit", "Cultivation of ioi rice", "IOIX unrelated"], names) == [
        "IOI posts record profit"
    ]


def test_matching_is_whole_word_and_case_insensitive_for_longer_names():
    names = ("MAYBANK", "Malayan Banking Berhad")
    assert _hits(["MAYBANK raises dividend", "maybank's outlook", "Maybankx is not it"], names) == [
        "MAYBANK raises dividend", "maybank's outlook",
    ]
    assert _hits(["Malayan  Banking shares jump"], names) == ["Malayan  Banking shares jump"]


def test_no_names_means_no_company_matches_but_market_items_still_flow():
    m = my_news_rss.match_items(_items(), "9999.KL", ())
    assert m.company == () and len(m.market) == 2


# ── 3. market-wide items ─────────────────────────────────────────────────────


def test_market_items_are_the_two_newest_bursa_klci_or_ringgit_titles():
    m = my_news_rss.match_items(_items(), "9999.KL", ("Zzzz Berhad",))
    assert [i.title for i in m.market] == [
        "Ringgit ends lower against US dollar amid hawkish Fed expectations",
        "Tech stocks rebound, but utilities drag Bursa Malaysia into negative territory",
    ]


def test_a_company_item_is_not_repeated_as_market_context():
    names = ("BURSA MALAYSIA", "Bursa Malaysia Berhad")
    m = my_news_rss.match_items(_items(), "1818.KL", names)
    company = {i.title for i in m.company}
    assert company and not company & {i.title for i in m.market}
    assert len(m.market) <= 2


# ── 4. merge and de-dup ──────────────────────────────────────────────────────


def test_company_items_merge_with_yahoo_and_market_items_are_labelled(monkeypatch):
    _turn_on(monkeypatch)
    set_market_data_provider(_Yahoo([_yahoo_item("Maybank unit wins licence", age_s=90000)]))
    out = fetch_live_news(KL)
    assert out is not None
    by_source = {}
    for h in out:
        by_source.setdefault(h.source, []).append(h)
    assert [h.title for h in by_source["yfinance"]] == ["Maybank unit wins licence"]
    mm = by_source["malaymail_rss"]
    company = [h for h in mm if h.publisher == "Malay Mail"]
    market = [h for h in mm if h.publisher != "Malay Mail"]
    assert [h.title for h in company] == ["Maybank 3Q net profit rises to RM2.74b despite lower revenue"]
    assert len(market) == 2
    assert all(h.publisher == "Malay Mail (market-wide, not company news)" for h in market)
    assert out[-2:] == market  # market context sits after the company items
    assert all(h.link.startswith("https://www.malaymail.com/") for h in mm)
    rendered = news_context.format_headline(company[0])
    assert "Malay Mail" in rendered and "CANARY" not in rendered


def test_a_title_already_from_yahoo_is_not_repeated(monkeypatch):
    _turn_on(monkeypatch)
    title = "Maybank 3Q net profit rises to RM2.74b despite lower revenue"
    set_market_data_provider(_Yahoo([_yahoo_item(title.upper(), age_s=60)]))
    out = fetch_live_news(KL) or []
    assert [h.title for h in out if "Maybank".lower() in h.title.lower()] == [title.upper()]


def test_the_company_cap_of_five_still_holds_and_market_items_ride_beside_it(monkeypatch):
    many = tuple(
        my_news_rss.FeedItem(f"Maybank story {n}", f"https://x.test/{n}", int(time.time()) - 600 * n)
        for n in range(1, 9)
    ) + _fresh_items()
    _turn_on(monkeypatch, items=many)
    set_market_data_provider(_Yahoo([_yahoo_item("Maybank yahoo item")]))
    out = fetch_live_news(KL) or []
    company = [h for h in out if h.publisher != "Malay Mail (market-wide, not company news)"]
    market = [h for h in out if h.publisher == "Malay Mail (market-wide, not company news)"]
    assert len(company) == news_context.DEFAULT_HEADLINE_LIMIT == 5
    assert len(market) == 2


def test_market_context_alone_does_not_make_the_feed_live(monkeypatch):
    _turn_on(monkeypatch, names=("Zzzz Berhad",))
    set_market_data_provider(_Yahoo(None))
    assert fetch_live_news("9999.KL") is None


def test_items_older_than_the_recency_floor_are_dropped(monkeypatch):
    old = tuple(i._replace(published_at=i.published_at - 30 * 86400) for i in _fresh_items())
    _turn_on(monkeypatch, items=old)
    set_market_data_provider(_Yahoo(None))
    assert fetch_live_news(KL) is None


def test_a_matched_malay_mail_headline_is_the_on_ticker_catalyst(monkeypatch):
    _turn_on(monkeypatch)
    set_market_data_provider(_Yahoo([_yahoo_item("Banks lead regional rally", age_s=60)]))
    out = fetch_live_news(KL) or []
    pick, on_ticker = pick_catalyst(out, KL, "Malayan Banking Berhad")
    assert on_ticker and pick.source == "malaymail_rss" and pick.publisher == "Malay Mail"
    market = next(h for h in out if "market-wide" in h.publisher)
    assert pick_catalyst([market], KL, "Malayan Banking Berhad")[1] is False


# ── 5. the switch ────────────────────────────────────────────────────────────


def _boom(*_a, **_k):
    raise AssertionError("the feed must not be touched")


def test_switch_off_means_no_fetch_and_the_note_says_not_enabled(monkeypatch):
    monkeypatch.setattr(my_news_rss, "_download", _boom)
    monkeypatch.setattr(my_news_rss, "names_for", _boom)
    set_market_data_provider(_Yahoo([_yahoo_item("Maybank unit wins licence")]))
    out = fetch_live_news(KL) or []
    assert [h.source for h in out] == ["yfinance"]
    assert my_news_rss.status() == "off"
    profile: dict = {}
    room_runner._stamp_my_macro(profile, {}, date(2026, 11, 24))
    assert profile["my_news_rss"] == "off"
    note = my_desk_footer(AgentId.NEWS_ANALYST, profile)
    assert "Malay Mail Bursa news feed is not enabled on this deployment" in note
    assert "this read does not include it" in note


def test_the_setting_defaults_off_in_code():
    from app.core.config import Settings

    assert Settings.model_fields["my_news_rss_enabled"].default is False


# ── 6. failure is loud and never cached ──────────────────────────────────────


class _Client:
    """httpx.Client stand-in: `outcomes` is consumed one per `get`."""

    calls = 0
    outcomes: list = []

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url):
        type(self).calls += 1
        out = type(self).outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def _resp(status=200, body=None):
    return httpx.Response(status, content=_fixture_bytes() if body is None else body)


@pytest.fixture
def client(monkeypatch):
    _Client.calls = 0
    _Client.outcomes = []
    monkeypatch.setattr(my_news_rss.httpx, "Client", _Client)
    return _Client


@pytest.mark.parametrize("bad", [
    httpx.ConnectError("boom"), _resp(503), _resp(200, b"<rss><channel></channel></rss>"), _resp(200, b"junk"),
])
def test_a_failed_fetch_is_reported_unavailable_and_never_cached(client, bad):
    client.outcomes = [bad, _resp()]
    first = my_news_rss.fetch_feed(now=1000.0)
    assert first.items is None and first.reason
    second = my_news_rss.fetch_feed(now=1001.0)  # a failure was not cached: this refetches
    assert client.calls == 2
    assert second.items is not None and len(second.items) == 12


def test_a_success_is_cached_for_fifteen_minutes_then_refetched(client):
    client.outcomes = [_resp(), _resp()]
    my_news_rss.fetch_feed(now=1000.0)
    my_news_rss.fetch_feed(now=1000.0 + 899)
    assert client.calls == 1
    my_news_rss.fetch_feed(now=1000.0 + 901)
    assert client.calls == 2


def test_a_failure_after_a_cached_success_inside_the_ttl_still_serves_the_cache(client):
    client.outcomes = [_resp()]
    my_news_rss.fetch_feed(now=1000.0)
    assert my_news_rss.fetch_feed(now=1100.0).items is not None
    assert client.calls == 1


def test_when_on_but_the_fetch_fails_the_note_says_unavailable_this_call(monkeypatch, client):
    monkeypatch.setattr(settings, "my_news_rss_enabled", True)
    client.outcomes = [httpx.ConnectError("down")] * 4
    monkeypatch.setattr(my_news_rss, "names_for", lambda t: MAYBANK)
    set_market_data_provider(_Yahoo([_yahoo_item("Maybank unit wins licence")]))
    out = fetch_live_news(KL) or []
    assert [h.source for h in out] == ["yfinance"]  # Yahoo is not taken down with it
    profile: dict = {}
    room_runner._stamp_my_macro(profile, {}, date(2026, 11, 24))
    assert profile["my_news_rss"] == "unavailable"
    note = my_desk_footer(AgentId.NEWS_ANALYST, profile)
    assert "Malay Mail Bursa news feed is unavailable this call" in note


def test_when_live_the_note_says_what_malay_mail_items_are(monkeypatch, client):
    monkeypatch.setattr(settings, "my_news_rss_enabled", True)
    client.outcomes = [_resp()]
    profile: dict = {}
    room_runner._stamp_my_macro(profile, {}, date(2026, 11, 24))
    assert profile["my_news_rss"] == "live"
    note = my_desk_footer(AgentId.NEWS_ANALYST, profile)
    assert "headline, link and date only" in note and "market context, not news about this company" in note


def test_the_existing_news_note_is_kept_and_other_desks_are_untouched():
    note = my_desk_footer(AgentId.NEWS_ANALYST, {"market": "MY", "my_news_rss": "off"})
    assert note.startswith("[AMI note: ") and "not available for this market" in note
    for agent in (AgentId.FUNDAMENTALS_ANALYST, AgentId.SOCIAL_MEDIA_ANALYST):
        assert "Malay Mail" not in (my_desk_footer(agent, {"market": "MY", "my_news_rss": "off"}) or "")
    bare = my_desk_footer(AgentId.NEWS_ANALYST, {"market": "MY"})
    assert "Malay Mail" not in bare


# ── 7. US unchanged ──────────────────────────────────────────────────────────


def test_a_us_ticker_never_touches_the_feed_and_is_identical_on_or_off(monkeypatch):
    monkeypatch.setattr(my_news_rss, "fetch_feed", _boom)
    monkeypatch.setattr(my_news_rss, "names_for", _boom)
    monkeypatch.setattr(my_news_rss, "items_for", _boom)
    yahoo = [
        _yahoo_item("NVIDIA beats estimates", age_s=3600, link="https://y/1"),
        _yahoo_item("Chip stocks slide", age_s=7200, link="https://y/2"),
    ]
    set_market_data_provider(_Yahoo(yahoo))
    monkeypatch.setattr(settings, "my_news_rss_enabled", False)
    off = fetch_live_news("NVDA")
    monkeypatch.setattr(settings, "my_news_rss_enabled", True)
    on = fetch_live_news("NVDA")
    assert on == off
    assert [h.title for h in on] == ["NVIDIA beats estimates", "Chip stocks slide"]
    assert {h.source for h in on} == {"yfinance"}
    block_on = news_context.build_news_context_block("NVDA")
    monkeypatch.setattr(settings, "my_news_rss_enabled", False)
    assert news_context.build_news_context_block("NVDA") == block_on


def test_a_us_sheet_gets_no_note_no_key_and_the_same_bank_variant(monkeypatch):
    assert my_desk_footer(AgentId.NEWS_ANALYST, {"my_news_rss": "off"}) is None
    kw = dict(news_state="live", social_state="live", market_withheld=False)
    off = room_bank.sheet_variant(**kw, ticker="NVDA")
    monkeypatch.setattr(settings, "my_news_rss_enabled", True)
    assert room_bank.sheet_variant(**kw, ticker="NVDA") == off == room_bank.sheet_variant(**kw)
    assert "my_" not in off


def test_the_bursa_bank_variant_is_revision_five_and_carries_the_switch(monkeypatch):
    kw = dict(news_state="live", social_state="live", market_withheld=False, ticker=KL)
    assert room_bank.MY_SHEET_REVISION == 5
    off = room_bank.sheet_variant(**kw)
    assert off.endswith("|my_rev=5")
    monkeypatch.setattr(settings, "my_news_rss_enabled", True)
    on = room_bank.sheet_variant(**kw)
    assert on == off + "|my_news=on" and on != off


# ── 8. compose parity ────────────────────────────────────────────────────────


def test_the_switch_is_forwarded_in_compose_default_off():
    compose = (_REPO / "docker-compose.yml").read_text()
    assert "MY_NEWS_RSS_ENABLED: ${MY_NEWS_RSS_ENABLED:-false}" in compose


def test_the_feed_url_and_user_agent_are_the_probed_ones():
    assert my_news_rss.FEED_URL == "https://www.malaymail.com/feed/rss/money"
    assert my_news_rss._USER_AGENT == "Mozilla/5.0"


def test_live_headline_shape_is_unchanged():
    assert LiveHeadline._fields == (
        "title", "link", "publisher", "published_at", "sentiment", "source", "summary",
    )
