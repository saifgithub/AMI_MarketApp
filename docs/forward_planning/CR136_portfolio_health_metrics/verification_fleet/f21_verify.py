"""F21 verification — do covariance-based CR136 metrics already see ETF overlap?

Fetches ~2y daily adjusted closes (SPY, QQQ, AAPL, MSFT, NVDA, AGG) via yfinance,
then computes for each test book: correlation matrix, annualized portfolio vol,
diversification ratio DR and DR^2, risk contributions (w_i*(Sigma w)_i / sigma_p^2),
HHI effective-N, beta vs SPY + R^2, and evaluates the CR136 rule engine
(R1 risk_share>=40%, R2 DR^2<2 AND n>=8, R3 beta>=1.3 AND R2>=0.2, R4 cash>=40%).

Falls back to a synthetic calibrated panel (seed=136) if network fetch fails.
"""
import sys
import numpy as np

np.set_printoptions(precision=4, suppress=True)

TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AGG"]
START, END = "2024-08-01", "2026-08-01"


def fetch_real():
    import yfinance as yf
    for attempt in range(3):
        try:
            df = yf.download(TICKERS, start=START, end=END, auto_adjust=True,
                             progress=False)["Close"]
            df = df.dropna()
            if len(df) > 400:
                return df
            print(f"attempt {attempt}: only {len(df)} rows", file=sys.stderr)
        except Exception as e:
            print(f"attempt {attempt} failed: {e}", file=sys.stderr)
    return None


def annualized_stats(rets):
    """rets: DataFrame-like 2D array of daily simple returns, cols = tickers."""
    cov_d = np.cov(rets, rowvar=False, ddof=1)
    vol_a = np.sqrt(np.diag(cov_d) * 252)
    corr = np.corrcoef(rets, rowvar=False)
    return cov_d * 252, vol_a, corr


def book_metrics(name, tickers, weights, cov_a, vols, corr, all_tickers,
                 spy_rets=None, book_rets=None, cash=0.0):
    idx = [all_tickers.index(t) for t in tickers]
    w = np.asarray(weights, dtype=float)
    S = cov_a[np.ix_(idx, idx)]
    sig = vols[idx]
    var_p = float(w @ S @ w)
    sigma_p = np.sqrt(var_p)
    dr = float(w @ sig) / sigma_p
    dr2 = dr * dr
    mcr = S @ w                       # marginal covar
    rc = w * mcr / var_p              # risk contributions, sum to 1
    hhi = float(np.sum(w ** 2))
    eff_n = 1.0 / hhi
    print(f"\n=== {name} ===")
    print(f"holdings n = {len(tickers)}, weights = {dict(zip(tickers, np.round(w,4)))}")
    sub = corr[np.ix_(idx, idx)]
    print("correlation matrix:")
    hdr = "        " + "".join(f"{t:>8}" for t in tickers)
    print(hdr)
    for i, t in enumerate(tickers):
        print(f"{t:>8}" + "".join(f"{sub[i,j]:8.3f}" for j in range(len(tickers))))
    print(f"annualized vols: {dict(zip(tickers, np.round(sig,4)))}")
    print(f"portfolio vol (ann) = {sigma_p:.4f} ({sigma_p*100:.2f}%)")
    print(f"DR = {dr:.4f}   DR^2 (effective independent bets) = {dr2:.4f}")
    print(f"HHI = {hhi:.4f}   HHI effective-N (weights) = {eff_n:.4f}")
    print("risk contributions (share of portfolio variance):")
    for t, r in zip(tickers, rc):
        print(f"  {t:>6}: {r*100:6.2f}%   (weight {w[tickers.index(t)]*100:.2f}%)")
    beta = r2 = None
    if spy_rets is not None and book_rets is not None:
        b, a = np.polyfit(spy_rets, book_rets, 1)
        resid = book_rets - (b * spy_rets + a)
        r2 = 1 - resid.var(ddof=0) / book_rets.var(ddof=0)
        beta = b
        print(f"beta vs SPY = {beta:.4f}   R^2 = {r2:.4f}")
    # ---- CR136 rule engine ----
    top_rs = float(rc.max())
    r1 = top_rs >= 0.40
    r2_rule = (dr2 < 2.0) and (len(tickers) >= 8)
    r3 = (beta is not None) and (beta >= 1.3) and (r2 >= 0.2)
    r4 = cash >= 0.40
    print("rule engine:")
    print(f"  R1 concentration (top risk_share>=40%): top={top_rs*100:.2f}% -> {'FIRES' if r1 else 'no fire'}")
    print(f"  R2 cluster (DR^2<2.0 AND n>=8): DR^2={dr2:.3f}, n={len(tickers)} -> {'FIRES' if r2_rule else 'no fire'}"
          + ("   [DR^2<2.0 is TRUE but n>=8 gate blocks]" if dr2 < 2.0 and len(tickers) < 8 else ""))
    if beta is not None:
        print(f"  R3 beta band (b>=1.3 AND R^2>=0.2): b={beta:.3f}, R^2={r2:.3f} -> {'FIRES' if r3 else 'no fire'}")
    print(f"  R4 cash drag (cash>=40%): cash={cash*100:.0f}% -> {'FIRES' if r4 else 'no fire'}")
    return dict(sigma_p=sigma_p, dr2=dr2, eff_n=eff_n, rc=dict(zip(tickers, rc)),
                top_rs=top_rs, beta=beta, r2=r2)


def main():
    df = fetch_real()
    synthetic = df is None
    if synthetic:
        print("!! NETWORK FETCH FAILED — synthetic calibrated panel (seed=136) !!")
        rng = np.random.default_rng(136)
        n = 502
        # calibrated: rho(SPY,QQQ)=.95 rho(SPY,AAPL)=.75 rho(QQQ,AAPL)=.85 ...
        vols_d = np.array([0.13, 0.18, 0.28, 0.24, 0.45, 0.06]) / np.sqrt(252)
        C = np.array([
            [1.00, 0.95, 0.75, 0.75, 0.70, 0.10],
            [0.95, 1.00, 0.80, 0.80, 0.78, 0.05],
            [0.75, 0.80, 1.00, 0.70, 0.60, 0.00],
            [0.75, 0.80, 0.70, 1.00, 0.62, 0.00],
            [0.70, 0.78, 0.60, 0.62, 1.00, 0.00],
            [0.10, 0.05, 0.00, 0.00, 0.00, 1.00]])
        L = np.linalg.cholesky(C)
        rets = (rng.standard_normal((n, 6)) @ L.T) * vols_d
        cols = TICKERS
    else:
        cols = list(df.columns)
        rets = df.pct_change().dropna().values
        print(f"REAL DATA: {len(rets)} daily returns, {df.index[0].date()} -> {df.index[-1].date()}")
        print(f"columns: {cols}")

    cov_a, vols, corr = annualized_stats(rets)
    spy = rets[:, cols.index("SPY")]

    def book_series(tickers, weights):
        idx = [cols.index(t) for t in tickers]
        return rets[:, idx] @ np.asarray(weights)

    # Book A — the review's poster child
    tA = ["SPY", "QQQ", "AAPL"]
    wA = [1/3, 1/3, 1/3]
    A = book_metrics("BOOK A: equal-weight SPY+QQQ+AAPL", tA, wA, cov_a, vols,
                     corr, cols, spy, book_series(tA, wA))

    # Book A' — richer 5-asset single-cluster book
    tA5 = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]
    wA5 = [0.2] * 5
    A5 = book_metrics("BOOK A5: equal-weight SPY+QQQ+AAPL+MSFT+NVDA", tA5, wA5,
                      cov_a, vols, corr, cols, spy, book_series(tA5, wA5))

    # Book B — genuinely diversified ETF book
    tB = ["SPY", "AGG"]
    wB = [0.6, 0.4]
    B = book_metrics("BOOK B: 60% SPY + 40% AGG", tB, wB, cov_a, vols, corr,
                     cols, spy, book_series(tB, wB))

    # ---- Look-through AAPL exposure (hardcoded index weights, see source note) ----
    # Approx AAPL weight: SPY ~6.9% (S&P500 cap-weight, mid-2025 SSGA fund page),
    # QQQ ~8.7% (Nasdaq-100, Invesco fund page, mid-2025). Book A equal weight.
    for w_spy_aapl, w_qqq_aapl, label in [(0.069, 0.087, "base"),
                                          (0.06, 0.08, "low"),
                                          (0.07, 0.09, "high")]:
        lt = 1/3 + (1/3) * w_spy_aapl + (1/3) * w_qqq_aapl
        print(f"\nLook-through AAPL exposure ({label}: SPY {w_spy_aapl*100:.1f}%, QQQ {w_qqq_aapl*100:.1f}%):"
              f" {lt*100:.2f}% vs naive 33.33% -> understated by {(lt-1/3)*100:.2f}pp"
              f" ({(lt/(1/3)-1)*100:.1f}% relative)")

    # Look-through effective single-name check vs typical mandate cap
    print("\nWeight-based single-name view: AAPL = 33.33% (naive) — a 35% cap would NOT trip;"
          " look-through ~38.5% WOULD trip. A 40% cap misses both.")

    # ---- summary deltas ----
    print("\n===== SUMMARY =====")
    print(f"data source: {'SYNTHETIC calibrated' if synthetic else 'REAL yfinance'}")
    print(f"Book A  (SPY/QQQ/AAPL): DR^2={A['dr2']:.3f} vs HHI eff-N={A['eff_n']:.2f}"
          f" | top risk share={A['top_rs']*100:.1f}% | beta={A['beta']:.3f}")
    print(f"Book A5 (5-name):       DR^2={A5['dr2']:.3f} vs HHI eff-N={A5['eff_n']:.2f}"
          f" | top risk share={A5['top_rs']*100:.1f}%")
    print(f"Book B  (SPY/AGG):      DR^2={B['dr2']:.3f} vs HHI eff-N={B['eff_n']:.2f}"
          f" | top risk share={B['top_rs']*100:.1f}%")


if __name__ == "__main__":
    main()
