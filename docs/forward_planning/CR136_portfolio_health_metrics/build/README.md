# CR136 build plan — module index and contracts

**What this is:** the development documentation for CR136 Rev 4, broken into
small, independently-deliverable modules (M01–M11), each sized for a single
build session by an Opus or Sonnet coder. **The pins live in
[`../CR136_portfolio_health_metrics.md`](../CR136_portfolio_health_metrics.md)
(Rev 4)** — every module doc conforms to it; where a module doc and Rev 4
disagree, Rev 4 wins and the module doc is defective. Nothing here re-derives
a threshold; every number was pinned by measurement (see Rev 4's verification
record).

**Reviews behind the pins:** `../EXTERNAL_PM_REVIEW.md`, `../PM_REVIEW.md`,
both integrated in Rev 4 after independent re-simulation.

---

## Module index

| # | Module | Layer | Depends on | Doc |
|---|---|---|---|---|
| M01 | Market-data foundation | backend | — | [M01_market_data_foundation.md](M01_market_data_foundation.md) |
| M02 | Estimator core | trading_math (stdlib-only) | — (fixtures offline) | [M02_estimator_core.md](M02_estimator_core.md) |
| M03 | Snapshot job + Tier 2 | backend | M01 | [M03_snapshot_job_tier2.md](M03_snapshot_job_tier2.md) |
| M04 | Metrics engine service | backend | M01, M02 | [M04_metrics_engine.md](M04_metrics_engine.md) |
| M05 | Rule engine | backend | M04 | [M05_rule_engine.md](M05_rule_engine.md) |
| M06 | Finding renderer + validator + LLM path | backend | M04, M05 | [M06_finding_renderer_validator.md](M06_finding_renderer_validator.md) |
| M07 | API + access gating | backend | M04, M06 | [M07_api_gating.md](M07_api_gating.md) |
| M08 | Journal integration | backend + mobile | M06 | [M08_journal_integration.md](M08_journal_integration.md) |
| M09 | Mobile: Health card + Finding + journal UI | mobile | M07 shape frozen | [M09_mobile_ui.md](M09_mobile_ui.md) |
| M10 | Backfill script | melehost ops | M03 | [M10_backfill.md](M10_backfill.md) |
| M11 | Verification, audit pack + promotion | cross | all | [M11_verification_promotion.md](M11_verification_promotion.md) |

**Build order:** M01 ∥ M02 → M03 ∥ M04 → M05 → M06 → M07 ∥ M08 → M09 → M10 →
M11. M02's fixtures need numpy **offline only** (fixture-generation script
runs outside the repo test suite; literals are checked in). M09 can start UI
scaffolding from SCREEN_DESIGNS.md (+ its Rev 2 amendments) before M07
freezes, but wire-up waits for the API shape.

**Audit lane:** M02 and M05 are the math-critical modules — Rev 4's risk
class recommends independent audit for exactly these two. Submit them through
`orchestration/audit/` when built; the Rev 4 verification scripts double as
the auditor's re-derivation pack.

---

## Conventions binding every module

- **Governance:** every commit tags `(AT:R<N> CR136)`. Registers are
  generated — row files only. Pathspec-commit only; never bare `git commit`.
- **Mac is pure editor:** verification = `pytest backend/tests/unit/ -q`
  (sqlite tempfile) + `flutter analyze` / `flutter test`. Anything live goes
  through melehost (`/promote-to-alpha`); never start a backend on the Mac.
- **Degrade loudly (CR040):** no silent fallback anywhere. New Settings
  fields MUST be forwarded in `docker-compose.yml`'s api-alpha env block or
  `backend/tests/unit/test_config_compose_parity.py:71` fails.
- **`trading_math/` contract:** stdlib-only, pure functions, no app imports,
  copy-portable (`trading_math/__init__.py`). No numpy at runtime or test
  time — fixtures are precomputed literals.
- **Constants in one place:** all sufficiency floors, rule thresholds,
  hysteresis bands, validator constants, scenario episodes, and gate defaults
  live in ONE constants module (M04 owns it; M05/M06 import from it). Never
  scattered literals. Every constant carries a comment naming its derivation
  in Rev 4.
- **AMI by name** in any user-visible string; "LLM" fine in code/logs.
- **File headers:** every new file gets a docstring explaining what it is and
  why. Comments only where the *why* is non-obvious.
- **i18n:** any new user-facing EN string flags `retranslate:[ar,ms]`; l10n
  keys carry context comments.
- **DEF210 precedent:** backend↔mobile journal enum parity is enforced by
  `backend/tests/unit/test_journal_entry_type_parity.py` — M08 updates it.

## Cross-module interface contracts (the freeze points)

1. **Metric block schema** (M04 → M05/M06/M07/M09, and CR137 later): exactly
   Rev 4's uncertainty-contract JSON — fields `metric, value, standard_error,
   n_observations, t_eff, window_days, sufficient, partial, dropped_holdings
   [{ticker, reason}], low_explanatory_power, contains_etfs, backcast, basis,
   engine_version`. `sufficient:false ⇒ value & standard_error null`.
2. **Estimator API** (M02 → M04), stdlib types only (lists/floats/dicts):
   - `ewma_covariance(returns: list[list[float]], lam: float = 0.97) ->
     list[list[float]]` — weighted-demeaned; rows = assets, cols = time,
     newest last. Raises on ragged input.
   - `t_eff(lam: float, t: int) -> float` — `1/Σwᵢ²` of the normalized
     truncated weights.
   - `portfolio_sigma(w, cov) -> float`; `euler_contributions(w, cov) ->
     list[float]` (sums to 1.0; zero rows contribute 0.0); `mcr(w, cov) ->
     list[float]`; `dr_squared(w, cov) -> float`; `beta_r2(cov, p_index,
     b_index) -> tuple[float, float]` OR computed from the joint matrix;
     `tracking_error(sigma_p, sigma_b, beta) -> float`;
     `hhi_effective_n(weights) -> float`;
     `bad_month(sigma_p_ann) -> float` (1.645·σ·√(21/252));
     `se_sigma(sigma_hat, t_eff) -> float`; `se_beta(...) -> float` (WLS).
   - M04 builds ONE joint EWMA matrix (risky holdings + SPY leg) and derives
     everything; cash appended as exact zeros AFTER estimation.
3. **Rule result shape** (M05 → M06): `{rule_id, fired: bool, state:
   "fired"|"cleared", slots: {…}, based_on: [metric ids]}` + `rule_states`
   dict persisted in the Finding payload and read back from the newest prior
   Finding (hysteresis memory + idempotency share one read).
4. **API surface** (M07 → M09):
   - `GET /v1/portfolio/health/{user_id}` — tiles payload (metric blocks +
     `generated_at`, `as_of`, gate status summary). Free, never gated.
   - `POST /v1/portfolio/health/{user_id}/finding` — generates + persists a
     Finding; returns the journal entry id + rendered sections; enforces the
     gate (mode/trial/daily-cap/plans) and `(portfolio_id, as_of)`
     idempotency (regeneration same day returns the existing entry).
   - Both `_own`-guarded like the existing sector-allocation route.
5. **Finding artefact** (M06 → M08/M09): head disclosure block + §F1–§F5
   markdown + payload (stripped context, triggered rules with slots,
   `rule_states`, engine_version). Stored verbatim; mobile renders the STORED
   sections, never regenerates.

## Seam register — resolved after the module docs landed

The eleven module docs were written in parallel, so each had to guess at its
neighbours' symbol names. These are now **pinned**; where a module doc differs,
this table wins and the doc is corrected on first touch.

| Seam | Pinned form | Producer → consumer |
|---|---|---|
| Shared constants module | `backend/app/services/portfolio_health_constants.py` | M04 owns; M01/M03/M05/M06/M07 import |
| Trading-day helper | `latest_trading_day() -> date \| None` | M01 → M03 |
| Snapshot vol hook | `predicted_vol_for_snapshot(user_id) -> PredictedVol \| None`, **σ as a decimal fraction** (unit cancellation in the F16 bias test) | M04 → M03 |
| Beta/R² signature | `beta_r2(w, cov, b_index)` — joint-matrix form, requires `w[b_index] == 0.0` | M02 → M04 |
| Engine entry point | `build_health_context(user_id) -> HealthContext` | M04 → M06/M07 |
| Finding entry point | `generate_and_persist_finding(...)` | M06 → M07 |
| Journal reads | `JournalStore.latest_portfolio_health_entry(...)`, `JournalStore.portfolio_health_stats(...)` — **M08 owns; M07 consumes, never re-implements** (retention + soft-delete filters make `list_for_user` unusable here) | M08 → M07 |
| Rule evaluator | `evaluate_rules(context, rule_states) -> (list[RuleResult], rule_states)`; `RULE_TEMPLATES` exported | M05 → M06 |
| Bad-print constants | `BAD_PRINT_*` **values live in the constants module**; M01's detector takes them as arguments (preserves M01's zero-dependency contract) | M04 (values) → M01 (detector) |
| Finding payload keys | `as_of`, `portfolio_id`, `sections` (`head`,`f1`…`f5`), `rule_states`, `context`, `engine_version`; journal `reference_id = portfolio_id` | M06 → M07/M08/M09 |
| Price basis | M01's stored closes are **adjusted**; M10's backfill needs **unadjusted** and therefore fetches its own (`auto_adjust=False`) — M01 serves M10 only for the trading-day grid | M01 ⇄ M10 |

Two module-doc findings that amended Rev 4 itself (already folded in):
**R0 is total-value basis** (the trade gate's own denominator is
`position_pct(market_value, portfolio_value)` — an invested-sleeve R0 would
fire where the gate does not), and **`test_journal_entry_type_parity.py` needs
no code edit** — it enforces same-commit atomicity of the backend enum and the
Dart model.

## Module doc template (each M-doc follows exactly)

1. **Purpose** — one paragraph; which Rev 4 sections it implements.
2. **Files** — new files (with header-docstring one-liner) and touched files
   (exact paths; file:line anchors verified at HEAD).
3. **Implementation spec** — function-by-function contracts, algorithms,
   constants consumed (by name, from the shared constants module).
4. **Out of scope for this module** — explicit non-goals + which module owns
   each neighbour concern.
5. **Tests** — named test files + the specific cases (boundaries at ±ε per
   Rev 4 acceptance); fixtures needed and where they come from.
6. **Acceptance** — checklist a reviewer can run (`pytest …`,
   `flutter test`, grep-able assertions).
7. **Hand-off** — what the next module may now assume exists.
