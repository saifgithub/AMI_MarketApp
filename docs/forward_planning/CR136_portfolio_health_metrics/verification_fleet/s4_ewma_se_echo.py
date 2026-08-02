"""Claims 6a + 6b: EWMA effective sample size / standard error, and the
rolling-window echo test (shock-exit discontinuity) EW-126 vs EWMA-0.97."""
import numpy as np

ANN = 252
SIG = 0.20
SIG_D = SIG / np.sqrt(ANN)
LAM = 0.97

# ---------- 6a: effective sample size and SE ----------
print("=== Claim 6a: EWMA effective sample size and SE ===")
ess_inf = (1 + LAM) / (1 - LAM)
for T in (504, 252, 126):
    age = np.arange(T)
    wt = LAM**age
    wt /= wt.sum()
    ess = 1.0 / np.sum(wt**2)
    cov = 1 - LAM**T
    print(f"T={T}: ESS = {ess:.2f}, weight coverage 1-lam^T = {cov:.4f}")
print(f"analytic (1+lam)/(1-lam) = {ess_inf:.2f}")

reps = 100_000
rng = np.random.default_rng(2026)


def measure_se(T, weights):
    sds = []
    chunk = 20_000
    done = 0
    while done < reps:
        n = min(chunk, reps - done)
        X = rng.standard_normal((n, T)) * SIG_D
        mu = X @ weights
        Xc = X - mu[:, None]
        var = np.einsum("rt,t,rt->r", Xc, weights, Xc)
        sds.append(np.sqrt(var))
        done += n
    s = np.concatenate(sds) * np.sqrt(ANN)
    return s.mean(), s.std()


# equal-weight T=126
w_eq = np.full(126, 1 / 126)
m_eq, se_eq = measure_se(126, w_eq)
# EWMA T=504
age = np.arange(503, -1, -1)
w_ew = LAM**age
w_ew /= w_ew.sum()
m_ew, se_ew = measure_se(504, w_ew)

ess_504 = 1.0 / np.sum(w_ew**2)
pred_eq = SIG / np.sqrt(2 * 126)
pred_ew = SIG / np.sqrt(2 * ess_504)
print(f"\nMC ({reps} reps, sigma = {SIG:.0%} ann):")
print(f"  equal-weight T=126: mean sigma_hat {m_eq:.4%}, SE {se_eq:.4%} "
      f"(analytic sigma/sqrt(2T) = {pred_eq:.4%})")
print(f"  EWMA 0.97, 504d:    mean sigma_hat {m_ew:.4%}, SE {se_ew:.4%} "
      f"(analytic sigma/sqrt(2*ESS) = {pred_ew:.4%})")
print(f"  measured SE ratio EWMA/EW = {se_ew/se_eq:.3f} "
      f"(claim ~1.40; analytic sqrt(126/ESS) = {np.sqrt(126/ess_504):.3f})")

# ---------- 6b: echo test ----------
print("\n=== Claim 6b: echo test, 600 days, one -8% day at t=300 ===")
Tt, shock_day, shock = 600, 300, -0.08
win = 126


def roll_vol_eq(r):
    out = np.full(Tt, np.nan)
    for t in range(win - 1, Tt):
        seg = r[t - win + 1 : t + 1]
        out[t] = np.sqrt(np.mean((seg - seg.mean()) ** 2) * ANN)
    return out


def roll_vol_ewma(r):
    out = np.full(Tt, np.nan)
    look = 504
    for t in range(win - 1, Tt):
        seg = r[max(0, t - look + 1) : t + 1]
        n = len(seg)
        wts = LAM ** np.arange(n - 1, -1, -1)
        wts /= wts.sum()
        mu = wts @ seg
        out[t] = np.sqrt(np.sum(wts * (seg - mu) ** 2) * ANN)
    return out


exit_day = shock_day + win  # first day the window no longer contains the shock
r1 = np.random.default_rng(5).standard_normal(Tt) * SIG_D
r1s = r1.copy(); r1s[shock_day] = shock
v_eq = roll_vol_eq(r1s); v_eqc = roll_vol_eq(r1)
v_ew = roll_vol_ewma(r1s)
print(f"single path (seed 5): EW vol day {exit_day-1} -> {exit_day}: "
      f"{v_eq[exit_day-1]:.4%} -> {v_eq[exit_day]:.4%} "
      f"(drop {(v_eq[exit_day]-v_eq[exit_day-1])*100:+.2f} pp)")
dd_cf = np.abs(np.diff(v_eqc[win:]))
print(f"  no-shock counterfactual median |daily change|: {np.median(dd_cf)*100:.4f} pp "
      f"-> exit jump = {abs(v_eq[exit_day]-v_eq[exit_day-1])/np.median(dd_cf):.0f}x median")
d_ew = np.abs(np.diff(v_ew[shock_day + 5:]))
print(f"  EWMA(0.97) after shock settles: max |daily change| t>{shock_day+5}: "
      f"{d_ew.max()*100:.3f} pp; at EW-exit day: "
      f"{abs(v_ew[exit_day]-v_ew[exit_day-1])*100:.4f} pp")

# systematic exit-day drop over 500 reps
drops, ew_at_exit = [], []
rng2 = np.random.default_rng(77)
for _ in range(500):
    r = rng2.standard_normal(Tt) * SIG_D
    r[shock_day] = shock
    seg_a = r[exit_day - win : exit_day]      # window that day, shock excluded
    seg_b = r[exit_day - 1 - win + 1 : exit_day]  # previous day window, shock included
    va = np.sqrt(np.mean((seg_a - seg_a.mean()) ** 2) * ANN)
    vb = np.sqrt(np.mean((seg_b - seg_b.mean()) ** 2) * ANN)
    drops.append(va - vb)
drops = np.array(drops)
print(f"500 reps: mean exit-day drop = {drops.mean()*100:+.2f} pp "
      f"(SD {drops.std()*100:.2f} pp)  [claim ~ -3 pp]")
