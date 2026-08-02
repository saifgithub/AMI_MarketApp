"""Claim 3 follow-up: N=2 degeneracy across 500 seeds — is gamma ever exactly 0,
what does delta do, and is shrinkage ever a real operation at N=2?"""
import numpy as np
from cr136lib import lw_const_corr, sample_cov, SIG_D

T = 126
R2 = np.array([[1.0, 0.5], [0.5, 1.0]])
L2 = np.linalg.cholesky(R2 * SIG_D**2)
gammas, deltas, tgt_diff = [], [], []
exact_zero = 0
for seed in range(500):
    rng = np.random.default_rng(1000 + seed)
    X2 = rng.standard_normal((T, 2)) @ L2.T
    Sig2, d2, aux = lw_const_corr(X2, return_delta=True)
    S2 = sample_cov(X2)
    F = aux["rbar"] * np.sqrt(np.outer(np.diag(S2), np.diag(S2)))
    np.fill_diagonal(F, np.diag(S2))
    gammas.append(aux["gamma"])
    deltas.append(d2)
    tgt_diff.append(np.abs(F - S2).max() / np.abs(S2).max())
    if aux["gamma"] == 0.0:
        exact_zero += 1
g = np.array(gammas); d = np.array(deltas); td = np.array(tgt_diff)
print(f"N=2, 500 seeds, T={T}:")
print(f"  gamma exactly 0.0:            {exact_zero}/500")
print(f"  gamma range (float dust):     [{g.min():.3e}, {g.max():.3e}]")
print(f"  max relative |target-sample|: {td.max():.3e}  (0 => target==sample always)")
print(f"  delta values: NaN {np.isnan(d).sum()}, ==1.0 {(d==1.0).sum()}, "
      f"==0.0 {(d==0.0).sum()}, other {((d>0)&(d<1)).sum()}")
