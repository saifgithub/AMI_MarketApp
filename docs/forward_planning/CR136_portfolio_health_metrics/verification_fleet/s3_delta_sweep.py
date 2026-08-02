"""Claim 5: fixed-delta sweep on the TRUE twin-book Sigma, shrunk toward its own
constant-correlation target. Find where reported DR^2 crosses the 2.0 trigger."""
import numpy as np
from cr136lib import twin_book, dr2

w, Sig, R = twin_book()
N = 10
var = np.diag(Sig)
sqv = np.sqrt(var)
corr = Sig / np.outer(sqv, sqv)
rbar = (corr.sum() - N) / (N * (N - 1))
F = rbar * np.outer(sqv, sqv)
np.fill_diagonal(F, var)
d0 = dr2(w, Sig)
print(f"true DR^2 = {d0:.4f}, rbar = {rbar:.5f}")
print(f"{'delta':>6} {'DR^2':>8} {'rel bias':>9} {'fires?':>7}")
for d in [0.0, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0]:
    Sd = d * F + (1 - d) * Sig
    v = dr2(w, Sd)
    print(f"{d:>6.1f} {v:>8.4f} {v/d0-1:>+8.1%} {'yes' if v < 2.0 else 'NO':>7}")

# exact crossing (analytic on the equal-vol structure: DR^2 = 1/(w'R_d w), linear in d)
from scipy.optimize import brentq  # noqa: E402
f = lambda d: dr2(w, d * F + (1 - d) * Sig) - 2.0
try:
    x = brentq(f, 0.0, 1.0)
    print(f"exact crossing: delta* = {x:.4f}")
except Exception:
    # fallback: fine grid
    grid = np.linspace(0, 1, 100001)
    vals = np.array([dr2(w, d * F + (1 - d) * Sig) for d in grid[::100]])
    # linear denominator => solve directly
    a = w @ Sig @ w
    b = w @ F @ w
    num = (w @ np.sqrt(var)) ** 2
    # num/(a + d(b-a)) = 2 => d = (num/2 - a)/(b - a)
    print(f"analytic crossing: delta* = {(num/2 - a)/(b - a):.4f}")
