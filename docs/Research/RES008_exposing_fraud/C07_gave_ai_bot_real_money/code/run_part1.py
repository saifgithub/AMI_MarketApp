"""
C07 Part 1 -- "the disclosed rule": Wilder RSI(14), long when RSI < 30, flat
when RSI > 70, long/flat only, run over U-EQ (22 tickers) daily (DEFINE,
HOLDOUT separately) and 60-minute (~730 days), `next_open` execution, 5 bps
per side, versus buy-and-hold and versus the matched-random placebo.

RSI is computed on each ticker's FULL loaded series (DEFINE+HOLDOUT together
for daily; the whole ~730-day pull for intraday) and only THEN sliced to the
reporting window, so a window never starts cold -- see `rsi_rule.py` and
`common/README.md`. Buy-and-hold is run through the identical `run_positions`
engine with a constant target_position of +1 over the same bars (same
execution/cost machinery), not a naive price-ratio shortcut, so it is
directly comparable.

Per ticker per window: net/gross total return, buy-and-hold total return,
exposure, n trades, win rate, and the placebo percentile of the net total
return within `matched_random_entries` (500 reps, same execution). A ticker
with zero trades in a window has no trade list to match a placebo against,
so it is reported with `placebo_percentile: null` and excluded from the
pooled placebo mean (stated in PREREGISTRATION.md).

Pooled per window: count of tickers where the rule beats buy-and-hold net;
paired difference in mean daily net return vs buy-and-hold via
`bootstrap.paired_diff_ci` on the CONCATENATION of each ticker's own
(rule_daily_net, buyhold_daily_net) series pair -- concatenation, not
averaging, per the prereg's "concatenate tickers' paired-difference series";
mean placebo percentile across tickers (zero-trade tickers excluded) with a
simple bootstrap CI over tickers (resampling which ticker, not which day).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
C07_DIR = THIS_DIR.parent
ROOT_DIR = C07_DIR.parent
OUT_DIR = C07_DIR / "out"

sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(ROOT_DIR))

from common.data import load_daily, load_intraday
from common.backtest import run_positions
from common.placebo import matched_random_entries, percentile_of
from common.bootstrap import paired_diff_ci, stationary_block_bootstrap_ci

from rsi_rule import rsi, rsi_state_machine

U_EQ = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "JPM", "JNJ", "XOM",
    "PG", "KO", "WMT", "DIS", "INTC", "CSCO", "BA", "GE", "PFE", "T", "SPY", "QQQ",
]

DEFINE_START, DEFINE_END = "2005-01-01", "2018-12-31"
HOLDOUT_START, HOLDOUT_END = "2019-01-01", "2026-08-31"
DAILY_LOAD_START = DEFINE_START  # full history so RSI is warm at DEFINE's first bar
DAILY_LOAD_END = HOLDOUT_END

COST_BPS = 5.0
RSI_PERIOD = 14
EXECUTION = "next_open"
PLACEBO_REPS = 500
PLACEBO_SEED_BASE = 20260917


def _slice(bars: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    mask = (bars.index >= pd.Timestamp(start)) & (bars.index <= pd.Timestamp(end))
    return bars.loc[mask]


def _run_one(bars_full: pd.DataFrame, window_bars: pd.DataFrame, ticker: str, seed: int) -> dict:
    """Run the RSI rule and buy-and-hold on `window_bars`, RSI computed on `bars_full`."""
    rsi_full = rsi(bars_full["close"], period=RSI_PERIOD)
    rsi_window = rsi_full.reindex(window_bars.index)
    target = rsi_state_machine(rsi_window)

    rule_result = run_positions(window_bars, target, cost_bps=COST_BPS, execution=EXECUTION)
    bh_target = pd.Series(1.0, index=window_bars.index)
    bh_result = run_positions(window_bars, bh_target, cost_bps=COST_BPS, execution=EXECUTION)

    rule_summary = rule_result.summary()
    n_trades = rule_summary["n_trades"]

    net_total_return = rule_summary["total_return"]
    gross_total_return = float((1.0 + rule_result.gross_daily_returns).prod() - 1.0)
    bh_total_return = float((1.0 + bh_result.daily_returns).prod() - 1.0)

    placebo_percentile = None
    if n_trades > 0:
        placebo = matched_random_entries(
            window_bars,
            rule_result.trades,
            n_reps=PLACEBO_REPS,
            cost_bps=COST_BPS,
            seed=seed,
            execution=EXECUTION,
        )
        placebo_percentile = percentile_of(net_total_return, placebo["total_returns"])

    return {
        "ticker": ticker,
        "net_total_return": net_total_return,
        "gross_total_return": gross_total_return,
        "buy_hold_total_return": bh_total_return,
        "exposure": rule_summary["exposure"],
        "n_trades": n_trades,
        "win_rate": rule_summary["win_rate"],
        "placebo_percentile": placebo_percentile,
        "beats_buy_hold_net": net_total_return > bh_total_return,
        "rule_daily_net": rule_result.daily_returns,
        "bh_daily_net": bh_result.daily_returns,
    }


def _pool_window(per_ticker: list[dict], window_name: str) -> dict:
    n_tickers = len(per_ticker)
    zero_trade = [r["ticker"] for r in per_ticker if r["n_trades"] == 0]
    with_trades = [r for r in per_ticker if r["n_trades"] > 0]

    n_beats_bh = sum(1 for r in per_ticker if r["beats_buy_hold_net"])

    rule_concat = np.concatenate([r["rule_daily_net"].to_numpy() for r in per_ticker])
    bh_concat = np.concatenate([r["bh_daily_net"].to_numpy() for r in per_ticker])
    paired_ci = paired_diff_ci(rule_concat, bh_concat, stat=np.mean, seed=0)

    percentiles = [r["placebo_percentile"] for r in with_trades if r["placebo_percentile"] is not None]
    if percentiles:
        mean_percentile_ci = stationary_block_bootstrap_ci(
            np.array(percentiles), stat=np.mean, seed=0
        )
    else:
        mean_percentile_ci = None

    return {
        "window": window_name,
        "n_tickers": n_tickers,
        "n_tickers_beat_buy_hold_net": n_beats_bh,
        "zero_trade_tickers": zero_trade,
        "n_tickers_with_trades": len(with_trades),
        "paired_diff_mean_daily_net_vs_buy_hold": {
            "estimate": paired_ci["estimate"],
            "lower": paired_ci["lower"],
            "upper": paired_ci["upper"],
            "block_len": paired_ci["block_len"],
            "n_boot": paired_ci["n_boot"],
        },
        "mean_placebo_percentile": (
            {
                "estimate": mean_percentile_ci["estimate"],
                "lower": mean_percentile_ci["lower"],
                "upper": mean_percentile_ci["upper"],
                "n_boot": mean_percentile_ci["n_boot"],
            }
            if mean_percentile_ci is not None
            else None
        ),
    }


def _strip_series(per_ticker: list[dict]) -> list[dict]:
    return [
        {k: v for k, v in r.items() if k not in ("rule_daily_net", "bh_daily_net")}
        for r in per_ticker
    ]


def _save_full_window_returns(define_per_ticker: list[dict], holdout_per_ticker: list[dict]) -> None:
    """Concatenate each ticker's DEFINE+HOLDOUT rule daily net returns and save to CSV.

    Consumed by Part 2 to build the "Part 1 RSI rule run as a 22-ticker
    equal-weight portfolio of its per-ticker daily net returns" comparator,
    per PREREGISTRATION.md, over the SAME 2005-2026 span Part 2 covers.
    """
    define_by_ticker = {r["ticker"]: r["rule_daily_net"] for r in define_per_ticker}
    holdout_by_ticker = {r["ticker"]: r["rule_daily_net"] for r in holdout_per_ticker}
    combined = {
        ticker: pd.concat([define_by_ticker[ticker], holdout_by_ticker[ticker]])
        for ticker in U_EQ
    }
    df = pd.DataFrame(combined)
    df.index.name = "date"
    df.to_csv(OUT_DIR / "rsi_rule_daily_net_returns_full_window.csv")


def run_daily_window(daily_bars: dict[str, pd.DataFrame], start: str, end: str, window_name: str) -> tuple[list[dict], dict]:
    per_ticker = []
    for i, ticker in enumerate(U_EQ):
        bars_full = daily_bars[ticker]
        window_bars = _slice(bars_full, start, end)
        seed = PLACEBO_SEED_BASE + i
        per_ticker.append(_run_one(bars_full, window_bars, ticker, seed))
    pooled = _pool_window(per_ticker, window_name)
    return per_ticker, pooled


def run_intraday_window(window_name: str = "intraday_60m") -> tuple[list[dict], dict]:
    per_ticker = []
    for i, ticker in enumerate(U_EQ):
        bars = load_intraday(ticker, "60m")
        seed = PLACEBO_SEED_BASE + 1000 + i
        per_ticker.append(_run_one(bars, bars, ticker, seed))
    pooled = _pool_window(per_ticker, window_name)
    return per_ticker, pooled


def main() -> None:
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading daily bars for {len(U_EQ)} U-EQ tickers ({DAILY_LOAD_START}..{DAILY_LOAD_END})...")
    daily_bars = load_daily(U_EQ, DAILY_LOAD_START, DAILY_LOAD_END)

    print("Running DEFINE window...")
    define_per_ticker, define_pooled = run_daily_window(daily_bars, DEFINE_START, DEFINE_END, "DEFINE")

    print("Running HOLDOUT window...")
    holdout_per_ticker, holdout_pooled = run_daily_window(daily_bars, HOLDOUT_START, HOLDOUT_END, "HOLDOUT")

    print("Running 60-minute intraday window...")
    intraday_per_ticker, intraday_pooled = run_intraday_window()

    print("Saving full-window (DEFINE+HOLDOUT) daily net returns for Part 2's equal-weight portfolio...")
    _save_full_window_returns(define_per_ticker, holdout_per_ticker)

    results = {
        "meta": {
            "universe": U_EQ,
            "rsi_period": RSI_PERIOD,
            "execution": EXECUTION,
            "cost_bps": COST_BPS,
            "placebo_reps": PLACEBO_REPS,
            "define_window": [DEFINE_START, DEFINE_END],
            "holdout_window": [HOLDOUT_START, HOLDOUT_END],
        },
        "DEFINE": {
            "per_ticker": _strip_series(define_per_ticker),
            "pooled": define_pooled,
        },
        "HOLDOUT": {
            "per_ticker": _strip_series(holdout_per_ticker),
            "pooled": holdout_pooled,
        },
        "intraday_60m": {
            "per_ticker": _strip_series(intraday_per_ticker),
            "pooled": intraday_pooled,
        },
    }

    results_path = OUT_DIR / "results_part1.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    elapsed = time.time() - t0
    print(f"Part 1 done in {elapsed:.1f}s. Wrote {results_path}")


if __name__ == "__main__":
    main()
