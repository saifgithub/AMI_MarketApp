<!-- coder lane — coder.mobile-owned. DEF084-MOBILE. -->
# DEF084-MOBILE — coder.mobile

STATUS: READY_FOR_AUDIT (round 1)

SHA: <pending — see commit below>
AUDIT-LANE: orchestration/audit/cr/DEF084-MOBILE.architect.md (SUBMITTED: round 1)
SELF-TEST: `flutter analyze lib/` → 4 pre-existing infos, none in touched files.
`flutter test` → All tests passed! (48). `uv run pytest
backend/tests/unit/test_arb_apostrophe_escaping.py -q` → 3 passed (DEF069 guard).

ACCEPTANCE: docs/defect/DEF084_halal_flag_is_an_allowlist_not_a_screen/ — Option 2 (Saiful
decided 2026-07-22). Mirrors DEF084-BE (bd5c74d) wording: "curated demonstration universe",
explicitly "not a Sharia screen".

DEPENDS-ON: DEF084-BE (MERGED — bd5c74d)
HOT-FILES: mobile/lib/l10n/app_en.arb, app_ar.arb, app_ms.arb (coder.mobile-internal, no
cross-agent collision)
