# Audit run report — CR027 round 2

- **Item:** CR027 (push + in-app notification capability; price alerts first consumer)
- **Submitted SHA:** `444a5469` (on `main`; round 1 was `d92b017d`)
- **Worktree:** `.claude/worktrees/audit-CR027`, reused via `git fetch` + `reset --hard`
- **Date:** 2026-08-01 (Asia/Riyadh)
- **Verdict:** COMPLETE (round 2) — 0 BLOCKER, 0 MAJOR

## Fix-diff scope

`d92b017d..444a5469`: 4 source files — migration (+4/−2), evaluator docstring
(+3/−1), `app_ar.arb` +17, `app_ms.arb` +17 — plus the audit lane's own files.
All round-1-cleared code untouched.

## What I ran (all from the worktree at `444a5469`)

| Check | Result |
|---|---|
| Full backend suite | **1940 passed, 13 warnings, 288.50s** — r1 count reproduced exactly |
| `alembic heads` | single head `8a4ce4f8abc3` |
| Registers verify | OK — DEF 208 / CR 131 |
| l10n parity standalone | 10/10 green |
| Blind mutation (r2): deleted `priceAlertSheetCreate` from `app_ms.arb` | parity gate RED naming exactly that key; restored byte-clean; 10/10 re-green |
| Full flutter suite ×5 | 407/407 ×4 green; first run 406/−1 — one unidentified flake (compact reporter overwrote the failure detail); not attributable to this CR, recorded as suite-hygiene nit |

## M1 closure evidence

All 15 round-1 missing keys present in both ARBs, English placeholders per the
DEF207 precedent (`{ticker}` placeholders intact). Gate proven live in both
directions (r1: caught the missing 15; r2 mutation: catches a single removed
key). The fix — not test drift — turns it green.

## M2 closure evidence

Migration imports `JsonB` from `app.db.base` and uses it for
`notifications.deep_link`, matching `NotificationRow.deep_link` and every
sibling JSON-column migration. Claim (e) now true.

## Folded-in nit fix (verified)

`_alert_mandate_check` docstring no longer claims locale runs; corrected
sentence matches the code. 3-line diff, no behavior change.

## Outstanding (not graded)

- `use_build_context_synchronously` info at `push_notification_listener.dart:59`
- bare `catch (_) {}` in `_pushLogin`/`_pushLogout`
- no multi-ticker price-error isolation test (code-read correct)
- one unidentified flutter-suite flake in 5 runs at this SHA
- DoD table absent — waived per gap-fill 7
- Real OneSignal measurement pending `/promote-to-alpha`; device walk
  (soft-ask, ALERT sheet, push deep-link tap) NEEDS-DEVICE-CHECK
