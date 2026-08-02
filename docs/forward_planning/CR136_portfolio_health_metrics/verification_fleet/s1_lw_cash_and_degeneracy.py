"""Claims 1-3: LW+cash NaN reproduction, risky-only-then-append fix, N=1/N=2 degeneracy."""
import numpy as np
from cr136lib import lw_const_corr, sample_cov, dr2, euler_contributions, SIG_D

rng = np.random.default_rng(136)

# ---------- Claim 1: 6 risky + cash, T=126, LW on the full panel ----------
T, Nr = 126, 6
R = np.full((Nr, Nr), 0.35)
np.fill_diagonal(R, 1.0)
Sig_true = R * SIG_D**2
L = np.linalg.cholesky(Sig_true)
X_risky = rng.standard_normal((T, Nr)) @ L.T
X_full = np.hstack([X_risky, np.zeros((T, 1))])  # cash column: exactly 0 every day

Sig_lw, delta, aux = lw_const_corr(X_full, return_delta=True)
n_nan_shrunk = int(np.isnan(Sig_lw).sum())
w_full = np.array([0.15, 0.15, 0.15, 0.15, 0.15, 0.10, 0.15])  # 85% risky, 15% cash
with np.errstate(invalid="ignore"):
    var_p = w_full @ Sig_lw @ w_full
    sig_p = np.sqrt(var_p) if var_p == var_p else np.nan
print("=== Claim 1: LW constant-correlation on 6 risky + cash, T=126 ===")
print(f"rbar = {aux['rbar']}, delta = {delta}")
print(f"NaN entries in shrunk Sigma: {n_nan_shrunk} of {Sig_lw.size}")
print(f"sigma_p = {sig_p}")

# where do the NaNs sit? count entries involving the cash row/col vs not
mask_cash = np.zeros_like(Sig_lw, dtype=bool)
mask_cash[-1, :] = True
mask_cash[:, -1] = True
print(f"NaNs on cash row/col: {int(np.isnan(Sig_lw[mask_cash]).sum())} of {mask_cash.sum()}")
print(f"NaNs elsewhere:       {int(np.isnan(Sig_lw[~mask_cash]).sum())} of {(~mask_cash).sum()}")

# ---------- Claim 2: fix = shrink risky-only, append zero cash row/col ----------
print("\n=== Claim 2: risky-only shrink + append cash row/col ===")
Sig_r, delta_r, _ = lw_const_corr(X_risky, return_delta=True)
Sig_fix = np.zeros((Nr + 1, Nr + 1))
Sig_fix[:Nr, :Nr] = Sig_r
print(f"delta (risky-only) = {delta_r:.4f}")
print(f"NaN entries in fixed Sigma: {int(np.isnan(Sig_fix).sum())}")

rc, sig_p_fix = euler_contributions(w_full, Sig_fix)
print(f"sigma_p (ann) = {sig_p_fix * np.sqrt(252):.6f}")
print(f"Euler contributions sum = {rc.sum():.17f}  (sum-1 = {rc.sum()-1:.3e})")
print(f"cash contribution = {rc[-1]:.17f}")

# sigma_p correctness vs direct computation on the risky sleeve alone
w_risky = w_full[:Nr]
sig_direct = np.sqrt(w_risky @ Sig_r @ w_risky)
print(f"sigma_p via full (w'Sig_fix w)^.5 = {sig_p_fix:.12e}")
print(f"sigma_p via risky sleeve direct   = {sig_direct:.12e}")
print(f"abs diff = {abs(sig_p_fix - sig_direct):.3e}")
# and vs portfolio-return-series sample vol using the same S (sanity, delta=0 case)
S_r = sample_cov(X_risky)
port = X_risky @ w_risky  # cash adds 0 to every day's return
port_c = port - port.mean()
sig_series = np.sqrt(port_c @ port_c / T)
sig_quad = np.sqrt(w_risky @ S_r @ w_risky)
print(f"[unshrunk cross-check] series vol {sig_series:.12e} vs quadform {sig_quad:.12e} "
      f"diff {abs(sig_series - sig_quad):.3e}")

# DR^2 well-defined under the fix (cash sd = 0 contributes 0 to numerator)
print(f"DR^2 (full book incl cash) = {dr2(w_full, Sig_fix):.4f}  <- finite, no NaN")

# ---------- Claim 3: N=1 and N=2 degeneracies ----------
print("\n=== Claim 3: N=1 and N=2 ===")
X1 = rng.standard_normal((T, 1)) * SIG_D
Sig1, delta1, aux1 = lw_const_corr(X1, return_delta=True)
print(f"N=1: rbar = {aux1['rbar']}, kappa = {aux1['kappa']}, delta = {delta1}")
print(f"N=1: shrunk Sigma = {Sig1.ravel()}  (sample var = {sample_cov(X1).ravel()})")

R2 = np.array([[1.0, 0.5], [0.5, 1.0]])
L2 = np.linalg.cholesky(R2 * SIG_D**2)
X2 = rng.standard_normal((T, 2)) @ L2.T
Sig2, delta2, aux2 = lw_const_corr(X2, return_delta=True)
S2 = sample_cov(X2)
F2t = aux2["rbar"] * np.sqrt(np.outer(np.diag(S2), np.diag(S2)))
np.fill_diagonal(F2t, np.diag(S2))
print(f"N=2: rbar = {aux2['rbar']:.6f} (the single pairwise corr = "
      f"{S2[0,1]/np.sqrt(S2[0,0]*S2[1,1]):.6f})")
print(f"N=2: max|target - sample| = {np.abs(F2t - S2).max():.3e}  (target == sample?)")
print(f"N=2: gamma = {aux2['gamma']:.6e}, kappa = {aux2['kappa']}, delta = {delta2}")
print(f"N=2: shrunk Sigma finite? {np.isfinite(Sig2).all()}")
