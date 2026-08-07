"""DEF227/228/229 — the three input defects behind the Market Analyst's
structural bearishness.

DEF227: `compute_technicals` worked out whether a stock was trending up or
down and then discarded the answer, so `Trend:` had two reachable values and
neither carried direction — a stock at its 50-day high and one pinned to its
52-week low rendered byte-identically.

DEF228: the technicals block stated support and breakout but never the current
price, so position-in-range had to be inferred. On live Alpha (run
`8da2d287`, GRAB, 2026-08-07) the agent inferred it wrong — asserted a
breakdown at $3.67 with the floor at $3.18 — and all twelve agents adopted it.

DEF229: (a) the provider chain ends in a synthetic random walk, so a yfinance
outage substituted fabricated OHLCV into a block asserting "Real yfinance
OHLCV"; (b) the 50-day high was labelled "breakout level", which names a level
as a trade trigger and makes the only long entry sit above the 50-day high by
definition.
"""

from __future__ import annotations

from app.core.config import settings
from app.services import technicals
from app.services.market_data import (
    Candle,
    CachingProvider,
    FallbackProvider,
    MockWalkProvider,
    history_with_source,
)
from app.services.room_prompts import build_room_messages
from app.services.technicals import compute_technicals, range_position_pct
from app.schemas import AgentId

_BASE_T = 1_800_000_000


def _candles(closes, highs=None, lows=None, volumes=None) -> list[Candle]:
    n = len(closes)
    highs = highs if highs is not None else [c + 1 for c in closes]
    lows = lows if lows is not None else [c - 1 for c in closes]
    volumes = volumes if volumes is not None else [1_000_000] * n
    return [
        Candle(t=_BASE_T + i * 86400, o=closes[i], h=highs[i], low=lows[i], c=closes[i], v=volumes[i])
        for i in range(n)
    ]


class _FakeProvider:
    """A named real feed — deliberately NOT one of the synthetic sources."""

    name = "yfinance"

    def __init__(self, candles):
        self._candles = candles

    def history(self, ticker, period):
        return self._candles


def _patch_feed(monkeypatch, candles):
    monkeypatch.setattr(
        technicals, "get_market_data_provider", lambda: _FakeProvider(candles)
    )


# ── DEF227 — the trend field must be able to say "up" ────────────────────


def test_rising_and_falling_series_produce_different_trend_strings(monkeypatch):
    """The guard DEF227 asks for by name. Before the fix both of these read
    "trading" — the field could not distinguish them, which is the whole
    defect. This assertion is what fails if the direction is ever discarded
    again, regardless of what the two values happen to be called."""
    rising = [100.0 + i * 0.5 for i in range(65)]
    falling = [100.0 - i * 0.5 for i in range(65)]

    _patch_feed(monkeypatch, _candles(rising))
    up = compute_technicals("AAPL")
    _patch_feed(monkeypatch, _candles(falling))
    down = compute_technicals("AAPL")

    assert up is not None and down is not None
    assert up.trend != down.trend


def test_trend_reads_uptrend_when_price_above_both_averages(monkeypatch):
    _patch_feed(monkeypatch, _candles([100.0 + i * 0.5 for i in range(65)]))
    t = compute_technicals("AAPL")
    assert t is not None
    assert t.trend == "uptrend"


def test_trend_reads_downtrend_when_price_below_both_averages(monkeypatch):
    _patch_feed(monkeypatch, _candles([200.0 - i * 0.5 for i in range(65)]))
    t = compute_technicals("AAPL")
    assert t is not None
    assert t.trend == "downtrend"


def test_trend_reads_consolidating_when_unaligned(monkeypatch):
    _patch_feed(monkeypatch, _candles([100.0 if i % 2 == 0 else 100.5 for i in range(65)]))
    t = compute_technicals("AAPL")
    assert t is not None
    assert t.trend == "consolidating"


def test_no_trend_value_is_the_direction_blind_token(monkeypatch):
    """"trading" was not a trend read in English — it was a null token under a
    label promising one. It must not be reachable from any series."""
    for closes in (
        [100.0 + i * 0.5 for i in range(65)],
        [200.0 - i * 0.5 for i in range(65)],
        [100.0 if i % 2 == 0 else 100.5 for i in range(65)],
    ):
        _patch_feed(monkeypatch, _candles(closes))
        t = compute_technicals("AAPL")
        assert t is not None
        assert t.trend != "trading"


# ── DEF228 — position in range is stated, never inferred ─────────────────


def test_range_position_pct_is_plain_arithmetic():
    assert range_position_pct(3.67, 3.18, 4.06) == 56
    assert range_position_pct(3.18, 3.18, 4.06) == 0
    assert range_position_pct(4.06, 3.18, 4.06) == 100


def test_range_position_pct_none_when_range_has_no_width():
    assert range_position_pct(5.0, 5.0, 5.0) is None


def test_one_on_one_block_states_the_last_close_and_its_position(monkeypatch):
    """The live GRAB shape from run 8da2d287: floor $3.18, high $4.06, last
    close $3.67 — inside the range, lower-middle. The agent called it a
    breakdown below the floor. The block now says where price sits."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    closes = [3.67] * 65
    lows = [3.50] * 64 + [3.18]
    highs = [3.90] * 64 + [4.06]
    _patch_feed(monkeypatch, _candles(closes, highs=highs, lows=lows))

    block = technicals.build_technicals_context_block("GRAB")
    assert block is not None
    assert "last close $3.67" in block
    assert "56% of that range" in block


def test_one_on_one_block_omits_position_when_range_is_flat(monkeypatch):
    """A percentage of a zero-width range is not a fact. Degrade to the range
    alone rather than printing a made-up position (CR040)."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    closes = [50.0] * 65
    _patch_feed(monkeypatch, _candles(closes, highs=[50.0] * 65, lows=[50.0] * 65))

    block = technicals.build_technicals_context_block("FLAT")
    assert block is not None
    assert "of that range" not in block


def test_room_fact_sheet_states_the_last_close_and_its_position(base_mandate):
    """The Room path carries a Reference price line, but it is a separately-
    sourced quote several lines up — the join the agent got wrong."""
    profile = {
        "support": 3.18,
        "breakout": 4.06,
        "last_close": 3.67,
        "field_state": {"technicals": "live"},
    }
    sp, _ = build_room_messages(
        agent_id=AgentId.MARKET_ANALYST, mandate=base_mandate, user_id=None,
        ticker="GRAB", profile=profile, transcript=[],
    )
    assert "50-day range: $3.18–$4.06, last close $3.67 (56% of that range)" in sp


def test_room_fact_sheet_falls_back_to_the_bare_range_without_a_last_close(base_mandate):
    profile = {
        "support": 3.18,
        "breakout": 4.06,
        "field_state": {"technicals": "live"},
    }
    sp, _ = build_room_messages(
        agent_id=AgentId.MARKET_ANALYST, mandate=base_mandate, user_id=None,
        ticker="GRAB", profile=profile, transcript=[],
    )
    assert "50-day range: $3.18–$4.06" in sp
    assert "of that range" not in sp


# ── DEF229(a) — a synthetic series never renders as a real one ───────────


def test_history_with_source_reports_the_leaf_that_served_the_bars():
    """`Quote.source` has always carried its leaf. History now does too —
    otherwise the mock walk is indistinguishable from yfinance."""
    chain = FallbackProvider(
        primary=CachingProvider(_FakeProvider(None), ttl_seconds=60.0),
        secondary=MockWalkProvider(),
    )
    bars, source = history_with_source(chain, "AAPL", "3m")
    assert bars  # the walk never fails, which is exactly the problem
    assert source == "mock_walk"


def test_history_with_source_reports_the_real_leaf_not_the_cache_wrapper():
    """A stack name ("cache(yfinance)") is not a leaf. The wrapper must not
    be what a provenance check reads."""
    chain = FallbackProvider(
        primary=CachingProvider(_FakeProvider(_candles([100.0] * 65)), ttl_seconds=60.0),
        secondary=MockWalkProvider(),
    )
    bars, source = history_with_source(chain, "AAPL", "3m")
    assert bars is not None
    assert source == "yfinance"


def test_compute_technicals_refuses_a_synthetic_series(monkeypatch):
    """The block this feeds asserts "Real yfinance OHLCV" in its own text. A
    mock walk arrives AS a successful history call, so the block would still
    render, still claim liveness, and still carry the (LIVE) treatment."""
    monkeypatch.setattr(
        technicals,
        "get_market_data_provider",
        lambda: FallbackProvider(
            primary=CachingProvider(_FakeProvider(None), ttl_seconds=60.0),
            secondary=MockWalkProvider(),
        ),
    )
    assert compute_technicals("AAPL") is None


def test_synthetic_refusal_is_logged_not_silent(monkeypatch):
    """CR040 degrade-loudly: the feed going synthetic must leave a trace, or
    the fact sheet just quietly says "not available" forever."""
    seen: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        technicals.logger, "warn", lambda event, **kw: seen.append((event, kw))
    )
    monkeypatch.setattr(
        technicals,
        "get_market_data_provider",
        lambda: FallbackProvider(
            primary=CachingProvider(_FakeProvider(None), ttl_seconds=60.0),
            secondary=MockWalkProvider(),
        ),
    )
    compute_technicals("AAPL")

    assert [e for e, _ in seen] == ["technicals_synthetic_feed_rejected"]
    assert seen[0][1]["source"] == "mock_walk"


def test_one_on_one_block_absent_when_the_feed_is_synthetic(monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(
        technicals,
        "get_market_data_provider",
        lambda: FallbackProvider(
            primary=CachingProvider(_FakeProvider(None), ttl_seconds=60.0),
            secondary=MockWalkProvider(),
        ),
    )
    assert technicals.build_technicals_context_block("AAPL") is None


# ── DEF229(b) — a level is named as a level, not as a trigger ────────────


def test_one_on_one_block_does_not_ship_a_trade_trigger_as_a_data_label(monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", True)
    _patch_feed(monkeypatch, _candles([100.0 + i * 0.5 for i in range(65)]))

    block = technicals.build_technicals_context_block("AAPL")
    assert block is not None
    assert "breakout level" not in block
    assert "50-day range" in block


def test_room_fact_sheet_does_not_ship_a_trade_trigger_as_a_data_label(base_mandate):
    profile = {
        "support": 90.0, "breakout": 110.0, "last_close": 105.0,
        "rsi": 55, "rsi_tone": "neither overbought nor oversold",
        "trend": "uptrend", "volume_tone": "above 20-day average",
        "field_state": {"technicals": "live"},
    }
    sp, _ = build_room_messages(
        agent_id=AgentId.MARKET_ANALYST, mandate=base_mandate, user_id=None,
        ticker="AAPL", profile=profile, transcript=[],
    )
    # The Market Analyst's own role prompt legitimately discusses breakouts as
    # a concept; what must not survive is the *data label* that named the
    # 50-day high as one.
    assert "breakout level" not in sp.lower()
    assert "50-day range: $90.0–$110.0" in sp
    assert "trend: uptrend" in sp.lower()
