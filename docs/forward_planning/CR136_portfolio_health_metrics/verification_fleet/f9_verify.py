"""F9 verification — risk-vs-money visual as a cash artefact + invested-sleeve fix.

Verifies EXTERNAL_PM_REVIEW.md F9 claims by direct computation:
  1. cash widens the (risk share - total-value money share) gap while risk shares,
     DR^2 are invariant and sigma_p scales linearly with invested fraction
  2. HHI effective-N over total value (cash as position, DEF149) is non-monotone in cash
  3. the fix (invested-sleeve money share) makes the gap cash-invariant; Euler
     risk shares on sleeve == on total book
  4. exactly which metrics cash dilutes (sigma_p, beta yes; DR^2, risk shares, R^2 no)
  5. screen encoding survival: common scale/origin, diversifier (risk<money) case,
     negative-RC case the bar chart cannot draw
All numbers printed are computed here; fixed seed for the simulated-returns leg.
"""
import numpy as np

np.set_printoptions(precision=6, suppress=True)

# ---------------------------------------------------------------- sleeve construction
# Review's book (reverse-engineered): 3-name sleeve, sleeve weights 50/30/20
#   -> HHI at 0% cash = 0.38 -> eff-N 2.63 matches the review exactly.
# Tune (sigma1, rho1x) so top-holding sleeve risk share ~ 79.3% and sigma_sleeve ~ 27.20%.
v = np.array([0.50, 0.30, 0.20])          # invested-sleeve weights
s23 = 0.20                                 # vols of names 2,3
r23 = 0.30                                 # corr(2,3)

def sleeve_stats(sig1, rho):
    sig = np.array([sig1, s23, s23])
    C = np.array([[1.0, rho, rho], [rho, 1.0, r23], [rho, r23, 1.0]])
    S = np.outer(sig, sig) * C
    var = v @ S @ v
    rc = v * (S @ v) / var                 # Euler risk shares (sum to 1)
    return np.sqrt(var), rc, S, sig

best = None
for sig1 in np.arange(0.30, 0.70, 0.0005):
    for rho in np.arange(0.0, 0.9, 0.0025):
        sp, rc, S, sig = sleeve_stats(sig1, rho)
        err = abs(rc[0] - 0.793) + abs(sp - 0.2720)
        if best is None or err < best[0]:
            best = (err, sig1, rho, sp, rc, S, sig)
err, sig1, rho, sig_sleeve, rc_sleeve, S3, sig3 = best
print("=== Sleeve (3 names, sleeve weights 50/30/20) ===")
print(f"tuned: sigma1={sig1:.4f}, sigma2=sigma3={s23}, rho(1,2)=rho(1,3)={rho:.4f}, rho(2,3)={r23}")
print(f"sigma_sleeve = {sig_sleeve*100:.2f}%   (review: 27.20%)")
print(f"sleeve risk shares = {rc_sleeve*100}   top = {rc_sleeve[0]*100:.1f}%  (review: 79.3%)")
DR2_sleeve = ((v @ sig3) / sig_sleeve) ** 2
print(f"DR^2 (sleeve) = {DR2_sleeve:.4f}")

# ---------------------------------------------------------------- total-book machinery
def total_book(cash_frac):
    """weights over TOTAL value, cash appended as zero-vol row (CR136 pin + DEF149)."""
    w = np.append(v * (1 - cash_frac), cash_frac)
    S = np.zeros((4, 4)); S[:3, :3] = S3
    sig = np.append(sig3, 0.0)
    return w, S, sig

def metrics(cash_frac):
    w, S, sig = total_book(cash_frac)
    var = w @ S @ w
    sp = np.sqrt(var)
    contrib = w * (S @ w)                              # Euler numerators
    rs = contrib / var                                 # risk shares (incl cash row)
    dr2 = ((w @ sig) / sp) ** 2
    hhi = np.sum(w ** 2)                               # cash as a position (DEF149)
    return sp, rs, dr2, hhi, w

print("\n=== Claim 1: cash sweep, TOTAL-VALUE money share vs risk share ===")
print("cash |  sigma_p | top risk share | top money(TOTAL) | gap(pp) | DR^2   | all risk shares")
rows = {}
for c in (0.0, 0.20, 0.40, 0.60):
    sp, rs, dr2, hhi, w = metrics(c)
    gap = (rs[0] - w[0]) * 100
    rows[c] = (sp, rs.copy(), dr2, hhi, w.copy())
    print(f"{int(c*100):3d}% | {sp*100:7.2f}% | {rs[0]*100:13.1f}% | {w[0]*100:15.1f}% | {gap:+6.1f} | {dr2:.4f} | {np.round(rs*100,4)}")

sp0 = rows[0.0][0]
print("\n(b) sigma_p linear in invested fraction: sigma_p(c)/sigma_p(0) vs (1-c):")
for c in (0.20, 0.40, 0.60):
    print(f"  c={c:.2f}: ratio={rows[c][0]/sp0:.12f}  (1-c)={1-c:.2f}  diff={rows[c][0]/sp0-(1-c):.2e}")
print("(c) DR^2 invariance: max |DR^2(c)-DR^2(0)| =",
      max(abs(rows[c][2] - rows[0.0][2]) for c in rows))
print("(d) risk-share invariance (risky names): max |rs(c)-rs(0)| =",
      max(np.max(np.abs(rows[c][1][:3] - rows[0.0][1][:3])) for c in rows))
print("    cash row risk share at every c:", [f"{rows[c][1][3]:.2e}" for c in rows])
print("    Euler sum at every c:", [f"{np.sum(rows[c][1]):.12f}" for c in rows])

print("\n=== Claim 2: HHI effective-N over TOTAL value (cash as position) ===")
for c in (0.0, 0.20, 0.40, 0.60):
    print(f"  cash={int(c*100):2d}%: eff-N = {1/rows[c][3]:.2f}   (review: "
          f"{ {0.0:'2.63',0.2:'3.53',0.4:'3.37',0.6:'2.38'}[c] })")
cs = np.linspace(0, 0.99, 991)
effn = np.array([1/np.sum(np.append(v*(1-c), c)**2) for c in cs])
c_peak = cs[np.argmax(effn)]
print(f"  fine sweep: eff-N peaks at cash={c_peak*100:.1f}% (eff-N={effn.max():.3f}) -> rises then falls: NON-MONOTONE")
print(f"  analytic turning point c* = 0.76/2.76 = {0.76/2.76*100:.1f}%")

print("\n=== Claim 3: the FIX — risk share vs INVESTED-SLEEVE money share ===")
print("cash | top risk share | top money(INVESTED) | gap(pp)")
for c in (0.0, 0.20, 0.40, 0.60):
    rs = rows[c][1]
    inv_money = v[0]                                   # invested-sleeve share, cash-free
    print(f"{int(c*100):3d}% | {rs[0]*100:13.1f}% | {inv_money*100:18.1f}% | {(rs[0]-inv_money)*100:+6.1f}")

# Euler referral: risk shares on invested sleeve alone == on total book
sp_s, rc_s, _, _ = sleeve_stats(sig1, rho)
print("sleeve-computed risk shares:", np.round(rc_s*100, 8))
print("total-book risk shares (any c, risky rows), c=0.40:", np.round(rows[0.40][1][:3]*100, 8))
print("max |sleeve rs - total-book rs| over all c:",
      max(np.max(np.abs(rows[c][1][:3] - rc_s)) for c in rows))

# gap reflects concentration, not cash: a more balanced sleeve
v_bal = np.array([1/3, 1/3, 1/3])
def gap_for(vw, cash):
    w = np.append(vw*(1-cash), cash)
    S = np.zeros((4,4)); S[:3,:3] = S3
    var = w @ S @ w
    rs = (w * (S @ w) / var)[:3]
    top = np.argmax(rs)
    return (rs[top] - vw[top]) * 100
print("balanced sleeve (1/3 each), invested-basis top gap across cash 0/20/40/60%:",
      [f"{gap_for(v_bal, c):+.2f}pp" for c in (0,0.2,0.4,0.6)])
print("concentrated sleeve invested-basis top gap across cash:",
      [f"{gap_for(v, c):+.2f}pp" for c in (0,0.2,0.4,0.6)])

print("\n=== Claim 4: which metrics does cash actually dilute? (simulated, seed=136) ===")
rng = np.random.default_rng(136)
T = 126
sig_b = 0.18 / np.sqrt(252)                            # daily benchmark vol
betas = np.array([1.6, 0.9, 0.7])
rb = rng.normal(0, sig_b, T)
idio = rng.normal(0, 1, (T, 3)) * (np.array([0.30, 0.12, 0.10]) / np.sqrt(252))
ra = rb[:, None] * betas + idio                        # asset daily returns
r_sleeve = ra @ v
def ols(y, x):
    b = np.cov(y, x, ddof=1)[0, 1] / np.var(x, ddof=1)
    r2 = np.corrcoef(y, x)[0, 1] ** 2
    return b, r2
print("cash | beta_hat | beta/beta0 | (1-c) | R^2     | ann vol")
b0 = None
for c in (0.0, 0.20, 0.40, 0.60):
    rp = (1 - c) * r_sleeve                            # cash earns 0
    b, r2 = ols(rp, rb)
    vol = np.std(rp, ddof=1) * np.sqrt(252)
    if b0 is None: b0 = b
    print(f"{int(c*100):3d}% | {b:8.4f} | {b/b0:10.6f} | {1-c:.2f} | {r2:.6f} | {vol*100:6.2f}%")
print("-> beta scales EXACTLY with invested fraction; R^2 exactly invariant.")

print("\n=== Claim 5: screen encoding with invested-sleeve money shares ===")
rs = rc_s
print("solid (risk) bars:  ", np.round(rs*100, 2), " sum:", f"{np.sum(rs)*100:.4f}%")
print("outline (money) bars:", np.round(v*100, 2), " sum:", f"{np.sum(v)*100:.4f}%")
print("both in [0,100], both sum to 100 -> common scale + origin: OK")

# diversifier: 4th name, low vol, slightly negative corr to the dominant name
v4 = np.array([0.45, 0.25, 0.15, 0.15])
sig4 = np.array([sig1, s23, s23, 0.15])
C4 = np.array([[1.0,  rho,  rho, -0.10],
               [rho,  1.0,  r23,  0.00],
               [rho,  r23,  1.0,  0.00],
               [-0.10, 0.0,  0.0,  1.00]])
S4 = np.outer(sig4, sig4) * C4
var4 = v4 @ S4 @ v4
rs4 = v4 * (S4 @ v4) / var4
print("\ndiversifier book (name4: w=15%, vol=15%, rho=-0.10 to top):")
for i,(m,r) in enumerate(zip(v4, rs4)):
    tag = "  <-- risk share < money share (diversifier)" if r < m and i == 3 else ""
    print(f"  name{i+1}: money {m*100:5.1f}%  risk {r*100:6.2f}%{tag}")

# hedge: strong negative corr -> negative RC
C5 = C4.copy(); C5[0,3] = C5[3,0] = -0.60
sig5 = sig4.copy(); sig5[3] = 0.30
S5 = np.outer(sig5, sig5) * C5
var5 = v4 @ S5 @ v4
rs5 = v4 * (S5 @ v4) / var5
print("\nhedge book (name4: w=15%, vol=30%, rho=-0.60 to top):")
for i,(m,r) in enumerate(zip(v4, rs5)):
    print(f"  name{i+1}: money {m*100:5.1f}%  risk {r*100:7.2f}%")
print(f"  sum of risk shares: {np.sum(rs5)*100:.2f}%  max single share: {np.max(rs5)*100:.2f}%")
print("  -> negative solid bar + a share >100% possible: bar chart must define both")

print("\n=== edge: 100% cash ===")
w = np.append(v*0.0, 1.0); S = np.zeros((4,4)); S[:3,:3] = S3
var = w @ S @ w
print(f"sigma_p = {np.sqrt(var):.6f}; invested-sleeve shares are 0/0 -> UNDEFINED, needs an explicit empty-state gate")
