"""
The zero-skill bot simulation core for C07 Part 2: up to 3 concurrent long
positions, drawn uniformly at random from the 10-name universe (TSLA joins
once it lists), holding period drawn uniformly from {1, 2, 3} trading days,
5 bps per side, equal 1/3-of-equity sizing per slot. No signal anywhere --
this is the "any bot can look good for a week" control.

Timeline per slot, no look-ahead: a position opened at bar t's OPEN with
holding period h is held through bars t..t+h-1 and exits at bar (t+h-1)'s
CLOSE. Its slot is free starting bar t+h -- so slot-freeing (an exit
realised at a close) and slot-filling (a new entry realised at the
FOLLOWING bar's open) never touch the same bar's price, and a newly freed
slot is filled at the very next opportunity (the next bar's open), matching
"a new position opened ... whenever a slot is free". Everything that
decides bar t's opens (which slots are free, what holding period is drawn)
is settled using only information already fixed at bar t's open -- no bar's
close influences that same bar's entry decision.

Equity accounting: each bot tracks total equity as a scalar starting at
1.0. An occupied slot commits `equity / 3` of CURRENT total equity at the
moment it opens (not a fixed initial fraction) -- the natural reading of
"each position 1/3 of equity" once multiple positions can close and reopen
across a multi-year run. Costs are 5 bps of notional charged on entry and
on exit (a full 10 bps round trip on the slot's own committed notional).

Vectorised ACROSS BOTS (the axis that matters at 2,000 bots): every bot
shares the same price path, so both the exit pass and the entry pass are
implemented as numpy array operations over all bots at once per trading
day, rather than a Python loop over bots. The only remaining Python loop is
over trading days (~5,450 for the full window), which is what "keep the
run to minutes" requires.
"""

from __future__ import annotations

import numpy as np

N_SLOTS = 3
HOLDING_CHOICES = np.array([1, 2, 3])
COST_BPS = 5.0
COST_RATE = COST_BPS / 10_000.0


def simulate_bots(
    close: np.ndarray,
    open_: np.ndarray,
    listed: np.ndarray,
    n_bots: int,
    seed_base: int = 0,
) -> np.ndarray:
    """Simulate `n_bots` zero-skill bots over the shared price path.

    `close`, `open_`: (n_days, n_tickers) float arrays, NaN where a ticker
    is not yet listed. `listed`: (n_days, n_tickers) bool, True once a
    ticker has valid data on that bar (used to gate ticker choice so a bot
    is never handed an unlisted TSLA).

    Returns `equity_path`: (n_days, n_bots) float array of each bot's total
    equity at the CLOSE of each day (so day-over-day pct_change is the
    bot's own daily net return series).
    """
    n_days, n_tickers = close.shape
    equity = np.ones(n_bots)
    equity_path = np.empty((n_days, n_bots))

    held_ticker = np.full((n_bots, N_SLOTS), -1, dtype=int)
    days_remaining = np.zeros((n_bots, N_SLOTS), dtype=int)
    entry_notional = np.zeros((n_bots, N_SLOTS))
    entry_price = np.zeros((n_bots, N_SLOTS))

    # One RNG stream per bot (seed_base + bot index), drawn from in a fixed
    # order (slot 0's decisions before slot 1's, day by day) so a run is
    # reproducible bot-by-bot regardless of how the numpy ops are batched.
    rngs = [np.random.default_rng(seed_base + b) for b in range(n_bots)]

    for t in range(n_days):
        listed_today = listed[t]
        active_idx = np.nonzero(listed_today)[0]
        n_active = len(active_idx)

        # --- Exit pass: vectorised across bots for each slot. ---
        for s in range(N_SLOTS):
            occ = held_ticker[:, s] >= 0
            if not occ.any():
                continue
            tk = held_ticker[occ, s]
            px = close[t, tk]
            valid_px = np.isfinite(px) & (px > 0)

            days_remaining[occ, s] -= 1
            expiring = occ.copy()
            expiring[occ] = (days_remaining[occ, s] <= 0) & valid_px
            if expiring.any():
                gross_ret = close[t, held_ticker[expiring, s]] / entry_price[expiring, s] - 1.0
                proceeds = entry_notional[expiring, s] * (1.0 + gross_ret)
                exit_cost = proceeds * COST_RATE
                pnl = (proceeds - exit_cost) - entry_notional[expiring, s]
                equity[expiring] += pnl
                held_ticker[expiring, s] = -1
                days_remaining[expiring, s] = 0
                entry_notional[expiring, s] = 0.0
                entry_price[expiring, s] = 0.0
            # A held position whose ticker has no valid price today (should
            # not occur inside a listed run, but guarded) simply is not
            # unwound this bar; it will be re-evaluated next bar.

        # --- Entry pass: fill every free slot, per bot, per slot in order. ---
        if n_active > 0:
            for s in range(N_SLOTS):
                free_rows = np.nonzero(held_ticker[:, s] == -1)[0]
                if len(free_rows) == 0:
                    continue
                held_mask = held_ticker[free_rows] >= 0  # (n_free, N_SLOTS)
                held_vals = held_ticker[free_rows]

                for i, b in enumerate(free_rows):
                    held_here = held_vals[i][held_mask[i]]
                    if len(held_here) == 0:
                        candidates = active_idx
                    else:
                        avail = np.ones(n_tickers, dtype=bool)
                        avail[held_here] = False
                        candidates = active_idx[avail[active_idx]]
                    if len(candidates) == 0:
                        continue
                    rng = rngs[b]
                    choice = candidates[rng.integers(0, len(candidates))]
                    entry_px = open_[t, choice]
                    if not np.isfinite(entry_px) or entry_px <= 0:
                        continue
                    holding = int(rng.choice(HOLDING_CHOICES))
                    notional = equity[b] / 3.0
                    cost = notional * COST_RATE
                    equity[b] -= cost
                    held_ticker[b, s] = choice
                    days_remaining[b, s] = holding
                    entry_notional[b, s] = notional
                    entry_price[b, s] = entry_px

        equity_path[t] = equity

    return equity_path
