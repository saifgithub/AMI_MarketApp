<!--
DEF084-MOBILE.architect.md — builder (coder.mobile) hand-off lane. State derives from round
numbers here vs DEF084-MOBILE.auditor.md (see PROTOCOL.md). Built by coder.mobile.
-->

# DEF084-MOBILE — audit lane (builder: coder.mobile)

**Item:** DEF084 — the Settings compliance toggle labelled `settingsComplianceHalal` ("Halal
screen") and its explanation sheet told the user a real Sharia screen runs. It enforces
membership in a fixed 7-ticker allowlist (see DEF084-BE, merged `bd5c74d`). Fourth occurrence
of the CLAUDE.md "degrade loudly" class. Register: [`docs/defect/def_list.md`](../../../docs/defect/def_list.md)
DEF084. Spec: [`DEF084_halal_flag_is_an_allowlist_not_a_screen.md`](../../../docs/defect/DEF084_halal_flag_is_an_allowlist_not_a_screen/DEF084_halal_flag_is_an_allowlist_not_a_screen.md).

**Product decision (Saiful, 2026-07-22): Option 2 only** — tell the truth about the allowlist,
mirroring DEF084-BE's wording ("curated demonstration universe", "not a Sharia screen"). This
lane = mobile UI copy only (DEF084-BE / DEF084-CONTENT / DEF084-ROOM are separate lanes).

**depends-on:** DEF084-BE (merged to main, `bd5c74d`) — read for exact wording, mirrored below,
not reinvented. **HOT-FILES touched:** `mobile/lib/l10n/app_en.arb`, `app_ar.arb`, `app_ms.arb`
(coder.mobile-internal soft-shared leaf, append-only convention followed) +
`mobile/lib/screens/settings/settings_screen.dart` (owned, not a HOT-FILE).

**Head SHA:** `e344b27`.

## What was done

1. **`app_en.arb`** — `settingsComplianceHalal`: `"Halal screen"` → `"Curated demonstration
   universe"`. New key `settingsComplianceHalalSubtitle`: `"A fixed 7-ticker list, not a Sharia
   screen"`, shown under the toggle label without needing to tap through. Both keys carry `@`
   metadata documenting the DEF084 rationale and marking them observance-sensitive.
2. **`app_ar.arb` / `app_ms.arb`** — added `settingsComplianceHalalSubtitle` (existing pre-fix
   labels for `settingsComplianceHalal` kept as-is: "فلتر الحلال" / "Saringan Halal"). Both keys
   carry a new `@` translator-note block (first use of `@` metadata in these two files — no prior
   convention existed to follow) explaining the EN source changed, that the AR/MS values are
   unreviewed placeholders, and instructing a human translator/SME to supply the corrected wording
   rather than have this pipeline invent religious terminology. Matches the assign lane's explicit
   instruction not to translate this string ourselves.
3. **`settings_screen.dart`** — `_row()` gained an optional `subtitle` param, rendered as a second
   line under the label (`AmiTypography.caption`, `AmiColors.textLow`); wired only for the `halal`
   row via `l.settingsComplianceHalalSubtitle`. The `_complianceExplanations['halal']` sheet
   (title + body, tapped via the info icon) was rewritten: it previously claimed the flag "filters
   out tickers that fail standard Shariah screens" and "flags companies whose debt-to-equity ratio
   crosses common AAOIFI thresholds" — this was the same false-computation claim DEF084 flags,
   just living in the modal instead of the label. New body names the actual 7 tickers, calls it a
   curated demonstration universe, states no ratio is computed, and notes real screens vary by
   standard (matching lesson `350`'s own point, without touching `screens/lessons/**`).

## Why the explanation-sheet body was in scope

The assign lane's ACCEPTANCE (Option 2, `DEF084_...md`) says relabel "everywhere — UI, mandate
copy, and lesson `355`". The bottom-sheet body is UI copy for this exact flag and asserted the
false claim in more detail (named AAOIFI thresholds) than the label ever did — leaving it would
have shipped a truthful label over a false explanation, one tap away. `mobile/lib/screens/lessons/**`
was not touched, per the lane's explicit exclusion.

## Definition of Done

| Row | Disposition |
|---|---|
| **Scope** | Mobile UI copy only: toggle label, new subtitle, explanation-sheet body, 3 ARB locales. No screen redesign, no `screens/lessons/**`, no version bump. |
| **Wording mirrors DEF084-BE** | "curated demonstration universe" / "not a Sharia screen" used verbatim, matching `bd5c74d`. |
| **AR/MS discipline** | No invented religious terminology; translator note added as `@` metadata per the lane's explicit instruction. |
| **DEF069 guard** | No literal `''` introduced — `uv run pytest backend/tests/unit/test_arb_apostrophe_escaping.py -q` → 3 passed. |
| **AMI by name** | No "the AI" language introduced. |
| **Localisations regenerated** | `flutter gen-l10n` run after ARB edits; generated `app_localizations*.dart` committed. |
| **Self-test** | `flutter analyze lib/` → 4 pre-existing infos (main.dart, floor_screen.dart), none in touched files. `flutter test` → 48/48 passed. |
| **Commit tag** | `e344b27` — `fix(mobile): DEF084 Option 2 … (AT:coder.mobile DEF084)`. |

## Tests run (self-test)

- `flutter analyze lib/` — 4 issues, all pre-existing (`main.dart:69` x2 deprecated_member_use,
  `floor_screen.dart:73,313` use_build_context_synchronously), none in files this lane touched.
- `flutter test` (full suite, 48 tests) — all passed.
- `uv run pytest backend/tests/unit/test_arb_apostrophe_escaping.py -q` — 3 passed (DEF069 guard,
  run across all three touched ARBs).

SUBMITTED: round 1
