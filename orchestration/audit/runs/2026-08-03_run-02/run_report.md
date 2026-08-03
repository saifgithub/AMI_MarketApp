# Audit run 2026-08-03 run-02 — CR136-M05 (rule engine), round 1

Auditor track U. Submission `orchestration/audit/cr/CR136-M05.architect.md`.
SCOPE: chunk. GATE: independent. depends-on: none (but both M02 and M05 must be
COMPLETE before promote, per the submission's own note).

Verdict: **AWAITING_FIXES** — 2 MAJOR, 1 MINOR. Full finding text in
`orchestration/audit/cr/CR136-M05.auditor.md`; this report is the evidence trail.

## Delivery + environment

SHA `a4265fd5` on `origin/main`. Audited detached in
`.claude/worktrees/audit-CR136-r1`, clean at checkout (DEF159 — never the shared
tree). Interpreter `"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python"`
from the worktree's `backend/`.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| `test_cr136_rule_engine.py` | 33 passed, 1.35s | **33 passed, 1.22s** | match |
| full `tests/unit/` at the SHA | 2240 passed, 13 warnings, 274.16s | **2240 passed, 13 warnings, 282.90s** | match |
| QA3 (R0 → invested-sleeve) | 1 fail claimed / 2 in addendum | **2 failed, 31 passed** | addendum exact |
| QA4 (R1 band → single line) | 2 fail | **2 failed, 31 passed** | claim exact |

QA3's two: `test_r0_agrees_with_the_gate_on_a_book_holding_CASH`,
`test_r0_sector_cap_agrees_with_the_allocation_surface_on_a_cash_book`.
QA4's two: `test_r1_hysteresis_and_forced_clear`,
`test_between_the_lines_preserves_whatever_state_it_was_in`.

## M1 — R2b weight floor, two bases (MAJOR)

Traced the two filters to source:

- `portfolio_health.py:612-614` — `floor = RULE_R2B_MIN_PAIR_WEIGHT_PCT / 100.0`
  tested against `v_weights`; `v_weights[i] = p.value / covered_invested`
  (`:367`), survivors only.
- `portfolio_rules.py:316-318` — `weight_of.get(a,0.0) >= RULE_R2B_MIN_PAIR_WEIGHT_PCT`;
  `weight_of` is `invested_weight_pct = 100.0 * p.value / full_invested` (`:643`),
  all risky holdings including dropped.

One constant, two denominators, and `covered_invested <= full_invested`.

Probe (`tests/unit/test_zz_auditor_probe.py` in the scratch worktree, not
committed) — book of 4 survivors + 1 dropped holding at 20% of invested value:

```
AAA: M04 covered-basis=5.6250pp (emitted=True) | M05 full-basis=4.5000pp (kept=False)
BBB: M04 covered-basis=5.6250pp (emitted=True) | M05 full-basis=4.5000pp (kept=False)
rho=0.97 vs fire line 0.90 -> R2b fired=False
```

Affected band: any pair between 4.0% and 5.0% of full invested value, whenever
drops approach `DROPPED_WEIGHT_MAX` (0.20). Direction is under-firing only — M05
can only subset M04's list, so the submission's stated worry ("the rule sees pairs
the payload never mentions") does not occur; the opposite does.

Existing coverage cannot catch it: `test_r2b_boundaries_and_weight_floor`
(:306-322) uses only `included=True` holdings, so both denominators are equal in
the fixture.

## M2 — R0 boundary rounding (MAJOR)

Breach test uses the unrounded weight; the slot is rounded at
`portfolio_rules.py:232` and rendered at 1 dp beside the cap by `_f5`
(`portfolio_finding.py:538-543`). Rendered end-to-end through the real `_f5` at a
true weight of 35.04% against a 35.0% cap:

```
  actual weight=35.04 cap=35.0 fired=True
  breach slot=[{'scope': 'name', 'cap_pct': 35.0, 'name': 'AAA', 'weight_pct': 35.0}]
  RENDERED §F5 SENTENCE:
  - Your mandate caps a single holding at 35.0%. AAA is at 35.0% of your total portfolio value today.
```

Severity was genuinely arguable (all financial surfaces round); resolved toward
MAJOR per PROTOCOL's doubt rule, and because R0's stated purpose is eliminating
exactly this shown-vs-enforced split.

## m1 — sector-cap boundary unpinned (MINOR)

Mutated `portfolio_rules.py:245`
`> sector_cap_frac + _SECTOR_EPSILON` → `>= sector_cap_frac - _SECTOR_EPSILON`,
run by me directly:

```
33 passed in 1.22s     (mutant — SURVIVED)
33 passed in 1.22s     (restored, git diff --stat empty)
```

Shipped operator is correct and matches `sector_allocation.py:238`
(`weight > cap + 1e-9`) exactly, so this is a missing guard rather than a defect.

## Mutations that were correctly killed

| Mutation | Observed | Verdict |
|---|---|---|
| `_step` high-is-bad fire `>=` → `>` | 3 failed, 30 passed | KILLED (`test_r1_boundaries`, `test_r2b_boundaries_and_weight_floor`, `test_r4_boundaries_and_hysteresis`) |

## §8 attack list — dispositions

1. **R0's total-value exception, re-derived from `safety_floor`** — upheld.
   `single_name_cap_pct` → percentage points; `position_pct`
   (`trading_math/portfolio.py:35-39`) → percent; gate compares
   `weight_pct > cap_single_name` (`safety_floor.py:632`), strict; R0 compares
   strict `>` at `portfolio_rules.py:227`; both over total portfolio value. A
   holding exactly AT its cap is compliant on both sides.
2. **The bands** — not re-simulated. The band *widths* are Rev 4 pins already
   audited at the CR136 doc lane (runs 2026-08-02_run-01/02, COMPLETE r2); what
   this lane owed was that the shipped constants match those pins and that the
   operators around them are right, which is what QA4 and the `_step` mutation
   establish. Re-running `c7_r1_band_derivation.py` would re-audit a closed lane.
3. **Hysteresis round-trip through a soft-deleted Finding** — correct and
   deliberate: `portfolio_finding.py:962-970` takes `rule_states` unconditionally
   from the prior while gating idempotent replay on `deleted_at is None`. A delete
   does not reset a fired rule.
4. **R2b's weight floor vs M04's pair list** — this is M1. The seam does not hold.
5. **Adapter vs explicit-kwargs core** — cannot disagree; sole production caller is
   `api/portfolio.py:202` through `evaluate_rules_for_context`.

## Also probed, clean

- Boundary operators observed directly: fire at `>=`, clear at `<`, sticky between,
  value exactly on the clear line stays fired. R3 band at SE 0.1 → `fire=1.36
  clear=1.24`.
- Unrecognised prior state → `cleared` (probed with a garbage value; rule did not
  start fired).
- `Other`-bucket skip is unreachable-by-`Cash`: `sector_of` returns a stored GICS
  sector or `Other`, never `Cash`, and `HoldingInput` carries no cash row — so R0
  skipping only `OTHER` where `api/portfolio.py:91` excludes
  `{OTHER, CASH}` is a difference with no reachable input.
- `RULE_SLOT_SCALE["R0"]`'s `cap`/`weight` keys are vestigial; `_f5` and the
  allow-list builder both special-case the `breaches` shape
  (`portfolio_finding.py:536-547`, `:686-690`), so registration is correct.

## Out-of-scope (architect mints the ID)

Zero-variance benchmark leg reaches an unguarded raise —
`portfolio_health.py:353` gates on risky diagonals only, so a flat benchmark
reaches `beta_r2` at `:436`:

```
cov_risky diagonals: [0.000185918270811292, 0.00018515755547357038]
benchmark diagonal : 0.0
all(cov_risky diag <= 0) -> False   <-- guard does not trip
beta_r2 raises: benchmark variance is zero — beta is undefined
```

Unit-level observation; end-to-end effect inferred from the call path, not
reproduced (no backend/DB on the Mac). In `portfolio_health.py` — neither lane's
file list.
