"""DEF302 — a supplied percentage must not be readable as describing something
other than the pair it was measured from.

Three misattributions in the 39-convene 2026-08-14 corpus, each quoting a
CORRECT figure against the wrong referent. These guards assert the two render
sites that supplied the travelling figures, and they assert values and
relationships rather than the presence of a label — a test that only checks the
words are there passes on a line whose arithmetic is inverted, which is the
failure it exists to catch.

Note what is NOT tested here, because it is not testable at this layer: whether
the model stops misattributing. That is Leg 5's re-measure. P2 — this is a
rendering change, so the honest claim is that the ambiguity is gone from the
input, not that the output is fixed.
"""

from __future__ import annotations

import pytest

from app.services.fundamentals import primary_trend_line


def _part(line: str) -> str:
    return line or ""


class TestPrimaryTrendStatesBothEnds:
    """The MU case: 'price 70.6% above it' was restated as 'the average is
    70.6% below the price'. Both readings are now supplied, so neither has to
    be derived."""

    def test_the_inverse_is_not_the_same_magnitude(self) -> None:
        # 1528.11 / 895.91 = +70.6% above; the average is 41.4% below the price.
        line = _part(primary_trend_line(895.91, 70.6))
        assert "70.6% above it" in line
        assert "41.4% below the price" in line
        # The exact number the corpus turn got wrong must NOT appear as a
        # "below" figure anywhere on the line.
        assert "70.6% below" not in line

    def test_below_case_inverts_the_other_way(self) -> None:
        # TSLA: price 16.4% BELOW the 200-day average of $406.63 →
        # the average sits 19.6% ABOVE the price.
        line = _part(primary_trend_line(406.63, -16.4))
        assert "16.4% below it" in line
        assert "19.6% above the price" in line

    def test_the_two_figures_round_trip(self) -> None:
        """The inverse of the inverse is the original — the property that makes
        the second figure a fact rather than a restatement."""
        for distance in (70.6, -16.4, 5.0, -40.0, 200.0):
            inverse = (100.0 / (1.0 + distance / 100.0)) - 100.0
            back = (100.0 / (1.0 + inverse / 100.0)) - 100.0
            assert back == pytest.approx(distance, abs=1e-6)

    def test_zero_distance_states_zero_both_ways(self) -> None:
        line = _part(primary_trend_line(100.0, 0.0))
        assert "0.0% above the price" in line or "0.0% below the price" in line

    def test_a_missing_distance_adds_no_inverse(self) -> None:
        """DEF053 / CR040 — absent beats invented. No distance means no
        second figure, not a zero."""
        line = _part(primary_trend_line(548.84, None))
        assert "548.84" in line
        assert "equivalently" not in line

    def test_a_total_loss_distance_does_not_divide_by_zero(self) -> None:
        """-100% would put the denominator at zero. It must degrade to the
        single reading rather than raise inside prompt assembly."""
        line = _part(primary_trend_line(10.0, -100.0))
        assert "100.0% below it" in line
        assert "equivalently" not in line

    def test_no_sma_renders_nothing(self) -> None:
        assert primary_trend_line(None, 12.0) is None


class TestStopDistanceIsBoundToItsOwnPair:
    """The SNOA case: '→ stop 6.0% below entry →' was reattached to the
    Conservative's own $1.03 level, 23.1% away."""

    def _line(self, **kw):
        from app.services.room_prompts import _drawdown_snapshot_line
        from app.schemas.mandate import Mandate  # noqa: F401  (shape only)

        return _drawdown_snapshot_line(**kw)

    def test_the_percentage_names_the_pair_on_the_same_clause(self) -> None:
        from app.services.room_prompts import _drawdown_snapshot_line

        class _M:
            max_drawdown_pct = 30.0

        line = _drawdown_snapshot_line(
            _M(),
            {"size_pct": 3.0, "entry": 203.62, "stop": 191.40},
            agent_size_pct=None,
            current_drawdown_pct=None,
        )
        assert "below THAT entry" in line
        # the pair itself, on the same clause as the percentage
        assert "191.40 from 203.62" in line
        assert "this percentage describes that pair only" in line
        # the bare form that travelled is gone
        assert "% below entry →" not in line

    def test_the_stop_distance_is_still_correct(self) -> None:
        """Binding the referent must not change the arithmetic."""
        from app.services.room_prompts import _drawdown_snapshot_line

        class _M:
            max_drawdown_pct = 30.0

        line = _drawdown_snapshot_line(
            _M(),
            {"size_pct": 3.0, "entry": 203.62, "stop": 191.40},
            agent_size_pct=None,
            current_drawdown_pct=None,
        )
        # 191.40 / 203.62 - 1 = -6.0%
        assert "6.0% below THAT entry" in line

    def test_no_proposal_renders_no_reference_line(self) -> None:
        from app.services.room_prompts import _drawdown_snapshot_line

        class _M:
            max_drawdown_pct = 30.0

        line = _drawdown_snapshot_line(
            _M(), None, agent_size_pct=None, current_drawdown_pct=None
        )
        assert "Reference position" not in line
        assert "max_drawdown_pct" in line
