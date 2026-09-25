<!--
run_report.md: auditor run report for CR233-BE round 1 (U68, taken over from U67). It holds the
evidence behind orchestration/audit/cr/CR233-BE.auditor.md.
-->

# 2026-09-25: CR233-BE round 1 (auditor U68)

**SHA audited:** lane `0167e999`, live at backend `685dbdd0` and mobile `+111`. **Verdict:**
`AWAITING_FIXES`, with 0 BLOCKER, 1 MAJOR and 0 MINOR.

## Environment

- **Scratch worktree:** `.claude/worktrees/audit-U68-L` at `685dbdd0`. The scratch probe
  `test_u68_probe_cr233be.py` was run against the real `/v1/sim/preview` and `/v1/sim/submit`
  routes through FastAPI TestClient on the sqlite fixture, and is deleted with the worktree.

## Probes (mark 408.14)

| Probe | Observed |
|---|---|
| P1 AMI path, BUY STOP trigger 1% of mark, $30k at mark vs $10k cash | preview accepted, fill_price 4.08; submit refused (300% > 150% cap) |
| P2 snapshot path, same order, $100k equity, cap 10% | STOP preview accepted at 4.08; the same qty as MARKET is refused (30% > 10%) |
| P3 snapshot path, BUY STOP_LIMIT trigger 412.22, limit 816.28 | accepted, sized at trigger (9.0%); can commit up to 17.8% at the limit |

## Mutations (reverted, tree re-checked clean)

| Mutation | Result |
|---|---|
| `preview_trade` drops `trigger_price` (api/sim.py:708) | 3 failed |

## Tests

- `test_cr233_preview_price_basis.py`, `test_sim_engine.py` and
  `test_def419_per_account_mandate_check.py`: 55 passed, EXIT=0.
- Full suite at `685dbdd0`: 6849 passed, 1 failed (the pre-existing `test_def247`).

FOREIGN: not run.
