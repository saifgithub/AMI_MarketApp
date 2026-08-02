"""CR136 verification — script 3: F10 max drawdown.
(a) E[MDD] table at sigma=20% ann, driftless: MC >= 20000 paths, two conventions
    (geometric price from log-returns; arithmetic BM level) vs the continuous
    formula sqrt(pi/2)*sigma*sqrt(T).
(b) expanding-window realised MDD monotone non-decreasing.
(c) fix test: rolling 252d trailing MDD with vol 30% -> 15% at midpoint: does the
    number improve after de-risking? (expanding-window comparator cannot.)
"""
import numpy as np

rng = np.random.default_rng(136)
sig_ann = 0.20
sig_d = sig_ann / np.sqrt(252)
R = 40_000
H = 504  # 2 years of trading days

logret = rng.standard_normal((R, H)) * sig_d

def mdd_geometric(lr):
    # price path from log-returns, MDD as fractional fall from running peak
    logp = np.cumsum(lr, axis=1)
    p = np.exp(logp)
    peak = np.maximum.accumulate(np.maximum(p, 1.0), axis=1)  # include start=1
    dd = 1 - p / peak
    return dd

def mdd_arithmetic(lr):
    # treat returns as arithmetic increments; MDD in return units from peak
    lvl = np.cumsum(lr, axis=1)
    peak = np.maximum.accumulate(np.maximum(lvl, 0.0), axis=1)
    dd = peak - lvl
    return dd

dd_g = mdd_geometric(logret)
dd_a = mdd_arithmetic(logret)

print("=" * 76)
print(f"F10 (a) — E[MDD], driftless, sigma=20% ann, R={R:,} paths, seed=136")
print("=" * 76)
print(f"{'window':>8} {'days':>5} {'formula sqrt(pi/2)*s*sqrt(T)':>30} "
      f"{'MC geometric':>13} {'MC arithmetic':>14} {'review table':>13}")
review_tbl = {63: 10.4, 126: 14.8, 252: 20.7, 504: 28.2}
for h, lab in [(63, "3m"), (126, "6m"), (252, "1y"), (504, "2y")]:
    Tyr = h / 252
    formula = np.sqrt(np.pi / 2) * sig_ann * np.sqrt(Tyr)
    mc_g = dd_g[:, :h].max(axis=1).mean()
    mc_a = dd_a[:, :h].max(axis=1).mean()
    print(f"{lab:>8} {h:>5} {formula*100:>29.2f}% {mc_g*100:>12.2f}% "
          f"{mc_a*100:>13.2f}% {review_tbl[h]:>12.1f}%")

print()
print("=" * 76)
print("F10 (b) — expanding-window realised MDD is monotone non-decreasing")
print("=" * 76)
run_mdd = np.maximum.accumulate(dd_g, axis=1)  # running max of drawdown series
diffs = np.diff(run_mdd, axis=1)
print(f"  min day-over-day change of running MDD across {R:,} paths x {H-1} "
      f"days: {diffs.min():.3e}  (>= 0 -> monotone: {bool((diffs >= 0).all())})")

print()
print("=" * 76)
print("F10 (c) — FIX test: rolling 252d trailing MDD, vol 30% -> 15% at midpoint")
print("=" * 76)
R2 = 20_000
H2 = 756
switch = 378
rng2 = np.random.default_rng(137)
s_hi = 0.30 / np.sqrt(252)
s_lo = 0.15 / np.sqrt(252)
z = rng2.standard_normal((R2, H2))
lr2 = np.concatenate([z[:, :switch] * s_hi, z[:, switch:] * s_lo], axis=1)
logp = np.cumsum(lr2, axis=1)
p = np.exp(logp)

W = 252
# rolling MDD at selected checkpoints
def rolling_mdd_at(p, t, W):
    win = p[:, t - W + 1:t + 1]
    peak = np.maximum.accumulate(win, axis=1)
    return (1 - win / peak).max(axis=1)

checkpoints = [377, 503, 629, 755]  # last hi-vol day; +126; +252; +378
labels = ["end of 30%-vol regime", "126d after de-risk",
          "252d after de-risk (window all 15%)", "378d after de-risk"]
print(f"  R={R2:,} paths, seed=137, 756 days, switch at day {switch} "
      f"(0-indexed), window W=252")
base = None
for t, lab in zip(checkpoints, labels):
    m = rolling_mdd_at(p, t, W).mean()
    if base is None:
        base = m
    print(f"  mean rolling-252d MDD at day {t:>3} ({lab}): {m*100:6.2f}%")
# per-path: fraction of paths whose rolling MDD at day 755 < at day 377
r377 = rolling_mdd_at(p, 377, W)
r755 = rolling_mdd_at(p, 755, W)
frac_improved = (r755 < r377).mean()
print(f"  fraction of paths improved (day755 < day377): {frac_improved*100:.1f}%")
# expanding-window comparator on same paths
peak_full = np.maximum.accumulate(p, axis=1)
dd_full = 1 - p / peak_full
exp377 = np.maximum.accumulate(dd_full, axis=1)[:, 377].mean()
exp755 = np.maximum.accumulate(dd_full, axis=1)[:, 755].mean()
frac_exp_improved = ((np.maximum.accumulate(dd_full, axis=1)[:, 755]
                      < np.maximum.accumulate(dd_full, axis=1)[:, 377]).mean())
print(f"  expanding-window MDD: day377 mean {exp377*100:.2f}% -> day755 mean "
      f"{exp755*100:.2f}%; fraction improved: {frac_exp_improved*100:.1f}% "
      f"(ratchet: can never improve)")
# theoretical reference: E[MDD] for 252d window at 30% and 15%
for s in [0.30, 0.15]:
    print(f"  reference formula at sigma={int(s*100)}%, T=1y: "
          f"{np.sqrt(np.pi/2)*s*100:.2f}% (continuous, arithmetic)")
