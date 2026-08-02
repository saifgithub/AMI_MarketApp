"""Claim 4 (F2): twin-book Monte Carlo — R2 fire rates under plain sample cov vs
LW constant-correlation shrinkage, sigma_p bias under LW.
Claim 7 (partial): same MC under EWMA(0.97, 504-lookback) sample cov, no shrinkage.
"""
import numpy as np
from cr136lib import twin_book, SIG_D

rng = np.random.default_rng(42)
w, Sig_true, R = twin_book()
N = 10
Lc = np.linalg.cholesky(Sig_true)
true_dr2 = float((w @ np.sqrt(np.diag(Sig_true))) ** 2 / (w @ Sig_true @ w))
true_sig_ann = float(np.sqrt(w @ Sig_true @ w) * np.sqrt(252))
eigmin = np.linalg.eigvalsh(R).min()
print(f"True Sigma check: DR^2 = {true_dr2:.4f} (claim 1.855), "
      f"sigma_p_ann = {true_sig_ann:.4%}, min eig(R) = {eigmin:.4f}")


def batch_sample_cov(X):
    T = X.shape[1]
    Xc = X - X.mean(axis=1, keepdims=True)
    return np.einsum("rti,rtj->rij", Xc, Xc) / T, Xc


def batch_lw(X):
    R_, T, N_ = X.shape
    S, Xc = batch_sample_cov(X)
    var = np.einsum("rii->ri", S).copy()
    sqv = np.sqrt(var)
    denom = np.einsum("ri,rj->rij", sqv, sqv)
    corr = S / denom
    rbar = (corr.sum(axis=(1, 2)) - N_) / (N_ * (N_ - 1))
    F = rbar[:, None, None] * denom
    idx = np.arange(N_)
    F[:, idx, idx] = var
    Y = Xc**2
    phi_mat = np.einsum("rti,rtj->rij", Y, Y) / T - S**2
    phi = phi_mat.sum(axis=(1, 2))
    theta = np.einsum("rti,rtj->rij", Xc**3, Xc) / T - var[:, :, None] * S
    scale = np.einsum("ri,rj->rij", 1.0 / sqv, sqv)
    off = scale * theta
    off[:, idx, idx] = 0.0
    rho = np.einsum("rii->r", phi_mat) + rbar * off.sum(axis=(1, 2))
    gamma = ((F - S) ** 2).sum(axis=(1, 2))
    kappa = (phi - rho) / gamma
    delta = np.clip(kappa / T, 0.0, 1.0)
    Sig = delta[:, None, None] * F + (1 - delta[:, None, None]) * S
    return Sig, delta, S


def batch_dr2_sig(Sig, w):
    sd = np.sqrt(np.einsum("rii->ri", Sig))
    num = (sd @ w) ** 2
    den = np.einsum("rij,i,j->r", Sig, w, w)
    return num / den, np.sqrt(den)


def run_T(T, reps, seed):
    r = np.random.default_rng(seed)
    Z = r.standard_normal((reps, T, N))
    X = Z @ Lc.T
    Sig_lw, delta, S = batch_lw(X)
    dr2_s, sig_s = batch_dr2_sig(S, w)
    dr2_l, sig_l = batch_dr2_sig(Sig_lw, w)
    return dr2_s, sig_s, dr2_l, sig_l, delta


for T, reps, seed in [(126, 4000, 7), (252, 4000, 8)]:
    dr2_s, sig_s, dr2_l, sig_l, delta = run_T(T, reps, seed)
    fire_s = (dr2_s < 2.0).mean()
    fire_l = (dr2_l < 2.0).mean()
    bias_l = sig_l.mean() * np.sqrt(252) / true_sig_ann - 1
    bias_s = sig_s.mean() * np.sqrt(252) / true_sig_ann - 1
    print(f"\nT={T}, reps={reps}:")
    print(f"  R2 fire rate  plain sample: {fire_s:.1%}   LW shrunk: {fire_l:.1%}")
    print(f"  mean DR^2     plain sample: {dr2_s.mean():.3f} ({dr2_s.mean()/true_dr2-1:+.1%})"
          f"   LW shrunk: {dr2_l.mean():.3f} ({dr2_l.mean()/true_dr2-1:+.1%})")
    print(f"  mean sigma_p bias  plain: {bias_s:+.1%}   LW: {bias_l:+.1%}"
          f"   (LW mean sigma {sig_l.mean()*np.sqrt(252):.2%} vs true {true_sig_ann:.2%})")
    print(f"  delta: median {np.median(delta):.3f}, P(delta=1) {np.mean(delta==1.0):.1%}")

# ---------- Claim 7 fire-rate piece: EWMA(0.97), 504-day lookback, no shrinkage ----------
lam = 0.97
T7, reps7 = 504, 2000
age = np.arange(T7 - 1, -1, -1)
wt = lam**age
wt /= wt.sum()
r7 = np.random.default_rng(99)
fires, dr2s_all = [], []
chunk = 500
for c in range(reps7 // chunk):
    Z = r7.standard_normal((chunk, T7, N))
    X = Z @ Lc.T
    mu = np.einsum("t,rti->ri", wt, X)
    Xc = X - mu[:, None, :]
    Sw = np.einsum("rti,rtj->rij", Xc * wt[None, :, None], Xc)
    d, s = batch_dr2_sig(Sw, w)
    dr2s_all.append(d)
dr2_e = np.concatenate(dr2s_all)
print(f"\nClaim 7 estimator [EWMA lam=0.97, 504d lookback, demeaned, no shrink], reps={reps7}:")
print(f"  R2 fire rate: {(dr2_e < 2.0).mean():.1%}")
print(f"  mean DR^2: {dr2_e.mean():.3f} ({dr2_e.mean()/true_dr2-1:+.1%}), "
      f"SD {dr2_e.std():.3f}  (plain-T126 SD for comparison follows)")
# spread comparison at T=126 plain
dr2_s126, *_ = run_T(126, 2000, 11)
print(f"  plain-sample T=126 DR^2 SD: {dr2_s126.std():.3f}")
