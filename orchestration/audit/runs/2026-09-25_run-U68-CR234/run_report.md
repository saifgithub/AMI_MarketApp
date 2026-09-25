<!--
run_report.md: auditor run report for CR234 round 1 (U68, taken over from U67). It holds the
evidence behind orchestration/audit/cr/CR234.auditor.md.
-->

# 2026-09-25: CR234 round 1 (auditor U68)

**SHA audited:** lane `fdcf9343`, shipped in mobile `+111` (the `lib/` at `685dbdd0` is identical to
`5c751bb8`). The backend enum is live on `685dbdd0`. **Verdict:** `AWAITING_FIXES`, with 0 BLOCKER,
1 MAJOR and 3 MINOR.

## Environment

- **Scratch worktree:** `.claude/worktrees/audit-U68-L`. I ran `flutter test` on the Mac, with no
  other flutter runs active.

## Tests and mutations (each reverted, tree re-checked clean)

| Run | Result |
|---|---|
| CR234 client, section and identity tests | 47 passed, EXIT=0 |
| Full mobile suite at +111 | `01:52 +1688: All tests passed!`, EXIT=0 |
| M1: paper-host check moved after `_dio.delete` | 14 passed (survives, MAJOR-1) |
| M2: no audit row on a successful cancel | 1 failed |
| M3: no provider refresh after a failed cancel | 11 passed (survives, MINOR-1) |
| Control: `submitOrder` POSTs before its host check | 3 failed (that guard works) |

## Reads

- **Backend Alpaca HTTP calls:** only the OAuth token POST (`alpaca_service.py:91`). DEF145 holds.
- **`hexPurple` elsewhere on the portfolio screen:** the sector palette (`portfolio_screen.dart:1153`)
  and `RestingOrderState.unknown` (`resting_orders_section.dart:92`).
- **Exception types:** `AlpacaOrderRejected` is not an `AlpacaException`, and `_cancel` catches
  only the latter.
- **Load-bearing AMI card guards, before vs after the extraction:** ellipsis 6/6, Flexible 5/5,
  committed 6/6, available 1/1, TweenAnimationBuilder 1/1.

FOREIGN: not run.
