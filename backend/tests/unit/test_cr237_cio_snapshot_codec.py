"""CR237 round 3 (auditor U66 MAJOR-B) — the CIO-retry snapshot's profile codec.

The snapshot is written to a JSONB column and read back by "Ask the CIO
again". Every value the live profile carries must come back as the same type
it went in as, or the retry's CIO prompt renders something else (or crashes,
as `LiveHeadline` did). A value the codec cannot rebuild must be refused, not
coerced.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import NamedTuple

import pytest

from app.services.buyback_price import BuybackPrice
from app.services.cio_snapshot_codec import decode_profile, encode_profile
from app.services.dividend_growth import DividendGrowth
from app.services.news_context import LiveHeadline


def _headline(i: int) -> LiveHeadline:
    return LiveHeadline(
        title=f"Headline {i}", link=f"https://example.com/{i}",
        publisher="Reuters", published_at=1_758_000_000 + i,
        sentiment=None if i % 2 else "Bullish", source="yfinance",
        summary=f"Summary {i}",
    )


def _dividend_growth() -> DividendGrowth:
    return DividendGrowth(
        first_year=2020, last_year=2024,
        rate_by_year=((2020, 0.82), (2024, 1.0)),
        total_by_year=((2020, 3.28), (2024, 4.0)),
        cagr_pct=5.1, raised_years=4, comparisons=4,
        payments_per_year=((2020, 4), (2024, 4)),
        specials=((date(2023, 5, 12), 0.5),),
        partial_year=None, truncated_by_gap=False,
    )


def _buyback() -> BuybackPrice:
    return BuybackPrice(
        avg_price=187.4, dollars=9.1e10, shares=4.86e8,
        period_start=date(2024, 10, 1), period_end=date(2025, 9, 30), quarters=4,
    )


def _round_trip(profile):
    stored = json.loads(json.dumps(encode_profile(profile), allow_nan=False))
    return decode_profile(stored)


def test_every_typed_value_in_a_live_profile_comes_back_as_itself():
    profile = {
        "news_headlines": [_headline(1), _headline(2), _headline(3)],
        "dividend_growth": _dividend_growth(),
        "buyback_price": _buyback(),
        "field_state": {"news": "live", "dividend_growth": "live"},
        "subreddit_split": ["r/stocks: 12", "r/investing: 4"],
        "executive_change_items": [{"filed": "2025-01-02", "excerpt": None}],
        "pe": 31.2, "volume_ratio": 1, "is_growth": True, "catalyst": "x",
    }

    back = _round_trip(profile)

    assert back == profile
    assert all(type(h) is LiveHeadline for h in back["news_headlines"])
    assert back["news_headlines"][1].title == "Headline 2"
    assert type(back["dividend_growth"]) is DividendGrowth
    assert back["dividend_growth"].specials == ((date(2023, 5, 12), 0.5),)
    assert type(back["buyback_price"].period_end) is date


def test_scalars_json_cannot_carry_are_rebuilt_exactly():
    profile = {
        "nan": float("nan"), "inf": float("inf"), "neg_inf": float("-inf"),
        "d": date(2025, 3, 1),
        "dt": datetime(2025, 3, 1, 12, 30, tzinfo=timezone.utc),
        "dec": Decimal("1.10"),
        "tup": (1, (2, "x")),
    }

    back = _round_trip(profile)

    assert math.isnan(back["nan"])
    assert back["inf"] == math.inf and back["neg_inf"] == -math.inf
    assert back["d"] == date(2025, 3, 1) and type(back["d"]) is date
    assert back["dt"] == profile["dt"]
    assert back["dec"] == Decimal("1.10")
    assert back["tup"] == (1, (2, "x"))


def test_the_encoding_is_strict_json():
    encoded = encode_profile({"x": float("nan"), "h": [_headline(1)]})
    json.dumps(encoded, allow_nan=False)


class _Unregistered(NamedTuple):
    a: int


@pytest.mark.parametrize("value", [
    _Unregistered(1),
    object(),
    {1: "non-string key"},
    {"__cr237__": "a key that would be read as a tag"},
])
def test_a_value_it_cannot_rebuild_is_refused_not_coerced(value):
    with pytest.raises(TypeError):
        encode_profile({"v": value})


def test_an_unknown_tag_is_refused_on_decode():
    with pytest.raises(ValueError):
        decode_profile({"v": {"__cr237__": "os.system", "v": {}}})
