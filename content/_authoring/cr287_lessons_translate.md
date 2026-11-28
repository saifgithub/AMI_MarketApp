# CR287 — sector-metric lesson (FUND 69) + four cross-links — AR/MS translation flag (→ i18n / language manager)

Filed 2026-11-27 (AT:B1 CR287). **This lane flags; the i18n lane translates.** See
[[feedback_content_change_flags_translation]]. Keyed by lesson `id`.

## 1. New lesson, no `.ar` / `.ms` sibling yet — `locale_versions: ["en"]`

| id | track / code | module | topic |
|---|---|---|---|
| `403_when_a_metric_doesnt_apply_banks_insurers_reits_utilities` | `fundamentals_analysis` · FUND 69 | M7 | when free cash flow, net debt, EV/EBITDA, P/E and payout ratios stop applying to banks, insurers, REITs and utilities |

Translator notes:

- **Section count is locale-locked: 7 `## ` sections** (Example, Three more families…, The trap, The steelman, Quiz, Try it, Takeaway). Keep each EN paragraph as one paragraph.
- **Quiz answer order must not change** (CR087 grading follows the served locale's `answer_index`): answers are 2, 0, 3.
- **Every figure is hypothetical and hand-checkable**: net income 3.6bn, equity 30bn, market value 36bn (ROE 12%, P/B 1.2x); loans +40bn / deposits +34bn gives −2.4bn, loans +10bn / deposits +30bn gives +23.6bn, a 26bn swing; REIT EPS 0.40, depreciation 0.30, distribution 0.55 gives 137.5% of EPS and 78.6% of FFO. Localise separators, never values.
- **Real standards figures stay exact:** 90% (REIT distribution rule, US and Malaysia), CET1 4.5% of risk-weighted assets plus a 2.5% buffer, a combined ratio below 100 meaning an underwriting profit.
- **Keep verbatim:** IFRS, IAS 7, IAS 40, MFRS, US GAAP, Basel, CET1, FFO, EPS, P/B, ROE, EV/EBITDA, REIT, Bursa Malaysia, Damodaran, Buffett, Nareit. "AMI" is the product name and never "the AI".
- **Percent vs percentage terms:** the −8% and +64% yields are shares of market value, not percentage points.
- **Nothing may read as advice.** No real company appears; the training-artifact line in Try it must survive.
- **Do not soften the "same number can be right on the sheet and wrong as evidence" line**; it is the lesson's thesis.

## 2. Existing lessons edited — `ar` + `ms` siblings now stale (retranslate:[ar,ms])

One line appended to the end of each EN file (after the Takeaway), a "See also" pointer to lesson 403. No section added, no figure changed. Translate the new final paragraph only.

| id | change |
|---|---|
| `035_cash_flow_vs_earnings` | final line `See also: <Lesson id="403_…"/> …` |
| `181_pb_for_banks_regulatory_book` | same |
| `188_net_debt_to_ebitda` | same |
| `314_reits_adrs_closed_end_funds` | same |

**Guard note:** `locale_staleness_check.py` mechanism 2 compares anchor multisets, and a new `<Lesson id>` token is one anchor, so it may or may not flag these four. The hand-written manifest is the fallback, as in `def423_lessons_retranslate.md`.

## 3. Translated 2026-11-28 (AT:B1 CR287, branch `cr287-l403-i18n`)

Done, and dual-checked: each translation was authored, then an independent ami-llm translation was produced from the EN source and the same translator notes (without seeing the first), compared section by section, and every meaning/figure/term/quiz-answer/keep-verbatim difference was resolved against EN.

1. Lesson 403 now has `.ar.mdx` and `.ms.mdx`; EN `locale_versions` is `["en", "ar", "ms"]`. Structure matches EN (7 sections, same paragraph counts, same figures, quiz answers 2, 0, 3).
2. The "See also" line is appended to the `.ar.mdx` and `.ms.mdx` of 035, 181, 188 and 314 (8 files). Staleness check does not flag them.
3. Glossary entries added in EN, AR and MS (and the bundled `mobile/assets/glossary/terms.en.json`): `net_interest_margin`, `nonperforming_loan_ratio`, `insurance_float`, `combined_ratio`, `ffo`. Append-only; the DEF144 baseline fingerprints for `terms.ar.json` and `terms.ms.json` were updated in the same commit.
4. Comparison result: 11 real differences, all resolved in favour of the authored translation (1 AR lesson, 7 MS lesson, 3 AR glossary); none in the see-also lines or the MS glossary. Mistranslations to watch for in any future machine pass: MS lending rendered as borrowing ("peminjaman"), accounting as "akauntan", revaluation as "penilai semula", balance sheet as "imbangan kunci"; AR FFO expanded as cash flow from operations.

## 4. Not done here

- AR/MS native-speaker review is still the i18n lane's call; this pass is author plus one independent model, not a human reviewer.
