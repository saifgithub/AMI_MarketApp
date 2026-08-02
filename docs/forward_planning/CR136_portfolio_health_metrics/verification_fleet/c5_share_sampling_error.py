"""Claim 5 adjudication: sampling error of TOP RISK-CONTRIBUTOR SHARE.

Operating point A (both reviews' T/N=5 point): N=25, T=126, top weight 30%,
single-factor structure, 2000 draws. EXTERNAL claims sd ~1.9pp, 95% half-width
~±3.6pp; PM_REVIEW claims 'plausibly ±15-20pp'.
Also: N=10 book, and a twin-heavy book (5-name correlated block at rho~0.9).
"""
import numpy as np

DRAWS = 2000
T = 126
sig_f = 0.16  # factor annual vol

def build_single_factor(N, seed, top_idio=None):
    r = np.random.default_rng(seed)
    betas = np.clip(r.normal(1.0, 0.20, N), 0.5, 1.6)
    idio = r.uniform(0.18, 0.35, N)  # annual idio vol, large-cap-ish
    if top_idio is not None:
        idio[0] = top_idio
    Sigma = np.outer(betas, betas) * sig_f**2 + np.diag(idio**2)
    return Sigma, betas, idio

def top_share_stats(Sigma, w, draws, seed, label):
    N = len(w)
    Sd = Sigma / 252.0
    L = np.linalg.cholesky(Sd)
    r = np.random.default_rng(seed)
    var_true = w @ Sigma @ w
    rc_true = w * (Sigma @ w) / var_true
    true_top_idx = int(np.argmax(rc_true))
    true_top = rc_true[true_top_idx]

    tops = np.empty(draws)
    same_id = np.zeros(draws, dtype=bool)
    for d in range(draws):
        X = r.normal(0, 1, (T, N)) @ L.T
        S = np.cov(X, rowvar=False)
        rc = w * (S @ w) / (w @ S @ w)
        tops[d] = rc.max()
        same_id[d] = int(np.argmax(rc)) == true_top_idx
    lo, hi = np.percentile(tops, [2.5, 97.5])
    print(f"\n{label}")
    print(f"  true top share = {true_top*100:.1f}%  (asset {true_top_idx}, weight {w[true_top_idx]*100:.1f}%)")
    print(f"  sampled top share: mean {tops.mean()*100:.2f}%  sd {tops.std(ddof=1)*100:.2f}pp")
    print(f"  95% range [{lo*100:.1f}%, {hi*100:.1f}%]  half-width ±{(hi-lo)/2*100:.2f}pp")
    print(f"  top-contributor identity stable in {same_id.mean()*100:.1f}% of draws")
    return tops.std(ddof=1)*100

# --- A: both reviews' exact operating point: N=25, T=126, top weight 30% ---
N = 25
Sigma, _, _ = build_single_factor(N, 42)
w = np.full(N, 0.70/(N-1)); w[0] = 0.30
top_share_stats(Sigma, w, DRAWS, 1, f"A) N=25, T=126, top weight 30%, single-factor (T/N={T/N:.1f})")

# --- B: N=10, top weight 30% ---
N = 10
Sigma10, _, _ = build_single_factor(N, 43)
w10 = np.full(N, 0.70/(N-1)); w10[0] = 0.30
top_share_stats(Sigma10, w10, DRAWS, 2, f"B) N=10, T=126, top weight 30% (T/N={T/N:.1f})")

# --- C: twin-heavy: N=25, assets 0-4 are near-twins (same beta, idio corr 0.9) ---
N = 25
r = np.random.default_rng(44)
betas = np.clip(r.normal(1.0, 0.20, N), 0.5, 1.6)
idio = r.uniform(0.18, 0.35, N)
betas[:5] = 1.1
idio[:5] = 0.28
Sigma_tw = np.outer(betas, betas) * sig_f**2 + np.diag(idio**2)
# idio correlation 0.9 inside the twin block
for i in range(5):
    for j in range(5):
        if i != j:
            Sigma_tw[i, j] += 0.9 * idio[i] * idio[j]
wtw = np.full(N, 0.70/(N-1)); wtw[0] = 0.30
ev = np.linalg.eigvalsh(Sigma_tw)
assert ev.min() > 0, "twin Sigma not PD"
top_share_stats(Sigma_tw, wtw, DRAWS, 3, "C) twin-heavy: N=25, top 30% + 4 twins (idio rho 0.9), T=126")

# --- D: extreme small book N=5, top 30%, T/N=25 -- and N=25 with T=63 (T/N=2.5) ---
Sigma5, _, _ = build_single_factor(5, 45)
w5 = np.full(5, 0.70/4); w5[0] = 0.30
top_share_stats(Sigma5, w5, DRAWS, 4, "D1) N=5, T=126, top weight 30%")

T = 63
Sigma, _, _ = build_single_factor(25, 42)
w = np.full(25, 0.70/24); w[0] = 0.30
top_share_stats(Sigma, w, DRAWS, 5, f"D2) N=25, T=63 (T/N={63/25:.1f}), top weight 30%")
