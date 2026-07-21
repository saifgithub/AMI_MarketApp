"""Portfolio statistics — variance, covariance, correlation, beta, wᵀΣw.

CR046 M11, opened for CR054 Wave 1 (BOK Level 11 / M18–M19 diversification &
modern portfolio theory, plus the M20 evidence lessons): the correlation, beta,
and portfolio-variance figures in worked examples are computed here, never
authored by hand (CR054 §4.5).

Sample convention (n-1 denominator) throughout, over equal-length return
series. Presented figures round 2 dp (`correlation`, `beta`); the dimensioned
quantities (`variance`, `covariance`, `portfolio_variance`) stay unrounded
because callers compose them (take a square root for volatility) and format
last.

Pure — lists of floats in, a float or None out.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import sqrt


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def variance(values: Sequence[float]) -> float | None:
    """Sample variance (n-1 denominator). None below 2 observations."""
    if len(values) < 2:
        return None
    m = _mean(values)
    return sum((v - m) ** 2 for v in values) / (len(values) - 1)


def covariance(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Sample covariance of two equal-length series. None on mismatch or n < 2."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx, my = _mean(xs), _mean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (len(xs) - 1)


def correlation(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Pearson correlation in [-1, 1], 2 dp. None when either series is flat.

    A flat series has zero variance — its correlation with anything is
    undefined, so the figure is omitted rather than defaulted.
    """
    cov = covariance(xs, ys)
    if cov is None:
        return None
    vx, vy = variance(xs), variance(ys)
    if not vx or not vy:
        return None
    return round(cov / sqrt(vx * vy), 2)


def beta(
    asset_returns: Sequence[float], market_returns: Sequence[float]
) -> float | None:
    """CAPM beta (2 dp): cov(asset, market) / var(market).

    None when the market series is flat (no denominator) or lengths mismatch.
    """
    cov = covariance(asset_returns, market_returns)
    var_market = variance(market_returns)
    if cov is None or not var_market:
        return None
    return round(cov / var_market, 2)


def portfolio_variance(
    weights: Sequence[float], cov_matrix: Sequence[Sequence[float]]
) -> float | None:
    """Portfolio return variance wᵀΣw over an n-asset covariance matrix.

    Unrounded (callers take sqrt for portfolio volatility). Weights are not
    forced to sum to 1 — long/short and levered teaching examples are legal.
    Returns None when the matrix isn't square-and-matching, isn't symmetric,
    or produces a negative variance (a hand-typed non-PSD matrix) — a wrong
    number a lesson must not ship.
    """
    n = len(weights)
    if n == 0 or len(cov_matrix) != n:
        return None
    for row in cov_matrix:
        if len(row) != n:
            return None
    for i in range(n):
        for j in range(i + 1, n):
            if abs(cov_matrix[i][j] - cov_matrix[j][i]) > 1e-9:
                return None
    total = sum(
        weights[i] * weights[j] * cov_matrix[i][j]
        for i in range(n)
        for j in range(n)
    )
    if total < 0:
        return None
    return total
