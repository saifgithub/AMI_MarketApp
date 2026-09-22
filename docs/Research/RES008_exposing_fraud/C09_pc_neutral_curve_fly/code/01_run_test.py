"""
C09 main test runner. Builds all four arms (PC-neutral fly, naive spread,
random-entry placebo, buy-and-hold) over DEFINE+HOLDOUT, and writes a JSON
results dump for 02_build_results.py to turn into RESULTS.md.

Run: .venv/bin/python3 C09_pc_neutral_curve_fly/code/01_run_test.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root for `common`

from common.data import load_daily
from common.placebo import matched_random_entries
from common.bootstrap import stationary_block_bootstrap_ci, paired_diff_ci

sys.path.insert(0, str(Path(__file__).resolve().parent))
from yield_data import load_yield_curve
from construction import build_signal, ETF_ORDER, LOOKBACK_DAYS
from multi_leg_backtest import run_portfolio, total_trade_count

DEFINE_START, DEFINE_END = "2007-01-01", "2018-12-31"
HOLDOUT_START, HOLDOUT_END = "2019-01-01", "2026-08-31"
COST_BPS = 5.0
SEED = 20260922
N_BOOT = 5000

OUT_DIR = Path(__file__).resolve().parent.parent / "out"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)

    print("Loading Treasury yield curve (PCA estimation input)...")
    yields = load_yield_curve(DEFINE_START, HOLDOUT_END)
    yield_changes = yields.diff().dropna()

    print("Loading U-RATES ETF bars (execution/P&L layer)...")
    bars_by_ticker = load_daily(ETF_ORDER, DEFINE_START, HOLDOUT_END)

    common_index = yield_changes.index
    for t in ETF_ORDER:
        common_index = common_index.intersection(bars_by_ticker[t].index)
    common_index = common_index.sort_values()

    yield_changes = yield_changes.loc[common_index]
    etf_close = pd.concat({t: bars_by_ticker[t]["close"] for t in ETF_ORDER}, axis=1).loc[common_index]
    etf_returns = etf_close.pct_change().dropna()

    yield_changes = yield_changes.loc[etf_returns.index]

    print(f"Aligned trading days: {len(yield_changes)} ({yield_changes.index[0].date()} -> {yield_changes.index[-1].date()})")
    print(f"PCA seed period ({LOOKBACK_DAYS} days) excluded from signal start.")

    print("Building PC-neutral fly signal (rolling 2y PCA, refit daily)...")
    fly_weights, position = build_signal(yield_changes, etf_returns)

    signal_start = fly_weights.dropna().index[0]
    print(f"First tradeable signal date: {signal_start.date()}")

    target_weights_a = fly_weights.mul(position, axis=0).reindex(common_index).fillna(0.0)

    print("Arm A: PC-neutral fly, running multi-leg backtest...")
    result_a = run_portfolio(bars_by_ticker, target_weights_a, cost_bps=COST_BPS)

    print("Arm B: naive unhedged IEF-minus-SHY spread, same signal construction...")
    naive_spread_return = (etf_returns["IEF"] - etf_returns["SHY"]).dropna()
    cum_naive = naive_spread_return.cumsum()
    from construction import ewma_zscore, EWMA_HALFLIFE, Z_CAP

    z_naive = ewma_zscore(cum_naive, EWMA_HALFLIFE)
    position_b = (-z_naive).clip(-Z_CAP, Z_CAP)
    target_weights_b = pd.DataFrame(0.0, index=common_index, columns=ETF_ORDER)
    target_weights_b["IEF"] = position_b.reindex(common_index).fillna(0.0)
    target_weights_b["SHY"] = -position_b.reindex(common_index).fillna(0.0)
    result_b = run_portfolio(bars_by_ticker, target_weights_b, cost_bps=COST_BPS)

    def split(returns: pd.Series) -> dict[str, pd.Series]:
        returns = returns.reindex(common_index).fillna(0.0)
        return {
            "define": returns.loc[DEFINE_START:DEFINE_END],
            "holdout": returns.loc[HOLDOUT_START:HOLDOUT_END],
        }

    arm_a_returns = split(result_a["daily_returns"])
    arm_b_returns = split(result_b["daily_returns"])

    print("Arm D: buy-and-hold, each U-RATES member + equal-weight basket...")
    bh_returns = {}
    for t in ETF_ORDER:
        r = etf_returns[t].reindex(common_index).fillna(0.0)
        bh_returns[t] = split(r)
    ew_basket = etf_returns[ETF_ORDER].mean(axis=1).reindex(common_index).fillna(0.0)
    bh_returns["EW_BASKET"] = split(ew_basket)

    print("Arm C: matched random-entry placebo vs. Arm A's realized trades (HOLDOUT)...")
    placebo_results = {}
    for t in ETF_ORDER:
        trades = result_a["leg_trades"][t]
        holdout_trades = trades[(trades["entry_date"] >= HOLDOUT_START) & (trades["entry_date"] <= HOLDOUT_END)]
        if len(holdout_trades) == 0:
            continue
        bars_holdout = bars_by_ticker[t].loc[HOLDOUT_START:HOLDOUT_END]
        placebo = matched_random_entries(
            bars_holdout, holdout_trades, n_reps=500, cost_bps=COST_BPS, seed=SEED, execution="next_open"
        )
        placebo_results[t] = {
            "n_trades": int(len(holdout_trades)),
            "total_returns_mean": float(placebo["total_returns"].mean()),
            "total_returns": placebo["total_returns"].tolist(),
        }

    def total_return(returns: pd.Series) -> float:
        return float((1.0 + returns).prod() - 1.0)

    def ci(returns: pd.Series) -> dict:
        arr = returns.to_numpy()
        return stationary_block_bootstrap_ci(arr, stat=lambda x: float(np.prod(1.0 + x) - 1.0), n_boot=N_BOOT, seed=SEED)

    results = {
        "meta": {
            "define_window": [DEFINE_START, DEFINE_END],
            "holdout_window": [HOLDOUT_START, HOLDOUT_END],
            "cost_bps": COST_BPS,
            "signal_start_date": str(signal_start.date()),
            "n_trading_days_aligned": int(len(common_index)),
        },
        "arm_a_pc_neutral_fly": {
            "define": {"total_return": total_return(arm_a_returns["define"]), "ci": ci(arm_a_returns["define"])},
            "holdout": {"total_return": total_return(arm_a_returns["holdout"]), "ci": ci(arm_a_returns["holdout"])},
            "n_trades_total": total_trade_count(result_a["leg_trades"]),
        },
        "arm_b_naive_spread": {
            "define": {"total_return": total_return(arm_b_returns["define"]), "ci": ci(arm_b_returns["define"])},
            "holdout": {"total_return": total_return(arm_b_returns["holdout"]), "ci": ci(arm_b_returns["holdout"])},
            "n_trades_total": total_trade_count(result_b["leg_trades"]),
        },
        "arm_c_placebo_by_leg_holdout": placebo_results,
        "arm_d_buy_hold": {
            t: {
                "define_total_return": total_return(bh_returns[t]["define"]),
                "holdout_total_return": total_return(bh_returns[t]["holdout"]),
            }
            for t in bh_returns
        },
        "a_minus_d_ewbasket_holdout_paired_ci": paired_diff_ci(
            arm_a_returns["holdout"].to_numpy(),
            bh_returns["EW_BASKET"]["holdout"].to_numpy(),
            stat=lambda x: float(np.prod(1.0 + x) - 1.0),
            n_boot=N_BOOT,
            seed=SEED,
        ),
        "a_minus_b_holdout_paired_ci": paired_diff_ci(
            arm_a_returns["holdout"].to_numpy(),
            arm_b_returns["holdout"].to_numpy(),
            stat=lambda x: float(np.prod(1.0 + x) - 1.0),
            n_boot=N_BOOT,
            seed=SEED,
        ),
    }

    def _clean(obj):
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items() if k != "replicates"}
        return obj

    out_path = OUT_DIR / "results.json"
    out_path.write_text(json.dumps(_clean(results), indent=2, default=str))
    print(f"\nWrote {out_path}")

    print("\n--- Headline (HOLDOUT, net of costs) ---")
    print(f"Arm A (PC-neutral fly):  total return {results['arm_a_pc_neutral_fly']['holdout']['total_return']:.4f}  "
          f"CI [{results['arm_a_pc_neutral_fly']['holdout']['ci']['lower']:.4f}, {results['arm_a_pc_neutral_fly']['holdout']['ci']['upper']:.4f}]  "
          f"n_trades={results['arm_a_pc_neutral_fly']['n_trades_total']}")
    print(f"Arm B (naive spread):   total return {results['arm_b_naive_spread']['holdout']['total_return']:.4f}")
    print(f"Arm D (EW basket B&H):  total return {results['arm_d_buy_hold']['EW_BASKET']['holdout_total_return']:.4f}")
    print(f"A - D paired diff CI:   [{results['a_minus_d_ewbasket_holdout_paired_ci']['lower']:.4f}, {results['a_minus_d_ewbasket_holdout_paired_ci']['upper']:.4f}]")
    print(f"A - B paired diff CI:   [{results['a_minus_b_holdout_paired_ci']['lower']:.4f}, {results['a_minus_b_holdout_paired_ci']['upper']:.4f}]")


if __name__ == "__main__":
    main()
