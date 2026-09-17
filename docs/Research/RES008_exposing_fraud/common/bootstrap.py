"""
Interval estimation for RES008: stationary block bootstrap, never a p-value.

Daily returns are autocorrelated and mean returns are poorly estimable at
the sample sizes a single-ticker backtest produces (Lo 2002) -- an ordinary
iid bootstrap or a t-test understates the true uncertainty because it
shuffles away the autocorrelation. The stationary bootstrap of Politis &
Romano (1994) resamples in blocks of geometrically-distributed random
length, preserving short-range dependence while still being asymptotically
valid for stationary weakly-dependent series.

No hypothesis test or p-value is exposed anywhere here -- report the window
and the interval, per the repo's method standard.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
from scipy import stats


def _stationary_bootstrap_indices(
    n: int, block_len: float, rng: np.random.Generator
) -> np.ndarray:
    """One stationary-bootstrap resample of indices into a length-n series.

    Blocks have geometrically distributed length with mean `block_len`;
    wrap-around at the end of the series keeps every draw length exactly n
    (circular block bootstrap variant of Politis-Romano).
    """
    p = 1.0 / block_len
    idx = np.empty(n, dtype=int)
    pos = 0
    cur = rng.integers(0, n)
    idx[0] = cur
    pos = 1
    while pos < n:
        if rng.random() < p:
            cur = rng.integers(0, n)
        else:
            cur = (cur + 1) % n
        idx[pos] = cur
        pos += 1
    return idx


def _default_block_len(n: int) -> float:
    return max(5, round(n ** (1.0 / 3.0) * 2))


def stationary_block_bootstrap_ci(
    x,
    stat: Callable[[np.ndarray], float] = np.mean,
    block_len: float | None = None,
    n_boot: int = 5000,
    alpha: float = 0.05,
    seed: int = 0,
) -> dict:
    """Percentile CI for `stat(x)` via the stationary block bootstrap.

    Returns {"estimate", "lower", "upper", "block_len", "n_boot", "replicates"}.
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n == 0:
        raise ValueError("x is empty")

    if block_len is None:
        block_len = _default_block_len(n)

    rng = np.random.default_rng(seed)
    replicates = np.empty(n_boot)
    for b in range(n_boot):
        idx = _stationary_bootstrap_indices(n, block_len, rng)
        replicates[b] = stat(x[idx])

    lower = float(np.quantile(replicates, alpha / 2.0))
    upper = float(np.quantile(replicates, 1.0 - alpha / 2.0))

    return {
        "estimate": float(stat(x)),
        "lower": lower,
        "upper": upper,
        "block_len": block_len,
        "n_boot": n_boot,
        "replicates": replicates,
    }


def paired_diff_ci(
    a,
    b,
    stat: Callable[[np.ndarray], float] = np.mean,
    block_len: float | None = None,
    n_boot: int = 5000,
    alpha: float = 0.05,
    seed: int = 0,
) -> dict:
    """CI for stat(a) - stat(b), resampling both series with the SAME block indices.

    Using the same resampled index path for `a` and `b` on each replicate
    preserves whatever pairing/joint structure they share (e.g. same dates)
    and is what makes this a paired rather than independent-samples CI.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if len(a) != len(b):
        raise ValueError("a and b must be the same length to be paired")
    n = len(a)
    if n == 0:
        raise ValueError("a/b are empty")

    if block_len is None:
        block_len = _default_block_len(n)

    rng = np.random.default_rng(seed)
    replicates = np.empty(n_boot)
    for r in range(n_boot):
        idx = _stationary_bootstrap_indices(n, block_len, rng)
        replicates[r] = stat(a[idx]) - stat(b[idx])

    lower = float(np.quantile(replicates, alpha / 2.0))
    upper = float(np.quantile(replicates, 1.0 - alpha / 2.0))

    return {
        "estimate": float(stat(a) - stat(b)),
        "lower": lower,
        "upper": upper,
        "block_len": block_len,
        "n_boot": n_boot,
        "replicates": replicates,
    }


def proportion_ci(successes: int, n: int, alpha: float = 0.05) -> dict:
    """Wilson score interval for a proportion (e.g. trade win rate).

    Treats each trial as an independent Bernoulli draw. That assumption is
    weak for trade win rates when trades overlap in time or share a common
    market-wide driver (correlated regimes, not independent coin flips) --
    use this for a quick read, not as the final word on significance;
    prefer the block bootstrap on a return series when trades are not
    plausibly independent.
    """
    if n <= 0:
        raise ValueError("n must be positive")
    if not (0 <= successes <= n):
        raise ValueError("successes must be between 0 and n")

    z = stats.norm.ppf(1.0 - alpha / 2.0)
    phat = successes / n
    denom = 1.0 + z**2 / n
    center = (phat + z**2 / (2 * n)) / denom
    half_width = (z * np.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2))) / denom

    return {
        "estimate": float(phat),
        "lower": float(max(0.0, center - half_width)),
        "upper": float(min(1.0, center + half_width)),
    }
