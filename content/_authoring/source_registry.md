# BOK source registry — the reputable-source allowlist (CR060)

**Owner:** Claude (BOK content-quality lane). **Purpose:** the authoritative allowlist that every
lesson/question/glossary/challenge `sources` entry must resolve to. The corpus-integrity test
(CR060) checks each cited source against this file; a `sources` value that doesn't map to a Tier
below fails the build (degrade loudly). AI-generated text is **never** a source of fact.

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

---

## Quality findings log (Claude, CR060 owner)

Issues I've flagged while seeding this registry. These are **provenance soft-spots** — citations
that describe a concept as "standard" without naming a checkable source. They pass "has a `sources`
field" but fail "resolves to a specific reputable source," and must be upgraded before their lessons
are marked `verified`:

- **QF-001** `304_bond_pricing_and_ytm` — *"Standard fixed-income present-value pricing…"* → replace
  with a Tier-2/3 citation (e.g. Hull, or a CFA fixed-income reading).
- **QF-002** `317_payoff_diagrams_intrinsic_time_value` — *"Standard option payoff decomposition…"*
  → cite Hull or CBOE explicitly.
- **QF-003** `320_implied_vs_realized_volatility` — *"Volatility risk premium — the documented
  tendency…"* → cite the VRP literature or a CBOE/academic source, not a bare assertion.

Log new findings here as verification passes run; resolved items get struck through with the fixing
commit.
