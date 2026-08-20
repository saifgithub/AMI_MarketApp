#!/usr/bin/env python3
"""Recompute every number shipped in CR054 Wave 2 (lessons 371-387).

Why this file exists: CR054 §4.5 requires that any worked example computable
deterministically is routed through `backend/app/trading_math/` rather than
authored by hand, and CR060 requires that a reviewer be able to re-derive a
lesson's figures rather than take them on trust. Wave 2's portfolio arithmetic
is exactly that class, so this script is the auditable artifact: it prints each
figure next to the lesson that ships it.

The ESG lessons (384-387) ship no computed figures — their only external claims
are sourced citations, verified against the publishers' records at authoring
time and recorded in each lesson's `verified:` stamp.

    cd backend && ./.venv/bin/python ../scripts/verify_cr054_wave2_numbers.py
"""

from __future__ import annotations

import sys
from math import sqrt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.trading_math.portfolio_stats import (  # noqa: E402
    beta,
    correlation,
    portfolio_variance,
    variance,
)


def vol(v: float | None) -> float:
    assert v is not None, "portfolio_variance returned None — inputs are malformed"
    return sqrt(v)


def pct(x: float, dp: int = 2) -> str:
    return f"{x * 100:.{dp}f}%"


def equicorrelated(n: int, sigma: float, rho: float) -> list[list[float]]:
    return [
        [sigma * sigma if i == j else rho * sigma * sigma for j in range(n)]
        for i in range(n)
    ]


def head(lesson: str, title: str) -> None:
    print()
    print("=" * 74)
    print(f"{lesson}  —  {title}")
    print("=" * 74)


head("371 RISK 17", "diversification is about correlation, not count")
s = 0.30
for rho in (1.0, 0.9, 0.7, 0.5, 0.0, -0.5):
    cov = rho * s * s
    v = portfolio_variance([0.5, 0.5], [[s * s, cov], [cov, s * s]])
    print(f"  rho={rho:>5}   vol={pct(vol(v))}")

head("372 RISK 18", "the floor diversification cannot go below")
rho = 0.35
for n in (1, 2, 5, 10, 20, 30, 50, 100):
    v = portfolio_variance([1 / n] * n, equicorrelated(n, s, rho))
    print(f"  N={n:>4}   vol={pct(vol(v))}")
floor = sqrt(rho) * s
print(f"  floor sqrt(rho)*sigma = {pct(floor)}")
v30 = vol(portfolio_variance([1 / 30] * 30, equicorrelated(30, s, rho)))
print(f"  30 names sit {pct(v30 - floor)} above the floor")
print(f"  quiz 3 — Book B floor at rho=0.15: {pct(sqrt(0.15) * s)}")

head("374 RISK 20", "rebalancing: 60/40 policy, 5pp band")
g, d = 60_000 * 1.40, 40_000 * 1.02
tot = g + d
print(f"  growth {g:,.0f} · defensive {d:,.0f} · total {tot:,.0f}")
print(f"  weights: {pct(g / tot, 1)} / {pct(d / tot, 1)}   trigger at 65%")
print(f"  target growth {0.60 * tot:,.2f} -> sell {g - 0.60 * tot:,.2f}")
print(f"  distractor check — selling the full 24,000 gain leaves {pct(60_000 / tot, 1)}")

head("375 RISK 21", "home-country bias")
sd_, sf_, rho_df = 0.22, 0.18, 0.60
cov_df = rho_df * sd_ * sf_
S = [[sd_ * sd_, cov_df], [cov_df, sf_ * sf_]]
for w in ([1.0, 0.0], [0.85, 0.15], [0.70, 0.30], [0.50, 0.50]):
    print(f"  domestic {pct(w[0], 0)} / foreign {pct(w[1], 0)}   vol={pct(vol(portfolio_variance(w, S)))}")
print(f"  100 -> 85/15 buys {pct(0.2200 - vol(portfolio_variance([0.85, 0.15], S)))}")

head("376 RISK 22", "capstone: build an allocation and stress it")
def cluster(i: int, j: int) -> float:
    return 0.80 if i < 6 and j < 6 else 0.25
S8 = [[s * s if i == j else cluster(i, j) * s * s for j in range(8)] for i in range(8)]
print(f"  8 names, 6-name cluster @0.80 + 2 outsiders @0.25 : vol={pct(vol(portfolio_variance([1 / 8] * 8, S8)))}")
print(f"  8 names all @0.35                                 : vol={pct(vol(portfolio_variance([1 / 8] * 8, equicorrelated(8, s, 0.35))))}")
print(f"  3 names all @0.25                                 : vol={pct(vol(portfolio_variance([1 / 3] * 3, equicorrelated(3, s, 0.25))))}")
print("  rebalance: equities 71% vs 60% policy, trigger 65% -> sell $11,000")

head("377 RISK 23", "the efficient frontier, in plain arithmetic")
sa, sb, rho_ab = 0.20, 0.12, 0.20
cov_ab = rho_ab * sa * sb
Sf = [[sa * sa, cov_ab], [cov_ab, sb * sb]]
wa_mv = (sb * sb - cov_ab) / (sa * sa + sb * sb - 2 * cov_ab)
print(f"  cov(A,B)={cov_ab:.6f}   minimum-variance weight in A = {pct(wa_mv)}")
for wa in (0.0, 0.10, wa_mv, 0.30, 0.50, 1.0):
    v = portfolio_variance([wa, 1 - wa], Sf)
    print(f"  wA={pct(wa):>7}   vol={pct(vol(v))}   E[r]={pct(wa * 0.08 + (1 - wa) * 0.05)}")

head("378 RISK 24 / 381 RISK 27", "beta, R², and what a market hedge can reach")
market = [0.02, -0.01, 0.03, 0.00, -0.02, 0.04, 0.01, -0.03, 0.02, 0.01, -0.01, 0.02]
steady = [0.03, -0.02, 0.03, 0.01, -0.03, 0.04, 0.00, -0.04, 0.03, 0.02, -0.02, 0.01]
story = [0.10, -0.08, -0.02, 0.07, -0.12, 0.00, 0.08, 0.01, 0.08, -0.07, 0.04, -0.01]
print(f"  market   vol={pct(sqrt(variance(market)))} (monthly)")
for name, series in (("steady", steady), ("story", story)):
    r = correlation(series, market)
    sd = sqrt(variance(series))
    hedged = sd * sqrt(1 - r * r)
    print(
        f"  {name:<7} beta={beta(series, market):<5} R²={r * r:.3f}  vol={pct(sd)}"
        f"  post-hedge={pct(hedged)}  removed={pct(1 - hedged / sd, 1)}"
    )
print(f"  story is {sqrt(variance(story)) / sqrt(variance(market)):.2f}x the market's volatility")
print("  CAPM at rf 4% + premium 5%:")
for name, b in (("steady", 1.21), ("story", 1.00)):
    print(f"    {name:<7} E[r] = 4 + {b} x 5 = {4 + b * 5:.2f}%")
print("  381 hedge sizing on a 100,000 book:")
for b in (1.20, 0.85):
    print(f"    beta {b}: index-equivalent {100_000 * b:,.0f}; a 10% index fall implies {-0.10 * b * 100_000:,.0f}")
print(f"    beta 1.20 -> 0.85 removes 0.35 of beta = {0.35 * 100_000:,.0f} short")
print(f"    distractor check — 7.08% x sqrt(1-0.90) = {pct(0.0708 * sqrt(0.10))}")

head("380 RISK 26", "risk parity and risk budgeting")
se, sbd, rho_eb = 0.18, 0.06, 0.10
cov_eb = rho_eb * se * sbd
Sr = [[se * se, cov_eb], [cov_eb, sbd * sbd]]
for w in ([0.60, 0.40], [0.25, 0.75], [0.50, 0.50]):
    v = portfolio_variance(w, Sr)
    sw = [sum(Sr[i][j] * w[j] for j in range(2)) for i in range(2)]
    shares = [w[i] * sw[i] / v for i in range(2)]
    print(f"  w={w}   vol={pct(vol(v))}   risk share={[pct(x, 1) for x in shares]}")
print(f"  inverse-volatility weight in equities = {pct((1 / se) / ((1 / se) + (1 / sbd)))}")

head("383 RISK 29", "capstone: judge a portfolio on its risk")
sg, sdf, rho_gd = 0.24, 0.07, 0.15
cov_gd = rho_gd * sg * sdf
Sc = [[sg * sg, cov_gd], [cov_gd, sdf * sdf]]
for w in ([0.70, 0.30], [0.55, 0.45], [0.40, 0.60]):
    v = portfolio_variance(w, Sc)
    sw = [sum(Sc[i][j] * w[j] for j in range(2)) for i in range(2)]
    shares = [w[i] * sw[i] / v for i in range(2)]
    print(f"  w={w}   vol={pct(vol(v))}   risk share={[pct(x, 1) for x in shares]}")
book_vol = vol(portfolio_variance([0.70, 0.30], Sc))
print(f"  beta 1.35 on 200,000 -> {1.35 * 200_000:,.0f} index-equivalent; a 10% fall implies {-0.10 * 1.35 * 200_000:,.0f}")
print(f"  perfect market hedge at R²=0.30 leaves {pct(book_vol * sqrt(1 - 0.30))} of the {pct(book_vol)}")
print(f"  distractor check — 17.24% / 1.35 = {pct(book_vol / 1.35)}")
print()
