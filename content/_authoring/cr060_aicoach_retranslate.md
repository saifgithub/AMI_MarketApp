# AI Coach — re-translation needed (DEF115 → i18n lane)

EN entries corrected under DEF115 whose **user-facing meaning changed** and which have AR/MS siblings.
Their translations now teach the old wording — re-translate from the corrected EN. Keyed by `id` (the
translations are keyed the same way). See [[feedback_content_change_flags_translation]].

| id | file | locales stale | why |
|---|---|---|---|
| qa_beg_market_cap | beginner.json | ar, ms | market-cap size buckets rewritten |
| qa_plt_coach_what_is | platform.json | ar, ms | nav label `-> Coach` → `-> Brief Your Agent`; AR/MS still read `-> Coach` |
| qa_plt_coach_reset | platform.json | ar, ms | nav label + "Coach History" wording; AR/MS still read `-> Coach` |
| qa_plt_halal_flag | platform.json | ar, ms | full rewrite to the CR069 sourced four-state screen (was the retired ratio screen) |
| qa_scam_check_asic_australia | scam.json | ar, ms | scam-report channel changed to Scamwatch |

**NOT stale (no re-translation):** the 12 typo fixes (`..`→`.`, meaning unchanged) and
`qa_beg_pick_first_stock` (metadata `related_lessons` only; prose unchanged).

**NOT applicable:** `qa_islamic_which_standard_does_ami_use` — `islamic_finance` is EN-only; when it is
first translated, translate from the corrected EN.

**Guard TODO (CR060 Phase 6):** generalize `locale_staleness_check.py` to the JSON surfaces via a per-`id`
`source_sha` stamp so this flag is produced automatically, not by hand.
