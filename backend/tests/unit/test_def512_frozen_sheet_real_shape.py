"""DEF512 — the frozen fact sheet survives the real shape of a production sheet.

Live Alpha logged `room_fact_sheet_not_freezable ... RatioBaseline ... has no JSON
encoding` on every convene: CR253 put a `RatioBaseline` NamedTuple on the sheet
without adding it to the codec's hand-kept registry, so no Room was ever banked.
The unit fixtures built sheets from plain dicts and never carried a real-data
type, so nothing noticed. This file builds the sheet the way production does,
through `_profile_for_ticker` with every optional block populated by its real
resolver or a faithful fake, and asserts:

  1. every value in that sheet encodes and decodes to itself (the walk-the-sheet
     guard: a new unserialisable type on the sheet fails here, naming its path,
     not on Alpha);
  2. freeze -> thaw gives a sheet equal to the fresh one, typed objects included;
  3. every desk's rendered sheet text and every Room desk prompt built from it
     are byte-identical between the fresh sheet and the thawed one.

Not driven here: the peer basket, EDGAR 8-K, debt-structure and filing-dimension
overlays. Each reduces its typed resolver result to plain str/int/float/list
before it touches the sheet (`_overlay_peer_comparison` etc.), so the sheet never
holds their types.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path as _FsPath

import pytest

from app.core.config import settings
from app.schemas import TWELVE_AGENT_IDS, AgentId
from app.services import (
    analyst_targets,
    buyback_price,
    edgar_filings_feed,
    edgar_pit,
    fundamentals,
    news_context,
    put_call,
    ratio_baselines,
    room_bank,
    room_runner,
    social_context,
    technicals,
)
from app.services.buyback_price import BuybackPrice
from app.services.cio_snapshot_codec import TAG, decode_profile, encode_profile
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import DividendPayment
from app.services.news_context import LiveDataState, LiveHeadline
from app.services.put_call import PutCallRatio
from app.services.ratio_baselines import RatioBaseline
from app.services.room_prompts import _format_profile, build_room_messages

_THIS_DIR = _FsPath(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import test_prompt_data_parity as P  # noqa: E402  (needs the path insert above)

_TICKER = P._TICKER


class _Provider(P._FakeEarningsProvider):
    def dividend_history(self, underlying):
        return [
            DividendPayment(date(y, m, 14), 0.20 + 0.01 * (y - 2018), "fake")
            for y in range(2018, 2026) for m in (2, 5, 8, 11)
        ]


_BUYBACK = BuybackPrice(
    avg_price=187.4, dollars=9.1e10, shares=4.86e8,
    period_start=date(2024, 10, 1), period_end=date(2025, 9, 30), quarters=4,
)


@pytest.fixture
def real_sheet(monkeypatch):
    """The production `_profile_for_ticker`, every fetch seam answering."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(settings, "suppress_analyst_consensus", False)
    monkeypatch.setattr(settings, "adanos_api_key", "x")
    for mod, name, fn in (
        (fundamentals, "fetch_live_fundamentals", lambda t: dict(P._FUND_SENTINEL)),
        (room_runner, "fetch_live_fundamentals", lambda t: dict(P._FUND_SENTINEL)),
        (technicals, "compute_technicals", lambda t: P._TECH_SENTINEL),
        (room_runner, "compute_technicals", lambda t: P._TECH_SENTINEL),
        (news_context, "fetch_live_news", lambda t, limit=3: [P._news_sentinel()]),
        (room_runner, "fetch_live_news", lambda t: [P._news_sentinel(), P._news_sentinel()]),
        (social_context, "fetch_live_sentiment", lambda t: P._SOCIAL_SENTINEL),
        (room_runner, "fetch_live_sentiment", lambda t: P._SOCIAL_SENTINEL),
        (fundamentals, "get_market_data_provider", lambda: _Provider()),
        (room_runner, "get_market_data_provider", lambda: _Provider()),
        (put_call, "fetch_put_call_ratio", lambda t: PutCallRatio(
            volume_ratio=0.81, oi_ratio=0.66, put_volume=1200, call_volume=1480,
            put_open_interest=9100, call_open_interest=13800, contracts=640,
            expiries=4, expiry_first=date(2026, 12, 4), expiry_last=date(2026, 12, 24),
            chain_date=date(2026, 11, 20),
        )),
        (buyback_price, "resolve_buyback_price", lambda facts, as_of: _BUYBACK),
        (edgar_pit, "load_facts", lambda *a, **k: {}),
        (edgar_filings_feed, "fetch_recent_filings", lambda t, a: ("live", [
            {"form": "10-Q", "label": "quarterly report", "filed_date": "2026-11-02"},
        ])),
        (analyst_targets, "fetch_analyst_detail", lambda t: {
            "analyst_rating_split": {
                "strong_buy": 9, "buy": 14, "hold": 8, "sell": 1, "strong_sell": 0,
            },
            "analyst_rating_split_history": [{
                "period": "-1m", "strong_buy": 8, "buy": 15, "hold": 8,
                "sell": 1, "strong_sell": 0,
            }],
            "analyst_tape": [{
                "date": "2026-11-10", "firm": "Fake & Co", "to_grade": "Buy",
                "from_grade": "Hold", "action": "up", "pt_action": "Raises",
                "current_pt": 300.0, "prior_pt": 280.0,
            }],
        }),
    ):
        monkeypatch.setattr(mod, name, fn)

    # Real baselines: the production reader builds the `RatioBaseline`s.
    today = datetime.now(timezone.utc).date()
    for i in range(1, 9):
        for metric, value in (
            (ratio_baselines.METRIC_PUT_CALL_VOLUME, 0.7 + 0.01 * i),
            (ratio_baselines.METRIC_PUT_CALL_OI, 0.6 + 0.01 * i),
            (ratio_baselines.METRIC_SENTIMENT_SCORE, 0.1 * i),
            (ratio_baselines.METRIC_MENTION_VOLUME, 50.0 + i),
        ):
            ratio_baselines.record_observation(
                _TICKER, metric, value, on=today - timedelta(days=i),
            )
    return room_runner._profile_for_ticker(_TICKER)


def _walk(value, path="profile"):
    yield path, value
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            yield from _walk(v, f"{path}[{i}]")


def test_the_fixture_is_the_real_shape(real_sheet):
    """Non-vacuity: the sheet carries the typed values production carries."""
    types_seen = {type(v) for _, v in _walk(real_sheet)}
    for needed in (RatioBaseline, PutCallRatio, LiveHeadline, BuybackPrice):
        assert needed in types_seen, f"fixture lost {needed.__name__}"
    assert any(type(v).__name__ == "DividendGrowth" for _, v in _walk(real_sheet))
    assert isinstance(real_sheet["put_call_volume_baseline"], RatioBaseline)
    assert isinstance(real_sheet["put_call_oi_baseline"], RatioBaseline)
    assert real_sheet["recent_filings_items"] and real_sheet["analyst_tape"]


def test_every_value_on_the_real_sheet_encodes_and_decodes_to_itself(real_sheet):
    encoded = encode_profile(real_sheet)
    assert decode_profile(encoded) == real_sheet


def test_freeze_then_thaw_renders_byte_identical_desk_prompts(real_sheet):
    d = date(2026, 11, 20)
    first = room_bank.freeze_fact_sheet(
        ticker=_TICKER, trading_date=d, variant="v", build=lambda: real_sheet,
    )
    assert first.sheet_hash is not None, "the real sheet must be freezable"

    def _no_rebuild():
        pytest.fail("the second convene must read the stored sheet")

    thawed = room_bank.freeze_fact_sheet(
        ticker=_TICKER, trading_date=d, variant="v", build=_no_rebuild,
    ).profile

    assert thawed == real_sheet
    assert _format_profile(thawed) == _format_profile(real_sheet)
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    for agent in AgentId:
        assert _format_profile(thawed, agent) == _format_profile(real_sheet, agent)
    for agent in TWELVE_AGENT_IDS:
        fresh = build_room_messages(
            agent_id=agent, mandate=mandate, ticker=_TICKER,
            profile=real_sheet, transcript=[],
        )
        assert fresh and build_room_messages(
            agent_id=agent, mandate=mandate, ticker=_TICKER,
            profile=thawed, transcript=[],
        ) == fresh


def test_the_stored_sheet_hash_is_stable_across_a_decode_encode_cycle(real_sheet):
    once = encode_profile(real_sheet)
    again = encode_profile(decode_profile(once))
    assert room_bank._canonical(once) == room_bank._canonical(again)


def test_codec_still_refuses_what_it_cannot_rebuild():
    class _Local:
        pass

    for bad in (_Local(), {1: "int key"}, object(), {_Local()}):
        with pytest.raises(TypeError):
            encode_profile({"x": bad})


def test_app_enums_sets_and_nested_namedtuples_round_trip():
    profile = {
        "state": LiveDataState.LIVE,
        "tags": frozenset({"b", "a"}),
        "open": {3, 1, 2},
        "base": RatioBaseline(0.7, 8, 60),
        "nested": [(RatioBaseline(0.1, 5, 60), date(2026, 1, 2))],
    }
    back = decode_profile(encode_profile(profile))
    assert back == profile
    assert type(back["state"]) is LiveDataState
    assert type(back["tags"]) is frozenset and type(back["open"]) is set


def test_a_stored_tag_cannot_name_a_class_outside_the_app():
    for tag in ("os:system", "builtins:dict", "app.services.cio_snapshot_codec:json"):
        with pytest.raises(ValueError):
            decode_profile({"x": {TAG: tag, "v": {}}})
