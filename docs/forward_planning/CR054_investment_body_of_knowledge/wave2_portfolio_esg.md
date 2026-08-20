# CR054 Wave 2 — the remainder: Portfolio theory (M18–M19) + ESG (M26)

**Filed:** 2026-08-20 · **Session:** AT:R73 · **Parent:** CR054 (umbrella, `in_progress`)

## Why this doc exists

CR054 §5 scoped **Wave 2 = "the moat + mandate strands": M24 (Discerning-CEO) · M25 (Islamic
finance) · M26 (ESG) · Level 11 portfolio theory (M18–M19)**, ~35 lessons. Two of the four shipped
as spun-out CRs and closed; two were never picked up and no CR covered them:

| Wave-2 module | Status before this doc | Evidence |
|---|---|---|
| M24 Discerning-CEO | **shipped** — `decision_evaluation`, EVAL 1–8, lessons 357–364 | CR062, `done` |
| M25 Islamic finance | **shipped** — `islamic_finance`, SHARIA 1–10, lessons 347–356 | CR058, `done` |
| M18 Diversification & allocation | **absent** — module 18 has 0 lessons corpus-wide | measured 2026-08-20 |
| M19 Modern theory & factors | **absent** — module 19 has 0 lessons corpus-wide | measured 2026-08-20 |
| M26 Sustainable / ESG | **absent** — module 26 has 0 lessons corpus-wide | measured 2026-08-20 |

Measured on the corpus, not inferred: `grep -h '^module:' content/lessons/*.en.mdx | sort | uniq -c`
returns modules 1–17 and 20–25. **18, 19 and 26 are the only gaps in the CR054 module map**, and
they are exactly the unshipped half of Wave 2. `risk_portfolio` holds 16 lessons, none of which
teaches correlation-based diversification, the frontier, CAPM/beta, factors, risk budgeting or
hedging; `ethics_integrity` holds ETHIC 1–10 (M22+M23) and nothing on ESG.

This doc closes the wave.

## Allocation (reserved — disjoint from every other lane)

**M18 + M19 — Level 11, Building a Portfolio.** Track `risk_portfolio`, prefix `RISK`, continuing
from the last live code `RISK 16` (`291_the_pm_and_your_mandate`).

| id | code | Module | Title |
|---|---|---|---|
| 371 | RISK 17 | M18 | Diversification is about correlation, not count |
| 372 | RISK 18 | M18 | The floor diversification cannot go below |
| 373 | RISK 19 | M18 | Strategic allocation vs tactical drift |
| 374 | RISK 20 | M18 | Rebalancing: the rule that makes you sell winners |
| 375 | RISK 21 | M18 | Home-country bias |
| 376 | RISK 22 | M18 | **Capstone: build an allocation and stress it** |
| 377 | RISK 23 | M19 | The efficient frontier, in plain arithmetic |
| 378 | RISK 24 | M19 | Beta and CAPM — what beta is, and what it is not |
| 379 | RISK 25 | M19 | Factors: value, size, momentum, quality, low-vol |
| 380 | RISK 26 | M19 | Risk parity and risk budgeting |
| 381 | RISK 27 | M19 | Hedging a book, and what a hedge actually costs |
| 382 | RISK 28 | M19 | Reading a factor claim someone hands you |
| 383 | RISK 29 | M19 | **Capstone: judge a portfolio on its risk, not its returns** |

**M26 — ESG.** Track `ethics_integrity` per **CR059** (which folded ESG into ETHIC rather than
minting a `mandate_compliance` track), prefix `ETHIC`, continuing from `ETHIC 10`. Level 13,
module 26 — the same specialty-strand shape M25 used (level 13 / module 25).

| id | code | Module | Title |
|---|---|---|---|
| 384 | ETHIC 11 | M26 | What an ESG score is, and what it is not |
| 385 | ETHIC 12 | M26 | Greenwashing: how to test the claim |
| 386 | ETHIC 13 | M26 | Exclusion, integration, stewardship — three different things |
| 387 | ETHIC 14 | M26 | **Capstone: read AMI's ESG-lite flag honestly** |

17 lessons. Wave-2 total with M24+M25 already shipped: **35** — the §5 estimate exactly.

**Supersedes the authoring prompt's stale row.** `lesson_authoring_prompt.md` v2 still maps
M25/M26 to `fundamentals_analysis` (written before CR059 locked the 13-facet taxonomy) and its
`track` enum lists 11 values, not 13. Corrected in the same commit — M25's shipped lessons already
live in `islamic_finance`, so the table was describing a corpus that does not exist.

## Numbers

Every portfolio figure in these lessons is computed against `backend/app/trading_math/
portfolio_stats.py` (CR046 M11 — the module's own docstring says it was opened for "CR054 Wave 1
… BOK Level 11 / M18–M19"), never authored by hand. The recompute script is
`scripts/verify_cr054_wave2_numbers.py`; it prints every shipped figure and is the artifact a
reviewer re-runs.

Per the CR060 worked-example rule every instrument is **openly hypothetical** — no real ticker
carries a price anywhere in this wave. The only real-world figures are sourced empirical claims
(below), each verified against its primary source this session.

## Sources admitted to the registry for this wave

Verified 2026-08-20 against the publishers' own pages, not from memory:

- Markowitz — *Portfolio Selection*, **J. Finance 7(1), March 1952, 77–91**
- Sharpe — *Capital Asset Prices*, **J. Finance 19(3), Sept 1964, 425–442**
- Fama & French — *The Cross-Section of Expected Stock Returns*, **J. Finance 47(2), 1992, 427–465**
- Fama & French — *Common Risk Factors in the Returns on Stocks and Bonds*, **JFE 33(1), 1993, 3–56**
- Jegadeesh & Titman — *Returns to Buying Winners and Selling Losers*, **J. Finance 48(1), 1993, 65–91**
- Statman — *How Many Stocks Make a Diversified Portfolio?*, **JFQA 22(3), 1987, 353–363** (already
  cited by lesson 365; never admitted to the registry)
- Evans & Archer — *Diversification and the Reduction of Dispersion*, **J. Finance, 1968** (same)
- French & Poterba — *Investor Diversification and International Equity Markets*, **AER 81(2),
  May 1991, 222–226**
- Berg, Kölbel & Rigobon — *Aggregate Confusion: The Divergence of ESG Ratings*, **Review of
  Finance 26(6), Nov 2022, 1315–1344**
- EU — **Regulation (EU) 2019/2088 (SFDR)**, Articles 8 / 9
- SEC — **Rule 35d-1 "Names Rule"**, Sept-2023 amendments (80% policy extended to ESG-suggestive names)

**Deliberately not claimed:** the widely-repeated "average ESG-rating correlation 0.54" and the
"credit ratings correlate ~0.99" comparison. The *Aggregate Confusion* abstract states the range
**0.38–0.71** and makes no credit-rating comparison, so the lessons ship the range and stop there.
This is the CR062 Tetlock-scale lesson applied before authoring rather than after.

## Guards (same commit — house rule)

- `LESSON_COUNT_FLOOR` 342 → 365 in `backend/tests/unit/test_lesson_corpus_integrity.py`.
  (Floor, not a pin — `test_cr054_guard_capstone_floor_pin.py` asserts it stays a `>=`.)
- The three new capstones (376, 383, 387) are picked up by the existing CR054-GUARD invariants:
  last-in-module + `capstone` and `synthesis` tags. `risk_portfolio` gains modules 18 and 19, so
  the last-in-module check now bites on a track that previously had one module.
- CR044 contiguity: `RISK` 1..29 and `ETHIC` 1..14 with no gaps — asserted by the existing
  `test_lesson_codes_are_contiguous_within_each_track`.
- No `agent_gateways.py` edit (DEF068 — gateways stay curated at 5).

## Mirrors (CR054 §4.7 — a gap that lands only in lessons leaves the Concierge blind)

- **Glossary** — new `portfolio_theory` category + ESG terms under a new `esg` category.
- **AI coach** — `content/ai_coach/portfolio_theory.json`, the questions users actually ask
  ("how many stocks is enough", "what does beta mean", "is my ESG fund actually green").
- **Daily challenges** — new scenarios on the M18/M19/M26 material.

## Out of scope, deliberately

- **No mobile work.** `risk_portfolio` and `ethics_integrity` are both already wired (enum, display
  name, prefix, hex facet, short label) — this wave adds lessons to live tracks, not tracks.
- **No AR/MS.** EN only, `locale_versions: ["en"]`, flagged for re-translation per the standing
  content rule. The i18n lane translates; this lane flags.
- **No CR053 UI work.** Lessons are authored born-linkable (`<Lesson id=…/>` tags), which is the
  content half CR054 §4.4 asked for; the quick-link UI is CR053's.
