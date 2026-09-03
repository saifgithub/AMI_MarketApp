# CR221 — Sourcing the Room's measured data demand

**Status:** in_progress · **Owner:** coder.api · **Filed:** 2026-09-03 · **Tag:** `(AT:R75 CR221)`

**Done at filing:** §1–§6 — the item register, the cross-check against CR219, a *verified free*
source for every open item but one, and the §6 measurement. **Open:** the design notes (§7
item 4), the §6 routing decision with the WP10 lane, and the one item (H2) with no free source
yet found.

---

## What

CR219 asked twelve agents, on every turn, to name the data they lacked. They answered **127
times**, and those 127 asks are **49 distinct data items**. Nine are already delivered, four
are closed, **36 are open**.

This CR takes those 36 and finds each one a source that is **free and reliable**. It does not
ship fact-sheet fields — every field is a follow-on CR. What was missing was not build
capacity; it was an answer to *"where does that number come from, does that source exist, and
what does it cost us?"* — asked once for all of it instead of one field at a time.

**The headline result: 35 of the 36 open items have a verified free source, and none of them
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
| A1 | Debt maturity ladder, repayments by year | 14 | 6 | ○ |
| A2 | Industrial vs. captive-finance debt split | **18** | **9** | ○ |
| A3 | Average interest rate / cost of debt | 6 | 4 | ○ |
| A4 | Fixed vs. floating rate mix | 4 | 3 | ○ |
| A5 | Interest coverage ratio | 2 | 2 | ✅ R33 `ab9decb2` |

### B · Valuation history & comparables

| | Item | Lines | Agents | |
|---|---|---|---|---|
| B1 | Historical *price-based* P/E + EV/EBITDA series (5–10y median, percentile, cycle-trough) | 13 | 6 | ○ |
| B2 | Cycle-median ROE | 1 | 1 | ○ |
| B3 | Peer-basket valuation multiples | 1 | 1 | ○ |
| B4 | Peer/sector median balance-sheet ratios (D/E, quick ratio) | 2 | 2 | ○ |
| B5 | Own-history multiples vs. past FYs' own fundamentals | — | — | ✅ R37 `d3943aa5` — narrower than B1 |

### C · Cash flow & capital allocation

| | Item | Lines | Agents | |
|---|---|---|---|---|
| C1 | Explicit capex line | 9 | 7 | ✅ R34 `a841ac13` — TTM only; C2/C9 carry the rest |
| C2 | Multi-year capex / FCF averages | 3 | 3 | ○ |
| C3 | Operating cash flow line + OCF→FCF bridge | 9 | 6 | ○ |
| C4 | Working-capital change detail | 2 | 2 | ○ |
| C5 | FCF conversion history (FCF ÷ net income) | 2 | 2 | ○ |
| C6 | Buyback pacing over the trailing quarters | 1 | 1 | ✅ R35 `c7c40213` |
| C7 | Buyback average execution price | 1 | 1 | ○ |
| C8 | Historical dividend growth CAGR | 2 | 2 | ○ |
| C9 | Projected dividend growth / forward payout target | 2 | 2 | ○ |

### D · Segment & geography

| | Item | Lines | Agents | |
|---|---|---|---|---|
| D1 | Revenue by business segment | 6 | 4 | ○ |
| D2 | Revenue by geography | 2 | 1 | ○ |

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
| I1 | Executive-change detail (identity, background, circumstance) | 5 | 1 | ○ |
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

**49 items · 9 delivered · 4 closed · 36 open.** One further request line is not a data item at
all (*"whether the 1.0h post-loss cooldown blocks all buys portfolio-wide"*) and leaves scope
in §7.

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
| A2 | absent | **Designed only** (R38, `ecbbd4b7`) — and see §6 |

---

## 4. The sources

Every "verified" below was probed against the live source in this session. Scripts in
`evidence/`. Nothing rests on an unprobed assumption about what an API contains.

### 4a · Already fetched by code we run today, and discarded — 10 items

Zero new network, zero new dependency. This is the R33/R34/R35 shape, six more times.

| Items | Where the data already is |
|---|---|
| **A3** cost of debt | `fundamentals.py:385` already reads `Interest Expense` from the quarterly income statement for R33's coverage ratio. Divide by average total debt, already on the sheet. |
| **C2 C3 C4 C5** cash-flow history, bridge, working capital, FCF conversion | `_fetch_statement_facts_uncached` (`fundamentals.py:210`) pulls the quarterly cash-flow statement; only the trailing four quarters survive. **B2** (cycle-median ROE) rides the same series. |
| **C8** dividend growth CAGR | `MarketDataProvider.dividend_history()` → `DividendPayment` (CR206), fetched today for the options desk's early-assignment rule. The sheet carries yield, indicated annual, payout and ex-date — never the growth series. |
| **G1 G2 G3** IV, skew, open interest | `MarketDataProvider.option_chain()` → `OptionQuote` carries `implied_vol`, `open_interest`, `volume` (CR172 §4). Its own docstring warns `implied_vol` is the provider's figure, *"provenance unknown and occasionally absurd"* — sanity-gating (`services/option_chain.py`) is the work, not the fetch. |
| **I2** catalyst magnitude | Not a source problem at all: we hold the daily bars and each headline's own date. *"The exact percentage magnitude of the CFO-driven rally"* is arithmetic on data in hand. |

### 4b · SEC EDGAR — free, no key, and we already call it — 8 items

| Items | Route | Verified |
|---|---|---|
| **A1** maturity ladder | `companyfacts` carries `LongTermDebtMaturitiesRepaymentsOfPrincipalIn{NextTwelveMonths,YearTwo…YearFive}`. They are simply absent from `INGEST_TAGS_US_GAAP`. | **Two filers.** CAT: 5 tags, 18 points each, FY end 2025-12-31 — 2026 $7,120M · 2027 $8,920M · 2028 $7,747M · 2029 $3,112M · 2030 $1,261M. Deere: 5 tags, 4 points each, FY end 2025-11-02. A five-entry addition to `edgar_tags.py`. |
| **C7** buyback execution price | `TreasuryStockSharesAcquired` ÷ R35's repurchase dollars. | CAT n=197, latest 2026-06-30 = 6,972,123 shares. **Deere has no shares-repurchased tag** — filer-inconsistent, so it ships with a real absent state, which is CR104's rule anyway. |
| **A2 A4 D1 D2** captive split, fixed/floating, segment and geographic revenue | **Not `companyfacts`** (§6). The filing's own rendered reports, indexed by `FilingSummary.xml` on the same host. | CAT 10-K `0000018230-26-000008` (filed 2026-02-13): `R106.htm` long-term debt by *Machinery, Power & Energy* vs. Financial Products; `R108.htm` the ladder; `R129.htm` disaggregation of revenue; `R136.htm` geographic areas. |
| **I1** executive-change detail | The submissions JSON tags every filing with its 8-K **item codes**; `5.02` is *"Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain Officers"*. Fetch that document when the code is present. | CAT's 2026-04-10 8-K (`0001104659-26-042062`) states it outright: **Kyle Epley, 53, appointed CFO effective 2026-05-01, succeeding Andrew R.J. Bonfield, who remains an employee through retirement on 2026-10-01.** That is *exactly* the question the News Analyst asked in 5 of 7 convenes — and once tagged `ABSENT (only the aggregated headline text was provided)`. It was in a filing we already download. |

### 4c · Free, reliable, no API key, new call — 5 items

| Items | Source | Verified |
|---|---|---|
| **H1** CPI, PPI | **FRED** `fredgraph.csv` — the keyless CSV endpoint. (The documented `api.stlouisfed.org` API *does* require a free key; the graph endpoint does not.) | `CPIAUCSL` 332.813 and `PPIACO` 284.057, both through 2026-07-01. |
| **H3** construction spending, housing starts | FRED, same endpoint | `TTLCONS` 2,157,581 and `HOUST` 1,239, through 2026-07-01. |
| **H1 (PMI leg)** | **ISM's PMI is proprietary and is no longer on FRED** — `NAPM` returns 404. Free activity substitutes verified: `CFNAI` (−0.08), `IPMAN` (99.314), `DGORDER` (339,392), all through 2026-07-01. | The honest render names the substitute, never labels it "PMI". |
| **C9 E4** forward growth / payout | **yfinance**, the provider we already call: `growth_estimates` (carries an `LTG` long-term-growth row) and `eps_trend`. | CAT's `+1y` stock trend 19.1%; **`LTG` is NaN for CAT** — ships with a real absent state. |
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

### 4f · Closed — 4 items

| Items | Why |
|---|---|
| **G4 G5** Level 2 depth, dark-pool prints | Real-time depth-of-book is per-seat licensed exchange data. No free source exists, and none is appropriate for a simulation-only training app. |
| **E3** guidance | Ruled out by CR219 R22; the sheet's disclaimer stands. Recorded so the register is complete, not to reopen it. |
| **J2** sentiment history | Structurally absent — the social cache keeps one row and overwrites it, by design. The agent correctly tagged its own gap `FORBIDDEN`. |

The right output for this class is a **declared absence** in the sheet's own vocabulary, so an
agent stops spending a turn asking. That is a CR219-shaped prompt change — the one piece of
work this CR hands back rather than sources.

---

## 5. The 36 open items are 14 sourcing decisions

| # | Decision | Items | Lines | Cost |
|---|---|---|---|---|
| 1 | Add 5 maturity tags to `edgar_tags.py` | A1 | 14 | 5 entries + a render |
| 2 | EDGAR filing-report route via `FilingSummary.xml` | A2 A4 D1 D2 | 30 | a new parse path, free host (§6) |
| 3 | Derive cost of debt from the interest expense R33 reads | A3 | 6 | a division |
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

**Six decisions need no new network at all** (3, 4, 7, 9, 11, 14). Six more ride hosts we
already call (1, 2, 8, 10, 13) or a parameter (5). Only #12 adds an HTTP dependency, and it
needs no key. **Zero paid providers.**

### Preliminary build order

Ranked by demand against sourcing cost. A recommendation, not a ruling.

| # | Item(s) | Why here |
|---|---|---|
| 1 | A1 + A3 | 20 lines from the two most-asked debt sub-items, for five tag entries and a division. Nothing blocks either. |
| 2 | I1 | 5 lines, one agent, stuck on the same wall in 6 of 7 convenes — and the answer is in a filing we already download. Cheapest high-conviction fix in the list. |
| 3 | C3 + C4 + C2 + C5 + B2 | 20 lines across five items, all one decision on data already pulled and thrown away. |
| 4 | A2 + A4 + D1 + D2 | 30 lines, the biggest payoff — and the biggest unknown. Needs its design note re-cut against §6 before any code. |
| 5 | C8 + C7 + C9 + E4 | Cheap, already fetched, filer-inconsistent → real absent states. |
| 6 | G1 + G2 + G3 | Fetched already; the IV sanity gating is the work. |
| 7 | H1 + H3 + I2 | One keyless dependency plus one derivation. Name the ISM substitute honestly. |
| 8 | B1 + F1–F9 + F11 | 32 lines but concentrated in 1–2 agents, and the sheet already answers the trend question five ways. High count, low breadth — deliberately last. |
| 9 | B3 + B4 | Low measured demand; its real value is unblocking a stale sheet denial. |
| — | H2 | Blocked on §4e. Probe the Atlanta Fed feed from melehost first. |
| — | E3 G4 G5 J2 | Declared absences, handed to CR219's surface. |

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

This is a live lane: `ingest_edgar_facts.py`, `edgar_tags.py`, `fundamentals.py` and
`room_runner.py` are all dirty in the working tree under WP10. **This CR does not touch them.**
Per stay-in-your-lane the finding is reported with its repro, and the routing is the
dispatcher's call:

- fold the correction into WP10 while it is open (cheapest — nothing has shipped), or
- let WP10 land its no-op and file a DEF against it.

Recommendation: the first.

---

## 7. Scope

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

## 8. Acceptance

1. `evidence/items.py` runs from any working directory, prints 49 items, and **exits non-zero**
   if any of the 127 lines claims no item or if the register's totals drift from §2.
2. `evidence/inventory.py` still prints all 127 lines by agent, from any working directory.
3. `evidence/edgar_census.py` exits 0 and prints the fact-point-key census for two filers.
4. Every §3 row names a commit SHA and a sheet line, or states the absence.
5. Every open item in §2 appears in exactly one §4 subsection, and every §4a–§4d verdict names
   the file, function or endpoint that serves it. Anything unverified says so in the row.
6. The §6 finding is delivered to the WP10 lane and the routing decision is recorded here with
   its date.
7. A design note exists per sourcing decision before its follow-on CR opens.
8. H2 is either sourced from melehost or recorded as a declared absence — not left ambiguous.

---

## Related

- [`../CR219_room_prompt_contradictions/`](../CR219_room_prompt_contradictions/CR219_room_prompt_contradictions.md)
  — the parent: the demand corpus, the arms, and WP06's six shipped fields.
- `../CR219_room_prompt_contradictions/dev_instructions/WP06_data_additions.md` — the rules
  every follow-on field commit inherits.
- `../CR219_room_prompt_contradictions/dev_instructions/R38_edgar_design_note.md` — the note §6
  corrects, and the template §7.4 reuses.
- [`../CR218_capital_return_field/`](../CR218_capital_return_field/) — the "precompute it" precedent.
- [`../CR164_room_backtest/`](../CR164_room_backtest/) — the EDGAR companyfacts ingest this CR
  extends by five tags.
- `../CR172_options_simulation/` — where `OptionQuote.implied_vol` and `open_interest` are already fetched.
- `../CR206_dividend_feed_for_early_assignment/` — where `DividendPayment` is already fetched.
