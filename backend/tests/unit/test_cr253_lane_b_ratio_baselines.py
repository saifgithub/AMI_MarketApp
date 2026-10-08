"""CR253 lane B(a) — rolling historical baselines for the emitted ratios.

"Put/call ratio 0.46" is unanswerable as a single point — high versus
what? This module persists one observation per (ticker, metric, calendar
day) on every successful live read (the read already happened for the
sheet; persisting it costs one upsert) and medians the trailing 90 days,
excluding today, so the put/call line and the social detail block can state
"vs trailing-90d baseline X (n daily reads on file)".

The rules pinned here:

**Never fabricated.** A day with no live read writes no row; fewer than
`_MIN_BASELINE_DAYS` distinct days on file renders "no baseline on file
yet", never an invented figure (CR040).

**Today is excluded from its own baseline** — a window containing the value
being judged is not a baseline.

**The median is computed in code** (CR179 Leg 4) — `statistics.median` here,
never the model's arithmetic.

**Store failures degrade loudly, never raise** — a lost baseline costs the
companion line, never the convene (the `_overlay_put_call` precedent).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.core.config import settings
from app.schemas.agents import AgentId
from app.services import put_call, ratio_baselines, room_prompts, room_runner
from app.services.market_data import OptionChain, OptionQuote
from app.services.put_call import aggregate_chains, put_call_line
from app.services.ratio_baselines import (
    RatioBaseline,
    comparison_clause,
    no_baseline_clause,
    record_observation,
    trailing_baseline,
)

_TODAY = date.today()
_METRIC = "put_call_volume"


def _seed(days: int, values: list[float] | None = None, *, metric: str = _METRIC,
           ticker: str = "TEST", end: date | None = None) -> None:
    """`days` observations on consecutive days ENDING at `end` (default
    yesterday), so the window is fully inside the trailing 90 days."""
    last = (end or (_TODAY - timedelta(days=1)))
    values = values or [0.5 + i * 0.1 for i in range(days)]
    for i in range(days):
        record_observation(
            ticker, metric, values[i],
            on=last - timedelta(days=days - 1 - i),
        )


class TestTheStore:
    def test_median_and_n_over_the_window(self):
        _seed(6, values=[0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
        base = trailing_baseline("TEST", _METRIC, today=_TODAY)
        assert base is not None
        assert base.median == 0.75  # median of 0.5..1.0
        assert base.n == 6
        assert base.window_days == 90

    def test_today_is_excluded_from_its_own_baseline(self):
        """The baseline exists to JUDGE today's read: today's observation
        must not move it."""
        _seed(5, values=[0.5, 0.5, 0.5, 0.5, 0.5])
        record_observation("TEST", _METRIC, 9.99, on=_TODAY)
        base = trailing_baseline("TEST", _METRIC, today=_TODAY)
        assert base is not None
        assert base.median == 0.5 and base.n == 5

    def test_fewer_than_five_days_is_no_baseline(self):
        _seed(4, values=[1.0, 2.0, 3.0, 4.0])
        assert trailing_baseline("TEST", _METRIC, today=_TODAY) is None

    def test_the_fifth_day_is_the_first_baseline(self):
        _seed(5, values=[0.4, 0.5, 0.6, 0.7, 0.8])
        base = trailing_baseline("TEST", _METRIC, today=_TODAY)
        assert base is not None and base.median == 0.6 and base.n == 5

    def test_the_window_is_ninety_calendar_days(self):
        """The 90-day boundary is pinned: a read 91 days ago is outside the
        trailing window, 90 days ago is inside it."""
        _seed(5, end=_TODAY - timedelta(days=86))  # days 90..86 ago: all inside
        base = trailing_baseline("TEST", _METRIC, today=_TODAY)
        assert base is not None and base.n == 5
        record_observation("TEST", _METRIC, 1.0, on=_TODAY - timedelta(days=91))
        base = trailing_baseline("TEST", _METRIC, today=_TODAY)
        assert base is not None and base.n == 5, "the 91-day-old read must stay outside"

    def test_a_second_read_the_same_day_replaces_not_duplicates(self):
        _seed(5)
        record_observation("TEST", _METRIC, 0.77, on=_TODAY - timedelta(days=1))
        record_observation("TEST", _METRIC, 0.88, on=_TODAY - timedelta(days=1))
        base = trailing_baseline("TEST", _METRIC, today=_TODAY)
        assert base is not None and base.n == 5, "one row per day, upserted"

    def test_metrics_are_namespaced(self):
        _seed(5, metric=_METRIC)
        assert trailing_baseline("TEST", "put_call_oi", today=_TODAY) is None

    def test_tickers_are_namespaced(self):
        _seed(5, ticker="TEST")
        assert trailing_baseline("OTHER", _METRIC, today=_TODAY) is None

    def test_a_bad_value_is_refused_not_stored(self):
        record_observation("TEST", _METRIC, float("nan"), on=_TODAY)
        record_observation("TEST", _METRIC, 0.5, on=_TODAY - timedelta(days=1))
        base = trailing_baseline("TEST", _METRIC, today=_TODAY)
        assert base is None, "one good read is below the floor; the NaN stored nothing"

    def test_store_failures_do_not_raise(self, monkeypatch):
        from app.db import session as db_session

        def _boom():
            raise RuntimeError("db gone")
        monkeypatch.setattr(db_session, "get_session", _boom)
        record_observation("TEST", _METRIC, 0.5, on=_TODAY)  # must not raise
        assert trailing_baseline("TEST", _METRIC, today=_TODAY) is None


class TestTheClauses:
    def test_comparison_clause_renders_the_baseline(self):
        clause = comparison_clause("sentiment score", 0.42, RatioBaseline(0.05, 9, 90))
        assert clause == (
            "sentiment score +0.42 vs trailing-90d median +0.05 "
            "(9 daily reads on file)"
        )

    def test_comparison_clause_unsigned_counts(self):
        clause = comparison_clause(
            "mention volume", 73561.0, RatioBaseline(60000.0, 9, 90),
            decimals=0, signed=False,
        )
        assert clause == (
            "mention volume 73561 vs trailing-90d median 60000 (9 daily reads on file)"
        )

    def test_no_baseline_is_none_for_the_caller_to_state(self):
        assert comparison_clause("sentiment score", 0.42, None) is None
        absence = no_baseline_clause()
        assert "no baseline on file yet" in absence
        assert "trailing 90 days" in absence


# ── The put/call line's companion ────────────────────────────────────────────


def _quote(volume, oi):
    return OptionQuote(
        strike=100.0, bid=1.0, ask=1.2, last=1.1,
        volume=volume, open_interest=oi, implied_vol=0.3,
    )


def _ratio(volume_ratio=0.8, oi_ratio=1.1):
    chains = [
        OptionChain(
            underlying="TEST", expiry=_TODAY + timedelta(days=7),
            calls=(_quote(400, 4000),), puts=(_quote(int(400 * volume_ratio), int(4000 * oi_ratio)),),
            source="yfinance",
        ),
    ]
    # Single chain: put volume 400*vr, call 400 → vr; OI 4000*oir / 4000 → oir.
    return aggregate_chains(chains, _TODAY)


def test_the_line_gains_the_trailing_baseline() -> None:
    line = put_call_line(
        _ratio(),
        volume_baseline=RatioBaseline(0.85, 12, 90),
        oi_baseline=RatioBaseline(1.02, 12, 90),
    )
    assert "volume 0.80" in line
    assert "trailing-90d baseline 0.85 (12 daily reads on file)" in line
    assert "open interest 1.10" in line
    assert "trailing-90d baseline 1.02 (12 daily reads on file)" in line


def test_no_baseline_states_the_absence_per_half() -> None:
    line = put_call_line(_ratio())
    assert line is not None
    assert line.count("no baseline on file yet") == 2, "each served half states it"


def test_an_unserved_half_has_no_companion() -> None:
    chains = [
        OptionChain(
            underlying="TEST", expiry=_TODAY + timedelta(days=7),
            calls=(_quote(None, 4000),), puts=(_quote(None, 4400),),
            source="yfinance",
        ),
    ]
    line = put_call_line(
        aggregate_chains(chains, _TODAY),
        oi_baseline=RatioBaseline(1.02, 12, 90),
    )
    assert "volume not served by the provider" in line
    assert "trailing-90d baseline 1.02" in line
    assert "no baseline on file yet" not in line


# ── The overlay: record on read, baseline onto the profile ──────────────────


class _Provider:
    def expiries(self, ticker):
        return [_TODAY + timedelta(days=7)]

    def option_chain(self, ticker, expiry):
        return OptionChain(
            underlying=ticker, expiry=expiry,
            calls=(_quote(400, 4000),), puts=(_quote(320, 4400),),
            source="yfinance",
        )


def test_the_overlay_records_and_carries_the_baseline(monkeypatch) -> None:
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(put_call, "get_market_data_provider", lambda: _Provider())
    _seed(5, values=[0.7, 0.75, 0.8, 0.85, 0.9])
    profile: dict = {"field_state": {}, "sentiment_tone": "mixed", "sentiment_score": "+0.10"}
    fs = profile["field_state"]
    room_runner._overlay_put_call(profile, fs, "TEST", None)
    assert fs["put_call"] == "live"
    base = profile.get("put_call_volume_baseline")
    assert base is not None and base.median == 0.8 and base.n == 5

    sheet = room_prompts._format_profile(profile, AgentId.SOCIAL_MEDIA_ANALYST)
    assert "trailing-90d baseline 0.80 (5 daily reads on file)" in sheet


def test_the_overlay_writes_todays_read_for_the_next_baseline(monkeypatch) -> None:
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(put_call, "get_market_data_provider", lambda: _Provider())
    _seed(4)
    profile: dict = {}
    field_state: dict[str, str] = {}
    room_runner._overlay_put_call(profile, field_state, "TEST", None)
    # Only 4 prior days: no baseline yet…
    assert profile["put_call_volume_baseline"] is None
    # …but today's read is on file, so it counts toward the next window.
    base = trailing_baseline("TEST", _METRIC, today=_TODAY + timedelta(days=1))
    assert base is not None and base.n == 5


def test_a_mock_run_never_touches_the_store(monkeypatch) -> None:
    monkeypatch.setattr(settings, "use_real_market_data", False)
    profile: dict = {}
    field_state: dict[str, str] = {}
    room_runner._overlay_put_call(profile, field_state, "TEST", None)
    assert field_state["put_call"] == "unavailable"
    assert trailing_baseline("TEST", _METRIC, today=_TODAY) is None


# ── The social detail block ──────────────────────────────────────────────────


def _social_profile(**over) -> dict:
    profile = {
        "field_state": {"social": "live"},
        "sentiment_tone": "moderately bullish",
        "sentiment_score": "+0.42 (live Reddit sentiment, Adanos)",
        "mention_trend": "73,561 Reddit mentions over 7d, trend: rising",
    }
    profile.update(over)
    return profile


def test_the_social_block_renders_the_baselines_line() -> None:
    profile = _social_profile(
        social_baselines=(
            "sentiment score +0.42 vs trailing-90d median +0.05 (9 daily reads on file); "
            "mention volume 73561 vs trailing-90d median 60000 (9 daily reads on file)"
        ),
    )
    sheet = room_prompts._format_profile(profile, AgentId.SOCIAL_MEDIA_ANALYST)
    assert "Baselines: sentiment score +0.42 vs trailing-90d median +0.05" in sheet
    assert "mention volume 73561 vs trailing-90d median 60000" in sheet


def test_the_social_block_states_the_absence() -> None:
    profile = _social_profile(
        social_baselines="no baseline on file yet — fewer than 5 daily reads",
    )
    sheet = room_prompts._format_profile(profile, AgentId.SOCIAL_MEDIA_ANALYST)
    assert "no baseline on file yet" in sheet


def test_no_key_no_line() -> None:
    sheet = room_prompts._format_profile(_social_profile(), AgentId.SOCIAL_MEDIA_ANALYST)
    assert "Baselines:" not in sheet
