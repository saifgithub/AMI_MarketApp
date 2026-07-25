<!-- dispatch assign lane — Architect-owned. CR052. QUEUED (no ASSIGNED line yet). -->
# DEF061-MOBILE — assign (queued): the CR040 honesty half of DEF061 for esg_lite + custom_constraints

KIND: code
INSTANCE: coder.mobile
ACCEPTANCE: docs/defect/DEF061_mandate_compliance_toggles_not_enforced/ (+ def_list.md DEF061 row)
DEPENDS-ON: —    <!-- the honest interim is correct NOW regardless of the esg/custom product fork; it can ship independently of DEF061-BE. -->
HOT-FILES: `mobile/lib/screens/settings/settings_screen.dart:365-386` (the 8 compliance-toggle rows + their subtitles).

**What:** DEF061-BE builds real enforcement for `no_fossil_fuels` + `no_tobacco_alcohol_gambling`. The
other two DEF061 toggles — `esg_lite` and `custom_constraints` — are **forked to Saiful** (no clean
sourced-data path; guessing repeats DEF059), so they stay **unenforced**. Settings currently sells all
four as hard per-trade filters (e.g. *"Filters out tickers whose primary revenue comes from…"*). Leaving
`esg_lite`/`custom_constraints` advertised as hard filters while they do nothing is the exact CR040
degrade-loudly / confident-but-false violation DEF061 exists to fix.

**Fix (honest interim, reversible):** for **only** `esg_lite` and `custom_constraints`, stop presenting
them as enforced per-trade filters — relabel to make clear they currently guide the analysts' narration,
not a deterministic block (e.g. subtitle → *"Guides how your analysts weigh this — not yet a hard
per-trade filter"*), or gate them behind a "coming soon" affordance. Do **not** touch the
`no_fossil_fuels`/`no_tobacco_alcohol_gambling`/`halal` rows — DEF061-BE makes those genuinely enforced,
so their existing copy becomes accurate. 3 locales (EN authored; AR/MS via the i18n track).

**Queued:** activate (write the assign round-1 signal line) once Saiful rules on the esg/custom fork —
if he greenlights **building** ESG + custom enforcement, this honesty lane is superseded by that build; if
he **scopes them out**, this relabel is the fix. Either way it is a small, low-risk, content-review-gated
change. (Prose deliberately omits the literal assign token so it is not parsed as a live signal.)
