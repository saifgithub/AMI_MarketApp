"""CR136 verification — script 2: MC checks.
(a) F7: SE(s) inflation at excess kurtosis 30, T=126, via normal scale-mixture
    (all moments finite) and Student-t nu=4.2 (kurtosis finite, 8th moment not).
(b) F17: relative sampling error of sigma_hat_p for fixed weights, N in {5,25,60,200},
    T=126; singularity check at N=200.
"""
import numpy as np

rng = np.random.default_rng(20260802)
T = 126

print("=" * 72)
print("F7 MC — SE(s) inflation at k_excess=30, T=126")
print("=" * 72)

# --- build 2-component zero-mean normal scale mixture with excess kurtosis 30
# with prob p variance k*v, else v. excess kurt = 3*(E[V^2]/E[V]^2 - 1)
p = 0.05
target_ratio = 1 + 30.0 / 3.0  # E[V^2]/E[V]^2 = 11
lo_k, hi_k = 1.0, 10000.0
for _ in range(200):
    mid = 0.5 * (lo_k + hi_k)
    r = (p * mid**2 + (1 - p)) / (p * mid + (1 - p)) ** 2
    if r < target_ratio:
        lo_k = mid
    else:
        hi_k = mid
kmix = 0.5 * (lo_k + hi_k)
sigma_d = 0.20 / np.sqrt(252)  # daily sd for 20% annualised
mean_v = p * kmix + (1 - p)
v_quiet = sigma_d**2 / mean_v
v_loud = kmix * v_quiet
kex_theory = 3 * ((p * kmix**2 + (1 - p)) / (p * kmix + (1 - p)) ** 2 - 1)
print(f"  mixture: p={p}, variance ratio k={kmix:.3f}, "
      f"theoretical k_excess={kex_theory:.3f}")

R = 200_000
# draw in chunks to bound memory
sds_mix = np.empty(R)
sds_gau = np.empty(R)
kurt_acc = []
chunk = 20_000
for i in range(0, R, chunk):
    n = min(chunk, R - i)
    is_loud = rng.random((n, T)) < p
    scale = np.where(is_loud, np.sqrt(v_loud), np.sqrt(v_quiet))
    x = rng.standard_normal((n, T)) * scale
    sds_mix[i:i + n] = x.std(axis=1, ddof=1)
    g = rng.standard_normal((n, T)) * sigma_d
    sds_gau[i:i + n] = g.std(axis=1, ddof=1)
    kurt_acc.append(x.ravel())
allx = np.concatenate(kurt_acc)
kex_emp = allx.var() ** -2 * np.mean((allx - allx.mean()) ** 4) - 3
print(f"  empirical k_excess of pooled draws ({allx.size:,} obs): {kex_emp:.2f}")

ann = np.sqrt(252) * 100
sd_mix = sds_mix.std(ddof=1) * ann   # SD of annualised vol estimate, in pp
sd_gau = sds_gau.std(ddof=1) * ann
analytic_gauss = 20.0 / np.sqrt(2 * T)
print(f"  R={R:,} reps, T={T}, sigma=20% ann, seed=20260802")
print(f"  MC SD(s_ann):  Gaussian = {sd_gau:.4f} pp  (analytic sigma/sqrt(2T) "
      f"= {analytic_gauss:.4f})")
print(f"  MC SD(s_ann):  mixture  = {sd_mix:.4f} pp  "
      f"({100*sd_mix/20:.1f}% of estimate)")
print(f"  MC inflation = {sd_mix/sd_gau:.3f}x   (analytic sqrt(32/2) = 4.000x)")
print(f"  mean(s_ann) mixture = {sds_mix.mean()*ann:.3f} pp (downward bias of s "
      f"under fat tails, for reference)")

# Student-t secondary check: nu s.t. excess kurt = 6/(nu-4) = 30 -> nu = 4.2
nu = 4.2
t_scale = sigma_d / np.sqrt(nu / (nu - 2))  # scale so variance = sigma_d^2
sds_t = np.empty(R)
for i in range(0, R, chunk):
    n = min(chunk, R - i)
    x = rng.standard_t(nu, size=(n, T)) * t_scale
    sds_t[i:i + n] = x.std(axis=1, ddof=1)
sd_t = sds_t.std(ddof=1) * ann
print(f"  Student-t nu=4.2 (k_excess=30 in theory; 8th moment infinite so MC "
      f"SD converges slowly):")
print(f"    MC SD(s_ann) = {sd_t:.4f} pp -> inflation {sd_t/sd_gau:.3f}x "
      f"(indicative only)")

print()
print("=" * 72)
print("F17 MC — rel. sampling error of sigma_hat_p, fixed weights, T=126")
print("=" * 72)
Rw = 20_000
rho = 0.3
for N in [5, 25, 60, 200]:
    rngN = np.random.default_rng(1000 + N)  # fixed seed per N
    vols = 0.20 + 0.10 * rngN.random(N)     # ann vols in [20%,30%], fixed
    C = np.full((N, N), rho)
    np.fill_diagonal(C, 1.0)
    Sig = np.outer(vols, vols) * C / 252.0  # daily covariance
    L = np.linalg.cholesky(Sig)
    w = np.full(N, 1.0 / N)
    sig_p_true = np.sqrt(w @ (Sig * 252) @ w)
    est = np.empty(Rw)
    for i in range(Rw):
        X = rngN.standard_normal((T, N)) @ L.T
        pr = X @ w
        est[i] = pr.std(ddof=1) * np.sqrt(252)
    rel = est.std(ddof=1) / sig_p_true
    print(f"  N={N:3d}: sigma_p_true={sig_p_true*100:.2f}%  "
          f"rel SE = {rel*100:.3f}%   (analytic 1/sqrt(2T) = "
          f"{100/np.sqrt(2*T):.3f}%)")
    if N == 200:
        X = np.random.default_rng(7).standard_normal((T, N)) @ L.T
        S = np.cov(X, rowvar=False, ddof=1)
        rank = np.linalg.matrix_rank(S)
        wSw = np.sqrt(w @ S @ w * 252)
        port_var = np.sqrt((X @ w).std(ddof=1) ** 2 * 252)
        print(f"       singularity check: rank(S) = {rank} of {N} "
              f"(singular: {rank < N}); w'Sw route = {wSw*100:.4f}% vs "
              f"univariate route = {port_var*100:.4f}% (identical: "
              f"{np.isclose(wSw, port_var)})")
