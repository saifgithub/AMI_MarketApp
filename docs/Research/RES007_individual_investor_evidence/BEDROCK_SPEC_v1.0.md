# BEDROCK
## US Mid-Cap Fundamental Systematic Portfolio
### Build Specification v1.0

Prepared by ATM Market Intel (AMI) Research
Date: 10 September 2026
Status: Decision-complete. Intended as the primary input to a Claude Code builder session.
Principal: Saiful. All design decisions were delegated to AMI Research and are logged in Section 1. The only decisions reserved for the principal are those involving spending (Section 11).

---

## 0. Summary

What: a long-only, 50-name, monthly-rebalanced portfolio of US mid-cap common stocks, selected by a fundamental composite score, with an insider-activity block and a filing-text-change block layered on in later phases.

Where the edge is expected to come from. Three sources, all of which are strongest where analyst attention is thin:

1. Slow diffusion of fundamental information (post-earnings drift, fundamental momentum).
2. Informed but unwatched parties (insider open-market purchases, 8-K event codes).
3. Unread text (year-over-year changes in 10-K risk factors and MD&A, the "Lazy Prices" effect).

Numerical factors alone are a known and crowded edge. The differentiation is (a) the text block, which requires a filing pipeline that participants at this capital scale rarely build, and (b) validation discipline that most participants skip.

Realistic outcome if everything works: 2% to 4% a year over the mid-cap benchmark net of costs, live information ratio 0.3 to 0.5, with relative drawdowns that can last two to three years. Expect live performance to be roughly half of the development backtest. If that bar is not worth the effort, stop here.

Kill criteria are numeric and are fixed before any backtest is run (Section 9). Budget: one data subscription (Section 11). Everything else is free or already owned.

---

## 1. Decision log

| # | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | Market | US-listed common stock | Point-in-time fundamentals, delisted coverage and a free filing corpus exist. No comparable stack exists for KSA. |
| D2 | Cap band | Market-cap rank 301 to 1200, re-ranked monthly | Rank-based definitions are stable across 26 years; dollar thresholds drift. Roughly Russell Midcap plus upper small cap. |
| D3 | Direction | Long-only. Short-leg information is used only as exclusions | Mid-cap borrow cost and squeeze risk destroy the short leg's paper alpha. |
| D4 | Holding style | Monthly rebalance with rank buffers; one-way turnover target under 100% a year | The edge is diffusion speed, not prediction. Costs must stay below the signal. |
| D5 | Model | Fixed-weight linear composite (primary); regularised gradient-boosted ranker (challenger, Phase 4) | Fixed weights cannot overfit. The challenger must beat them out of sample or be discarded. |
| D6 | Data | Sharadar (fundamentals, prices, actions, events, insiders); SEC EDGAR (text); Ken French library (factor returns) | Sharadar is the only point-in-time, survivorship-free source at personal-licence cost. |
| D7 | Development and holdout split | Development 2000-01 to 2016-12; holdout 2017-01 to 2026-08, run once | The holdout covers the 2018 Q4, 2020 and 2022 regimes. |
| D8 | Neutralisation | Sector-neutral (Sharadar `sector`) and size-neutral within the band | Otherwise "value" silently becomes "long energy, short software". |
| D9 | Boring overlay | Built as a configurable filter, default off, cost measured explicitly | It is a preference, not an alpha source. Measure what it costs before keeping it. |
| D10 | GB10 role | EDGAR text pipeline only (embeddings and LLM classification, batch) | The numeric pipeline needs no GPU and must run on any laptop. |
| D11 | Spec lineage | Clean specification; SPEC-HIGH-LEVEL v0.2 is not extended | v0.2 is outside this project's scope. A clean restatement is cheaper than reconciling two documents. |
| D12 | Codename | BEDROCK | Matches the mandate: unglamorous businesses, fundamentals first. |

---

## 2. Objective and benchmarks

Objective: maximise net information ratio against Benchmark A, subject to the turnover and concentration limits in Section 7.

Benchmark A (primary): the equal-weighted monthly return of the eligible universe defined in Section 3. This isolates stock selection from size and equal-weight effects.

Benchmark B (secondary, the opportunity cost): S&P MidCap 400 total return, investable through IJH or MDY.

Report both. A strategy that beats A but not B is a stock picker losing to its own construction. A strategy that beats B but not A is riding an equal-weight premium and has no selection skill.

---

## 3. Universe

Computed at each month-end T from Sharadar `tickers`, `daily` and `stocks`:

1. `category` is Domestic Common Stock. This excludes ADRs, preferreds, funds and secondary share classes.
2. Primary exchange is NYSE, Nasdaq or NYSE American.
3. Exclude `sector` in {Financial Services, Real Estate}. Their accounting does not compare and their signals need separate treatment. Utilities stay in.
4. Exclude biotechnology and pharmaceutical names with trailing-four-quarter revenue below USD 50m (pre-revenue drug developers).
5. Unadjusted price at T is at least USD 5.
6. At least 8 quarters of ARQ fundamentals with non-null revenue and total assets are usable at T. This also excludes IPOs younger than roughly two years, a known negative-return cohort.
7. Rank all survivors of steps 1 to 6 by `marketcap` at T; keep ranks 301 to 1200.
8. Within the band, drop the bottom 10% by 63-day median dollar volume.

Expected size: 800 to 950 names per month. Membership is stored as a table keyed by month-end. Nothing downstream may query membership for a date other than the one being scored (leakage test L2, Section 9).

Delisting handling. Sharadar `actions` provides delisting dates; `tickers.isdelisted` and `lastpricedate` corroborate. Rules:
- Acquisition or merger (an `acquisitionby` action precedes the delisting): the last traded price is the exit price.
- Everything else (bankruptcy, liquidation, exchange-initiated, or no action record at all): apply a -30% return on the delisting day to the last traded price (the Shumway 1997 convention), then exit.
- The haircut is a config parameter. Sensitivity at -50% must be reported alongside every gate report.

Optional filters (config flags, default off):
- BORING overlay (Section 5.6).
- Shariah screen (AAOIFI-style ratios: total debt to market cap below 33%, interest-bearing securities to market cap below 33%, non-permissible revenue below 5%; plus sector exclusions). Included because a shariah-preferred sleeve exists elsewhere in the principal's architecture. Not applied to the base case.

---

## 4. Data

### 4.1 Sharadar (personal-use licence, direct from sharadar.com)

Tables and their role:

- `fundamentals`, dimension ARQ only. MRQ, MRY and MRT are never read in any research path. `datekey` (the filing date) is the only date used for availability. `calendardate` and `reportperiod` are used for seasonal alignment only.
- `daily`: market cap, EV and precomputed ratios by trading day. Used for universe ranking only. Every ratio inside a signal is recomputed from ARQ so that the lag is controlled in one place.
- `stocks` (SEP): daily OHLCV, split-adjusted and dividend-adjusted. Total return is computed from `closeadj`.
- `actions`: splits, dividends, spin-offs, delistings, acquisitions, ticker changes.
- `events`: 8-K item codes since 1993. Used in Phase 2 (Section 5.4).
- `insiders`: Forms 3, 4 and 5 since 2005. Used in Phase 2 (Section 5.3). Availability is `filingdate`, never `transactiondate`.
- `tickers`: securities master. `permaticker` is the join key everywhere; `ticker` is reused across companies and is never a key. The CIK is parsed from the `secfilings` URL for the EDGAR join.
- `sp500`: not used for selection. Used once, to confirm the strategy is not accidentally an index-inclusion trade.
- `descriptions`: the indicator code map. The field names used in Section 5 (revenue, cor, ebit, ebitda, netinc, ncfo, capex, ncfdiv, ncfcommon, assets, debt, cashneq, eps, marketcap, ev) must be verified against this table at build time before any feature code is written.

Availability rule: a fundamental record with `datekey` = d becomes usable at the close of the first trading day strictly after d. One extra day of conservatism is cheap. One day of leakage is fatal.

### 4.2 SEC EDGAR (free)

- Quarterly full-index files enumerate 10-K, 10-K405, 10-KSB, 10-Q and 10-QSB filings per CIK.
- Fetch primary documents with a declared User-Agent header at no more than 10 requests per second (SEC fair-access policy). Roughly 90,000 filings for the universe; a few hours of wall time at the limit.
- Store extracted items only: Item 1A and Item 7 from 10-K; Item 2 from 10-Q. Gzip, keyed by (cik, accession, form, period). Raw HTML is discarded after extraction, or kept compressed if disk allows.
- Item 1A (risk factors) only exists for fiscal years ending on or after 1 December 2005. The full text signal therefore starts in 2006; before that only MD&A similarity is computed.

### 4.3 Ken French Data Library (free)

Fama-French five factors plus momentum, monthly. Used for attribution regressions only.

### 4.4 Explicitly excluded

Analyst estimates (not in Sharadar, and mid-cap consensus is thin anyway). Earnings-call transcripts (proprietary; a spending decision and a scraping liability). Short interest (FINRA data is free but the join is awkward; deferred to a later version). Any current-view API of any kind.

---

## 5. Signals

All raw metrics are computed per (permaticker, month-end T) from the latest usable ARQ records. TTM means the sum of the latest four usable quarters. Every signal is then: winsorised at the 1st and 99th percentiles cross-sectionally, z-scored within `sector`, then residualised against log(marketcap) within the band. Higher is better in every case; signs are applied at definition.

### 5.1 Value block (V)

- EBIT yield = ebit_TTM / ev, where ev = marketcap + debt - cashneq from ARQ, not from `daily`.
- FCF yield = (ncfo_TTM - capex_TTM) / ev.
- Net payout yield = (dividends paid_TTM + net share repurchases_TTM) / marketcap, from `ncfdiv` and `ncfcommon` with signs handled explicitly.

V is the mean of the three z-scores.

Excluded on purpose: price to book (unreliable after 2000 under intangible-heavy accounting) and price to earnings (dominated by EBIT yield with a worse denominator).

### 5.2 Quality block (Q)

- Gross profitability = (revenue_TTM - cor_TTM) / assets.
- ROIC = NOPAT_TTM / (assets - cashneq - non-interest-bearing current liabilities). NOPAT = ebit × (1 - 0.21) from 2018, ebit × (1 - 0.35) before.
- Accruals = -(netinc_TTM - ncfo_TTM) / assets.
- Asset growth = -(assets / assets one year prior - 1).
- Cash conversion = min(ncfo_TTM / netinc_TTM, 3) when netinc_TTM > 0, else 0. Capped so tiny denominators cannot dominate.
- Leverage = -(net debt / ebitda_TTM), floored at -10, set to 0 (neutral) when ebitda_TTM is zero or negative.

Q is the mean of the six z-scores.

### 5.3 Fundamental momentum block (FM)

- SUE = (eps_q - eps_{q-4}) / stdev(eps_q - eps_{q-4}) over the prior 8 quarters. This is the seasonal random-walk definition, used because there is no consensus feed. It is refreshed whenever a new ARQ record becomes usable, so the 60-day post-announcement drift is captured by monthly rescoring.
- ΔGP/A = gross profitability now minus one year ago.
- ΔNet margin = (netinc / revenue)_TTM minus the same one year ago.
- Price momentum 12-1 = total return from T minus 12 months to T minus 1 month. Included at half weight, as a diffusion proxy only. One-month reversal is deliberately not traded.

FM is the weighted mean: SUE 1.0, ΔGP/A 1.0, ΔNet margin 1.0, 12-1 momentum 0.5.

### 5.4 Insider and event block (I), Phase 2, data from 2005

From `insiders`, restricted to officers and directors, trailing 180 days by `filingdate`:

- Net purchase intensity = (sum of open-market purchase value, code P, minus 0.25 × sum of open-market sale value, code S) / marketcap. Sales carry a 0.25 multiplier because they are mostly liquidity-driven.
- Cluster flag = 1 if three or more distinct insiders bought in the trailing 90 days.
- I = z(net purchase intensity) + 0.5 × cluster flag.

From `events` (8-K item codes; the code map is in `descriptions`), applied as additive penalties to the composite rather than as z-scores:

- Item 4.01 (auditor change) within 12 months: -0.5.
- Item 4.02 (non-reliance on previously issued financial statements): hard exclusion for 24 months.
- Item 5.02 with a CEO or CFO departure within 6 months: -0.25.
- Item 1.01 or 8.01 that the Phase 3 classifier identifies as an announced acquisition of the company: hard exclusion. The stock is now a merger-arbitrage position, not a fundamental one.

Before 2005 the composite runs without I and the remaining weights renormalise. The 2005 boundary is a regime break and every report must show results on both sides of it.

### 5.5 Text block (T), Phase 3, GB10, data from 2006

Anchored on Cohen, Malloy and Nguyen, "Lazy Prices", Journal of Finance 2020: firms whose 10-K and 10-Q language changes materially go on to underperform, the effect persists beyond a year, and it is strongest where attention is low. Mid-caps are its natural home.

Computation per filing:

1. Section extraction: Item 1A and Item 7 (10-K), Item 2 (10-Q). Extraction is LLM-assisted where regex section boundaries fail, which is common before 2010.
2. Similarity: cosine similarity between the section embedding this period and the same section one year earlier (10-K) or one quarter earlier (10-Q). Chunk at roughly 500 tokens, mean-pool, compare. Also compute Jaccard similarity on sentence sets as a second, model-free measure.
3. Sentiment delta: change in the Loughran-McDonald negative-word proportion on the same section, period over period. Dictionary-based, no GPU required.
4. Change classification (LLM, temperature 0, pinned weights, versioned prompt): for filings in the bottom similarity quintile only, classify the changed passages into {new litigation, customer concentration, going-concern language, covenant or liquidity, competitive threat, regulatory, accounting policy, boilerplate reshuffle}. Output is strict JSON validated against a schema.

T = z(similarity) - z(negative-word delta) - 0.5 × [material category flagged]. Boilerplate reshuffles do not count as material.

Compute budget on the GB10: roughly five million chunks to embed (a few hours) and roughly 20,000 filings through the LLM with long prefill and short output (one overnight run). This workload profile is compute-bound rather than generation-bound, so the machine's memory bandwidth ceiling is not the binding constraint. Run as a nightly batch, never interactively.

Model selection: the strongest open-weight instruction model that fits in 128GB at 8-bit or NVFP4 precision at build time, and a top-ranked open embedding model with at least 8k context. Both pinned by weight hash in the repository. No model version is named here because the choice will be stale by build time.

T is admitted into the composite only if its incremental IC, after residualising T against the Phase 2 composite, is significant out of sample within the development window (Section 9.5). Its weight is capped at 0.20 regardless of measured strength.

### 5.6 BORING overlay (config flag, default off)

A name passes if all of the following hold: positive revenue in each of the last 8 quarters; R&D to revenue below 10%; 8-quarter standard deviation of gross margin below the sector median; 8-quarter standard deviation of capex to revenue below the sector median; 252-day idiosyncratic volatility (residual of a market regression) below the 70th percentile of the band.

Run the base case with and without the flag. Report the IR difference. The flag stays on only if the cost is below 0.05 IR.

### 5.7 Hard exclusions before scoring

- Beneish M-score above -1.78 (probable earnings manipulation).
- Altman Z (original non-financial form) below 1.8.
- The Item 4.02 and announced-acquisition exclusions from Section 5.4.
- Any name missing more than one of the V or Q inputs. Do not impute; drop.

---

## 6. Composite

Score = 0.30 V + 0.30 Q + 0.25 FM + 0.15 I + w_T × T + event penalties

where w_T is at most 0.20 and, when T is admitted, the other four weights are scaled by (1 - w_T).

Weights are fixed by prior, not fitted. The only permitted adjustment is setting a block's weight to zero if its development-window IC has the wrong sign with |t| above 2. Any other reweighting is a trial and must be logged in the registry (Section 9.4).

Challenger (Phase 4): a LightGBM ranking objective on the block scores (not the raw metrics), with monotone constraints matching the prior signs, maximum depth 3, at most 200 trees, trained walk-forward with a 3-month embargo. It replaces the linear composite only if its net IR on development data exceeds the composite's by at least 0.10 and the Deflated Sharpe Ratio still clears with the challenger's trials counted.

---

## 7. Portfolio construction

- Rank the eligible universe after exclusions at each month-end T.
- Entry: each vacancy is filled by the highest-ranked name not already held with rank 50 or better.
- Exit: a held name is sold when its rank exceeds 120, when it leaves the universe (a cap-band exit is tolerated for three months before forced sale, to avoid churn at the band edges), or on a hard exclusion.
- Target 50 names. Equal weight at rebalance. No intra-month rebalancing. Single-name cap 4%. Sector cap 25%, with any excess reallocated to the next-ranked names in other sectors.
- Fully invested; residual cash below 2%.
- All trades execute at the close of the trading day after T. No same-day execution is assumed anywhere in the backtest.

---

## 8. Cost model

There is no bid-ask history in the data stack, so costs are era-based one-way charges on traded value: 40 bps before April 2001 (pre-decimalisation), 25 bps from April 2001 to December 2009, 15 bps from 2010 onward. Add 5 bps for any name in the bottom quartile of the band by dollar volume. Report gross and net; every gate is evaluated on net.

Sensitivity: rerun the base case at twice these costs. If the net IR at double costs falls below 0.25 on development data, widen the exit buffer to rank 150 before touching anything else.

---

## 9. Validation protocol

### 9.1 Splits

Development: 2000-01-31 to 2016-12-31 (the effective start reflects the 8-quarter history requirement on fundamentals available from 1998).

Holdout: 2017-01-31 to 2026-08-31. Run exactly once, at Phase 5, with the configuration frozen and hashed before the run. A second holdout run for any reason means the holdout is burnt and the project is declared unvalidated. There is no appeal from this rule.

### 9.2 Leakage tests (unit tests; all must pass before any backtest runs)

- L1: for every feature value at T, the maximum `datekey` used is strictly before T minus one trading day.
- L2: universe membership at T uses only `daily` and `stocks` rows dated on or before T.
- L3: returns used for evaluation at T begin at the T+1 close.
- L4: a synthetic ticker with a deliberately post-dated `datekey` is rejected by the as-of join.
- L5: the MRQ, MRY and MRT dimensions are unreachable from feature code (import-time assertion).

### 9.3 Metrics (reported per block, per composite, per era)

- Monthly Spearman IC against 1-, 3-, 6- and 12-month forward returns; Newey-West t-statistic with lag equal to the horizon; IC decay curve.
- Quintile spread returns (Q5 minus Q1), for information only. Nothing is traded short.
- Long-only excess return, tracking error and IR against Benchmarks A and B; maximum relative drawdown and its duration in months.
- One-way annualised turnover.
- Attribution: regression of excess returns on Fama-French five factors plus momentum; alpha and its t-statistic.
- Deflated Sharpe Ratio (Bailey and López de Prado) using the trial count from the registry, and Probability of Backtest Overfitting via combinatorially symmetric cross-validation with 16 blocks.
- For the challenger only: purged k-fold with a 3-month embargo.

### 9.4 Trial registry

Every backtest run, including debugging runs, appends one row to `trials.parquet`: config hash, git commit, timestamp, universe size, all metrics. The Deflated Sharpe Ratio reads N from this file. Deleting rows has the same status as burning the holdout.

### 9.5 Gates

Phase 1 (numeric composite, development window): monthly IC at the 3-month horizon at least 0.03 with Newey-West t at least 3.0; net IR against Benchmark A at least 0.40; one-way turnover at most 100%; DSR at least 0.95; six-factor alpha t-statistic at least 2.0.

Phase 2 (insiders and events added): incremental net IR of at least 0.05 over Phase 1 on data from 2005, or the block is dropped.

Phase 3 (text added): incremental IC of residualised T at least 0.015 with t at least 2.5 on data from 2006, or the block is dropped.

Phase 4 (challenger): as specified in Section 6.

Phase 5 (holdout, once): net IR against Benchmark A at least 0.25 and positive excess return against Benchmark B. Failure means stop, not iterate.

Phase 6 (paper trading): three monthly rebalance sheets generated live from the frozen configuration before any capital decision is brought to the principal.

---

## 10. Architecture

Repository `bedrock/`, Python 3.12, managed with `uv`. Machine-agnostic: every path derives from a single `BEDROCK_DATA` environment variable so the same checkout runs on the GB10 and on any laptop in the fleet.

Stack: Polars and DuckDB (lake and joins); NumPy; statsmodels (Newey-West, regressions); LightGBM (challenger); PyTorch with aarch64 CUDA wheels; sentence-transformers (embeddings); a local inference server for the LLM (vLLM or llama.cpp, whichever has the cleaner aarch64 Blackwell build at build time); pytest; pydantic-settings for configuration. No pandas in hot paths.

Layout:

```
bedrock/
  config/        base.yaml, boring.yaml, shariah.yaml, costs.yaml
  ingest/        sharadar_bulk.py, edgar_index.py, edgar_fetch.py, edgar_extract.py
  lake/          schema.sql, asof.py   (the point-in-time join; the only place fundamentals are read)
  universe/      membership.py, delisting.py
  features/      value.py, quality.py, fmom.py, insiders.py, events.py
                 text/embed.py, text/similarity.py, text/lm_dict.py, text/classify.py
  scoring/       neutralise.py, composite.py, challenger.py
  portfolio/     select.py, weights.py, costs.py
  backtest/      engine.py, benchmarks.py
  validation/    leakage_tests.py, ic.py, dsr.py, pbo.py, registry.py
  reports/       phase_report.py   (one markdown report per phase gate)
  live/          rebalance_sheet.py   (monthly: target holdings, trades, one-line rationale per name)
  tests/
```

Lake: Parquet under `BEDROCK_DATA/lake/`, partitioned by year, with DuckDB views on top. Sharadar bulk downloads land in `BEDROCK_DATA/raw/sharadar/YYYY-MM-DD/` and are never modified; each research run records which snapshot it used. EDGAR extracted items live in `BEDROCK_DATA/filings/` keyed by CIK and accession.

GB10 responsibilities: `ingest/edgar_*` and `features/text/*`, and nothing else. Everything upstream and downstream of the text block must run on a laptop in under ten minutes for the full history, so the numeric research loop never waits on the GPU.

Reproducibility: pinned lockfile; model weights pinned by hash; prompts versioned in the repository; every report embeds the git commit and the data snapshot date.

---

## 11. Spending

Required now:

- Sharadar Bundle, Full History (all 14 tables, history to the 1990s), personal-use licence direct from sharadar.com. USD 69 per month or USD 499 per year. Recommendation: monthly through Phases 0 to 2 (about three months), converting to annual only if the Phase 1 gate passes. The 5-year and 10-year tiers are not acceptable: they exclude 2000 to 2009 and leave a single drawdown cycle in the development window.

Licence note: the personal-use terms do not cover use in an AMI commercial product. If BEDROCK outputs ever feed a client deliverable, a commercial licence (Nasdaq Data Link research tier, low hundreds of dollars per month) becomes a separate spending decision.

Not required: SEC EDGAR (free), Ken French library (free), open-weight models (free), compute (owned).

Future spending decisions that will be brought back to the principal: capital allocation at Phase 6; a broker choice if execution is to be automated; a commercial data licence if productised; earnings-call transcript data if a v2 wants it.

---

## 12. Build plan

Phase 0, week 1: subscribe, bulk-download, build the lake, implement `asof.py`, pass L1 to L5. Deliverable: leakage test report.

Phase 1, weeks 2 to 4: universe, V, Q, FM, composite, backtest engine, cost model, benchmarks, registry, DSR and PBO. Deliverable: Phase 1 gate report on development data, including the BORING overlay cost measurement.

Phase 2, week 5: insiders and events. Gate.

Phase 3, weeks 6 to 9: EDGAR pipeline on the GB10, similarity and sentiment deltas, LLM classification for the bottom quintile, T admission test. Gate.

Phase 4, week 10: challenger. Keep or discard.

Phase 5, week 11: freeze, hash, single holdout run. Go or stop.

Phase 6, months 4 to 6: three paper rebalances. Then the capital decision returns to the principal.

---

## 13. Known risks, stated plainly

1. Crowding. Value and quality tilts in US mid-caps are run by every systematic manager. The numeric block is table stakes. Expected decay is real, and it is why the gates are set where they are.
2. Two cycles. Development data contains 2000 to 2002 and 2008. The holdout adds 2018, 2020 and 2022. That is thin for a strategy whose worst periods run for years.
3. Regime breaks in the data. Insiders from 2005, risk factors from 2006, decimalisation in 2001. The composite is not the same object across the whole sample, and every report must say so.
4. Text pipeline brittleness. Pre-2010 filings are inconsistently structured. Extraction failures are logged and their rate reported. A name with a failed extraction receives a neutral T, not a missing one.
5. LLM determinism. Temperature 0 with pinned weights is reproducible on one machine and one driver version; a driver update can change outputs. Every classification is cached with its model hash. History is never reclassified silently.
6. Licence scope. See Section 11.
7. Behavioural. The largest single risk is the principal overriding the system during a two-year relative drawdown, which the development data will show is likely to occur. The paper-trading phase exists partly to rehearse living through that.

---

## Addendum A (10 September 2026): sequencing under a data-spend hold

The principal has held the Sharadar subscription. Consequences and the revised order:

1. Nothing in Sections 5.1 to 5.4, 7, 8 or 9.5 can be validated without point-in-time, survivorship-free fundamentals and prices. The free SEC Financial Statement Data Sets can replace the fundamentals table at the cost of several weeks building the securities master and the CIK-to-ticker history. Nothing free replaces delisted price history with corporate actions. The validation gates therefore stay closed until a data decision is made. Backtests on survivor-only free price data are not permitted as a substitute. For the text signal in particular, survivorship bias is not a small distortion: the firms whose language changed shortly before they failed are exactly the ones that would be missing.

2. Work that proceeds at zero spend, in this order:

   a. Repository skeleton, configuration, `asof.py`, and leakage tests L1 to L5 against a synthetic fixture that mimics the Sharadar ARQ schema (columns and dimension semantics taken from public documentation). Real data must drop in later without code changes.

   b. EDGAR pipeline on the GB10: index, fetch, and extraction of Items 1A, 7 and 2 for a provisional universe. Provisional universe = filers whose `EntityPublicFloat` (dei tag in the SEC data sets) ranks between 300 and 1200 each fiscal year. This is a crude annual float ranking used only to bound the crawl. It is replaced by the Section 3 definition as soon as cap data exists.

   c. Extraction quality report: failure rate by fiscal year and form type. This is the largest single engineering risk in the project, and it can be retired before any money is spent.

   d. Embeddings, similarity and Loughran-McDonald deltas computed and cached per filing. The LLM classification step is deferred until similarity quintiles can be computed on a real universe.

3. What this buys: by the time the data decision is revisited, the differentiated half of the system exists and its brittleness is known. What it does not buy: any evidence that the strategy works. Pipeline health says nothing about the edge.

---

## Addendum B (10 September 2026): design changes forced by the evidence sweep

1. Insider block (5.4): add the routine-trader filter from Cohen, Malloy and Pomorski (2012). An insider who traded in the same calendar month in each of the prior three years is routine; routine trades are dropped before computing net purchase intensity and the cluster flag. Only opportunistic trades score.

2. Fundamental momentum (5.3): the prior weight on SUE falls from 1.0 to 0.5. Martineau (2022) finds post-earnings drift absent outside microcaps after roughly 2001; SUE stays in the block only so that it fails on data rather than on assertion, and its sign gate applies in the mid-cap band specifically.

3. Quality block (5.2): accruals become an exclusion screen (drop the worst decile) rather than a scored input. The scored quality inputs reduce to five.

4. Text block (5.5): T is first an exclusion filter (drop the bottom similarity quintile after material-change classification) and only second a score. The Phase 3 gate is measured as the incremental net IR from the exclusion, with the positive-score contribution reported separately.

5. Phase 0 gains a step 0e, zero spend: download the Jensen-Kelly-Pedersen factor returns and underlying sorted portfolios from jkpfactors.com (free, through December 2025) for every characteristic used in Section 5, and report each one's US long-short performance for 2017 to 2025 against 2000 to 2016. Any characteristic whose recent-period return has the wrong sign with a t-statistic above 2 has its prior weight set to zero before Phase 1 begins. This does not test the cap band; it only removes dead signals before money is spent testing them.

6. Framing (Section 0): the evidence favours small and micro caps for inefficiency and mid caps for tradability. The band is a compromise between the two, not a sweet spot, and Section 0 should be read that way.

---

## Addendum C (10 September 2026): results of the zero-spend factor check (Phase 0, step 0e)

Data: Jensen, Kelly and Pedersen US factor returns by size segment (jkpfactors.com, through December 2025), long-short tercile spreads within segment, capped value weighted. Band proxy = mean of the Large and Small segments (NYSE 20th to 80th percentile), which brackets the rank 301 to 1200 universe. Full per-segment table, including Micro, in `jkp_band_era_check.csv`.

Findings in the band, annualised spread and Sharpe, 2000 to 2016 versus 2017 to 2025:
- Value (EBITDA/EV, FCF yield, net payout yield): 8.5% to 13.2%, SR 0.50 to 0.79, falling to 1.2% to 2.9%, SR 0.07 to 0.22.
- Profitability (cash-based operating profit/assets, operating profit/assets, gross profit/assets): 5.8% to 8.9%, SR 0.75 to 1.13, falling to 4.5% to 4.9%, SR 0.52 to 0.78.
- Asset growth: 8.4%, SR 0.67, falling to 1.5%, SR 0.17.
- Accruals, leverage, F-score, QMJ composite: no reliable spread in the band in either era. Leverage was negative in 2000 to 2016.
- SUE and profitability-change proxies: no spread in the band in 2000 to 2016 (SUE worked only in Micro: 7.3%, t 5.6); SUE 2.5%, SR 0.48 in 2017 to 2025.
- Price momentum 12-1: 2.3%, SR 0.11, rising to 7.4%, SR 0.60.
- The v1.0 numeric weighting applied to these spreads: 5.0%, SR 0.90 in 2000 to 2016; 2.3%, SR 0.47 in 2017 to 2025. A long-only book captures roughly half of a long-short spread, so the numeric block alone does not reach the Section 0 bar in the recent era.

Changes. Each is defensible from the 2000 to 2016 data and the literature alone; the 2017 to 2025 figures confirm but were not the basis.
1. Quality block (5.2) becomes: cash-based operating profitability (Ball, Gerakos, Linnainmaa and Nikolaev 2016: operating profit minus operating accruals, over total assets) weight 2; gross profitability 1; operating profitability 1; asset growth 1. Leverage removed. Cash conversion removed as redundant with cash-based profitability. Accruals remain an exclusion screen only.
2. Fundamental momentum block (5.3) becomes: 12-1 price momentum weight 2; SUE 1; ΔGP/A 1. The net-margin-change input is removed.
3. Composite (6): Score = 0.40 Q + 0.15 V + 0.20 FM + 0.25 I (+ w_T × T, cap 0.20, others scaled by 1 - w_T). Value stays at reduced weight because a nine-year drought is within its historical behaviour and the 2000 to 2016 evidence is strong; it is not expected to contribute near term.

Holdout contamination, recorded. Step 0e as written in Addendum B compared 2017 to 2025 against 2000 to 2016 at the factor level, so the holdout period has been viewed at factor level before Phase 1. It cannot be unseen. Corrections: (a) the trial registry opens with 48 entries (16 signals by 3 segments) dated 10 September 2026, and the Deflated Sharpe Ratio counts them; (b) every weight change above must be defensible from 2000 to 2016 data alone, and is; (c) no factor-level or strategy-level statistic from 2017 onward is computed again until Phase 5; (d) step 0e is amended for any future signal (text, insiders): pre-checks use data ending 2016-12-31 only.

Caveats: nine years is one regime; the spreads are capped value weighted terciles, not the 50-name long-only construction of Section 7; Micro results were consistently stronger and are outside the band by design.

---

## Addendum D (10 September 2026): pre-commitment research results

All items were run at zero spend. Supporting files: `etf_buy_vs_build.csv`, `edgar_extraction_sample.csv`, `jkp_band_era_check.csv`.

### D1. Buy-versus-build on the numeric baseline
Mid-cap factor ETFs regressed on the Fama-French five factors plus momentum, and measured against IJH (S&P MidCap 400). Since July 2019 (85 months, the current methodology of the Invesco S&P MidCap factor ETFs): XMMO (momentum) +3.6% a year over IJH, tracking error 9.2%, IR 0.39, momentum loading 0.39, six-factor alpha zero. XMHQ (quality) +2.4%, TE 6.2%, IR 0.38, RMW loading 0.22, alpha zero. XMVM (value with momentum) +3.1%, IR 0.41. Value ETFs with twenty-year records (IMCV, VOE, IJJ) delivered -0.4% to -0.8% a year against IJH. Concentrated all-cap factor funds (QVAL, QMOM) show negative six-factor alpha of -2.7% to -4.0% a year.
Conclusion: the numeric block is purchasable as pure factor exposure at roughly 30 bps a year. Its long-only value in BEDROCK (Addendum C: about half of a 2.3% spread) is no better than what a 50/50 XMHQ/XMMO position has delivered. The build is justified only by the insider and text layers.
Change: Benchmark B (Section 2) becomes a 50/50 XMHQ/XMMO blend rebalanced annually, with IJH reported alongside. That is the true opportunity cost.

### D2. Lazy Prices, read from the tables
Whole-document long-short (non-changers minus changers): 18 to 45 bps a month equal weighted, up to 58 bps a month value weighted (t 3.59), or 2% to 7% a year. The 188 bps a month figure is the Risk Factors section alone, Jaccard measure, five-factor alpha (t 2.76), the strongest of sixty cells (four measures, five sections, three specifications) and resting on 2006 to 2014 data because Item 1A did not exist earlier. The paper states that any positive alpha on the non-changer long side reverts to zero quickly while the changer underperformance persists for six months and does not reverse. The average changer is a $3.5bn firm and the average non-changer $2.5bn, so the effect lives at mid-cap size and is not a small-cap artefact. Sample ends 2014.
Implication: in a long-only book the text block is an exclusion filter and nothing else. Rough bound on its value: if about 20% of any 50-name selection would otherwise be changers and changers underperform by 2% to 6% a year, exclusion is worth 0.4% to 1.2% a year before post-2014 decay. Section 5.5 stands as amended in Addendum B; the expectation attached to it is lowered to that range.

### D3. Insider signal decay after 2007
A direct replication of Cohen, Malloy and Pomorski on recent data reports the opportunistic-trade factor alpha falling from roughly 1.2% to 1.6% a month to 0.3% to 0.4% a month, a 60% to 70% decline. A 2024 study of Form 4 purchases from November 2018 to November 2023 finds positive but lower abnormal returns that vanish, and turn negative, once the tradable dollar amount per signal is limited to a realistic size. The one live product with a long record, the insider-sentiment ETF NFO (September 2006 to February 2020, closed at $81m), returned +0.4% a year over IJH with tracking error 7.2%, IR 0.05, net of a 0.66% fee; +3.1% a year over the S&P 500 in 2007 to 2013, -1.9% in 2014 to 2020.
Implication: realistic long-only contribution of the insider block is 0.5% to 1.0% a year, and it needs the routine-trader filter to reach that.

### D4. Drawdown profile of the revised blend, development window only
Long-short spread, band proxy, 1971 to 2016: 6.9% a year, Sharpe 1.37, maximum drawdown -11.6%. Two underwater stretches of 32 months (November 2002 to July 2005) and 31 months (March 2009 to October 2011); worst 12-month spread -10.1% (to February 2010). In 2000 to 2016 the spread averaged 6.4% a year, but 72% of the cumulative spread came from 2000 to 2002; 2003 to 2016 averaged about 2.2% a year, which is the same order as 2017 to 2025. The decay story in Addendum C is partly a 2000 to 2002 outlier story.
Implication: the principal must expect two to three years of relative underperformance per decade, and should read the 2000 to 2016 development result with the first three years mentally removed.

### D5. EDGAR extraction feasibility (119 10-Ks, 12 issuers, 1998 to 2024)
With regex section extraction alone: MD&A found in 54% of 2001 to 2005 filings and 67% to 83% later; Risk Factors found in 91% to 100% of post-2006 filings. The dominant failure is structural, not parsing: a meaningful share of unglamorous issuers incorporate MD&A by reference to the annual report filed as Exhibit 13, including in 2024. Pre-2001 filings have no primary document and require the full submission file. After parsing the full submission and Exhibit 13, MD&A extraction reached 90% overall (83% to 92% by era) and Risk Factors 95%. Remaining failures cluster by issuer (one issuer failed in every year sampled), which the neutral-T rule in Section 13 handles.
Changes to Section 4.2: ingest the full submission text for every filing, split on document type, and take the MD&A from Exhibit 13 whenever the 10-K body's Item 7 is a pointer. Sample caveat: eleven of the twelve issuers are survivors; failure rates on delisted small issuers will be higher.

### D6. Tax and legal drag
Confirmed: there is no US-Saudi income tax treaty, so US-source dividends paid to a Saudi-resident individual are withheld at 30%, and this applies to US-domiciled ETFs as well as to directly held stocks. Capital gains are not taxed for a non-resident alien below 183 days of US presence. US estate-tax exposure on US-situs assets above a small exemption remains a live issue to verify with an adviser.
Implication: withholding does not favour the ETF route over the build, since XMHQ and XMMO are US-domiciled; it favours an Irish-domiciled plain S&P 400 UCITS fund (15% treaty rate) over both, worth roughly 0.25% to 0.3% a year on a 1.5% to 2% yielding book. The estate-tax point applies to both routes equally.

### D7. Realistic contribution, long-only, net of costs, before tax
| Block | Expected contribution over IJH | Basis |
|---|---|---|
| Numeric (buyable) | 1.0% to 1.5% | half of a 2% to 3% spread, less costs |
| Insiders (opportunistic only) | 0.5% to 1.0% | D3 |
| Text exclusion | 0.4% to 1.0% | D2, before post-2014 decay |
| Total build | 2% to 3.5% | |
| 50/50 XMHQ/XMMO | 1% to 2% expected (3% realised 2019 to 2026) | D1 |
| Build minus buy | roughly 1% to 1.5% a year | |

That incremental 1% to 1.5% a year is the entire economic case for the build. It arrives with two to three year relative drawdowns, a 30% dividend withholding that applies either way, and an eleven-week build plus a monthly operating routine. Whether it is worth it depends on the capital it would be applied to, which is a matter for the principal.

---

## Addendum E (10 September 2026): reuse of AMI_MarketApp components

The AMI_MarketApp repository (saifgithub/AMI_MarketApp, public since 10 September 2026) already contains a point-in-time fundamentals engine, `backend/app/services/edgar_pit.py` (CR164), resolving XBRL facts as of a historical date using only facts whose filed date is on or before it, with staleness refusal for late or delisted filers, plus `asof_context.py` and `numeric_provenance.py`.

Changes:
1. Section 4.2 and Addendum A item 2a: the leakage-correct fundamentals join for 2009 onward is to be built on `edgar_pit` rather than written fresh. Its filed-date rule is the same availability rule as Section 4.1. XBRL coverage begins in 2009, so 2000 to 2008 fundamentals and the full delisted universe still require the Sharadar tables.
2. Section 11: the paid-data case narrows to (a) survivorship-free price history with delisting returns and (b) pre-2009 fundamentals. The fundamentals half of the original justification is withdrawn for 2009 onward.
3. The trial-registry discipline in Section 9.4 has a working precedent in the repository: RES006 was pre-registered and frozen before code ran. The BEDROCK registry should follow that file's format.
