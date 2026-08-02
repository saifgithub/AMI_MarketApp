# CR136 build — M04: Metrics engine service

> Conforms to CR136 Rev 4 + build/README.md. Where this doc and Rev 4 disagree, Rev 4 wins.

## 1. Purpose

The deterministic Portfolio Health engine: loads the user's sim book, builds **one**
joint EWMA covariance matrix (risky holdings + SPY leg) via M02, and derives every
Tier-1 block — each wrapped in Rev 4's full uncertainty contract. Implements Rev 4
§"The framework" (Tier 1 table), §"Sufficiency contract", §"Estimator pins" 2–5/8,
and §"The uncertainty contract". This module also owns the **shared constants
module** — the single home for every CR136 constant (README convention: M05/M06/M07
import from here; `trading_math/` stays pure and constant-free).

## 2. Files

**New:**

- `backend/app/services/portfolio_health_constants.py` — header one-liner:
  *"CR136 M04 — single home for every CR136 constant (sufficiency floors, rule
  thresholds + hysteresis bands, validator constants, scenario episodes, bad-print
  params, gate defaults); import from here, never scatter literals."*
  Import-pure: **stdlib only, zero `app.*` imports** (so `app/core/config.py` and
  M01 may import it without cycles).
- `backend/app/services/portfolio_health.py` — header one-liner:
  *"CR136 M04 — deterministic Portfolio Health metrics engine: one EWMA Σ per
  evaluation, every block wrapped in the Rev 4 uncertainty contract."*
- `backend/tests/unit/test_cr136_metrics_engine.py` — header one-liner:
  *"CR136 M04 — engine pipeline, sufficiency boundaries at ±1, and
  uncertainty-contract shape tests."*

**Touched:** none. (M07 wires `Settings`/routes; M05/M06 import the constants.)

**Read-only anchors (verified at HEAD 645de77c):**

- `backend/app/core/config.py:141` — `use_real_market_data: bool = False`; `:450` — `settings` singleton.
- `backend/app/db/models.py:986` — `class TickerReferenceRow`; `:1006` — `is_etf` column (**zero readers today** outside the ingest path `app/services/ticker_reference.py:115/:141/:206/:213` — M04 is its first production consumer).
- `backend/app/db/models.py:321-335` — `SimPortfolioRow` (`current_cash` `:328`), `SimHoldingRow` follows.
- `backend/app/services/sim_engine.py:415-417` — `portfolio_marks_snapshot(user_id) -> (portfolio, marks, total_value, drawdown_pct, price_source)` — the one-fetch snapshot the engine loads holdings/cash/marks from (same call `app/api/portfolio.py:68-70` uses, via `asyncio.to_thread`).
- `backend/app/services/sector_allocation.py:246-260` — `SectorMap` (`.sector(ticker)` `:255`, unknown → `"Other"`); `:321` `default_sector_map()`; `:327` `default_sector_map_async()` — **CR026's real sector resolver; reuse it, do not re-implement**.
- `backend/app/services/market_data.py:72` — `Candle(t, o, h, low, c, v)`; `:150-157` — `_PERIOD_MAP` (today max = 65 daily bars → 64 returns, why M01 exists); `:399/:437` — 60s history TTL (M01 lengthens for daily series).
- `backend/app/trading_math/portfolio_stats.py:58` — `beta()` validates length not dates; the engine aligns by date before any math (Rev 4 estimator pin 5).
- `backend/app/trading_math/__init__.py:1-16` — the stdlib-only/pure contract; why constants live in `services/`, not `trading_math/`.

## 3. Implementation spec

### 3.1 `portfolio_health_constants.py`

Every constant carries a comment naming its Rev 4 derivation (README convention;
acceptance greps for it). Exact names and values:

```python
ENGINE_VERSION = "cr136.v1"        # Rev 4 estimator pin 8
BENCHMARK_TICKER = "SPY"           # Rev 4 estimator pin 5 (SPY adjusted close)
EWMA_LAMBDA = 0.97                 # Rev 4 estimator pin 1 (RiskMetrics investing factor)
DATA_WINDOW_YEARS = 2              # Rev 4 estimator pin 4 (fetch 2y daily bars)
MAX_RETURNS = 504                  # Rev 4 estimator pin 4 (estimator uses up to 504 returns)
TRADING_DAYS_PER_YEAR = 252        # Rev 4 estimator pin 6 (√252, trading-day series only)

# Sufficiency contract (Rev 4 table, supersedes Rev 3)
T_MIN = 126                        # floor: observed aligned returns
T_OVER_N_MIN = 5.0                 # gates ONLY DR²/risk-contribution/MCR (F17)
DROPPED_WEIGHT_MAX = 0.20          # dropped invested weight above this ⇒ Tier-1 insufficient
LOW_R2_THRESHOLD = 0.20            # low_explanatory_power flag; also R3's R² gate (M05)
TIER2_MIN_SNAPSHOTS = 21           # Tier-2 rolling-MDD floor (F10; consumed by M03/M07)
TIER2_MDD_WINDOW_DAYS = 252        # Tier-2 rolling trailing window (F10; consumed by M03)

# Typical bad month (F13; pins reproduce 2.71/6.07/12.44% at σ=26.2%)
BAD_MONTH_Z = 1.645
BAD_MONTH_TRADING_DAYS = 21

# Scenario panel (Rev 4 Tier-1 table; M11 verifies against live SPY at promotion)
SCENARIO_EPISODES = (
    {"id": "covid_2020", "label": "COVID crash",
     "start": "2020-02-19", "end": "2020-03-23", "benchmark_return": -0.339},
    {"id": "drawdown_2022", "label": "2022 drawdown",
     "start": "2022-01-03", "end": "2022-10-12", "benchmark_return": -0.254},
)

# Rule engine thresholds + hysteresis (Rev 4 rule table; consumed by M05)
R1_FIRE_RISK_SHARE = 0.415;  R1_CLEAR_RISK_SHARE = 0.385;  R1_MIN_RISKY_HOLDINGS = 4
R2_FIRE_DR2 = 1.85;          R2_CLEAR_DR2 = 2.15;          R2_MIN_HOLDINGS = 8
R2B_FIRE_RHO = 0.90;         R2B_CLEAR_RHO = 0.85;         R2B_MIN_PAIR_WEIGHT = 0.05
R3_BETA_LINE = 1.3;          R3_BAND_SE_MULT = 0.6         # R3 R² gate = LOW_R2_THRESHOLD
R4_FIRE_CASH = 0.41;         R4_CLEAR_CASH = 0.39

# Validator constants (Rev 4 §LLM prompt contract pt 5; consumed by M06)
HEADLINE_MAX_WORDS = 16
REGISTER_LEXICON = (  # 20 terms, verbatim from Rev 4; §F1/§F2/§F5 must not match
    "shrinkage", "covariance", "OLS", "R²", "standard error", "estimator",
    "regression", "confidence interval", "kurtosis", "Ledoit", "Markowitz",
    "Choueifaty", "CAPM", "pro-forma", "eigen", "quadratic", "sampling error",
    "heteroskedastic", "JPM", "EWMA",
)
VALIDATOR_FIXED_TOKENS = ("252", "95", "1.96", "500", "M11", "M12")  # Rev 4 list is
# open ("citation years, …") — M06 extends THIS tuple, never a local list.

# Bad-print detector params (Rev 4 data-hygiene gate; ALGORITHM owned by M01 —
# M01's detector takes these as arguments so M01 keeps zero deps; values are
# M01's pins, homed here. Copy the numeric values from M01's merged doc.)
BAD_PRINT_SIGMA_MULT = <M01 pin>
BAD_PRINT_REVERSAL_FRACTION = <M01 pin>

# Access-gate defaults (Rev 4 §Access gating; M07 wires them as the Settings
# field defaults — config.py may import this module, it is import-pure)
GATE_MODE_DEFAULT = "trial"
TRIAL_DAYS_DEFAULT = 14
TRIAL_FINDINGS_DEFAULT = 7
DAILY_CAP_DEFAULT = 2
PLANS_DEFAULT = "TRADER,FLOOR_MANAGER"
```

### 3.2 `portfolio_health.py` — function contracts

```python
def compute_health(
    *,
    holdings: list[tuple[str, float]],            # (ticker, quantity), qty > 0
    marks: dict[str, float],                      # ticker → current price
    cash: float,
    series: dict[str, list[tuple[str, float]]],   # ticker → [(iso_date, adj_close)],
                                                  # oldest→newest; includes BENCHMARK_TICKER when fetched
    sector_of: Callable[[str], str],              # SectorMap.sector or test fixture
    etf_tickers: frozenset[str],
    as_of: str,                                   # iso date of evaluation
) -> dict:
```

Pure, deterministic, no I/O, JSON-serialisable return — the unit under test.

```python
async def build_portfolio_health(user_id: UUID, *, sim: SimEngine) -> dict:
```

Orchestration for M07: **step 0, mock refusal** — `settings.use_real_market_data`
false ⇒ return the refusal payload immediately, load nothing. Otherwise:
`portfolio_marks_snapshot` via `asyncio.to_thread` (the `api/portfolio.py:68` idiom)
→ M01 daily-history fetch for holdings + `BENCHMARK_TICKER` (bind to M01's exported
batch/daily-history name; M01 builds first) → `_etf_ticker_set(...)` →
`default_sector_map_async()` → `compute_health(...)`.

```python
def _etf_ticker_set(tickers: Iterable[str]) -> frozenset[str]:
```

First production reader of `is_etf`: one `select(TickerReferenceRow.symbol)
.where(symbol.in_(tickers), is_etf.is_(True))` inside `get_session()` (idiom:
`sector_allocation.py:300-302`). Missing row ⇒ not an ETF (never raises).

### 3.3 Pipeline (ordered; deviations are defects)

1. **Mock refusal** (in `build_portfolio_health`, before any load): return
   `{"status": "refused_mock_data", "reason": "use_real_market_data=false",
   "engine_version", "generated_at"}` — no metrics, no blocks (amber
   system-unavailable state; copy is M09's).
2. **No holdings:** empty book ⇒ `{"status": "no_holdings", "engine_version",
   "generated_at", "as_of"}` (mirrors CR026's empty-`{}` card-hide contract).
3. **Load series** (2y daily adj-close per holding + SPY, via M01); truncate each
   to the newest `MAX_RETURNS + 1` closes.
4. **Bad-print gate:** run M01's detector on each holding's own return series,
   passing `BAD_PRINT_*` from the constants module. Flagged ⇒ holding dropped,
   `dropped_holdings` entry `{"ticker", "reason": "data_quality"}`. Never repaired,
   never silently included. SPY flagged ⇒ benchmark unusable (step 6 path).
5. **Short-history rule:** holding with < `T_MIN` observations (or no series) ⇒
   dropped, entry `{"ticker", "reason": "short_history"}`.
6. **Benchmark check:** SPY series absent, flagged, or contributing < `T_MIN`
   aligned returns after the date inner-join ⇒ beta/TE/scenario blocks
   `sufficient: false` with `insufficient_cause: "benchmark_misaligned"`.
   **Never re-gridded** — no forward-fill, no calendar padding.
7. **Alignment:** inner join on iso dates across surviving holdings (+ SPY when
   usable). T = joined return count, capped at `MAX_RETURNS`. T < `T_MIN` ⇒ all
   estimator-derived blocks insufficient, `insufficient_cause: "short_window"`.
8. **Dropped-weight check:** dropped invested value / full invested value >
   `DROPPED_WEIGHT_MAX` ⇒ every estimator-derived Tier-1 block
   `sufficient: false`, `insufficient_cause: "dropped_weight_exceeded"`
   (`weight_concentration` still ships — accounting).
9. **One Σ:** `ewma_covariance(returns, lam=EWMA_LAMBDA)` (M02) over survivors
   + SPY leg — **built once**; simple daily returns `P_t/P_{t-1} − 1` on adjusted
   closes (linear aggregation keeps wᵀΣw ≡ the weighted portfolio series, Rev 4
   estimator pin 2's verified identity). Cash appended as an exact zero row/column
   AFTER estimation (M02 contract).
10. **Derive all blocks** (§3.4), then assemble the payload (§3.5).

Weight conventions after drops: `covered_invested = Σ qty·mark` over survivors;
invested-sleeve weights `vᵢ = valueᵢ / covered_invested`; LEVEL basis total =
`covered_invested + cash` (R5's `{covered}` copy pins this reading);
`weight_concentration` alone uses the FULL invested book including dropped
holdings (accounting needs no history). Root `cash_fraction = cash /
(full_invested + cash)` (accounting; R4's input).

### 3.4 Blocks — metric id, formula, basis, gates

All vols/returns/weights/shares are decimal fractions (renderer ×100); annualise
daily σ by `√TRADING_DAYS_PER_YEAR`. M02 supplies the math functions; formulas
here are the acceptance meaning.

| metric id | value | SE | basis | gate |
|---|---|---|---|---|
| `portfolio_volatility` | σₚ = √(wᵀΣw) annualised; w over covered total book, cash zero row | `se_sigma(σ̂ₚ, t_eff)` = σ̂ₚ/√(2·T_eff), T_eff = `t_eff(EWMA_LAMBDA, T)` — **never** σ̂/√(2T) | `total_value` | T ≥ T_MIN |
| `beta` | β = cov_w(p,b)/var_w(b) = Σᵢwᵢ·Σ[i,b] / Σ[b,b] from the joint Σ; extension `r_squared` = cov_pb²/(var_p·var_b); `low_explanatory_power` = (R² < LOW_R2_THRESHOLD) — **beta still ships when true** | WLS: (σ_ε,w/σ_b,w)/√T_eff, σ_ε,w² = σ_p² − β²σ_b² (daily) | `total_value` | T ≥ T_MIN + benchmark usable |
| `tracking_error` | √max(0, σₚ² + σ_b² − 2βσ_b²) annualised (Rev 4 identity: 26.20/15.87/1.301 → 16.82%) | null (derived; components carry SEs) | `total_value` | inherits `beta` |
| `effective_bets` | DR² with DR = (Σᵢvᵢσᵢ)/σ_inv over the invested sleeve (cash-invariant, verified) | null by decision (rules gate via hysteresis) | `invested_sleeve` | T ≥ T_MIN AND T/N ≥ T_OVER_N_MIN |
| `risk_contribution` | value = top holding's risk share; extensions `per_holding: [{ticker, invested_weight, risk_share}]` (Euler wᵢ(Σw)ᵢ/σₚ², sums to 1), `per_sector: [{sector, risk_share}]` via `sector_of` (unknown → `"Other"`), `top: {ticker, risk_share, invested_weight}` | null by decision | `invested_sleeve` | same as `effective_bets` |
| `mcr` | value = max per-holding MCR; extension `per_holding: [{ticker, mcr}]`, MCR = (Σv)ᵢ/σ_inv annualised (trim-to-cash convention, F3) | null by decision | `invested_sleeve` | same as `effective_bets` |
| `weight_concentration` | value = HHI = Σvᵢ² over the FULL invested sleeve; extensions `effective_n` = 1/HHI, `holdings_count` | null always (accounting) | `weights` | none — always sufficient |
| `typical_bad_month` | BAD_MONTH_Z · σₚ · √(BAD_MONTH_TRADING_DAYS/252), positive magnitude (renderer shows −X%; σₚ=0.262 → 0.1244) | null (derived) | `total_value` | inherits `portfolio_volatility` |
| `scenario_panel` | value = min over episodes of β·benchmark_return; extension `episodes: [{id, label, start, end, benchmark_return, implied_portfolio_return}]` from `SCENARIO_EPISODES` | null (derived) | `total_value` | inherits `beta` |

N for the T/N gate = surviving risky holdings in Σ (SPY leg and cash excluded).
**σₚ and beta gate on T alone (F17)** — a T/N failure must leave them sufficient.

### 3.5 Payload shape (the frozen M04 → M05/M06/M07/M09 contract)

Root: `status: "ok"`, `as_of`, `generated_at`, `engine_version`, `benchmark:
"SPY"`, `contains_etfs` (any invested holding in `etf_tickers` — R0's disclosure
input), `partial`, `dropped_holdings`, `holdings_count`,
`risky_holdings_count` (N in Σ), `total_value`, `invested_value`,
`covered_invested_value`, `cash_fraction`, `context: {benchmark_vol_ann,
correlation_pairs}`, `blocks: {<metric id>: block}`.

`context.correlation_pairs` (R2b's input; comparisons are precomputed —
Rev 4 prompt-contract pt 2): `[{a, b, rho, weight_a, weight_b}]` for every
surviving pair with both invested weights ≥ `R2B_MIN_PAIR_WEIGHT`, ρ from the
EWMA Σ (Σᵢⱼ/√(ΣᵢᵢΣⱼⱼ)). `benchmark_vol_ann` = √Σ[b,b] annualised, null when the
benchmark is unusable.

Every block carries **exactly** Rev 4's uncertainty-contract fields — `metric,
value, standard_error, n_observations, t_eff, window_days, sufficient, partial,
dropped_holdings, low_explanatory_power, contains_etfs, backcast, basis,
engine_version` — plus the per-block extensions in §3.4 and
`insufficient_cause: str | null` (`"short_window" | "t_over_n" |
"benchmark_misaligned" | "dropped_weight_exceeded"`; the machine hook for F20's
our-limit copy, which M06/M09 own). Field rules:

- `sufficient: false` ⇒ `value` AND `standard_error` **null — never 0.0**;
  `n_observations`/`window_days` still filled (they explain why).
- `partial: true` on every estimator-derived block when any holding was dropped;
  `dropped_holdings` mirrored non-empty on each such block (contract:
  partial ⇒ non-empty on every surface). `weight_concentration.partial` = false.
- `n_observations` = T (aligned daily returns used); `window_days` = calendar-day
  span of the aligned window; `t_eff` non-null exactly where an SE uses it.
- `backcast: true` on all Σ-derived blocks (all of §3.4 except
  `weight_concentration`, which is `false` — today's weights, no past returns).
- `low_explanatory_power`: boolean on `beta`, null elsewhere.
- `contains_etfs`: true on `weight_concentration` (and root) when any invested
  holding is an ETF; false elsewhere.
- `basis` exactly as §3.4's column; `engine_version` on every block and root.

## 4. Out of scope for this module

- Daily-history fetch, batching, TTLs, and the bad-print **algorithm** — M01
  (M04 passes the `BAD_PRINT_*` constants in).
- The math functions and their known-answer fixtures (`ewma_covariance`, `t_eff`,
  `euler_contributions`, `dr_squared`, `se_sigma`, `se_beta`, …) — M02.
- Snapshots, `predicted_vol_ann`, Tier-2 MDD — M03 (it imports
  `TIER2_*`/`ENGINE_VERSION` from the constants module).
- Rule evaluation, hysteresis state machine, templates — M05 (imports `R*`
  constants and reads `context.correlation_pairs`, root `cash_fraction`,
  `contains_etfs`).
- Finding rendering, validator, register check, **all user-visible copy** — M06/M09.
  **M04 ships zero user-visible strings** (machine states only), so no
  `retranslate:[ar,ms]` flags arise here; F20's our-limit copy binds to
  `insufficient_cause` + `n_observations` downstream.
- Routes, `_own` guard, `Settings` fields + compose parity, gating — M07 (wires
  `GATE_*`/`TRIAL_*`/`DAILY_CAP_*`/`PLANS_DEFAULT` as the Settings defaults).
- Journal write/idempotency — M08. Sector-map refresh — CR026 (read-only reuse).

## 5. Tests

`backend/tests/unit/test_cr136_metrics_engine.py` — all against `compute_health`
with crafted/seeded synthetic series (helper `_walk(seed, n, start="2024-01-02")`,
`random.Random(seed)`, weekday-only iso dates; no numpy, no network). Cases:

1. `test_sufficiency_boundary_125_126` — 125 aligned returns ⇒
   `portfolio_volatility.sufficient` false, value+SE null,
   `insufficient_cause == "short_window"`; 126 ⇒ true, value+SE non-null.
2. `test_tn_gate_boundary` — T=249/N=50 (4.98) ⇒ `effective_bets`,
   `risk_contribution`, `mcr` insufficient with cause `"t_over_n"` **while
   `portfolio_volatility` and `beta` are sufficient** (F17); T=250/N=50 (5.0) ⇒ all pass.
3. `test_dropped_weight_boundary` — dropped invested weight 19.9% ⇒ blocks stay
   sufficient with `partial: true`; 20.1% ⇒ every estimator-derived block
   insufficient, cause `"dropped_weight_exceeded"`; `weight_concentration` still sufficient.
4. `test_strip_readiness` — for every insufficient block: `value is None and
   standard_error is None` (never 0.0); sufficient blocks non-null value.
5. `test_mock_mode_refusal` — monkeypatch `settings.use_real_market_data = False`
   ⇒ `build_portfolio_health` returns `status == "refused_mock_data"`, no
   `blocks` key, and performed no snapshot/history load (spy on the callables).
6. `test_benchmark_misalignment_rejected` — SPY series equal length but off-grid
   dates ⇒ `beta`/`tracking_error`/`scenario_panel` insufficient, cause
   `"benchmark_misaligned"`, β null (never re-gridded); `portfolio_volatility` sufficient.
7. `test_etf_flag` — one holding in `etf_tickers` ⇒ root and
   `weight_concentration.contains_etfs` true; all other blocks false.
8. `test_basis_per_block` — assert §3.4's basis map verbatim for all 9 blocks.
9. `test_sector_aggregation` — `sector_of` mapping 2 tickers → "Tech", 1 unknown
   ⇒ `per_sector` has Tech = sum of member shares, `"Other"` bucket present,
   shares sum to 1 ± 1e-9.
10. `test_engine_version_everywhere` — `"cr136.v1"` on root and every block.
11. `test_euler_and_cash_identity` — `per_holding` risk shares sum to 1 ± 1e-9;
    with cash fraction c: total-book σₚ == (1−c)·σ_inv within 1e-12.
12. `test_se_uses_t_eff` — σₚ SE == σ̂ₚ/√(2·t_eff(0.97, T)) and != σ̂ₚ/√(2T)
    (Rev 4: equal-weight formula understates by ~27%).
13. `test_low_explanatory_power` — near-uncorrelated book vs SPY ⇒ R² < 0.20,
    flag true, **β value still non-null**.
14. `test_bad_print_dropped_for_quality` — synthetic spike+reversal series ⇒
    dropped with `reason == "data_quality"`, `partial: true`; a genuine crash day
    (no reversal) passes (detector semantics owned by M01; this asserts wiring).
15. `test_short_history_renormalise` — one holding at 60 obs ⇒ dropped
    (`"short_history"`), surviving `invested_weight`s sum to 1, `partial: true`
    mirrored with non-empty `dropped_holdings` on every estimator-derived block.
16. `test_inheritance` — `typical_bad_month.sufficient` tracks
    `portfolio_volatility`; `scenario_panel.sufficient` tracks `beta`.
17. `test_no_holdings_state` — empty book ⇒ `status == "no_holdings"`, no blocks.
18. `test_single_holding_book` — N=1: σₚ == holding vol × (1−c), DR² == 1.0,
    top risk share == 1.0 (Rev 4 small-book pin).
19. `test_correlation_pairs` — twin series both ≥ 5% weight ⇒ pair present with
    ρ > 0.9; a 4%-weight holding appears in no pair.
20. `test_scenario_and_bad_month_arithmetic` — implied returns == β·(−0.339) and
    β·(−0.254); bad month == 1.645·σₚ·√(21/252) (σₚ=0.262 ⇒ 0.1244 ± 1e-4).
21. `test_gate_default_constants` — `GATE_MODE_DEFAULT == "trial"`, 14, 7, 2,
    `"TRADER,FLOOR_MANAGER"` (M07's compose-parity test covers the Settings side).
22. `test_constants_import_pure` — importing `portfolio_health_constants` pulls
    no `app.*` module (inspect `sys.modules` delta in a subprocess, or assert the
    module's source has no `from app`/`import app`).

Fixtures: M02's checked-in literals cover math correctness; this file's synthetic
series only exercise pipeline/gating, so crafted walks suffice.

## 6. Acceptance

- [ ] `cd backend && pytest tests/unit/test_cr136_metrics_engine.py -q` — all pass.
- [ ] `pytest backend/tests/unit/ -q` — no regressions (sqlite tempfile; Mac is pure editor).
- [ ] `grep -c "Rev 4" backend/app/services/portfolio_health_constants.py` ≥ 15 —
      every constant names its derivation.
- [ ] `grep -rn "0\.415\|1\.85\|0\.97" backend/app/services/portfolio_health.py`
      returns nothing — no scattered literals; all reads via the constants module.
- [ ] `grep -n "import numpy" backend/app/services/portfolio_health*.py` — nothing.
- [ ] Both new source files open with the stated header docstrings.
- [ ] Payload of a sufficient run round-trips `json.dumps` and every block carries
      all 14 contract fields (test 4 + 8 + 10 jointly enforce this).
- [ ] No user-visible strings in either new file (grep for sentence-like literals;
      machine states/reasons only).

## 7. Hand-off

**ADDED AT:R66** — the payload also carries a root-level `holdings` list, one
row per risky holding (dropped ones included):
`{ticker, sector, invested_weight_pct, included, drop_reason, risk_share_pct}`.
M05's `HoldingInput` doc always pinned the sector as "M04 resolves via the CR026
SectorMap" — M04 is the only layer holding `sector_of` — but the list itself was
never emitted, so the M04 → M05 seam had no data path until M07 became the first
caller. `invested_weight_pct` divides by FULL invested value, every risky
holding included: R0 converts it to a total-value weight using the cash
fraction, and that identity only holds while the denominators agree. Dropped
holdings carry a weight because a mandate cap applies to real money whether or
not the price history was long enough to estimate a covariance from.

M05 may now assume: the frozen payload (§3.5) with 9 blocks + root context;
`R*`/hysteresis constants importable from
`app.services.portfolio_health_constants`; `correlation_pairs`, `cash_fraction`,
`contains_etfs`, and `top` risk-contributor pre-computed. M06 may assume:
stripped-context inputs where insufficient blocks are null-valued and every number
it may cite exists as a payload leaf; `REGISTER_LEXICON`/`HEADLINE_MAX_WORDS`/
`VALIDATOR_FIXED_TOKENS` homed in the constants module. M07 may assume:
`build_portfolio_health(user_id, sim=...)` returns exactly one of
`refused_mock_data | no_holdings | ok` payloads, is side-effect-free (no journal
writes), and `GATE_*` defaults are importable for its Settings fields. M03 may
assume `ENGINE_VERSION` and `TIER2_*` constants. CR137 consumes the same §3.5
contract unchanged.
