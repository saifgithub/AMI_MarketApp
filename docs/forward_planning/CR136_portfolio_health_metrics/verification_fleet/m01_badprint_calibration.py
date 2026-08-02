"""Measure a volatility-scaled bad-print bound on real market data.

Rev 4 pins the hygiene screen as "a same-day |return| exceeding a
volatility-scaled bound with next-day reversal". The shipped M01 detector used a
flat 40%, which the audit confirmed is ~196 daily sigma on a low-vol holding.
This measures what k (sigma multiplier) and floor actually behave correctly:

  (a) ZERO fires on clean real series, including crash windows;
  (b) detection of an injected phantom print at the magnitudes the reviews name.
"""
from __future__ import annotations

import statistics
import sys

import yfinance as yf

MAD_TO_SIGMA = 1.4826


def robust_sigma(returns: list[float]) -> float:
    if len(returns) < 3:
        return 0.0
    med = statistics.median(returns)
    mad = statistics.median([abs(r - med) for r in returns])
    return MAD_TO_SIGMA * mad


def returns_of(closes: list[float]) -> list[float]:
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]


def detect(closes: list[float], k: float, floor: float, hard: float,
           reversal: float) -> list[int]:
    """Candidate algorithm: MAD-scaled sigma, price-basis reversal."""
    n = len(closes)
    if n < 3:
        return []
    rs = returns_of(closes)
    sigma = robust_sigma(rs)
    bound = max(k * sigma, floor)
    flagged = []
    for i in range(1, n):
        prev, cur = closes[i - 1], closes[i]
        if not (prev > 0.0 and cur > 0.0):
            flagged.append(i)
            continue
        r = cur / prev - 1.0
        if abs(r) > hard:
            flagged.append(i)
            continue
        if abs(r) > bound and i + 1 < n:
            nxt = closes[i + 1]
            move = cur - prev
            undone = (cur - nxt) / move if move != 0.0 else 0.0
            if undone >= reversal:
                flagged.append(i)
    return flagged


BASKET = [
    ("SPY", "large-cap index"), ("AAPL", "mega-cap"), ("NVDA", "high-beta"),
    ("TSLA", "very high vol"), ("BND", "bond ETF"), ("AGG", "bond ETF"),
    ("XLU", "utilities"), ("KO", "staple"), ("JNJ", "staple"),
    ("GLD", "gold"), ("SMCI", "volatile small/mid"), ("PFE", "pharma"),
]
WINDOWS = [("2024-08-01", "2026-08-01", "recent 2y"),
           ("2019-08-01", "2021-08-01", "COVID crash window"),
           ("2021-08-01", "2023-08-01", "2022 drawdown window")]


def main() -> int:
    k = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    floor = float(sys.argv[2]) if len(sys.argv) > 2 else 0.10
    hard, reversal = 1.00, 0.60
    print(f"candidate: k={k} sigma, floor={floor:.2%}, hard={hard:.0%}, "
          f"reversal>={reversal:.0%} of the price move\n")

    total_fires = 0
    worst = []
    for start, end, label in WINDOWS:
        print(f"── {label} ({start} → {end}) ──")
        for ticker, note in BASKET:
            try:
                df = yf.Ticker(ticker).history(start=start, end=end, interval="1d")
            except Exception as exc:
                print(f"  {ticker:6s} fetch failed: {exc}")
                continue
            if df is None or df.empty:
                print(f"  {ticker:6s} no data")
                continue
            closes = [float(v) for v in df["Close"].tolist()]
            rs = returns_of(closes)
            sig = robust_sigma(rs)
            mx = max(abs(r) for r in rs)
            sigmas = mx / sig if sig > 0 else float("inf")
            fires = detect(closes, k, floor, hard, reversal)
            total_fires += len(fires)
            worst.append((sigmas, ticker, label, mx, sig))
            flag = f"  FIRES={fires}" if fires else ""
            print(f"  {ticker:6s} {note:22s} n={len(closes):4d} "
                  f"sigma_robust={sig*100:5.2f}%/d  max|r|={mx*100:6.2f}% "
                  f"({sigmas:5.1f} sigma)  bound={max(k*sig, floor)*100:5.2f}%{flag}")
        print()

    print(f"TOTAL FALSE FIRES ON CLEAN REAL DATA: {total_fires}")
    worst.sort(reverse=True)
    print("largest real moves by sigma:")
    for s, t, w, mx, sig in worst[:5]:
        print(f"  {t} {w}: {mx*100:.2f}% = {s:.1f} sigma (sigma={sig*100:.2f}%/d)")

    # ── Injection test: phantom print + full reversal, on the recent window.
    print("\n── injected phantom print (full price round trip) ──")
    for ticker, note in [("BND", "bond ETF"), ("XLU", "utilities"),
                         ("KO", "staple"), ("SPY", "index"), ("TSLA", "very high vol")]:
        df = yf.Ticker(ticker).history(start="2024-08-01", end="2026-08-01", interval="1d")
        closes = [float(v) for v in df["Close"].tolist()]
        sig = robust_sigma(returns_of(closes))
        line = [f"  {ticker:6s} sigma={sig*100:5.2f}%/d bound={max(k*sig, floor)*100:5.2f}%  "]
        for pct in (0.10, 0.15, 0.20, 0.30, 0.40, 0.80):
            probe = list(closes)
            idx = len(probe) // 2
            probe[idx] = probe[idx - 1] * (1.0 + pct)
            probe[idx + 1] = probe[idx - 1]          # exact round trip
            caught = idx in detect(probe, k, floor, hard, reversal)
            line.append(f"{int(pct*100)}%:{'HIT ' if caught else 'miss'} ")
        print("".join(line))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
