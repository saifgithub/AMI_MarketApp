<!--
run_report.md: auditor run report for DEF417 round 1 (U68, taken over from U67). It holds the
evidence behind orchestration/audit/cr/DEF417.auditor.md.
-->

# 2026-09-25: DEF417 round 1 (auditor U68)

**SHA audited:** lane `6205dcd2`, merged and live at `685dbdd0` (`alpha-2026-09-25-4`). **Verdict:**
`AWAITING_FIXES`, with 0 BLOCKER, 2 MAJOR and 1 MINOR.

## Environment

- **Scratch worktree:** `.claude/worktrees/audit-U68-L` at `685dbdd0`. The scratch probe
  `test_u68_probe_def417.py` was never committed and is deleted with the worktree.
- **Throwaway Postgres:** `audit_u68_l_pg`. The migration round trip is recorded in the DEF416
  report.
- **Live, read-only:** in-container file hashes, plus `SELECT`s on
  `classification_universe_snapshots`, `sharia_universe_snapshots` and `ticker_reference`.

## Probes

| Probe | Observed |
|---|---|
| Live snapshot coverage | latest as_of 2026-09-24: 502 sectors, 0 market_caps, 0 avg_volumes (not yet refreshed since promotion) |
| Measured set vs tradable set | parent 503; ticker_reference 13,246 active, 12,743 not in parent (96%) |
| GNS (real microcap, active symbol) via SimEngine.submit, liquid_only ON, S&P-only fresh universe | accepted=True, blocked_by=None, liquidity=unknown, advisories=[] |
| NANO (fixture microcap inside the map) | accepted=False, blocked_by=compliance, liquidity=excluded |
| mobile/lib references to `liquidity` | 0 |

## Mutations (each reverted, tree re-checked clean)

| Call site mutated | DEF417 test file |
|---|---|
| sim_engine.py:1472 submit, universe ignored | 2 failed |
| sim_engine.py:2671 preview, universe ignored | 1 failed |
| room_runner.py:4087 _assemble_verdict, None | 1 failed |
| room_runner.py:5885 live-PM enforce_safety_floor, None | 25 passed (survives) |
| sim_engine.py:1983 fill_resting_order, universe ignored | 25 passed (survives) |

## Tests

- `test_def417_liquid_only_enforcement.py`, `test_safety_floor.py` and
  `test_def061_compliance_enforcement.py`: 90 passed, EXIT=0.
- Full suite at `685dbdd0`: 6849 passed, 1 failed (the pre-existing `test_def247`).

FOREIGN: not run.
