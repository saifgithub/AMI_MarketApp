# BOK source registry — the reputable-source allowlist (CR060)

**Owner:** Claude (BOK content-quality lane). **Purpose:** the authoritative allowlist that every
lesson/question/glossary/challenge `sources` entry must resolve to. AI-generated text is **never**
a source of fact.

**The enforcing test is `backend/tests/unit/test_cr054_canon_sourcing_spine.py` (CR054 §4.3, added
2026-08-27).** This paragraph previously asserted that "the corpus-integrity test (CR060) checks
each cited source against this file; a `sources` value that doesn't map to a Tier below fails the
build (degrade loudly)" — and **no such test existed**. Nothing under `backend/` or `scripts/`
referenced this file at all: not a test, not a script, not app code. A registry that describes its
own enforcement in the present tense, with nothing behind it, is P21 written in prose instead of
code, and it is more dangerous than an unguarded file because it stops anyone looking.

What the test actually does, so this stays honest: resolution is by **surname set**, so
`Blaise Pascal & Pierre de Fermat` resolves to `Pascal & Fermat` — which also means a new source
sharing a surname with an admitted one would pass. **29 cited authorities do not resolve today**
and are frozen in `cr054_unadmitted_sources_baseline.json` as a ratchet: a NEW unadmitted source
fails the build, the baseline may only shrink, and an entry that stops being cited must leave it.
The 29 are the "not yet admitted to the allowlist" set this file already describes below, now
enumerated with the lessons that owe each debt. Nine further lessons carry `sources: []` — the key
present, the list empty — and are ceilinged so that count cannot grow.

**Internal-only (Saiful, AT:R63):** provenance is owner-facing QA — users never see sources in the
app. This registry and the `sources`/`verified` fields exist so *we* are certain the content is
correct, not to display citations. No user-facing UI consumes them.

This is a living file — add sources as content earns them, keeping the tiering honest. A source's
presence here means "reputable enough to cite," **not** "this lesson has been verified" — that is a
separate `verified:{by,date}` stamp (CR060 §2).

---

## Tier 1 — Primary / official (highest authority)

Filings, exchanges, regulators, central banks, official statistics. Cite the specific
release/rule/report, not the institution alone.

| Source | Typical use |
|---|---|
| U.S. SEC (e.g. Rule 10b-5, Securities Exchange Act 1934) | market integrity, insider trading, disclosure |
| Securities Commission Malaysia (SC) · Bursa Malaysia | MY market rules, Shariah SAC list |
| Tadawul · Saudi CMA | GCC market structure |
| Company filings — 10-K / 10-Q / 8-K / annual report | fundamentals, statements, ratios |
| US Bureau of Economic Analysis — NIPA | GDP, macro |
| US Bureau of Labor Statistics — CPI, Employment Situation | inflation, labor |
| National Bureau of Economic Research — Business Cycle Dating | recession/cycle dating |
| Federal Reserve — Federal Reserve Act, FOMC materials, H.4.1, FRED | monetary policy, rates, balance sheet |
| US Congressional Budget Office — Budget & Economic Outlook | fiscal policy, deficits |
| US Department of the Treasury — Fiscal Data | debt, issuance |
| Bank Negara Malaysia — OPR decisions | MY policy, FX |
| Saudi Central Bank (SAMA) — USD peg | GCC FX |
| Freddie Mac — Primary Mortgage Market Survey | rate transmission to mortgages |
| IMF · World Bank | cross-country macro |
| U.S. SEC — Rule 35d-1 (the fund "Names Rule"), Sept-2023 amendments | fund naming, the 80% investment policy, ESG-suggestive names |
| EU — Regulation (EU) 2019/2088 (SFDR), Articles 8 / 9 | sustainability-related product disclosure |

## Tier 2 — Standard-setters & professional bodies

| Source | Typical use |
|---|---|
| CFA Institute — Code of Ethics & Standards of Professional Conduct | ethics, fiduciary, suitability |
| CMT Association | technical-analysis standards |
| GARP — FRM body of knowledge | risk, VaR |
| AAOIFI — Shariah Standards | Islamic finance (CR058) |
| CBOE | option structures, retail-options research |
| CME Group | futures specs, settlement |
| Index rulebooks — S&P, MSCI, FTSE, Dow Jones Islamic | indices, Shariah screening |
| Institute for Supply Management — PMI | macro indicators |
| The Conference Board — Leading Economic Index | macro indicators |

## Tier 3 — Canonical texts (the CR054 canon)

| Source | Typical use |
|---|---|
| Graham — *The Intelligent Investor* · Graham & Dodd — *Security Analysis* | value, margin of safety |
| Damodaran — valuation works | DCF, multiples, cost of capital |
| Bodie, Kane & Marcus — *Investments* | portfolio theory, CAPM |
| Hull — *Options, Futures & Other Derivatives* | derivatives |
| Bogle — *Common Sense on Mutual Funds* (1999) | passive, expense ratios |
| Kahneman & Tversky — behavioral works (e.g. base-rate neglect, 1973) | behavioral finance |
| Taleb — *Fooled by Randomness* / *The Black Swan* | tails, randomness |
| Marks — *The Most Important Thing* | cycles, risk |
| Ellis — *Winning the Loser's Game* | costs, indexing |
| Shiller — *Irrational Exuberance* / *Narrative Economics* | bubbles, sentiment |
| Irving Fisher — *The Theory of Interest* (1930) | the Fisher equation |
| Pascal & Fermat — problem of points (1654) | expected value origin |
| Tetlock & Gardner — *Superforecasting* (2015) | calibration, resolution, Brier scoring — **note: reports Brier on the 0–2 scale (0.5 = chance); the single-event convention is 0–1 (0.25 = chance). Always name which convention a figure uses.** |
| Annie Duke — *Thinking in Bets* (2018) | "resulting" — judging decision quality by outcome quality |
| Gary Klein — "Performing a Project Premortem", *HBR* (Sept 2007) | the pre-mortem / prospective hindsight |
| Mauboussin — *The Success Equation* (2012) | luck vs skill, sample size, reversion to the mean |
| Parasuraman & Riley (1997), "Humans and Automation: Use, Misuse, Disuse, Abuse", *Human Factors* 39(2) | automation bias, cognitive offloading |
| Markowitz — "Portfolio Selection", *Journal of Finance* 7(1) (1952), 77–91 | portfolio variance, covariance, the efficient set |
| Sharpe — "Capital Asset Prices", *Journal of Finance* 19(3) (1964), 425–442 | CAPM, beta, systematic vs specific risk |
| Fama & French — "The Cross-Section of Expected Stock Returns", *Journal of Finance* 47(2) (1992), 427–465 | size and book-to-market in the cross-section |
| Fama & French — "Common Risk Factors in the Returns on Stocks and Bonds", *JFE* 33(1) (1993), 3–56 | the constructed three-factor model |
| Jegadeesh & Titman — "Returns to Buying Winners and Selling Losers", *Journal of Finance* 48(1) (1993), 65–91 | momentum over 3–12 month holding periods |
| Statman — "How Many Stocks Make a Diversified Portfolio?", *JFQA* 22(3) (1987), 353–363 | how many names — **note: the paper's conclusion is at least 30 for a borrowing investor and 40 for a lending one; do not quote a single number** |
| Evans & Archer — "Diversification and the Reduction of Dispersion", *Journal of Finance* (1968) | the earlier ~10-name estimate |
| French & Poterba — "Investor Diversification and International Equity Markets", *AER* 81(2) (1991), 222–226 | home-country bias — **its 98/94/82% domestic shares are late-1980s data and must be dated when cited** |
| Berg, Kölbel & Rigobon — "Aggregate Confusion: The Divergence of ESG Ratings", *Review of Finance* 26(6) (2022), 1315–1344 | ESG rater divergence — **the abstract states a 0.38–0.71 correlation range and a 56/38/6 measurement-scope-weight split; it does NOT state an average of 0.54 and makes NO credit-rating comparison, both of which circulate widely** |

The nine Tier-3 entries and two Tier-1 entries added last were admitted by **CR054 Wave 2**
(M18/M19 portfolio theory + M26 ESG), each verified against the publisher's own record at
authoring time rather than from memory. Two carry caveats for the same reason the Tetlock entry
does: the Statman "30 or 40" conclusion is routinely flattened to a single number, and the
*Aggregate Confusion* result is routinely quoted with an average correlation and a credit-rating
comparison that appear nowhere in the paper. Wave 2's lessons ship the range and stop there.
Evans & Archer, Statman and French & Poterba were already cited in the corpus (lesson 365) without
ever having been admitted here — that gap is closed by the same commit.

The five entries above them were added by **CR062** (EVAL track) — the decision-science canon behind
module M24. The Tetlock caveat is not decoration: the first CR062 verification pass caught a lesson
computing Brier on the 0–1 scale while citing a source that reports on 0–2, which is a
citation-integrity defect even though every number was arithmetically correct.

Several sweep passes also proposed **peer-reviewed primary research** not listed here — Barber &
Odean (2000), Barber/Lee/Liu/Odean (2014), Chague/De-Losso/Giovannetti (2020) on retail trader
performance; Coval & Shumway (2005) on post-loss risk-taking; Sloan (1996) on accruals. They are
reputable and were used as *evidence against* lessons, but are **not yet admitted to the
allowlist** — admitting them is a decision, not a formality, and belongs to the remediation CR.

---

## Verification passes

### 2026-07-22 — sourced batch (lessons 293–345, 30 lessons) · dual-AI-pass + adversarial refute

Full auditable record: **`cr060_verification_report_2026-07-22.md`** (this folder).

- ✅ **10 VERIFIED** and stamped `verified: {by: cr060-ai-dual-pass, date: 2026-07-22, …}`:
  ETHIC 6/8, ASST 19, MACRO 3/7/11/12, QUANT 1/3/8 (lessons 298, 300, 321, 325, 329, 333, 334, 335,
  337, 342).
- ⚠️ **20 FINDINGS** (genuine defects, handed to the education lane — not fixed by this lane):
  ETHIC 1/2, ASST 2/9/10/15/17/18/20, MACRO 1/2/4/5/6/8/9/10, QUANT 2/6/11 (lessons 293, 294, 304,
  311, 312, 317, 319, 320, 322, 323, 324, 326, 327, 328, 330, 331, 332, 336, 340, 345).
  **7 of them poison a graded quiz answer/explanation** (311, 322, 323, 324, 327, 328, 345).
- ⚖️ **1 legal escalation** — `294 ETHIC 2` insider trading: "MNPI, no matter how you learned it"
  contradicts *Chiarella*/*Dirks* (breach-of-duty required). **Needs human/SME sign-off**, not an
  auto-fix. See report §5.

## Quality findings log (Claude, CR060 owner)

Provenance soft-spots — citations that name no checkable source. Now **subsumed** into the
2026-07-22 findings above (each of these lessons also has content findings in the report):

- **QF-001** `304_bond_pricing_and_ytm` (ASST 2) — *"Standard fixed-income present-value pricing…"*
  → cite Hull or a CFA fixed-income reading. *(Lesson also has a market-practice overstatement.)*
- **QF-002** `317_payoff_diagrams_intrinsic_time_value` (ASST 15) — *"Standard option payoff
  decomposition…"* → cite Hull or CBOE. *(Lesson also mislabels the at-the-money case.)*
- **QF-003** `320_implied_vs_realized_volatility` (ASST 18) — *"Volatility risk premium — the
  documented tendency…"* → cite the VRP literature / CBOE. *(Lesson also mis-frames short-vol as a
  "coin flip".)*

Log new findings here as verification passes run; resolved items get struck through with the fixing
commit.
