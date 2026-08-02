"""Claim 6c: report-to-report R2 stability over 25 monthly reports (21-day steps),
EW-126 vs EWMA-0.97(504), with hysteresis sweep h in {0, .05, .1, .15, .2}.
Books: boundary true DR^2 = 1.8553, detection book 1.7, clean book 2.3.
Metrics: flip rate (boundary), detection rate (1.7 book), false-fire rate (2.3 book).
"""
import numpy as np
from cr136lib import twin_book, solve_rho_base_for_dr2, SIG_D

N = 10
REPS = 400
STEP, NREP = 21, 25
LOOK_EW, LOOK_EWMA = 126, 504
LAM = 0.97
TLEN = LOOK_EWMA + STEP * (NREP - 1) + 1  # 1009
THR = 2.0

books = {}
for name, tgt in [("boundary", None), ("detect_1.7", 1.7), ("clean_2.3", 2.3)]:
    if tgt is None:
        w, Sig, R = twin_book()
    else:
        rb = solve_rho_base_for_dr2(tgt)
        w, Sig, R = twin_book(rho_base=rb)
    sd = np.sqrt(np.diag(Sig))
    true_dr2 = (w @ sd) ** 2 / (w @ Sig @ w)
    eig = np.linalg.eigvalsh(R).min()
    books[name] = (w, Sig)
    print(f"book {name}: rho_base={R[0,2]:.4f}, true DR^2={true_dr2:.4f}, min eig={eig:.4f}")

age = np.arange(LOOK_EWMA - 1, -1, -1)
wt_ewma = LAM**age
wt_ewma /= wt_ewma.sum()


def batch_dr2(X, w):
    """X: (reps, T, N) window, equal-weight demeaned sample cov -> DR^2 per rep."""
    Xc = X - X.mean(axis=1, keepdims=True)
    S = np.einsum("rti,rtj->rij", Xc, Xc) / X.shape[1]
    sd = np.sqrt(np.einsum("rii->ri", S))
    return (sd @ w) ** 2 / np.einsum("rij,i,j->r", S, w, w)


def batch_dr2_ewma(X, w):
    mu = np.einsum("t,rti->ri", wt_ewma, X)
    Xc = X - mu[:, None, :]
    S = np.einsum("rti,rtj->rij", Xc * wt_ewma[None, :, None], Xc)
    sd = np.sqrt(np.einsum("rii->ri", S))
    return (sd @ w) ** 2 / np.einsum("rij,i,j->r", S, w, w)


def state_series(dr2_mat, h):
    """dr2_mat: (reps, NREP). Hysteresis state machine; report 0 = plain threshold."""
    st = np.empty_like(dr2_mat, dtype=bool)
    st[:, 0] = dr2_mat[:, 0] < THR
    for k in range(1, NREP):
        fire = dr2_mat[:, k] < THR - h
        clear = dr2_mat[:, k] > THR + h
        st[:, k] = np.where(fire, True, np.where(clear, False, st[:, k - 1]))
    return st


results = {}
for name, (w, Sig) in books.items():
    Lc = np.linalg.cholesky(Sig)
    rng = np.random.default_rng(hash(name) % 2**31)
    Z = rng.standard_normal((REPS, TLEN, N))
    X = Z @ Lc.T
    dr2_ew = np.empty((REPS, NREP))
    dr2_em = np.empty((REPS, NREP))
    for k in range(NREP):
        end = LOOK_EWMA + STEP * k
        dr2_ew[:, k] = batch_dr2(X[:, end - LOOK_EW : end, :], w)
        dr2_em[:, k] = batch_dr2_ewma(X[:, end - LOOK_EWMA : end, :], w)
    results[name] = (dr2_ew, dr2_em)
    print(f"\n{name}: DR^2 mean/SD  EW126 {dr2_ew.mean():.3f}/{dr2_ew.std():.3f}   "
          f"EWMA {dr2_em.mean():.3f}/{dr2_em.std():.3f}")
    # consecutive-report autocorrelation of DR^2
    for lbl, m in [("EW126", dr2_ew), ("EWMA", dr2_em)]:
        a = m[:, :-1].ravel(); b = m[:, 1:].ravel()
        print(f"  {lbl} consecutive-report corr: {np.corrcoef(a, b)[0,1]:.3f}")

print("\n=== hysteresis sweep ===")
hdr = f"{'h':>5} | {'est':>6} | {'flip% (boundary)':>16} | {'detect% (1.7)':>13} | {'false% (2.3)':>12}"
print(hdr); print("-" * len(hdr))
for h in [0.0, 0.05, 0.10, 0.15, 0.20]:
    for ei, lbl in [(0, "EW126"), (1, "EWMA")]:
        st_b = state_series(results["boundary"][ei], h)
        flips = (st_b[:, 1:] != st_b[:, :-1]).mean()
        st_d = state_series(results["detect_1.7"][ei], h)
        det = st_d.mean()
        st_c = state_series(results["clean_2.3"][ei], h)
        fal = st_c.mean()
        ok = "  <- PASS" if (flips < 0.10 and det >= 0.85 and fal <= 0.15) else ""
        print(f"{h:>5.2f} | {lbl:>6} | {flips:>15.1%} | {det:>12.1%} | {fal:>11.1%}{ok}")
