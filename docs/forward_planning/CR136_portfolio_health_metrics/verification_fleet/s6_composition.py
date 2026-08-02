"""Claim 7: shipping-composition check — EWMA(0.97) cov on risky sleeve, cash row
appended, no shrinkage. Euler identity exactness + sigma_p vs direct weighted vol
of the portfolio return series (cash included as literal zero returns).
Run across 200 seeds to show exactness is structural, not one lucky draw."""
import numpy as np
from cr136lib import twin_book, ewma_cov, euler_contributions

N, T, LAM = 10, 504, 0.97
w_r, Sig_true, _ = twin_book()
Lc = np.linalg.cholesky(Sig_true)
cash = 0.10
w_full = np.concatenate([w_r * (1 - cash), [cash]])

age = np.arange(T - 1, -1, -1)
wt = LAM**age
wt /= wt.sum()

max_sum_err, max_cash, max_sig_err, max_dr2_nan = 0.0, 0.0, 0.0, 0
for seed in range(200):
    rng = np.random.default_rng(3000 + seed)
    X = rng.standard_normal((T, N)) @ Lc.T
    S_r = ewma_cov(X, LAM)                     # risky-only EWMA cov
    S_full = np.zeros((N + 1, N + 1))
    S_full[:N, :N] = S_r                       # cash row/col = exact zeros
    rc, sig_q = euler_contributions(w_full, S_full)
    # direct: EWMA-weighted vol of the full portfolio return series (cash returns = 0)
    port = np.hstack([X, np.zeros((T, 1))]) @ w_full
    mu = wt @ port
    sig_d = np.sqrt(np.sum(wt * (port - mu) ** 2))
    max_sum_err = max(max_sum_err, abs(rc.sum() - 1.0))
    max_cash = max(max_cash, abs(rc[-1]))
    max_sig_err = max(max_sig_err, abs(sig_q - sig_d) / sig_d)
    sd = np.sqrt(np.diag(S_full))
    d2 = (w_full @ sd) ** 2 / (w_full @ S_full @ w_full)
    if not np.isfinite(d2):
        max_dr2_nan += 1

print("Claim 7 composition [EWMA 0.97 risky-only + cash appended, no shrink], 200 seeds:")
print(f"  max |sum(Euler contributions) - 1|: {max_sum_err:.3e}")
print(f"  max |cash contribution|:            {max_cash:.3e}")
print(f"  max rel |sigma_quadform - sigma_series|: {max_sig_err:.3e}")
print(f"  non-finite DR^2 count: {max_dr2_nan}/200")
