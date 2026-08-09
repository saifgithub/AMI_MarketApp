"""CR109 slice 1 — `trading_math/twr.py`: chain-linked time-weighted return.

The one test that matters here is the capital-event split: a naive whole-
period return reads a real loss followed by a fresh stake as flat (or even
positive), because it only compares the first and last NAV. TWR must not.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.trading_math.twr import (
    NavPoint,
    alpha_vs_benchmark,
    sub_period_returns,
    time_weighted_return,
)

_START = date(2026, 1, 5)


def _navs(values: list[float], events: list[str | None]) -> list[NavPoint]:
    assert len(values) == len(events)
    return [
        NavPoint(as_of=_START + timedelta(days=i), nav=v, capital_event=e)
        for i, (v, e) in enumerate(zip(values, events))
    ]


def test_time_weighted_return_is_none_below_two_points() -> None:
    assert time_weighted_return([]) is None
    assert time_weighted_return(_navs([10_000.0], ["open"])) is None


def test_time_weighted_return_matches_naive_when_no_capital_event() -> None:
    navs = _navs(
        [10_000.0, 11_000.0, 12_000.0],
        ["open", None, None],
    )
    twr = time_weighted_return(navs)
    assert twr == pytest.approx(0.20)
    assert sub_period_returns(navs) == [pytest.approx(0.20)]


def test_twr_chain_links_across_a_capital_event_a_loss_does_not_read_as_flat() -> None:
    """The plan's own acceptance scenario, made numerically unambiguous: a
    naive (end/start - 1) whole-period return is exactly 0% here — flat —
    while the real experience was a 40% loss followed by an unchanged fresh
    stake. TWR must report the loss, not the flat naive number."""
    navs = _navs(
        [10_000.0, 6_000.0, 10_000.0, 10_000.0],
        ["open", None, "restart", None],
    )

    naive_whole_period = navs[-1].nav / navs[0].nav - 1.0
    assert naive_whole_period == pytest.approx(0.0), "fixture must read flat naively"

    returns = sub_period_returns(navs)
    assert returns == [pytest.approx(-0.40), pytest.approx(0.0)]

    twr = time_weighted_return(navs)
    assert twr == pytest.approx(-0.40)
    assert twr != pytest.approx(naive_whole_period)


def test_twr_chain_links_across_a_capital_event_with_gains_on_both_sides() -> None:
    """A second numeric case: a -40% run, a fresh $10k stake, then +10% on
    the new stake. Naive whole-period reads +10% (masks the drawdown
    entirely); TWR compounds both legs: 0.6 * 1.1 - 1 = -0.34."""
    navs = _navs(
        [10_000.0, 6_000.0, 10_000.0, 11_000.0],
        ["open", None, "restart", None],
    )
    twr = time_weighted_return(navs)
    assert twr == pytest.approx(-0.34)


def test_sub_period_returns_skips_a_baseline_only_period() -> None:
    """Two capital events back to back leave a sub-period with no second
    observation — it contributes nothing, not a spurious 0%."""
    navs = _navs(
        [10_000.0, 10_000.0, 12_000.0],
        ["open", "restart", None],
    )
    returns = sub_period_returns(navs)
    assert returns == [pytest.approx(0.20)]


def test_alpha_vs_benchmark_is_excess_return() -> None:
    assert alpha_vs_benchmark(0.08, 0.05) == pytest.approx(0.03)
    assert alpha_vs_benchmark(-0.02, 0.05) == pytest.approx(-0.07)
