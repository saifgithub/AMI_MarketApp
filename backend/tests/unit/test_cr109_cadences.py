"""CR109 slice 6 — the other four cadences.

Saiful, playing the shipped build: *"How do I join the monthly, quarterly, etc
games?"* You couldn't: `_SUPPORTED_CADENCES` held one entry and
`CADENCE_GAIN_WEIGHT` held one row, so weekly was not the first cadence — it
was the only one, with the rest wired as no-ops.

All five are calendar-anchored. Everyone in a field starts on the same day,
which is the property §6.2 chose placement scoring for and the one thing
merging cohorts across start dates would destroy. Demand-gated ROLLING starts
for the long cadences are a different feature (slice 4) and need thin-field
thresholds set against a measured entry rate, which does not exist yet.

The two tests worth reading first are the ones that pin mistakes rather than
behaviour:

  * `test_every_cadence_benchmark_period_is_a_period_the_app_can_fetch` — the
    app's period vocabulary is `1d/1w/1m/3m/1y/2y/5y`, NOT yfinance's
    `1mo/3mo/6mo`. A string outside it makes `history()` return None, which
    the scoring pass turns into a benchmark TWR of 0.0 — so every quarterly,
    half and annual run would have been scored against a FLAT index and read
    as enormous alpha. Written after making exactly that mistake.
  * `test_the_stipend_period_key_is_the_cadence_own_period` — keying every
    cadence off ISO week would let a monthly run claim the finish stipend
    weekly, which is the farm the once-per-period guard exists to close.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.services import games_scoring as scoring
from app.services import games_service as games
from app.services.games_scoring_pass import _BENCHMARK_PERIOD_BY_CADENCE
from app.services.market_data import VALID_PERIODS

_ALL = games._SUPPORTED_CADENCES

# Sunday 23:00 ET, 2026-08-09 — every cadence has an entry-accepting field.
_NOW = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)


def test_all_five_cadences_are_supported():
    assert _ALL == ("week", "month", "quarter", "half", "year")


# ══ Period anchoring ════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "cadence,day,expected_start,expected_end",
    [
        ("week", date(2026, 8, 12), date(2026, 8, 10), date(2026, 8, 14)),
        ("month", date(2026, 8, 12), date(2026, 8, 1), date(2026, 8, 31)),
        ("quarter", date(2026, 8, 12), date(2026, 7, 1), date(2026, 9, 30)),
        ("half", date(2026, 8, 12), date(2026, 7, 1), date(2026, 12, 31)),
        ("year", date(2026, 8, 12), date(2026, 1, 1), date(2026, 12, 31)),
        # Boundaries — a day that IS a period start belongs to that period.
        ("quarter", date(2026, 10, 1), date(2026, 10, 1), date(2026, 12, 31)),
        ("half", date(2026, 1, 1), date(2026, 1, 1), date(2026, 6, 30)),
        ("month", date(2026, 2, 28), date(2026, 2, 1), date(2026, 2, 28)),
    ],
)
def test_period_boundaries(cadence, day, expected_start, expected_end):
    start = games.period_start(cadence, day)
    assert start == expected_start
    assert games.period_end(cadence, start) == expected_end


def test_a_weekly_run_ends_on_the_friday_not_the_sunday():
    """A run that "ends" on a day the market never opened has two dead days on
    the end of it."""
    start = games.period_start("week", date(2026, 8, 12))
    assert start.weekday() == 0
    assert games.period_end("week", start).weekday() == 4


@pytest.mark.parametrize("cadence", _ALL)
def test_periods_tile_without_gap_or_overlap(cadence):
    """One field's entry window opens the instant the previous one's closes.
    That invariant is what makes "exactly one entry-accepting field per
    cadence at any time" true, which `enter_field`'s one-live-run check
    relies on."""
    start = games.period_start(cadence, date(2026, 3, 15))
    for _ in range(6):
        nxt = games.next_period_start(cadence, start)
        assert games.period_end(cadence, start) < nxt
        assert games.previous_period_start(cadence, nxt) == start
        if cadence != "week":
            # Longer cadences tile the calendar exactly; weekly deliberately
            # leaves the weekend out of the run.
            assert games.period_end(cadence, start) == nxt - _ONE_DAY
        start = nxt


_ONE_DAY = date(2026, 1, 2) - date(2026, 1, 1)


@pytest.mark.parametrize("cadence", _ALL)
def test_a_field_exists_for_every_cadence(cadence):
    from app.db import get_session

    with get_session() as s:
        field = games.ensure_field(s, cadence, now=_NOW)
        assert field.cadence == cadence
        assert field.state in ("announced", "entry_open", "locked", "live")
        assert field.starts_on == games.period_start(cadence, field.starts_on)
        assert field.ends_on == games.period_end(cadence, field.starts_on)


@pytest.mark.parametrize("cadence", _ALL)
def test_ensure_field_is_idempotent(cadence):
    from app.db import get_session

    with get_session() as s:
        first = games.ensure_field(s, cadence, now=_NOW).id
        second = games.ensure_field(s, cadence, now=_NOW).id
    assert first == second


# ══ One live run per cadence — never two of a kind (§4.1) ═══════════════════


def test_a_player_may_hold_one_run_of_every_cadence():
    """Five books, one per cadence. §4.1 permits exactly this."""
    user_id = uuid4()
    runs = {c: games.enter_field(user_id, cadence=c, now=_NOW).run_id for c in _ALL}
    assert len(set(runs.values())) == len(_ALL)


@pytest.mark.parametrize("cadence", _ALL)
def test_but_never_two_of_a_kind(cadence):
    """The rule closes a farm, not a UI limit: career points pay +100 for a
    win and only -40 for a loss, so parallel entries in the SAME cadence are
    strictly +EV."""
    user_id = uuid4()
    games.enter_field(user_id, cadence=cadence, now=_NOW)
    with pytest.raises(games.AlreadyEnteredError):
        games.enter_field(user_id, cadence=cadence, now=_NOW)


def test_an_unknown_cadence_is_refused():
    with pytest.raises(games.UnsupportedCadenceError):
        games.enter_field(uuid4(), cadence="fortnight", now=_NOW)


def test_list_cadences_offers_all_five_with_per_cadence_held_flags():
    user_id = uuid4()
    games.enter_field(user_id, cadence="month", now=_NOW)

    rows = games.list_cadences(user_id, now=_NOW)
    assert [r["cadence"] for r in rows] == list(_ALL)
    held = {r["cadence"]: r["already_held"] for r in rows}
    assert held["month"] is True
    assert held["week"] is False
    assert held["year"] is False
    for row in rows:
        assert row["starts_on"] < row["ends_on"]
        assert row["entry_opens_at"] < row["locks_at"]


# ══ Scoring weights (§6.3) ══════════════════════════════════════════════════


def test_the_cadence_weights_match_the_design_table():
    assert scoring.CADENCE_GAIN_WEIGHT == {
        "week": 1.0, "month": 4.0, "quarter": 13.0, "half": 26.0, "year": 52.0,
    }
    assert scoring.CADENCE_LOSS_WEIGHT == {
        "week": 1.0, "month": 2.0, "quarter": 3.6, "half": 5.1, "year": 7.2,
    }


@pytest.mark.parametrize("cadence", _ALL)
def test_losses_scale_with_the_square_root_of_gains(cadence):
    """§6.3's asymmetry: a long BAD run is mostly market conditions, so a
    player is not crushed for having stayed invested through a bear half."""
    gain = scoring.cadence_weight(cadence, negative=False)
    loss = scoring.cadence_weight(cadence, negative=True)
    assert abs(loss - gain ** 0.5) < 0.06, (cadence, gain, loss)
    assert loss <= gain


def test_neither_cadence_is_a_farm():
    """§6.3's own balance check: winning the year is worth exactly what
    winning all 52 weeks is worth. If these diverge, one cadence becomes the
    rational-only play."""
    year = 100 * scoring.cadence_weight("year", negative=False)
    weeks = 100 * scoring.cadence_weight("week", negative=False) * 52
    assert year == weeks


@pytest.mark.parametrize("cadence", _ALL)
def test_the_stipend_scales_with_the_cadence(cadence):
    assert scoring.finish_stipend(cadence) == round(
        scoring.FINISH_STIPEND * scoring.CADENCE_GAIN_WEIGHT[cadence]
    )


def test_the_stipend_period_key_is_the_cadence_own_period():
    """Keying every cadence off ISO week would collapse twelve monthly periods
    a year into fifty-two keys — the stipend would be claimable weekly on a
    monthly run, which is the farm this guard closes."""
    jan = date(2026, 1, 5)
    feb = date(2026, 2, 2)
    mid_jan = date(2026, 1, 26)

    # Same month, different ISO weeks -> the SAME stipend period.
    assert (scoring.cadence_period_key("month", date(2026, 1, 1))
            == scoring.cadence_period_key("month", mid_jan))
    # Different months -> different periods.
    assert (scoring.cadence_period_key("month", jan)
            != scoring.cadence_period_key("month", feb))

    assert scoring.cadence_period_key("quarter", date(2026, 7, 1)) == "quarter:2026-Q3"
    assert scoring.cadence_period_key("half", date(2026, 7, 1)) == "half:2026-H2"
    assert scoring.cadence_period_key("half", date(2026, 1, 1)) == "half:2026-H1"
    assert scoring.cadence_period_key("year", date(2026, 6, 1)) == "year:2026"
    assert scoring.cadence_period_key("week", date(2026, 8, 10)).startswith("week:2026-W")


@pytest.mark.parametrize("cadence", _ALL)
def test_every_cadence_has_a_distinct_period_key_per_period(cadence):
    start = games.period_start(cadence, date(2026, 2, 10))
    keys = set()
    for _ in range(5):
        keys.add(scoring.cadence_period_key(cadence, start))
        start = games.next_period_start(cadence, start)
    assert len(keys) == 5


# ══ The benchmark window — the mistake this file was written for ════════════


def test_every_cadence_benchmark_period_is_a_period_the_app_can_fetch():
    """The app's period vocabulary is `1d/1w/1m/3m/1y/2y/5y`, NOT yfinance's
    `1mo/3mo/6mo`. `YfinanceProvider.history` returns None for anything
    outside it, and `_benchmark_twr_for_field` turns None into 0.0 — so a
    wrong string here does not raise, it silently scores every run of that
    cadence against a FLAT index. Written after making that exact mistake."""
    assert set(_BENCHMARK_PERIOD_BY_CADENCE) == set(_ALL)
    for cadence, period in _BENCHMARK_PERIOD_BY_CADENCE.items():
        assert period in VALID_PERIODS, (
            f"{cadence} asks for {period!r}, which history() cannot fetch — "
            f"the benchmark would silently read 0.0"
        )


def test_the_benchmark_window_contains_the_run():
    """A quarterly run scored against one week of SPY would read as enormous
    alpha or enormous failure, neither of which happened."""
    span_days = {"1d": 1, "1w": 7, "1m": 31, "3m": 93, "1y": 365, "2y": 730}
    for cadence, period in _BENCHMARK_PERIOD_BY_CADENCE.items():
        start = games.period_start(cadence, date(2026, 3, 15))
        run_days = (games.period_end(cadence, start) - start).days + 1
        assert span_days[period] >= run_days, (cadence, period, run_days)
