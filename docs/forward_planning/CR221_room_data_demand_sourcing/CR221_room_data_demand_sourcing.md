# CR221 — Sourcing the Room's measured data demand

**Status:** in_progress · **Owner:** coder.api · **Filed:** 2026-09-03 · **Tag:** `(AT:R75 CR221)`

**Done at filing:** §1–§6 — the item register, the cross-check against CR219, a *verified free*
source for every open item but one, and the §6 measurement. **Ruled 2026-09-03:** R38's route
is CR221's (`ac55352c`) — CR219 ships a declared-absent entry now, this CR builds the real line
later, inheriting `WP10_R38_parked/` as its head start. **Built:** slot 1 (A1 + A3), slot 3
(C3 + C4 + DEF400), the history arm (C2/C5/B2), and slot 4 (A2 + D1 + D2, with A4 closed) —
§5 "Build status". **Measured:** §7 rounds 1–3 (round 3 = the slot-4 `dims` arm, §7.10: A2 answered, D2 unread); two flags live on Alpha since 2026-09-10, the three slot-4 flags OFF.
**Open:** slot 4's ingest on Alpha and its §7 round, the remaining slots, and the one item
(H2) with no free source yet found.

---

## What

CR219 asked twelve agents, on every turn, to name the data they lacked. They answered **127
times**, and those 127 asks are **49 distinct data items**. Nine are already delivered, five
are closed (four at filing; A4 joined them in the slot-4 build, 2026-09-11), **35 are open**.

This CR takes those open items and finds each one a source that is **free and reliable**. It does not
ship fact-sheet fields — every field is a follow-on CR. What was missing was not build
capacity; it was an answer to *"where does that number come from, does that source exist, and
what does it cost us?"* — asked once for all of it instead of one field at a time.

**The headline result: 34 of the 35 open items have a verified free source, and none of them
needs a paid provider.** Most are SEC EDGAR or FRED — one of which we already call, the other
of which turns out to need no API key. One item (Fed-path probabilities) has no free source we
could verify.

## Why

1. **The demand is measured, not guessed.** Seven convenes, twelve agents, an `(a)/(b)/(c)`
   addendum on every turn. It is the closest thing this project has to a Room specification
   written by its consumers, unprompted as to content.

2. **The residue is where the verdicts get decided.** CR219 shipped six fields. The single
   largest ask — the captive-finance debt split, 18 lines from 9 of 12 agents — is designed
   against a source that does not carry it (§6), and the second largest — the maturity ladder,
   14 lines from 6 agents — has no CR219 row at all.

3. **Sourcing one field at a time re-asks the same question.** R33/R34/R35 were each
   discovered, separately, to be derivations of data already in hand. Six more items are the
   same shape. One sweep is cheaper than six discoveries, and it is the only way to see that
   ten technical-indicator items share one decision, or that the News Analyst's five-times-
   repeated question is answered by a filing we already download.

---

## 1. How the demand was measured

CR219 put a `DATA I LACKED:` addendum on every turn asking each agent to name what it lacked,
what it would have changed, and whether the gap was ABSENT / WITHHELD / FORBIDDEN. All seven
convenes are banked complete — system prompt, user message, reasoning trace, answer.

| Source | Convenes | Request lines |
|---|---|---|
| `CR219/evidence/arms/{h_short,h_medium,h_long,h_very_long,g_income_now,g_learning}` | 6 mandate variations, one shared profile | 102 |
| `CR219/evidence/convene_CAT_long_wealth/` | 1 full 12-agent live-profile convene | 25 |
| | | **127** |

**127 is how loud the demand is, not how much data is missing.** One ticker through seven
convenes repeats heavily: the maturity ladder alone is 14 of those lines. Deduplicated at *one
item = one distinct thing an agent asked for*, the corpus is **49 items**.

```bash
V=backend/.venv/bin/python
$V docs/forward_planning/CR221_room_data_demand_sourcing/evidence/inventory.py   # the 127 lines, verbatim, by agent
$V docs/forward_planning/CR221_room_data_demand_sourcing/evidence/items.py       # the 49-item register + its assertions
$V docs/forward_planning/CR221_room_data_demand_sourcing/evidence/edgar_census.py # the §6 measurement
```

`items.py` exits non-zero if any request line claims no item, or if the register's totals drift
from what this document states — the doc and the corpus cannot silently diverge.

**One correction to CR219's own count.** Its `aggregate_arms.py` reports 26 debt asks and 17
`(unbucketed)`. Eight of those seventeen are debt asks its regex misses (*"maturity schedule
for the $45.1B"* has no `debt maturity` bigram) and a ninth is claimed by its peer pattern.
Counted as items, debt is **35 request lines from 9 of 12 agents**, not 26.

---

## 2. The register — 49 distinct data items

Line and agent counts are `items.py`'s, not this document's. A line naming two things claims
both items, so counts do not sum to 127. **✅ delivered · ⛔ closed · ○ open.**

### A · Debt & capital structure

| | Item | Lines | Agents | |
|---|---|---|---|---|
| A1 | Debt maturity ladder, repayments by year | 14 | 6 | ◐ slot 1 `472efbfc` — `room_debt_maturity_enabled`, OFF |
| A2 | Industrial vs. captive-finance debt split | **18** | **9** | ◐ slot 4 `aff954b6` — `room_debt_split_enabled`, OFF; needs the dimensional ingest first (§7.6c) |
| A3 | Average interest rate / cost of debt | 6 | 4 | ◐ slot 1 `472efbfc` — `room_cost_of_debt_enabled`, OFF |
| A4 | Fixed vs. floating rate mix | 4 | 3 | ⛔ not structural — slot 4, §5 |
| A5 | Interest coverage ratio | 2 | 2 | ✅ R33 `ab9decb2` |

### B · Valuation history & comparables

| | Item | Lines | Agents | |
|---|---|---|---|---|
| B1 | Historical *price-based* P/E + EV/EBITDA series (5–10y median, percentile, cycle-trough) | 13 | 6 | ○ |
| B2 | Cycle-median ROE | 1 | 1 | ◐ `room_roe_history_enabled`, OFF; basis corrected in `9da0be32` |
| B3 | Peer-basket valuation multiples | 1 | 1 | ○ |
| B4 | Peer/sector median balance-sheet ratios (D/E, quick ratio) | 2 | 2 | ○ |
| B5 | Own-history multiples vs. past FYs' own fundamentals | — | — | ✅ R37 `d3943aa5` — narrower than B1 |

### C · Cash flow & capital allocation

| | Item | Lines | Agents | |
|---|---|---|---|---|
| C1 | Explicit capex line | 9 | 7 | ✅ R34 `a841ac13` — TTM only; C2/C9 carry the rest |
| C2 | Multi-year capex / FCF averages | 3 | 3 | ◐ `room_fcf_history_enabled`, OFF |
| C3 | Operating cash flow line + OCF→FCF bridge | 9 | 6 | ◐ `room_cashflow_bridge_enabled`, OFF |
| C4 | Working-capital change detail | 2 | 2 | ◐ `room_cashflow_bridge_enabled`, OFF |
| C5 | FCF conversion history (FCF ÷ net income) | 2 | 2 | ◐ `room_fcf_conversion_enabled`, OFF |
| C6 | Buyback pacing over the trailing quarters | 1 | 1 | ✅ R35 `c7c40213` |
| C7 | Buyback average execution price | 1 | 1 | ◐ slot 5, §7.12 — `room_buyback_price_enabled`, OFF; $664.64 for CAT once the new tag is ingested, absent for MSFT (no share tag) |
| C8 | Historical dividend growth CAGR | 2 | 2 | ◐ slot 5, §7.12 — `room_dividend_growth_enabled`, OFF; declared-rate basis |
| C9 | Projected dividend growth / forward payout target | 2 | 2 | ○ |

### D · Segment & geography

| | Item | Lines | Agents | |
|---|---|---|---|---|
| D1 | Revenue by business segment | 6 | 4 | ◐ slot 4 `aff954b6` — `room_segment_revenue_enabled`, OFF; needs the dimensional ingest first |
| D2 | Revenue by geography | 2 | 1 | ◐ slot 4 `aff954b6` — `room_geographic_revenue_enabled`, OFF; needs the dimensional ingest first |

### E · Earnings expectations

| | Item | Lines | Agents | |
|---|---|---|---|---|
| E1 | Consensus estimate revisions | 2 | 1 | ✅ R21-DATA `ecb8f199` |
| E2 | Earnings surprise history | 2 | 1 | ✅ R21-DATA `ecb8f199` |
| E3 | Management guidance | 2 | 1 | ⛔ ruled out by CR219 R22 |
| E4 | Long-term (3–5y) forward EPS growth estimates | 1 | 1 | ○ |

### F · Price series & technicals

| | Item | Lines | Agents | |
|---|---|---|---|---|
| F1 | Raw OHLC bar series / chart patterns | 1 | 1 | ○ |
| F2 | Weekly & monthly timeframe indicators | 2 | 1 | ○ |
| F3 | MACD | 3 | 1 | ○ |
| F4 | Moving-average crossover signals | 2 | 1 | ○ |
| F5 | Stochastic / momentum divergence | 1 | 1 | ○ |
| F6 | Volume-at-price / volume profile / point-of-control | 4 | 2 | ○ |
| F7 | Historical support & resistance levels | 2 | 1 | ○ |
| F8 | Candlestick pattern recognition | 1 | 1 | ○ |
| F9 | RSI history (troughs, multi-year trend, rolling baseline) | 3 | 2 | ○ |
| F10 | ATR(14) | 1 | 1 | ✅ R36 `a4459b01` |
| F11 | Historical gap-down / overnight slippage statistics | 4 | 2 | ○ |

### G · Options & order flow

| | Item | Lines | Agents | |
|---|---|---|---|---|
| G1 | Implied volatility level / expected move | 5 | 5 | ○ |
| G2 | IV skew | 1 | 1 | ○ |
| G3 | Open interest & options volume | 1 | 1 | ○ |
| G4 | Level 2 order-book depth / bid density | 3 | 1 | ⛔ no free source |
| G5 | Dark-pool prints & institutional flow | 1 | 1 | ⛔ no free source |

### H · Macro

| | Item | Lines | Agents | |
|---|---|---|---|---|
| H1 | Macro prints: CPI, PPI, PMI/ISM | 2 | 1 | ○ |
| H2 | Fed path / rate-cut probability | 5 | 3 | ○ **the one unsourced item** |
| H3 | End-market macro: construction spending, housing starts, mining capex | 2 | 1 | ○ |

### I · News depth

| | Item | Lines | Agents | |
|---|---|---|---|---|
| I1 | Executive-change detail (identity, background, circumstance) | 5 | 1 | ◐ slot 2 `d6c364c2` — `room_executive_change_enabled`, OFF; needs the in-container 8-K ingest first (§7.6c) |
| I2 | Catalyst magnitude (the % move a headline caused) | 2 | 1 | ○ |

### J · Social

| | Item | Lines | Agents | |
|---|---|---|---|---|
| J1 | Raw bullish/bearish split, buzz score, mention counts | 4 | 1 | ✅ pre-CR219 |
| J2 | Sentiment history / rolling baseline | 1 | 1 | ⛔ structurally absent — the cache keeps one row, by design |

### K · User context

| | Item | Lines | Agents | |
|---|---|---|---|---|
| K1 | Decision Journal history for this ticker | 1 | 1 | ✅ DEF054/DEF055 — the arm ask is a harness artifact (empty journal) |

**49 items · 9 delivered · 13 dark · 5 closed · 22 open** (4 closed / 36 open at filing; A4 closed in the slot-4 build, 2026-09-11).

**`◐` dark is not a cosmetic fourth state — it is the one this register was missing, and its absence hid the whole build.** A producer merged behind a flag that defaults False is not on the sheet, so it is not delivered; its code exists, so calling it open says something false. Slots 1 through 5 shipped thirteen items and every one of them sat at `○` — including A2, the single largest item at 18 request lines from 9 agents. The register script could not notice, because it compared a hardcoded `EXPECTED` dict against totals derived from the same hardcoded list: a guard validating its own constant. It now reads `backend/app/core/config.py` and fails if a dark item's flag is missing there, if a dark item names no flag, or if an open item names one (§7.13).

The distinction is also what §7 needs to pick its next arm: a flag flip and a sprint of work are different sizes of job, and `○` could not tell them apart.

One further request line is not a data item at
all (*"whether the 1.0h post-loss cooldown blocks all buys portfolio-wide"*) and leaves scope
in §8.

Read the counts as demand *shape*, not just size: A2 is 9 of 12 agents independently hitting
the same wall, while F3–F8 are one agent asking eight ways. The build order in §5 weights both.

---

## 3. Cross-check — what CR219 already delivered

Verified against the regenerated sheet at `CR219/evidence/rendered/sheets/__FULL__.txt`:

| Item | Sheet line today | Closes the ask? |
|---|---|---|
| A5 | `Interest coverage (EBIT / interest expense) (LIVE): 9.4x` | **Yes** |
| C1 | `Capital expenditure (LIVE): $6,543M (trailing 4 quarters)` | **Partly** — 9 lines from 7 agents also wanted the history (C2) and the bridge (C3) |
| C6 | `Buyback pacing (LIVE): …four quarters… — PACESENT` | **Yes**; C7 (execution price) still open |
| F10 | ATR line, execution/risk lanes | **Yes** |
| B5 | `Multiples vs. own history (LIVE): … median 15.7x / 11.3x` | **Partly** — it is today's price against past FYs' *own fundamentals*; B1's 13 lines asked for a price-based series. Different number, and the sheet says so plainly. |
| E1, E2 | `Earnings revisions (LIVE)` + `Surprise history (LIVE)` | **Yes** (E3 guidance deliberately excluded) |
| J1 | buzz score, bullish/bearish %, mention counts, classified split | **Yes** |
| K1 | wired via `journal_context.py` | **Yes** |
| A2 | absent | **Built, dark** — designed R38 `ecbbd4b7`, built slot 4 `aff954b6`; `room_debt_split_enabled` is OFF and the dimensional ingest has not run, so the sheet still shows nothing — and see §6 |

---

## 4. The sources

Every "verified" below was probed against the live source in this session. Scripts in
`evidence/`. Nothing rests on an unprobed assumption about what an API contains.

### 4a · Already fetched by code we run today, and discarded — 10 items

Zero new network, zero new dependency. This is the R33/R34/R35 shape, five more times.
**A3 was here until it was probed** — see §4b and DEF399 for why the probe moved it.

| Items | Where the data already is |
|---|---|
| **C2 C3 C4 C5** cash-flow history, bridge, working capital, FCF conversion | `_fetch_statement_facts_uncached` (`fundamentals.py:210`) pulls the quarterly cash-flow statement; only the trailing four quarters survive. **B2** (cycle-median ROE) rides the same series. |
| **C8** dividend growth CAGR | `MarketDataProvider.dividend_history()` → `DividendPayment` (CR206), fetched today for the options desk's early-assignment rule. The sheet carries yield, indicated annual, payout and ex-date — never the growth series. |
| **G1 G2 G3** IV, skew, open interest | `MarketDataProvider.option_chain()` → `OptionQuote` carries `implied_vol`, `open_interest`, `volume` (CR172 §4). Its own docstring warns `implied_vol` is the provider's figure, *"provenance unknown and occasionally absurd"* — sanity-gating (`services/option_chain.py`) is the work, not the fetch. |
| **I2** catalyst magnitude | Not a source problem at all: we hold the daily bars and each headline's own date. *"The exact percentage magnitude of the CFO-driven rally"* is arithmetic on data in hand. |

### 4b · SEC EDGAR — free, no key, and we already call it — 8 items

| Items | Route | Verified |
|---|---|---|
| **A1** maturity ladder | `companyfacts` carries `LongTermDebtMaturitiesRepaymentsOfPrincipalIn{NextTwelveMonths,YearTwo…YearFive}`. They are simply absent from `INGEST_TAGS_US_GAAP`. | **Two filers.** CAT: 5 tags, 18 points each, FY end 2025-12-31 — 2026 $7,120M · 2027 $8,920M · 2028 $7,747M · 2029 $3,112M · 2030 $1,261M. Deere: 5 tags, 4 points each, FY end 2025-11-02. A five-entry addition to `edgar_tags.py`. |
| **C7** buyback execution price | `TreasuryStockSharesAcquired` ÷ R35's repurchase dollars. | CAT n=197, latest 2026-06-30 = 6,972,123 shares. **Deere has no shares-repurchased tag** — filer-inconsistent, so it ships with a real absent state, which is CR104's rule anyway. |
| **A2 D1 D2** captive split, segment and geographic revenue (A4 fixed/floating was routed here too and closed in the build — §4f) | **Not `companyfacts`** (§6). The filing's own rendered reports, indexed by `FilingSummary.xml` on the same host — **built 2026-09-11 one step short of that**, from the extracted XBRL instance the R-pages are rendered from (§5, slot 4). | CAT 10-K `0000018230-26-000008` (filed 2026-02-13): `R106.htm` long-term debt by *Machinery, Power & Energy* vs. Financial Products; `R108.htm` the ladder; `R129.htm` disaggregation of revenue; `R136.htm` geographic areas. |
| **A3** cost of debt | `InterestExpense` (income statement) and `InterestPaidNet` (cash-flow supplemental), over EDGAR gross debt — both legs from one store at one `as_of`. **Not** the yfinance row §4a first assumed. | **This premise was probed and failed, which is DEF399.** CAT's FY2025 income statement (`R3.htm`) carries *Interest expense of Financial Products* $1,359M **plus** *excluding Financial Products* $502M = **$1,861M**; yfinance's four quarters sum to **$529M**, 28% of it, because the finance arm's interest is booked inside cost of revenue. GM reads 0.17x against its own `us-gaap:InterestExpense`. CAT tags **no** income-statement interest concept in `companyfacts` (dimensional lines again — §6 on a second item), so it resolves on cash interest or not at all. Where the two bases disagree >2x (HOG $31M vs $331M, F $7,613M vs $3,501M) the honest output is **absence**, not the friendlier number. |
| **I1** executive-change detail | The submissions JSON tags every filing with its 8-K **item codes**; `5.02` is *"Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain Officers"*. Fetch that document when the code is present. | CAT's 2026-04-10 8-K (`0001104659-26-042062`) states it outright: **Kyle Epley, 53, appointed CFO effective 2026-05-01, succeeding Andrew R.J. Bonfield, who remains an employee through retirement on 2026-10-01.** That is *exactly* the question the News Analyst asked in 5 of 7 convenes — and once tagged `ABSENT (only the aggregated headline text was provided)`. It was in a filing we already download. |
| **A6** captive funding cost / finance-arm NIM — *surfaced by round 3 (§7.10), outside the 127-line census; the §1 totals are unchanged* | The same extracted-instance route as slot 4: the arm's interest expense is a dimensional fact on the finance member, annual in the 10-K and quarter + YTD in each 10-Q. **Not `companyfacts`** — CAT's `companyconcept` for `FinancingInterestExpense` answers 404. | **Four captive filers probed 2026-09-11** (latest 10-K + latest 10-Q each). **Funding cost: CAT, F, PCAR feasible** — CAT `FinancingInterestExpense` × `FinancialProductsMember` FY2025 $1,359M (Q2-26 $362M vs Q2-25 $336M), over finance-arm debt filed at both year-ends ($29,799M → $32,617M as three components); F `InterestExpenseOperating` × `FordCreditMember` FY2025 $7,133M over $137,868M → $141,417M; PCAR on a **custom tag** `pcar:InterestAndOtherBorrowingExpense` FY2025 $783.0M, and PCAR files the rate itself (4.5% effective on FS debt, 10-K only). **DE partial**: the numerator is filed (`InterestExpenseOperating` × FS segment, FY2025 $2,923M) but no captive-side debt is tagged on any axis — only FS segment assets ($70,300M) or John Deere Capital's own filings (CIK 27673, not fetched). **NIM: not sourceable for CAT, DE, F** — none files an interest-income concept for the arm (CAT bundles it in *Revenues of Financial Products* $3,609M; F's only `InvestmentIncomeInterest` $357M is cash interest and would misstate a NIM by an order of magnitude); PCAR alone files `InterestAndFeeIncomeLoansAndLeases` $1,428.7M. One 10-K + one 10-Q yield **2** discrete quarters (current and prior-year twin), no 10-K carries a 90-day context and no filer files Q4, so four consecutive quarters need three 10-Qs plus a subtraction. A build extends the instance-tag allowlist and adds a custom-taxonomy path for PCAR; a line would state *interest expense ÷ average finance-arm debt, FY* with both instants named, never a NIM. |

### 4c · Free, reliable, no API key, new call — 4 items

*(H1 takes two rows — its CPI/PPI leg and its PMI leg have different answers — but it is one item.)*

| Items | Source | Verified |
|---|---|---|
| **H1** CPI, PPI | **FRED** `fredgraph.csv` — the keyless CSV endpoint. (The documented `api.stlouisfed.org` API *does* require a free key; the graph endpoint does not.) | `CPIAUCSL` 332.813 and `PPIACO` 284.057, both through 2026-07-01. |
| **H1 H3 — RE-PROBED: the technical premise holds, the LEGAL one does not** | Same endpoint, three probes, 2026-09-11. | **Technically confirmed and refreshed**: keyless `fredgraph.csv` returns HTTP 200 `application/csv` for `CPIAUCSL` (332.813, Jul 2026), `PPIACO` (287.928, **Aug 2026** — the CSV carried the Sep 10 print the same day it was probed), `TTLCONS` (2,157,581) and `HOUST` (1,239); the keyed JSON API without a key is a hard 400 (`Variable api_key is not set`); publication lag is 10–33 days after the reference month; values are **identical to the BLS primary** for CPI and PPI, so switching source would change only whose terms govern. Zero new Python dependencies (`httpx` is already installed); one new outbound host. **But three flags, and the first is Saiful's or a lawyer's call, not a build decision.** (1) **Terms.** FRED grants the keyless web route "solely for your personal, non-commercial use", bars "scripts, spiders, scrapers, bots" except as allowed by the *keyed API* terms, and routes app-building "through the free API" — `fredgraph.csv` is named nowhere as a permitted automated route. Worse for both routes: the prohibited-use list bars use "in connection with the development or training of any software program or system or machine learning, including … large language models … generative artificial intelligence". **An automated fetch from a paid app into an LLM room sits inside those words on either route**, so H1/H3 do not ship on FRED without that read; if it rules FRED out, BLS and Census publish the same series directly (not probed — no numbers or terms asserted for them). The sanctioned engineering path, if the read allows it, is the **free keyed API** as an env-driven setting, which makes it a CR040 compose-parity item (absent key ⇒ loud absent state). (2) **CR040 reliability.** FRED's edge **silently hangs** 15–20 s with zero bytes on a branded user-agent while accepting a library UA — a hang, not an HTTP error — so any fetch needs a library UA, a short timeout, a real absent state, and must never sit uncached on the convene hot path. (3) **PMI.** ISM is not on FRED (`NAPM` 404, search returns zero series); the only free PMI-shaped series are **zero-centred regional Fed diffusion indices** (Empire 20.6, Philly 47.4, Dallas 11.6, Aug 2026, all `Copyrighted: Citation Required`) which must be named as what they are — calling any of them "PMI" is the DEF059 mislabel shape. H3's mining leg has a real quarterly BEA series (`E318RC1Q027SBEA`, $92.664B SAAR 2026Q2) but BEA's "mining exploration, shafts, and wells" is dominated by US oil-and-gas drilling, so it carries **BEA's own title verbatim**, never "mining capex". Attribution ("Source: BLS via FRED") is required on every label. **H2 untouched** — still the negative control. |
| **H3** construction spending, housing starts | FRED, same endpoint | `TTLCONS` 2,157,581 and `HOUST` 1,239, through 2026-07-01. |
| **H1 (PMI leg)** | **ISM's PMI is proprietary and is no longer on FRED** — `NAPM` returns 404. Free activity substitutes verified: `CFNAI` (−0.08), `IPMAN` (99.314), `DGORDER` (339,392), all through 2026-07-01. | The honest render names the substitute, never labels it "PMI". |
| **C9 E4** forward growth / payout | **yfinance**, the provider we already call: `growth_estimates` (carries an `LTG` long-term-growth row) and `eps_trend`. | CAT's `+1y` stock trend 19.1%; **`LTG` is NaN for CAT** — ships with a real absent state. **⚠ OVERTURNED 2026-09-11 — see the row below.** |
| **C9 E4 — RE-PROBED, and this row replaces the one above** | Three independent probes, 2026-09-11, on the same provider. | **E4 is not a sometimes-absent cell; it is a field the provider does not serve.** `LTG.stockTrend` is null on **every ticker probed by all three probes (21, 50 and 10-ticker sweeps, and on both yfinance 1.3.0 and 1.5.1)**, and the raw Yahoo `earningsTrend` payload has **no `+5y` period at all** — the `LTG` row exists only because yfinance appends the *S&P 500 index* figure (0.122, identical on every ticker) from `indexTrend`. Rendering that as a stock's long-term growth would be a DEF059-shaped mislabel. **C9 likewise**: none of CAT's 185 `.info` keys is a projection or a payout target (`target*Price` are price targets); what exists is the indicated forward annual rate (`dividendRate`, already shipped as `EarningsInfo.dividend_rate` under CR030, basis verified as last-declared × frequency — exact on four quarterly USD payers, inexact on the monthly REIT O and the ADR TSM) and a trailing GAAP `payoutRatio` (already read). **Both ship as declared absences (the §4f pattern), not as per-convene absent states** — an absent state that always fires is a declared absence and the sheet should say so. What the provider *does* add and we do not fetch is **next-fiscal-year** consensus EPS growth (`earnings_estimate` `+1y`: CAT 19.1%, 27 analysts, 32.377 avg), on a payload `fundamentals.py`'s `eps_trend` call already caches — so it costs zero extra network. It answers a nearer question than E4's 3–5y and must be labelled **"next fiscal year"**, never "long-term". A derived forward payout (`dividendRate` ÷ forward EPS: CAT 20.1%) is arithmetic on consensus and must say so; NVDA's +257.1% last-declaration step-up and O's 236% trailing payout are why neither can be called "growth" or shipped unlabelled. |
| *(supporting)* | **US Treasury** daily par yield curve CSV — free, keyless | 2026-09-02 row returned: 1mo 3.83 … 30y 5.27. The standard input for a *derived* rate path; see H2. |

### 4d · Reachable with what we already own — 13 items

| Items | The call we do not make |
|---|---|
| **B1** and **F1–F9, F11** | `market_data._PERIOD_MAP` already defines `"1y"` (weekly bars), `"2y"` (504 daily bars, CR136) and `"5y"` (monthly). The Room profile is pinned to `_HISTORY_PERIOD = "3m"` (`fundamentals.py:1717`, ~65 daily bars). A parameter, not a provider. MACD, crossovers, Bollinger and volume profile are all computable from bars we can already fetch — the sheet's blanket denial of them is a *choice* that should be re-decided knowingly rather than inherited. |
| **B3 B4** peer basket | `classification_universe.py` persists sector/industry for the ~503 S&P parent constituents, refreshed daily, off the request path. The cohort exists; the cost is N per-peer fundamentals fetches. Note the CR219 R37/WP01-R7 collision marker: shipping this makes the sheet's *"No peer-basket comparison exists"* denial false, and it must be rewritten in the same commit. |

### 4e · No free source found — 1 item

| Item | What was checked |
|---|---|
| **H2** Fed path / rate-cut probability — 5 lines, 3 agents | CME FedWatch is the market standard and is not a free API. The **Atlanta Fed's Market Probability Tracker** publishes exactly this, free, from a Reserve Bank — but its data files (`mpt-current.csv`, `mpt_hist.xlsx`) return a bot-challenge HTML page from this environment under both a plain and a browser user-agent, so **machine-fetchability is unverified**; probe it from melehost before committing to it. FRED serves no probability series. A *derived* path from the free Treasury curve is possible but answers a different question than *"25bps or 50bps"*, and saying otherwise would be the DEF059 shape. |

### 4f · Closed — 5 items

| Items | Why |
|---|---|
| **A4** fixed vs. floating mix | Closed 2026-09-11 in the slot-4 build. The filing carries no fixed/floating fact; what it tags is per-instrument stated rates on `DebtInstrumentAxis` (CAT, DE) — a list of notes, not a mix — and summing them into one figure is the guess the persona already forbids. 4 lines, 3 agents. |
| **G4 G5** Level 2 depth, dark-pool prints | Real-time depth-of-book is per-seat licensed exchange data. No free source exists, and none is appropriate for a simulation-only training app. |
| **E3** guidance | Ruled out by CR219 R22; the sheet's disclaimer stands. Recorded so the register is complete, not to reopen it. |
| **J2** sentiment history | Structurally absent — the social cache keeps one row and overwrites it, by design. The agent correctly tagged its own gap `FORBIDDEN`. |

The right output for this class is a **declared absence** in the sheet's own vocabulary, so an
agent stops spending a turn asking. That is a CR219-shaped prompt change — the one piece of
work this CR hands back rather than sources.

---

## 5. The open items are 14 sourcing decisions

| # | Decision | Items | Lines | Cost |
|---|---|---|---|---|
| 1 | Add 5 maturity tags to `edgar_tags.py` | A1 | 14 | 5 entries + a render |
| 2 | EDGAR filing route — the extracted XBRL instance (§6; A4 closed in the build) | A2 D1 D2 | 26 | a new parse path, free host (§6) — **built, slot 4** |
| 3 | EDGAR interest expense (accrual + cash) over EDGAR gross debt | A3 | 6 | two tag families, same host |
| 4 | Keep the multi-year statement series instead of the trailing four | B2 C2 C5 (+B1's fundamentals leg) | 6 | discarded data |
| 5 | Fetch the profile at a longer bar window | B1 F1–F9 F11 | 32 | a parameter |
| 6 | Peer cohort × fundamentals | B3 B4 | 3 | N fetches, cohort exists |
| 7 | Render the cash-flow detail already pulled | C3 C4 | 11 | discarded data |
| 8 | `TreasuryStockSharesAcquired` ÷ R35's dollars | C7 | 1 | one tag |
| 9 | `DividendPayment` history (CR206) | C8 | 2 | already fetched |
| 10 | yfinance `growth_estimates` / `eps_trend` | C9 E4 | 3 | already our provider |
| 11 | `OptionQuote` chain + IV sanity gating | G1 G2 G3 | 7 | already fetched |
| 12 | FRED `fredgraph.csv`, keyless | H1 H3 | 4 | one HTTP dep, no key |
| 13 | EDGAR 8-K Item 5.02 | I1 | 5 | same host we already call |
| 14 | Derive catalyst magnitude from bars + headline date | I2 | 2 | arithmetic |

**Five decisions need no new network at all** (4, 7, 9, 11, 14). Seven more ride hosts we
already call (1, 2, 3, 8, 10, 13) or a parameter (5). Only #12 adds an HTTP dependency, and it
needs no key. **Zero paid providers.**

### Preliminary build order

Ranked by demand against sourcing cost. A recommendation, not a ruling.

| # | Item(s) | Why here |
|---|---|---|
| 1 | A1 + A3 | 20 lines from the two most-asked debt sub-items. **Source layer landed 2026-09-03** — see Build status below. |
| 2 | I1 | 5 lines, one agent, stuck on the same wall in 6 of 7 convenes — and the answer is in a filing we already download. Cheapest high-conviction fix in the list. |
| 3 | C3 + C4 + C2 + C5 + B2 | 20 lines across five items, all one decision on data already pulled and thrown away. |
| 4 | A2 + D1 + D2 (+ A4, closed) | 26 lines, the biggest payoff — and the biggest unknown. **Built 2026-09-11** — see "Slot 4 built" below. |
| 5 | C8 + C7 + C9 + E4 | Cheap, already fetched, filer-inconsistent → real absent states. |
| 6 | G1 + G2 + G3 | Fetched already; the IV sanity gating is the work. |
| 7 | H1 + H3 + I2 | One keyless dependency plus one derivation. Name the ISM substitute honestly. |
| 8 | B1 + F1–F9 + F11 | 32 lines but concentrated in 1–2 agents, and the sheet already answers the trend question five ways. High count, low breadth — deliberately last. |
| 9 | B3 + B4 | Low measured demand; its real value is unblocking a stale sheet denial. |
| — | H2 | Blocked on §4e. Probe the Atlanta Fed feed from melehost first. |
| — | E3 G4 G5 J2 | Declared absences, handed to CR219's surface. |

### Build status

The register's `○` column is unchanged for A1 and A3 **on purpose**: it tracks what the
Room can see, and until the render lands the agents are still short of both. What exists
today is the source layer.

Two-phase by necessity, not preference. `room_runner._profile_for_ticker` and
`room_prompts._format_profile` are the render sites and both are dirty under CR219's
prompt lane, so phase 1 touches producer files only. That also keeps DEF098's parity
guard quiet: it keys off the *fetcher's* output dict, and nothing here adds a key to it.

| | Landed (`472efbfc`) | Pending phase 2 |
|---|---|---|
| **A1** | `edgar_tags.DEBT_MATURITY_LADDER` (5 tags, in `INGEST_TAGS_US_GAAP`); `services/debt_maturity.py` — one-vintage resolver, derived beyond-year-five, the two reconciling figures; `room_debt_maturity_enabled` + compose; 13 tests, 2 mutations killed. | the render, and the basis line it must carry |
| **A3** | `edgar_tags.INTEREST_ACCRUAL` / `INTEREST_CASH`; `services/interest_cost.py` — three labelled bases, >2x disagreement refusal; `valuation.cost_of_debt_pct` with a 40% artifact ceiling; `room_cost_of_debt_enabled` + compose; 13 tests, 2 mutations killed. | the render; and A3 is **DEF399's fix vehicle**, so the shipped `interest_coverage` numerator changes with it |

**Two things the build found that the sourcing pass did not.**

**1. The ladder does not reconcile to the sheet, and must say so.** CAT's five buckets sum
to **$28,160M** against a fact sheet reading **gross debt $45,146M**. Both are right: the
ladder is long-term principal only, excluding short-term borrowings ($5,514M) and
everything beyond year five (derived, $9,656M). An agent handed the ladder beside gross
debt with no basis note reads a $17B gap as a contradiction and burns a turn on it —
which is the CR219 failure class this whole CR sits downstream of. The resolver therefore
returns the reconciling figures, and the render is not free to omit them.

**2. EDGAR gross debt is short for the same filers, and it is not patched.**
`DEBT_ANCHOR + DEBT_OPTIONAL_ADD` sums to $36,210M for CAT, because it tags current
maturities dimensionally and `LongTermDebtCurrent` / `DebtCurrent` resolve to nothing.
That biases the cost of debt HIGH — 5.1% against ~4.3% on the fuller base. The missing
piece is exactly A1's year-one bucket, so the two items compose; adding it conditionally
would double-count for every filer that *does* tag current debt, and would redefine gross
debt for one consumer only. Recorded as a bound on the figure, not fixed behind the
reader's back.

### Phase 2 landed, and slot 3 opened (2026-09-03)

The prompt lane cleared at `8d495606`, so the two render sites became writable and phase 2
shipped: `95e7dbec` (the A1/A3 render, flag-gated, with the dark-ingest warning),
`7a9854eb` (an unreachable fact store degrades the block instead of killing every Room
run — the crash a fresh solo-dev DB would have hit), `fb0a916a` (A3's denominator struck at
the numerator's own period end, not at `as_of`; MSFT was pairing FY2024 interest with a
2026 balance sheet and reading 7.3%), `e9d3c131` (the ladder's reconciliation clause).

`8b4f189c` then shipped **C3 + C4** — the cash-flow bridge — and with it the fix for a
defect the bridge could not be built without.

| | Shipped | Flag |
|---|---|---|
| **C3/C4** | `fundamentals._ttm_millions` + five source keys off the `.quarterly_cashflow` frame already fetched; `cashflow_bridge_line` on both surfaces; working-capital drivers with a remainder that closes the sum. | `room_cashflow_bridge_enabled` |
| **DEF400** | `free_cash_flow` — and with it `fcf_yield` and CR218's `capital_return_pct_fcf` — derived as OCF − capex, falling back to `.info` when a filer's four quarters are short. | `fundamentals_fcf_from_statements_enabled` |

**The third thing the build found: a shipped number is wrong, and the Room escalates on it.**
`.info`'s `freeCashflow` reconciles to nothing — CAT **$5,049M** against $13,569M − $4,575M =
**$8,994M**, which the same frame's own `Free Cash Flow` row confirms to the dollar. It was
right when CR218 shipped (that comment records $8,961M), so this is provider drift on a
rendered figure. It lands on the capital-return line: **200% of TTM FCF** on the stale number,
**112%** on the filed one. §7's first replay then showed this is not latent — **four of twelve
agents reasoned from it in a single convene**, three naming *"the 200% FCF payout"* and one
quoting `$5,049M` by value. A company returning twice its free cash flow is a solvency alarm;
112% is an ordinary cyclical year. Filed and fixed as **DEF400**.

Two consequences for this CR. **C3/C4 unblocked** — §5's build order had them waiting on
DEF400, and the fix is the same code path. **C2/C5 remain open**: they want the FCF *series*,
which the bridge does not carry.

**Slot 2 (I1, EDGAR 8-K `5.02`) stays behind slot 3**, and the reason is worth recording: I1 is
5 request lines from 1 agent and needs a new external-prose-on-request path, while slot 3 is
20 lines across 5 items over a frame we already fetch. Breadth per unit of new surface, not
sequence in the register.

### Slot 4 built — A2, D1, D2 from the filing's own XBRL instance; A4 closed (2026-09-11, `aff954b6`)

Saiful's pick for the final window (2026-09-10: *"we have an additional 6 hours"* → slot 4). The
§6 re-route is now code, and the route is one step shorter than §4b's `FilingSummary.xml`
proposal. The R-pages (`R106.htm`, `R129.htm`, `R136.htm`) are rendered HTML of the same
data that the **extracted XBRL instance** carries as facts —
`https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary_stem}_htm.xml`, one XML per
filing, free, same host, same user-agent. Its `xbrli:context` elements carry the
`xbrldi:explicitMember` dimensions that `companyfacts` strips, so the parser reads
`(concept, axis, member, period)` cells directly instead of scraping tables.
`backend/scripts/ingest_edgar_dimensional.py` fetches the newest original 10-K's instance per
ticker (amendments skipped), parse-validates it, and stores derived rows under a house
taxonomy (`ami:CaptiveFinanceDebt:<concept>`, `ami:IndustrialDebt:<concept>`,
`ami:SegmentRevenue:<tier>:<member>`, `ami:GeographicRevenue:<member>`,
`ami:ConsolidatedRevenue:<concept>`) in the existing `edgar_facts` store, point-in-time by
`filed` like everything else in it.

**Measured on the four registry filers' FY2025 10-Ks** (read live 2026-09-10, `$M`):

| | Captive debt | Industrial debt | Segments (tier, coverage) | Geography (coverage) |
|---|---|---|---|---|
| CAT | 32,617 | 10,713 | 4 · external sales · 101% of 67,589 | 4 regions · 100% |
| F | 141,417 | 21,919 | 4 · incl. intersegment · 100% of 187,267 | 5 · 100% |
| PCAR | 15,666 | *not tagged* → captive-only | 1 member at 92% → **refused** | 3 · 100% |
| DE | *no dimensional debt facts* → **UNAVAILABLE** | — | 4 · incl. intersegment · 101% of 45,684 | 6 · 100% |

**Four things the build settled, each pinned by a test.**

**1. The industrial figure is read from its own column, never derived.** CAT tags both sides
of its consolidating balance sheet on `srt:ProductOrServiceAxis`, and the two
`LongTermDebtAndCapitalLeaseObligations` cells — Financial Products $20,018M, Machinery,
Power & Energy $10,678M — sum to the non-dimensional `LongTermDebtNoncurrent` $30,696M to the
dollar. The parked WP10 contract derived industrial as consolidated minus captive; on CAT that
gives **$3,593M for a filed $10,713M**, because the house gross-debt tags are a different
family from the column's. A filer that tags one side gets one side (PCAR), and the
captive-only line says outright that industrial is *not* the difference.

**2. Registry matching is exact, not substring.** Ford's industrial column is
`CompanyExcludingFordCreditMember`; a "contains `fordcredit`" rule files the industrial
parent under the lender. Four filers in `edgar_tags.CAPTIVE_FINANCE` (CAT, DE, F, PCAR), each
with its lender named and both member sets listed; a filer outside it gets no line at all.

**3. A breakdown is a partition or it is nothing.** Filings tag overlapping cuts side by side:
CAT carries `country:US` + `NonUsMember` beside its four regions, and an aggregate segment
member beside the four segments. The resolver takes the largest member set whose sum sits
within 10% of the *same filing's* consolidated revenue, at least two members, and the line
states the coverage either way ("these sum to 101% of the $67,589M consolidated total, the
difference being corporate items, intersegment sales and eliminations"). Segment revenue is
tried in tiers — external sales (`OperatingSegmentsExcludingIntersegmentElimination`), then
including intersegment (`OperatingSegments`), then bare members — and the tier order is not
cosmetic: Deere's bare members cover 87% and would have failed the band; its operating-segment
tier covers 101%.

**4. Units resolve through `xbrli:unit`, not the `unitRef` string.** A `unitRef` is an id the
filer's tool chooses. CAT writes `usd`; Deere writes `Ifeqnbq-buca0lohammirw`. The first
parser draft read the id as the unit and silently dropped **all 278 of Deere's facts** — the
CR040 shape exactly, a filer reading as "tags nothing" for a parsing reason. Found by the
four-filer smoke, not by the suite, which is the fourth time in this CR that running on a real
filing found what a fixture could not.

**A4 (fixed vs. floating mix) closes ⛔ — not structural.** Nothing in the instance carries a
fixed/floating split as a fact. What exists is per-instrument stated rates on
`DebtInstrumentAxis` (CAT, DE), which is a list of notes, not a mix; summing them into one
would be the "guess is worse than the blended figure" the persona already forbids. 4 lines
from 3 agents, and the register's totals move: **9 delivered · 5 closed · 35 open.** Decision
#2 now covers three items, 26 lines.

**Render.** Three flags — `room_debt_split_enabled`, `room_segment_revenue_enabled`,
`room_geographic_revenue_enabled` — default off, forwarded in compose. The overlay populates
the profile regardless (one `field_state` key per item: `debt_split`, `segment_revenue`,
`geographic_revenue`), and the flag gates the Room render only, the CR221 slot-1 convention
that keeps §7's control arm a flag flip. `debt_split` is LIVE for every registry filer, in one
of three states the line names — resolved, captive-only, UNAVAILABLE — and absent for everyone
else. The 1-on-1 sheet is untouched, like A1/A3. **CR219's R38 declared-absent entry is
retired**: its collision markers were armed for exactly this line and went red on the first
render, which is the mechanism working; the persona now defers to the sheet's "Debt split"
line and denies the split only where the sheet has none. 73 tests across
`test_cr221_a2_debt_split.py` and `test_cr221_d1_d2_revenue_breakdown.py`, built on CAT's
filed cells.

**Promoted 2026-09-11 (`alpha-2026-09-11-1` / `445f6a43`), by hand over Tailscale** — the
`melehost` alias resolves to a LAN address the Mac could not reach that night. Postflight
identity, readiness, config and market green; alembic at head; the tag also carries the 1a
lane's DEF401 and DEF403. **The suite gate had said FAIL and the promotion went ahead anyway**:
the gate ran as `preflight_suite.sh | tail` inside a background task, the task reported
*tail's* exit 0, and the one failure was DEF403's register-row link (docs-only, fixed at
`9aff8fef`), so nothing shipped was wrong — but the gate had said no and nothing downstream
noticed. Filed as **DEF405** with a guard the same night (the gate now writes
`.deliveryos/suite_verdict.json` with the commit it tested, and postflight's new `suite` check
fails a promotion whose record is missing, stale, partial, for another commit, or not PASS —
`failure_patterns.md` P35, the third DEF326-shaped instance).

**The dimensional ingest ran inside `ami_api_alpha` the same hour**: 146 of 150 filings, 0
failures, 2,736 `ami:` rows (segment 1,067 · geographic 1,173 · consolidated 460 · captive debt
17 · industrial debt 19). The four skips are three foreign filers (NIO, SPOT, XPEV — 20-F, no
10-K) and XOM, whose ticker the SEC map now points at *ExxonMobil Holdings Corp* (CIK 2115436,
a successor with no annual filing yet) while the 10-Ks sit under CIK 34088 — recorded, not
worked around. Resolved on Alpha's own store, inside the container: CAT $32,617M / $10,713M,
F $141,417M / $21,919M, DE UNAVAILABLE, all to the dollar against the Mac; AAPL segments
(Americas, Europe, Greater China…) 100%, MSFT's three segments 100% and its US/Non-US
geography 100%, NVDA's two segments 100%. PCAR is not in the 150-ticker universe, so its
captive-only shape exists on the Mac's smoke only. **All three flags remain OFF.**

### Slot 2 built — I1 from 8-K Item 5.02 (2026-09-11, `98e1b36f`)

Register item I1, "Executive-change detail (identity, background, circumstance)": 5 request lines
from one agent, the News Analyst, all on CAT's CFO transition. §4b's route is now code —
`backend/app/services/edgar_8k.py`, `backend/scripts/ingest_edgar_8k.py`, migration
`cr221a0b0c0d4`, and `_overlay_executive_change` in `room_runner.py`.

**Store-backed, not request-time.** §4b framed I1 as "a new external-prose-on-request path";
the build rejected that. A live sec.gov call inside `_profile_for_ticker` would have been the
Room's first runtime network dependency on EDGAR (every other slot is DB-only), needed a
patchable seam for the parity and CR219 fixtures (which run the real profile builder against an
empty sqlite), and put the SEC's rate limit and a 5 s retry inside a convene. So the ingest
script reads the submissions index (`filings.recent.items`, a comma-separated string — token
match, "5.02" must not match "5.03"), fetches each Item 5.02 primary document, parses the section
with stdlib `html.parser` (no new dependency) and stores it in `edgar_8k_items`; `edgar_facts`
cannot hold prose (`value` is `Numeric NOT NULL`). One `edgar_8k_scans` row per pass records
`scanned_at`, `covered_since` (how far back the index page reaches) and the window, so the sheet
can say "none filed between X and Y" as a **dated claim** — without it, a quiet filer and an
empty store are the same silence.

**Five states, each with its own log event** (`executive_change_state`; `field_state`
key `executive_change`):

| state | field_state | log | meaning |
|---|---|---|---|
| `filed` | live | `edgar_8k_item_unextracted` (info, per item without text) | the scan covers the window and found Item 5.02 filings in it |
| `none_in_window` | live | none | the scan covers the window and found none — rendered as "none filed between … Do not supply one from memory." |
| `unscanned` | unavailable | `edgar_8k_not_ingested` (no scan row for ANY ticker) or `edgar_8k_ticker_not_scanned` | the ingest never ran, or this ticker is not on its list |
| `stale` | unavailable | `edgar_8k_scan_stale` | the newest scan cannot vouch for the render window (verified_through < verified_from) |
| `unreadable` | unavailable | `edgar_8k_unreadable` | the store raised |

A document that failed to fetch or parse at ingest still gets its item row (`extract_status`
`fetch_failed` / `unextracted`, text NULL) **and** the scan row — the filing's existence comes
from the index; the sheet names the accession and says its content is not supplied. The next run
retries non-extracted rows without `--force`.

**Windows and cap, measured.** Ingest window 365 days; render window 180 days; verified window =
[max(covered_since, scanned_at − 365, as_of − 180), min(scanned_at, as_of)]. At most 2 filings
render. The excerpt is sentence-bounded at 1,200 chars (a period after Mr./Inc./an initial is not
a sentence end) with the "Item 5.02" prefix and the Reg S-K caption stripped: on CAT's
0001104659-26-042062 the body is 2,058 chars and the excerpt 1,053 — it keeps "appointed Kyle
Epley as the Company's Chief Financial Officer, effective May 1, 2026, succeeding Andrew R.J.
Bonfield", "retirement from the Company on October 1, 2026" and "joined Caterpillar in 1996",
and drops the pay bullets ("$930,500" is absent). Every string reaching the line passes
`sanitize_for_prompt` at the render seam. The rendered line carries form, filed date, age in
days from the sheet's run date, event date (`reportDate`) and accession, plus a trailer that Item
5.02 also covers director elections and pay terms and the analyst must not infer a reason the
filing does not state. AAPL's 2026-04-20 8-K pins the parser's one trap: the in-body "Item
5.02(c)(3) of Form 8-K" is not the heading.

**Lane and provenance.** News lane (the News Analyst plus every full-sheet agent), placed beside
the catalyst line so tenure-withholding strips it; it renders under `withheld_paid` because the
paywall is on the FEED and this source is free; it has its own `field_state` key because `news`
is four-state and surcharge-bound. The header gets its own bullet ("a free source, NOT the news
feed above and NOT under its 7-day floor"). The 1-on-1 `build_news_context_block` is untouched,
like every prior slot.

**Persona, overlay, guard — edited by hand in the same commit.** `news_analyst.md` line 19 now
defers to the `"Executive change (8-K Item 5.02)"` line by its exact label and denies only the
residual (macro calendar, S-1/10-K text); `overlay_generator.py`'s news bullet keeps its R11
prefix and names the line; the CR219 allowlist entry's anchor and `why` are rewritten. The
guard could not catch this one itself — the `sheets` fixture flips no `room_*` flag, and an
allowlisted entry has no collision markers — so `test_cr221_i1_executive_change.py` pins the
coupling (persona and overlay contain the label verbatim; the anchor is a substring of the
persona line).

**Deploy order (§7.6c).** Promote → `docker exec ami_api_alpha python scripts/ingest_edgar_8k.py
--user-agent "AMI Trade CR221 (saiful.mazli@gmail.com)"` → read the summary's named failures
(`[fetch_failed]`, `[unextracted]`, `[recent_block_short]`) → set
`ROOM_EXECUTIVE_CHANGE_ENABLED=true` in melehost's `.env`. Freshness is a cron follow-up
(Saiful's call): without a re-run, `edgar_8k_scan_stale` fires 180 days after the last scan and
the line goes unavailable rather than quietly out of date. Live probe on the Mac (2026-09-11,
scratch sqlite): CAT and F both resolve — CAT to the Epley/Bonfield filing, F to the
2026-04-15 departure of J. Douglas Field (202 chars, rendered complete); 5.7 s for both tickers.
**The flag stays OFF until the §7.3 citation-rate rig runs**; `replay.py` has the `exec` arm, and
the CAT pickles must be rebuilt after the ingest (R46: a rebuild moves every other live field).

**Review round (2026-09-11).** Four MAJOR findings against `98e1b36f`, all of one shape — a line
that states something the data behind it cannot vouch for — plus the MINORs that were cheap:

- *An unreadable index read as a quiet filer.* `select_502_filings` returned `[]` for a submissions
  JSON whose shape had changed (`filings.recent` renamed, items as `"Item 5.02,Item 9.01"`,
  `filingDate` renamed or unparseable), the ingest wrote the scan row anyway, and the sheet rendered
  a LIVE "none filed between X and Y" — P26 exactly. Now `recent_block` validates the five columns
  it reads (present, one length), every in-window 8-K's item string must be `d.dd` tokens and its
  date must parse, and any of those raises `IndexUnreadable`; `ingest_ticker` writes **no scan row**
  on it and names the ticker under `[index_unreadable]`. The Room reads it as `unscanned`. Seven
  shapes are parametrised in the test, and the ingest-to-overlay consequence is pinned end to end
  (`test_ingest_writes_no_scan_row_for_an_unreadable_index_and_names_it`). The 150-ticker index
  format is unchanged — the live re-ingest of CAT, F, GOOGL and GOOG ran with `index_unreadable: 0`.
- *A false count.* Three Item 5.02 filings in the window rendered as "2 filings between …". The
  overlay now carries `executive_change_total`; the line says "4 filings (newest 2 shown; 2 older
  not shown)" — Alphabet's real store, above, is the measured case.
- *A cross-reference read as the heading, or as its end.* "The information set forth in Item 5.02 of
  this Current Report …" in Item 1.01 became the section, labelled "complete"; "filed pursuant to
  Item 5.02 of Form 8-K" mid-section cut it off before "not the result of any disagreement". The
  anchor is now the **line start** of `html_to_text`'s block-per-line output (a heading starts a
  block; a reference sits mid-sentence), the first candidate whose section clears the 40-char floor
  wins, and the parenthesis lookahead is gone — because the live probe found Alphabet's 2026-06-05
  8-K (`0001652044-26-000059`) heading its section "Item 5.02(c) Appointment of Principal Officer",
  which the first parser stored as `unextracted`. It is the third real fixture; it extracts at 1,117
  chars, complete, and the retry pass picked it up without `--force`.
- *Cheap MINORs.* The days between the scan and the sheet's run date are named in the line ("The
  163 days after 2026-04-01 … are NOT verified"); the seam re-caps an over-long excerpt
  (`EXCERPT_CAP`, with an ellipsis) instead of trusting the profile dict; items are read by the scan
  row's **CIK**, not the ticker, so GOOG shows GOOGL's filings rather than reading as quiet (the
  ingest dedups on CIK; the read index is now `(cik, filed)`); `<noscript>`/`<textarea>`/
  `<template>`/`<iframe>`/`<svg>`/`<head>` and anything styled `display:none`, `visibility:hidden`,
  `font-size:0` or `hidden` are dropped by the text extractor; the `edgar_8k_ticker_not_scanned`
  warn names both causes (not on the list, or the last pass failed before a scan row); the persona
  sentence now says *filing text* reaches the analyst only through the line (a headline may still
  report a change) and asks for the role/names/circumstance the filing states rather than a
  verbatim quote. Not fixed: the single-capital abbreviation guard (harmless, never lengthens an
  excerpt); the CR219 guard cannot see flag-gated store-backed lines by construction — the pin
  stays in this slot's test file.

**Review rounds 2 and 3 (2026-09-11, `c25fee09`, `d6c364c2`).** Two more refuting passes, each
of two lenses, each landing MAJORs that were real and evidenced by a run:

- *Round 2.* A submissions JSON with every column present and **zero rows** (the shape
  `filings.files` pagination produces) read as a quiet filer — now `IndexUnreadable`, no scan
  row. A filer that heads its sub-items separately ("Item 5.02(b) Departure …", then "Item
  5.02(c) Appointment …") was cut at the second sub-heading and the truncated departure labelled
  complete — the terminator now excludes the section's own code. The hidden-text filter was
  narrower than the module claimed — it is now **exactly the stated list** (inline and
  `<style>`-bound class/id rules), with colour, external stylesheets, layout and compound
  selectors named as what it does not detect. The excerpt is bracketed `⟦filing text begins⟧ …
  ⟦filing text ends⟧` with those glyphs stripped from the filing text, because a plain `"` in a
  filing closed an ASCII quotation and let the rest read as sheet prose. Aging warn at 30 days;
  a backtest `as_of` before the scan's window names the store, not a re-run; `has_item` deleted.
- *Round 3.* The round-2 filter matched CSS property names as **substrings**: `border-width:0`,
  `min-height:0`, `line-height:0` with `overflow:hidden`, and `backface-visibility:hidden` — the
  CSS EDGAR puts on visible table cells (`border-width: 0` is in the AAPL fixture) — dropped
  filing prose the line then labelled complete. Every property regex now carries a left boundary.
  And the round-2 terminator exclusion had undone the documented pass-over of a line-start
  reference ahead of the real heading ("Item 5.02 of Form 8-K applies."): the section started
  at the reference and swallowed the heading. A 5.02 match with no body line of its own before
  another 5.02 heading is now passed over; a sub-item heading, whose body is on the next line,
  still starts the section. Cheap MINORs with it: `opacity:.0`/`0%` hide, margin offsets count
  as off-screen, a rule inside an `@media` block is not read (stated), and a sentence opening
  "Signature Bank …" no longer terminates the section. The three real fixtures are
  byte-identical before and after both rounds (AAPL 1,726 · CAT 2,216 · GOOGL 1,130 chars).

Merged onto `main` as `98e1b36f`…`d6c364c2`; 268 tests green across the I1 file and the guards.
Audit lane `CR221-SLOT2` follows.

---

## 6. The R38 correction — measured, and it lands on a lane in flight

**R38's design note states that the industrial-vs-captive split "lives in the `companyfacts`
payload's per-fact `segment` object" and that the work is a dimensional parser over data we
already ingest. That premise does not hold.**

Measured against the live endpoint (`evidence/edgar_census.py`):

| Filer | us-gaap fact points | Points carrying a `segment` key |
|---|---|---|
| Caterpillar (CIK 18230) | 39,403 | **0** |
| Deere (CIK 315189) | 35,550 | **0** |

Every fact point on both filers carries exactly `{end, val, accn, fy, fp, form, filed, frame,
start}`. There is no `segment` object to parse: `companyfacts` serves the **consolidated,
non-dimensional** fact only. That is why CAT's `Revenues` shows 345 points with 118 duplicate
`(start, end)` pairs — the same consolidated figure restated across filings, distinguished by
`accn`/`filed`, not by segment member.

`backend/scripts/ingest_edgar_facts.py` currently carries an uncommitted
`_segment_member_names(fact)` reading `fact.get("segment")` (lines 129–142) plus two call sites
gated on it. **On this evidence it returns `[]` for every fact of every filer**, so the
dimensional pass finds nothing and the captive-split resolver produces no data — which, under
CR040, must not be allowed to look like *"this filer has no captive-finance segment"*, R38's
own documented common case. The two states are indistinguishable at the render layer as
designed, and a parser that cannot fire has no test that can prove it wrong.

**The data is real** — §4b verified it in CAT's `R106.htm`. R38's *conclusion* (no new provider,
no paid feed) survives; its *route* does not.

### Ruled, 2026-09-03 (`ac55352c`)

WP10's own escape hatch fired on the same evidence, reached independently — its finished parser
returned nothing against the live payload. Saiful ruled, verbatim:

> accept recommendation: Declared-absent entry in CR219 now now and Re-route under CR221 later

**Enacted:** CR219 closes R38 with a `SHEET_ABSENTS` declared-absent entry whose collision
markers are drawn from the parked patch's own render strings — so the availability guard goes
red the day a real split line lands. The full WP10 build (5 source files, 83 green tests) is
parked at `CR219/dev_instructions/WP10_R38_parked/`, **not deleted**: its registry, config flag,
three-state contract, both render sites and ~60 route-independent tests are route-independent
and are this CR's head start. Only the route changes — `companyfacts` dimensional parse becomes
the `FilingSummary.xml` per-filing reports of §4b.

---

## 7. Measurement — proving the data changed the Room

**Required deliverable (Saiful, 2026-09-03):** once the fields are built, re-run CR219's own
convenes with the new data and conclude how much difference it makes.

This section is written *before* the build because it constrains it: an A/B that cannot be run
later is one nobody designed for now.

### 7.1 The endpoint problem — read this before choosing a metric

**"Did the verdict change" cannot be the primary endpoint.** The PM's verdict is measurably
noisy: `risk_officer.py:32` records **19.7% of convenes splitting across byte-identical
inputs**. Production has defaulted to `pm_self_consistency_samples=5` since CR214, and CR219's
R47 found every remaining n=5 flip is a **parse-loss tie**, not indecision. A verdict that moves
after we add a field is, at any n we can afford, indistinguishable from a coin landing
differently. CR219's own `aggregate_arms.py` refuses to attribute verdicts for exactly this
reason, and this CR inherits that refusal.

So the primary endpoint is not the verdict. It is **whether the Room stopped asking**.

### 7.2 Primary endpoint — demand extinction, per item

Re-run the same seven convenes with the same `DATA I LACKED:` addendum, and score the replies
against the **49-item register** using `evidence/items.py`, which already maps request text to
item ids. The baseline is this CR's own corpus.

| | Baseline (2026-09-02) | Prediction after the build |
|---|---|---|
| Items we shipped | asked 1–18 times each | **asked 0 times** |
| Items we declared absent (E3, G4, G5, J2) | asked 2–3 times each | asked ~0 — a declared absence should stop the question |
| Items we did not ship (H2) | 5 | unchanged — the negative control |

This endpoint is direct, pre-registered, per-item, and needs no significance test to be
readable: an item asked 18 times by 9 agents that is asked 0 times afterwards has been
answered. An item that is *still* asked after we shipped it is the more interesting result —
it means the render is not where the agent looks, which is precisely the CR219 failure class.

**H2 is the negative control** and must not be dropped from the run: if demand falls on
everything including the one item we did not source, the instrument is measuring something
other than the data.

### 7.3 Secondary — is the new data actually used?

1. **Citation rate per new line**, via CR219's `evidence/analysis/citation_rates.py`. The
   precedent is the whole reason CR219 exists: on identical sheets, margin *structure* was
   cited 95.5% of the time and margin *trend* 24.2%. A field nobody cites cost tokens and
   context for nothing, and that is a finding, not a failure to hide.
2. **Reasoning-trace presence.** The convenes bank full reasoning traces. A number that appears
   in the reasoning but not the answer is being used and not shown; the reverse is being shown
   and not used. Both are worth knowing and neither shows up in a verdict.
3. **Cost.** Prompt tokens, latency, and remaining context headroom against the served budget —
   the check WP06 already ran once when the sheet grew.

### 7.4 Recorded, not attributed

Verdict distribution across arms, labelled with its n and the 19.7% figure, exactly as
`aggregate_arms.py` prints it today. Recorded so the run is complete; **not** offered as
evidence the data changed a decision.

### 7.5 Design — what makes the comparison valid

- **One profile pickle per ticker.** `harness/build_profile.py` caches profiles precisely
  because market data moves between fetches (R46); the README's rule is that *every arm in a
  comparison must load the same pickle*. The control and treatment arms therefore differ in the
  new fields **and nothing else** — same prices, same news, same FOMC countdown.
- **Therefore: every CR221 field ships behind its own config flag, default off.** The control
  arm is a flag flip against one enriched pickle, not a second build or an earlier checkout.
  This is a build constraint, not a measurement preference — without it the A/B is not
  runnable, and it also satisfies WP06's degrade-loudly rule for free.
- **Same battery.** The six mandate arms plus the full convene, same tickers, same
  `mandates.py` `BATTERY`, run through `harness/run_convene.py` as `room_runner` calls it.
- **Both models.** The arms were run on Gemini 3.1 Pro to get reasoning traces; production
  serves Qwen3.8. Score the production model for what users get, and the arms model for
  comparability with the CR219 baseline. Do not merge the two into one number.

### 7.6 The live instrument — and why it counts something else

CR219's **R53** (landed 2026-09-03, `8d495606`) puts a permanent `DATA GAPS:` tail on every
Alpha convene plus `backend/scripts/aggregate_data_gaps.py` — a standing demand signal on real
traffic. That is the trailing confirmation this CR's one-off re-run cannot give: it answers
"did demand stay down, on tickers we never tested".

**It is not comparable to this CR's register.** `aggregate_data_gaps.py:85` copies
`aggregate_arms.py`'s `BUCKETS` taxonomy verbatim — the same regex this CR measured as
undercounting debt (26 asks against an actual 35) and dropping 17 lines to `(unbucketed)`.
Production telemetry keyed to that taxonomy cannot be scored against the 49-item register,
and the undercount lands on the single largest ask.

**Resolved 2026-09-03 — no change asked for, and none needed.** R53 landed at `8d495606`
with the taxonomy deliberately frozen, and its own comment gives the reason: *"the arms
prototype's own bucket taxonomy, unchanged — the point is that this script's ranking is
directly comparable to the number the arms experiment already produced, not a fresh
categorization that would break that comparison."* That is right for R53's purpose.
Re-keying it to `items.py` would buy CR221 comparability by destroying R53's.

So the two instruments count different things **by design**, and this CR states it rather
than reconciling it: R53 answers *"which areas is the Room short in, tracked continuously
against a fixed prototype baseline"*; CR221 §7.2 scores with `items.py` and answers *"did
this specific item stop being asked for"*. **Neither number may be quoted as the other.**
The one live figure that must not be repeated in a CR221 report is R53's debt-bucket count —
measured here as undercounting 26 against an actual 35, with 8 of the 17 `(unbucketed)`
lines being debt asks its regex misses and a 9th claimed by a peer pattern.

### 7.6b The instrument, and three things the build settled about it

**The instrument is the arms addendum, not R53's shipped tail.** R53's
`DATA GAPS:` block is the right permanent production signal, but it is
ANALYSTS-only (`room_prompts.py:1693`) — four agents. The register's demand
comes from twelve: A1's fourteen lines span six, most of them researchers and
risk debators the shipped tail never reaches. Scoring with it would measure a
quarter of the demand and report it as the whole. So `measurement/replay.py`
appends `evidence/convene_gemini.py`'s addendum **byte-identical** — reworded,
it would not be the question the 127-line baseline answered — and it does so
through a `VLLMClient` subclass, so CR219's harness files are read, never
edited.

**The baseline has to be re-run, for a second reason.** §7.5 already required
it (one pickle per ticker, R46). The stronger reason is that the banked corpus
was produced by **`gemini-3.1-pro-preview`**, and the replay runs the
production model, on-prem `qwen3.8-flash-next` (`root` read from `/v1/models`,
2026-09-03). The banked 127 lines are the register's *provenance*; they are not
this experiment's control arm.

**The control arm is a flag flip, and that is now verified rather than
asserted.** The same cached CAT profile renders a 3,968-character fact sheet
with both flags off and 4,315 with both on — the 347-character delta is the two
new lines and nothing else moved.

### 7.6c Deployment prerequisite — the flags turn on nothing without this

Measured on Alpha 2026-09-03: `edgar_facts` holds **351,139 rows across 150
tickers** and **zero** under any of the five maturity tags or the two interest
tag families, because the last ingest ran **2026-08-19** — before those tags
existed in `INGEST_TAGS_US_GAAP`. Enabling either flag against that store
renders nothing, and nothing is indistinguishable at the sheet from "this filer
discloses none".

So, in order: promote, **re-run `backend/scripts/ingest_edgar_facts.py --force`**
(without `--force` it skips every ticker that already has facts, which is all
150 of them), then enable. `edgar_debt_structure_tags_not_ingested` is the warn
that fires if that order is not followed — the CR040 loud-degrade this CR owes
DEF038/DEF063.

The local measurement store is deliberately **not** the solo-dev `.local.db`.
That file is stamped at an alembic revision it never actually migrated to, so
hand-creating `edgar_facts` in it would rebuild DEF215's exact failure —
a table Alembic has no record of, and the next `upgrade head` dying on
`DuplicateTable` while later ALTERs that running code depends on never run.
`measurement/edgar.db` is a fresh, gitignored, three-ticker store instead.

### 7.6d The negative control has to change, and this is recorded BEFORE the run

§7's design names **H2** (Fed-path rate-cut probability) as the negative control: the one item
with no free source, nothing built, so its ask must not fall. Round 1's first four convenes say
that control carries no information. H2 was asked **0 times in all three arms** of the short
mandate and once in the long pilot — an item asked 0–1 times per convene cannot show a fall,
so "H2 did not fall" would be true of a coin.

**The control is therefore D1 + A2** — revenue by business segment, and the industrial vs.
captive-finance debt split. Nothing is built for either; both are on this CR's own open list;
and unlike H2 they are asked constantly (D1 alone: 6 asks in one 12-agent convene). A control
needs a rate high enough that a fall would be visible, and these have it.

This is written down before round 1 finished on purpose. Swapping a control after seeing which
one moved is how a null becomes a finding, and §7.1 exists to stop exactly that.

H2 stays in the report as an observation — it is still the one item with no free source — but
it is no longer load-bearing.

### 7.7 What "how much difference it makes" will be reported as

One table, per item: baseline asks → post-build asks → citation rate → whether it appeared in
reasoning. Plus the cost delta and the recorded-only verdict distribution. The conclusion is
allowed to be **"less than we expected"** — a null on a field is a finding about that field,
and the negative control is there to make a null readable rather than deniable.

### 7.8 ROUND 1 RESULT — the primary endpoint failed, and the secondary one is decisive

Nine clean convenes: `off` / `debt` / `cash` × short / medium / long, CAT, one profile pickle
throughout, control arm a flag flip. Stamps `20260903T123617Z`, `20260903T175205Z`,
`20260903T180639Z`. Reproduce with:

```
replay.py --score-only 20260903T123617Z 20260903T175205Z 20260903T180639Z
citations.py --stamp 20260903T123617Z 20260903T175205Z 20260903T180639Z
outcomes.py  --stamp 20260903T123617Z 20260903T175205Z 20260903T180639Z
```

#### The primary endpoint is dead at this n, and the negative control is what killed it

| | off | debt | cash | |
|---|---|---|---|---|
| **TOTAL data named** | 54 | 56 | 50 | every datum, register-matched or not |
| A1 maturity ladder | 1 | **0** | 0 | shipped in `debt` |
| A3 cost of debt | 0 | 0 | 0 | shipped in `debt` — never asked at all in round 1 |
| C3 cash-flow bridge | 3 | 1 | **0** | shipped in `cash` |
| C4 working capital | 0 | 1 | **0** | shipped in `cash` |
| **D1 segment revenue** | 10 | 6 | 4 | **negative control — nothing built** |
| **A2 captive split** | 7 | 0 | 2 | **negative control — nothing built** |

Every shipped item ends at zero in its own arm. That reads like a clean result and it is not one:
**the negative control fell further than any treatment.** D1+A2 go 17 → 6 → 6 across arms where
nothing about segment or captive-finance data changed, a 65% fall in an item that was predicted
flat. A treated item falling 3 → 0 cannot be attributed to its treatment when the untreated
control falls 17 → 6 beside it.

§7.6d swapped the control from H2 to D1+A2 *before* this run finished, precisely so the null
would be readable instead of deniable. It is readable. The primary endpoint reports **no
measurable demand extinction**.

#### Why it failed — the addendum is rank-limited, not count-limited

The totals are the tell: **54 / 56 / 50**, flat, while individual items swing by 7. The Room does
not name every gap it has; each agent names its top few, so the addendum is a ranked shortlist
with a roughly fixed length. Fill one gap and the next one moves up into the slot — the count
stays, the composition changes. Per-item ask counts are therefore a **zero-sum reallocation**,
not a census of what is missing, and differencing them across arms measures re-ranking rather
than satisfaction.

This retroactively justifies §1's own framing. CR219's 127 lines were always "how loud is the
demand", never "how much data is missing" — that is why this CR deduplicated to 49 items in the
first place. Round 1 shows the same limit applies to the *differences* between two runs of the
instrument, not only to its absolute counts.

A second, cheaper reason compounds it. Round 1 is 3 mandates; the banked corpus is 7 convenes
across 6 mandate arms plus a full live convene. Per-item baselines in the `off` arm are 0–3
asks, against register line-counts of 14 (A1) and 5 (A3). **A3 was asked zero times in all nine
convenes**, so the one item whose sourcing verdict this build overturned has no baseline to fall
from. An endpoint that needs a fall needs a baseline, and at 3 mandates most items do not have one.

#### The secondary endpoint separates cleanly — and DEF400 is the result

| item | arm | cited / 36 turns | cited / agents that asked for it |
|---|---|---|---|
| A1 maturity ladder | debt | 1 | **1 / 6** |
| A3 cost of debt | debt | 2 | **0 / 4** (cited, but by agents that never asked) |
| C3 cash-flow bridge | cash | 7 | **5 / 6** |
| C4 working capital | cash | 0 | **0 / 2** |

**DEF400 — the same figure, before and after the fix:**

| figure | off | debt | cash |
|---|---|---|---|
| stale `$5,049M` / `200% of FCF` | 5 of 12 agents | 5 of 12 | **0 of 12** |
| filed `$8,994M` / `112% of FCF` | 0 of 12 | 0 of 12 | **7 of 12** |

Zero overlap in either direction, across 108 turns. Five of twelve agents argued from a wrong
free-cash-flow number in both untreated arms; none did in the treated arm, and *more* agents
picked up the correct figure than had picked up the wrong one. This is the one endpoint in the
whole design that produced perfect separation, and it is not about a new field — it is about a
field that was already shipped and wrong.

What that wrongness was doing, verbatim from the two untreated arms — `off` and `debt`, both of
which carry the stale figure: `HEADLINE: Capital returned at 200% of TTM FCF` (short/off,
long/off, medium/debt), `$5,049M TTM FCF is structurally unsustainable without further debt`
(short/off), `Capital Destruction via Debt` and `a structural deficit, not a surplus`
(medium/debt). It reached the verdict — the
medium/`off` PM wrote *"I raised the size from 2.5% to 2.75% … but capped below the 3.0% hard
limit due to the 200% capital-return-to-FCF ratio."* In the `cash` arm the same agents write
`HEADLINE: Capital return 112% of FCF` — still worth saying, no longer an alarm.

#### Recorded, not attributed — and the cost

| arm | convenes | prompt tok | out tok | vs off | verdicts |
|---|---|---|---|---|---|
| off | 3 | 152,593 | 11,247 | +0.0% | APPROVE 2, PASS 1 |
| debt | 3 | 162,098 | 12,564 | **+6.2%** | APPROVE 2, PASS 1 |
| cash | 3 | 163,944 | 11,918 | **+7.4%** | PASS 2, APPROVE 1 |

Verdicts behave exactly as §7.1 predicted and are reported for the record only. The three arms
produce 2/1, 2/1 and 1/2 APPROVE/PASS, and the internal approve-vote counts swing 0/5 to 5/5
within a single arm. One of the three PASSes is an unrelated 4% position-size compliance block.
Nothing here is attributable to a data field at n=3.

#### How much difference it makes — the answer

1. **Demand: none measurable.** The instrument reallocates asks rather than extinguishing them,
   and the negative control moved more than every treatment combined. This endpoint should not
   be re-run at this n; it needs either many more convenes or a different instrument.
2. **Correctness: decisive.** DEF400 removes a false alarm from 5 of 12 agents with 100%
   separation, on a field the Room was already using to size positions.
3. **Use: one of four lines landed.** C3 reached 5 of its 6 askers. A1 reached 1 of 6, A3 reached
   0 of 4 while being cited twice by agents that never asked, C4 reached 0 of 2.
4. **Cost: +6–7% prompt tokens** per convene, output flat.

**Ship recommendation, in flag order.** `fundamentals_fcf_from_statements_enabled` (DEF400) and
`room_cashflow_bridge_enabled` (C3/C4) are earned by this measurement — one fixes a wrong number,
the other is read by the agents that wanted it and carries the clause explaining the substitution.
A1 and A3 are correct, cheap and under-used *at this n*; their case rests on the banked corpus
(14 lines / 6 agents and 5 lines / 4 agents) which round 1 is too small to confirm or refute, so
they ship with that stated rather than on evidence they do not have. C2/C5/B2 are unmeasured —
round 2 has not run, and it needs a rebuilt profile pickle since the current one predates those
keys.

### 7.9 ROUND 2 — the history arm, and a second confirmation that the endpoint is blind

Six convenes, `off` vs `history` × short/medium/long, stamp `20260903T191926Z`, on a rebuilt CAT
pickle carrying the C2/C5/B2 keys the round-1 pickle predates (**107 LIVE fields vs 100**). Round
1's pickle is moved aside rather than deleted, so its exact sheet stays recoverable.

| | off | history |
|---|---|---|
| **TOTAL data named** | 55 | 54 |
| **C2** multi-year FCF/capex averages | — | — |
| **C5** FCF conversion history | — | — |
| **B2** cycle ROE + median | — | — |
| D1 segment revenue *(control)* | 2 | 2 |
| A2 captive split *(control)* | 6 | 8 |
| B3 peer-basket multiples | 5 | 1 |
| F10 ATR(14) | 5 | 3 |
| J1 raw social split | 5 | 4 |

**All three items this arm ships are absent from the scored table entirely — zero asks in both
arms.** They have no baseline to fall from, which is the same shape as A3 in round 1. Two rounds
now agree independently: at three mandates on one ticker, most register items are simply not
asked for often enough to support a difference. The control behaved this time (D1 2/2, A2 6/8),
and it did not rescue the endpoint — B3 still swung 5 → 1 on an untreated item, so the noise
floor is intact even when the control happens to sit still.

Round 2 therefore confirms §7.8's conclusion rather than extending it. **The demand-extinction
endpoint is retired.** It should not be re-run for a third arm at this n.

#### What round 2 actually produced was a defect in the arm it was testing

The measurement's value came from reading what it *rendered*, not from its endpoint. Extracting
the history arm's three lines off the banked sheet showed:

```
Return on equity history (LIVE): FY2025 41.7% · … , 4-year median 47.6%,
currently 57%, net income over year-end equity
```

`currently 57%` sitting beside `FY2025 41.7%` under a closing clause naming *one* basis. Round
1's render of the same fiscal data four hours earlier read `currently 41.7%`, which is what made
it visible. Measured at one instant on CAT: the series' FY2025 is 41.7% (filed net income
$8,884M over year-end equity $21,318M) and `.info`'s `returnOnEquity` is 57.0%, off vendor TTM
income $10,844M — **a 22% gap in the numerator alone, 15.3 points in the ratio**. The line was
applying a basis it had computed to a number it had not: DEF400's shape on a second field, in
the very line whose docstring claimed to prevent "two ratios sharing a name".

It survived its own test suite because the fixture passed `41.7` as both the newest FY and the
current figure, so the divergent case never ran — the same fixture-shaped blindness the parity
guard's docstring warns about. Fixed in `9da0be32`: the current figure is carried only with its
divergence named, exactly as `cashflow_bridge_line` carries the vendor FCF it cannot reconcile,
and the basis clause now reads "each year …" so it describes only the series. Two tests added,
one on the measured 57.0 case and one at 43.2 pinning that 1.5 points still reads as agreement.

**Caught before the flag was ever enabled, so nothing shipped wrong** — but the sequence is worth
recording, because it is the third time in this CR that rendering a field on live data found
something no unit test could: DEF399 (interest coverage 31.8× against a real ~6×), DEF400 (the
vendor FCF), and now B2. The measurement rig earns its keep as a *renderer*, whatever its
endpoint does.

---

## 7.12 Slot 5 — C8 dividend growth, C7 implied buyback price

Two items, both decisions that needed no new network: C8 rides the `DividendPayment` history
CR206 already fetches (decision 9, IN HAND), and C7 is a quotient of R35's repurchase dollars
over one new tag (decision 8, REACHABLE).

### C8 — the basis is the declared rate, not the calendar-year sum

The obvious implementation sums each calendar year's payments and takes the CAGR of the sums.
Measured on Realty Income, that implementation prints a dividend cut the company never made.
O pays monthly; its May 2024 ex-date slipped to 2024-06-03, so eleven ex-dates land in 2024 and
thirteen in 2025. The calendar sums run 3.062 → 2.872 → 3.490 while the declared rate rose every
single month. A sum basis reads 5.90% CAGR against the rate basis's true 2.25%, and an analyst
reading the sheet would see a monthly payer that cut and then surged.

So the series carries the **last declared rate of each year**, with the calendar sums beside it
and the payment count per year stated, because an uneven cadence is information rather than noise
to smooth away.

Three further structural rules, each from a measured case:

| Rule | The case that produced it |
|---|---|
| Specials excluded from both bases and named | Costco's $15.00 of 2023-12-27. A naive sum reads 18.96 for 2023 and prints a 79% collapse in 2024 |
| A genuine step-up is a raise, not a special | GE's rate went 0.0638 → 0.28 in 2024, a 4.4× move that the special filter must not eat |
| The window truncates at a gap and says so | Disney paid nothing in 2020, 2021 and 2022; a five-year window would bridge the suspension and call the recovery steady growth |
| The partial current year is never in the series | 2026 is excluded and the line says it was |

### C7 — pairing is not enough, the window must be contiguous

The live probe found a defect in my own first implementation, and it is the finding worth
recording from this slot. CAT's `companyfacts` on 2026-09-11 carries 26 discrete quarters on the
dollar tag and 47 on the share tag, but the newest four they **both** carry are Q1 of 2023, 2024,
2025 and 2026 — the same calendar quarter four years running. Summing them gives $13,543M over
26.1M shares and a **$518.82 "trailing-twelve-month" average price spanning three and a quarter
years**. That is `edgar_pit.ttm()`'s documented hazard arriving through a second series: a hole in
the middle, summed as though contiguous.

My first window check counted quarters and did not require them to abut. Fixed with a contiguity
guard and a 330-to-400-day span guard. CAT then resolves $664.64 over 2025-07-01..2026-06-30,
which sits inside CAT's own close range for that year (low $386.02, high $1,062.93, mean $632.74).
**CAT is an absent state today, not a number** — and that is the correct answer, because the four
shared quarters are not a year.

Deere tags no share count at all (CR221 §4b: CAT n=197 points, Deere none), so the absent state is
the common outcome rather than an error.

### What mutation-proofing found, and it was not nothing

Ten mutations, and the first sweep killed only seven. The three survivors were a real gap in the
tests, not a scoring artefact, and two of them hid behind a later guard:

| Mutation | Why it first survived |
|---|---|
| Drop the contiguity guard | The measured Q1×4 case spans 1,185 days, so the **span** guard caught it anyway. No test had a case where contiguity was the only check that could fire |
| Drop the one-year span guard | The only bad-span case was that same Q1×4 window, which contiguity caught first. Each guard was shadowed by the other |
| Weaken the share floor to `shares > 0` | The residual case divided $7.2bn by 40 shares and got $180.6M per share, which `MAX_PRICE` refused. The floor was never the deciding check |

Three tests were added, each constructed so **only** the target guard can fire: a one-month hole
inside a 395-day span (contiguity alone), four contiguous 71-day periods spanning 287 days (span
alone), and 999 shares against $1.5M for a plausible-looking $1,501.50 per share that only the
floor rejects.

Writing them turned up two more facts about the upstream filter. `quarterly_series` keeps only
periods of 70 to 100 days, so:

- A first draft of the span test used half-year periods. They never reach the resolver at all —
  the series came back empty and the test passed for the wrong reason, exactly like the test it
  replaced. A first draft of the pairing test shifted a period to 58 days, with the same result.
- Four contiguous periods that pass the filter span between about **256 and 418 days**, so both
  ends of the year check are reachable and neither is decoration.
- Three contiguous periods span at most **314 days**, and the span guard requires 330. So
  `len(paired) < 4` relaxed to `< 3` changes no outcome: it is **provably equivalent**, and the
  one surviving mutation is unreachable by construction rather than untested. The check is kept
  because its log message names the condition the span message would not, and the test records the
  arithmetic so a future change to the upstream filter re-opens the question loudly.

Two more mutations were then added for the render itself, and they caught a live flaw the whole
suite had missed. The line formatted amounts with `:,.4g`, which drops trailing zeros: CAT's $1.20
declared rate printed as **"$1.2"** and its $5.00 annual total as **"$5"**. On a dividend series
that reads as a different figure, and twenty-three passing tests had nothing to say about it
because not one looked at the digits. Plain two decimals is wrong the other way — GE's $0.0498
rate rounds away to $0.05, losing the precision the 4.4× raise is measured on. Fixed with a
`_money` helper: cents above a dime, four decimals below it, both shapes pinned by a test and both
directions mutation-killed.

Final sweep: **eleven of twelve mutations killed, each by the test named for it; the twelfth proved
equivalent.**

Two lessons, and the second is a near-miss rather than a finding:

1. **A guard behind another guard is untested by default.** A sweep that counts survivors without
   asking *which test should have died* will not tell you that, and neither will a green suite.
   This is the §7.11 lesson arriving a second time in the same CR.
2. **I read the sweep's result through `tail -12` and concluded every mutation had died** — the
   pipe reported the tail's exit 0 and the script's `sys.exit(1)` never reached me. That is
   DEF405's exact shape, committed by the person who wrote up DEF405, on the gate he built to
   check his own work. Re-run bare, the sweep still reported one survivor. The rule generalises
   past `preflight_suite.sh`: **read the exit code of the thing that computed the verdict, not of
   whatever printed it.**

### Deployment prerequisite, run — and running it overturned the C7 case study

`room_buyback_price_enabled` renders nothing until `ingest_edgar_facts.py --force` has run once
for the new `TreasuryStockSharesAcquired` tag, because the tag is new to `INGEST_TAGS_US_GAAP` in
this slot and no existing row carries it. Run against the measurement store on 2026-09-11: 156
facts inserted, 3,681 deduped, all 156 of them the new tag.

**With a complete ingest, the CAT case above does not reproduce.** The two tags share 55
quarters, and the newest six run consecutively:

| Quarter | Dollars | Shares | Implied |
|---|---|---|---|
| 2025-01-01..2025-03-31 | $3,660M | 7,515,281 | $487.01 |
| 2025-04-01..2025-06-30 | $828M | 2,666,175 | $310.56 |
| 2025-07-01..2025-09-30 | $362M | 847,999 | $426.89 |
| 2025-10-01..2025-12-31 | $340M | 3,048,960 | $111.51 |
| 2026-01-01..2026-03-31 | $5,028M | 5,557,798 | $904.67 |
| 2026-04-01..2026-06-30 | $1,494M | 1,414,325 | $1,056.33 |

C7 resolves to **$664.64 over 2025-07-01..2026-06-30**, which is the figure the unit tests
predicted from the same inputs, so the fixtures are corroborated. But **"the newest four shared
quarters are Q1 of 2023, 2024, 2025 and 2026" was an artefact of an incomplete ingest, not a
property of CAT's filings.** The store I first probed held **zero** rows for the share tag; the
sparse Q1-only pattern came from that emptiness, not from EDGAR. The §7.12 narrative above is left
as written because it is what I believed at build time, and this paragraph is the correction
rather than a rewrite of the record.

**What survives the correction, and what does not:**

- **The guards stand.** Contiguity and span are still the difference between a trailing-year
  quotient and a multi-year total labelled as one, and `ttm()` documents that hazard
  independently of CAT. They are simply no longer justified by *this* case.
- **The absent state is real, and better attested than before.** Microsoft carries **72 dollar
  quarters and zero share quarters** in the same store, so C7 is correctly absent there; Deere and
  Exxon carry too little to resolve at all. That is the DEF399 shape the unpaired-legs guard
  exists for, measured on real filings.
- **A new finding the correction produced: the per-quarter implied prices are not usable.** The
  spread runs $111.51 to $1,056.33 in a year CAT traded $386.02 to $1,062.93. The differencing is
  arithmetically correct — the two tags' year-to-date points are simply not synchronised
  quarter by quarter — and it averages out over four: FY2025 whole-year reads $368.65 and H1 2026
  reads $935.44, both plausible against the price path. **So the four-quarter aggregate is the
  only honest granularity for this item, and rendering a per-quarter implied price would be
  wrong.** The line renders the aggregate only, which is what it already did, now for a measured
  reason rather than a design guess.
- **A process lesson, and it is the same one twice in one slot.** §7.12's guards were justified by
  a case produced by a store I had not verified was populated. I checked the *shape* of what came
  back and not whether the source had any rows at all. The DEF405 note above says to read the exit
  code of what computed the verdict; this says to check that the input existed before believing
  what the output implies.

Both flags remain False by default and compose-forwarded. Nothing is enabled.


## 7.13 The register could not see its own build

Asked how much of CR221 was still outstanding, I answered from my own lane and said two things.
That was wrong, and checking it properly found a defect in the instrument the CR uses to answer
that exact question.

`evidence/items.py` is the register: 49 items, the script that claims each of the 127 request
lines for one of them, and the totals §2 quotes. It reported **35 open**. The true figure was 22.
Thirteen items had a producer service, a line helper, a flag-gated render and an overlay, all
merged to main — and the register called every one of them `open`, the same word it uses for an
item with no code at all.

**The cause was a missing state, not thirteen missed edits.** The register had three: `delivered`
meaning on the sheet today, `closed`, and `open`. Everything CR221 actually built landed in none
of them. A producer behind a flag that defaults False is not on the sheet, so it is not delivered;
its code exists, so `open` states something false. With nowhere correct to put them, slots 1
through 5 left thirteen items where they started.

**And the guard could not notice, because it was checking itself.** The script asserted
`actual == EXPECTED` where `EXPECTED` was a hardcoded dict and `actual` was recomputed from the
same hardcoded list in the same file. It agreed with itself on every run and exited 0 throughout.
Worse than useless: correcting a single status without also editing the dict would have made the
script fail, so the check actively held the drift in place.

### The fix, and what makes it a guard

A fourth state `BUILT` (`◐` dark), carrying the name of the Settings flag that gates its render,
and a check that reads `backend/app/core/config.py`:

- every dark item must name a flag that exists in that file;
- a dark item naming no flag fails — the flag is the evidence for the claim;
- an open item naming a flag fails — `open` now means no code exists.

That turns a self-referential comparison into a claim about the code, which is the property the
old check lacked. Verified by three mutations rather than by reading it:

| Mutation | Result |
|---|---|
| Rename A1's flag to one not in `config.py` | exit 1, names A1 and the missing flag |
| Strip A1's flag while leaving it dark | exit 1, "BUILT means 'merged behind a flag', so the flag is the evidence" |
| Give open item F1 a flag | exit 1, "only BUILT items carry one" |

The register now reports **9 delivered · 13 dark · 5 closed · 22 open**, and eleven stale `○`
rows in §2 plus the §3 cross-check row for A2 were corrected to match.

### Why it mattered beyond bookkeeping

Three reasons this was worth stopping for.

1. **A2 was among the thirteen.** At 18 request lines from 9 agents it is the register's single
   largest item, and the register said it was unbuilt while its code sat on main behind an off
   flag.
2. **§7 selects its next arm from this field.** A flag flip and a sprint of build work are
   different sizes of job, and `open` could not tell them apart, so the measurement plan was
   reading from a field that could not answer its question.
3. **It is the third instance of one shape in this CR.** §7.11 found a guard hiding behind another
   guard. §7.12 found three mutations surviving because each guard was shadowed by a later one,
   and separately found that I had read a sweep's verdict through `tail -12` and taken the pipe's
   exit 0 for the script's. Now a guard that validated its own constant. **Every one is a check
   that appeared to pass while testing nothing**, and in each case the green result was what
   delayed finding it. The common repair is the same: make the check assert against something it
   does not itself produce.

The failure-patterns register (`docs/initial_specs/08_tech/failure_patterns.md`) treats a second
occurrence as requiring an entry with an enforcing check, and a third as a Dilemma rather than
another point fix (CR185). Three instances of *self-validating check* inside one CR meets that
bar, and it is recorded here for whoever reads this CR next; filing it is a governance call, not
one to make silently inside a measurement section.

---

## 8. Scope

**In scope**

1. The 49-item register, reproducible and self-asserting (`evidence/items.py`), over the
   127-line corpus (`evidence/inventory.py`).
2. The §3 cross-check — every item against every CR219 field, on the regenerated sheet.
3. A **free, reliable** source per open item (§4), each verified against the live source or
   explicitly marked unverified.
4. A one-page design note per sourcing decision that a follow-on CR would build, in this
   folder, on the R38 template (endpoint, rate limits, cache strategy, failure mode) — *before*
   any code.
5. The §6 correction, reported to the WP10 lane with its repro.
6. The ranked build order, with its inputs shown.
7. **The build itself** — the fetch/derive/cache layer for every sourced item, each behind its
   own config flag (§7.5 makes this a hard constraint, not a preference), landed on WP06's
   existing per-field rules.
8. **The §7 re-run and its conclusion** — CR219's convenes replayed against the enriched
   profile, scored per item, with the cost delta and the negative control reported.
9. **R38's re-route**, inheriting `WP10_R38_parked/`.

**Out of scope**

- **Shipping any fact-sheet field.** Every field is a follow-on CR under WP06's existing rules
  (CR104 provenance, guard entry in the same commit, persona `## Inputs` in the same commit,
  compose parity, one field per commit).
- **Any prompt or persona edit**, including the declared-absence lines §4f recommends.
- **Paid providers.** None is proposed, and the one item without a free source (H2) is left
  open rather than solved by spending.
- **The two non-data items** — the Decision Journal (already wired) and the cooldown-scope
  clarification (a CR219 instruction-collision item).
- **Re-running the arms.** The corpus is banked and sufficient; a post-fix re-measurement is
  CR219 R30's trailing question, not this one's.

---

## 9. Acceptance

1. `evidence/items.py` runs from any working directory, prints 49 items, and **exits non-zero**
   if any of the 127 lines claims no item, if the register's totals drift from §2, or if the
   register has drifted from the CODE — every `◐` dark item must name a Settings flag that
   exists in `backend/app/core/config.py`, and no `○` open item may name one. Verified by
   three mutations: a renamed flag, a dark item with no flag, and an open item carrying one;
   each exits 1 with the item named.
2. `evidence/inventory.py` still prints all 127 lines by agent, from any working directory.
3. `evidence/edgar_census.py` exits 0 and prints the fact-point-key census for two filers.
4. Every §3 row names a commit SHA and a sheet line, or states the absence.
5. Every open item in §2 appears in exactly one §4 subsection, and every §4a–§4d verdict names
   the file, function or endpoint that serves it. Anything unverified says so in the row.
6. The §6 finding is delivered to the WP10 lane and the routing decision is recorded here with
   its date.
7. A design note exists per sourcing decision before its follow-on CR opens.
8. H2 is either sourced from melehost or recorded as a declared absence — not left ambiguous.
9. **Every shipped field is behind its own config flag, defaulting off, forwarded in
   `docker-compose.yml`'s `api-alpha` block** (`test_config_compose_parity.py` enforces). A
   field that cannot be switched off cannot be the treatment arm of §7's A/B.
10. **The §7 re-run is executed and reported**: per-item baseline asks → post-build asks,
    citation rate per new line, reasoning-trace presence, cost delta, and the recorded-only
    verdict distribution labelled with its n and the 19.7% flip figure. H2's demand is reported
    as the negative control.
11. The §7.6 taxonomy collision is raised with the R53 lane, and the outcome recorded here.

---

## Related

- [`../CR219_room_prompt_contradictions/`](../CR219_room_prompt_contradictions/CR219_room_prompt_contradictions.md)
  — the parent: the demand corpus, the arms, and WP06's six shipped fields.
- `../CR219_room_prompt_contradictions/dev_instructions/WP06_data_additions.md` — the rules
  every follow-on field commit inherits.
- `../CR219_room_prompt_contradictions/dev_instructions/R38_edgar_design_note.md` — the note §6
  corrects, and the template §8.4 reuses.
- [`../CR218_capital_return_field/`](../CR218_capital_return_field/) — the "precompute it" precedent.
- [`../CR164_room_backtest/`](../CR164_room_backtest/) — the EDGAR companyfacts ingest this CR
  extends by five tags.
- `../CR172_options_simulation/` — where `OptionQuote.implied_vol` and `open_interest` are already fetched.
- `../CR206_dividend_feed_for_early_assignment/` — where `DividendPayment` is already fetched.

### 7.10 ROUND 3 — the dims arm: the split is answered, and the demand moves one step downstream

**Run.** Stamp `20260910T164026Z`, 2026-09-10 16:40–17:30Z, from the Mac against vLLM over
Tailscale (`100.79.86.15:8048`, `/v1/models` root `qwen38-flash-next-nvfp4`). CAT, two arms
(`off`, `dims` = A2 + D1 + D2 rendered), three mandates (short, medium, long): 6 convenes,
36 turns per arm. Profile rebuilt for this round (110 LIVE fields) from the Mac's sqlite
EDGAR store, the three lines read from rows the slot-4 ingest wrote there; each arm forces
every other flag False. Negative control H2, recorded before the run (§7.6d). Six result
files under `measurement/results/`, scored with `replay.py --score-only`, `citations.py`,
`outcomes.py` — the numbers below are those scripts' output, not a reading of the transcripts.

**Primary endpoint — `DATA I LACKED:` counts.**

| mandate | total off | total dims | A2 off | A2 dims | D1 / D2 / H2 |
|---|---|---|---|---|---|
| short | 12 | 18 | 3 | 1 | 0 / 0 / 0 in both arms |
| medium | 11 | 18 | 0 | 5 | 0 / 0 / 0 |
| long | 9 | 15 | 0 | 0 | 0 / 0 / 0 |
| **all** | **32** | **51** | **3** | **6** | — |

Read literally, the arm that ships the debt split is asked for it twice as often. Read the
lines, and it is not so. The three `off` asks are for the split itself (Fundamentals,
Conservative, Neutral — all short mandate: *"a breakout of CAT's $39,201M net debt between
industrial debt and Captive Finance debt"*). None of the six `dims` matches asks for the split.
One (Bear, short) asks for the *cash-flow* split by arm. Five (Bull, Bear, Research Manager,
Trader, Neutral — medium) ask for the same new thing: *"Caterpillar Financial Services' net
interest margin trend over the last 4 quarters"*, *"interest expense breakdown or yield on debt
issued for the captive finance arm"*. The A2 regex claims them because they name the finance
arm. So: **the split ask is extinct in the arm that carries it, and its successor is the
finance arm's funding cost** — one step downstream of the figure that was supplied.

The totals rising 32 → 51 is the third sighting of the rounds-1/2 finding: the endpoint is
rank-limited. Supply a datum and the agents name the next one; the count does not fall, it
refills. This round adds the mechanism — the refill is not random, it is the *adjacent*
datum (split → cost of the split's larger half).

**Secondary endpoint — citation of the shipped figure** (`citations.py`, markers widened to
the `$32.6B` / `$10.7B` forms agents actually write):

| item | cited / 36 turns | cited / corpus askers | the shape it took |
|---|---|---|---|
| A2 debt split | 8 | **8 of 9** | Bull: *"the $32.6B captive finance debt is funded lending, not distress"*; Fundamentals: *"industrial debt is $10.7B, manageable against $5.0B FCF"*; Bear/Conservative (medium): *"$32.6B captive debt exposure is unquantified without NIM data"* |
| D1 segments | 2 | 1 of 4 | named, not argued from |
| D2 geography | 0 | 0 of 1 | never used |

Eight of the nine agents who had asked for the split in the banked corpus used it once it
was there, and used it both ways — the Bull to dismiss the blended leverage, the Bear to
locate the rate risk in the finance arm. That is the figure doing what a figure should. The
geography line, asked for once in 127 lines, was read by nobody.

**Outcomes and cost** (`outcomes.py`): PASS in all six cells; PM agreement 5/5 in five cells,
3/5 in medium/dims (two of five samples approved). Prompt tokens `dims` 153,937 vs `off`
156,352 (−1.5%) — three sheet lines cost nothing measurable; the difference is turn-length
noise, as in rounds 1 and 2.

**What this supports.** Turning `room_debt_split_enabled` on is supported on every axis this
rig measures: the ask disappears, 8 of 9 askers cite it, the verdict does not move, the cost
does not move. `room_segment_revenue_enabled` is weakly supported (one of four askers).
`room_geographic_revenue_enabled` is not supported by this round (never cited) and should stay
OFF until a ticker whose story *is* geographic (a China-exposed name, say) is measured. The
flips are Saiful's call; none is made here.

**Candidate item — measured the same night.** The successor ask — the captive arm's interest
expense and net interest margin by quarter, five asks in one convene — is **A6**, probed on
four captive filers' latest 10-K and 10-Q instances (§4b, A6 row): the funding-cost side is
feasible for CAT, F and PCAR and partial for DE (no captive-side debt tagged); the NIM side is
not sourceable for CAT, DE or F, because none files an interest-income concept for the arm.
Not built; not in the §1 totals, which count the original 127-line census.

**One line for another lane.** In both arms the FCF figure agents cite is the vendor
`$5,049M` / `200% of FCF` (5 of 12 agents in `off`); the filed `$8,994M` / `112%` sits on the
same profile and is cited by none. That is DEF400's sheet-rendering question, noted here
because the rig saw it, and left to that lane.


### 7.11 ROUND 4 — the exec arm: the item nobody asked for, and every asker cited

`20260910T191437Z` · CAT × {short, medium, long} × {`off`, `exec`} · 6 convenes, 36 analyst turns
· `/models/qwen38-flash-next-nvfp4`, `thinking=False`, `pm_samples=5` · profile rebuilt at run
start (`profile_CAT.round4.pkl`, 111 LIVE fields both arms) · code measured: `d6c364c2` (main),
the third review round's fixes included.

**The render seam, checked before the numbers.** The sheet line appears in the `exec` arm only —
`off` carries zero `Executive change` sheet lines and `exec` carries one; the persona sentence
that tells the News Analyst how to read the line is in both prompts by design, so a naive grep
for the label finds it twice and means nothing. The flag bought **1,975 prompt characters**.

**Primary endpoint: I1 was never asked for, in either arm, in any mandate.** Not in round 4, and
not in rounds 2 or 3 either — `I1` appears in no convene's request scoring at any stamp. The
demand-extinction table cannot move an item that is never demanded, so on the primary endpoint
this build scores **nothing at all**:

| | `off` | `exec` |
|---|---|---|
| I1 executive-change detail — asks | 0 | 0 |
| Total data items named | 48 | 48 |

This is the §7.1 endpoint failure in its purest form yet. The 127-line census recorded the News
Analyst asking for executive-change detail in **5 of 7 convenes** — that is why I1 was built. The
rank-limited endpoint (§7.9) is why it now asks for nothing: with the CFO change *answered on the
sheet*, the analyst's five scarcest asks are simply five other things, and the register-matched
count stays flat at 48 because the demand redistributes rather than shrinking.

**Secondary endpoint: 1 of 1 askers cited it, in all three mandates, quoting the filing.** The
one agent the line is for used it every single time:

| item | arm | cited/turns | cited/askers | askers |
|---|---|---|---|---|
| I1 | `exec` | 1/36 | **1 / 1** | `news_analyst` |

Verbatim, and precise — the names, both dates, the filing's own date, the item code:

- *short*: “The 8-K filing dated **2026-04-10** confirms **Kyle Epley** assumed the **CFO** role
  effective **2026-05-01**, succeeding **Andrew R.J. Bonfield** (retiring **2026-10-01**).” …
  “No new Item 5.02 filings have appeared since **2026-04-10**.”
- *medium*: “The **8-K filed 2026-04-10** (153 days old) confirms CFO transition to **Kyle
  Epley** … replacing **Andrew R.J. Bonfield**. This is settled.”
- *long*: “The 8-K … is 153 days old and **likely absorbed into the reference price** of
  $802.47.”

Three things in that are worth more than the citation rate. The analyst read the **age** the line
states and did something with it — “153 days old”, “settled”, “absorbed into the reference price”
— which is the gap sentence the second review round argued for, working as intended. It read the
**absence** correctly too (“no new Item 5.02 filings since”), which is the `none_in_window` half
of the state machine. And the fact **propagated**: in the short mandate the Bull Researcher cited
it second-hand (“the Macro & Events analyst confirmed that the CFO transition is a closed event”),
so one sheet line reached an agent that never saw it.

**Cost and verdicts.** The arm costs **+7.9%** prompt tokens (155,407 → 167,713 over 3 convenes)
for 1,975 characters of filing text. Verdicts move in both directions and are **not attributed**
(§7.1: 19.7% split on identical inputs) — `short` PASS→APPROVE, `long` APPROVE→PASS, `medium`
PASS→PASS. Three convenes per arm cannot separate a 2-in-6 flip from noise, and this round makes
no claim that it does.

**What this supports.** `room_executive_change_enabled` is supported on the axis that has proven
decisive four rounds running — the agent it is built for cites it, quotes it accurately, respects
its stated age, and passes it on — and unsupported on the axis this rig has now shown blind four
times. At +7.9% for one ticker's one filing, the honest reading is that the line earns its place
for a name with a real 5.02 event and costs 7.9% for nothing on a name without one, which is
exactly what the `none_in_window`/`unscanned` states are for. The flip is Saiful's call, and it
needs the in-container ingest first (§7.6c): the flag turns on nothing without scan rows.

**A fourth confirmation, and a recommendation about the endpoint itself.** Four rounds, four
builds, four times the primary endpoint said nothing and the secondary endpoint said everything.
Rounds 1–3 could be read as "the endpoint is noisy"; round 4 removes that reading, because here
the demand for the built item was **exactly zero in both arms** — there was never a number to
move. The rank-limited "five things I lacked" ask is not a demand *measure*; it is a demand
*sample*, and a sample of size five from a distribution of 36 open items cannot see a single
item's satisfaction. §7.2's primary endpoint should be retired in favour of §7.3's citation rate
for any future slot, and the register's per-item line counts should be read as *what the Room
asked once*, never as *what the Room needs*.
