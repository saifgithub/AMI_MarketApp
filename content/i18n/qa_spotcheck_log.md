# QA spot-check log

Automated-check results per CR083 translation run. Native-speaker QA is logged here as
a non-blocking follow-up (Saiful confirmed 2026-07-24: automated checks only for M5
closure; native QA before public MVP launch, not before).

## Native QA — non-blocking follow-up

- **Status:** not started. No native-speaker review has been arranged yet.
- **Trigger:** before public MVP launch (not before). See `docs/initial_specs/10_delivery/risks.md`'s
  "Translation quality degrades user trust" risk row for the original mitigation this defers.
- **Scope when it happens:** a sample per locale across all 3 tiers, prioritizing the
  `strict_review` cluster (see `sensitive_keys.json`) and any lesson flagged "NEEDS REVIEW"
  by `scripts/i18n_verify_lesson_translation.py --summary`.

## Run history

<!-- Append one entry per translation run: date, tier, script, locale(s), counts, failures. -->

### 2026-07-24 — Tier 1 (ARB gap-fill)

`scripts/translate_arb_lan.py --locales ar ms`, model `ami-llm`. 103 AR + 104 MS keys
translated (gap from 428-key EN source), 0 failed batches. Post-run check: 0/427
translatable keys missing in either locale. 10 `exclude`-listed Sharia-observance keys
confirmed still holding their literal EN value (pre-seeded, correctly skipped).
`flutter gen-l10n` regenerated clean.

Spot-check (5 random keys, both locales): translations read as natural, brand/ticker/
placeholder rules held. One minor miss: `leagueReputation` → AR echoed the English word
"REPUTATION" instead of translating it (short single-word label). Logged, not blocking —
exactly the class of miss the non-blocking native-QA follow-up above is for.

### 2026-07-24 — Tier 2 (glossary, ai_coach, daily_challenges)

`scripts/translate_content_lan.py --type {glossary,ai_coach,daily_challenges}`, model
`ami-llm`, run sequentially (never parallel). All three: 0 failed batches.

- Glossary: 208/208 terms translated, both locales.
- AI Coach: 280/295 translated, both locales. 15 missing = exactly `content/ai_coach/islamic_finance.json`'s
  entry count — confirms the `exclude` relocation held (file was absent from the glob during
  the run, restored after via `i18n_apply_exclusions.py --stage content --post`).
- Daily Challenges: 193/193 translated, both locales — includes the 10 `2026_12.json`
  `strict_review` entries (Islamic-finance-themed month), auto-translated per Saiful's
  decision, pending the stricter confidence bar before counting as verified.

Spot-check: `qa_plt_halal_flag` (the one `strict_review` entry in `platform.json`) and a
`2026_12.json` sample both read as natural AR/MS with correct AAOIFI/ticker/brand handling.
One AR word choice ("ينتهش" for "violates") reads slightly informal — logged for the
native-QA follow-up, not blocking.

`scripts/i18n_coverage_report.py` run — see `coverage_status.md`. Tier 3 not started yet.
