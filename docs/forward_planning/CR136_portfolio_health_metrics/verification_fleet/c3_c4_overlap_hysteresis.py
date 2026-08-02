"""Claims 3 + 4: overlapping monthly windows — flip rates, gating strategies, band sweep.

25 consecutive monthly reports: 126-day OLS beta windows stepped 21 days over one
630-day series (shared innovations). Gates compared:
  (a) point estimate >= 1.3
  (b) 90% CI lower bound > 1.3 (beta_hat - 1.645*SE_hat > 1.3)
  (c) hysteresis: fire at 1.3 + k*SE_hat, clear at 1.3 - k*SE_hat, else hold state
Fire rate = mean fraction of 25 reports in fired state; flip rate = mean fraction
of 24 consecutive pairs whose state changes.
Same DGP as claim 2 (sig_e set so SE(beta_hat) ~= 0.090 at T=126).
"""
import numpy as np

rng = np.random.default_rng(20260803)
T, STEP, N_REP_WIN = 126, 21, 25
TOTAL = T + (N_REP_WIN - 1) * STEP  # 630
REPS = 2000
THR = 1.3
sig_m = 0.16 / np.sqrt(252)
sig_e = 0.090 * sig_m * np.sqrt(T)

def run_beta_paths(beta, reps, seed):
    r = np.random.default_rng(seed)
    rm = r.normal(0, sig_m, (reps, TOTAL))
    rp = beta * rm + r.normal(0, sig_e, (reps, TOTAL))
    bh = np.empty((reps, N_REP_WIN)); se = np.empty((reps, N_REP_WIN))
    for j in range(N_REP_WIN):
        s = j * STEP
        x = rm[:, s:s+T]; y = rp[:, s:s+T]
        xc = x - x.mean(axis=1, keepdims=True)
        yc = y - y.mean(axis=1, keepdims=True)
        sxx = (xc**2).sum(axis=1)
        b = (xc*yc).sum(axis=1) / sxx
        res = yc - b[:, None]*xc
        se[:, j] = np.sqrt((res**2).sum(axis=1)/(T-2)/sxx)
        bh[:, j] = b
    return bh, se

def gate_point(bh, se):
    return bh >= THR

def gate_ci(bh, se):
    return (bh - 1.645*se) > THR

def gate_hyst(bh, se, k):
    reps, n = bh.shape
    state = np.zeros((reps, n), dtype=bool)
    cur = np.zeros(reps, dtype=bool)
    for j in range(n):
        fire_on = bh[:, j] >= THR + k*se[:, j]
        fire_off = bh[:, j] < THR - k*se[:, j]
        cur = np.where(fire_on, True, np.where(fire_off, False, cur))
        state[:, j] = cur
    return state

def summarize(state):
    fire = state.mean()
    flips = (state[:, 1:] != state[:, :-1]).mean()
    return fire*100, flips*100

betas = [1.00, 1.15, 1.30, 1.45, 1.60]
ks = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0]

results = {}
for i, beta in enumerate(betas):
    bh, se = run_beta_paths(beta, REPS, 100+i)
    row = {"point": summarize(gate_point(bh, se)),
           "ci": summarize(gate_ci(bh, se))}
    for k in ks:
        row[f"hyst{k}"] = summarize(gate_hyst(bh, se, k))
    results[beta] = row

print(f"reps={REPS}, reports/rep={N_REP_WIN}, T={T}, step={STEP}, "
      f"SE target 0.090\n")
print("CLAIM 3: point-estimate flip rate at true beta=1.30 "
      f"= {results[1.30]['point'][1]:.1f}%  (claim ~18%)\n")

print("CLAIM 4 table (fires% / flips%):")
hdr = f"{'beta':>5} | {'point':>13} | {'CI-lower':>13} | " + " | ".join(f"hyst k={k:>3}" for k in ks)
print(hdr)
for beta in betas:
    r = results[beta]
    cells = [f"{r['point'][0]:5.1f}/{r['point'][1]:4.1f}", f"{r['ci'][0]:5.1f}/{r['ci'][1]:4.1f}"]
    cells += [f"{r[f'hyst{k}'][0]:5.1f}/{r[f'hyst{k}'][1]:4.1f}" for k in ks]
    print(f"{beta:5.2f} | " + " | ".join(f"{c:>13}" if i<2 else c for i, c in enumerate(cells)))

print("\nCriterion check (worst-case flip <10% across beta grid AND detection>=85% at beta=1.45):")
for k in ks:
    worst_flip = max(results[b][f"hyst{k}"][1] for b in betas)
    det = results[1.45][f"hyst{k}"][0]
    ok = worst_flip < 10 and det >= 85
    print(f"  k={k}: worst flip={worst_flip:.1f}%  detection@1.45={det:.1f}%  -> {'PASS' if ok else 'FAIL'}")
p_worst = max(results[b]["point"][1] for b in betas)
c_worst = max(results[b]["ci"][1] for b in betas)
print(f"  point: worst flip={p_worst:.1f}%  detection@1.45={results[1.45]['point'][0]:.1f}%")
print(f"  CI:    worst flip={c_worst:.1f}%  detection@1.45={results[1.45]['ci'][0]:.1f}%")
