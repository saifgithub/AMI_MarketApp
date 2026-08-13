# CR166 — Census the data we already hold, before adding one more field by hand

**Filed:** 2026-08-11 · **Status:** proposed · **Decision:** Saiful, 2026-08-11 — *"look at what else we can give the agents to help with the decisions. how do we determine what else the agents need? remember we do not let the agent calculate. all numbers should be provided."*
**Source:** a live Room convene for AAPL benchmarked against an external TradingAgents report for the same ticker and date, then a supply-side audit of `fundamentals.py`, `technicals.py`, `market_data.py` and `room_prompts.py`.

---

## Why

We are discovering missing fact-sheet fields **one at a time, by hand, per agent**, and each discovery
costs a full review cycle.

- CR145 Tier A found `marketCap`, `freeCashflow` and `totalDebt` — *"all three already fetched then
  discarded"* — via a data-sufficiency review of one agent.
- CR150 found beta, volatility and short interest missing from the Bear's sheet by reviewing the Bear.
- CR152 found five compliance inputs *"promised and never rendered, all already computed"* by
  reviewing the Trader.

Each is correct. Together they are a pattern nobody has named: **the same root cause is being
rediscovered per agent, and no one has looked at the whole supply.** Market cap is the proof —
the mandate carried *"Avoid microcaps (< $500M market cap)"* as a HARD constraint in 17 of 18 prompts
while 0 of 18 fact sheets stated one, and the rule sat unfollowable for months because the field was
never *missing*; it was fetched and thrown away.

**So we ran the census.** Measured 2026-08-11 against live yfinance:

| | count |
|---|---|
| Keys returned by the single `yf.Ticker(t).info` call we already make | **180** |
| Of those, numeric | 132 |
| Keys we actually read (`fundamentals.py` + `market_data.py`) | **23** |
| **Numeric fields already in memory and never passed to any agent** | **112** |

One network call. We use 23 keys of 180. There is no second fetch, no cache to build, and no new
provider in that number — CR145 Tier D is blocked on a fundamentals cache because it proposes
*additional* calls (`.income_stmt`, `.cashflow`); **this CR proposes zero additional calls.**

Availability is checked, not assumed. Across AAPL / PLTR / RIVN / SNDK — a mega-cap, a high-multiple
grower, a loss-maker and a mid-cap — 29–33 of the 33 candidate fields are present, and every absence
is semantically meaningful (no dividend → no `dividendDate`; SNDK has no `beta` or `debtToEquity`),
which is exactly what CR104's per-field `field_state` gating already renders correctly.

### The prompts are being corrected against the wrong side of the mismatch

`content/agents/fundamentals_analyst.md` currently instructs the agent:

> *"The margin figure is `profitMargins`, i.e. net; **no gross margin** and no margin *trend* is
> computed, so do not describe either"*

`grossMargins` is in the `info` dict we already fetch (AAPL: 0.48653). So is `operatingMargins`
(0.32623) and `ebitdaMargins` (0.35979). CR145 Batch 6 resolved the documented mismatch by **deleting
the demand** — removing the gross-margin ask from the role text. Against a field we hold, that is the
wrong direction, and it is the specific failure mode a census prevents: without an inventory, a
prompt/data mismatch looks like an over-ambitious prompt every time, never like an under-served one.

(The *trend* half of that sentence stays correct — `info` is point-in-time and a margin series needs
`.income_stmt`, which is CR145 Tier D and stays there.)

---

## How we determine what the agents need — the method

Saiful's constraint is the instrument. **If agents never calculate, then every number an agent states
must already be on its sheet** — so the gap is a *measurable residual*, not a judgement call:

> **Need = numbers agents state − numbers we gave them.**

`scripts/prompt_quality_sweep.py` M3 already computes exactly this, classing every numeric token as
**grounded** (in the agent's own sheet), **inherited** (in the transcript it was handed), or **novel**.
Novel *is* the residual. M3 stops at counting it. Three legs make it a determination method:

### Leg 1 — triage the residual (measured; the main instrument)

Split "novel" four ways. Each bucket has one fixed remedy, so the output is a work list:

| Bucket | Test | Remedy |
|---|---|---|
| **Derivable** | a function of fields already on the sheet | **Precompute and hand it over.** Required by the no-calculation rule |
| **Sourceable** | a real field we hold or can fetch | Render it (this CR) or file the fetch |
| **Unsourceable** | no real source | Forbid explicitly and state the absence — CR038 / DEF053 precedent |
| **Out of lane** | real and live, but another desk's | CR145's firewall owns it; this count is the firewall's regression metric |

The derivable bucket carries a free correctness check: recompute each figure and compare. Mismatches
are defects. This is how DEF066 → DEF235 → DEF241 were each found individually — and a fourth
instance is already in hand (below). A sweep finds the rest in one pass instead of one per quarter.

### Leg 2 — the unfollowable-constraint audit (static, cheap, run first)

For every mandate constraint and every `enforce_safety_floor` check, ask whether each number needed
to evaluate it is on the sheet. No runs required. This is the method that found market cap; CR152
Finding 4 found five more the same way for one agent. It has never been run across all rules.

### Leg 3 — the job-description audit (judged; goes last)

For each of the 12 roles, what question is it asked and what is the minimum input set? This is the
only leg that catches what Leg 1 structurally cannot. **Leg 1 is a lagging indicator**: it measures
demand for numbers agents think to reach for. A Market Analyst that has never been given a 200-day
SMA does not write *"200-day unavailable"* — it simply never discusses the primary trend, and the
residual stays silent. Leg 3 is where that shows up, which is why it is judged and checked against
Legs 1–2 rather than leading.

---

## Scope

### Tier A — the census itself (the durable deliverable)

A script that diffs *fetched* against *rendered* and fails when the gap grows: enumerate every key the
`info` call returns, every field `compute_technicals` computes, and every field the `Quote` /
`EarningsInfo` objects carry, minus everything `_format_profile` can render. **The point is not this
one-off list — it is that the next field cannot hide for months.** Pairs with
`test_prompt_data_parity.py`, which asks whether a *computed* field is rendered anywhere; this asks
the question one layer earlier, of *fetched* fields.

### Tier B — fields already fetched, never passed, that bind to a stated rule or job line

Every entry must name the rule or role-text line it serves, and a lane. Nothing enters on
availability alone.

**Fundamentals lane**

| Field | Binds to |
|---|---|
| `trailingEps` | We render a P/E on two bases with no earnings behind either. Nothing on the sheet lets the agent sanity-check the multiple it quotes |
| `totalRevenue`, `revenuePerShare` | We render growth % with no base. 16% of what is not answerable |
| `grossMargins`, `operatingMargins`, `ebitdaMargins` | Role text: *"Prioritise durable margins."* One net figure is not a margin structure |
| `returnOnEquity`, `returnOnAssets` | Role text: *"balance sheet strength"* — currently served by two debt figures and nothing on returns |
| `currentRatio`, `quickRatio`, `debtToEquity` | Same line. Liquidity and leverage are the standard reads and all three are held |
| `payoutRatio`, `trailingAnnualDividendRate`, `dividendDate` | Role text: *"capital allocation."* A yield alone cannot say whether the dividend is covered. `ex_dividend_date` + `dividend_rate` are **already on the `EarningsInfo` object the Room renders the earnings line from** (CR030) and are dropped at the render site |
| `numberOfAnalystOpinions`, `targetHighPrice`, `targetLowPrice`, `targetMedianPrice`, `recommendationMean` | We render *"buy, target $322.28"* and hide that 41 analysts back it with a 215–400 dispersion. A consensus with no spread reads as precision we do not have |
| `heldPercentInstitutions`, `heldPercentInsiders`, `sharesOutstanding`, `floatShares` | Ownership base for the liquidity constraint market cap only half-serves |

**Technicals lane**

| Field | Binds to |
|---|---|
| `twoHundredDayAverage` + `twoHundredDayAverageChangePercent` | **Zero hits for "200-day" anywhere in the CR or defect registers.** No agent can discuss the primary trend. `compute_technicals` pulls only 3 months (`_HISTORY_PERIOD = "3m"`, ~65 bars) so it *cannot* compute one — but the value is sitting in the `info` dict already fetched. No longer history needed |
| `previousClose` + `regularMarketChangePercent`, `dayHigh`, `dayLow`, `open` | The sheet states a price and never says whether it moved. `Quote` already carries `change_pct` and `market_state`; grep finds **zero** references to either in `room_prompts.py` or `room_runner.py` |
| `52WeekChange` + `SandP52WeekChange` | Relative strength against the index, already in the dict. Neither agent nor mandate can currently ask "versus what?" |
| `averageVolume`, `averageDailyVolume10Day` | We render a volume *ratio*; the absolute base is what makes a liquidity rule checkable |
| `fiftyDayAverage` | We compute our own from 3 months of bars. Rendering the provider's alongside is a free cross-check, not a duplicate — a divergence is a data-quality signal (`_reference_price_line` already reconciles exactly this shape for price) |

### Tier C — the derived figures we still make agents assemble

Under the no-calculation rule these are not optional. Handed over as scalars, labelled *AMI computed
this — quote it, do not recompute it*, per the DEF241 pattern.

- **% distance from the anchor to every level on the sheet.** We do this for the consensus target,
  the 50-day range low, both 52-week ends and the 50-day SMA. Not for the 20-day SMA or the 50-day
  range **high** — the two an agent reaches for when arguing upside.
- **Position size in shares and dollars** at the mandate cap for this price. `trading_math/portfolio.py`
  already converts size% → quantity; the agents get the percentage and do the rest in prose.

### Tier D — a defect this audit surfaced, needing its own ID

`aggressive_debator` stated a *"0.30 pt portfolio-drawdown contribution from a 3.0% position with a
6.0% stop"* on the AAPL run of 2026-08-11 10:46 UTC. The correct figure is 3.0 × 6.0 / 100 = **0.18 pt**,
which the prompt supplied and which the Conservative and Neutral debators both quoted correctly.

This is **the fourth instance of DEF066's class** (DEF066 the formula, DEF235 the parser feeding it,
DEF241 the agent doing it in prose) and it **slips DEF241's guard**: the *"YOUR position — AMI computed
this"* line is appended only when the agent's size differs from the reference ceiling
(`abs(agent_size_pct - size) > 0.01`, `room_prompts.py:411`), and the Aggressive debator argues *at*
the ceiling — so it receives the reference line only, and still restated it wrong. Needs a DEF ID
minted before it can be filed.

---

## Explicitly NOT in this CR

Checked against the register rather than assumed. **Several fields I would otherwise have proposed are
already claimed, and re-proposing them would have been the exact per-agent rediscovery this CR is
filed against:**

- **ATR / realised volatility** — claimed by **CR152** (*"free math over OHLC already pulled"*, deferred
  behind CR145 Tier C) and by **CR150**. **Explicitly REJECTED for the Market Analyst by CR146**, which
  replayed the evidence and ruled *"ATR keeps its merit as a stop-distance input for the Trader, a
  different CR."* Not reopened here.
- **Beta, short interest** — claimed by **CR150**, with the *"reported-as-of, not live"* labelling
  requirement short interest needs (`dateShortInterest` lags ~2 weeks). Listed in the census for
  completeness; not re-proposed.
- **Margin *trend*, buybacks** — CR145 Tier D, correctly blocked on the absent fundamentals cache
  because both need `.income_stmt` / `.cashflow`, i.e. additional calls.
- **Raw OHLCV bars in the prompt** — rejected by CR146 on budget, and it would hand agents a series to
  compute from, which is precisely what the no-calculation rule forbids.
- **Revenue segments, M&A history, company guidance** — CR145's out-of-scope list; need a new provider.
- **Governance risk scores** (`auditRisk`, `boardRisk`, `overallRisk`, `compensationRisk`) — in the dict,
  **rejected**: opaque proprietary scores with no published methodology. We would be lending a number
  our own credibility without being able to say what it measures.
- **`allTimeLow`** — rejected: split-adjusted to $0.049 for AAPL. Arithmetically true, analytically
  meaningless, and a number an agent could build a "99.98% above the low" claim on.
- **Bid/ask/size, `sourceInterval`, epoch and gmt-offset fields** — rejected as microstructure and
  plumbing with no bearing on a long-horizon simulated decision.

---

## Risks, and the argument against this CR

**This CR pushes directly against CR145 Tier C, which shipped six days after being filed and made the
sheets *smaller*** — fundamentals −30.5%, market −53.9%, news −53.0%, social −54.8%. Adding fields
re-inflates exactly what that tier reduced. The tension is real and is the central design question
here, not a footnote.

Three things resolve it, and they are conditions of shipping, not mitigations:

1. **Lane assignment is mandatory per field.** CR145 reduced sheets by removing *other desks'* data,
   not by removing depth. Adding depth *within* a lane is the complementary move; adding an unassigned
   field to the shared block is the thing CR145 forbids.
2. **Every field names the rule or role line it serves.** A field that cannot is rejected — see the
   rejected list, which is the discipline being applied rather than described.
3. **Net against deletions.** The Market Analyst's sheet lost 53.9%; it can afford a primary-trend
   line. The full-sheet agents cannot afford all of Tier B and should take Tier C first.

**The honest weakness of this CR is that the census measures *supply*, not *demand*.** 112 unused
fields is a fact about our code, not evidence any agent needs them. Leg 1's residual is the demand
measurement. ~~It has not been run~~ — **AMENDED 2026-08-13, see below: it has, and it changed this
CR's own recommendation.** Tier B remains a **ranked hypothesis set**, not a proven roster; Leg 1
tells us which lane is demanding, never which specific field would satisfy it.

**A second-order risk:** more numbers is not more reasoning. Our AAPL run put twelve agents on roughly
six shared figures; the failure was information *diversity*, and a wider sheet could as easily produce
twelve agents reciting sixty figures. Leg 1's re-measure is what would detect that, and it is the
acceptance gate below for exactly that reason.

**Latency:** `fundamentals.py` has no cache — every convene and every 1-on-1 message fetches live
(CR145 Tier D). Tier B adds no calls, so it adds no latency; it also does nothing about the fact that
an uncached `.info` call already sits on the Room's critical path.

---

## Acceptance

Structured so it cannot be claimed by inspection — the CR145 Tier A/C precedent, which correctly
refused to claim response-side effects.

1. **Tier A:** the census script runs in CI and fails when a fetched field reaches no agent, in either
   direction (a rendered field with no fetch, a fetched field with no render). Union-of-lanes stays
   equal to the full sheet, per `test_the_union_of_all_lanes_is_the_full_sheet`.
2. **Tier B/C:** per-field `field_state` provenance (CR104), absent rather than labelled when not live
   (DEF053), rendered on **both** surfaces so Room and 1-on-1 cannot state different figures for the
   same company (the `pe_line` / `Company size` precedent).
3. **The gate that matters:** a post-promotion re-measure of Leg 1 on ≥30 convenes, comparing
   grounded / inherited / novel rates against a pre-change baseline on the same prompt epoch.
   **Novel should fall.** If it does not, the fields were not the constraint and Tier B should be
   partially reverted rather than extended. A prompt or data change whose effect is not re-measured is
   the CR105 Amendment-1 trap.
4. **NOT claimed on merge:** that any agent *uses* a new field, that reasoning quality improved, or
   that the residual closed. All three are response-side and need a post-promotion corpus.

---

## AMENDMENT 1 — 2026-08-13: Leg 1 was already run, and it flipped this CR's recommendation

**Leg 1 did not need commissioning.** The post-Batch-9 re-measurement (`421e0a98`, 2026-08-13) ran 40
live convenes on the same 13 tickers as the 08-07 epoch and explicitly graded this CR:

> *"M3 is CR166's own acceptance gate and it passed: novel fell."* — 4.3% → **2.7%** (grounded 92.6%
> → 95.3%).

The corpus is committed at `../CR143_agent_prompt_audit/corpus/*_2026-08-13-epoch.json`, and it is
valid on the **current** epoch: no commit since has touched `room_prompts.py`, `room_runner.py`,
`fundamentals.py`, `technicals.py` or `content/agents/`, and Alpha's deployed `room_prompts.py` /
`room_runner.py` md5s match local HEAD (verified 2026-08-13). So the ~40-convene / ~2 h / ~480-credit
cost this CR budgeted for Leg 1 is **zero**, and the same-epoch baseline the acceptance gate demands
already exists.

**It also contradicted this CR's own lane recommendation.** Per-agent M3:

```text
market_analyst        3.1 → 0.6      research_manager      1.0 → 2.8   ↑
conservative_debator  5.4 → 1.2      fundamentals_analyst  2.3 → 3.6   ↑
neutral_debator       5.6 → 1.6      news_analyst          0.0 → 1.1   ↑
bull_researcher       7.5 → 2.8      trader                6.7 → 4.7
aggressive_debator    4.9 → 2.7      bear_researcher       6.0 → 4.8
social_media_analyst  0.0 → 0.0
```

The original recommendation was **technicals lane first**, on the Leg 3 argument that the 200-day gap
is the clearest structural hole. The measurement says the technicals lane is now the *cleanest* read
in the Room (0.6%) — Batch 6 handed the Market Analyst SMA-20/50, the volume ratio and the 52-week
distances, and *"an agent given the number stops inventing it."* The lane with rising, measured demand
is **fundamentals** (2.3 → 3.6), and the memo's own second reading explains why: Batch 5 firewalled
`fundamentals_analyst` **out of** technicals/news/social, so it may be starved in its own lane.

**This does not retire the 200-day argument.** Leg 3 exists precisely because Leg 1 is a lagging
indicator: an agent never given a 200-day SMA does not write *"200-day unavailable"*, it simply never
discusses the primary trend, so 0.6% novel is blindness on that field, not sufficiency. Technicals
moves to a later stage on **relative** return, not because the hole closed.

## Decisions taken — Saiful, 2026-08-13

1. **Tier B ships, staged, lane-assigned — `fundamentals` lane FIRST** (revised from technicals on the
   Amendment-1 evidence above). Technicals follows after the re-measure.
2. **Leg 1 before Tier B — satisfied** by the 08-13 corpus; no new run commissioned.
3. **Gross margin: supply the field and restore the ask.** `grossMargins` / `operatingMargins` /
   `ebitdaMargins` render; the margin-structure line returns to `fundamentals_analyst.md`. The margin
   *trend* half of the disclosure stays correct and stays in CR145 Tier D.
4. **Tier D stays inside CR166** — no separate DEF ID minted for the `aggressive_debator` 0.30-vs-0.18
   recurrence.

**Stage 1 scope** (this CR's first promotion): Tier A census guard + Tier B fundamentals lane +
decision 3 + Tier D + **the folded CR168 identity fields** (`longName`, `exchange`). Identity rides
Stage 1 because it is the same dict, the same fetcher and the same renderer — and because it is
**string-only**: M3 counts numeric tokens, so it cannot move the novel rate and cannot confound this
stage's gate. The other four touch **different agents**, so the per-agent M3 re-measure still
attributes cleanly — deliberately not the bundling the 08-13 memo criticised in its own results.

**Stage 1's specific gate:** `fundamentals_analyst` novel falls from **3.6%**, `aggressive_debator`
from **2.7%**, both against the 08-13 corpus. If fundamentals does not fall, the memo's *"more supplied
numbers invite more derived ones"* reading gains support and Tier B is partially reverted rather than
extended.

---

## Superseded — original open decisions (kept for the record)

1. **Does Tier B ship at all, given CR145 Tier C just cut the sheets in half?** This is the design
   decision, and it is the same shape as the one Saiful took for CR145 Tier C (default-open vs
   firewall). Recommend: yes, but lane-assigned and staged — technicals lane first (it lost the most
   and the 200-day gap is the clearest single hole). — **SUPERSEDED by Amendment 1: fundamentals
   first.**
2. **Do we run Leg 1 before or after Tier B?** Running it first makes Tier B evidence-led and costs
   ~40 convenes (~2 h, ~480 credits) plus a frozen prompt epoch. Running it after makes Tier B a
   hypothesis the same measurement then grades. Recommend: **before** — it is the only thing that
   converts this from a well-argued list into a determination.
3. **Gross margin — supply the field or keep the deletion?** CR145 Batch 6 removed the demand. The
   field is held. One of the two should change.
