# Audit run 2026-08-03 run-01 — CR136-M02 (estimator core), round 1

Auditor track U. Submission `orchestration/audit/cr/CR136-M02.architect.md`.
SCOPE: chunk. GATE: independent. depends-on: none.

## Delivery check

SHA `a4265fd5` resolves and is ON `origin/main` (`git branch -r --contains
a4265fd5` → `origin/HEAD -> origin/main`, `origin/main`). Audited detached in
`.claude/worktrees/audit-CR136-r1` @ `a4265fd58c7fe2d53cca30153325e19bf860167d`,
`git status --porcelain` clean at checkout — never the shared tree (DEF159).

## Reproduced measurements

| Check | Submission | Auditor | Result |
|---|---|---|---|
| `test_cr136_estimator_core.py` | 42 passed, 1.69s | **42 passed** (75 with M05, 2.71s) | match |
| full `tests/unit/` at the SHA | 2240 passed, 13 warnings, 274.16s | **2240 passed, 13 warnings, 282.90s** | match |

Interpreter: `"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m
pytest`, run from the worktree's `backend/` (BINDINGS — bare `pytest` resolves to
Homebrew and lacks the deps).

## Blind independent re-derivation (numpy, written from the stated definitions)

Not a read of the implementation — an independent numpy implementation built from
the mathematical definitions, then diffed. Seed `default_rng(20260803)`, n=6,
T=504, 3-factor model + a forced near-duplicate pair (measured
`corr(a2,a3)=0.9712809399208977`), last index as benchmark.

Max relative difference, mine vs module, per function:

| Function | max abs diff | max rel diff |
|---|---|---|
| `ewma_covariance` | 5.421010862427522e-20 | 6.80024784998181e-16 |
| `t_eff` (T=504) | 2.842170943040401e-14 | 4.328180964405069e-16 |
| `portfolio_sigma` | 0.0 | 0.0 |
| `euler_contributions` | 0.0 | 0.0 |
| `mcr` | 0.0 | 0.0 |
| `dr_squared` | 0.0 | 0.0 |
| `beta_r2` (beta, r2) | 0.0 | 0.0 |
| `tracking_error` | 0.0 | 0.0 |
| `hhi_effective_n` | 0.0 | 0.0 |
| `se_sigma` | 2.168404344971009e-19 | 3.798791964460118e-16 |
| `se_beta` | 1.3877787807814457e-17 | 1.3435445055235788e-16 |
| `bad_month`, `annualize_vol`, `append_zero_row` | 0.0 | 0.0 |

Every disagreement is at or under float64 epsilon (~2.2e-16 relative); nothing
approaches 1e-12. Summation-order noise (`math.fsum` vs numpy pairwise), not
disagreement.

**`t_eff` direct sum vs the closed form** `(1+λ)/(1−λ)·(1−λᵗ)/(1+λᵗ)` — the
submission's claim that the closed form is an independent check, tested:

- T=126: direct `62.89744156709606`, closed `62.897441567096045`, rel `2.259369278167305e-16`
- T=252: direct `65.60576200215165`, closed `65.60576200215164`, rel `2.1660985684056133e-16`
- T=504: direct `65.66663839646255`, closed `65.66663839646252`, rel `4.328180964405069e-16`

T=126 → 62.897 reproduces the constants file's "ESS 62.9" pin.

**Identities.** `sum(euler_contributions)` = 1.0 exactly (deviation 0.0).
`Σᵢwᵢ·mcrᵢ` = `0.006541572337355486` vs σₚ `0.006541572337355487` (deviation
−8.673617379884035e-19).

**Cash invariance** (pin 6 — the exactness claim), `append_zero_row` at c = 0.0 /
0.2 / 0.5: σₚ scales by exactly (1−c) (deviation 0.0 at every c); β deviation max
−5.551115123125783e-17; risky-leg Euler contributions max deviation
1.3877787807814457e-17; DR² deviation 0.0; R² deviation max 5.551115123125783e-17.
Exact to float epsilon, as claimed.

**Short series (the M04 seam, architect's attack #4).** T=1 → the all-zero 6×6
matrix, no exception, matching the docstring's "the formula's own output".
`t_eff(0.97,1)` = 1.0. T=2 → a genuine non-zero matrix, `t_eff(0.97,2)` =
1.9995362975939. Module and independent implementation agree at both.

**Cost.** `ewma_covariance` n=6,T=504: 0.9691 ms; n=30,T=504: 13.0273 ms (mean of
20). Pure-Python is not a latency problem at this size.

## Fixture provenance — the claim that decides whether the suite means anything

Submission §9 attack 1: "They are literals. Regenerate a subset with your own
numpy and check the generator is not the same code path as the implementation."

- **No import path to the implementation.** `scripts/cr136_generate_fixtures.py:26-32`
  imports only `argparse`, `sys`, `datetime.date`, `numpy` (plus a `yfinance`
  import local to `--verify-scenarios`, unrelated to fixture generation).
  `grep -n "trading_math\|portfolio_risk"` on the generator matches docstring
  prose only (lines 11, 17) — no executable import. The generator reimplements
  every formula in numpy with a different code shape (`np.outer`, explicit weight
  vectors) than the module's stdlib loops.
- **Bit-exact regeneration.** All 13 generated fixtures (55 individual floats)
  regenerated and compared via `ast.literal_eval` with `==`, no tolerance:
  `FIXTURE_A_COV`, `FIXTURE_B_{COV,SIGMA,DR2,CONTRIBUTIONS,MCR}`,
  `FIXTURE_D_{COV,BETA,R2,VAR_P,VAR_B,TE_DAILY,SE_BETA}` → **ALL BIT-EXACT MATCH**,
  zero mismatches.
- **Deterministic.** No RNG anywhere in the generator (`grep -in "random\|seed\|rand("`
  → no match); two runs byte-identical.
- **numpy is genuinely not a declared test dependency.** Absent from
  `pyproject.toml`'s `[project.dependencies]` and `.dev`; present only transitively
  via `yfinance>=1.0`. `grep -rn numpy app/trading_math/` → no matches. The
  stdlib-only contract is enforced in-suite by `test_stdlib_purity_guard` (AST
  parse, import roots ⊆ {math, __future__}), which passes.

Two fixtures are NOT generator output, and both are explained rather than blind:
`FIXTURE_D_T_EFF = 62.897` is the generator's own hand-set input constant
(`cr136_generate_fixtures.py:144`), independently re-derived in-suite by
`test_t_eff_pins` and cross-checked against the closed form; fixture (c) (uniform-ρ)
is built inline by closed-form algebra (`_uniform_rho_cov`, test line 128), which
the test says outright.

## Revert-proof QA — re-performed, not read

Each mutation applied one at a time, suite run, file restored via
`git checkout --` and re-run green before the next. Baseline 75 passed across
both module suites.

| Mutation | Submission claim | Observed | Result |
|---|---|---|---|
| QA1 `se_sigma` → `σ̂/√(2·504)` | 2 fail | **2 failed, 40 passed** | claim exact |
| QA2 EWMA weights → `1/(1−λ)` denominator | 8 fail | **8 failed, 34 passed** | claim exact |

QA1 failures: `test_se_sigma`, `test_se_sigma_is_not_the_equal_weight_formula` —
the two named. QA2 failures include `test_ewma_covariance_known_answer`,
`test_t_eff_direct_sum_matches_the_closed_form`,
`test_the_non_uniform_fixtures_are_the_estimator_own_output`.

**Auditor-authored mutations the submission did NOT claim** — aimed at the three
guards §9 asked me to attack:

| Mutation | Observed | Verdict |
|---|---|---|
| `beta_r2`: delete the `w[b_index] != 0.0` guard (`if False`) | 1 failed, 41 passed | **KILLED** — `test_beta_r2_requires_a_zero_weight_benchmark_leg` |
| `_PSD_DUST` 1e-12 → 1e-3 (clamp loose enough to swallow a real negative) | 3 failed, 39 passed | **KILLED** — `test_the_psd_dust_clamp_is_exercised_on_the_clamping_side`, `test_the_tracking_error_clamp_is_exercised_on_real_dust`, `test_se_beta_clamp_is_bounded_not_unbounded` |

Both guards §9 nominated as loosenable are real guards. Worktree restored:
`git diff --stat` empty.

## Architect's own attack list, dispositions

1. **Fixtures** — verified above, claim holds.
2. **`beta_r2`'s exact `w[b_index] == 0.0` check** — guard present at
   `portfolio_risk.py:298-302`; covered by `test_beta_r2_requires_a_zero_weight_benchmark_leg`.
   Mutation-checked below.
3. **PSD-dust clamps** — `_PSD_DUST = 1e-12` is an ABSOLUTE bound while daily
   variances run ~1e-4…1e-6, so in relative terms the clamp is ~1e6–1e7 looser
   than float noise on a 500-term sum requires. It cannot bite in this pipeline:
   `ewma_covariance` returns `Σ_j w_j·d_j d_jᵀ` with all `w_j > 0`, a sum of PSD
   rank-1 matrices, hence PSD by construction — so `wᵀΣw < 0` is reachable only
   from a caller-supplied hand-built Σ, which M02's contract excludes. Recorded as
   an observation, not a finding; it would matter the day a caller passes an
   externally-built matrix.
4. **`t_eff` on a very short series** — verified above (T=1, T=2, both sides of
   the M04 T≥126 floor).

## Verdict

Zero BLOCKER, zero MAJOR. See `orchestration/audit/cr/CR136-M02.auditor.md`.
