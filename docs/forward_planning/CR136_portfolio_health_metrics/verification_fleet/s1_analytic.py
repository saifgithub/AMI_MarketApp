"""CR136 verification — script 1: closed-form/analytic checks.
Claims: F7 algebra + table, F7 floor numbers, F12 TE identity numeric,
F13 VaR reconstruction, Lo(2002) CI + significance/power days, EWMA formulas.
"""
import numpy as np

print("=" * 72)
print("CLAIM 1 (F7) — inflation factor algebra")
print("=" * 72)
# SE(s) inflation over Gaussian = sqrt((k_excess+2)/2)
for k in [3.2, 5.2, 10.0, 30.0]:
    infl = np.sqrt((k + 2) / 2)
    print(f"  k_excess={k:5.1f}  ->  inflation = sqrt(({k}+2)/2) = {infl:.4f}x")
# invert: what k gives 1.9x?
k_from_19 = 2 * 1.9**2 - 2
print(f"  solve 1.9 = sqrt((k+2)/2)  ->  k_excess = 2*1.9^2-2 = {k_from_19:.3f}")
print(f"  review TABLE row says k=3.2 -> 1.90x; actual at 3.2: "
      f"{np.sqrt((3.2+2)/2):.3f}x  (so table row kurtosis label is wrong)")
print(f"  review TEXT says 1.9x corresponds to k ~ 5.2: "
      f"at 5.2 -> {np.sqrt((5.2+2)/2):.4f}x  (text is right)")

print()
print("=" * 72)
print("CLAIM 2 (F7) — SE floor at T=126, sigma=20%")
print("=" * 72)
T = 126
sig = 20.0  # pp annualised
se_gauss = sig / np.sqrt(2 * T)
print(f"  Gaussian SE(s) = sigma/sqrt(2T) = 20/sqrt(252) = {se_gauss:.4f} pp "
      f"({100*se_gauss/sig:.1f}% of estimate)")
for k in [3.0, 3.2, 5.2, 6.0, 10.0, 30.0]:
    infl = np.sqrt((k + 2) / 2)
    se = se_gauss * infl
    print(f"  k_excess={k:5.1f}: infl={infl:.3f}x  SE={se:.3f} pp  "
          f"= {100*se/sig:.1f}% of estimate")
print("  -> review's 5.04pp / 25.2% at k=30, and honest range at k in [3,6]:")
lo_se = se_gauss * np.sqrt((3 + 2) / 2)
hi_se = se_gauss * np.sqrt((6 + 2) / 2)
print(f"     SE in [{lo_se:.2f}, {hi_se:.2f}] pp  "
      f"= [{100*lo_se/sig:.1f}%, {100*hi_se/sig:.1f}%] of a 20% estimate")

print()
print("=" * 72)
print("CLAIM 4 (F12) — TE identity numeric check")
print("=" * 72)
# TE^2 = Var(Rp-Rb) = sp^2 + sb^2 - 2Cov(Rp,Rb); beta = Cov/sb^2 => Cov = beta*sb^2
sp, sb, beta = 26.20, 15.87, 1.301
te2 = sp**2 + sb**2 - 2 * beta * sb**2
te = np.sqrt(te2)
print(f"  sp=26.20 sb=15.87 beta=1.301")
print(f"  TE^2 = {sp**2:.2f} + {sb**2:.2f} - 2*{beta}*{sb**2:.2f} = {te2:.3f}")
print(f"  TE = {te:.4f}%   (review claims 16.82%)")
# MC consistency: build a joint Gaussian with exactly these moments and verify
rng = np.random.default_rng(42)
cov_pb = beta * (sb / 100) ** 2
Sig = np.array([[(sp / 100) ** 2, cov_pb], [cov_pb, (sb / 100) ** 2]])
X = rng.multivariate_normal([0, 0], Sig / 252, size=2_000_000)
d = X[:, 0] - X[:, 1]
te_mc = d.std(ddof=1) * np.sqrt(252) * 100
print(f"  MC check (2e6 daily draws, seed 42): sd(Rp-Rb)*sqrt(252) = {te_mc:.3f}%")
# implied correlation sanity
rho = cov_pb / ((sp / 100) * (sb / 100))
print(f"  implied corr(Rp,Rb) = {rho:.4f}  (must be <=1 for the numbers to be coherent)")

print()
print("=" * 72)
print("CLAIM 5 (F13) — parametric VaR reconstruction")
print("=" * 72)
for z, zlab in [(1.645, "z=1.645"), (1.6448536269514722, "z=exact")]:
    for sig_ann in [26.20]:
        row = []
        for h, hlab in [(1, "1d"), (5, "1w"), (21, "1mo(21d)"), (22, "1mo(22d)")]:
            var = z * (sig_ann / 100) * np.sqrt(h / 252) * 100
            row.append(f"{hlab}={var:.2f}%")
        print(f"  sigma={sig_ann}% {zlab}: " + "  ".join(row))
# what sigma exactly reproduces 2.71/6.07/12.44?
for target, h in [(2.71, 1), (6.07, 5), (12.44, 21), (12.44, 22)]:
    sig_imp = target / (1.645 * np.sqrt(h / 252))
    print(f"  implied sigma for {target}% at h={h}: {sig_imp:.2f}%")

print()
print("=" * 72)
print("CLAIM 7 — Lo (2002) SR standard errors")
print("=" * 72)
T90 = 90
SR_ann = 1.0
SR_d = SR_ann / np.sqrt(252)
SE_d = np.sqrt((1 + SR_d**2 / 2) / T90)
SE_ann = SE_d * np.sqrt(252)
z975 = 1.959963984540054
lo95 = SR_ann - z975 * SE_ann
hi95 = SR_ann + z975 * SE_ann
print(f"  T=90 daily, SR_ann=1.0: SR_d={SR_d:.6f}  SE_d={SE_d:.6f}  "
      f"SE_ann={SE_ann:.4f}")
print(f"  95% CI (z={z975}): [{lo95:.4f}, {hi95:.4f}]   (claim: [-2.28, +4.28])")
print(f"  with z=1.96: [{SR_ann-1.96*SE_ann:.4f}, {SR_ann+1.96*SE_ann:.4f}]")
# days to 95% significance (50% power): SR_d*sqrt(T) / sqrt(1+SR_d^2/2) = z
for z, zlab in [(1.959963984540054, "1.959964"), (1.96, "1.96")]:
    T_sig = z**2 * (1 + SR_d**2 / 2) / SR_d**2
    print(f"  z={zlab}: T* = z^2*(1+SR_d^2/2)/SR_d^2 = {T_sig:.3f} "
          f"-> ceil = {int(np.ceil(T_sig))} days ({T_sig/252:.2f} yrs)")
# 80% power: sqrt(T)*SR_d/sqrt(1+SR_d^2/2) = z_{.975} + z_{.80}
z80 = 0.8416212335729143
for zc, zlab in [(1.959963984540054, "1.959964"), (1.96, "1.96")]:
    T_pow = (zc + z80) ** 2 * (1 + SR_d**2 / 2) / SR_d**2
    print(f"  80% power (z_crit={zlab}, z_0.80={z80:.4f}): T = {T_pow:.2f} "
          f"-> ceil = {int(np.ceil(T_pow))} days ({T_pow/252:.2f} yrs)")
# Lo Table 1 worked example the review cites: SE=0.188 at SR=1.50, T=60
se_lo = np.sqrt((1 + 1.50**2 / 2) / 60)
print(f"  Lo Table-1 anchor: SE at SR=1.50 (per-period), T=60: {se_lo:.4f} "
      f"(review cites 0.188)")

print()
print("=" * 72)
print("CLAIM 8 — EWMA effective sample + half-life")
print("=" * 72)
for lam in [0.94, 0.96, 0.97, 0.98]:
    teff = (1 + lam) / (1 - lam)
    hl = np.log(2) / np.log(1 / lam)
    cut1 = np.log(100) / np.log(1 / lam)
    # numeric ESS check (Kish) with truncated weights
    w = lam ** np.arange(20000)
    ess = w.sum() ** 2 / (w**2).sum()
    print(f"  lam={lam}: T_eff=(1+l)/(1-l)={teff:.3f}  ESS_numeric={ess:.3f}  "
          f"half-life={hl:.2f}d  1%cutoff={cut1:.1f}d")
    # half-life numeric: weight at day h vs day 0
    h = np.log(0.5) / np.log(lam)
    print(f"           numeric: lam^{h:.2f} = {lam**h:.6f} (should be 0.5)")
