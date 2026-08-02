"""Test the candidate fixes: (a) lowering R2 gate to n>=2/3 — false-positive check
on 50/50 SPY+AGG (uncorrelated, vol-imbalanced); (b) max-pairwise-rho rule R2b
(any pair rho >= 0.9) — hit/miss across all test books."""
import numpy as np
import yfinance as yf
from itertools import combinations

df = yf.download(["SPY", "QQQ", "AAPL", "MSFT", "AGG"], start="2024-08-01",
                 end="2026-08-01", auto_adjust=True, progress=False)["Close"].dropna()
rets = df.pct_change().dropna()


def test(tickers, w, label):
    R = rets[list(tickers)].values
    S = np.cov(R, rowvar=False, ddof=1) * 252
    C = np.corrcoef(R, rowvar=False)
    w = np.asarray(w, float)
    sig = np.sqrt(np.diag(S))
    dr2 = (float(w @ sig) / np.sqrt(w @ S @ w)) ** 2
    lowered = dr2 < 2.0 and len(tickers) >= 2
    pairs = [(tickers[i], tickers[j], C[i, j])
             for i, j in combinations(range(len(tickers)), 2)]
    hot = [(a, b, r) for a, b, r in pairs if r >= 0.9]
    print(f"{label}: DR^2={dr2:.3f}")
    print(f"   lowered-gate R2 (DR^2<2, n>=2): {'FIRES' if lowered else 'no fire'}"
          + ("   <-- FALSE POSITIVE: 'they move together' at rho="
             f"{max(r for *_, r in pairs):.3f}" if lowered and not hot else ""))
    print(f"   R2b max-pair-rho>=0.9: "
          + (", ".join(f"{a}-{b} rho={r:.3f} FIRES" for a, b, r in hot) or "no fire")
          + f"   (max pair rho={max(r for *_, r in pairs):.3f})")


test(("SPY", "AGG"), [0.5, 0.5], "50/50 SPY+AGG (diversified starter)")
test(("SPY", "AGG"), [0.6, 0.4], "60/40 SPY+AGG")
test(("SPY", "QQQ", "AAPL"), [1/3]*3, "equal-weight SPY+QQQ+AAPL (overlap)")
test(("SPY", "QQQ", "AAPL", "MSFT"), [0.25]*4, "equal-weight SPY+QQQ+AAPL+MSFT")
test(("SPY", "QQQ"), [0.5, 0.5], "50/50 SPY+QQQ (pure overlap)")
