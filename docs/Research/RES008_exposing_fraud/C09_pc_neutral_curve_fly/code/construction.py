"""
PC-neutral Treasury curve fly construction, per PREREGISTRATION.md.

Pipeline (mirrors Andreev's slides 10-11, 20, 24 exactly, mapped onto
`U-RATES` tradeable ETFs -- see PREREGISTRATION.md for the full spec and
disclosed deviations):

  1. Daily yield changes on the 6 Treasury par tenors.
  2. Rolling 2-year PCA (unstandardized, raw yield-change covariance) fit at
     each date using only data through that date -- no lookahead.
  3. Map PC1/PC2 loadings from the 6 yield tenors onto the 5 `U-RATES` ETF
     buckets (nearest-tenor assignment) and solve the minimum-notional
     weight vector with zero net PC1 and PC2 exposure.
  4. EWMA z-score of the resulting fly's own cumulative ETF-return series;
     position = -z, capped at +-3.
  5. One-day execution delay (`next_open`, handled by common/backtest.py).

Every step here operates on data available at or before the day the signal
is used -- `rolling_pca_loadings` and `fly_weights_series` both loop forward
in time and only ever look at yields/returns up to and including index i.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# 6 Treasury par tenors (years) matching yield_data.TENORS order.
_TENOR_YEARS = np.array([2, 5, 7, 10, 20, 30], dtype=float)

# U-RATES ETF -> nearest Treasury tenor(s) for loading assignment.
# IEF (7-10y) sits between two tenors; averaged.
_ETF_TENOR_MAP = {
    "SHY": [2],
    "IEI": [5],
    "IEF": [7, 10],
    "TLH": [20],
    "TLT": [30],
}

ETF_ORDER = ["SHY", "IEI", "IEF", "TLH", "TLT"]

LOOKBACK_DAYS = 504  # ~2 trading years, Andreev's stated window (slide 11)
EWMA_HALFLIFE = 20
Z_CAP = 3.0


def _tenor_loading(loadings: np.ndarray, tenor_years: list[int]) -> float:
    idx = [int(np.where(_TENOR_YEARS == t)[0][0]) for t in tenor_years]
    return float(np.mean(loadings[idx]))


def rolling_pca_loadings(yield_changes: pd.DataFrame) -> pd.DataFrame:
    """PC1/PC2 loadings on the 6 tenors, refit daily on a trailing window.

    Returns a DataFrame indexed like `yield_changes` (rows before the first
    full window are NaN) with columns pc1_<tenor>, pc2_<tenor> for each of
    the 6 tenors, sign-fixed so each date's PC1 has a positive mean loading.
    """
    tenors = list(yield_changes.columns)
    n = len(yield_changes)
    values = yield_changes.to_numpy()

    out = np.full((n, 2 * len(tenors)), np.nan)

    for i in range(LOOKBACK_DAYS, n):
        window = values[i - LOOKBACK_DAYS : i]  # strictly before day i's own change
        window = window - window.mean(axis=0, keepdims=True)
        # SVD on the demeaned window; first two right singular vectors are PC1/PC2.
        _, _, vt = np.linalg.svd(window, full_matrices=False)
        pc1, pc2 = vt[0], vt[1]

        if pc1.mean() < 0:
            pc1 = -pc1
        # PC2 sign fixed so its long-end loading is positive (slope convention:
        # short end negative, long end positive -- a steepener has a positive PC2).
        if pc2[-1] < 0:
            pc2 = -pc2

        out[i, : len(tenors)] = pc1
        out[i, len(tenors) :] = pc2

    cols = [f"pc1_{t}" for t in tenors] + [f"pc2_{t}" for t in tenors]
    return pd.DataFrame(out, index=yield_changes.index, columns=cols)


def fly_weights_series(pca_loadings: pd.DataFrame) -> pd.DataFrame:
    """Per-date `U-RATES` weights with zero net PC1 and PC2 exposure.

    Solves, for each date with valid loadings, the minimum-norm weight
    vector w (5 ETFs) subject to:
        sum(w_i * pc1_loading_i) = 0
        sum(w_i * pc2_loading_i) = 0
        sum(|w_i|) = 1  (normalized gross exposure, applied after solving)
    via least-squares projection onto the null space of the 2xN constraint
    matrix, then rescaled to unit gross notional so every date's fly has
    comparable size before the EWMA signal scales it further.
    """
    tenors = [t for t in ["2", "5", "7", "10", "20", "30"]]  # unused, kept for clarity
    n = len(pca_loadings)
    weights = np.full((n, len(ETF_ORDER)), np.nan)

    for i in range(n):
        row = pca_loadings.iloc[i]
        if row.isna().any():
            continue

        pc1_etf = np.array([_tenor_loading(row.filter(like="pc1_").to_numpy(), _ETF_TENOR_MAP[e]) for e in ETF_ORDER])
        pc2_etf = np.array([_tenor_loading(row.filter(like="pc2_").to_numpy(), _ETF_TENOR_MAP[e]) for e in ETF_ORDER])

        constraint = np.vstack([pc1_etf, pc2_etf])  # 2x5
        # Null space of the 2x5 constraint via SVD: last (5-2)=3 right
        # singular vectors span weight vectors with zero net PC1/PC2 loading.
        _, _, vt = np.linalg.svd(constraint)
        null_basis = vt[2:]  # (3, 5)

        # Minimum-notional representative: the null-space vector closest to
        # an equal-weight long/short fly (Andreev's "fly" shape) -- project
        # a seed alternating-sign vector onto the null space.
        seed = np.array([1.0, -1.0, 1.0, -1.0, 1.0])
        coeffs = null_basis @ seed
        w = coeffs @ null_basis

        gross = np.abs(w).sum()
        if gross > 1e-9:
            w = w / gross
        weights[i] = w

    return pd.DataFrame(weights, index=pca_loadings.index, columns=ETF_ORDER)


def ewma_zscore(x: pd.Series, halflife: int) -> pd.Series:
    """EWMA mean/std z-score of `x`, computed causally (no lookahead)."""
    mean = x.ewm(halflife=halflife, adjust=False).mean()
    var = (x - mean).pow(2).ewm(halflife=halflife, adjust=False).mean()
    std = var.pow(0.5)
    z = (x - mean) / std.replace(0.0, np.nan)
    return z


def build_signal(
    yield_changes: pd.DataFrame,
    etf_returns: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    """Full pipeline: yield changes + ETF returns -> (fly_weights, position).

    `etf_returns` must be aligned to `yield_changes`' index (both daily,
    same trading calendar). Returns (fly_weights, target_position) where
    target_position is the EWMA-z-score-derived scalar signal, capped at
    +-Z_CAP, to be applied to `fly_weights` at each date. Both are causal:
    fly_weights[i] uses only yield_changes through i; target_position[i]
    uses only the fly-return history through i.
    """
    loadings = rolling_pca_loadings(yield_changes)
    weights = fly_weights_series(loadings)

    fly_return = (weights.shift(1) * etf_returns).sum(axis=1, skipna=False)
    # shift(1): the weight computed AT close(i) is applied to the return
    # REALIZED on day i+1's leg in the backtest engine (next_open execution
    # handles the actual 1-day delay); here we need the fly's own return
    # series for the signal, which itself must not look ahead -- weights[i]
    # decided at close(i) cannot price day i's own already-realized return.
    fly_return = fly_return.dropna()

    cum_fly = fly_return.cumsum()
    z = ewma_zscore(cum_fly, EWMA_HALFLIFE)
    position = (-z).clip(-Z_CAP, Z_CAP)

    return weights, position
