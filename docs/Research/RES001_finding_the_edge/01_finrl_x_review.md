# RES001 — FinRL-X (AI4Finance): is it a usable basis for anything?

Reviewed 2026-08-30 against `master` @ last push 2026-05-02.
Repo: https://github.com/AI4Finance-Foundation/FinRL-Trading

## Verdict

**Not a fork basis, not a dependency.** Worth a couple of hours' reading for two ideas.
Don't take the code and don't cite the numbers.

## What it actually is

Not what the name says. Rewritten as **FinRL-X**, a weight-centric quant platform
(data → strategy → backtest → Alpaca execution). RL is one side module,
`src/strategies/rl_model.py`, and it is **not installable**: it imports `finrl`,
`stable_baselines3` and `gymnasium`, none of which are in `requirements.txt`.

The one good idea is the contract: `w_t = R(T(A(S(X_≤t))))` — selection, allocation, timing,
risk overlay — with a single target-weight vector as the only interface between strategy and
execution, each stage contract-preserving.

## Signal quality

| Check | Finding |
|:--|:--|
| Stars (3.6k) | **Legacy.** 2021–2024 = 19 commits total. Current code is ~5 months old (`base_strategy.py` created 2026-04-10). Stars were earned by a different codebase — the 2020 ensemble-DRL paper. |
| Freshness | Last push 2026-05-02; 55 open issues. |
| Tests | **Zero test files** across 84 files, while `pytest`, `mypy`, `black`, `flake8` all sit in requirements. It places live Alpaca orders. |
| README | Points at `examples/FinRL_Full_Workflow.ipynb` — does not exist. |
| Hygiene | 219 MB repo; a 44 MB `.7z` and a 24 MB CSV committed to git. |
| Data licensing | The committed fundamentals CSV is FMP/WRDS-derived, redistributed under Apache-2.0. |

## The performance claims

- **"62.16% annualised, Sharpe 1.96"** is a 5-month paper-trading window (+19.76% actual).
  Sharpe SE on that sample is roughly ±0.9 — indistinguishable from 0.5 or from 3.0.
- **2018–2025 backtest:** the headline "Rolling Strategy" beats QQQ by +0.12 Sharpe with a
  *worse* max drawdown (−38.95% vs −35.12%) and higher vol.
- Only **Adaptive Rotation** is interesting (Sharpe 1.10, MDD −21.5%) — but its config ships
  as `AdaptiveRotationConf_v1.2.1.yaml` / `v1.2.2.yaml`, tuned against the window that reports
  the result. In-sample.

## The best part, and its flaw

`ML_STOCK_SELECTION.md` has real point-in-time discipline: the
`datadate → tradedate → actual_tradedate → trade_price → y_return` chain, a "you cannot buy at
quarter-end because the report isn't public yet" rule, and a hard pre-run assertion that
recomputes `y_return` and fails the run on mismatch.

`run_bucket()` in `src/strategies/ml_bucket_selection.py` then undercuts it:

1. Picks best-of-8 models by **MSE on a 3-quarter validation window** — ~3 effectively
   independent observations once the market factor is removed. Selecting noise.
2. **MSE is the wrong loss for a ranking problem** — dominated by the market factor, so it
   rewards predicting "the market went up", not ranking stocks. Rank IC is the metric.
3. No walk-forward evaluation of the selection procedure, so the reported backtest is not
   reproducible from the script.

## Worth borrowing

1. **The weight-vector contract** — a typed target-weight vector as the Room's sole
   machine-readable output makes it structurally checkable rather than prompt-checkable
   (our CR038 rule). Cheapest, highest-value idea here.
2. **The point-in-time spec** — as a hard rule for fundamentals work and as BOK material.
3. **`bt` + nonlinear cost models** (their PR #86) if we ever backtest agent picks.

**Out of bounds:** the whole `src/trading/` Alpaca layer. Simulation-only is locked.

## Where it landed

The evaluation question this raised ("how would we score a weight vector?") is answered by
**CR136** — attribution and second moments, no Sharpe, sufficiency contract. The contract half
is the missing interface for **CR137**, the reserved Portfolio Room. Neither is filed off this
review; both predate it.
