# CR069 — Source a real Sharia-compliance indicator for the `halal` flag

**Status:** proposed (BRIEF — architect/build team implements; this lane files and reviews) ·
**Filed:** 2026-07-23 (AT:R59) · **Source:** Saiful

> Saiful: *"We have had to drop the 'Halal' filter because we currently do not have an indicator to
> say if a ticker/counter is halal/shariah compliant or not. Your assignment is to understand from
> the datafeeds that we have if there are such indicators available. Search the web if there is a
> way to have this indicator."*
>
> Direction after the research landed: *"derived from the published ETF and look into shariah
> compliant API"* · *"US, Malaysia, and research for other markets, and look at the available API
> for cost evaluation."*

---

## What

Source a **real** Shariah-compliance indicator so the `halal` mandate flag can enforce something the
system actually knows, instead of the 7-ticker placeholder it enforces today. Three phases: a free
US universe derived from published Shariah ETF holdings, Malaysia via the Securities Commission's
official list, and a costed evaluation of the paid screening APIs for everything else.

**This CR is the brief.** The research below is a head-start, not a mandate — the architect and
build team own the design, the implementation, and the guard.

## Why

[DEF084](../../defect/DEF084_halal_flag_is_an_allowlist_not_a_screen/DEF084_halal_flag_is_an_allowlist_not_a_screen.md)
established the state we're in:

- Real screening math **exists** — `sharia_screen()`, `sharia_debt_ratio()`,
  `sharia_liquidity_ratio()`, `sharia_impermissible_income_ratio()`, `purification_amount()` in
  [`backend/app/trading_math/screening.py`](../../../backend/app/trading_math/screening.py) (CR046 M13).
- …and is **called by nothing**. The only references outside the module are re-exports in
  `trading_math/__init__.py`.
- What actually enforces `halal` is `DEFAULT_HALAL_DEMO_UNIVERSE` —
  `{"AAPL","MSFT","NVDA","GOOGL","META","TSLA","AMZN"}` at
  [`sim_engine.py:80`](../../../backend/app/services/sim_engine.py), consumed at `:463` and `:624`,
  passed at [`api/mandate.py:274`](../../../backend/app/api/mandate.py).
- DEF084 **Option 2 shipped**: the UI now says so honestly —
  *"Curated demonstration universe … not a Sharia screen"*
  ([`settings_screen.dart:355`](../../../mobile/lib/screens/settings/settings_screen.dart),
  `app_en.arb:395`), shipped to devices in build `0.1.0+51`.

Option 2 was the minimum acceptable state, not the destination. The blocker was never the math — it
was the **indicator**. This CR sources it, which is DEF084's Option 1.

## Research findings (measured 2026-07-22/23 on the Mac, not estimated)

### 1. None of our data feeds carries a compliance indicator

| Feed | Used for | Sharia indicator? |
|---|---|---|
| Yahoo — `yfinance` + `query1.finance.yahoo.com/v8/finance/chart` | prices, fundamentals, news | **No** |
| Alpha Vantage (`news_context.py`) | news sentiment | **No** |
| Adanos (`social_context.py`) | Reddit sentiment | **No** |
| Alpaca (`alpaca_service.py`) | user paper-trading link | **No** |
| federalreserve.gov FOMC calendar | macro dates | n/a |

Verified directly: `yfinance 1.3.0`, `Ticker("AAPL").info` → **180 keys, zero** matching
`shar*` / `hala*` / `islam*` / `compli*`. The nearest neighbour is `esgPopulated`, an ESG-data flag,
not an Islamic screen.

### 2. Self-computing from yfinance cannot produce a screen

```
totalDebt      84,710,998,016   ✓ AAOIFI debt ratio
totalCash      68,507,000,832   ✓ AAOIFI liquidity ratio
marketCap   4,771,848,126,464   ✓ denominator
totalRevenue  451,442,016,256   ✓ denominator
sector        "Technology"      ~ too coarse for the business-activity screen
revenue by segment              ✗ → impermissible-income ratio NOT computable
```

Two of three ratios, and nothing usable for the business-activity screen (`Financial Services`
catches Islamic banks and payment processors alike). Shipping that as "a Sharia screen" would be
DEF084 again, one layer deeper. **Rejected as a primary source.**

### 3. The ETF-derived route works — verified live

```
$ curl https://www.sp-funds.com/wp-content/uploads/data/TidalFG_Holdings_SPUS.csv
HTTP:200  bytes:23574  type:text/csv   → 220 rows, 219 distinct tickers, Date=07/22/2026
Date,Account,StockTicker,CUSIP,SecurityName,Shares,Price,MarketValue,Weightings,...
07/22/2026,SPUS,NVDA,67066G104,NVIDIA Corp,1858121,207.29,385169902.09,13.32%,...
```

No API key, refreshed daily, and it behaves like a real screen: **JPM, BAC, WFC, KO, PM, MO, WYNN
are all absent** (banks, tobacco, casino). SPUS tracks the *S&P 500 Sharia Industry Exclusions
Index*, AAOIFI-aligned, screened by S&P DJI — not by us. Sibling CSVs at the same path are also live
(`TidalFG_Holdings_SPSK.csv` sukuk, `..._SPRE.csv` REIT).

A second source is equally available: **HLAL** (Wahed, FTSE Shariah USA, fatwa by Yasaar Ltd),
published as a Google Sheet in the **identical Tidal schema** —
`https://docs.google.com/spreadsheets/d/1UC1Bk67bGuYsos_i8y_HQpNoHpVHAvqf71MbgrafJOQ/export?format=csv&gid=0`
→ HTTP 200, 21.7 KB, 213 rows, same `07/22/2026` as-of date. **ISUS.L** (iShares MSCI USA Islamic,
~141 holdings) is a third.

**Trap:** `yfinance.funds_data.top_holdings` returns **only 10 rows** for SPUS and HLAL. It is not a
substitute for the CSV.

### 3a. The two sources disagree on ~48% of names — this decides the architecture

Both CSVs pulled the same day, plain-alpha tickers only:

```
SPUS (S&P / AAOIFI): 216      HLAL (FTSE): 210
agree (in both):     146
SPUS only:            70      (ABBV, ACN, BKNG, HD, IBM, ORCL, PEP, TMO, UNP, …)
HLAL only:            64      (GOOG, META, KO, CVX, T, INTC, PFE, DELL, EA, …)

UNION 280 · INTERSECTION 146 · disagreement 134 names = 47.9% of the union
```

This is lesson `350_standards_differ_why_the_same_stock_flips` measured on our own data, and it has
three hard consequences:

1. **"Second source as failover" is unsafe and must not be built.** Falling back from SPUS to HLAL
   silently changes the standard under the user — META and KO are non-compliant under one and
   compliant under the other. A failover would flip a ticker's observance verdict with no signal.
2. **Union is the loosest possible screen and is sourced from nobody** — it would be AMI's own
   invented standard, which is the DEF084 failure with extra steps. Intersection is defensible as a
   *conservative* screen but is likewise no published standard, and it would wrongly exclude 134
   names that some scholar body cleared.
3. **Therefore: one named primary standard, full stop.** The second source becomes a *monitoring*
   signal (alert when the two diverge on a name a user holds or is convening), never an input to the
   verdict.

**Note for the product decision:** today's `DEFAULT_HALAL_DEMO_UNIVERSE` contains **META**, which
SPUS/AAOIFI screens **out**. Whichever standard is chosen, the current 7-ticker list is not a subset
of it.

### 4. Malaysia is free and authoritative

The Securities Commission's **Shariah Advisory Council** publishes the *List of Shariah-Compliant
Securities* on Bursa Malaysia — a two-tier screen (business-activity benchmarks + financial-ratio
benchmarks), updated **every May and November** (latest effective 28 Nov 2025). Verified fetchable:
`https://www.sc.com.my/api/documentms/download.ashx?id=<doc-id>` → HTTP 200, 533 KB,
`application/pdf`. **PDF only — no CSV, no API, no machine-readable feed.**

### 5. Paid APIs — for the cost evaluation

Vendor-published figures, gathered 2026-07-22:

| Provider | Coverage | Standards | Price |
|---|---|---|---|
| **Halal Terminal** | 50k–200k assets, 58 endpoints, async bulk index screening | AAOIFI, DJIM, FTSE, MSCI, S&P | free 500 tokens/mo; **$19 / $49 / $199** per mo; $0.008–0.01/token overage |
| **Zoya** | 40k+ globally; Basic = US, Advanced = 20+ markets | AAOIFI-based (single) | **$399/mo** Commercial Basic; **$1,399/mo** Commercial Advanced |
| **Musaffa** | 120k+ securities, 70+ markets incl. **GCC + Malaysia**; Starter/Pro/Premium tiers | AAOIFI-based | **quote-only, contact sales** |
| Akinda / Finispia / HalalScreener | smaller | AAOIFI | not priced publicly |

**Caveat:** the head-to-head comparison found in search is published by Halal Terminal — one of the
vendors. Treat their relative rankings as marketing; the price points are each vendor's own
published figures and should be re-confirmed before any purchase.

## Scope

### Phase 1 — US universe from published Shariah ETF holdings (free, ships first)

A fetcher + cache that pulls the **primary standard's** holdings CSV, extracts `StockTicker` plus the
`Date` column as the **as-of stamp**, and exposes the set as the `halal` universe in place of
`DEFAULT_HALAL_DEMO_UNIVERSE`.

**DECIDED (Saiful, 2026-07-23): the standard is AAOIFI, sourced from SPUS — "for what it covers."**
That last clause is scope, not hedging: SPUS screens the S&P 500, so AAOIFI/SPUS is authoritative
for S&P 500 members and **silent — not negative — for everything else**. Build the three-state logic
around exactly that boundary.

**No failover, no union, no intersection** (see §3a: the sources disagree on 47.9% of the union).
HLAL is fetched as a *divergence monitor* only: log when FTSE and AAOIFI disagree on a name a user
holds or convenes, and surface it as the "standards differ" teaching moment — never as an input to
the verdict.

If the primary source is unavailable, the flag **degrades loudly** (constraint 3). It must never
quietly answer from the other standard.

The CSV carries non-equity rows (cash / CVR line items such as `003654100CVR`, `2602335D`) — filter
them, and assert a plausible row count so a truncated download cannot quietly shrink the universe.

### Phase 1b — UI copy (ships with Phase 1, same commit)

The DEF084 copy says "curated demonstration universe … not a Sharia screen." After Phase 1 that is
false in the other direction — it *is* a screen now, for what it covers. Replace it. Proposed EN
strings below; the build team may tighten wording, but must not drop the standard name, the source,
the as-of date, or the coverage boundary.

`settingsComplianceHalal` (toggle label)

> **Sharia screen — AAOIFI**

`settingsComplianceHalalSubtitle`

> **AAOIFI standard, S&P 500 Sharia index · as of {date}**

`_complianceExplanations['halal']` — title **"Sharia screen (AAOIFI)"**, body:

> Restricts trading to companies that pass the AAOIFI Sharia screen, as applied by S&P Dow Jones to
> the S&P 500 Sharia Industry Exclusions Index. AMI reads that index's published constituents — it
> does not run its own ruling. Currently {n} companies, as of {date}.
>
> Coverage is the S&P 500. A company outside it hasn't been screened by this standard, so AMI will
> tell you it's unscreened rather than guess.
>
> Sharia standards disagree. AAOIFI, DJIM, FTSE, MSCI and S&P apply different thresholds and
> denominators, so the same company can pass one and fail another — today, AAOIFI and FTSE differ on
> about half the names between them. This screen follows AAOIFI.

**The unknown state** — three states, and "unknown" must read as *no ruling*, not as a soft no.
Shown wherever a ticker's status appears (Room convene, trade rejection, watchlist):

- **Passes** → *"{TICKER} passes the AAOIFI screen (S&P 500 Sharia, as of {date})."*
- **Screened out** → *"{TICKER} is in the S&P 500 but does not pass the AAOIFI screen, so this
  mandate won't trade it."*
- **Unknown** → *"{TICKER} isn't in the S&P 500, so the AAOIFI screen AMI uses hasn't reviewed it.
  That's not a ruling either way — AMI doesn't know."*
- **Source unavailable / stale** (constraint 3, degrade loudly) → *"AMI couldn't refresh the Sharia
  screen (last updated {date}). The halal filter is paused until it can."*

Whether an unknown ticker is **blocked or permitted** with the disclosure attached is a behaviour
choice, not a copy choice — build team proposes, and it goes in the Gate at the end.

New/changed ARB keys need translator notes and stay **placeholder in AR and MS** until reviewed —
observance-sensitive, same posture as the DEF084 strings.

### Phase 2 — Malaysia via the SC SAC list

Parse the SC PDF into a ticker set versioned by its effective date. It is a **twice-yearly
snapshot**, so it needs an explicit staleness guard, not a silent stale read. Adds a PDF-parsing
dependency — flag it per the lean-stack rule before adding.

### Phase 3 — Vendor evaluation (decision doc only, no integration)

- Run Halal Terminal's free 500-calls/month tier against a sample; report **measured** agreement
  with the Phase-1 ETF-derived set.
- Request quotes from Musaffa and Zoya.
- Build the cost model from real call volume: convenes/month × tickers/convene × cache hit rate. A
  per-ticker verdict cached for a rebalance period is a very different bill from an uncached
  per-convene call.
- **GCC/Tadawul has no free authoritative source.** If GCC coverage is wanted it forces a paid
  vendor; Musaffa is the only one whose published coverage includes both GCC and Malaysia.
- Deliver a recommendation with numbers. **The buy decision is Saiful's.**

## Design constraints — these are the DEF084 lessons; the fix fails if it repeats them

1. **Name the standard, the source, and the as-of date** wherever the verdict is shown. Lesson
   `350_standards_differ_why_the_same_stock_flips` teaches that the same stock passes one standard
   and fails another — the product must not contradict its own curriculum. *"AAOIFI-aligned, per the
   S&P 500 Sharia Industry Exclusions Index, as of 22 Jul 2026"* is a claim we can defend.
2. **A universe is not a screen — three states, not two.** In-list = screened compliant. In the
   parent index but absent from the Shariah subset = screened out. **Not in the parent index at all
   = unknown**, and it must say so. Collapsing "unknown" into "haram" is a false assurance in the
   other direction; this is exactly why Phase 1 is a *universe* claim, not a *screen* claim.
3. **Degrade loudly** (CR040, fourth-occurrence class). If the fetch fails or the data is stale
   beyond its rebalance window, the flag fails **visibly** — never a silent fall back to a stale set
   or to today's 7-ticker list. This is an observance decision; silence is the worst outcome.
4. **Do not wire `sharia_screen()` to guessed inputs.** The three-ratio math stays dormant until a
   source supplies real debt / liquid-asset / impermissible-income figures — that is Phase 3, not
   Phase 1. Phase 1 is a sourced allowlist and must be described as one.
5. **Licensing is open, not resolved.** ETF holdings are published free under SEC daily-transparency
   rules, but index constituent lists and weights are separately licensed by S&P and FTSE, and
   FTSE's terms restrict using their data to build products. Reading a fund's regulatory disclosure
   is not obviously the same as licensing an index feed, and US case law is inconsistent on
   constituent lists. **Saiful should put this to the lawyer before Phase 1 is marketed** — it does
   not block building or internal testing.
6. **Content is gated on the product decision.** The 10 SHARIA lessons are still dark behind DEF082
   and 8 of 10 carry threshold errors (AAOIFI is 30/30/5, not the 33% they state). Per CR060 the
   ratio and ruling corrections go to Saiful or a qualified SME — never auto-fixed, never by the
   education lane. Do not correct lesson `355` until Phase 1's behaviour is locked, or it will
   document a behaviour that is about to change again.

## Guard

DEF084 already specified it and it is still unbuilt: **a test asserting every mandate flag is
enforced by the mechanism its user-facing copy describes.** For `halal` that means asserting the
enforcement path reads the sourced universe, and that the UI copy names the same standard and source
the code used. A flag whose only implementation is a literal set is exactly what this guard exists
to refuse. Ships in the same commit as the fix, per the `failure_patterns.md` house rule.

## Acceptance

1. Full backend unit suite green (886 at the last measured run), with the new guard proven **red
   before** the fix lands.
2. Fetcher test against a checked-in CSV fixture: 219 tickers parsed, junk rows dropped, as-of date
   extracted; a truncated or 500 response **raises** rather than yielding a short universe.
3. Enforcement behaviour: a `halal` mandate rejects a ticker absent from the sourced universe with a
   message naming the standard and date; a ticker outside the parent index returns **unknown**, not
   a rejection.
4. Live smoke after promotion: convene one name inside the set and one outside it, read the prompts
   back from `llm_audit`, and confirm the agents receive the sourced verdict **with its provenance**,
   not a bare boolean.
5. Phase 3 output is a numbers table — measured API agreement against the Phase-1 set and a real
   monthly cost at projected convene volume. No estimate stated as a measurement.

## Out of scope

- Any brokerage or real-trading integration (permanently out — simulation-only).
- Correcting the SHARIA lesson content (CR060 + SME escalation owns that; sequenced after Phase 1).
- Purchasing a vendor API — Phase 3 produces the recommendation; the decision is Saiful's.

## Governance

Commit tag `(AT:R<N> CR069)`. Closes the sourcing gap DEF084 left open (its Option 1) and supersedes
the Option-2 placeholder without removing its honesty. Relates to **CR046** (the screening math is
M13, already written and waiting), **CR040** (degrade loudly), **CR060** (Sharia content is
SME-escalated), and **DEF082** (lesson-gating sequencing).

---

## GATE — items needing Saiful, deliberately last

**None of these block Phase 1 or Phase 1b. Build now; these resolve in parallel.**

| # | Item | Blocks | Status |
|---|---|---|---|
| G1 | **Standard choice** — AAOIFI via SPUS, "for what it covers" | Phase 1 | **RESOLVED 2026-07-23** |
| G2 | **UI copy** — approve or tighten the Phase 1b strings | Phase 1b merge | **RESOLVED 2026-07-23** — build to the copy above |
| G3 | **Unknown-ticker behaviour** — block with disclosure, or permit with disclosure? Build team proposes; Saiful rules | nothing (default: **block + disclose**, the conservative read) | open |
| G4 | **Index-constituent licensing** — SEC daily-transparency publication is not obviously an S&P data licence; FTSE's terms restrict building products on their data; US case law inconsistent on constituent lists | **marketing/public launch only** — not building, not internal testing | open · lawyer |
| G5 | **Halal Terminal free-tier account** (500 calls/mo) — Saiful registers, Claude cannot self-serve | Phase 3 only | open |
| G6 | **Musaffa + Zoya quotes** — both quote-only/contact-sales | Phase 3 only | open |
| G7 | **SHARIA lesson corrections** — 8 of 10 carry threshold errors (AAOIFI is 30/30/5, not the 33% stated); 2 escalated on scholarly-position grounds. SME sign-off per CR060 | lesson content only; sequenced after Phase 1 behaviour locks; also behind DEF082 | open · SME |

G3 has a safe default so the build team is never stalled on it: **block and disclose**, using the
unknown-state copy in Phase 1b. If Saiful rules the other way it is a one-line change.
