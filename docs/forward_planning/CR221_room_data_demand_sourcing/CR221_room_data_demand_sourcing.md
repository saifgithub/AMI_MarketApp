# CR221 — Sourcing the Room's measured data demand

**Status:** in_progress · **Owner:** coder.api · **Filed:** 2026-09-03 · **Tag:** `(AT:R75 CR221)`

**Done at filing:** §1–§6 — the item register, the cross-check against CR219, a *verified free*
source for every open item but one, and the §6 measurement. **Ruled 2026-09-03:** R38's route
is CR221's (`ac55352c`) — CR219 ships a declared-absent entry now, this CR builds the real line
later, inheriting `WP10_R38_parked/` as its head start. **Open:** the build itself, the §7
measurement re-run it is designed for, and the one item (H2) with no free source yet found.

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
| A2 | absent | **Designed only** (R38, `ecbbd4b7`) — and see §6 |

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
| **A2 A4 D1 D2** captive split, fixed/floating, segment and geographic revenue | **Not `companyfacts`** (§6). The filing's own rendered reports, indexed by `FilingSummary.xml` on the same host. | CAT 10-K `0000018230-26-000008` (filed 2026-02-13): `R106.htm` long-term debt by *Machinery, Power & Energy* vs. Financial Products; `R108.htm` the ladder; `R129.htm` disaggregation of revenue; `R136.htm` geographic areas. |
| **A3** cost of debt | `InterestExpense` (income statement) and `InterestPaidNet` (cash-flow supplemental), over EDGAR gross debt — both legs from one store at one `as_of`. **Not** the yfinance row §4a first assumed. | **This premise was probed and failed, which is DEF399.** CAT's FY2025 income statement (`R3.htm`) carries *Interest expense of Financial Products* $1,359M **plus** *excluding Financial Products* $502M = **$1,861M**; yfinance's four quarters sum to **$529M**, 28% of it, because the finance arm's interest is booked inside cost of revenue. GM reads 0.17x against its own `us-gaap:InterestExpense`. CAT tags **no** income-statement interest concept in `companyfacts` (dimensional lines again — §6 on a second item), so it resolves on cash interest or not at all. Where the two bases disagree >2x (HOG $31M vs $331M, F $7,613M vs $3,501M) the honest output is **absence**, not the friendlier number. |
| **I1** executive-change detail | The submissions JSON tags every filing with its 8-K **item codes**; `5.02` is *"Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain Officers"*. Fetch that document when the code is present. | CAT's 2026-04-10 8-K (`0001104659-26-042062`) states it outright: **Kyle Epley, 53, appointed CFO effective 2026-05-01, succeeding Andrew R.J. Bonfield, who remains an employee through retirement on 2026-10-01.** That is *exactly* the question the News Analyst asked in 5 of 7 convenes — and once tagged `ABSENT (only the aggregated headline text was provided)`. It was in a filing we already download. |

### 4c · Free, reliable, no API key, new call — 4 items

*(H1 takes two rows — its CPI/PPI leg and its PMI leg have different answers — but it is one item.)*

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
| 4 | A2 + A4 + D1 + D2 | 30 lines, the biggest payoff — and the biggest unknown. Needs its design note re-cut against §6 before any code. |
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
