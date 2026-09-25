<!--
run_report.md: auditor run report for CR233 round 1 (U68, taken over from U67). It holds the
evidence behind orchestration/audit/cr/CR233.auditor.md.
-->

# 2026-09-25: CR233 round 1 (auditor U68)

**SHA audited:** lane `662c11aa`, shipped in mobile `+111`. The mobile `lib/` at `685dbdd0` is
identical to `5c751bb8`. **Verdict:** `COMPLETE`, with 0 BLOCKER, 0 MAJOR and 2 MINOR. The
preview's price basis is graded in CR233-BE, which is AWAITING_FIXES.

## Environment

- **Scratch worktree:** `.claude/worktrees/audit-U68-L`. I ran `flutter pub get` and then
  `flutter test` on the Mac, with no other flutter runs active.

## Tests and mutations (each reverted, tree re-checked clean)

| Run | Result |
|---|---|
| `flutter test test/services/alpaca/` plus the cr227/cr230/cr233/def419 screen tests | 115 passed, EXIT=0 |
| M1: `validateAlpacaOrder` dropped before the POST | 5 failed |
| M2: `'type'` hard-coded to `'market'` | 4 failed |
| M3: short-side stop-loss check off | 1 failed |
| M4: short-side take-profit check off | 77 passed (survives, MINOR-2) |

## Reads

- **User-facing copy:** no "gtc" or "good-till-cancelled" string anywhere in `lib/` (MINOR-1).
- **Alpaca placement gate:** every placement is gated on `preview.accepted`.

FOREIGN: not run.
