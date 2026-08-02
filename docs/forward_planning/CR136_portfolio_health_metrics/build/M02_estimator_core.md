# CR136 build — M02: Estimator core

> Conforms to CR136 Rev 4 + build/README.md. Where this doc and Rev 4 disagree, Rev 4 wins.

**AUDIT LANE.** M02 is math-critical (with M05): when built, submit through
`orchestration/audit/`; the Rev 4 verification-fleet scripts are the
auditor's re-derivation pack.

## 1. Purpose

The deterministic math kernel of CR136: the EWMA-weighted covariance estimator
(Rev 4 "Estimator pins" 1–7) and every second-moment Tier-1 metric derived
from it — σₚ, Euler risk contributions, MCR, DR², β+R², tracking error,
HHI→effective-N, typical bad month, scenario replay, `se_sigma` (T_eff-based)
and WLS `se_beta`. Pure functions over stdlib types; no I/O, no config, no
numpy, no app imports. M04 feeds it aligned daily-return series; every policy
decision (sufficiency floors, scenario constants, thresholds) lives in M04.

A **new** module beside `portfolio_stats.py`, not an extension: that file is
sample-convention (n−1), rounds for BOK display, returns `None` on invalid
input; this one is population-style weighted, unrounded, and raises — mixing
conventions in one file invites the silent-misuse class CR040 targets.

## 2. Files

**New** (each header-docstring one-liner given verbatim):

- `backend/app/trading_math/portfolio_risk.py` —
  `"""EWMA portfolio risk estimator core (CR136 M02) — one weighted covariance matrix (λ=0.97, weighted-demeaned, population-style) and every second-moment metric Rev 4 pins derived from it. Stdlib-only; no app imports; callers gate sufficiency."""`
- `backend/scripts/cr136_generate_fixtures.py` —
  `"""CR136 M02 fixture generator — DEV-ONLY. Independent numpy implementation that prints known-answer literals for test_cr136_estimator_core.py; also verifies the M04 scenario-episode constants against SPY (--verify-scenarios). Never imported by tests or app code."""`
- `backend/tests/unit/test_cr136_estimator_core.py` —
  `"""CR136 M02 estimator-core tests — offline-numpy known-answer fixtures (literals, provenance in comments), Euler/closed-form identities, N=1/N=2 boundaries, t_eff pins, stdlib-purity guard."""`

**Touched:**

- `backend/app/trading_math/__init__.py` — add the new public names under a
  `# CR136 portfolio risk estimator core (M02)` comment group in the import
  block (after `portfolio_stats`, `__init__.py:39-45`) and in `__all__`
  (`__init__.py:74-135`); extend the "Scope today" docstring paragraph
  (`__init__.py:18-31`) with one clause: `portfolio_risk` (EWMA covariance +
  CR136 whole-portfolio risk metrics, M02). The design contract at
  `__init__.py:9-16` (pure, stdlib-only, no `app` imports) binds this module.

No other file changes; no Settings fields in M02 (`docker-compose.yml`
untouched). Registers/row files are the coordinating session's job.

## 3. Implementation spec

### Module constants (in `portfolio_risk.py`)

`trading_math` cannot import from `app`, so the *estimator-definition*
constants live here (M04 imports these). *Policy* constants — SUFFICIENCY
floors, rule thresholds, scenario episode returns, gate defaults — live in
M04's single constants module (build/README.md "Constants in one place").

```python
EWMA_LAMBDA = 0.97            # Rev 4 estimator pin 1 — RiskMetrics *investing* factor; 0.94 is the trading factor and is wrong here
TRADING_DAYS_PER_YEAR = 252   # Rev 4 estimator pin 6 — trading-day series only
TRADING_DAYS_PER_MONTH = 21   # Rev 4 F13 — 1 month = 21 trading days
BAD_MONTH_Z = 1.645           # Rev 4 F13 — 1-in-20 one-sided Gaussian z
```

### Conventions binding every function

- **Input orientation (README contract, verbatim):** `returns` is
  `list[list[float]]`, rows = assets, cols = time, **newest last**; column
  `j` (0-indexed, `j = 0..T-1`) has age `T-1-j`.
- **Stdlib types only**, all outputs **unrounded** — M06/M09 format last.
- **Errors:** structurally invalid input ⇒ `raise ValueError` naming the
  violation. Never `None`, never NaN, never a silent default (CR040; README
  pins non-Optional returns). M04 gates sufficiency *before* calling.
- **Matrix validation** (shared `_validate(w, cov)` helper): `len(w) ==
  len(cov)`, every row length `== n`, `|cov[i][j] - cov[j][i]| <= 1e-9`
  (mirrors `portfolio_stats.py:89-92`, but raising).
- **Zero-weight legs:** every `w`-based function accepts the joint matrix
  with the benchmark leg (and appended cash row) at weight exactly `0.0`;
  such legs contribute exactly `0.0` to every sum (Rev 4 estimator pin 2).

### Function contracts

1. `ewma_covariance(returns: list[list[float]], lam: float = EWMA_LAMBDA) -> list[list[float]]`
   - Unnormalized weight for column `j`: `u_j = lam ** (T-1-j)`; normalized
     `w_j = u_j / Σu` — normalized over the available window, newest last.
   - Weighted mean per asset: `μ_a = Σ_j w_j · r[a][j]`. **Weighted-demeaned.**
   - `Σ_ab = Σ_j w_j · (r[a][j] − μ_a)(r[b][j] − μ_b)` — **population-style
     weighted covariance, NO dof correction** (no `1/(1−Σw²)` factor; the
     fixtures define exactness). Compute upper triangle, mirror.
   - Raises `ValueError`: empty `returns`, any empty row, ragged rows,
     `lam` outside `(0, 1)`.
   - `T = 1` returns the all-zero matrix (the formula's own output; the
     T ≥ 126 floor is M04's).
   - Micro-check (single asset, `[0.0, 0.02]`, λ=0.97): weighted population
     variance = `λ/(1+λ)² · Δ²` = `0.97/1.97² · 0.0004` ≈ `9.99768e-05`.
2. `t_eff(lam: float, t: int) -> float`
   - Build the same normalized truncated weights; return `1 / Σ_j w_j²`.
     Implemented as the **direct sum**, not the closed form — the closed form
     `(1+λ)/(1−λ) · (1−λ^t)/(1+λ^t)` is the tests' independent check.
   - Raises `ValueError`: `t < 1`, `lam` outside `(0, 1)`.
   - Pins: asymptote `(1+λ)/(1−λ)` ≈ 65.667 at λ=0.97; **62.897 at t=126**
     (Rev 4 sufficiency table's "T_eff ≈ 63–66"; ESS 62.9).
3. `portfolio_sigma(w: list[float], cov: list[list[float]]) -> float`
   - `√(wᵀΣw)`. Daily σ when `cov` is daily; annualize via `annualize_vol`.
   - After `_validate`: if `wᵀΣw < 0`, clamp to `0.0` when `≥ -1e-12`
     (floating dust), else `ValueError` (non-PSD input — a wrong number that
     must not ship, same stance as `portfolio_stats.py:98-99`).
4. `euler_contributions(w: list[float], cov: list[list[float]]) -> list[float]`
   - `(Σw)_i = Σ_j cov[i][j] · w_j`; contribution_i = `w_i · (Σw)_i / σₚ²`.
   - Sums to 1.0 (Euler identity — structural); zero rows contribute exactly
     `0.0`. Raises `ValueError` when `σₚ == 0.0`.
5. `mcr(w: list[float], cov: list[list[float]]) -> list[float]`
   - `(Σw)_i / σₚ` (Rev 4 F3 — the true per-dollar quantity). Raises
     `ValueError` when `σₚ == 0.0`. Identity: `Σ_i w_i · mcr_i = σₚ`.
6. `dr_squared(w: list[float], cov: list[list[float]]) -> float`
   - `DR = (Σ_i w_i · σ_i) / σₚ` with `σ_i = √cov[i][i]`; return `DR²`.
     Cash-invariant with the zero row (Rev 4 F9, verified exact). Raises
     `ValueError` when `σₚ == 0.0`.
7. `beta_r2(w: list[float], cov: list[list[float]], b_index: int) -> tuple[float, float]`
   - **Joint-matrix form** — build/README.md contract 2 explicitly allows
     "OR computed from the joint matrix"; pinned here because Rev 4 defines
     `Cov_w(p,b)/Var_w(b)` *"from the same Σ"* with the benchmark as a leg —
     no separate portfolio leg is estimated.
   - Requires `w[b_index] == 0.0` (`ValueError` otherwise — the benchmark is
     an estimation leg, never a holding).
   - `cov_pb = Σ_i w_i · cov[i][b_index]`; `var_b = cov[b_index][b_index]`;
     `var_p = wᵀΣw`.
   - `beta = cov_pb / var_b`; `r2 = cov_pb² / (var_p · var_b)` (weighted ρ²).
   - Raises `ValueError` when `var_b == 0` (flat benchmark) or `var_p == 0`.
8. `tracking_error(sigma_p: float, sigma_b: float, beta: float) -> float`
   - `√(σₚ² + σ_b² − 2βσ_b²)` — Rev 4 verbatim. Scale-consistent: both σ
     daily → TE daily; both annualized → TE annualized.
   - Radicand `< 0`: clamp to `0.0` when `≥ -1e-12` (identical book vs
     benchmark), else `ValueError` (inconsistent inputs).
   - Pin: `(0.2620, 0.1587, 1.301)` → `0.168216…` → 16.82%.
9. `hhi_effective_n(weights: list[float]) -> float`
   - `HHI = Σ vᵢ²`; returns effective-N `= 1/HHI`. Precondition (documented,
     not re-normalized here): `weights` are M04's invested-sleeve weights
     summing to 1 (Rev 4 F9 basis pin). Raises `ValueError` on empty or
     all-zero input.
10. `bad_month(sigma_p_ann: float) -> float`
    - `BAD_MONTH_Z · σ · √(TRADING_DAYS_PER_MONTH / TRADING_DAYS_PER_YEAR)`
      — Rev 4 F13 verbatim (`1.645 · σₚ · √(21/252)`). Fractions in and out
      (`0.262` → `0.124419` = 12.44%). The product ships **only** this
      monthly figure; 1d/1w variants exist only as test identities.
11. `scenario_replay(beta: float, episode_return: float) -> float`
    - `beta × episode_return`. Episode constants (COVID 2020-02-19→03-23 ≈
      −0.339; 2022 drawdown 2022-01-03→10-12 ≈ −0.254) live in M04's
      constants module; verified by `--verify-scenarios` (below) + M11 live.
12. `se_sigma(sigma_hat: float, t_eff: float) -> float`
    - `sigma_hat / √(2 · t_eff)` — Rev 4 sufficiency pin; **never** the
      equal-weight `σ/√(2T)` (understates ~27% under EWMA). Raises
      `ValueError` when `t_eff <= 0`.
13. `se_beta(var_p: float, var_b: float, beta: float, t_eff: float) -> float`
    - `√(max(0.0, var_p − beta²·var_b) / (t_eff · var_b))` — algebraically
      Rev 4's WLS form `SE(β̂) = (σ_ε,w/σ_b,w)/√T_eff` with weighted residual
      variance `σ_ε,w² = Var_w(p) − β²Var_w(b)`; the `max(0, ·)` clamp covers
      floating dust at R² → 1. Raises `ValueError` when `var_b <= 0` or
      `t_eff <= 0`.
14. `append_zero_row(cov: list[list[float]]) -> list[list[float]]`
    - New `(n+1)×(n+1)` matrix: input copied into the top-left block, last
      row and column exact `0.0`. Input **not** mutated (fresh lists).
15. `annualize_vol(sigma_daily: float) -> float`
    - `sigma_daily · √TRADING_DAYS_PER_YEAR` (×√252, Rev 4 estimator pin 6)
      — the one annualisation helper; everything else operates on daily.

**There is NO Ledoit–Wolf shrinkage anywhere** (Rev 4 estimator pin 1 —
removed entirely; F1/F2). Do not implement it, do not leave a stub for it.

### Cash handling (Rev 4 estimator pins 2–3, verbatim behaviour)

Σ is estimated over **risky holdings plus the benchmark leg only**. M04 then
calls `append_zero_row(cov)` and extends `w` with the cash weight (`w` spans
total value, cash as the zero row). The Euler identity holds exactly with the
zero row — structural, by bilinearity: `(Σw)_cash = 0` ⇒ contribution
`= 0.0` exactly, Σ contributions still `= 1.0`. Verified by test, not assumed.

### Fixture generation (offline, dev-only)

`backend/scripts/cr136_generate_fixtures.py`:

- **numpy allowed here only** — already in the backend venv transitively via
  yfinance (`backend/pyproject.toml:27-31`), no new dependency. Run by hand
  (`backend/.venv/bin/python backend/scripts/cr136_generate_fixtures.py`);
  never imported by tests or app code.
- **Independent implementation:** weighted-demeaned population covariance via
  explicit numpy weight vectors (`np.average` + outer-product accumulation).
  Must NOT import or call `app.trading_math` — independence is the point
  (Rev 4 estimator pin 7).
- **Deterministic:** input return series are hand-written decimal literals in
  the script (no RNG), duplicated into the test file. Expected outputs
  printed at full `repr` precision as a paste-ready snippet, each block
  tagged with script name, date, numpy version (provenance comment).
- Emits fixtures (a)–(d) of §5. For fixture (b) the script **asserts the
  correlation structure is non-uniform before emitting** (F8 pin: at least
  one pair ρ ≥ +0.6, one pair ρ ≤ −0.3, one pair |ρ| ≤ 0.25) and aborts
  otherwise — a uniform-ρ fixture cannot detect a degenerate estimator.
- `--verify-scenarios`: fetches SPY adjusted close via yfinance (dev-only
  network), computes the two episode returns, compares to the pinned
  constants (−33.9%, −25.4%); exits non-zero when |diff| > 0.5 pp (tolerance
  is this doc's choice — Rev 4 pins "≈"; adjusted series drift with dividend
  adjustments). Satisfies the Tier-1 table's "constants verified against the
  SPY adjusted series at build time (M02 acceptance)"; M11 re-verifies live.

## 4. Out of scope for this module

- **Sufficiency gating** (T ≥ 126, T/N ≥ 5, dropped-weight 20%, short-history
  drop, mock-mode refusal) — M04. M02 computes whatever it is given.
- **Metric block JSON / uncertainty contract** and **policy constants**
  (SUFFICIENCY, thresholds, hysteresis bands, scenario episodes, gate
  defaults) — M04.
- **Date alignment, SPY inner join, bad-print data-hygiene screen** — M01
  (exact algorithm there) + M04. M02 receives aligned equal-length rows;
  `portfolio_stats.py:58`'s length-only `beta()` is the cautionary
  precedent — alignment is fixed upstream, not here.
- **Rounding/formatting, percent rendering** — M06/M09. **Tier-2 rolling
  MDD** — M03 (`returns.py`/`portfolio.py` territory).
- **User-visible strings: none in M02** — no AMI-naming or
  `retranslate:[ar,ms]` obligations arise here (they bind M06/M09).
- **Ledoit–Wolf / any shrinkage** — permanently out (Rev 4 pin 1).

## 5. Tests

One file: `backend/tests/unit/test_cr136_estimator_core.py`. Imports the
public names from `app.trading_math` (package root, matching
`test_trading_math.py`). Fixture literals at the top in a `# ── FIXTURES —
generated by backend/scripts/cr136_generate_fixtures.py …` section.

**Fixtures (literals checked in; provenance comments mandatory):**

- (a) **EWMA known-answer**: N=3, T=8, λ=0.97, hand-written return literals →
  expected 3×3 covariance at full precision.
- (b) **Non-uniform correlation structure** (F8): N=4, T=8 returns with the
  non-uniform ρ structure asserted by the script → expected cov, σₚ, DR²,
  `euler_contributions`, `mcr` literals for weights `[0.4, 0.3, 0.2, 0.1]`.
- (c) **Uniform-ρ closed form** — built in-test analytically (no script
  needed): N=10, equal σ=0.02, equal weights, uniform ρ.
- (d) **β/R²/TE joint fixture**: 3 risky + SPY-stand-in benchmark leg (4×4
  joint matrix from EWMA over T=8 literals), `w = [0.5, 0.3, 0.2, 0.0]` →
  expected `beta`, `r2`, `var_p`, `var_b`, `te_daily`, `se_beta` literals.

**Cases (names indicative; boundaries per Rev 4 acceptance):**

1. `test_ewma_covariance_known_answer` — fixture (a); per-entry
   `abs ≤ 1e-15` vs literals.
2. `test_ewma_covariance_single_asset_closed_form` — `[[0.0, 0.02]]`, λ=0.97:
   `abs(var − 0.97/1.97**2 * 0.0004) < 1e-18`.
3. `test_ewma_covariance_raises` — ragged rows raise `ValueError`; empty
   input raises; `lam` ∈ {0.0, 1.0, −0.1} raises; and fixture (a) rows
   time-reversed produce a *different* matrix (guards silent oldest-last).
4. `test_t_eff_pins` — at `t=5000` (asymptotic), `round(t_eff(λ, t), 3)` ==
   `32.333 / 65.667 / 99.000` at λ = `0.94 / 0.97 / 0.98`;
   `abs(t_eff(0.97, 126) − 62.897) < 1e-3`; `abs(t_eff(0.97, 252) − 65.61)
   < 5e-3` (Rev 4 pin 4's ESS 65.61); direct sum vs closed form
   `(1+λ)/(1−λ)·(1−λ^t)/(1+λ^t)` agree `< 1e-9`; `t_eff(0.97, 0)` raises.
5. `test_portfolio_sigma` — fixture (b) literal; asymmetric matrix raises;
   dimension mismatch raises.
6. `test_euler_sum_with_cash_row` — fixture (b) cov → `append_zero_row` →
   `w = [0.3, 0.225, 0.15, 0.075, 0.25]` (25% cash):
   `abs(sum(contribs) − 1.0) <= 1e-9` (Rev 4 bound); cash entry `== 0.0`
   **exactly**; fixture (d)'s benchmark leg at `w=0.0` likewise `== 0.0`.
7. `test_mcr` — fixture (b) literals; identity
   `abs(Σ wᵢ·mcrᵢ − σₚ) < 1e-12`.
8. `test_dr_squared` — fixture (c) closed form:
   `abs(dr2 − 1/(1/N + (1−1/N)·ρ)) < 1e-9`, `round(dr2, 2) == 1.22` at
   ρ=0.8 and `== 3.57` at ρ=0.2 (Rev 4 acceptance values); fixture (b)
   non-uniform literal (F8); cash invariance — DR² with 40% cash + zero row
   `==` DR² invested-only `< 1e-12` (Rev 4 F9).
9. `test_beta_r2_te_joint_fixture` — fixture (d) literals for `beta`, `r2`;
   `w[b_index] != 0` raises; flat benchmark (`var_b == 0`) raises;
   `tracking_error(√var_p, √var_b, beta)` matches the fixture's `te_daily`
   `< 1e-12`.
10. `test_tracking_error_pin` — `round(100 * tracking_error(0.2620, 0.1587,
    1.301), 2) == 16.82` (Rev 4 numeric pin); identical inputs
    `(0.2, 0.2, 1.0)` → `0.0` (clamp); grossly inconsistent inputs raise.
11. `test_hhi_effective_n` — ten `0.1` weights → `10.0 ± 1e-9`; `[1.0]` →
    `1.0`; `[0.9, 0.1]` → `abs(x − 1/0.82) < 1e-9`; empty and all-zero raise.
12. `test_bad_month_pins` — exact identity `bad_month(s) ==
    BAD_MONTH_Z * s * sqrt(21/252)`; `round(100 * bad_month(0.262), 2) ==
    12.44` (the monthly figure the product ships); √-time-family identity
    inline (not module functions): `1.645*0.262*sqrt(1/252)` → 2.71% and
    with `sqrt(5/252)` → 6.07%, each via `round(100*x, 2)` (Rev 4 acceptance
    2.71/6.07/12.44 at σ=26.2%).
13. `test_scenario_replay` — `round(scenario_replay(1.301, -0.339), 4) ==
    -0.4410`; `scenario_replay(0.0, -0.339) == 0.0`.
14. `test_se_sigma` — exact identity vs `s/√(2·t_eff)`;
    `round(se_sigma(0.20, 65.667), 6) == 0.017452`; `t_eff <= 0` raises.
    Rev 4's "equal-weight formula is NOT used" holds structurally: `se_sigma`
    takes only `t_eff`; no function takes a raw `T` for an SE (grep in §6).
15. `test_se_beta` — fixture (d): `se_beta(var_p, var_b, beta, t_eff=62.897)`
    matches the fixture literal `< 1e-12`; clamp case
    `se_beta(0.0001, 0.0002, 1.0, 60.0) == 0.0`; `var_b <= 0` and
    `t_eff <= 0` raise.
16. `test_append_zero_row` — 2×2 → 3×3; top-left preserved; last row+col all
    exactly `0.0`; input matrix unmutated after the call.
17. `test_n1_boundary` — `w=[1.0]`, `cov=[[0.0004]]`: `portfolio_sigma ==
    0.02` (σₚ = the holding's vol), `dr_squared == 1.0` exactly (DR² ≡ 1),
    `euler_contributions == [1.0]` (share ≡ 100%), `mcr == [0.02]` — defined
    outputs, no NaN (Rev 4 small-books pin).
18. `test_n2_boundary` — 2-asset EWMA from inline T=8 literals: every
    function returns a finite float; nothing degenerate (no LW anywhere —
    Rev 4 removed shrinkage entirely).
19. `test_sigma_zero_raises` — all-zero `w` (or zero matrix) →
    `euler_contributions` / `mcr` / `dr_squared` raise `ValueError`; and
    `test_annualize_vol` — `annualize_vol(0.0165) == 0.0165 *
    math.sqrt(252)` exact.
20. `test_stdlib_purity_guard` — parse `portfolio_risk.py` with `ast`:
    every `Import`/`ImportFrom` is `math`, `__future__`, or relative
    (`from .` …); explicitly assert no `numpy` and no `app` import (the
    `__init__.py:9-16` contract, made structural).

## 6. Acceptance

Checklist a reviewer runs from the repo root (`/Volumes/Extreme
Pro/AMI_MarketApp` — quote the path):

- [ ] `pytest backend/tests/unit/test_cr136_estimator_core.py -q` green, then
      `pytest backend/tests/unit/ -q` (full suite) still green.
- [ ] `grep -in -E "numpy|from app|import app|ledoit|shrink" backend/app/trading_math/portfolio_risk.py`
      — no matches (stdlib purity; no LW, Rev 4 pin 1).
- [ ] `grep -rn "cr136_generate_fixtures" backend/tests/` — no matches (the
      script is never imported by tests).
- [ ] The only SE divisor in the module is `2 * t_eff`; no function takes a
      raw `T` for an SE (Rev 4: the equal-weight formula is NOT used).
- [ ] Fixture blocks carry provenance comments (script name, date, numpy
      version); fixture (b)'s comment states its non-uniform ρ structure (F8).
- [ ] `backend/.venv/bin/python backend/scripts/cr136_generate_fixtures.py`
      re-emits literals identical to those checked in (determinism), and
      `--verify-scenarios` exits 0 (episode constants within 0.5 pp of SPY).
- [ ] `python -c "from app.trading_math import ewma_covariance, t_eff, portfolio_sigma, euler_contributions, mcr, dr_squared, beta_r2, tracking_error, hhi_effective_n, bad_month, scenario_replay, se_sigma, se_beta, append_zero_row, annualize_vol"`
      succeeds (backend venv, `backend` on path).
- [ ] Every new file's header docstring matches §2.
- [ ] **Audit lane:** submitted through `orchestration/audit/` per
      build/README.md; commit tagged `(AT:R<N> CR136)`, pathspec-commit only.

## 7. Hand-off

After M02 lands, M04 (metrics engine) may assume:

- The 15 functions of §3 exist under `app.trading_math` with exactly those
  signatures and semantics; outputs unrounded; structural invalidity raises
  `ValueError` — a bug to surface, not catch-and-null (M04 gates first).
- **One joint EWMA matrix** (risky holdings + SPY leg at `w[b_index] = 0.0`)
  yields σₚ, Euler, MCR, DR², β+R², TE — build Σ once, derive everything
  (build/README.md contract 2). Cash appended **after** estimation via
  `append_zero_row`; Euler exact with the zero row (tested; cash exactly 0).
- `EWMA_LAMBDA`, `TRADING_DAYS_PER_YEAR`, `TRADING_DAYS_PER_MONTH`,
  `BAD_MONTH_Z` are importable estimator-definition constants; M04's
  constants module holds every policy number (SUFFICIENCY, scenario episode
  returns −0.339/−0.254, thresholds) and must not duplicate these four.
- SEs are `t_eff`-based only; `t_eff(EWMA_LAMBDA, T)` is what M04 publishes
  in the `t_eff` field of every metric block carrying an SE.
- N=1 and N=2 books produce defined outputs — no special-casing in M04
  (single-holding copy is M06/M09's). Fixture provenance + the offline
  generator feed M11's audit pack; the scenario-constant SPY check ran at
  build time and re-runs live in M11.
