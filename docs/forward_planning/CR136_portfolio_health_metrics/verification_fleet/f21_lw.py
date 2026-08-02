"""Hand-rolled Ledoit-Wolf (2004, identity-target) shrinkage check for Book A.
Verifies the spec's LW pin does not change the DR^2 / R1 conclusions at T=500, N=3."""
import numpy as np
import yfinance as yf

df = yf.download(["SPY", "QQQ", "AAPL"], start="2024-08-01", end="2026-08-01",
                 auto_adjust=True, progress=False)["Close"].dropna()
X = df.pct_change().dropna()[["SPY", "QQQ", "AAPL"]].values
T, N = X.shape
Xc = X - X.mean(0)
S = Xc.T @ Xc / T

mu = np.trace(S) / N
F = mu * np.eye(N)
d2 = np.sum((S - F) ** 2)
b2_bar = sum(np.sum((np.outer(x, x) - S) ** 2) for x in Xc) / T**2
b2 = min(b2_bar, d2)
shrink = b2 / d2
S_lw = shrink * F + (1 - shrink) * S

for name, C in [("sample", S), ("ledoit-wolf", S_lw)]:
    Ca = C * 252
    w = np.full(N, 1/3)
    sig = np.sqrt(np.diag(Ca))
    var_p = float(w @ Ca @ w)
    dr2 = (float(w @ sig) / np.sqrt(var_p)) ** 2
    rc = w * (Ca @ w) / var_p
    print(f"{name}: shrinkage={shrink:.5f}  DR^2={dr2:.4f}  "
          f"risk shares={np.round(rc*100,2)}  top={rc.max()*100:.2f}% "
          f"-> R1 {'FIRES' if rc.max() >= 0.40 else 'no fire'}")
print(f"T={T}, N={N}")
