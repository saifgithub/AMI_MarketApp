"""Deliverable: derive R1's hysteresis band (pp) at the 40% risk-share threshold.

Same machinery as the R3 derivation: 25 monthly reports, 126-day sample-cov
windows stepped 21 days over one 630-day multivariate series (shared innovations).
Book: N=25 single-factor (as claim-5 setup A), top weight 30%; top asset's idio
vol tuned by bisection so TRUE top-contributor share hits each grid value.
Gates on the sampled top share s_hat (max component share, Euler decomposition):
  point: s_hat >= 40
  hysteresis(b): fire at >= 40+b pp, clear at < 40-b pp, else hold.
Criterion: worst-case flip rate < 10% across grid AND detection >= 85% 'just
above threshold' (defined as threshold + ~1.7 sd, mirroring beta=1.45 = 1.3+1.67*SE;
with sd ~2.2pp that is ~43.7% -> tested at the 44% grid point).
"""
import numpy as np

T, STEP, N_WIN = 126, 21, 25
TOTAL = T + (N_WIN - 1) * STEP
REPS = 600
N = 25
THR = 40.0
sig_f = 0.16

r0 = np.random.default_rng(42)  # same as claim-5 setup A
betas = np.clip(r0.normal(1.0, 0.20, N), 0.5, 1.6)
idio_base = r0.uniform(0.18, 0.35, N)
w = np.full(N, 0.70/(N-1)); w[0] = 0.30

def true_top_share(top_idio):
    idio = idio_base.copy(); idio[0] = top_idio
    S = np.outer(betas, betas)*sig_f**2 + np.diag(idio**2)
    rc = w * (S @ w) / (w @ S @ w)
    return rc.max()*100, S

def tune(target):
    lo, hi = 0.05, 2.5
    for _ in range(60):
        mid = 0.5*(lo+hi)
        s, _ = true_top_share(mid)
        if s < target: lo = mid
        else: hi = mid
    s, S = true_top_share(0.5*(lo+hi))
    return s, S, 0.5*(lo+hi)

def run_grid_point(S_true, seed):
    Ld = np.linalg.cholesky(S_true/252.0)
    r = np.random.default_rng(seed)
    shares = np.empty((REPS, N_WIN))
    for rep in range(REPS):
        X = r.normal(0, 1, (TOTAL, N)) @ Ld.T
        for j in range(N_WIN):
            Xi = X[j*STEP:j*STEP+T]
            Sc = np.cov(Xi, rowvar=False)
            rc = w * (Sc @ w) / (w @ Sc @ w)
            shares[rep, j] = rc.max()*100
    return shares

def gate_hyst(sh, b):
    reps, n = sh.shape
    state = np.zeros((reps, n), dtype=bool)
    cur = np.zeros(reps, dtype=bool)
    for j in range(n):
        cur = np.where(sh[:, j] >= THR + b, True,
              np.where(sh[:, j] < THR - b, False, cur))
        state[:, j] = cur
    return state

def summarize(state):
    return state.mean()*100, (state[:, 1:] != state[:, :-1]).mean()*100

targets = [36, 38, 40, 42, 43, 44, 46]
bands = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]

results, sds = {}, {}
for i, tgt in enumerate(targets):
    s_true, S_true, ti = tune(tgt)
    sh = run_grid_point(S_true, 500+i)
    sds[tgt] = sh.std(ddof=1)
    row = {}
    for b in bands:
        row[b] = summarize(gate_hyst(sh, b))
    results[tgt] = (s_true, row)
    print(f"true share {s_true:5.2f}% (top idio {ti*100:.0f}%): per-window sd of s_hat = {sh.std(ddof=1):.2f}pp")

print(f"\nreps={REPS}, reports={N_WIN}, T={T}, step={STEP}, N={N}, top weight 30%")
print("\nfires% / flips% by true share and band (b=0 is the point gate):")
print(f"{'true':>6} | " + " | ".join(f"b={b:>3}pp" for b in bands))
for tgt in targets:
    s_true, row = results[tgt]
    print(f"{s_true:6.2f} | " + " | ".join(f"{row[b][0]:5.1f}/{row[b][1]:4.1f}" for b in bands))

print("\nCriterion (worst flip <10% anywhere on grid AND detection >=85% at true share ~44%):")
for b in bands:
    worst = max(results[t][1][b][1] for t in targets)
    det = results[44][1][b][0]
    ok = worst < 10 and det >= 85
    print(f"  b={b}pp: worst flip={worst:.1f}%  detection@44%={det:.1f}%  -> {'PASS' if ok else 'FAIL'}")
