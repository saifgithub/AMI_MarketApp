"""
C01 — "a neural network predicts tomorrow's stock price" — the pre-registered test.

Runs arms A1, A2, B-price, B-return over U-LSTM (10 tickers) x 3 seeds, computes
M1-M6 exactly as PREREGISTRATION.md defines them, and writes out/results_full.json
(every number, per ticker-seed and pooled, with the M4 daily series; git-ignored),
out/results.json (the same with each M4 series summarised, via slim_results.py)
and out/summary.txt (a plain table).

Arm definitions (fixed by the prereg, not tunable here):
  A1        lookback=100, scaler fit on the WHOLE series (the leak being
            reproduced), 65/35 split, LSTM_A1 architecture, target=next close.
  A2        lookback=60, scaler fit on the whole series, 80/20 split,
            LSTM_A2 architecture, target=next close.
  B-price   same architecture+split as A1, scaler fit on TRAIN segment only,
            target=next close.
  B-return  same architecture+split as A1, scaler fit on TRAIN segment only,
            target=next-day return (not price level).

M5 (the leak) is exactly A1 vs B-price test RMSE, since B-price is defined as
A1's architecture/split with the scaler-fit changed -- that is the "identical
model with the scaler fit on train only" the prereg calls for.

No parameter here was chosen after seeing a result. The one contingency
(epochs -> 50 for all arms if a single A1 run exceeds 4 minutes) was timed
BEFORE this script existed, on one throwaway A1 run: 51.6s on MPS, well under
the 4-minute threshold, so all arms use the pre-registered 100 (A1) / 20 (A2)
epochs unchanged. See out/DEVIATIONS.md for that timing and the device choice.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.preprocessing import MinMaxScaler

THIS_DIR = Path(__file__).resolve().parent
C01_DIR = THIS_DIR.parent
ROOT_DIR = C01_DIR.parent
OUT_DIR = C01_DIR / "out"

sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(ROOT_DIR))

from common.data import load_daily
from common.backtest import run_positions
from common.bootstrap import stationary_block_bootstrap_ci, paired_diff_ci, proportion_ci

import slim_results
from lstm_core import (
    LSTM_A1,
    LSTM_A2,
    make_windows,
    train_model,
    predict,
    set_all_seeds,
    recursive_forecast,
)

TICKERS = ["AAPL", "MSFT", "AMZN", "NVDA", "TSLA", "JPM", "XOM", "KO", "INTC", "SPY"]
SEEDS = [0, 1, 2]
START = "2012-01-01"
END = "2026-08-31"
DEVICE = torch.device("mps")
COST_BPS = 5.0

A1_EPOCHS = 100
A2_EPOCHS = 20
A1_BATCH = 64
A2_BATCH = 32
A1_LOOKBACK = 100
A2_LOOKBACK = 60
A1_SPLIT = 0.65
A2_SPLIT = 0.80
M6_STEPS = 30


def load_all_bars() -> dict[str, "pd.DataFrame"]:
    return load_daily(TICKERS, START, END)


def split_index(n: int, lookback: int, split_frac: float) -> int:
    """Index into the raw price series where the test segment begins.

    split_frac fraction of the RAW series is train; windows whose target falls
    at or after this index belong to the test segment. This mirrors "chronological
    N/(100-N) split" applied to the series itself, not to the window count.
    """
    return int(round(n * split_frac))


def build_windows_and_split(scaled: np.ndarray, raw_close: np.ndarray, lookback: int, split_frac: float):
    """Return train/test window arrays plus bookkeeping for RMSE unscaling and
    for the persistence baseline, split so that no test-segment raw close
    contributes to a training window's target."""
    n = len(scaled)
    split_at = split_index(n, lookback, split_frac)

    X, y_scaled = make_windows(scaled, lookback)
    # window i has target index (i + lookback) in the raw series.
    target_idx = np.arange(lookback, n)
    train_mask = target_idx < split_at
    test_mask = ~train_mask

    return {
        "X_train": X[train_mask],
        "y_train": y_scaled[train_mask],
        "X_test": X[test_mask],
        "y_test_scaled": y_scaled[test_mask],
        "target_idx_test": target_idx[test_mask],
        "split_at": split_at,
    }


def unscale(values: np.ndarray, scaler: MinMaxScaler) -> np.ndarray:
    return scaler.inverse_transform(np.asarray(values, dtype=np.float64).reshape(-1, 1)).reshape(-1)


def rmse(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.sqrt(np.mean((np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)) ** 2)))


def m1_persistence_ratio(y_pred_price: np.ndarray, y_true_price: np.ndarray, prev_close_price: np.ndarray) -> dict:
    model_rmse = rmse(y_pred_price, y_true_price)
    naive_rmse = rmse(prev_close_price, y_true_price)
    ratio = model_rmse / naive_rmse if naive_rmse != 0 else float("nan")
    return {"model_rmse": model_rmse, "naive_rmse": naive_rmse, "ratio": ratio}


def m2_tracks_tomorrow_or_yesterday(y_pred_price: np.ndarray, y_true_price: np.ndarray, prev_close_price: np.ndarray) -> dict:
    """Test-segment index i is time t_i; consecutive test points are consecutive
    calendar steps (the test segment is contiguous), so i plays the role of "t"
    for i in 0..n-2.

    First correlation (does the forecast move with TOMORROW):
      predicted change = ŷ(t+1) - y(t)   = y_pred_price[1:]  - y_true_price[:-1]
      actual change     = y(t+1) - y(t)   = y_true_price[1:]  - y_true_price[:-1]

    Second correlation (does the forecast just ECHO YESTERDAY):
      ŷ(t+1) - ŷ(t) = y_pred_price[1:] - y_pred_price[:-1]
      y(t) - y(t-1) = y_true_price[:-1] - prev_close_price[:-1]
    """
    pred_change = y_pred_price[1:] - y_true_price[:-1]
    actual_change = y_true_price[1:] - y_true_price[:-1]

    pred_change_echo = y_pred_price[1:] - y_pred_price[:-1]
    actual_change_yesterday = y_true_price[:-1] - prev_close_price[:-1]

    def safe_corr(a, b):
        if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0:
            return float("nan")
        return float(np.corrcoef(a, b)[0, 1])

    corr_tomorrow = safe_corr(pred_change, actual_change)
    corr_yesterday_echo = safe_corr(pred_change_echo, actual_change_yesterday)

    max_lag = 10
    n = len(y_pred_price)
    lags = range(-max_lag, max_lag + 1)
    best_lag, best_corr = 0, -2.0
    pred_c = y_pred_price - np.mean(y_pred_price)
    true_c = y_true_price - np.mean(y_true_price)
    for lag in lags:
        if lag < 0:
            a, b = pred_c[-lag:], true_c[: n + lag]
        elif lag > 0:
            a, b = pred_c[: n - lag], true_c[lag:]
        else:
            a, b = pred_c, true_c
        if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0:
            continue
        c = float(np.corrcoef(a, b)[0, 1])
        if c > best_corr:
            best_corr, best_lag = c, lag

    return {
        "corr_pred_change_vs_actual_change": corr_tomorrow,
        "corr_pred_change_vs_yesterday_echo": corr_yesterday_echo,
        "peak_xcorr_lag": best_lag,
        "peak_xcorr_value": best_corr,
    }


def m3_direction(pred_sign: np.ndarray, actual_sign: np.ndarray) -> dict:
    hits = (pred_sign == actual_sign)
    n = len(hits)
    n_hits = int(hits.sum())
    hit_rate = float(hits.mean()) if n else float("nan")
    always_up_base_rate = float((actual_sign > 0).mean()) if n else float("nan")
    wilson = proportion_ci(n_hits, n) if n else None
    return {
        "hit_rate": hit_rate,
        "n_hits": n_hits,
        "n": n,
        "always_up_base_rate": always_up_base_rate,
        "wilson_ci": wilson,
    }


def train_arm(model_cls, lookback, split_frac, epochs, batch_size, scaler_scope, target_kind, ticker, seed, bars):
    """Train one (ticker, seed) cell for a given arm config.

    scaler_scope: 'whole' (Arm A leak) or 'train' (Arm B).
    target_kind: 'price' or 'return'.
    """
    close = bars["close"].to_numpy(dtype=np.float64)
    n = len(close)
    split_at = split_index(n, lookback, split_frac)

    if target_kind == "return":
        rets = np.zeros_like(close)
        rets[1:] = close[1:] / close[:-1] - 1.0
        rets[0] = 0.0
        feature_series = rets
    else:
        feature_series = close

    if scaler_scope == "whole":
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaled = scaler.fit_transform(feature_series.reshape(-1, 1)).reshape(-1)
    elif scaler_scope == "train":
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaler.fit(feature_series[:split_at].reshape(-1, 1))
        scaled = scaler.transform(feature_series.reshape(-1, 1)).reshape(-1)
    else:
        raise ValueError(scaler_scope)

    split_data = build_windows_and_split(scaled, close, lookback, split_frac)

    set_all_seeds(seed)
    model = model_cls()
    train_model(
        model,
        split_data["X_train"],
        split_data["y_train"],
        epochs=epochs,
        batch_size=batch_size,
        device=DEVICE,
    )

    pred_scaled_test = predict(model, split_data["X_test"], DEVICE)
    pred_unscaled = unscale(pred_scaled_test, scaler)
    true_unscaled = unscale(split_data["y_test_scaled"], scaler)

    target_idx_test = split_data["target_idx_test"]
    prev_close_or_return = feature_series[target_idx_test - 1]

    seed_window = scaled[split_at - lookback : split_at]

    return {
        "model": model,
        "scaler": scaler,
        "pred_unscaled": pred_unscaled,
        "true_unscaled": true_unscaled,
        "target_idx_test": target_idx_test,
        "prev_feature_test": prev_close_or_return,
        "close_series": close,
        "split_at": split_at,
        "seed_window": seed_window,
        "feature_series": feature_series,
    }


def m4_money(bars, pred_price_or_return, target_idx_test, ticker_close, arm_kind) -> dict:
    """Position = 1 iff predicted next value > current known value, else 0
    (never short -- the prereg says 'Long ... else flat'), decided at the
    close of bar t = target_idx_test - 1. Fed through run_positions over a
    bars slice that starts one bar BEFORE the first test target (so the
    signal decided at that bar's close has a well-defined position to hold
    into) and ends at the last test target -- i.e. exactly the TEST segment's
    own realised returns, nothing from train. Buy-and-hold is a constant +1
    position run through the identical function over the identical bars.
    """
    import pandas as pd

    decide_idx = target_idx_test - 1
    close_vals = bars["close"].to_numpy(dtype=np.float64)

    if arm_kind == "return":
        signal = (pred_price_or_return > 0).astype(float)
    else:
        current_close = close_vals[decide_idx]
        signal = (pred_price_or_return > current_close).astype(float)

    decide_dates = bars.index[decide_idx]
    aligned_bars = bars.iloc[decide_idx[0] : target_idx_test[-1] + 1]

    position = pd.Series(0.0, index=aligned_bars.index)
    position.loc[decide_dates] = signal
    position = position.ffill()

    bh_position = pd.Series(1.0, index=aligned_bars.index)

    results = {}
    for execution in ("same_close", "next_open"):
        model_res = run_positions(aligned_bars, position, COST_BPS, execution=execution)
        bh_res = run_positions(aligned_bars, bh_position, COST_BPS, execution=execution)
        # Drop the alignment bar (index 0 = the pre-test decide bar) so only
        # TEST-segment realised returns are reported, per the prereg.
        results[execution] = {
            "model_daily_returns": model_res.daily_returns.iloc[1:],
            "bh_daily_returns": bh_res.daily_returns.iloc[1:],
        }
    return results


def m6_recursive_forecast(model, scaler, seed_window, close_series, split_at, target_kind, feature_series) -> dict:
    forecast_scaled = recursive_forecast(model, seed_window, M6_STEPS, DEVICE)
    forecast_unscaled = unscale(forecast_scaled, scaler)

    realized_future = feature_series[split_at : split_at + M6_STEPS]
    n_avail = min(len(realized_future), M6_STEPS)
    forecast_unscaled = forecast_unscaled[:n_avail]
    realized_future = realized_future[:n_avail]

    if target_kind == "return":
        forecast_path = forecast_unscaled
        realized_path = realized_future
    else:
        forecast_path = np.diff(np.concatenate([[close_series[split_at - 1]], forecast_unscaled]))
        realized_path = np.diff(np.concatenate([[close_series[split_at - 1]], realized_future]))

    forecast_std = float(np.std(forecast_path))
    realized_std = float(np.std(realized_path))
    ratio = forecast_std / realized_std if realized_std != 0 else float("nan")

    return {
        "forecast_daily_change_std": forecast_std,
        "realized_daily_change_std": realized_std,
        "ratio": ratio,
        "n_steps_used": int(n_avail),
    }


def run_arm(arm_name, model_cls, lookback, split_frac, epochs, batch_size, scaler_scope, target_kind, all_bars, timing):
    per_ticker_seed = []
    for ticker in TICKERS:
        bars = all_bars[ticker]
        for seed in SEEDS:
            t0 = time.time()
            cell = train_arm(model_cls, lookback, split_frac, epochs, batch_size, scaler_scope, target_kind, ticker, seed, bars)
            elapsed = time.time() - t0
            timing.setdefault(arm_name, []).append(elapsed)

            pred = cell["pred_unscaled"]
            true = cell["true_unscaled"]
            prev = cell["prev_feature_test"]

            if target_kind == "return":
                naive_zero = np.zeros_like(true)
                naive_today = prev
                m1 = {
                    "model_rmse": rmse(pred, true),
                    "naive_zero_rmse": rmse(naive_zero, true),
                    "naive_today_rmse": rmse(naive_today, true),
                    "ratio_vs_zero": rmse(pred, true) / rmse(naive_zero, true) if rmse(naive_zero, true) != 0 else float("nan"),
                    "ratio_vs_today": rmse(pred, true) / rmse(naive_today, true) if rmse(naive_today, true) != 0 else float("nan"),
                }
                pred_change = pred
                actual_change = true
                pred_sign = np.sign(pred)
                actual_sign = np.sign(true)
            else:
                m1 = m1_persistence_ratio(pred, true, prev)
                pred_change = pred - prev
                actual_change = true - prev
                pred_sign = np.sign(pred_change)
                actual_sign = np.sign(actual_change)

            if target_kind == "return":
                m2_tracks_tomorrow_pair = (pred, true)
                m2_echo_pair = (pred[1:], prev[1:])
                m2 = {
                    "corr_pred_vs_actual": (
                        float(np.corrcoef(pred, true)[0, 1]) if np.std(pred) > 0 and np.std(true) > 0 else float("nan")
                    ),
                    "corr_pred_vs_yesterday_return": (
                        float(np.corrcoef(pred[1:], prev[1:])[0, 1])
                        if len(pred) > 1 and np.std(pred[1:]) > 0 and np.std(prev[1:]) > 0
                        else float("nan")
                    ),
                }
            else:
                m2 = m2_tracks_tomorrow_or_yesterday(pred, true, prev)
                m2_tracks_tomorrow_pair = (pred[1:] - true[:-1], true[1:] - true[:-1])
                m2_echo_pair = (pred[1:] - pred[:-1], true[:-1] - prev[:-1])

            m3 = m3_direction(pred_sign, actual_sign)

            m4_raw = m4_money(bars, pred, cell["target_idx_test"], cell["close_series"], target_kind)
            m4 = {
                execution: {
                    "model_daily_returns": v["model_daily_returns"].tolist(),
                    "bh_daily_returns": v["bh_daily_returns"].tolist(),
                    "dates": [d.isoformat() for d in v["model_daily_returns"].index],
                }
                for execution, v in m4_raw.items()
            }

            m6 = m6_recursive_forecast(
                cell["model"], cell["scaler"], cell["seed_window"], cell["close_series"], cell["split_at"], target_kind, cell["feature_series"]
            )

            per_ticker_seed.append(
                {
                    "ticker": ticker,
                    "seed": seed,
                    "arm": arm_name,
                    "n_test": len(true),
                    "train_seconds": elapsed,
                    "M1": m1,
                    "M2": m2,
                    "M3": m3,
                    "M4": m4,
                    "M6": m6,
                    "_m2_tracks_tomorrow_pair": (
                        m2_tracks_tomorrow_pair[0].tolist(),
                        m2_tracks_tomorrow_pair[1].tolist(),
                    ),
                    "_m2_echo_pair": (m2_echo_pair[0].tolist(), m2_echo_pair[1].tolist()),
                }
            )
            print(f"  {arm_name} {ticker} seed={seed} done in {elapsed:.1f}s  M1_ratio={m1.get('ratio', m1.get('ratio_vs_zero')):.4f}")
    return per_ticker_seed


def pool_m1(rows) -> dict:
    ratios = [r["M1"].get("ratio", r["M1"].get("ratio_vs_zero")) for r in rows]
    ratios = [r for r in ratios if not np.isnan(r)]
    return {
        "median_ratio": float(np.median(ratios)),
        "frac_below_1": float(np.mean(np.array(ratios) < 1.0)),
        "n": len(ratios),
        "ratios": ratios,
    }


def pool_m3(rows) -> dict:
    per_ticker = {}
    for r in rows:
        m3 = r["M3"]
        per_ticker.setdefault(r["ticker"], []).append(m3["hit_rate"])
    n_total = sum(r["M3"]["n"] for r in rows)
    hits_total = sum(r["M3"]["n_hits"] for r in rows)
    base_rates = [r["M3"]["always_up_base_rate"] for r in rows]
    pooled_wilson = proportion_ci(int(hits_total), int(n_total)) if n_total else None
    max_base_rate = float(np.max(base_rates)) if base_rates else float("nan")
    tickers_exceeding = 0
    for ticker, rates in per_ticker.items():
        mean_rate = np.mean(rates)
        if mean_rate > max(max_base_rate, 0.5):
            tickers_exceeding += 1
    return {
        "pooled_hit_rate": hits_total / n_total if n_total else float("nan"),
        "pooled_wilson_ci": pooled_wilson,
        "max_base_rate": max_base_rate,
        "n_tickers_exceeding_base_and_50pct": tickers_exceeding,
        "n_tickers_total": len(per_ticker),
    }


def _corr_stat(paired_2d: np.ndarray) -> float:
    a_, b_ = paired_2d[:, 0], paired_2d[:, 1]
    if np.std(a_) == 0 or np.std(b_) == 0:
        return 0.0
    return float(np.corrcoef(a_, b_)[0, 1])


def pool_m2(rows) -> dict:
    """Pooled CI for H2's two M2 correlations, per the spec's 'first M2 interval
    includes 0' wording -- point corr(predicted change, actual change) alone
    cannot be judged against an interval, so this pools each ticker-seed's
    (predicted-change, actual-change) pairs across ALL rows into one paired
    series and runs it through common.bootstrap.stationary_block_bootstrap_ci
    with a correlation statistic (the function accepts any 1-D-indexable
    array, including an (n, 2) paired array, since it only resamples row
    indices) -- reusing the shared library's own block-bootstrap machinery
    rather than writing a second one here.
    """
    tomorrow_a = np.concatenate([np.asarray(r["_m2_tracks_tomorrow_pair"][0]) for r in rows])
    tomorrow_b = np.concatenate([np.asarray(r["_m2_tracks_tomorrow_pair"][1]) for r in rows])
    echo_a = np.concatenate([np.asarray(r["_m2_echo_pair"][0]) for r in rows])
    echo_b = np.concatenate([np.asarray(r["_m2_echo_pair"][1]) for r in rows])

    tomorrow_ci = stationary_block_bootstrap_ci(np.column_stack([tomorrow_a, tomorrow_b]), stat=_corr_stat, seed=0)
    echo_ci = stationary_block_bootstrap_ci(np.column_stack([echo_a, echo_b]), stat=_corr_stat, seed=0)

    return {
        "pooled_corr_tracks_tomorrow": tomorrow_ci,
        "pooled_corr_echoes_yesterday": echo_ci,
    }


def pool_m4(rows, seed_filter=None) -> dict:
    result = {}
    for execution in ("same_close", "next_open"):
        model_concat = []
        bh_concat = []
        for r in rows:
            if seed_filter is not None and r["seed"] != seed_filter:
                continue
            model_concat.extend(r["M4"][execution]["model_daily_returns"])
            bh_concat.extend(r["M4"][execution]["bh_daily_returns"])
        model_arr = np.array(model_concat, dtype=np.float64)
        bh_arr = np.array(bh_concat, dtype=np.float64)
        if len(model_arr) == 0:
            result[execution] = None
            continue
        ci = paired_diff_ci(model_arr, bh_arr, stat=np.mean, seed=0)
        result[execution] = ci
    return result


def _json_safe(obj):
    """Recursively convert numpy/pandas scalars to plain Python and drop the
    'replicates' key from any bootstrap-CI dict -- estimate/lower/upper/
    block_len/n_boot fully describe the interval; the raw 5000-float
    resampling arrays are not part of what the writeup needs and json's
    default=str would silently truncate them via numpy's own repr anyway.
    """
    if isinstance(obj, dict):
        return {
            k: _json_safe(v)
            for k, v in obj.items()
            if k != "replicates" and not k.startswith("_m2_")
        }
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return _json_safe(obj.tolist())
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    timing = {}
    overall_t0 = time.time()

    print("Loading data...")
    all_bars = load_all_bars()

    print("=== Arm A1 ===")
    a1_rows = run_arm("A1", LSTM_A1, A1_LOOKBACK, A1_SPLIT, A1_EPOCHS, A1_BATCH, "whole", "price", all_bars, timing)

    print("=== Arm A2 ===")
    a2_rows = run_arm("A2", LSTM_A2, A2_LOOKBACK, A2_SPLIT, A2_EPOCHS, A2_BATCH, "whole", "price", all_bars, timing)

    print("=== Arm B-price ===")
    b_price_rows = run_arm("B-price", LSTM_A1, A1_LOOKBACK, A1_SPLIT, A1_EPOCHS, A1_BATCH, "train", "price", all_bars, timing)

    print("=== Arm B-return ===")
    b_return_rows = run_arm("B-return", LSTM_A1, A1_LOOKBACK, A1_SPLIT, A1_EPOCHS, A1_BATCH, "train", "return", all_bars, timing)

    total_wall = time.time() - overall_t0

    m5_rows = []
    for a1_row, bp_row in zip(a1_rows, b_price_rows):
        assert a1_row["ticker"] == bp_row["ticker"] and a1_row["seed"] == bp_row["seed"]
        m5_rows.append(
            {
                "ticker": a1_row["ticker"],
                "seed": a1_row["seed"],
                "a1_test_rmse": a1_row["M1"]["model_rmse"],
                "b_price_test_rmse": bp_row["M1"]["model_rmse"],
                "rmse_change": bp_row["M1"]["model_rmse"] - a1_row["M1"]["model_rmse"],
            }
        )

    results = {
        "meta": {
            "tickers": TICKERS,
            "seeds": SEEDS,
            "start": START,
            "end": END,
            "device": str(DEVICE),
            "a1_epochs": A1_EPOCHS,
            "a2_epochs": A2_EPOCHS,
            "total_wall_seconds": total_wall,
            "timing_by_arm_seconds": timing,
        },
        "A1": {
            "per_ticker_seed": a1_rows,
            "pooled_M1": pool_m1(a1_rows),
            "pooled_M2": pool_m2(a1_rows),
            "pooled_M3": pool_m3(a1_rows),
            "pooled_M4": pool_m4(a1_rows),
            "pooled_M4_seed0": pool_m4(a1_rows, seed_filter=0),
            "pooled_M4_seed1": pool_m4(a1_rows, seed_filter=1),
            "pooled_M4_seed2": pool_m4(a1_rows, seed_filter=2),
        },
        "A2": {
            "per_ticker_seed": a2_rows,
            "pooled_M1": pool_m1(a2_rows),
            "pooled_M2": pool_m2(a2_rows),
            "pooled_M3": pool_m3(a2_rows),
            "pooled_M4": pool_m4(a2_rows),
        },
        "B-price": {
            "per_ticker_seed": b_price_rows,
            "pooled_M1": pool_m1(b_price_rows),
            "pooled_M2": pool_m2(b_price_rows),
            "pooled_M3": pool_m3(b_price_rows),
            "pooled_M4": pool_m4(b_price_rows),
            "pooled_M4_seed0": pool_m4(b_price_rows, seed_filter=0),
            "pooled_M4_seed1": pool_m4(b_price_rows, seed_filter=1),
            "pooled_M4_seed2": pool_m4(b_price_rows, seed_filter=2),
        },
        "B-return": {
            "per_ticker_seed": b_return_rows,
            "pooled_M1": pool_m1(b_return_rows),
            "pooled_M2": pool_m2(b_return_rows),
            "pooled_M3": pool_m3(b_return_rows),
            "pooled_M4": pool_m4(b_return_rows),
            "pooled_M4_seed0": pool_m4(b_return_rows, seed_filter=0),
            "pooled_M4_seed1": pool_m4(b_return_rows, seed_filter=1),
            "pooled_M4_seed2": pool_m4(b_return_rows, seed_filter=2),
        },
        "M5_leak": {
            "per_ticker_seed": m5_rows,
            "median_rmse_change": float(np.median([r["rmse_change"] for r in m5_rows])),
        },
    }

    with open(OUT_DIR / "results_full.json", "w") as f:
        json.dump(_json_safe(results), f, indent=2)

    write_summary(results)
    slim_results.main()
    print(f"\nTotal wall time: {total_wall:.1f}s. Wrote out/results_full.json, out/results.json and out/summary.txt")


def write_summary(results: dict) -> None:
    lines = []
    lines.append("C01 -- LSTM predicts price -- SUMMARY")
    lines.append("=" * 60)
    meta = results["meta"]
    lines.append(f"device={meta['device']}  a1_epochs={meta['a1_epochs']}  a2_epochs={meta['a2_epochs']}")
    lines.append(f"total_wall_seconds={meta['total_wall_seconds']:.1f}")
    lines.append("")

    for arm in ("A1", "A2", "B-price", "B-return"):
        r = results[arm]
        lines.append(f"--- {arm} ---")
        m1 = r["pooled_M1"]
        lines.append(f"M1 median ratio(model_rmse/naive_rmse) = {m1['median_ratio']:.4f}  frac<1 = {m1['frac_below_1']:.2f}  n={m1['n']}")
        m2 = r["pooled_M2"]
        t_ci = m2["pooled_corr_tracks_tomorrow"]
        e_ci = m2["pooled_corr_echoes_yesterday"]
        lines.append(
            f"M2 pooled corr(tracks tomorrow) = {t_ci['estimate']:.4f}  CI=[{t_ci['lower']:.4f}, {t_ci['upper']:.4f}]  "
            f"| pooled corr(echoes yesterday) = {e_ci['estimate']:.4f}  CI=[{e_ci['lower']:.4f}, {e_ci['upper']:.4f}]"
        )
        m3 = r["pooled_M3"]
        lines.append(
            f"M3 pooled hit_rate = {m3['pooled_hit_rate']:.4f}  wilson_ci = "
            f"[{m3['pooled_wilson_ci']['lower']:.4f}, {m3['pooled_wilson_ci']['upper']:.4f}]  "
            f"max_base_rate = {m3['max_base_rate']:.4f}  "
            f"tickers_exceeding = {m3['n_tickers_exceeding_base_and_50pct']}/{m3['n_tickers_total']}"
        )
        for execution in ("same_close", "next_open"):
            m4 = r["pooled_M4"][execution]
            if m4:
                lines.append(
                    f"M4 [{execution}] paired diff mean daily return (model - buyhold) = "
                    f"{m4['estimate']:.6f}  CI=[{m4['lower']:.6f}, {m4['upper']:.6f}]"
                )
        lines.append("")

    lines.append("--- M5 (the leak): A1 vs B-price test RMSE ---")
    lines.append(f"median RMSE change (B-price - A1) = {results['M5_leak']['median_rmse_change']:.6f}")
    lines.append("")

    lines.append("--- M6 (30-day recursive forecast) sample, A1 per ticker-seed ---")
    for row in results["A1"]["per_ticker_seed"]:
        m6 = row["M6"]
        lines.append(f"{row['ticker']} seed={row['seed']}: forecast/realized daily-change std ratio = {m6['ratio']:.4f}")

    (OUT_DIR / "summary.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
