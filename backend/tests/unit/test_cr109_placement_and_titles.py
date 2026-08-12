"""CR109 slice 4 — the placement curve, the title ladder, the forfeit floor.

Pure arithmetic only; the scoring pass that routes onto this path is tested
separately. Every number asserted here is taken from CR109.md's own tables
(§6.2's rank-of-30 row, §6.3's balance check, §6.4's ladder) rather than from
the implementation — a test that recomputes what the code computes proves the
code is self-consistent, which is not the property that matters for a formula
that writes permanent Records.
"""

from __future__ import annotations

import pytest

from app.services.games_scoring import (
    MIN_FORFEIT_DEBIT,
    PLACEMENT_MIN_FIELD,
    TITLE_MIN_FIELD,
    TITLE_MULTIPLIER,
    cadence_weight,
    forfeit_debit,
    placement_p,
    placement_to_points,
    title_for,
    title_multiplier,
)


def _base(rank: int, n: int = 30) -> float:
    return placement_to_points(placement_p(rank, n))


# ── §6.2's table, verbatim ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "rank,expected",
    [(1, 100), (3, 80), (6, 53), (10, 23), (20, -12), (25, -26), (30, -40)],
)
def test_the_rank_of_30_table_from_the_design(rank, expected):
    assert round(_base(rank)) == expected


def test_rank_fifteen_of_thirty_is_the_tables_tilde_zero():
    # The design's own cell reads "~0", not 0 — rank 15 of 30 sits just
    # above the midpoint, so the exact value is +0.64. Asserting a rounded 0
    # here would be asserting something the spec never claimed.
    assert _base(15) == pytest.approx(0.64, abs=0.01)


def test_first_pays_exactly_the_ceiling_and_last_exactly_the_floor():
    assert _base(1) == pytest.approx(100.0)
    assert _base(30) == pytest.approx(-40.0)


def test_winning_is_worth_two_and_a_half_times_what_losing_costs():
    # The asymmetry is the design's, and it lives in the CURVE — not in a
    # multiplier applied afterwards. If someone re-derives the shape, this
    # is the property that must survive.
    assert _base(1) == pytest.approx(abs(_base(30)) * 2.5)


def test_the_middle_of_the_field_is_worth_approximately_nothing():
    # §6.5's "the median player's Record does not move" — asserted so that
    # the finish stipend's reason for existing stays visible in the tests.
    # A field of 30 has no exact midpoint rank, so bracket it instead.
    assert _base(15) > 0 > _base(16)
    assert abs(_base(15)) < 1.0 and abs(_base(16)) < 1.5


def test_placement_stays_well_behaved_over_a_large_field():
    # §6.2: "400th of 5000 gives p ~= 0.92".
    assert placement_p(400, 5000) == pytest.approx(0.92, abs=0.005)


# ── The n >= 8 fence (§6.6 problem 1) ────────────────────────────────────


@pytest.mark.parametrize("n", [1, 2, 3, 7])
def test_a_thin_field_never_reaches_the_placement_formula(n):
    # The acceptance criterion is "n = 1 and n = 2 never reach the placement
    # formula" — and it must REFUSE rather than return something. At n=1 the
    # formula divides by zero; at n=2 it is exactly 1.0 or 0.0, which is the
    # maximum prize in the game decided by a coin flip.
    with pytest.raises(ValueError, match="placement needs"):
        placement_p(1, n)


def test_the_fence_opens_at_exactly_eight():
    assert PLACEMENT_MIN_FIELD == 8
    assert placement_p(1, 8) == pytest.approx(1.0)
    assert placement_p(8, 8) == pytest.approx(0.0)


@pytest.mark.parametrize("rank", [0, -1, 9, 100])
def test_a_rank_outside_the_field_is_refused(rank):
    with pytest.raises(ValueError, match="outside a field"):
        placement_p(rank, 8)


def test_titles_need_a_bigger_field_than_scoring_does():
    # "A thin field can score, but a title needs a minimum field. Prestige
    # needs witnesses." (§6.6)
    assert TITLE_MIN_FIELD > PLACEMENT_MIN_FIELD


# ── §6.3's balance check ─────────────────────────────────────────────────


def test_fifty_two_weekly_wins_equal_one_annual_win_at_the_same_title():
    # The design's own check, and the reason the gain row is linear in
    # committed time: neither cadence may be a farm.
    annual = _base(1) * cadence_weight("year", negative=False) * 1.4
    weekly = _base(1) * cadence_weight("week", negative=False) * 1.4 * 52
    assert annual == pytest.approx(weekly)


def test_a_long_bad_run_is_damped_by_the_square_root_row():
    # Losses scale with sqrt(cadence): a player should not be crushed for
    # having been invested through a bear half-year.
    assert cadence_weight("year", negative=True) == pytest.approx(7.2)
    assert cadence_weight("year", negative=True) < cadence_weight(
        "year", negative=False,
    )


# ── §6.4's ladder ────────────────────────────────────────────────────────


def test_the_ladder_is_monotonic_in_points():
    seen = [
        title_for(career_points=pts, finished_runs=0, forfeits=0, qualifying_finishes=1)
        for pts in (0, 499, 500, 2_500, 10_000, 30_000, 1_000_000)
    ]
    multipliers = [title_multiplier(t) for t in seen]
    assert multipliers == sorted(multipliers)
    assert seen[0] == "apprentice"
    assert seen[-1] == "floor_veteran"


@pytest.mark.parametrize(
    "points,expected",
    [(0, "apprentice"), (499, "apprentice"), (500, "analyst"), (2_499, "analyst"),
     (2_500, "trader"), (10_000, "senior"), (30_000, "floor_veteran")],
)
def test_each_threshold_fires_on_its_own_boundary(points, expected):
    assert title_for(
        career_points=points, finished_runs=0, forfeits=0, qualifying_finishes=1,
    ) == expected


def test_the_second_rung_is_a_milestone_not_a_number():
    # Amendment D correction 3: three finished runs, none forfeited —
    # reachable in three weeks, fires once, cannot be farmed.
    assert title_for(career_points=0, finished_runs=3, forfeits=0) == "associate"
    assert title_multiplier("associate") == pytest.approx(1.2)


def test_two_finishes_is_not_yet_the_milestone():
    assert title_for(career_points=0, finished_runs=2, forfeits=0) == "apprentice"


def test_a_forfeit_withholds_the_milestone_rung():
    # "three runs finished, NONE forfeited" — the rung rewards finishing
    # what you start, which is the whole behaviour it exists to celebrate.
    assert title_for(career_points=0, finished_runs=9, forfeits=1) == "apprentice"


def test_points_outrank_the_milestone_when_both_could_apply():
    # A player at 600 who forfeited once is an Analyst. Demoting them for it
    # would make the x1.4 multiplier depend on a fact the points already
    # priced — and would break monotonicity in points, which the multiplier
    # being a MULTIPLIER on those same points cannot survive.
    assert title_for(
        career_points=600, finished_runs=9, forfeits=4, qualifying_finishes=1,
    ) == "analyst"


def test_a_named_rung_needs_a_witnessed_field():
    # §6.6: "a thin field can score, but a title needs a minimum field.
    # Prestige needs witnesses." 30,000 points earned entirely in thin
    # fields buys the points, not the name.
    assert title_for(
        career_points=30_000, finished_runs=0, forfeits=0, qualifying_finishes=0,
    ) == "apprentice"
    assert title_for(
        career_points=30_000, finished_runs=0, forfeits=0, qualifying_finishes=1,
    ) == "floor_veteran"


def test_the_milestone_rung_is_exempt_from_the_witness_requirement():
    # Amendment D built rung 2 FOR the early player in a thin field. Gating
    # it on 20 entrants would freeze every alpha player at apprentice —
    # exactly the frozen goal gradient the rung was added to fix. This is
    # the design reading that most needs to be visible if it is wrong.
    assert title_for(
        career_points=0, finished_runs=3, forfeits=0, qualifying_finishes=0,
    ) == "associate"


def test_an_unknown_or_missing_title_scores_as_apprentice_never_as_zero():
    # Zeroing would silently delete a real result — the run scored, the
    # ladder just could not be resolved.
    assert title_multiplier(None) == 1.0
    assert title_multiplier("") == 1.0
    assert title_multiplier("archmage") == 1.0


def test_every_title_in_the_ladder_has_a_multiplier():
    for title in ("apprentice", "associate", "analyst", "trader", "senior",
                  "floor_veteran"):
        assert title in TITLE_MULTIPLIER


# ── The minimum forfeit debit (§18) ──────────────────────────────────────


def test_one_forfeit_stays_cheaper_than_a_genuinely_bad_finish():
    # "the mercy rule must remain merciful" — a last-place weekly finish is
    # -40; the forfeit floor must sit well under it, or restarting becomes
    # the more expensive choice and the design's own advice to restart after
    # a blowup turns into a trap.
    assert forfeit_debit("week") < abs(_base(30))


def test_the_forfeit_floor_scales_on_the_loss_row_not_the_gain_row():
    # A player abandoning a year is not 52x worse than one abandoning a
    # week. Using the gain row here would cost 520 for one annual forfeit —
    # five times the maximum win in the game.
    assert forfeit_debit("year") == round(MIN_FORFEIT_DEBIT * 7.2)
    assert forfeit_debit("year") < MIN_FORFEIT_DEBIT * 52


def test_the_floor_is_positive_and_the_caller_owns_the_sign():
    # Same convention as `finish_stipend`, so a caller cannot accidentally
    # add a debit by forgetting to negate one of the two.
    assert forfeit_debit("week") > 0
    assert forfeit_debit("month") > 0
