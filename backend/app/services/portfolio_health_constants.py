"""CR136 M04 — single home for every CR136 constant (sufficiency floors, rule thresholds + hysteresis bands, validator constants, scenario episodes, bad-print params, gate defaults); import from here, never scatter literals.

Rev 4's standing instruction is "never scattered literals", and the reason is not
tidiness: every threshold below was fixed by a measurement, and a number copied
into a call site is a number nobody can trace back to the simulation that
justified it. Each constant therefore names its Rev 4 derivation in a comment.

**Import-pure: stdlib only, zero `app.*` imports.** `app/core/config.py` reads
the gate defaults from here for its `Settings` field defaults, and M01's
price-history store reads the data-layer pins — either import would become a
cycle the moment this module reached back into `app`.

That purity is also why the five *estimator-definition* constants
(`EWMA_LAMBDA`, `TRADING_DAYS_PER_YEAR`, `TRADING_DAYS_PER_MONTH`,
`BAD_MONTH_Z`, `CALENDAR_DAYS_PER_YEAR`) are deliberately NOT redefined here —
they live in `app.trading_math.portfolio_risk`, which is where the estimator
that uses them lives, and M02's hand-off forbids duplicating them.
`portfolio_health.py` imports them (and `grid_periods_per_year`, CR139) from
there. One definition, no drift.

Seeded by M01 with the data-layer pins; M04 owns it and everything below.
"""

from __future__ import annotations

# ── Engine identity + data layer ────────────────────────────────────────────

ENGINE_VERSION = "cr136.v1"              # Rev 4 estimator pin 8 — on root and every block, so old journal entries stay interpretable

# Rev 4 estimator pin 5 — the benchmark leg is SPY's adjusted close, ridden
# through the identical history path (same table, same hygiene rules) so the
# inner join in M04 compares like with like.
BENCHMARK_TICKER = "SPY"

# Rev 4 estimator pin 4 — fetch 2 years of daily bars. The pre-CR136 layer
# topped out at 65 daily bars ("3m"), i.e. 64 returns against a floor of 126.
HISTORY_FETCH_PERIOD = "2y"
DATA_WINDOW_YEARS = 2

# Rev 4 estimator pin 4 — "the estimator uses up to 504 returns" (2 × 252
# trading days). HISTORY_MAX_ROWS caps stored CLOSES served per ticker;
# MAX_RETURNS caps the RETURNS the estimator consumes. They are both 504, which
# means a single ticker's own window yields at most 503 returns — immaterial by
# Rev 4's own pin, which records ESS 65.61 at a 252-day lookback vs 65.67 at
# 504 and calls a 252-day lookback acceptable. At λ=0.97 the 504th observation
# carries a normalised weight of ~7e-9.
HISTORY_MAX_ROWS = 504
MAX_RETURNS = 504

# Rev 4 uncertainty contract — the `reason` recorded on a `dropped_holdings`
# entry when the data-hygiene gate (not short history) removed the holding.
DATA_QUALITY_DROP_REASON = "data_quality"
SHORT_HISTORY_DROP_REASON = "short_history"
# CR040: a feed outage and a genuinely young security are NOT the same fact, and
# telling a user "not enough price history for this holding" when the truth is
# "our feed is down" is the wrong answer to the question that rule asks.
FEED_UNAVAILABLE_DROP_REASON = "feed_unavailable"

# ── Sufficiency contract (Rev 4 table, supersedes Rev 3) ────────────────────

# Rev 4 sufficiency table — 126 observed returns. Window coverage 1−λ^126 =
# 97.85% of EWMA weight; ESS 62.9 = 96% of the asymptote, so the floor stays
# meaningful under exponential weighting.
T_MIN = 126

# Rev 4 F17, measured: for a FIXED weight vector the relative sampling error of
# σ̂ₚ is 1/√(2T) INDEPENDENT of N (6.29–6.37% across N = 5…200 at T = 126,
# unchanged even where the sample covariance is singular). So this gate applies
# ONLY to the quantities that touch off-diagonals — DR², risk contributions and
# MCR. σₚ and beta gate on T alone.
T_OVER_N_MIN = 5.0

# Rev 4 short-history rule — dropped invested weight above this and the whole
# Tier-1 block reads insufficient rather than describing a book it has not seen.
DROPPED_WEIGHT_MAX = 0.20

# DEF213 / CR139 — the joined return grid's density, `window_days /
# n_observations`. `_join` intersects dates across the holdings and the
# benchmark, `_returns_on` then takes consecutive close-to-close ratios ON
# THAT GRID. Originally (DEF213, 2026-08-03) `annualize_vol` multiplied by
# √252 unconditionally, so a return spanning k trading days was annualised as
# if it spanned one — measured: thinning to every other trading day overstated
# σ by 1.372×/1.424× (24/24 seeds), and re-annualising the same estimate at
# the grid's true period count returned 0.970, localising the entire gap in
# the annualisation constant. One thinly-traded holding of three was enough —
# `_join` intersects, so its holes thinned every metric in the book: +6.1% σ
# at 5% of its days missing, +7.9% at 10%, +12.5% at 20%, +29.8% at 40%, with
# `dropped_holdings` EMPTY and `partial` FALSE at every level.
#
# CR139 shipped the correction: `annualize_vol` now takes the grid's own
# realised rate (`trading_math.grid_periods_per_year`, derived from these same
# two numbers) instead of assuming 252, so the bias above no longer occurs at
# ANY density — this guard's ORIGINAL justification ("refuse because the old
# annualisation would not fit") is gone.
#
# RE-DERIVED, NOT RETIRED — for a DIFFERENT reason, argued here rather than
# measured, because measuring it properly would need a fresh live-market
# fetch and a new Monte-Carlo sweep this pass did not run (flagged as
# follow-on work, not silently skipped):
#   `grid_periods_per_year` reads a calendar-day ratio as a PROXY for how many
#   trading days each period truly spans. That proxy is validated (by the
#   clean-book measurement below) up to the density a real calendar naturally
#   produces; past that, an increasingly large gap is decreasingly well
#   modelled as ordinary weekend/holiday spacing, and the σ this produces —
#   though no longer biased in the DEF213 direction — carries growing,
#   unquantified extra uncertainty the disclosed F17 sampling error does not
#   cover. Separately, and more concretely: every metric this book computes
#   (σ, DR², beta, risk shares — R1–R3's inputs are ratios of Σ's own entries
#   and so are UNAFFECTED by the annualisation constant, but they still come
#   from the SAME Σ) is weighted by the same EWMA λ=0.97, whose half-life is
#   22.8 GRID periods (M02). On a grid sparse enough to trip this line, those
#   22.8 periods span more than 22.8 real trading days — at the threshold
#   itself, ratio 1.65 implies grid periods ~1.65/1.4535 ≈ 1.135 real trading
#   days each, stretching the half-life to ~25.8 trading days (~1.14 months,
#   against the nominal "about a month" M02 describes) — a small, clearly
#   tolerable drift, well inside the ~66-day effective sample the module
#   already discloses as its ordinary operating point. That smallness is why
#   1.65 is RETAINED rather than loosened: it is comfortably conservative
#   under this new argument too, even though it was not re-derived FROM it.
#
# 1.65 itself, measured 2026-08-03 on the real US-equity calendar
# (`def213_guard_threshold.py`, 10y of daily bars, 8 instruments across both
# venues and four asset classes — all 8 share ONE calendar, 2513 of 2513
# dates, so a clean book's join loses nothing for calendar reasons):
#   · clean-book ratio, 11,038 rolling windows at every length the engine
#     consumes (126…504 returns): mean 1.4535, MAX 1.4921 (a 126-return window
#     over the holiday-dense 2024-12-31→2025-07-07 stretch).
#   · CONSTRUCTED tail — Yahoo's free endpoint caps that ticker at ~10y today, so
#     9/11 (4 sessions) and Sandy (2) are outside the fetchable window; deleting
#     a block of L consecutive sessions from the real calendar reproduces the
#     shape. Worst: 1.5556 at L=5, longer than any US closure since 1933.
# 1.65 clears that constructed worst case by 6.1% and the observed one by 10.6%,
# and fires above 11.9% of one holding's days missing.
GRID_DENSITY_MAX = 1.65

# Rev 4 Tier-1 table — R² below this sets `low_explanatory_power`; also R3's
# own R² gate (M05). Beta still ships when the flag is true; it is labelled,
# not withheld.
LOW_R2_THRESHOLD = 0.20

# Rev 4 F10 — the old "≥ 2 snapshots" floor was vacuous, and an
# expanding-window max drawdown is a monotone ratchet a de-risking user can
# never improve (measured: minimum day-over-day change exactly 0.0; the rolling
# window restores improvability on 87.4% of paths).
TIER2_MIN_SNAPSHOTS = 21
# Named _SNAPSHOTS, not _DAYS: it counts stored snapshot ROWS, and rows exist
# only for trading days. Calling it days would invite calendar arithmetic, which
# is the one thing CR136 refuses to do anywhere.
TIER2_MDD_WINDOW_SNAPSHOTS = 252

# Rev 4 F16 — the institutional bias test. z = realised return / predicted vol
# must have sd ~ 1; at T=252 the acceptance band is [0.911, 1.089]. The band
# applies AT T=252, not at small n, so the helper reports n and never verdicts.
BIAS_SD_BAND = (0.911, 1.089)

# ── Typical bad month (Rev 4 F13) ───────────────────────────────────────────
# The z and the 21-day month live in `trading_math.portfolio_risk` as
# BAD_MONTH_Z / TRADING_DAYS_PER_MONTH (M02 owns the arithmetic). Pins
# reproduce 2.71 / 6.07 / 12.44 % at σ = 26.2% for 1d / 1w / 1mo.

# ── Scenario panel (Rev 4 Tier-1 table) ─────────────────────────────────────
# Verified 2026-08-02 against SPY on the PRICE basis (`auto_adjust=False`):
# COVID −34.10% vs −33.90% pinned (0.20pp), 2022 −25.36% vs −25.40% (0.04pp).
# The price basis matters: on dividend-adjusted closes the 2022 episode reads
# −24.50%, a 0.90pp miss, because Rev 4's figures are S&P 500 PRICE-index
# returns and the sim pays no dividends. `backend/scripts/cr136_generate_fixtures.py
# --verify-scenarios` re-runs the check; M11 re-runs it live at promotion.
SCENARIO_EPISODES = (
    {"id": "covid_2020", "label": "COVID crash",
     "start": "2020-02-19", "end": "2020-03-23", "benchmark_return": -0.339},
    {"id": "drawdown_2022", "label": "2022 drawdown",
     "start": "2022-01-03", "end": "2022-10-12", "benchmark_return": -0.254},
)

# ── Rule engine thresholds + hysteresis (Rev 4 rule table; consumed by M05) ──
#
# Every band below is a measured width, not a round number. Under EWMA the
# boundary flip rate is 21.3% (vs 8.9% for an equal-weight window), so
# hysteresis is mandatory on every Σ-derived rule — a metric that crosses its
# threshold twice a week teaches nothing. CI-lower-bound gating was measured and
# REJECTED: detection collapses to 50.8% on a genuinely high-beta book.

# UNITS. A threshold whose rule renders a percentage is stored in PERCENTAGE
# POINTS and carries a `_PCT` suffix; everything else is in the metric's own
# native unit. The suffix is load-bearing, not decoration: M04's payload is in
# decimal fractions while M05's rule API is in percentage points, and an
# unlabelled 0.415-vs-41.5 mix-up is not a visible error — it is a rule that
# silently never fires.

RULE_R1_FIRE_TOP_RISK_SHARE_PCT = 41.5   # Rev 4 R1 — band ±1.5pp = 0.6× the measured per-window sd (~2.2–2.4pp at T/N=5); worst flip 7.7%, detection 95.6% at true 44%
RULE_R1_CLEAR_TOP_RISK_SHARE_PCT = 38.5
RULE_R1_MIN_RISKY_HOLDINGS = 4           # Rev 4 R1 — small books have structurally high top shares (60/40 SPY+AGG reads 94.5%); the contribution table carries the fact, the rule stays silent
RULE_R1_TEXTBOOK_THRESHOLD_PCT = 40      # the literal "40" inside R1's own template — registered as a slot so M06's allow-list stays closed (F15)

RULE_R2_FIRE_DR2 = 1.85                  # Rev 4 R2 — band ±0.15 measured: 5.5% flips, 99.3% detection at true 1.7, 1.3% false-fire at true 2.3
RULE_R2_CLEAR_DR2 = 2.15
RULE_R2_MIN_HOLDINGS = 8

RULE_R2B_FIRE_RHO = 0.90                 # Rev 4 R2b — band 0.05 ≈ 3× SE(ρ̂) at ρ=0.9, T=126
RULE_R2B_CLEAR_RHO = 0.85
RULE_R2B_MIN_PAIR_WEIGHT_PCT = 5.0       # Rev 4 R2b — R2's holdings≥8 gate structurally silences every small book; this is the rule that actually catches SPY+QQQ (ρ=0.952 measured)

RULE_R3_BETA_BASE = 1.3                  # Rev 4 R3 — fire at β̂ ≥ base + 0.6·SE(β̂), clear below base − 0.6·SE(β̂); the band self-scales with sample size; worst flip 8.0%, detection 96.0% at true β 1.45
RULE_R3_SE_BAND_MULT = 0.6
# R3's R² co-gate is deliberately the SAME constant as `low_explanatory_power`
# above, not a second 0.2: a beta the engine has already flagged as barely
# explained by the market must not be the beta a rule fires on. One name keeps
# the two from ever drifting apart.

RULE_R4_FIRE_CASH_PCT = 41.0             # Rev 4 R4 — ±1pp band is convention (an accounting quantity; the band only suppresses drift flap)
RULE_R4_CLEAR_CASH_PCT = 39.0

# Rev 4 F21 — the fixed disclosure, shared by R0 and M04's weight tile. Measured:
# an ETF counted as one holding understates true single-name exposure by ~5pp
# (AAPL 38.5% look-through vs 33.3% naive), enough to cross a 35% cap silently.
# retranslate:[ar,ms]
ETF_OVERLAP_DISCLOSURE = (
    "counts each ETF as one holding; index-fund overlap is not looked through "
    "— your true single-name exposure can be higher."
)

# ── Validator constants (Rev 4 §LLM prompt contract pt 5; consumed by M06) ──

HEADLINE_MAX_WORDS = 16           # Rev 4 §F1

# Appended to any headline built on a `partial: true` block. Two tokens, which
# is why every §F1 template is sized to 14 or fewer — the pair has to stay
# inside HEADLINE_MAX_WORDS, so the two constants belong together.
# retranslate:[ar,ms]
F1_PARTIAL_MARKER = " (partial data)"

# Rev 4 F19 — §F1/§F2/§F5 are the plain-language register and must not match
# any of these; §F3/§F4 are exempt. Measured 0/10 false positives on plausible
# §F2 prose. This is why §F1's R² requirement is surfaced as "the market
# explains only X% of this book's day-to-day moves" — the literal form would
# trip the check by design.
REGISTER_LEXICON = (
    "shrinkage", "covariance", "OLS", "R²", "standard error", "estimator",
    "regression", "confidence interval", "kurtosis", "Ledoit", "Markowitz",
    "Choueifaty", "CAPM", "pro-forma", "eigen", "quadratic", "sampling error",
    "heteroskedastic", "JPM", "EWMA",
)

# ── Metric value units (M09 §3.1 units pin, made machine-readable) ──────────
#
# Tier-1 engine values are decimal FRACTIONS (M04 §3.4) and any consumer
# rendering a percent multiplies by 100. Tier-2 `realised_*` values arrive
# ALREADY IN PERCENT (M03 §3.5) because they are computed from stored portfolio
# values, not from returns. Tier-1 `beta` / `effective_bets` /
# `weight_concentration` are dimensionless RATIOS and are never rendered with a
# percent sign at all.
#
# The distinction is not cosmetic: applying the fraction convention to a Tier-2
# block publishes a 15.34% drawdown as "1534.00%" — measured, and it reached §F3
# while §F1 rendered the same block correctly, so the two sections of one
# Finding disagreed by two orders of magnitude. The map is consulted by BOTH the
# renderer and the allow-list builder, so a percent-unit value can never be
# registered at the fraction scale and vice versa.
UNIT_FRACTION = "fraction"
UNIT_PERCENT = "percent"
UNIT_RATIO = "ratio"
METRIC_VALUE_UNIT = {
    "portfolio_volatility": UNIT_FRACTION,
    "beta": UNIT_RATIO,
    "tracking_error": UNIT_FRACTION,
    "effective_bets": UNIT_RATIO,
    "risk_contribution": UNIT_FRACTION,
    "mcr": UNIT_FRACTION,
    "weight_concentration": UNIT_RATIO,
    "typical_bad_month": UNIT_FRACTION,
    "scenario_panel": UNIT_FRACTION,
    "realised_max_drawdown": UNIT_PERCENT,
    "realised_return": UNIT_PERCENT,
}
# Only the value-bearing keys carry the block's unit. `t_eff`, counts and window
# lengths are plain numbers in every block, and treating them as percentages
# would widen the allow-list for no gain.
PERCENT_UNIT_KEYS = ("value", "standard_error")

# Rev 4 §LLM prompt contract pt 5(c) — the fixed constants list checked in beside
# the sufficiency block. Rev 4's own list is open ("citation years, …"); M06
# extends THESE sets, never a local one. Scale-aware, never unioned: the union
# was MEASURED to false-accept "Your beta is 62." on a book whose 0.62 lives in
# the percent set.
VALIDATOR_FIXED_RAW = {
    "1952", "2004", "2008",      # citation years: Markowitz; Ledoit & Wolf; Choueifaty & Coignard
    "252", "504", "126", "21",   # annualisation, data window, sufficiency floor, trading-day month
    "1.96", "1.645", "0.97",     # z for a 95% CI, z for the 1-in-20 month, λ
    "500",                       # "S&P 500" tokenizes as 500
    "30", "4", "3", "6", "2",    # fat-tail block: κ≈30 crash bound, the 4.0× factor, the κ 3–6 range, §5.3.2's tail
    "5.3",                       # "§5.3.2" tokenizes as 5.3 and 2
    "1", "20",                   # "1-in-20 bad month"
    "10", "10000",               # $10k / $10,000 starting capital
    "11", "12",                  # the M11 / M12 BOK lesson cross-reference
    "2020", "2022",              # scenario-episode display years
    "0",                         # "no commissions, spreads, or taxes" adjacents
}
VALIDATOR_FIXED_PCT = {
    "95",                        # 95% CI
    "40",                        # R1's own template literal, "more than 40%"
    "97",                        # Barber & Odean's zero-cost line
    "2.0", "2.5", "10", "13",    # the fat-tail honesty range: 2.0–2.5pp = 10–13%
}

# Rev 4 validator category (b): which slots of which rule are NUMBERS, and at
# which scale. A slot not listed here is text and is never registered as one.
RULE_SLOT_SCALE = {
    "R0": {"cap": "pct", "weight": "pct"},
    "R1": {"risk_share": "pct", "weight": "pct", "threshold_mention": "pct"},
    "R2": {"n": "raw", "dr2": "raw"},
    "R2b": {"rho": "raw"},
    "R3": {"beta": "raw", "r2_pct": "pct", "window": "raw"},
    "R4": {"cash": "pct"},
    "R5": {"covered": "pct"},
}

# Rev 4 §F5's speech-act pin, made structural. The publisher's exclusion is
# unavailable to us (15 U.S.C. §80b-2(a)(11)(D); Lowe v. SEC), worldwide store
# distribution puts the FCA/MiFID II/CMA/SC perimeters in scope at alpha, and
# the live site states the product "does not and will not give investment
# advice" — so this has to hold on EVERY path, including the deterministic one.
# Prompt instructions are not controls (CR038); these are.
F5_FORBIDDEN_IMPERATIVES = (
    "buy", "sell", "trim", "cut", "reduce", "add", "increase", "decrease",
    "rebalance", "hedge", "diversify", "exit", "close", "open", "rotate",
    "shift", "move", "switch", "take", "avoid",
)
F5_FORBIDDEN_PHRASES = (
    "you should", "you must", "you need to", "we recommend", "we suggest",
    "consider selling", "consider buying", "consider trimming",
)

# Rev 4 §F3's verbatim pin. One constant, no forked copies — the whole point is
# that the same sentence appears in every Finding forever.
# retranslate:[ar,ms]
NON_STATIONARITY_CAVEAT = (
    "These estimates describe the window just past. In market stress, "
    "correlations between holdings rise sharply — diversification measured in "
    "calm markets can overstate the protection available in a crisis."
)

# Verbatim from mobile/lib/l10n/app_en.arb `disclaimerShort`. Line 1 of every
# Finding's head block, and the line the archived journal entry carries forever.
# retranslate:[ar,ms]
DISCLAIMER_SHORT = "Educational simulation. Not investment advice."

# Rev 4 journal storage plan — the wire value. M08 lands the EntryType member and
# the Dart mapping in one commit; until then M06 resolves it lazily and the call
# raises loudly rather than writing an entry no client can name (DEF210).
PORTFOLIO_HEALTH_ENTRY_TYPE = "portfolio_health_analysis"

# ── Bad-print detector params (Rev 4 data-hygiene gate) ─────────────────────
#
# The ALGORITHM is owned by M01 — its detector takes these as arguments so it
# keeps its zero-dependency contract (build/README.md seam register).
#
# Rev 4 pins the screen as "a same-day |return| exceeding a VOLATILITY-SCALED
# bound with next-day reversal". A flat absolute bound cannot satisfy that: on a
# bond ETF at 0.26%/day, a 40% threshold sits at ~150 daily sigma, so the screen
# is inert on exactly the low-volatility holdings where a phantom print is most
# visible and most damaging.
#
# Both numbers below were measured on real market data (2026-08-02, script
# preserved in the CR136 audit pack): 18 tickers x 3 two-year windows including
# the COVID crash and the 2022 drawdown, 8,671 genuine days that ALSO pass the
# reversal test. The largest of those in sigma units is BND 2020-03-12 at 27.6σ
# (|r| = 5.44%, sigma = 0.20%/day) — which is why the floor exists; the largest
# above the floor is XLU 2020-03-16 at 11.0σ (|r| = 11.36%). k = 15 leaves 36%
# headroom over that worst genuine event and fires on none of the 8,671.
#
# The direction of the calibration is deliberate and one-sided: a genuine crash
# day is the single most informative observation a volatility estimate has, and
# a false drop removes the user's holding from their own risk analysis. Missing
# a small phantom costs a little accuracy; dropping a real crash costs the
# estimate exactly when it matters most.
BAD_PRINT_SIGMA_MULT = 15.0              # |r| must exceed this many robust (MAD-scaled) daily sigma
BAD_PRINT_MIN_ABS_RETURN = 0.10          # ...AND this absolute floor, so a near-zero sigma cannot make the bound absurd
BAD_PRINT_REVERSAL_MIN_FRACTION = 0.60   # next trading day must undo ≥60% of the PRICE move (not of the return — an exact round trip scores 1.0 at any magnitude)
BAD_PRINT_HARD_ABS_RETURN = 1.00         # |r| > 100% is flagged unconditionally

# ── Access-gate defaults (Rev 4 §Access gating) ─────────────────────────────
# M07 wires these as the `Settings` field defaults. `trial` is the launch
# default; flipping to full plan-gating later is a config change, not a code
# change. The Health-card TILES are free in every mode — gating applies only to
# full Finding generation.
GATE_MODE_DEFAULT = "trial"
# DEF219. `TRIAL_DAYS_DEFAULT` no longer gates — `evaluate_gate` counts
# Findings, not days — and is reported to clients as advisory only. The trial
# budget is 3 rather than 7 because at Saiful's monthly cadence a user needs a
# FIRST reading, a SECOND to compare it against, and a third for a direction;
# seven was sized for a daily/weekly product that this is not. Three Findings
# cost ~20s of on-prem GPU in total (measured: 6,539 ms for the one real
# Finding on live Alpha), so the number is chosen for what a trialist needs to
# see, not for what it costs us.
TRIAL_DAYS_DEFAULT = 14
TRIAL_FINDINGS_DEFAULT = 3
# Unreachable for a single-portfolio user: `dedupe_key = <portfolio_id>:<date>`
# already caps them at one Finding per day. This only binds a user holding 2+
# portfolios.
DAILY_CAP_DEFAULT = 2
PLANS_DEFAULT = "TRADER,FLOOR_MANAGER"

# ── Machine-readable states (no user-visible copy anywhere in M04) ──────────

# ── Snapshot provenance (DEF217) ────────────────────────────────────────────
# An all-cash book is valued from `current_cash` alone: no quote is consulted,
# so `_aggregate_source_from_quotes` hits its empty-dict default and labels an
# EXACT valuation `mock_walk`. That collision is what made the label useless —
# a correct row and a fabricated one were indistinguishable, so nothing could
# filter on it. Naming the cash case restores the label's one job.
SNAPSHOT_SOURCE_CASH_ONLY = "cash_only"

INSUFFICIENT_SHORT_WINDOW = "short_window"
INSUFFICIENT_T_OVER_N = "t_over_n"
INSUFFICIENT_BENCHMARK_MISALIGNED = "benchmark_misaligned"
INSUFFICIENT_DROPPED_WEIGHT = "dropped_weight_exceeded"
INSUFFICIENT_FEED_UNAVAILABLE = "feed_unavailable"
INSUFFICIENT_ZERO_VARIANCE = "zero_variance"
INSUFFICIENT_SPARSE_GRID = "sparse_grid"      # DEF213 — see GRID_DENSITY_MAX

STATUS_OK = "ok"
STATUS_NO_HOLDINGS = "no_holdings"
STATUS_REFUSED_MOCK_DATA = "refused_mock_data"

BASIS_TOTAL_VALUE = "total_value"
BASIS_INVESTED_SLEEVE = "invested_sleeve"
BASIS_WEIGHTS = "weights"
