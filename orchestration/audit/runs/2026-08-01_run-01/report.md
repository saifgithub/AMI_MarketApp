# Audit run report — CR027 round 1

- **Item:** CR027 (push + in-app notification capability; price alerts first consumer)
- **Submitted SHA:** `d92b017d` (on `main`; confirmed on `origin/main`)
- **Scope:** `cr` (stated). 12 commits, 47 files, +2899/−10 over `961ac328`.
- **Worktree:** `.claude/worktrees/audit-CR027`, detached at the SHA. Kept for round 2.
- **Date:** 2026-08-01 (Asia/Riyadh)
- **Verdict:** AWAITING_FIXES (round 1) — 0 BLOCKER, 2 MAJOR

## What I ran (all from the worktree)

| Check | Command | Result |
|---|---|---|
| Full backend suite | `backend/.venv/bin/python -m pytest tests/unit/ -q` from `backend/` | **1940 passed, 13 warnings, 280.58s** — architect's 1940 reproduced exactly |
| Targeted batch | 5 new test files + test_audit + test_no_blocking_io + test_config_compose_parity | 74 passed |
| Migration head | `python -m alembic heads` | single head `8a4ce4f8abc3` |
| Registers | `python3 scripts/registers/gen_registers.py verify all` | OK — DEF 208 / CR 131 |
| Blind mutation | `_threshold_breached` `<`→`<=` | exactly 1 RED (boundary param), restored, 19/19 re-green, tree clean |
| Lane collisions | `git diff main...origin/lane/* -- models.py safety_floor.py alembic/` | empty for all remote lanes |
| Mobile analyze | `flutter analyze --no-fatal-infos` | exit 0; 6 infos (baseline 5 + 1 new in the CR's own listener file) |
| Mobile tests | `flutter test -r compact` (failures re-run `-r expanded`) | **405 passed, 2 FAILED** |

## The two failures (MAJOR M1)

`test/l10n_key_parity_test.dart`, both locales:

```
app_ar.arb has no keys missing against app_en.arb [E]
app_ms.arb has no keys missing against app_en.arb [E]
Actual: [priceAlertRowCancelTooltip, priceAlertSheetCreate,
  priceAlertSheetPriceLabel, priceAlertSheetThresholdLabel,
  priceAlertSheetTitle, priceAlertTypeManualAbove, priceAlertTypeManualBelow,
  priceAlertTypeStop, priceAlertTypeTarget, priceAlertsSectionHeading,
  pushSoftAskAccept, pushSoftAskBody, pushSoftAskDecline, pushSoftAskTitle,
  tickerDetailActionSetAlert]
```

All 15 missing keys are CR027's own additions to `app_en.arb`. The DEF137
parity gate went RED on the CR's own strings; `flutter test` is not among the
submission's listed frontend evidence.

## MAJOR M2 (no test failure — claim/schema drift)

Migration `8a4ce4f8abc3:34` uses `sa.JSON()` for `notifications.deep_link`;
the model uses `JsonB()` from `app.db.base`. Every sibling migration with JSON
columns uses `JsonB()`. Submission claim (e) asserted both tables use the
portable TypeDecorators — false for this column. Runtime-compatible today;
permanent json-vs-jsonb drift on Postgres once promoted. Fix is free now.

## File-by-file read coverage

Backend: `notification_service.py`, `price_alert_evaluator.py`,
`price_alert_store.py`, `api/price_alerts.py`, `scripts/send_notification.py`,
migration, and diffs of `models.py`, `main.py`, `audit.py`, `conftest.py`,
compose-parity + no-blocking-io pins, `docker-compose.yml` — read in full,
plus `safety_floor.py::check_mandate_compliance` read side-by-side against the
evaluator's framing (every non-eligibility branch confirmed inert under
side=SELL + zero context).

Mobile: `auth_providers.dart`, `main.dart`, `app.dart`, `deep_link_dispatcher.
dart`, `onesignal_notification_service.dart`, `onesignal_config.dart`,
`notification_service.dart`, `notification_models.dart`, `app_navigator_key.
dart`, `push_notification_listener.dart`, `price_alert_sheet.dart`,
`price_alert_providers.dart`, `notification_providers.dart`,
`ticker_detail_screen.dart`, `api_client.dart`, `models/price_alert.dart`,
`pubspec.yaml`, `Info.plist`, `Runner.entitlements`, `AndroidManifest.xml`.

All adversarial-focus items (a)–(i) verified as claimed except where the two
MAJORs land. Nits and NEEDS-DEVICE-CHECK items are in
`orchestration/audit/cr/CR027.auditor.md`.
