"""Shared library for CR136 covariance-estimator claim verification.

Implements the Ledoit-Wolf (2004) 'Honey, I Shrunk the Sample Covariance Matrix'
constant-correlation shrinkage estimator, EWMA weighted covariance, DR^2, Euler
risk contributions, and the F2 'twin book' construction. All numbers used in the
verification report are produced by scripts importing this module.
"""
import numpy as np

ANN = 252
VOL_ANN = 0.20
SIG_D = VOL_ANN / np.sqrt(ANN)  # daily vol per name


def sample_cov(X):
    """Demeaned sample covariance with 1/T normalisation (LW convention)."""
    T = X.shape[0]
    Xc = X - X.mean(axis=0, keepdims=True)
    return Xc.T @ Xc / T


def lw_const_corr(X, return_delta=False):
    """Ledoit-Wolf constant-correlation shrinkage (covCor). X: T x N returns.

    Follows Ledoit & Wolf (2004) exactly: S with 1/T, rbar = mean pairwise corr,
    target F, pi-hat, rho-hat, gamma-hat, kappa, delta = clamp(kappa/T, 0, 1).
    No guards: division-by-zero / NaN propagate deliberately so degeneracies
    can be observed (that is the point of claims 1 and 3).
    """
    T, N = X.shape
    Xc = X - X.mean(axis=0, keepdims=True)
    S = Xc.T @ Xc / T
    var = np.diag(S).copy()
    with np.errstate(divide="ignore", invalid="ignore"):
        sqv = np.sqrt(var)
        denom = np.outer(sqv, sqv)
        corr = S / denom
        rbar = (corr.sum() - N) / (N * (N - 1)) if N > 1 else np.nan
        F = rbar * denom
        np.fill_diagonal(F, var)
        # pi-hat
        Y = Xc**2
        phi_mat = Y.T @ Y / T - S**2
        phi = phi_mat.sum()
        # theta[i,j] = mean_t(x_ti^3 * x_tj) - s_ii * s_ij
        theta = (Xc**3).T @ Xc / T - var[:, None] * S
        # rho-hat
        scale = np.outer(1.0 / sqv, sqv)  # sqrt(s_jj/s_ii)
        off = scale * theta
        np.fill_diagonal(off, 0.0)
        rho = np.trace(phi_mat) + rbar * off.sum()
        gamma = np.sum((F - S) ** 2)
        kappa = (phi - rho) / gamma
        delta = max(0.0, min(1.0, kappa / T)) if np.isfinite(kappa) else np.nan
        Sig = delta * F + (1 - delta) * S if np.isfinite(delta) else np.full_like(S, np.nan)
    if return_delta:
        return Sig, delta, dict(rbar=rbar, phi=phi, rho=rho, gamma=gamma, kappa=kappa)
    return Sig


def ewma_cov(X, lam=0.97, demean=True):
    """EWMA weighted sample covariance. X: T x N, most recent row LAST.

    Weights w_t proportional to lam^age (age 0 = most recent), normalised to sum 1.
    demean=True subtracts the same-weighted mean (keeps Euler/direct identity exact).
    """
    T = X.shape[0]
    age = np.arange(T - 1, -1, -1)  # row 0 oldest
    w = lam**age
    w = w / w.sum()
    if demean:
        mu = w @ X
        Xc = X - mu
    else:
        Xc = X
    return (Xc * w[:, None]).T @ Xc


def dr2(w, Sig):
    """Diversification ratio squared: (sum w_i * sd_i)^2 / (w' Sig w)."""
    sd = np.sqrt(np.diag(Sig))
    return float((w @ sd) ** 2 / (w @ Sig @ w))


def euler_contributions(w, Sig):
    """Euler risk contributions w_i*(Sig w)_i / sigma_p^2. Sums to 1 identically."""
    var_p = float(w @ Sig @ w)
    return w * (Sig @ w) / var_p, np.sqrt(var_p)


def twin_book(rho_base=0.30, rho_pair=0.85, n=10, w_pair=0.30):
    """F2 twin-heavy book: N names, equal 20%-ann vol, all pairwise rho_base
    except names (0,1) at rho_pair; weights w_pair each on the twins, rest equal."""
    R = np.full((n, n), rho_base)
    np.fill_diagonal(R, 1.0)
    R[0, 1] = R[1, 0] = rho_pair
    Sig = R * SIG_D**2
    w = np.full(n, (1 - 2 * w_pair) / (n - 2))
    w[0] = w[1] = w_pair
    return w, Sig, R


def solve_rho_base_for_dr2(target_dr2, rho_pair=0.85, n=10, w_pair=0.30):
    """Solve the base correlation giving a target true DR^2 on the twin structure.
    Equal vols => DR^2 = 1/(w'Rw); w'Rw = sum w^2 + 2 w_pair^2 rho_pair
    + (1 - sum w^2 - 2 w_pair^2) * rho_base.
    """
    w = np.full(n, (1 - 2 * w_pair) / (n - 2))
    w[0] = w[1] = w_pair
    s2 = np.sum(w**2)
    pair_term = 2 * w_pair * w_pair * rho_pair
    rest_coeff = 1 - s2 - 2 * w_pair * w_pair
    rho_base = (1.0 / target_dr2 - s2 - pair_term) / rest_coeff
    return rho_base
