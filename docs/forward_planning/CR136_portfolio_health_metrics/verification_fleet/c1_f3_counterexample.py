"""Claim 1 + 6: F3 counterexample — RC vs MCR ranking, per-dollar trim test.

Book: A (w=60%, vol=16%), B (w=10%, vol=55%), cash 30%, rho(A,B)=0.15.
Verifies: sigma_p, risk shares, MCR values, direct sigma_p recomputation after
trimming 1% of portfolio value from A vs from B (proceeds to cash), and the
reworded-R1 sentence's numbers.
"""
import numpy as np

sA, sB, rho = 0.16, 0.55, 0.15
Sigma = np.array([[sA*sA, rho*sA*sB, 0.0],
                  [rho*sA*sB, sB*sB, 0.0],
                  [0.0, 0.0, 0.0]])  # cash row/col = 0

def stats(w):
    var = w @ Sigma @ w
    sig = np.sqrt(var)
    Sw = Sigma @ w
    mcr = Sw / sig                    # marginal contribution d(sigma)/d(w_i)
    rc = w * Sw                       # component contribution to variance
    share = rc / var                  # risk share (sums to 1 incl. cash at 0)
    return sig, mcr, share

w0 = np.array([0.60, 0.10, 0.30])
sig0, mcr0, share0 = stats(w0)
print(f"sigma_p base           = {sig0*100:.4f}%   (claim ~11.76 / 11.7580)")
for i, name in enumerate(["A", "B", "Cash"]):
    print(f"  {name:4s} w={w0[i]*100:5.1f}%  MCR={mcr0[i]:.4f}  risk_share={share0[i]*100:6.2f}%")

print(f"\nargmax risk_share = {['A','B','Cash'][int(np.argmax(share0))]}   (claim: A, ~72.4%)")
print(f"argmax MCR        = {['A','B','Cash'][int(np.argmax(mcr0))]}   (claim: B, 0.3246 vs 0.1419)")

# trim 1% of portfolio value from A -> cash
wA = np.array([0.59, 0.10, 0.31])
sigA, _, _ = stats(wA)
dA = (sigA - sig0) * 1e4  # bp
# trim 1% of portfolio value from B -> cash
wB = np.array([0.60, 0.09, 0.31])
sigB, _, _ = stats(wB)
dB = (sigB - sig0) * 1e4

print(f"\ntrim 1% from A: sigma {sig0*100:.4f}% -> {sigA*100:.4f}%   delta = {dA:+.2f} bp  (claim -14.2)")
print(f"trim 1% from B: sigma {sig0*100:.4f}% -> {sigB*100:.4f}%   delta = {dB:+.2f} bp  (claim -31.6)")
print(f"ratio B/A effectiveness = {dB/dA:.3f}x  (claim ~2.2x)")

# Claim 6: reworded sentence on this book
print("\n--- Claim 6: reworded R1 sentence ---")
print(f'"A accounts for {share0[0]*100:.1f}% of portfolio risk while holding '
      f'{w0[0]*100:.0f}% of its value."')
print(f"  risk_share(A) computed from Euler decomposition = {share0[0]*100:.4f}% -> "
      f"statement is a definitionally true report of computed quantities")
print(f"  (note: share denominator = total variance, cash contributes 0; "
      f"weight denominator = total value incl. cash)")
print(f'MCR ranking as separate metric: MCR_B={mcr0[1]:.4f} > MCR_A={mcr0[0]:.4f} -> '
      f"names B as best per-dollar trim, matching direct recomputation "
      f"({dB:+.1f}bp vs {dA:+.1f}bp)")

# cross-check MCR against finite-difference per-dollar effect
eps = 1e-6
for i, name in enumerate(["A", "B"]):
    wp = w0.copy(); wp[i] -= eps; wp[2] += eps
    fd = (stats(wp)[0] - sig0) / (-eps)
    print(f"finite-diff d sigma/d w_{name} (to cash) = {fd:.4f}  vs MCR_{name} = {mcr0[i]:.4f}")
