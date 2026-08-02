"""Claim 2: F4 independent-window fire rates for R3 (beta >= 1.3).

Model: r_p,t = beta * r_m,t + eps_t, daily. Market annual vol 16%.
Idiosyncratic vol chosen so SE(beta_hat) ~ 0.090 at T=126 (implies R^2 ~0.59-0.66
across beta 1.2-1.4, inside the review's 'R^2 ~ 0.5-0.65' large-cap band).
3000+ independent windows per true beta; OLS with intercept.
"""
import numpy as np

rng = np.random.default_rng(20260802)
T = 126
N_WIN = 5000  # >= 3000 required
sig_m = 0.16 / np.sqrt(252)
target_se = 0.090
sig_e = target_se * sig_m * np.sqrt(T)   # SE = sig_e/(sig_m*sqrt(T)) asymptotically

print(f"params: T={T}, windows={N_WIN}, sig_m(daily)={sig_m:.6f}, "
      f"sig_e(daily)={sig_e:.6f} (annual {sig_e*np.sqrt(252)*100:.1f}%)")

for beta in [1.20, 1.30, 1.40]:
    rm = rng.normal(0, sig_m, (N_WIN, T))
    ep = rng.normal(0, sig_e, (N_WIN, T))
    rp = beta * rm + ep
    # OLS with intercept, vectorized
    rm_c = rm - rm.mean(axis=1, keepdims=True)
    rp_c = rp - rp.mean(axis=1, keepdims=True)
    sxx = (rm_c**2).sum(axis=1)
    bhat = (rm_c * rp_c).sum(axis=1) / sxx
    resid = rp_c - bhat[:, None] * rm_c
    s2 = (resid**2).sum(axis=1) / (T - 2)
    se = np.sqrt(s2 / sxx)
    r2 = 1 - (resid**2).sum(axis=1) / (rp_c**2).sum(axis=1)
    fire = (bhat >= 1.3)
    print(f"\ntrue beta={beta:.2f}: fire rate P(beta_hat>=1.3) = {fire.mean()*100:.1f}%")
    print(f"  empirical SD(beta_hat) = {bhat.std(ddof=1):.4f}   mean OLS SE = {se.mean():.4f}")
    print(f"  mean R^2 = {r2.mean():.3f}   mean beta_hat = {bhat.mean():.4f}")
