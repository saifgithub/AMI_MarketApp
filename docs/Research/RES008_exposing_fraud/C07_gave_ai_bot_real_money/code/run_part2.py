"""
C07 Part 2 -- "what a short window can show": the zero-skill bot (see
`zero_skill_bot.py`) simulated 2,000 times over the 10-name universe
(AAPL MSFT AMZN GOOGL NVDA TSLA DIS JPM KO WMT; TSLA joins 2010-06-29) on
daily bars 2005-01-03 -> 2026-08-31, up to 3 concurrent 1/3-equity long
slots, holding period uniform on {1,2,3} trading days, 5 bps per side.

For every rolling 5-trading-day and 21-trading-day window (step 1 day),
every bot's window return minus SPY's return over the same bars. Reported:
the share of (bot, window) pairs beating SPY / beating by >= 1pt / by >=
3pt, for the zero-skill bot and (as a comparator, not a re-run) for Part
1's RSI rule treated as one 22-ticker equal-weight daily-net-return
portfolio (loaded from `out/rsi_rule_daily_net_returns_full_window.csv`,
written by `run_part1.py`); the 5th/25th/50th/75th/95th percentile of the
zero-skill bot's weekly (5-day) and monthly (21-day) excess return; the
zero-skill bot's trade win rate and mean 21-day return conditional on a
TRENDING month (equal-weight buy-and-hold basket of the 10 names up >= 8%
over the 21 days) versus unconditionally; and the sample-size arithmetic
n = (2*sigma/mu)^2 (mu = 5%/52 weekly, 5%/12 monthly) for a genuine +5
points/year edge to clear two standard errors, using the MEASURED sigma of
the zero-skill bot's own weekly/monthly excess return.

No look-ahead: every rolling window's return uses only bars inside that
window; the "trending" classification of a 21-day window uses only that
window's own bars; a trade is counted as "opened inside a trending window"
by its own entry date falling in that window, never by information from
after the window closes.
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

from common.data import load_daily
from common.bootstrap import proportion_ci as _proportion_ci

from zero_skill_bot import simulate_bots, N_SLOTS, HOLDING_CHOICES, COST_RATE

TICKERS = ["AAPL", "MSFT", "AMZN", "GOOGL", "NVDA", "TSLA", "DIS", "JPM", "KO", "WMT"]
START, END = "2005-01-03", "2026-08-31"
N_BOTS = 2000
SEED_BASE = 0
WEEK_WINDOW = 5
MONTH_WINDOW = 21
TRENDING_THRESHOLD = 0.08
EDGE_PTS_PER_YEAR = 0.05
WEEKS_PER_YEAR = 52.0
MONTHS_PER_YEAR = 12.0


def load_universe() -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray, pd.DatetimeIndex, pd.Series]:
    all_tickers = TICKERS + ["SPY"]
    bars = load_daily(all_tickers, START, END)
    calendar = bars["SPY"].index

    close = pd.DataFrame(index=calendar)
    open_ = pd.DataFrame(index=calendar)
    for t in TICKERS:
        b = bars[t].reindex(calendar)
        close[t] = b["close"]
        open_[t] = b["open"]

    listed = close.notna().to_numpy()
    spy_close = bars["SPY"]["close"].reindex(calendar)
    return close, open_, listed, calendar, spy_close


def rolling_window_returns(equity_path: np.ndarray, window: int) -> np.ndarray:
    """(n_windows, n_bots) simple return over each rolling `window`-bar span.

    Window i covers equity_path[i] (start-of-window equity, i.e. the close
    just BEFORE the window's first bar begins accruing this window's
    return) through equity_path[i + window] -- so window i uses only bars
    i+1 .. i+window, never anything before bar i's close or after bar
    i+window's close.
    """
    n_days = equity_path.shape[0]
    n_windows = n_days - window
    start = equity_path[0:n_windows]
    end = equity_path[window : window + n_windows]
    with np.errstate(divide="ignore", invalid="ignore"):
        return end / start - 1.0


def rolling_window_returns_1d(prices: np.ndarray, window: int) -> np.ndarray:
    n_days = len(prices)
    n_windows = n_days - window
    start = prices[0:n_windows]
    end = prices[window : window + n_windows]
    return end / start - 1.0


def share_stats(excess: np.ndarray) -> dict:
    flat = excess.ravel()
    flat = flat[np.isfinite(flat)]
    n = len(flat)
    return {
        "n_pairs": int(n),
        "share_beats_spy": float(np.mean(flat > 0.0)),
        "share_beats_spy_by_1pt": float(np.mean(flat >= 0.01)),
        "share_beats_spy_by_3pt": float(np.mean(flat >= 0.03)),
    }


def load_rsi_rule_portfolio_returns(calendar: pd.DatetimeIndex) -> pd.Series:
    path = OUT_DIR / "rsi_rule_daily_net_returns_full_window.csv"
    df = pd.read_csv(path, index_col="date", parse_dates=["date"])
    portfolio = df.mean(axis=1, skipna=True)
    portfolio = portfolio.reindex(calendar).fillna(0.0)
    return portfolio


def rsi_portfolio_prices(daily_net_returns: pd.Series) -> np.ndarray:
    return (1.0 + daily_net_returns).cumprod().to_numpy()


def trending_month_analysis(
    close: pd.DataFrame,
    open_: pd.DataFrame,
    listed: np.ndarray,
    calendar: pd.DatetimeIndex,
    seed_base: int,
) -> dict:
    """Re-run every bot with the SAME seeds but keep a trade log, to test win rate by regime.

    A single `simulate_bots` call already gives the equity path but not a
    trade-level log; this reruns the identical per-bot RNG streams (same
    `seed_base + b` per bot, so each bot draws the exact same ticker
    choices and holding periods `simulate_bots` drew) through an
    unvectorised, per-bot loop that additionally records each trade's
    entry bar and net return, matched against which 21-day windows are
    "trending" as of that entry bar. All `N_BOTS` bots are replayed (not a
    subsample) for consistency with the headline run; this loop is the
    slower of Part 2's two passes (no numpy vectorisation across bots, only
    within a bot's own 3 slots) but still completes in minutes at this
    scale (measured, see DEVIATIONS.md).
    """
    n_days, n_tickers = close.shape[0], close.shape[1]
    close_np = close.to_numpy()
    open_np = open_.to_numpy()

    valid_mask = listed
    with np.errstate(invalid="ignore"):
        basket_price = np.nanmean(np.where(valid_mask, close_np, np.nan), axis=1)

    trending = np.zeros(n_days, dtype=bool)
    month_return = np.full(n_days, np.nan)
    for i in range(n_days - MONTH_WINDOW):
        r = basket_price[i + MONTH_WINDOW] / basket_price[i] - 1.0
        month_return[i] = r
        trending[i] = r >= TRENDING_THRESHOLD

    n_trend_windows = int(trending[: n_days - MONTH_WINDOW].sum())
    n_total_windows = n_days - MONTH_WINDOW
    share_trend_windows = n_trend_windows / n_total_windows if n_total_windows > 0 else float("nan")

    trend_trade_returns = []
    all_trade_returns = []
    trend_month_forward_returns = []

    n_bots_trend = N_BOTS
    for b in range(n_bots_trend):
        rng = np.random.default_rng(seed_base + b)
        held_ticker = np.full(N_SLOTS, -1, dtype=int)
        days_remaining = np.zeros(N_SLOTS, dtype=int)
        entry_notional = np.zeros(N_SLOTS)
        entry_price = np.zeros(N_SLOTS)
        entry_bar = np.zeros(N_SLOTS, dtype=int)
        equity = 1.0

        for t in range(n_days):
            for s in range(N_SLOTS):
                if held_ticker[s] >= 0:
                    px = close_np[t, held_ticker[s]]
                    if np.isfinite(px) and px > 0:
                        days_remaining[s] -= 1
                        if days_remaining[s] <= 0:
                            gross_ret = px / entry_price[s] - 1.0
                            proceeds = entry_notional[s] * (1.0 + gross_ret)
                            exit_cost = proceeds * COST_RATE
                            pnl = (proceeds - exit_cost) - entry_notional[s]
                            equity += pnl
                            net_ret = pnl / entry_notional[s]
                            eb = entry_bar[s]
                            all_trade_returns.append(net_ret)
                            if eb < n_days - MONTH_WINDOW and trending[eb]:
                                trend_trade_returns.append(net_ret)
                            held_ticker[s] = -1

            active_idx = np.nonzero(listed[t])[0]
            if len(active_idx) > 0:
                for s in range(N_SLOTS):
                    if held_ticker[s] == -1:
                        held_here = held_ticker[held_ticker >= 0]
                        avail = np.ones(n_tickers, dtype=bool)
                        if len(held_here) > 0:
                            avail[held_here] = False
                        candidates = active_idx[avail[active_idx]]
                        if len(candidates) == 0:
                            continue
                        choice = candidates[rng.integers(0, len(candidates))]
                        entry_px = open_np[t, choice]
                        if not np.isfinite(entry_px) or entry_px <= 0:
                            continue
                        holding = int(rng.choice(HOLDING_CHOICES))
                        notional = equity / 3.0
                        cost = notional * COST_RATE
                        equity -= cost
                        held_ticker[s] = choice
                        days_remaining[s] = holding
                        entry_notional[s] = notional
                        entry_price[s] = entry_px
                        entry_bar[s] = t

    for i in range(n_days - MONTH_WINDOW):
        if trending[i]:
            trend_month_forward_returns.append(month_return[i])

    all_arr = np.array(all_trade_returns)
    trend_arr = np.array(trend_trade_returns)

    n_all = len(all_arr)
    n_trend = len(trend_arr)
    all_wins = int(np.sum(all_arr > 0)) if n_all else 0
    trend_wins = int(np.sum(trend_arr > 0)) if n_trend else 0

    unconditional_win_rate = float(all_wins / n_all) if n_all else float("nan")
    trend_win_rate = float(trend_wins / n_trend) if n_trend else float("nan")
    trend_mean_21d_return = float(np.mean(trend_month_forward_returns)) if trend_month_forward_returns else float("nan")

    unconditional_win_rate_ci = _proportion_ci(all_wins, n_all) if n_all else None
    trend_win_rate_ci = _proportion_ci(trend_wins, n_trend) if n_trend else None

    return {
        "n_trending_windows": n_trend_windows,
        "n_total_21d_windows": n_total_windows,
        "share_of_windows_trending": share_trend_windows,
        "trend_trade_win_rate": trend_win_rate,
        "trend_trade_win_rate_wilson_ci": trend_win_rate_ci,
        "n_trend_trades": len(trend_trade_returns),
        "trend_mean_21d_return": trend_mean_21d_return,
        "unconditional_trade_win_rate": unconditional_win_rate,
        "unconditional_trade_win_rate_wilson_ci": unconditional_win_rate_ci,
        "n_all_trades": len(all_trade_returns),
    }


def sample_size_arithmetic(sigma: float, periods_per_year: float, edge_pts_per_year: float) -> dict:
    mu = edge_pts_per_year / periods_per_year
    n_periods = (2.0 * sigma / mu) ** 2
    n_years = n_periods / periods_per_year
    return {"sigma": sigma, "mu_per_period": mu, "n_periods": float(n_periods), "n_years": float(n_years)}


def main() -> None:
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading daily bars for {len(TICKERS)} tickers + SPY ({START}..{END})...")
    close, open_, listed, calendar, spy_close = load_universe()
    close_np = close.to_numpy()
    open_np = open_.to_numpy()
    spy_prices = spy_close.to_numpy()

    print(f"Simulating {N_BOTS} zero-skill bots over {len(calendar)} trading days...")
    equity_path = simulate_bots(close_np, open_np, listed, n_bots=N_BOTS, seed_base=SEED_BASE)
    print(f"  bot simulation done in {time.time() - t0:.1f}s")

    week_excess_bot = rolling_window_returns(equity_path, WEEK_WINDOW) - rolling_window_returns_1d(spy_prices, WEEK_WINDOW)[:, None]
    month_excess_bot = rolling_window_returns(equity_path, MONTH_WINDOW) - rolling_window_returns_1d(spy_prices, MONTH_WINDOW)[:, None]

    week_share_bot = share_stats(week_excess_bot)
    month_share_bot = share_stats(month_excess_bot)

    print("Loading Part 1 RSI-rule equal-weight portfolio comparator...")
    rsi_portfolio_returns = load_rsi_rule_portfolio_returns(calendar)
    rsi_prices = rsi_portfolio_prices(rsi_portfolio_returns)

    rsi_week_ret = rolling_window_returns_1d(rsi_prices, WEEK_WINDOW)
    rsi_month_ret = rolling_window_returns_1d(rsi_prices, MONTH_WINDOW)
    spy_week_ret = rolling_window_returns_1d(spy_prices, WEEK_WINDOW)
    spy_month_ret = rolling_window_returns_1d(spy_prices, MONTH_WINDOW)

    rsi_week_excess = rsi_week_ret - spy_week_ret
    rsi_month_excess = rsi_month_ret - spy_month_ret
    rsi_week_share = share_stats(rsi_week_excess)
    rsi_month_share = share_stats(rsi_month_excess)

    week_pct = np.percentile(week_excess_bot[np.isfinite(week_excess_bot)], [5, 25, 50, 75, 95])
    month_pct = np.percentile(month_excess_bot[np.isfinite(month_excess_bot)], [5, 25, 50, 75, 95])

    print(f"Running trending-month conditional analysis over {N_BOTS} bots (this replays the full sim)...")
    trend_t0 = time.time()
    trend_stats = trending_month_analysis(close, open_, listed, calendar, seed_base=SEED_BASE)
    print(f"  trending-month analysis done in {time.time() - trend_t0:.1f}s")

    week_sigma = float(np.nanstd(week_excess_bot, ddof=1))
    month_sigma = float(np.nanstd(month_excess_bot, ddof=1))
    week_n = sample_size_arithmetic(week_sigma, WEEKS_PER_YEAR, EDGE_PTS_PER_YEAR)
    month_n = sample_size_arithmetic(month_sigma, MONTHS_PER_YEAR, EDGE_PTS_PER_YEAR)

    results = {
        "meta": {
            "tickers": TICKERS,
            "start": START,
            "end": END,
            "n_bots": N_BOTS,
            "n_trading_days": int(len(calendar)),
            "week_window": WEEK_WINDOW,
            "month_window": MONTH_WINDOW,
            "trending_threshold": TRENDING_THRESHOLD,
            "edge_pts_per_year_for_sample_size": EDGE_PTS_PER_YEAR,
        },
        "zero_skill_bot": {
            "week_vs_spy": week_share_bot,
            "month_vs_spy": month_share_bot,
            "week_excess_percentiles": {
                "p5": float(week_pct[0]), "p25": float(week_pct[1]), "p50": float(week_pct[2]),
                "p75": float(week_pct[3]), "p95": float(week_pct[4]),
            },
            "month_excess_percentiles": {
                "p5": float(month_pct[0]), "p25": float(month_pct[1]), "p50": float(month_pct[2]),
                "p75": float(month_pct[3]), "p95": float(month_pct[4]),
            },
        },
        "rsi_rule_equal_weight_portfolio": {
            "construction": "mean of the 22 U-EQ tickers' Part-1 RSI-rule daily net returns (equal-weight, rebalanced daily), compounded into a price path",
            "week_vs_spy": rsi_week_share,
            "month_vs_spy": rsi_month_share,
        },
        "trending_month_conditional": trend_stats,
        "sample_size_arithmetic": {
            "weekly": week_n,
            "monthly": month_n,
        },
    }

    results_path = OUT_DIR / "results_part2.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    np.savez_compressed(
        OUT_DIR / "part2_arrays.npz",
        week_excess_bot=week_excess_bot,
        month_excess_bot=month_excess_bot,
    )

    elapsed = time.time() - t0
    print(f"Part 2 done in {elapsed:.1f}s. Wrote {results_path}")


if __name__ == "__main__":
    main()
