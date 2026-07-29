# Run report — 2026-07-30_run-01 — CR101-BE1 round 1

VERDICT: COMPLETE (round 1)

- ITEM: CR101-BE1 (SCOPE: `chunk`)
- SHA audited: `9608d56d69a06652ae9f3fc0dee06ece8fc2f533` (`lane/CR101-BE1.coder.api`, from `main` @ `51c24018`)
- Method: detached scratch worktree `.claude/worktrees/audit-CR101-BE1/` (removed after); never audited `main` or the builder's worktree.

## Reproductions

| Check | Command (from worktree `backend/` unless noted) | Result |
|---|---|---|
| Full backend suite | `backend/.venv/bin/python -m pytest tests/unit/ -q` | **1623 passed, 236.26s** (lane claimed 1623 / 235.6s) |
| Touched test files (8) | `pytest test_cr101_be1_settable_risk_caps.py test_mandate_store.py test_safety_floor.py test_position_sizing.py test_def153_single_name_cap_market_order.py test_cr026_sector_allocation.py test_cr056_no_assumed_data.py test_overlay_generator.py -q` | **121 passed** |
| Register drift (worktree root) | `python3 scripts/registers/gen_registers.py verify all` | DEF 175 / CR 118 — OK, no drift |
| Direct-path claim on `main` | `git show 51c24018:backend/app/services/sim_engine.py` | `check_mandate_compliance` at `:536`, `:710`; no risk-tier clamp in file — builder's two-path measurement accurate |
| Pre-CR101 literals | diff deletions vs test pins | `_TOLERANCE_TO_CAP` and `SINGLE_NAME_CAP_PCT == 50.0` match `_PRE_CR101_*` pins exactly |
| Constraint reachability | `schemas/mandate.py:59` | `concentration_tolerance` is `ge=1, le=5` — out-of-range snap unreachable |
| Stale references | grep worktree `app/` | no raw `risk_tier_cap(` outside `sizing.py`; no `SINGLE_NAME_CAP_PCT` / `_TOLERANCE_TO_CAP` left |

## Auditor blind mutation (own, reverted)

M-A1: `safety_floor.single_name_cap_pct` fallback `SINGLE_NAME_ABSOLUTE_CAP_PCT` → `risk_tier_cap(mandate.risk_score)`
(the assign's literal instruction).

- RED: migration proof (acceptance 4 pin), both settable-cap floor tests, four-leg guard,
  safety_floor/position_sizing fallback assertions, and **40 `test_sim_engine.py` tests** —
  same "exceeds single-name cap 3.0%" shape as the builder's 43-failure discovery run.
- Reverted via `git checkout --`; `git diff` empty; worktree confirmed clean.

## Findings

- BLOCKER: 0. MAJOR: 0.
- MINOR (4, observations): m1 split now co-visible in one PM prompt; m2 out-of-range
  tolerance snap (unreachable); m3 raw `SAFETY_FLOOR_BLOCK` export carries `[[CAP]]`;
  m4 user-set cap can exceed the old 50% absolute backstop (fenced, deliberate).
- OUT-OF-SCOPE (architect mints): the direct-submit (50%) vs Room (risk-tier preset)
  single-name cap split for unset users — pre-existing, disclosed, DEF recommended.

## DoD

SCOPE: `chunk` — DoD not owed; one was supplied and verified accurate (scope list,
1623 count, no-manual-verification disclosure, commit tag `9608d56d`, register untouched).
