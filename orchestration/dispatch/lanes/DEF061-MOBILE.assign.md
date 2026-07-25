<!-- dispatch assign lane — Architect-owned. CR052. QUEUED (no ASSIGNED line yet). -->
# DEF061-MOBILE — assign (queued): the CR040 honesty half of DEF061 for esg_lite + custom_constraints

KIND: code
INSTANCE: coder.mobile
ACCEPTANCE: docs/defect/DEF061_mandate_compliance_toggles_not_enforced/ (+ def_list.md DEF061 row)
DEPENDS-ON: —    <!-- the honest interim is correct NOW regardless of the esg/custom product fork; it can ship independently of DEF061-BE. -->
HOT-FILES: `mobile/lib/screens/settings/settings_screen.dart:365-386` (the 8 compliance-toggle rows + their subtitles).

**What (fork resolved 2026-07-25):** DEF061-BE builds enforcement for `no_fossil_fuels` +
`no_tobacco_alcohol_gambling` + **`esg_lite` (curated best-effort proxy)**; `custom_constraints` stays
freeform with the PM explaining what it can't hard-enforce (`DEF061-ROOM`). So Settings copy for the four
now needs to MATCH what actually happens — the CR040 fix is accuracy, not hiding:

**Fix (copy, 3 locales — EN authored, AR/MS via the i18n track):**
- `no_fossil_fuels` / `no_tobacco_alcohol_gambling` — copy stays a hard filter (now true), but note it's
  screened against a curated sector/industry list of the tradable universe (unclassified names pass with
  a disclosure).
- `esg_lite` — relabel to *"Excludes a curated best-effort list (fossil + sin + weapons/defense) — not a
  rated ESG score."* Do NOT imply a rating AMI doesn't have.
- `custom_constraints` — relabel to *"Your analysts weigh these; the PM flags any condition it can't
  hard-enforce."* Not presented as a deterministic block.

**Queued:** activate (write the assign round-1 signal line) once DEF061-BE lands (so the fossil/sin/esg
copy matches shipped behaviour) and DEF061-ROOM's PM-explain wording is settled. Small, low-risk,
content-review-gated. (Prose omits the literal assign token so it is not parsed as a live signal.)
