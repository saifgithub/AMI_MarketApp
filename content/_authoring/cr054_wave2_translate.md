# CR054 Wave 2 — new content awaiting AR/MS translation (→ i18n / language manager)

Filed 2026-08-20 (AT:R73, CR054). **This lane flags; the i18n lane translates.** Everything below is
brand-new EN with no `.ar`/`.ms` sibling at all — a different case from
`cr060_lessons_retranslate.md`, which tracks EN bodies edited *after* their siblings were translated
(the DEF105 staleness class). Nothing here is stale; it simply does not exist yet in AR or MS.
See [[feedback_content_change_flags_translation]].

**Safe to translate now: YES for all of it.** The EN is final — every figure is recomputed by
`scripts/verify_cr054_wave2_numbers.py` and every citation was verified against its publisher's
record at authoring time. There is no pending decision that would move this content, unlike the
DEF105/CR101 cohort.

## Lessons — 17 files, `locale_versions: ["en"]`

| ids | track / code | module | topic |
|---|---|---|---|
| 371–376 | `risk_portfolio` · RISK 17–22 | M18 | diversification, the systematic floor, strategic vs tactical allocation, rebalancing bands, home bias, capstone |
| 377–383 | `risk_portfolio` · RISK 23–29 | M19 | efficient frontier, beta/CAPM/R², factors, risk parity, hedging, evaluating a factor claim, capstone |
| 384–387 | `ethics_integrity` · ETHIC 11–14 | M26 | ESG ratings, greenwashing, exclusion/integration/stewardship, capstone on AMI's ESG-lite flag |

**Translator notes specific to this batch:**

- **Numbers are load-bearing and must not be re-rounded.** Volatilities are quoted to 2 dp and
  differences to the same precision (`29.24%`, `0.76 percentage points`, `17.75%`). Several quiz
  keys turn on the exact figure, and a translated `29.2%` breaks the reader's ability to reproduce
  the arithmetic. Localise the decimal separator, never the value.
- **Percent vs percentage point.** The lessons distinguish them deliberately throughout (a fall
  *from* 22.00% *to* 20.43% is 1.57 **percentage points**, not 1.57%). Languages that share one word
  for both need a construction that keeps the distinction.
- **Keep proper nouns verbatim:** Markowitz, Sharpe, Fama, French, Jegadeesh, Titman, Statman,
  Evans, Archer, Poterba, Berg, Kölbel, Rigobon; CAPM, MPT, R², SFDR, and the SEC "Names Rule".
  Journal names stay in English.
- **`0.38 to 0.71` in lessons 384/387 is a verified published range** and must not be smoothed to an
  average — see the caveat in `source_registry.md`. Same for Statman's "at least 30 … and 40",
  which is two numbers, not a range and not one number.
- **Regulatory framing is load-bearing** as everywhere else: nothing may read as advice, and lesson
  387 in particular describes what AMI's ESG-lite flag *does* — a factual description of a control,
  which must not soften into a claim that the portfolio is "ESG-screened".
- Lessons 376, 383 and 387 are **capstones**: their `capstone` and `synthesis` tags are structural
  (a corpus guard reads them), and their quiz answer order must not be changed — grading follows the
  served locale's `answer_index` (CR087), so a reordered option set mis-grades AR/MS users.

## Glossary — 34 new EN terms in `content/glossary/terms.en.json`

Two new categories: **`portfolio_theory`** (24 terms) and **`esg`** (10). `terms.ar.json` /
`terms.ms.json` are unchanged at 208 entries, so AR/MS readers get the prettified id for these
until they land. Ids, `category`, `see_also`, `related_lessons`, `related_agents` and `tags` are
locale-neutral — only `term` and `definition` localise.

**After translating, re-copy `content/glossary/terms.<locale>.json` to
`mobile/assets/glossary/terms.<locale>.json`** — the device reads the bundled asset, not the
corpus, and `test_def325_glossary_asset_parity.py` fails the build when the two disagree. The EN
copy was refreshed in the same commit as this file.

## AI coach — 13 new EN entries

`content/ai_coach/portfolio_theory.json` (8) and `content/ai_coach/esg.json` (5). The locale
directories `content/ai_coach/ar/` and `content/ai_coach/ms/` need matching files with the same
ids; the service already loads EN 308 against AR/MS 280, so this widens an existing gap rather
than creating one.

## Daily challenges — 12 new EN scenarios

`content/daily_challenges/2026_12.json`, days 11–22 (the month previously ran to day 10). The
`ar/` and `ms/` sibling directories need the same 12 ids. Quiz-style content: the `answer` index
must survive translation unchanged.

## Pre-existing backlog this lane did not create

Six lessons were already EN-only before this wave and are not tracked in any manifest:
`365`–`370` (EDGE 99–104, CR129 + CR132). Flagged here for visibility, not scheduled by this lane.
