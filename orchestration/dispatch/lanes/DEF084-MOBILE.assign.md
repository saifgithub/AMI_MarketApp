<!-- dispatch assign lane — Architect-owned. CR052. -->
# DEF084-MOBILE — assign

KIND: code
INSTANCE: coder.mobile
ACCEPTANCE: docs/defect/DEF084_halal_flag_is_an_allowlist_not_a_screen/DEF084_halal_flag_is_an_allowlist_not_a_screen.md — Option 2 (Saiful decided 2026-07-22)
DEPENDS-ON: DEF084-BE (backend names the concept first; mirror its wording, do not invent your own)
HOT-FILES: mobile/lib/l10n/app_en.arb (+ app_ar.arb, app_ms.arb) — coder.mobile-internal

**What:** the Settings compliance toggle is labelled **"Halal screen"**
(`app_en.arb:395` `settingsComplianceHalal`; `app_ms.arb:89` "Saringan Halal"; `app_ar.arb:127`
"فلتر الحلال"). It is not a screen — it is a 7-ticker curated demonstration universe (DEF084).
Relabel the toggle and give it a subtitle that says plainly what it does, matching the wording
DEF084-BE lands. AR + MS strings: leave a translator note in the ARB `@` metadata rather than
inventing a religious term — Saiful arranges translation externally, and this string is
observance-sensitive.

**Small lane.** One toggle, one label, one subtitle, three locales. Do not redesign the settings
screen. Do not touch `mobile/lib/screens/lessons/**` (DEF082 just landed there).

**Gotchas that have bitten this repo:**
- **DEF069 — ARB apostrophes.** `use-escaping` is off, so a literal `''` in an ARB value renders as
  two apostrophes on screen. Write a single `'`. `test_arb_apostrophe_escaping.py` will fail you.
- **AMI by name** in anything a user reads — never "the AI".
- Regenerate localisations after editing ARBs; `flutter analyze` clean + `flutter test` green
  before hand-off.
- Do **not** bump the version. The Architect batches the store build.

ASSIGNED: coder.mobile round 1
DISPATCH: OPEN

## Audit gate: WAIVED BY THE ARCHITECT, NOT PASSED — pending Saiful's confirmation

This lane never went through `auditor.core`. Its source was pushed **straight to main**
(`e344b27`) instead of a branch, so the "Architect integrates on COMPLETE" step was bypassed
before I could route it. I reviewed it myself and accepted it: label + subtitle + bottom-sheet
copy, `flutter analyze` clean, 48/48 tests, no behaviour change, no version bump.

That is an Architect review, not an independent verification. Recorded here explicitly so the
distinction is not lost — if Saiful wants the gate applied retroactively, re-open at round 2.

DISPATCH: ACCEPTED (round 1, audit waived)
