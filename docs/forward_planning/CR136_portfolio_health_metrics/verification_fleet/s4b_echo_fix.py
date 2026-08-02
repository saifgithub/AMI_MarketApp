"""Claim 6b follow-up: corrected 500-rep systematic exit-day drop, and a clean
EWMA no-discontinuity metric (shock-attributable vol delta: shocked minus unshocked)."""
import numpy as np

ANN = 252
SIG_D = 0.20 / np.sqrt(ANN)
LAM = 0.97
Tt, shock_day, shock, win = 600, 300, -0.08, 126
exit_day = shock_day + win  # 426: first day window [t-125, t] excludes day 300

# systematic EW exit-day drop over 500 reps (windows fixed: inclusive of day t)
rng2 = np.random.default_rng(77)
drops = []
for _ in range(500):
    r = rng2.standard_normal(Tt) * SIG_D
    r[shock_day] = shock
    seg_prev = r[exit_day - win : exit_day]       # day 425 window = days 300..425
    seg_exit = r[exit_day - win + 1 : exit_day + 1]  # day 426 window = days 301..426
    vp = np.sqrt(np.mean((seg_prev - seg_prev.mean()) ** 2) * ANN)
    ve = np.sqrt(np.mean((seg_exit - seg_exit.mean()) ** 2) * ANN)
    drops.append(ve - vp)
drops = np.array(drops)
print(f"EW-126 exit-day drop, 500 reps: mean {drops.mean()*100:+.2f} pp, "
      f"SD {drops.std()*100:.2f} pp, range [{drops.min()*100:+.2f}, {drops.max()*100:+.2f}] pp")

# EWMA: shock-attributable component = vol(shocked path) - vol(unshocked path), same noise
def ewma_vol_path(r):
    out = np.full(Tt, np.nan)
    for t in range(win - 1, Tt):
        seg = r[max(0, t - 504 + 1) : t + 1]
        n = len(seg)
        wts = LAM ** np.arange(n - 1, -1, -1)
        wts /= wts.sum()
        mu = wts @ seg
        out[t] = np.sqrt(np.sum(wts * (seg - mu) ** 2) * ANN)
    return out

r = np.random.default_rng(5).standard_normal(Tt) * SIG_D
rs = r.copy(); rs[shock_day] = shock
dv = ewma_vol_path(rs) - ewma_vol_path(r)  # shock-attributable elevation
d_at = lambda t: (dv[t] - dv[t - 1]) * 100
print(f"\nEWMA(0.97) shock-attributable vol elevation (shocked - unshocked, same noise):")
print(f"  entry day 300: jump {d_at(shock_day):+.2f} pp (responds AT the event)")
print(f"  elevation: day 301 {dv[301]*100:+.2f} pp -> day 425 {dv[425]*100:+.2f} pp "
      f"-> day 426 {dv[426]*100:+.2f} pp -> day 599 {dv[599]*100:+.2f} pp")
print(f"  change at EW-exit day 426: {d_at(exit_day):+.4f} pp  <- no discontinuity")
print(f"  max |daily change| of elevation after day 305: "
      f"{np.max(np.abs(np.diff(dv[shock_day+5:])))*100:.4f} pp")
# half-life check for lambda=0.97 (vol elevation decays as lam^(dt/2) roughly)
hl = np.log(0.5) / np.log(LAM)
print(f"  variance half-life ln(.5)/ln(lam) = {hl:.1f} days")
# same shock-attributable metric for EW-126: the jump at exit is the discontinuity
def ew_vol_path(r):
    out = np.full(Tt, np.nan)
    for t in range(win - 1, Tt):
        seg = r[t - win + 1 : t + 1]
        out[t] = np.sqrt(np.mean((seg - seg.mean()) ** 2) * ANN)
    return out
dve = ew_vol_path(rs) - ew_vol_path(r)
print(f"\nEW-126 shock-attributable elevation: day 425 {dve[425]*100:+.2f} pp -> "
      f"day 426 {dve[426]*100:+.2f} pp (one-day cliff {((dve[426]-dve[425]))*100:+.2f} pp)")
