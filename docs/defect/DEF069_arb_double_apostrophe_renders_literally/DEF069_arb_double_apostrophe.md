# DEF069 — Doubled apostrophes in the EN ARB render literally as `''`

**Source:** prompt (Saiful, on-device acceptance test of the CR047 Winzip card — screenshot).
**Area:** l10n / copy. **Round:** AT:R63. **Status:** fixed.

## Symptom

On the live Winzip countdown card (`+39` on device) the body read:

> You**''**ve used this Room. AMI**''**s topping you up — your next Room unlocks in 04:36.

Two visible apostrophes everywhere a contraction/possessive should have one.
Saiful: *"Bad use of punctuation. It's only a single apostrophe."*

## Root cause

Flutter gen-l10n's `use-escaping` option is **off** (unset in
[`mobile/l10n.yaml`](../../../mobile/l10n.yaml) → defaults to `false`). With
escaping off, the ICU quote character is **not** processed: a literal `''` in an
ARB value is emitted verbatim into the generated Dart string and renders as two
apostrophes. The correct authoring is a **single** `'`.

CR047 authored `roomWinzipBody` / `roomPaywallBody` with `''`, on the mistaken
assumption that ARB apostrophes must be ICU-escaped. They don't — not under this
project's config. The generated Dart proved it:

```
lib/generated/l10n/app_localizations_en.dart:1069
  return 'You\'\'ve used this Room. AMI\'\'s topping you up …';   // → You''ve
```

## Scope — not just CR047

A sweep of `app_en.arb` found **9 doubled-apostrophe occurrences across 8 keys**,
6 of them pre-dating CR047 and silently shipping wrong copy:

| Key | Rendered (before) |
|---|---|
| `roomWinzipBody` (CR047) | You''ve … AMI''s |
| `roomPaywallBody` (CR047) | You''ve used your Room credits |
| `onboardingErrorTitle` | CAN''T REACH THE BACKEND |
| `portfolioStartSimTradingBody` | Your PM''s safety floor |
| `journalNoteHint` | What you''d do differently |
| `lessonReaderQuizOnlyBannerOne` | that''s your teaching surface |
| `mergeSheetMandate` | we''ll drop the older one |
| `roomTradeTicketCaption` | the verdict''s size / stop / target |

`app_ar.arb` / `app_ms.arb` had **0** occurrences (not yet translated).

## Fix

- `app_en.arb`: global `''` → `'` (all 9 occurrences). Regenerated l10n; generated
  Dart now emits `You\'ve` / `AMI\'s` / `PM\'s` → renders single apostrophes.
- Ships to device as build `0.1.0+40` (APK + TestFlight). Backend unaffected — no
  promote needed.

## Guard (recurring class ⇒ guard, per CLAUDE.md)

- `backend/tests/unit/test_arb_apostrophe_escaping.py` — fails if any `''` appears
  in `mobile/lib/l10n/app_*.arb`. Runs in the `pytest` promote-preflight gate
  (the one automated gate; `flutter analyze` does **not** catch this). Skips
  gracefully if the ARB isn't present (e.g. a mobile-excluded checkout).
- `docs/initial_specs/08_tech/failure_patterns.md` — new entry: apostrophes in ARB
  are single, never `''`, while `use-escaping` is off.
