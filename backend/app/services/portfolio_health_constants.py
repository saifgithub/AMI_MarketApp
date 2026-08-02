"""CR136 shared constants — every threshold, band, and pin in one module.

Rev 4's standing instruction is "never scattered literals": every sufficiency
floor, rule threshold, hysteresis band, validator constant, scenario episode
and gate default for Portfolio Health lives here, and every one of them carries
a comment naming the Rev 4 derivation that pinned it. The reason is not tidiness
— Rev 4's thresholds were each fixed by a measurement, and a literal copied into
a call site is a number nobody can trace back to the simulation that justified
it.

Seeded by M01 with the data-layer pins. **M04 owns this module** and extends it
with `SUFFICIENCY`, the rule thresholds/bands, validator constants, scenario
episodes and gate defaults.
"""

from __future__ import annotations

# ── Data layer (M01) ────────────────────────────────────────────────────────

# Rev 4 estimator pin 5 — the benchmark leg is SPY's adjusted close, ridden
# through the identical history path (same table, same hygiene rules) so the
# inner join in M04 compares like with like.
BENCHMARK_TICKER = "SPY"

# Rev 4 estimator pin 4 — fetch 2 years of daily bars. The pre-CR136 layer
# topped out at 65 daily bars ("3m"), i.e. 64 returns against a floor of 126.
HISTORY_FETCH_PERIOD = "2y"

# Rev 4 estimator pin 4 — "the estimator uses up to 504 returns" (2 × 252
# trading days). Reads are trimmed to the trailing 504 rows.
HISTORY_MAX_ROWS = 504

# Rev 4 uncertainty contract — the `reason` recorded on a `dropped_holdings`
# entry when the data-hygiene gate (not short history) removed the holding.
DATA_QUALITY_DROP_REASON = "data_quality"

# Rev 4 data-hygiene gate. The three bad-print bounds are convention, chosen
# conservatively (M01): they must not fire on a genuine crash day, because a
# real -45% session is exactly the observation the volatility estimate needs
# most. Calibration is deliberately loose in that direction.
BAD_PRINT_SPIKE_ABS_RETURN = 0.40        # same-day |return| that opens the reversal test
BAD_PRINT_REVERSAL_MIN_FRACTION = 0.60   # next-day reversal ≥ 60% of the spike, opposite sign
BAD_PRINT_HARD_ABS_RETURN = 1.00         # |r| > 100% is flagged unconditionally
