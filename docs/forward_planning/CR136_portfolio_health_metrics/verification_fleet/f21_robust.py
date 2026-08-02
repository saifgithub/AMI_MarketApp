"""F21 robustness — window sensitivity of R1 fire, risk-balanced SPY/AGG DR^2,
Ledoit-Wolf vs sample covariance on the 3-holding book."""
import numpy as np
import yfinance as yf

np.set_printoptions(precision=4, suppress=True)
TICKERS = ["SPY", "QQQ", "AAPL", "AGG"]

df = yf.download(TICKERS, start="2024-08-01", end="2026-08-01",
                 auto_adjust=True, progress=False)["Close"].dropna()
cols = list(df.columns)
rets_full = df.pct_change().dropna()
print(f"rows full={len(rets_full)}")


def metrics(rets, tickers, w, label):
    R = rets[tickers].values
    S = np.cov(R, rowvar=False, ddof=1) * 252
    w = np.asarray(w, float)
    sig = np.sqrt(np.diag(S))
    var_p = float(w @ S @ w)
    sigma_p = np.sqrt(var_p)
    dr2 = (float(w @ sig) / sigma_p) ** 2
    rc = w * (S @ w) / var_p
    print(f"{label}: sigma_p={sigma_p*100:.2f}%  DR^2={dr2:.3f}  "
          f"risk shares={dict(zip(tickers, np.round(rc*100,2)))}  "
          f"top={rc.max()*100:.2f}% -> R1 {'FIRES' if rc.max()>=0.40 else 'no fire'}")
    return dr2, rc


# 1) Window sensitivity of R1 on Book A (SPY/QQQ/AAPL equal weight)
for days, lab in [(500, "2y"), (252, "1y"), (126, "6m")]:
    metrics(rets_full.tail(days), ["SPY", "QQQ", "AAPL"], [1/3]*3,
            f"Book A window={lab} ({days}d)")

# 2) SPY/AGG: dollar 60/40 vs inverse-vol (risk-balanced) weights
R2 = rets_full[["SPY", "AGG"]].values
sig2 = np.sqrt(np.diag(np.cov(R2, rowvar=False, ddof=1) * 252))
iv = (1/sig2) / (1/sig2).sum()
print(f"\ninverse-vol weights SPY/AGG = {np.round(iv,4)}")
metrics(rets_full, ["SPY", "AGG"], [0.6, 0.4], "SPY/AGG 60/40 dollar")
metrics(rets_full, ["SPY", "AGG"], iv, "SPY/AGG inverse-vol")
# theoretical max DR^2 for 2 assets at their measured rho
rho = np.corrcoef(R2, rowvar=False)[0, 1]
print(f"measured rho(SPY,AGG)={rho:.3f}; max attainable DR^2 for 2 assets = "
      f"{2/(1+rho):.3f} (at risk-parity weights)")
rho_eq = np.corrcoef(rets_full[["SPY","QQQ","AAPL"]].values, rowvar=False)
print(f"Book A pairwise rhos: SPY-QQQ={rho_eq[0,1] if cols else 0:.3f}")

# 3) Ledoit-Wolf vs sample covariance on Book A
try:
    from sklearn.covariance import LedoitWolf
    R3 = rets_full[["SPY", "QQQ", "AAPL"]].values
    lw = LedoitWolf().fit(R3)
    S_lw = lw.covariance_ * 252
    w = np.array([1/3]*3)
    sig = np.sqrt(np.diag(S_lw))
    var_p = float(w @ S_lw @ w)
    dr2_lw = (float(w @ sig) / np.sqrt(var_p)) ** 2
    rc_lw = w * (S_lw @ w) / var_p
    print(f"\nLedoit-Wolf (shrinkage={lw.shrinkage_:.4f}): DR^2={dr2_lw:.3f}  "
          f"top risk share={rc_lw.max()*100:.2f}% -> R1 {'FIRES' if rc_lw.max()>=0.40 else 'no fire'}")
except ImportError:
    print("\nsklearn not available — LW check skipped (sample cov only)")
