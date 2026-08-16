# Batch Runs & the Results Store

**Built 2026-08-15.** Scripts: [`sample_universe.py`](../scripts/sample_universe.py),
[`batch_analysis.py`](../scripts/batch_analysis.py),
[`results_store.py`](../scripts/results_store.py)

Phase 2 works on single names. This is the machinery for running it across a
sector-stratified sample and keeping the output in a form that supports
analysis months later.

---

## 1. Sampling

`sample_universe.py` draws N tickers from the S&P 500 spread across all 11 GICS
sectors. The universe is scraped once and cached to `data/sp500_universe.csv`
(503 names), so runs don't depend on Wikipedia being up. Wikipedia returns 403
to pandas' default urllib user-agent — a real UA header is required.

Two modes:
- `proportional` (default) — mirrors index composition. Realistic mix.
- `equal` — same count per sector. **Better for bug-hunting**, because it
  over-samples the small, weird sectors (Energy, Materials, Real Estate) where
  the collector is most likely to break on unusual accounting.

```bash
python3 scripts/sample_universe.py -n 100 --seed 42 --out data/batch_seed42.csv
python3 scripts/sample_universe.py -n 100 --mode equal --plain   # pipeable
```

Sector diversity is the point: banks have no gross margin and carry deposits as
liabilities, REITs report FFO with huge depreciation, utilities are regulated
and debt-heavy. A sample of 100 tech names would validate almost nothing.

**Note:** the universe legitimately contains very recent spinoffs (`FDXF`
FedEx Freight, `HONA` Honeywell Aerospace). These are not parse errors. They
are also the names most likely to have thin statement history, so they are
worth keeping rather than filtering.

## 2. Measured throughput (GB10, 2026-08-15)

Fetch is negligible; **the LLM stage is the entire cost.**

| Stage | Measured | 100 tickers |
|---|---|---|
| yfinance + OpenBB fetch, 8 threads | 0.71 s/ticker, 0 failures / 32 | ~1–2 min |
| Qwen3.6, concurrency 8 | 9.86 s/ticker, 201 tok/s | 16.4 min |
| Qwen3.6, concurrency 12 | 8.43 s/ticker, 225 tok/s | 14.1 min |
| Qwen3.6, concurrency 16 | 6.32 s/ticker, 298 tok/s | 10.5 min |
| Nemotron 3.5, concurrency 4 | 76.7 s/ticker, 159 tok/s | ~2.1 hr |
| Nemotron 3.5, concurrency 8 | 76.8 s/ticker, 163 tok/s | ~2.1 hr |

Three findings worth keeping:

1. **Nemotron does not scale with concurrency.** conc 4 and conc 8 give
   identical per-ticker cost (76.7 vs 76.8 s). It saturates at ~160 tok/s
   because it emits ~12,000 tokens per analysis versus Qwen's ~2,000. Raising
   concurrency on it buys nothing. It is **~5× the cost** of Qwen for this job.
2. **Both models share one GPU.** `--model both` costs roughly the *sum*, not
   the max (~2.5–3 hr for 100). An early Qwen batch measured 32.1 s/ticker —
   3.4× its own benchmark — purely because a Nemotron benchmark was running
   concurrently. Always benchmark on an idle GPU.
3. **Port 8000 is production** (5 consumers). Concurrency there is additive
   load on them, which is why `--concurrency` defaults to 4 rather than the
   fastest setting. Runs are resumable, so an interruption only re-costs
   unfinished names.

## 3. Why results go in SQLite, not just CSV

**yfinance has no point-in-time history.** It serves current and *restated*
figures. A batch run is therefore a **perishable snapshot** — the exact numbers
a model saw today cannot be reconstructed tomorrow, or ever. This is the same
limitation that blocked Phase 1 backtesting ([lgbm_results.md](lgbm_results.md)),
and here it dictates the storage design.

If only the markdown prose is kept, every numeric input behind every verdict is
lost and the run becomes unauditable. So `results_store.py` persists three
layers per analysis:

1. **structured numeric inputs** — queryable, so verdicts can be correlated
   against ratios
2. **the full brief text** — the exact bytes the model was shown
3. **the full response** + parsed verdict fields

SQLite over CSV/parquet because it is a single file, needs no server, supports
real joins across runs and models, and survives partial writes.

### Schema

| Table | Grain | Purpose |
|---|---|---|
| `runs` | one per (batch, model) | timestamp, model, **prompt_sha**, seed, concurrency |
| `fundamentals` | one per (run, ticker) | numeric snapshot + `brief` + `info_json` |
| `analyses` | one per (run, ticker, model) | rating, conviction, timeframe, full `response`, tokens |
| `conflicts` | one per disagreement | cross-verification data-quality track |

Two views ship with it: `v_analysis` (flat verdict + numeric context join) and
`v_model_disagreement` (names where Qwen and Nemotron rated differently).

Design details that matter:

- **`prompt_sha`** hashes the system + user template, so a later analysis can
  tell which prompt version produced which verdict. Without it, results from
  before and after a prompt change are silently incomparable.
- **`price` and `as_of_utc` on every row.** This is deliberate: it makes
  forward returns computable later by joining future prices onto the analysis
  date. That is the only honest way to ask *"did the BUY calls actually work?"*
- **Annual balance-sheet figures are stored in separate `ann_*` columns** from
  the TTM/MRQ summary metrics. Mixing those two bases is precisely the bug that
  broke both models earlier; keeping them in distinct columns makes it
  structurally hard to repeat.
- Snapshots are written **before** the LLM is asked, so a run that dies
  mid-way still leaves a complete record of the perishable inputs.

### Usage

```bash
# run + store
python3 scripts/batch_analysis.py --csv data/batch_seed42.csv --model qwen --concurrency 6

# inspect
python3 scripts/results_store.py                       # row counts
python3 scripts/results_store.py --sql "SELECT * FROM v_analysis LIMIT 20"
python3 scripts/results_store.py --export tmp/export   # all tables to CSV
```

```python
from results_store import ResultsStore
st = ResultsStore()
df = st.to_frame("SELECT * FROM v_analysis")           # -> pandas
```

### Analyses this enables

- Does rating track valuation? (`GROUP BY rating` over `trailing_pe`,
  `debt_to_equity`) — on a 4-name smoke test, BUY averaged 16.7x P/E vs SELL at
  338x, so the verdicts are at least coherent with the inputs.
- Rating distribution by sector — does the model systematically dislike
  utilities or REITs?
- Qwen vs Nemotron disagreement rate, and whether it concentrates in particular
  sectors or in names with many data conflicts.
- Data-quality tracking over time from the `conflicts` table.
- **Forward-return scoring** once enough time has passed — join later prices on
  `ticker` + `as_of_utc`.

## 4. Confidence, scenarios and Expected Value

Added 2026-08-16. The verdict block already carried a categorical
`Conviction: HIGH/MEDIUM/LOW`; that is too coarse for the analysis this store
exists to support, so the model is now also asked for numbers.

### Two confidence numbers, deliberately not blended

- **`confidence`** (0-100) - P(the rating is the right call) over the stated
  time frame.
- **`data_confidence`** (0-100) - trust in the underlying figures, *independent
  of the analytical view*.

They are kept separate because `data_confidence` has an **objective external
check**: the `conflicts` table counts real cross-source disagreements for the
same ticker. So we can ask whether the model's stated doubt actually responds
to evidence, rather than being decorative. The `v_confidence_calibration` view
does exactly that.

**Result at n=100: `data_confidence` does NOT respond to real conflicts.**

An early 4-name smoke test suggested it did (95 → 63). That was noise. The
100-name run falsifies it:

| conflicts | n | avg confidence | avg data_confidence |
|---|---|---|---|
| 0 | 5 | 65.0 | 81.0 |
| 1 | 52 | 68.1 | 80.3 |
| 2 | 43 | 69.1 | 79.3 |

`corr(n_conflict, data_confidence) = -0.043` — indistinguishable from zero.

The cleanest evidence is an accidental natural experiment. **GOOG and GOOGL
both drew into the sample** — the same company, two share classes, with
effectively identical fundamentals (ROE identical to 5 decimal places, P/E
17.24 vs 17.36, 2 conflicts each). They received **data_confidence 90 and 70**.
A 20-point spread on the same data, and GOOGL omitted the fair-value line that
GOOG supplied.

`data_confidence` does vary (std 12.5, range 40–90) — it just doesn't vary with
the thing it claims to measure. **Treat it as unreliable.** The column is worth
keeping because the question is now measurable rather than assumed, but it
should not be used as a filter.

`confidence` has a related problem: **68 of 100 answers were exactly 65%**, and
only four distinct values appear (60/65/75/85), despite the prompt explicitly
asking for the full range. It is a categorical variable wearing numeric
clothing, and adds little over the HIGH/MEDIUM/LOW conviction it sits beside.

### Scenarios → EV

The model supplies a three-point distribution and a fair value:

```
- Bear case: NN% probability, target $NNN
- Base case: NN% probability, target $NNN
- Bull case: NN% probability, target $NNN
- Fair value: $NNN
```

**The LLM is explicitly forbidden from computing the expected value itself.**
The prompt says so ("Do NOT compute a weighted average or expected value
yourself... the arithmetic is done downstream") and `parse_scenarios()` does
the maths in Python. Two reasons:

1. Language models are unreliable at multi-step arithmetic.
2. A weighted average the model computes itself cannot be audited against its
   own inputs. Computing it here makes `ev_price` reproducible from the stored
   components — verified: an independent recompute matched all four stored
   values exactly.

`prob_sum` is stored rather than silently normalised. A set that doesn't sum to
~100 means the model didn't really construct a distribution, and that is worth
being able to filter on.

### The derived columns are disposable

Every raw input is persisted (`bear_prob`/`bear_target`, `base_*`, `bull_*`,
`fair_value`, `price`), so `ev_price`/`ev_return` can be regenerated at will —
or replaced with an entirely different formula — **without re-querying any
model**:

```python
st.recompute_ev(dry_run=True)                      # reproduces stored values
st.recompute_ev(fn=my_formula, dry_run=False)      # e.g. downside-weighted
```

Demonstrated: weighting the bear case double moved GOOGL from +2.9% to −0.7%
expected return, no LLM call involved.

### What this enables

- **Rating vs EV coherence.** On the smoke test GOOGL came back BUY with only
  **+2.9%** expected return — a BUY that the model's own distribution barely
  supports. That tension is invisible without EV and is now queryable.
- Ranking a watchlist by EV rather than by rating label.
- Calibration over time: do 75%-confidence calls actually resolve right ~75%
  of the time? Testable once forward prices exist, because `price` and
  `as_of_utc` are stored.

### Caveat that matters

LLM self-reported confidence is **generally poorly calibrated** — it tends to
correlate weakly with accuracy. Capturing it makes calibration measurable; it
does not make the number trustworthy yet. The same applies to the price
targets: they are the model's judgement, not a valuation model, and Phase 1's
result says the prior on any of this having predictive power should be
skeptical. Store it, test it, don't act on it as a probability.

## 5. First full run — 100 tickers, 11 sectors (2026-08-16)

`data/batch100_equal.csv` (seed 7, equal mode), Qwen3.6, concurrency 6,
`run_id=20260815T213336-qwen`.

**Pipeline held up completely.**

| Check | Result |
|---|---|
| Fetch | **100/100**, 0 failures, 46.7s (0.47 s/ticker) |
| Analyses | **100/100** ok, 19.8 min (11.9 s/ticker) |
| Rating / confidence / data_confidence / EV parsed | **100/100** |
| Fair value parsed | 99/100 |
| Scenario probabilities summing to exactly 100 | **100/100** |
| Cross-source conflicts flagged | 138 (~1.4/ticker) |

**EV is coherent with the rating**, with almost no overlap between bands:

| rating | n | mean EV | min | max |
|---|---|---|---|---|
| BUY | 26 | +7.8% | +1.3% | +16.3% |
| HOLD | 61 | −0.3% | −6.1% | +7.2% |
| SELL | 13 | −8.2% | −15.3% | +0.2% |

Extremes are sensible: TSLA SELL at 311x trailing P/E (−15.3% EV), ESS (REIT)
SELL at 44.9x, versus DIS/ORCL/EXPE BUY at 21–26x.

**There is a strong sector tilt**, and it is the main thing to be skeptical of:

| sector | BUY | HOLD | SELL | mean EV |
|---|---|---|---|---|
| Communication Services | 6 | 3 | 0 | +5.3% |
| Information Technology | 3 | 6 | 0 | +4.0% |
| Health Care | 4 | 5 | 0 | +3.5% |
| Financials | 3 | 6 | 0 | +2.2% |
| Energy | 3 | 6 | 1 | +1.2% |
| Utilities | 0 | **9** | 0 | +0.8% |
| Consumer Discretionary | 4 | 3 | 2 | +0.6% |
| Industrials | 1 | 7 | 1 | −0.6% |
| Consumer Staples | 2 | 4 | 3 | −2.0% |
| Real Estate | 0 | 7 | 2 | −2.3% |
| Materials | 0 | 5 | 4 | −4.0% |

Utilities came back **9/9 HOLD**; Materials and Real Estate produced **zero
BUYs**. This may be genuine — capital-intensive, rate-sensitive, low-growth
businesses do screen poorly on exactly these ratios — or it may be that the
prompt's implicit yardstick (margins, ROE, growth) is a poor fit for regulated
utilities and REITs, where FFO and rate base matter more than net margin. Open
thread #1 (sector-median comparison) addresses precisely this, and this run is
the evidence that it matters.

## 6. Standing caveat

A batch of verdicts is **opinion synthesis, not forecast**. Phase 1 established
this class of data has no usable predictive power. Storing prices for forward
scoring makes that testable — it does not presuppose the answer, and the
Phase 1 result says the prior should be skeptical.

---

# Market-Analyst Lens (added 2026-08-16)

Module: [`market_data.py`](../scripts/market_data.py) · run with
`--lens market`.

A **second, separate lens**. The fundamental analyst asks *what is this
business worth*; the market analyst asks *what is the tape saying and what is
the regime*. They are kept apart deliberately — the market brief contains **no
financial statements at all** — so the two verdicts stay independent and
comparable on the same name. Blending them would produce one muddy answer and
destroy the comparison.

## Why this was needed

An audit of what we were feeding the model showed Phase 1 covered ~2.5 of the 9
data categories a market analyst normally uses, and the Phase 2 fundamentals
brief covered about one (8 descriptive price fields). Worse, a scan of all 100
responses from the first full run showed the model cited those technical fields
**0/100 times** for 52-week high and **0/100** for the 200d MA. They were dead
weight.

## Coverage now

| Category | Status |
|---|---|
| Price & volume | ✅ 2y daily OHLCV |
| Derived technicals | ✅ MA stack (20/50/200), RSI, Bollinger z, drawdown, vol regime |
| Relative strength | ✅ vs SPY **and** vs the name's own sector ETF, 1m/3m/6m/12m |
| Cross-asset | ✅ SPY, VIX, 10y, 5y, dollar, HYG, LQD, oil, gold |
| Derived intermarket | ✅ credit appetite (HYG/LQD), yield curve (10y−5y) |
| Market breadth | ✅ computed across all **503** constituents |
| Positioning | ✅ short % float, days to cover, institutional/insider |
| Options | ✅ ATM IV, put/call OI, put−call skew, implied vs realised |
| Macro releases | ❌ needs FRED |
| Microstructure | ❌ needs paid tick/order-book data |

The regime block (cross-asset + breadth + sector RS) is identical for every
ticker, so it is fetched **once per run** (~15s) and prepended to each brief
rather than recomputed per name.

## Bugs found while building it

1. **tz-aware vs tz-naive index.** `Ticker.history()` returns a tz-aware index;
   `yf.download()` returns tz-naive. Joining them matched **zero rows**, so
   every relative-strength figure silently rendered as `n/a`. Fixed by
   normalising both to plain dates. This is the same class of failure as the
   Phase 1 BTC timezone leak — silent, and invisible unless you read the output.
2. **`period="1y"` returns ~251 rows**, but a 12-month return needs 253. Every
   12m cross-asset column rendered `n/a`. Fixed by fetching 2y and taking the
   trailing year for percentiles.

## First result — the two lenses genuinely disagree

Same four names, same model, same day:

| ticker | fundamental | market |
|---|---|---|
| GOOGL | BUY | **SELL** |
| LYV | SELL | **BUY** |
| FOX | BUY | **SELL** |
| PSKY | SELL | SELL |

Three of four flipped. That is the design working: two independent views on the
same asset, not one view restated.

**The market lens actually uses the new data**, unlike the old 8-field block.
Its LYV BUY cites +15.3% relative strength vs XLC (the weakest sector), 15.6%
short interest at 11.13 days to cover, position at the 52w high, and RSI 61.84
— then names $178 (the 50d MA) as the level that invalidates the call. Time
frame 4–8 weeks, properly shorter than the fundamental lens's 12–18 months.

Market-lens `data_confidence` also runs much higher (90–95% vs 60–95%), which
is coherent: price data has no cross-source conflicts to flag.

## The caveat that must travel with these results

**Phase 1 of this project tested price-derived technical features for
predictive power and found none** — best AUC 0.5528, negative edge against a
naive baseline in 30/32 cells, and a data ceiling rather than a model ceiling.

That finding is deliberately **kept out of the prompt**: telling the model its
inputs are useless would just make it hedge, and we want its genuine read. But
it belongs in every write-up. A market-lens verdict is a coherent reading of
the tape, not evidence the tape predicts anything. The `price` + `as_of_utc`
columns make it testable against forward returns, which is the only way this
question gets settled.

## Head-to-head: both lenses, same 100 names, same day (2026-08-16)

`run_id=20260815T223009-qwen` (market) vs `20260815T213336-qwen` (fundamental).
100/100 ok on both; market run 18.0 min (10.8 s/ticker), fetch 0.16 s/ticker
(no statements to pull).

### The two lenses are statistically independent

| | fundamental | market |
|---|---|---|
| BUY | 26 | 39 |
| HOLD | 61 | 30 |
| SELL | 13 | 31 |

Agreement matrix (rows = fundamental, cols = market):

| | BUY | HOLD | SELL |
|---|---|---|---|
| **BUY** | 14 | 6 | 6 |
| **HOLD** | 22 | 18 | 21 |
| **SELL** | 3 | 6 | 4 |

- Observed agreement **36%**
- Chance agreement from the marginals **32.5%**
- **Cohen's kappa = +0.052**
- Direct opposites (BUY vs SELL) **9/100**
- EV correlation between lenses **+0.085**

Kappa of 0.05 is indistinguishable from independence. The market view carries
essentially **no information** about the fundamental view. That is the strongest
possible confirmation that the two briefs are genuinely different questions and
not one question restated — the design goal — but it also means they cannot
both be right about the same names, and nothing here says which is.

The market lens is also markedly **more decisive** (30 HOLD vs 61), which is
what you would expect: a technical read resolves to a direction more readily
than a valuation does.

### The fundamental sector tilt does NOT reproduce

This was the key test. Sector-mean EV under each lens:

| sector | fundamental EV | market EV | fund BUYs | mkt BUYs |
|---|---|---|---|---|
| Materials | **−4.03%** | **+2.83%** | **0** | **5** |
| Real Estate | −2.32% | −0.64% | 0 | 1 |
| Consumer Staples | −1.99% | +2.44% | 2 | 4 |
| Industrials | −0.56% | +1.61% | 1 | 4 |
| Consumer Discretionary | +0.57% | +1.36% | 4 | 4 |
| Utilities | +0.83% | −0.79% | 0 | 1 |
| Energy | +1.23% | +1.18% | 3 | 4 |
| Financials | +2.15% | +3.22% | 3 | 5 |
| Health Care | +3.45% | +2.77% | 4 | 6 |
| Information Technology | +4.01% | +0.24% | 3 | 1 |
| Communication Services | **+5.25%** | +0.57% | 6 | 4 |

**Correlation of sector-mean EV across lenses: −0.132** — slightly *negative*.

Materials reverses outright: the worst sector on fundamentals (0 BUYs, −4.0% EV)
becomes one of the better ones on the tape (5 BUYs, +2.8%). Communication
Services and IT reverse the other way.

Two readings are live and this run cannot separate them:

1. The fundamental yardstick (margins, ROE, growth) is a poor fit for
   capital-intensive and cyclical sectors, so the tilt is an artefact — which
   is what open thread #1 (sector-median comparison) predicts and would fix.
2. The market lens is noise, and its sector pattern means nothing. Phase 1's
   negative result on technical features says keep this firmly on the table.

Only forward returns settle it, and `price` + `as_of_utc` are stored for both.

### Most interpretable disagreements

| ticker | sector | fundamental | market |
|---|---|---|---|
| ORCL | Info Tech | BUY +13.6% | SELL −3.5% |
| EL | Cons Staples | SELL −10.6% | BUY +6.8% |
| ALB | Materials | HOLD −2.7% | BUY +12.0% |
| IP | Materials | SELL −8.7% | BUY +8.0% |
| CI | Health Care | BUY +9.0% | SELL −3.2% |

ORCL is the textbook case: cheap on statements, but −37.7% over 12m, below its
200d MA with a bearish MA stack. Classic value-versus-momentum conflict, and
exactly the tension a single blended brief would have hidden.

### Schema bug found here

`CREATE VIEW IF NOT EXISTS` is a **no-op against an existing view**, so adding
`lens` to `analyses` left `v_analysis` silently on its old definition. Views are
pure derived definitions, so `ResultsStore` now **drops and recreates all views
on every open**. Rows written before the column existed were backfilled to
`lens='fundamental'`.

---

# Earnings-Quality Lens (added 2026-08-16)

Module: [`earnings_quality.py`](../scripts/earnings_quality.py) ·
`--lens quality`.

A **third lens, and the cheapest** — it needs no new data source. Every input
comes from the OpenBB statements the fundamental collector already fetches.
Only the question changes:

| lens | question |
|---|---|
| fundamental | what is this business worth? |
| market | what is the tape saying? |
| **quality** | **are these earnings real?** |

It targets a failure mode the other two structurally cannot see: a company can
post excellent margins and returns — which the fundamental lens rewards — while
net income quietly diverges from cash flow. It is given **no price and no
valuation multiples**, so the accounting view cannot be coloured by whether the
stock looks cheap.

Computed: CFO/NI, FCF/NI, Sloan accrual ratio; DSO/DPO/inventory-days trends;
full 8-factor Beneish M-score; normalized-vs-reported income, unusual items,
stock comp as % of revenue and of CFO; capex/D&A; goodwill/assets; interest
coverage; diluted share count.

## Read the GRADE, not the rating

`--lens quality` returned **69/99 BUY**, which looks like a broken lens. It
isn't: its BUY/HOLD/SELL answers *"is the accounting clean?"*, and for S&P 500
large caps the answer is usually yes. Its discriminating output is the grade,
now stored in its own `quality_grade` column:

| grade | n | mean EV |
|---|---|---|
| HIGH | 69 | +4.6% |
| ADEQUATE | 23 | −36.4% |
| QUESTIONABLE | 7 | −7.3% |
| POOR | 2 | −72.5% |

Nine names flagged QUESTIONABLE or POOR — the actual output of this lens:

| ticker | sector | grade | rating | conf | EV |
|---|---|---|---|---|---|
| IP | Materials | **POOR** | SELL | 85% | −95.1% |
| SOLV | Health Care | **POOR** | SELL | 75% | −49.9% |
| EL | Consumer Staples | QUESTIONABLE | HOLD | 70% | −145.9% |
| LEN | Cons Discretionary | QUESTIONABLE | SELL | 75% | −27.3% |
| MS | Financials | QUESTIONABLE | SELL | 70% | −22.9% |
| CVS | Health Care | QUESTIONABLE | HOLD | 70% | +121.7% |
| EW | Health Care | QUESTIONABLE | HOLD | 70% | +35.1% |
| LRCX | Info Tech | QUESTIONABLE | HOLD | 75% | −13.0% |
| NWSA | Comm Services | QUESTIONABLE | HOLD | 70% | +1.2% |

**Design lesson:** a new lens may not be comparable on the fields the existing
ones use. Forcing the quality lens into the shared BUY/HOLD/SELL vocabulary
made it look uninformative; its native vocabulary is a 4-level grade.

## Five bugs found building it

1. **`inventories`, not `inventory`.** OpenBB uses the plural. Every
   inventory-days cell rendered `n/a` — *including for a grocer*, which should
   have been the tell. Kroger now correctly shows 22–24 days.
2. **`or 0` turned missing into zero.** A missing receivables figure displayed
   as a confident **0.0 days DSO** — reads as "collects instantly" rather than
   "unknown".
3. **OpenBB's oldest period is a stub row** (mostly NaN), wasting one of only
   4–5 periods of trend. `.all(axis=1)` never fired because a few fields
   survive; switched to a 90%-null threshold.
4. **Unit mismatch → uniform −100% EV.** This lens anchors scenarios to
   *annual net income*, not price. The brief renders "$496.00M", so the model
   replied "target $496" — in millions — against a raw-dollar anchor. The
   parser now detects the scale gap and snaps to the nearest power of 1000
   (a no-op for the price-anchored lenses), and handles negative targets
   (`$-1.50B` is a legitimate bear case when the anchor is earnings) plus
   explicit B/M/K suffixes.
5. **Cross-unit fallback → EV of 2.5×10⁷.** `anchor = ev_anchor or currentPrice`
   silently substituted a *share price* for a *net-income* anchor whenever the
   former was missing. Root cause: **OpenBB's income schema varies by company**
   — utilities and some health-care names have no `net_income` column at all
   (AEE, ISRG), only `net_income_attributable_to_common_shareholders` or
   `net_income_continuous_operations`. That also degraded the *briefs*, not just
   the EV: 2/99 showed "Net income: n/a" throughout, so the model assessed cash
   backing with no numerator. Fixed with a wider lookup chain; EV now never
   falls back across units. Those 2 names were re-run; the other 97 were valid.

## Three-way comparison: all lenses are mutually independent

| pair | n | agreement | Cohen's kappa |
|---|---|---|---|
| fundamental vs market | 100 | 36% | **+0.052** |
| fundamental vs quality | 99 | 39% | **+0.071** |
| market vs quality | 99 | 32% | **−0.068** |

EV correlations: fund↔market **+0.085**, fund↔quality **−0.021**,
market↔quality **−0.090**.

All three kappas are indistinguishable from zero. The three lenses are
**mutually independent signals**. That is the strongest confirmation that they
ask genuinely different questions rather than restating one — but independence
is not validity. Three uncorrelated signals are only useful if at least one has
predictive power, and nothing here establishes that for any of them. Phase 1
says hold the market lens to a especially sceptical standard.

`price` and `as_of_utc` are stored for all three, so forward returns will
eventually settle which (if any) is worth anything.
