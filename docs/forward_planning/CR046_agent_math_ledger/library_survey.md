# Library survey — financial-math build vs. adopt (CR046 Decision D1)

**Kept on purpose.** Saiful: *"keep the library list; when we expand we look at it again."* Before
adding any new calculation to the ledger, re-read this to decide hand-roll vs. adopt. Survey run
2026-07-20 (AT:R62); re-verify licenses/maintenance before acting on it later — these facts drift.

## Ground truth on our side
`app/trading_math/indicators.py::rsi` (ported from `services/technicals.py`, DEF052) computes RSI as
a **simple average of gains/losses over 14 periods** — this is **Cutler's RSI**, not Wilder's. Every
mainstream TA library defaults to **Wilder's smoothing** (SMMA/RMA), which produces different numbers
(EMA/Wilder RSI overshoots Cutler by 5–10 points during fast moves). So adopting any indicator lib
for RSI means re-baselining `tests/unit/test_technicals.py`. Our SMA/trend/volume/support logic is
trivial closed-form and matches everyone.

## Comparison — indicator libraries

| Library | Covers | Dependency weight | License | Maintenance | RSI vs ours |
|---|---|---|---|---|---|
| **TA-Lib** | RSI, SMA, EMA, MACD, BBands +150 | C-extension; since v0.6.5 pip ships binary wheels bundling the C lib, but still a compiled binary dep | BSD-2 ✅ | Very active | Wilder ✗ |
| **ta** (bukosabino) | RSI, SMA, EMA, MACD, BBands + | pandas+numpy, pure-Python → ~zero marginal cost (we already ship both) | MIT ✅ | Active-ish | Wilder ✗ |
| **pandas-ta** | RSI, EMA, MACD, BBands +130 | pandas+numpy pure-Python (optional TA-Lib accel) | MIT ✅ | Original repo threatened archival Jul 2026; active fork `pandas-ta-classic` | Wilder (RMA) ✗ |
| **finta** | RSI, MACD, BBands | pandas, pure-Python | **LGPLv3+** ⚠️ | Dormant (2021) | Wilder ✗ |
| **stockstats** | RSI, MACD, BBands | pandas wrapper | BSD-3 ✅ | Active | Wilder/SMMA ✗ |
| **tulipy** | RSI, SMA, EMA, MACD, BBands +100 | C-extension (Cython→Tulip C); wheels spotty | **LGPLv3** ⚠️ | Unmaintained | Wilder ✗ |

## Comparison — portfolio / risk / returns libraries

| Library | Covers (of our backlog) | Dependency weight | License | Maintenance | Verdict |
|---|---|---|---|---|---|
| **empyrical-reloaded** | **Sharpe, Sortino, max_drawdown, CAGR, Calmar, vol, alpha/beta, VaR** | numpy+pandas+**scipy** (only new dep; manylinux wheels, no system lib) | Apache-2.0 ✅ | Active (v0.5.12, Jun 2025) | **CLEAR WIN** |
| empyrical (original) | same | same | Apache-2.0 ✅ | Stale (Quantopian dead) | use -reloaded |
| **quantstats** | metrics + HTML tearsheets | +matplotlib (heavy) | Apache-2.0 ✅ | Active | overkill for headless |
| **ffn** | returns, drawdown, CAGR, Sharpe | pandas+numpy+scipy(+matplotlib) | MIT ✅ | Healthy | fine, empyrical leaner |
| **pyfolio-reloaded** | tearsheets (wraps empyrical) | heavy (matplotlib) | Apache-2.0 ✅ | Active | overkill |
| **numpy-financial** | IRR/NPV/PMT — none of our needs | numpy only | BSD ✅ | Active | irrelevant |
| **QuantLib** | derivatives/fixed-income pricing | huge C++/SWIG | BSD-3 ✅ | Active | CLEAR NO (scope + friction) |
| **riskfolio-lib** | portfolio optimization | heavy (cvxpy) | BSD-3 ✅ | Active | NO |
| **PyPortfolioOpt** | mean-variance optimization | cvxpy | MIT ✅ | Active | NO (our caps are policy, not optimization) |
| **vectorbt** | backtesting engine | numba (heavy) | **Apache-2.0 + Commons Clause** ⛔ | Active | **NO — Commons Clause restricts commercial resale; license risk for a paid app** |
| **bt** (pmorissette) | backtesting framework | pandas | MIT ✅ | Active | NO (we don't backtest) |

**Bespoke, no library primitive exists:** position-level "drawdown contribution" (size% × stop-dist%)
and per-tier single-name % caps. These are our safety math (M02) + product policy (M03).

## Recommendation per need-family
1. **Live indicators (RSI/SMA/trend/volume/support) — HAND-ROLL (kept).** ~40 lines of pure, tested,
   deterministic Python; Wilder mismatch kills any adopt for zero gain.
2. **Backlog indicators (EMA, MACD, Bollinger) — HAND-ROLL**, or wrap **`ta`** (MIT, pure pandas/numpy
   we already ship) for *new* indicators only if the backlog grows — never route RSI through it.
3. **Return/risk metrics (Sharpe, max drawdown, CAGR, vol, Sortino, Calmar) — ADOPT
   `empyrical-reloaded`** (Apache-2.0; only new dep is scipy). The clear win; edge-case annualization
   isn't worth re-deriving. *If the backlog is literally only Sharpe+maxDD+CAGR, those are ~30 lines
   each and hand-rollable to honor "no new deps" — take empyrical the moment Sortino/Calmar/VaR land.*
4. **win-rate + realized/unrealized P&L — HAND-ROLL** (trivial, over our own fills; not in empyrical).
5. **Drawdown-contribution + per-tier caps — HAND-ROLL (kept).** No library primitive.

**Net:** hand-roll the indicator layer, adopt `empyrical-reloaded` for the returns/risk backlog, keep
drawdown-contribution and sizing caps bespoke. One new dependency total (empyrical-reloaded → scipy),
permissively licensed, no C system libs — **pending Saiful's dep sign-off**.

## Sources
TA-Lib (PyPI) · ta bukosabino (MIT) · pandas-ta / pandas-ta-classic fork · finta (LGPL, Snyk) ·
stockstats · tulipy (LGPL) · empyrical-reloaded (Apache-2.0) · quantstats · ffn (MIT) ·
pyfolio-reloaded · numpy-financial · QuantLib-SWIG · riskfolio-lib · PyPortfolioOpt (MIT) ·
vectorbt (Commons Clause license) · bt (MIT) · Cutler's vs Wilder's RSI (rsimonitor.com).
