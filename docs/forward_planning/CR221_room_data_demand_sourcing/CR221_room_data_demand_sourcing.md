# CR221 — Sourcing the Room's measured data demand

**Status:** in_progress · **Owner:** coder.api · **Filed:** 2026-09-03 · **Tag:** `(AT:R75 CR221)`

**Done at filing:** §1–§5 and the preliminary build order — the inventory, the cross-check
against CR219, a verdict for every residue item, and the §5 measurement. **Open:** the design
notes (§6 item 4), the §5 routing decision with the WP10 lane, and the two new-dependency
decisions that are Saiful's.

---

## What

CR219 asked twelve agents, on every turn, to name the data they lacked. They named it
**127 times**. CR219 then shipped six of those fields and designed a seventh; this CR takes
the **whole demand list**, checks each item against what CR219 actually built, and — for
everything left — **finds the source**.

This CR's deliverable is a **sourcing verdict per item**, not a fact-sheet field. Fields are
what the follow-on CRs build. What is missing today is not build capacity; it is an answer to
*"where would that number even come from, and does that source exist?"* — asked once, for all
of it, instead of one field at a time.

Four verdict classes, and every item lands in exactly one:

| Verdict | Meaning |
|---|---|
| **IN HAND** | The data is already fetched by code we run today and thrown away. Zero new network, zero new dependency. |
| **REACHABLE** | An existing dependency serves it at a call we do not currently make (different endpoint, different window, different parameter). |
| **NEW DEPENDENCY** | Needs a provider we do not have. Flagged per CLAUDE.md's lean-stack rule — Saiful's call, not a worker's. |
| **PERMANENTLY ABSENT** | No source we can reach serves it. The correct output is a **declared absence** on the sheet, not a field. |

## Why

Three reasons, in order of force.

1. **The demand is measured, not guessed.** CR219's arms put a `DATA I LACKED:` addendum on
   every turn across six mandate variations plus one full live convene. 127 request lines from
   12 agents. That is the closest thing this project has to a specification for what the Room
   needs — written by the consumers, unprompted as to content.

2. **The residue is where the verdicts get decided.** CR219's own measurement showed the debt
   cluster is the #1 ask (26 requests, 9 of 12 agents) and that the CAT insolvency narrative
   was built without interest coverage. R33 shipped coverage. **The other three quarters of
   that cluster — maturity ladder, average rate, fixed-vs-floating — have no CR219 row at
   all**, and the biggest single sub-ask (industrial-vs-captive split, 18 requests) is designed
   against a source that does not carry it (§5).

3. **Sourcing one field at a time re-asks the same question.** R33/R34/R35 were all
   "derivations of data in hand" and were discovered as such one at a time. Five more items in
   §4 are the same shape. One sweep is cheaper than five discoveries, and it is the only way to
   see that four separate asks (dividend CAGR, buyback execution price, FCF conversion history,
   historical quick-ratio medians) share one source.

---

## 1. The demand — how it was captured, and how to reproduce it

CR219 ran seven convenes with a per-turn addendum asking each agent to list, in an
`(a)/(b)/(c)` form, the data it lacked, what it would have changed, and whether the data was
ABSENT / WITHHELD / FORBIDDEN. All seven are banked complete — system prompt, user message,
reasoning trace, answer.

| Source | Convenes | Request lines |
|---|---|---|
| `CR219/evidence/arms/{h_short,h_medium,h_long,h_very_long,g_income_now,g_learning}` | 6 mandate variations, one shared profile | 102 |
| `CR219/evidence/convene_CAT_long_wealth/` | 1 full 12-agent live-profile convene | 25 |
| | | **127** |

Reproduce the clustering (CR219's own script, arms only — the 102 figure):

```bash
V=backend/.venv/bin/python
$V docs/forward_planning/CR219_room_prompt_contradictions/evidence/analysis/aggregate_arms.py
```

Reproduce this CR's full inventory (all seven convenes, verbatim lines, grouped by agent, plus
the debt sub-split and the unbucketed residue):

```bash
$V docs/forward_planning/CR221_room_data_demand_sourcing/evidence/inventory.py
```

**One correction to carry forward.** CR219's `aggregate_arms.py` buckets by regex and reports
17 lines as `(unbucketed)` over all seven convenes, with 26 in its debt bucket. **Eight of
those seventeen are debt asks its debt pattern misses** — *"maturity schedule for the $45.1B"*
carries no `debt maturity` bigram — and one more (*"sector median debt-to-equity and quick
ratios"*) is claimed by its peer pattern first. The true debt cluster is **35 distinct request
lines from 9 of 12 agents**, not 26. This CR's inventory sub-splits it rather than re-running
the same regex, and clusters every line: zero unclustered.

---

## 2. The canonical demand

Clusters are **mutually exclusive** — first match wins, so the 15 rows sum to 127 and no line
is double-counted. Agent counts are distinct agents making that ask. Reproduced exactly by
`evidence/inventory.py`.

| # | Ask | Lines | Agents | Representative request |
|---|---|---|---|---|
| 1 | **Debt** (sub-split below) | **35** | **9** | *"A breakdown of the $45,146M gross debt separating core industrial manufacturing from its captive finance arm"* |
| 2 | Historical valuation multiples, 5–10y | 17 | 9 | *"Historical 5-to-10 year baseline averages for CAT's trailing P/E and EV/EBITDA"* |
| 3 | Price series: weekly/monthly bars, MACD/crossovers, volume profile, support/resistance, candlesticks | 14 | 2 | *"Volume-by-price or volume profile nodes near the 200-day SMA"* |
| 4 | Capex / cash-flow detail (working-capital bridge, FCF conversion history) | 9 | 6 | *"A detailed cash-flow statement showing CapEx and working capital changes"* |
| 5 | Order book, dark pool, options flow, IV / skew / open interest | 9 | 6 | *"Real-time Level 2 order book depth and bid-ask spread at the $768.45 support level"* |
| 6 | Macro series (CPI/PPI/PMI/ISM, Fed path, construction spend, mining capex) | 8 | 3 | *"Forward macroeconomic indicators … or expected Fed rate path ahead of the FOMC meeting"* |
| 7 | Segment / geographic revenue split | 7 | 4 | *"Revenue breakdown by segment (Construction vs. Resource vs. Energy & Transportation)"* |
| 8 | Dividend growth CAGR, forward payout, buyback pacing + execution price | 6 | 5 | *"Historical dividend growth rate (CAGR)"* |
| 9 | News depth: CFO identity, catalyst magnitude | 6 | 1 | *"Details on the CFO transition (who the new executive is or their prior mandate)"* |
| 10 | Raw social split / buzz / mention counts | 5 | 1 | *"Exact bullish/bearish split percentages, buzz scores, and mention volume counts"* |
| 11 | Earnings revisions / surprise history / guidance | 4 | 1 | *"Earnings surprise history and revision trends"* |
| 12 | Volatility for stop sizing (ATR, gap risk, slippage) | 4 | 3 | *"Average True Range (ATR) over the last 14 to 20 days"* |
| 13 | Peer / sector comparables | 1 | 1 | *"Valuation multiples (P/E, EV/EBITDA) for peers like Deere and AGCO"* |
| 14 | Decision Journal history for this ticker | 1 | 1 | *"The user's actual Decision Journal history for Caterpillar"* |
| 15 | Mandate-rule clarification (cooldown scope) | 1 | 1 | *"whether the 1.0h post-loss cooldown blocks all buys portfolio-wide, or only re-entry"* |
| | | **127** | **12** | |

### Debt (#1) — sub-split

A line naming two things is counted in both sub-asks, so these do not sum to 35.

| Sub-ask | Lines | Agents |
|---|---|---|
| Industrial vs. captive-finance split | 18 | 9 |
| Maturity schedule / ladder | 14 | 6 |
| Average interest rate / cost of debt | 5 | 4 |
| Fixed vs. floating | 4 | 3 |
| Interest coverage | 2 | 2 |

Two of the fifteen clusters (#14, #15) are not data-source problems; they leave scope in §6.
Reading the cluster counts, note that **#9 and #10 and #11 are each one agent asking
repeatedly** — a persistent single-consumer need, not a Room-wide one — while #1's 35 lines
come from 9 of the 12. Demand is not uniform and the build order (§4, closing) should not treat
it as if it were.

---

## 3. Cross-check against what CR219 built

CR219's WP06 (`dev_instructions/WP06_data_additions.md`) shipped six fields and designed one.
Verified against the regenerated sheet at `CR219/evidence/rendered/sheets/__FULL__.txt`:

| Ask | CR219 row | Commit | On the sheet today | Closes the ask? |
|---|---|---|---|---|
| Interest coverage | R33 | `ab9decb2` | `Interest coverage (EBIT / interest expense) (LIVE): 9.4x` | **Yes** |
| Explicit capex | R34 | `a841ac13` | `Capital expenditure (LIVE): $6,543M (trailing 4 quarters)` | **Partly** — TTM only; 11 lines asked for the multi-year series and the working-capital bridge |
| Buyback pacing | R35 | `c7c40213` | `Buyback pacing (LIVE): …4 quarters… — PACESENT` | **Yes** for pacing; execution price still open |
| ATR(14) | R36 | `a4459b01` | ATR line, execution/risk lanes | **Yes** |
| Own-history multiples | R37 | `d3943aa5` | `Multiples vs. own history (LIVE): … median 15.7x / 11.3x` | **Partly** — 4 FYs, and it is *today's price against past fundamentals*, which the sheet says plainly. 16 lines asked for a 5–10y **price-based** multiple series. Different number. |
| Earnings revisions + surprise history | R21-DATA | `ecb8f199` | `Earnings revisions (LIVE)` + `Surprise history (LIVE)` | **Yes** (guidance deliberately excluded — R22) |
| Raw social split / buzz / mentions | pre-CR219 | — | buzz score, bullish/bearish %, mention counts, classified split | **Yes** |
| Decision Journal history | DEF054/DEF055 | — | wired to Bull/Bear via `journal_context.py` | **Yes** — the arm request is a harness artifact (synthetic user, empty journal) |
| Industrial vs. captive debt split | R38 | `ecbbd4b7` (design note only) | absent | **Designed, not built — and see §5** |

**Everything else in §2 has no CR219 row.** That residue is what this CR sources.

---

## 4. The residue, with a sourcing verdict

Every verdict below that says "verified" was probed in this session; the probe commands are in
`evidence/`. Nothing here is asserted from memory of what an API contains.

### IN HAND — already fetched, currently discarded

| Item | Where it already is | Note |
|---|---|---|
| **Average cost of debt** (5 lines, 4 agents) | `fundamentals.py:385` already reads `Interest Expense` from the quarterly income statement for R33's coverage ratio. Divide by average total debt (already on the sheet). | Derivation, zero new network. **EDGAR is not a route here** — verified: CAT's 703 us-gaap tags contain no weighted-average-rate tag at all; Deere has exactly one (`ShortTermDebtWeightedAverageInterestRate`) and it is short-term only and stale since 2022. Filer-inconsistent, so the derivation is the only reliable route. |
| **Multi-year capex / FCF-conversion / working-capital series** (9 lines, 6 agents) | `_fetch_statement_facts_uncached` (`fundamentals.py:210`) already pulls the quarterly cash-flow statement; only the trailing four quarters survive. | Same shape as R33–R35: the data is fetched and discarded. |
| **Historical quick-ratio / balance-sheet medians** (1 line, inside the 17-line multiples cluster) | Same quarterly statement pull. | |
| **Dividend growth CAGR / forward payout** (4 of the 6-line dividend/buyback cluster) | `MarketDataProvider.dividend_history()` → `DividendPayment` (CR206) is fetched today for the options desk's early-assignment rule. The Room sheet carries yield, indicated annual, payout and ex-date — never the growth series. | Zero new network. |
| **Options IV / open interest / volume / skew** (6 of the 9-line flow cluster) | `MarketDataProvider.option_chain()` → `OptionQuote` carries `implied_vol`, `open_interest`, `volume` (CR172 §4), with `classify_option_quote`'s three-state fillability guard already in place. | The Trader, the PM and both debators ask for IV for stop sizing and FOMC event risk; the data is fetched elsewhere in this same process. `OptionQuote`'s own docstring warns that `implied_vol` is the provider's figure, "provenance unknown and occasionally absurd" — sanity-gating it is `services/option_chain.py`'s job and would have to be part of any render. |
| **Peer basket for comparables** (1 clustered line, plus a second — *"sector median debt-to-equity and quick ratios … like Deere and AGCO"* — that clusters under Debt) | `classification_universe.py` persists sector/industry for the ~503 S&P parent constituents, refreshed daily, off the request path. | The cohort exists. The sheet says *"No peer-basket comparison exists"* — true today, and it need not stay true. Note the CR219 R37/WP01-R7 collision marker: shipping this makes that denial fully false. |

### REACHABLE — an existing dependency, at a call we do not make

| Item | The call we do not make | Verified |
|---|---|---|
| **Debt maturity ladder** (14 lines, 6 agents) | `companyfacts` — the endpoint `ingest_edgar_facts.py` already calls — carries `LongTermDebtMaturitiesRepaymentsOfPrincipalIn{NextTwelveMonths,YearTwo,YearThree,YearFour,YearFive}`. They are simply not in `INGEST_TAGS_US_GAAP`. | **Verified on two filers** (`evidence/edgar_census.py`). CAT: all 5 tags, 18 points each, latest FY end 2025-12-31 — 2026 $7,120M · 2027 $8,920M · 2028 $7,747M · 2029 $3,112M · 2030 $1,261M. Deere: all 5 tags, 4 points each, latest FY end 2025-11-02. This is a five-entry addition to `edgar_tags.py` plus a render. |
| **Weekly / monthly bars, longer support-resistance window, volume profile** (14 lines) | `market_data._PERIOD_MAP` already defines `"1y"` (weekly bars), `"2y"` (504 daily bars, added by CR136) and `"5y"` (monthly). The Room profile is pinned to `_HISTORY_PERIOD = "3m"` (`fundamentals.py:1717`, ~65 daily bars). | A parameter, not a provider. MACD/crossovers/Bollinger are computable from bars we can already fetch — the sheet's blanket denial of them (disclosure line 4) is a *choice*, and it should be re-decided knowingly rather than inherited. Note the demand shape: 14 lines but only 2 agents, and the sheet already carries 20/50/200-day SMAs, RSI, relative strength and the window trend. |
| **Buyback average execution price** (1 line) | `TreasuryStockSharesAcquired` in `companyfacts`, ÷ the repurchase dollars R35 already renders. | **Verified, and filer-inconsistent**: CAT n=197 points, latest end 2026-06-30 = 6,972,123 shares; **Deere has neither shares-repurchased tag**. Ships only with a real absent state, which is CR104's rule anyway. |
| **Segment / geographic revenue split** (7 lines) and **industrial-vs-captive debt split** (18 lines) | **Not `companyfacts`** — see §5. The data is in the filing's own rendered reports, reachable from `FilingSummary.xml` on the same `sec.gov` host we already fetch. | **Verified on CAT's 10-K** `0000018230-26-000008` (filed 2026-02-13): `R106.htm` renders long-term debt split by *Machinery, Power & Energy* vs. Financial Products; `R108.htm` the maturity ladder; `R129.htm` disaggregation of revenue; `R136.htm` information about geographic areas. This is the largest single sourcing decision in the CR — 25 request lines across two clusters, and a route change for a lane in flight. |

### NEW DEPENDENCY — flag, do not build unasked

| Item | Candidate source | Cost shape |
|---|---|---|
| **Macro series** (8 lines, 3 agents): CPI, PPI, ISM/PMI, construction spending, mining capex, Fed-path probabilities | FRED (free, API key, includes construction spending and every CPI/PPI/PMI print). Fed-path *probabilities* are a separate matter — CME FedWatch is the market standard and is not a free API; 4 of the 8 lines ask specifically for the rate-cut probability, which FRED does not serve. | One keyed HTTP dependency + a cache, and it still does not close half the cluster. The sheet already carries a REAL FOMC countdown from the Fed's calendar; the ask is for the *content* of the expectation, which the countdown deliberately does not claim. |
| **News depth** (6 lines, 1 agent): CFO identity, catalyst magnitude, article body | Today `news_context` carries headline + publisher + age. Body text or an entity-tagged feed is a different product tier. | Flag. The shape of the ask is worth reading: the News Analyst asked in **6 of 7 convenes** to know *who* the incoming CFO is before scoring a CFO-driven rally, and once tagged its own gap `ABSENT (only the aggregated headline text was provided)`. One agent, but it is stuck on the same wall every run. |

### PERMANENTLY ABSENT — declare it, do not chase it

| Item | Why |
|---|---|
| **Level 2 order-book depth, bid density, dark-pool prints** (3 of the 9-line flow cluster) | No consumer-reachable source serves real depth-of-book for a simulation-only training app; the ask is for real-time exchange data with per-seat licensing. The Trader asked for it in 3 of 7 convenes, twice naming the same $768.45 level. |
| **Company guidance** (2 of the 4-line revisions cluster) | Already ruled out by CR219 R22 — the sheet's disclaimer stands, and the overlay was rewritten to stop demanding it. Recorded here so the demand list is complete, not to reopen it. |

The right output for this class is a **declared absence** in the sheet's own vocabulary, so an
agent stops spending a turn asking. That is a CR219-shaped prompt change, and it is the one
piece of prompt work this CR hands back rather than sources.

### Preliminary build order

Ranked by (lines × agents) against sourcing cost. This is the CR's recommendation, not a
ruling; §7.7 requires the final ordering to show its inputs.

| # | Item | Lines × agents | Cost | Why here |
|---|---|---|---|---|
| 1 | Debt maturity ladder | 14 × 6 | 5 tag entries + a render | Highest demand for the lowest cost in the whole list. Nothing blocks it. |
| 2 | Average cost of debt | 5 × 4 | a division | Rides the same commit as #1 and finishes the debt cluster's cheap half. |
| 3 | Multi-year capex / FCF-conversion series | 9 × 6 | discarded data | Third R33-shaped derivation; extends R34 rather than adding a line. |
| 4 | Segment / geographic revenue **and** industrial-vs-captive debt | 25 lines, 2 clusters | a new EDGAR route (§5) | Biggest payoff, biggest unknown. Needs its design note re-cut before code. |
| 5 | Dividend growth CAGR + buyback execution price | 6 × 5 | already fetched | Cheap; filer-inconsistent, so it ships with a real absent state. |
| 6 | Options IV / open interest | 6 lines | already fetched, needs sanity gating | The gating, not the fetch, is the work. |
| 7 | Longer price window (weekly/monthly, volume profile) | 14 × **2** | a parameter | High line count, only two consumers, and the sheet already answers the trend question five ways. Deliberately below #6. |
| 8 | Peer basket | 2 lines | cohort exists | Low measured demand; unblocks a stale sheet denial, which is its real value. |
| — | Macro, news depth | 14 lines | new dependency | Not ranked — Saiful's decision, not a build queue item. |
| — | Level 2, guidance | 5 lines | none | Declared absence, handed to CR219's surface. |

---

## 5. The R38 correction — measured, and it affects a lane in flight

**R38's design note states that the industrial-vs-captive split "lives in the `companyfacts`
payload's per-fact `segment` object today" and that the work is a dimensional parser over the
data we already ingest. That premise does not hold.**

Measured this session against the live endpoint:

| Filer | us-gaap fact points in `companyfacts` | Points carrying a `segment` key |
|---|---|---|
| Caterpillar (CIK 18230) | 39,403 | **0** |
| Deere (CIK 315189) | 35,550 | **0** |

Every fact point on both filers carries exactly `{end, val, accn, fy, fp, form, filed, frame, start}`.
There is no `segment` object to parse. The `companyfacts` API serves the **consolidated,
non-dimensional** fact only — which is why `Revenues` shows 345 points for CAT with 118
duplicate `(start, end)` pairs: those are the same consolidated figure restated across
filings, distinguished by `accn`/`filed`, not segment members.

`backend/scripts/ingest_edgar_facts.py` currently carries an uncommitted
`_segment_member_names(fact)` reading `fact.get("segment")` (lines 129–142) and two call sites
that gate on it. **On this evidence it returns `[]` for every fact of every filer**, so the
dimensional pass finds nothing and the captive-split resolver silently produces no data —
which, under CR040, must not be allowed to look like "this filer has no captive-finance
segment" (R38's own documented common case). The two states are indistinguishable at the
render layer as designed.

**The data does exist** — §4 verified it in CAT's `R106.htm`. It is at a different endpoint:
the filing's rendered reports, indexed by `FilingSummary.xml`, on the same host. So R38's
*conclusion* (no new provider needed) survives; its *route* does not.

This is a live lane — `ingest_edgar_facts.py`, `edgar_tags.py`, `fundamentals.py` and
`room_runner.py` are all dirty in the working tree under WP10. **This CR does not touch
them.** Per the stay-in-your-lane rule the finding is reported, with its repro, and the
routing decision is the dispatcher's:

- fold the correction into WP10 while it is open (cheapest — nothing has shipped yet), or
- let WP10 land its no-op and file a DEF against it.

Recommendation: the first. A parser that cannot fire has no test that can prove it wrong.

---

## 6. Scope

**In scope**

1. The complete 127-line demand inventory, reproducible, sub-split, agent-attributed
   (`evidence/inventory.py`).
2. The cross-check in §3 — every ask against every CR219 field, on the regenerated sheet.
3. A sourcing verdict per residue item (§4), each either **verified against the live source in
   this CR** or explicitly marked a candidate.
4. A one-page design note per **REACHABLE** item that a follow-on CR would build, in this
   folder, on the R38 template (endpoint, rate limits, cache strategy, failure mode) —
   *before* any code.
5. The §5 correction, reported to the WP10 lane with its repro.
6. A ranked build order for the follow-on CRs, by (demand lines × agents) ÷ sourcing cost.

**Out of scope**

- **Shipping any fact-sheet field.** Every field is a follow-on CR under WP06's existing rules
  (CR104 provenance, guard entry in the same commit, persona `## Inputs` in the same commit,
  compose parity, one field per commit).
- **Any prompt or persona edit.** Including the declared-absence lines §4 recommends for the
  permanently-absent class — those are CR219's surface.
- **Taking the new-dependency decisions.** FRED and a news-body tier are flagged for Saiful,
  per the lean-stack rule; this CR presents cost and coverage, not a fait accompli.
- **The two non-data items** (Decision Journal — already wired; cooldown-scope clarification —
  a prompt-clarity item that belongs to CR219's instruction-collision class).
- **Re-running the arms.** The demand corpus is banked and sufficient; a second measurement
  after the fields ship is CR219 R30's trailing question, not this one's.

---

## 7. Acceptance

1. `evidence/inventory.py` runs from any working directory and prints all 127 request lines
   grouped by agent, with the cluster sub-split reproducing §2's counts exactly.
2. Every row of §3's cross-check names a commit SHA and a sheet line (or states its absence),
   and each is checkable against `CR219/evidence/rendered/sheets/__FULL__.txt` at HEAD.
3. Every §4 item carries a verdict, and every **IN HAND** / **REACHABLE** verdict names the
   file, function or endpoint that serves it. No verdict rests on an unprobed assumption about
   an API's contents.
4. §5's measurement is reproducible by a script in `evidence/` that hits the live endpoint and
   prints the fact-point-key census for at least two filers.
5. The §5 finding is delivered to the WP10 lane, and the routing decision (fold in vs. DEF) is
   recorded here with its date.
6. A design note exists for each REACHABLE item before any follow-on CR opens.
7. The ranked build order is written down, with the ranking inputs shown, so the follow-on
   ordering is arguable rather than asserted.

---

## Related

- [`../CR219_room_prompt_contradictions/`](../CR219_room_prompt_contradictions/CR219_room_prompt_contradictions.md)
  — the parent. The demand corpus, the arms, and WP06's six shipped fields.
- `../CR219_room_prompt_contradictions/dev_instructions/WP06_data_additions.md` — the rules
  every follow-on field commit inherits.
- `../CR219_room_prompt_contradictions/dev_instructions/R38_edgar_design_note.md` — the design
  note §5 corrects, and the template §6.4 reuses.
- [`../CR218_capital_return_field/`](../CR218_capital_return_field/) — the "precompute it"
  precedent.
- [`../CR164_room_backtest/`](../CR164_room_backtest/) — the EDGAR companyfacts ingest this CR
  extends by five tags.
- `../CR172_options_simulation/` — where `OptionQuote.implied_vol` and `open_interest` are
  already fetched.
- `../CR206_dividend_feed_for_early_assignment/` — where `DividendPayment` is already fetched.
