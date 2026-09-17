"""
Bootstrap CI checks: coverage on iid Gaussian data over many seeded
repetitions, self-paired diff is exactly [0, 0], and the Wilson proportion
interval matches the closed-form formula.
"""

from __future__ import annotations

import numpy as np

from common.bootstrap import paired_diff_ci, proportion_ci, stationary_block_bootstrap_ci


def test_mean_ci_covers_true_mean_most_of_the_time():
    true_mean = 0.1
    n_reps = 200
    covered = 0
    for seed in range(n_reps):
        rng = np.random.default_rng(seed)
        x = rng.normal(loc=true_mean, scale=1.0, size=2000)
        ci = stationary_block_bootstrap_ci(x, n_boot=200, alpha=0.05, seed=seed)
        if ci["lower"] <= true_mean <= ci["upper"]:
            covered += 1

    coverage = covered / n_reps
    assert 0.90 <= coverage <= 0.99


def test_paired_diff_ci_of_series_with_itself_is_zero():
    rng = np.random.default_rng(0)
    x = rng.normal(size=300)
    ci = paired_diff_ci(x, x, n_boot=200, seed=1)

    assert ci["estimate"] == 0.0
    np.testing.assert_allclose(ci["lower"], 0.0, atol=1e-12)
    np.testing.assert_allclose(ci["upper"], 0.0, atol=1e-12)


def test_stationary_bootstrap_reproducible_with_same_seed():
    rng = np.random.default_rng(2)
    x = rng.normal(size=100)
    ci_a = stationary_block_bootstrap_ci(x, n_boot=200, seed=42)
    ci_b = stationary_block_bootstrap_ci(x, n_boot=200, seed=42)

    assert ci_a["lower"] == ci_b["lower"]
    assert ci_a["upper"] == ci_b["upper"]


def test_proportion_ci_matches_wilson_formula():
    successes, n = 62, 100
    ci = proportion_ci(successes, n, alpha=0.05)

    z = 1.959963984540054
    phat = successes / n
    denom = 1 + z**2 / n
    center = (phat + z**2 / (2 * n)) / denom
    half_width = (z * np.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2))) / denom
    expected_lower = center - half_width
    expected_upper = center + half_width

    np.testing.assert_allclose(ci["lower"], expected_lower, atol=1e-9)
    np.testing.assert_allclose(ci["upper"], expected_upper, atol=1e-9)
    assert ci["lower"] < phat < ci["upper"]


def test_proportion_ci_edge_cases_stay_within_bounds():
    ci_zero = proportion_ci(0, 10)
    assert ci_zero["lower"] >= 0.0
    assert ci_zero["upper"] <= 1.0

    ci_all = proportion_ci(10, 10)
    assert ci_all["lower"] >= 0.0
    assert ci_all["upper"] <= 1.0
