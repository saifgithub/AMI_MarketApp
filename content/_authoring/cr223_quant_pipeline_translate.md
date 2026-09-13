# CR223 — QUANT 13–15 signal pipeline — new content awaiting AR/MS translation (→ i18n / language manager)

Filed 2026-09-13. **This lane flags; the i18n lane translates.** All three lessons below are
brand-new EN with no `.ar`/`.ms` sibling at all — the same case as `cr054_wave2_translate.md`, and a
different case from the DEF105 staleness class (EN bodies edited *after* their siblings were
translated). Nothing here is stale; it simply does not exist yet in AR or MS.
See [[feedback_content_change_flags_translation]].

**Safe to translate now: YES for all of it.** The EN is final. Every figure was recomputed from the
series printed in the lessons themselves, and the two external citations were verified against the
publishers' records at authoring time. No pending decision would move this content.

## Lessons — 3 files, `locale_versions: ["en"]`

| ids | track / code | module | topic |
|---|---|---|---|
| 400 | `quant_methods` · QUANT 13 | M27 | standardising a signal: time-series demeaning, spread, z-scoring, cross-sectional demeaning |
| 401 | `quant_methods` · QUANT 14 | M27 | combining signals: orthogonalisation against factors, inverse-volatility weighting, Σ\|w\| = 1 |
| 402 | `quant_methods` · QUANT 15 | M27 | capstone — why a correctly built pipeline still underdelivers |

**Translator notes specific to this batch:**

- **Every number in these lessons is reproducible arithmetic, not a quoted statistic.** The reader
  is meant to recompute them by hand. The series (2, 6, 2, 6 / 0, 10, 0, 10 / 7, 9, 7, 9), the
  standard deviations (2, 5, 1), the z-scores (4, 1, 1), the cross-sectional mean (2) and the
  demeaned values (+2, −1, −1) form one chain — changing any one of them breaks it. Localise the
  decimal separator, never the value.
- **The weights in 401 are exact.** +50%, −25%, +25%, from 0.6 ÷ 1, −0.6 ÷ 2 and 0.6 ÷ 2 normalised
  by 1.2. R² = 0.64 from a correlation of 0.8, leaving 36%. These must not be re-rounded.
- **Lesson 402's AUC figures are AMI's own measured result** and are load-bearing: **0.5528**,
  **0.5055**, **p = 0.62**, on 32 large-cap US equities over 2,891 trading dates. The body
  deliberately frames these as our finding on that universe and window, with an explicit statement
  that a different universe or horizon can give a different answer. **That hedge must survive
  translation intact** — without it the lesson reads as a general claim about markets, which it is
  not, and which we cannot support.
- **Percent vs percentage point.** Lesson 402's uncertainty table quotes 40.0 pp, 1.78 pp, 20.0 pp,
  0.89 pp, 8.9 pp and 0.40 pp — all percentage *points*. Languages sharing one word for both need a
  construction that preserves the distinction.
- **Keep proper nouns verbatim:** Fama, French, Bodie, Kane, Marcus; R², AUC, CAPM. Journal names
  stay in English. "AMI" is the name of the product and is never rendered as "the AI" or "the
  model" in any locale.
- **Lesson 402 is a capstone**: its `capstone` and `synthesis` tags are structural (a corpus guard
  reads them), and its quiz answer order must not be changed — grading follows the served locale's
  `answer_index` (CR087), so a reordered option set mis-grades AR/MS users.
- **Section counts are locale-locked.** Lesson 400 has 6 `## ` sections, 401 has 7 (it carries a
  steelman), 402 has 6. The AR/MS siblings must carry the same counts — interactive mode anchors to
  section indices, not heading text.
- **Nothing here may read as advice.** All three lessons describe a method and its limits; the
  worked names (Alpha, Beta, Gamma) are openly hypothetical and must stay that way. No real ticker
  appears anywhere in this batch, deliberately.
