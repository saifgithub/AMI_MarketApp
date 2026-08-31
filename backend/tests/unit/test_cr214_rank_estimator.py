"""CR214 — the rank estimator that lets every convene count.

The bucket tests in `backtest_report.py` park ~90% of a sweep in PASS, where a
binary verdict expresses no ordering: CR164 Phase B scored 40 APPROVEs over 18
as-of dates, i.e. 1-4 signal names per date against a measured 13.0% per-name
4-week excess-return SD. `Verdict.approve_votes` is 0..N over the independent
CIO draws, so a per-date rank correlation rests on the whole cross-section
instead.

What is pinned here is the arithmetic and, more importantly, the REFUSALS. An
IC that quietly returned 0.0 for a date expressing no ranking would dilute the
average toward a null the data never asserted — the CR040 failure mode applied
to a statistic.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.backtest_report import H_LONG, _avg_ranks, graded_score, spearman


# ── ranks ────────────────────────────────────────────────────────────────────


def test_ranks_are_one_based_and_ordered():
    assert _avg_ranks([10.0, 20.0, 30.0]) == [1.0, 2.0, 3.0]


def test_ties_take_the_average_rank():
    """Ties are the NORMAL case: `approve_votes` takes at most N+1 distinct
    values over ~100 names, so a rank that broke on ties would be unusable."""
    assert _avg_ranks([5.0, 5.0, 9.0]) == [1.5, 1.5, 3.0]
    assert _avg_ranks([1.0, 1.0, 1.0, 1.0]) == [2.5] * 4


def test_rank_is_position_independent():
    assert _avg_ranks([30.0, 10.0, 20.0]) == [3.0, 1.0, 2.0]


# ── spearman ─────────────────────────────────────────────────────────────────


def test_perfect_monotone_agreement_is_one():
    assert spearman([1.0, 2.0, 3.0, 4.0], [10.0, 20.0, 30.0, 40.0]) == pytest.approx(1.0)


def test_perfect_inversion_is_minus_one():
    assert spearman([1.0, 2.0, 3.0, 4.0], [40.0, 30.0, 20.0, 10.0]) == pytest.approx(-1.0)


def test_it_ranks_rather_than_correlating_levels():
    """The point of a RANK statistic: one wild outlier must not carry the
    result. A 4-week single-name excess return of +50% is a real occurrence in
    this data (CR164 Phase B's RSI was +51.4% and carried 45% of that batch's
    P&L), which is exactly why the primary metric is rank-based."""
    assert spearman([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 5000.0]) == pytest.approx(1.0)


def test_ties_on_one_side_do_not_break_it():
    ic = spearman([0.0, 0.0, 1.0, 1.0], [1.0, 2.0, 3.0, 4.0])
    assert ic is not None and 0.0 < ic < 1.0


# ── the refusals, which are the load-bearing half ────────────────────────────


def test_no_dispersion_in_votes_is_undefined_not_zero():
    """A date where every run scored the same vote count expresses NO ranking.
    Returning 0.0 would fold a non-observation into the average as evidence
    for the null."""
    assert spearman([3.0, 3.0, 3.0, 3.0], [1.0, 2.0, 3.0, 4.0]) is None


def test_no_dispersion_in_returns_is_undefined_not_zero():
    assert spearman([1.0, 2.0, 3.0, 4.0], [7.0, 7.0, 7.0, 7.0]) is None


def test_two_points_are_refused():
    """A 2-point rank correlation is always exactly +/-1 and carries no
    information; averaging such dates in would manufacture signal."""
    assert spearman([1.0, 2.0], [5.0, 9.0]) is None
    assert spearman([1.0], [5.0]) is None


def test_length_mismatch_raises_rather_than_truncating():
    """Silently zipping to the shorter list would score returns against the
    wrong runs and still print a confident number."""
    with pytest.raises(ValueError):
        spearman([1.0, 2.0, 3.0], [1.0, 2.0])


def test_a_defined_ic_is_finite():
    ic = spearman([0.0, 1.0, 2.0, 3.0, 4.0], [-0.05, 0.01, 0.0, 0.03, 0.10])
    assert ic is not None and math.isfinite(ic) and -1.0 <= ic <= 1.0


# ── the long horizon ─────────────────────────────────────────────────────────


def test_the_long_horizon_is_about_ninety_calendar_days():
    """Phase B's own closing caveat: stated horizons have a median of 90
    CALENDAR days while scoring stopped at 20 TRADING days, so its four-week
    numbers grade name selection rather than the theses. 62 trading rows is
    ~90 calendar days at 4.83 rows/week."""
    assert H_LONG == 62
    assert 85 <= H_LONG * 7 / 4.83 <= 95


# --- DEF388: the graded score is a fraction, not a vote count ---------------
#
# `samples` is what the provider actually returned, not what was configured.
# The very first convenes of the CR214 sweep came back 1-of-1 and 3-of-5 in the
# same batch, so the two scales coexist in real data.


class _Row:
    def __init__(self, approve_votes, samples):
        self.approve_votes = approve_votes
        self.samples = samples


def test_score_is_the_approval_fraction():
    assert graded_score(_Row(3, 5)) == pytest.approx(0.6)
    assert graded_score(_Row(5, 5)) == pytest.approx(1.0)
    assert graded_score(_Row(0, 5)) == pytest.approx(0.0)


def test_a_unanimous_short_sample_outranks_a_split_full_sample():
    """1-of-1 is a stronger approval than 3-of-5 and must rank above it.

    On the raw count the order inverts (1 < 3), which is the whole defect.
    """
    assert graded_score(_Row(1, 1)) > graded_score(_Row(3, 5))


def test_missing_denominator_is_none_not_zero():
    assert graded_score(_Row(0, None)) is None
    assert graded_score(_Row(3, 0)) is None
    assert graded_score(_Row(None, 5)) is None


def test_the_defect_would_have_reordered_the_cross_section():
    """Same date, same returns: counts and fractions give opposite ICs."""
    rows = [_Row(1, 1), _Row(2, 5), _Row(3, 5)]
    returns = [0.10, -0.05, 0.02]
    counts = [float(r.approve_votes) for r in rows]
    fractions = [graded_score(r) for r in rows]
    assert spearman(counts, returns) == pytest.approx(-0.5)
    assert spearman(fractions, returns) == pytest.approx(1.0)
