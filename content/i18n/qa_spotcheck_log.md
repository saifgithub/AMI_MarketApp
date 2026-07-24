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
