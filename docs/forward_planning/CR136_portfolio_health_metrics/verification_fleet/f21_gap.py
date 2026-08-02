"""Which overlapping ETF books evade EVERY specced rule? 50/50 SPY+QQQ and
equal-weight SPY+QQQ+AAPL+MSFT, real data, full rule sweep incl. R3 beta."""
import numpy as np
import yfinance as yf

df = yf.download(["SPY", "QQQ", "AAPL", "MSFT"], start="2024-08-01",
                 end="2026-08-01", auto_adjust=True, progress=False)["Close"].dropna()
rets = df.pct_change().dropna()
spy = rets["SPY"].values


def book(tickers, w, label):
    R = rets[list(tickers)].values
    S = np.cov(R, rowvar=False, ddof=1) * 252
    w = np.asarray(w, float)
    sig = np.sqrt(np.diag(S))
    var_p = float(w @ S @ w)
    sigma_p = np.sqrt(var_p)
    dr2 = (float(w @ sig) / sigma_p) ** 2
    rc = w * (S @ w) / var_p
    p = R @ w
    beta, a = np.polyfit(spy, p, 1)
    r2 = 1 - (p - (beta * spy + a)).var() / p.var()
    n = len(tickers)
    fires = []
    if rc.max() >= 0.40: fires.append(f"R1({tickers[rc.argmax()]} {rc.max()*100:.1f}%)")
    if dr2 < 2.0 and n >= 8: fires.append("R2")
    if beta >= 1.3 and r2 >= 0.2: fires.append("R3")
    print(f"{label}: n={n} DR^2={dr2:.3f} HHI-effN={1/np.sum(w**2):.2f} "
          f"sigma_p={sigma_p*100:.2f}% beta={beta:.3f} R^2={r2:.3f}")
    print(f"   risk shares={dict(zip(tickers, np.round(rc*100,1)))}")
    print(f"   rules fired: {fires if fires else 'NONE — book passes clean'}")


book(("SPY", "QQQ"), [0.5, 0.5], "50/50 SPY+QQQ (near-total overlap, rho=0.952)")
book(("SPY", "QQQ", "AAPL", "MSFT"), [0.25]*4, "equal-weight SPY+QQQ+AAPL+MSFT")
book(("SPY", "QQQ", "AAPL"), [1/3]*3, "equal-weight SPY+QQQ+AAPL (reference)")
