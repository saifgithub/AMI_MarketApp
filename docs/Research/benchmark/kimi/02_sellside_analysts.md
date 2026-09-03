# Sell-Side Analyst Teams — Human Benchmark Deep Dive

Benchmark group: bank/broker equity research desks issuing buy/hold/sell calls and
12-month price targets. Research date: 2026-08-09. All figures carry citation
references mapping to the numbered Sources list at the bottom. Discrepancies and
single-source figures are flagged inline.

---

## Executive summary — headline numbers

- **Buy recommendations carry real but modest alpha.** New buy calls produce an
  average ~+3.0% abnormal return in the 3-day event window and a further ~+2.4%
  post-recommendation drift that is short-lived (~1 month); new sell calls drop
  ~-4.7% on announcement and drift ~-9.1% over the following six months [1][2].
- **Consensus-following strategies earn ~+4%/yr gross, ~zero net.** Buying the
  most favorably rated stocks (daily rebalanced) returned +4.13%/yr gross
  abnormal and shorting the least favorably rated returned -4.91%/yr (Zacks,
  1986–1996), but transaction costs consumed essentially all of it [3][4].
- **The median analyst is roughly a coin flip; the top tier is not.** TipRanks
  measures a "success rate" (% of ratings profitable over up to 1 year) and
  average return per rating [8]. Its Top-25 analysts of 2021 averaged a 67.6%
  success rate [9], while working analysts cited in press coverage routinely sit
  in the ~40–65% band [10] — so the human bar is ~50–55% median, ~65–70% elite.
- **Ratings are structurally skewed to buys.** Recent FactSet counts: 59.2% buy /
  36.0% hold / 4.8% sell of ~12,900 S&P 500 ratings; 5-year averages ~54.4% buy
  and ~6.1% sell [11][12]. At the 2000 bubble peak it was 73% buy / 2% sell [13].
- **12-month price targets are unreliable.** Only ~38% of targets are met exactly
  at the 12-month mark; ~54–64% are touched at some point during the year
  depending on the study and era [14][15][16].
- **EPS forecasts are systematically optimistic.** Over 25 years analysts expected
  10–12% annual earnings growth vs ~6% realized — forecasts on average ~100% too
  high [17]; bottom-up quarterly EPS estimates are cut an average of 4.3% during
  each quarter (20-year average) [18].
- **Signal value decays fast.** Most usable alpha concentrates in days-to-weeks
  after a recommendation or revision; buy-side drift is exhausted in ~1 month and
  the strongest information content sits near earnings announcements [1][3][19].
- **Why:** investment-banking conflicts and career incentives. Lead-underwriter
  analysts issued 50% more buy recommendations than unaffiliated analysts, and
  those affiliated buys significantly underperformed over the following two years
  [20][21].

---

## 1. Recommendation alpha & hit rates

### Study × horizon × result

| Study | Sample / data | Horizon | Result | Ref |
|---|---|---|---|---|
| Womack (1996), *J. Finance* | 14 major US brokerages, First Call/Zacks-type recs, 1989–1991 | 3-day event window | Buys +3.0%, sells -4.7% average abnormal announcement return | [1][2] |
| Womack (1996) | same | Post-event drift | Buys: +2.4% mean drift, "modest and short-lived" (~1 month); Sells: -9.1% drift extending ~6 months | [1][2] |
| Barber, Lehavy, McNichols, Trueman (2001), *J. Finance* | Zacks consensus recs, 1986–1996 | Annual, daily rebalancing | Most-favorable consensus quintile +4.13%/yr gross abnormal; least-favorable -4.91%/yr; edge shrinks with weekly/monthly rebalancing; **no strategy beat the market net of trading costs** | [3][4] |
| Barber et al. (2003), *Fin. Analysts J.* — "Reassessing" | update through mid-2005 | Annual | Gross abnormal returns persist but remain largely eaten by transaction costs; consensus levels alone are not a tradable edge for retail | [4][5] |
| Jegadeesh, Kim, Krische, Lee (2004), *J. Finance* | US recs + characteristics | Quarterly | **Change** in consensus recommendation is a stronger return predictor than the **level**; the most-popular (most-favored) glamour stocks without value/momentum support earn the *worst* subsequent returns | [6][7] |
| Loh & Mian (2006), *JFE* | I/B/E/S recs + EPS forecasts | Monthly | Recs by the most EPS-accurate analyst quintile beat the least accurate quintile by **1.27%/month** factor-adjusted; a long-short on their recs yields 0.737%/month Carhart 4-factor alpha | [22][23] |
| Ivkovic & Jegadeesh (2004), *JFE* | Earnings-forecast + rec revisions | Weeks–quarter | Information content of upward revisions/upgrades is concentrated shortly after issuance and peaks near earnings announcements; downgrades behave asymmetrically | [19] |

**Hit-rate framing.** None of the classic studies publish a clean "% of buys that
beat the S&P 500 over 12 months" number; they work in average abnormal returns.
The closest aggregate hit-rate source is TipRanks' platform data (next section).
The consistent academic picture: the *average* buy call is worth roughly +2–4%
gross annualized alpha concentrated early, i.e. barely above noise per call —
consistent with median hit rates only slightly above 50%.

---

## 2. Aggregate analyst stats (TipRanks-style)

TipRanks tracks "tens of thousands" of financial experts and defines [8]:

- **Success rate** = % of ratings that earned a positive return over a default
  1-year window (or until the rating changes).
- **Average return** = mean return per rating over the same window.
- Rankings weight statistical significance (number of ratings).

Observed figures:

- **Top 25 Wall Street analysts of 2021: 67.6% average success rate** [9].
  *(Single secondary source — Public.com citing TipRanks' 2021 awards; could not
  re-verify on tipranks.com directly, which returns 403 to automated fetches.)*
- **Top-10 analysts (Jan 2025 snapshot):** the #1 analyst showed an 88% success
  rate and 14% average return over 95 ratings [10].
- **Working-analyst band:** press articles embedding live TipRanks data show
  named covering analysts at major banks (BofA, Barclays, RBC, Citi, J.P. Morgan,
  Morgan Stanley, Piper Sandler, Stifel, TD Cowen, Craig-Hallum, Goldman) with
  1–2 year success rates scattered across **~39–65%** and average returns from
  **-4.6% to ~+29%** [10]. Median of those sampled sits near ~51–55%.
- TipRanks does not publish an official all-analyst mean success rate on its
  public methodology pages; treat ~**50–55% as the defensible median estimate**
  and flag it as inferred, not directly published [8][10].

**Top vs median gap:** the elite cohort (~67–88% success) is separated from the
median (~50–55%) by roughly 15–30 hit-rate points, and the academic literature
corroborates that skill dispersion is real and persistent: EPS-forecast accuracy
predicts recommendation profitability with a 1.27%/month top-vs-bottom-quintile
spread [22].

---

## 3. The buy/sell skew

| Era / date | Buy | Hold | Sell | Source |
|---|---|---|---|---|
| 2000 (bubble peak, Investars data) | 73% | 25% | 2% | [13] |
| 2001 | 62% | 35% | 3% | [13] |
| 2008 (post-crisis) | 39% | 47% | 14% | [13] |
| FactSet 5-yr (month-end) averages, as of Mar 2024 | 54.4% | ~39.5% | 6.1% | [12] |
| FactSet point-in-time count (12,939 S&P 500 ratings) | 59.2% | 36.0% | 4.8% | [11] |

Notes:

- The skew is persistent and only moderately reformed after the 2003 Global
  Settlement and Reg FD: sells moved from ~2–3% to ~5–6%, not to parity [12][13].
- Barber, Lehavy, McNichols & Trueman (2006, *JAE*) document that the *level*
  distribution is so buy-heavy that sell-side "hold" is economically a negative
  signal — their later work shorts holds against buys precisely to correct for
  the optimism bias [5][24].
- **Implication for call quality:** with >50% of all ratings being buys, an
  unconditional "buy everything" heuristic would match the median analyst's
  output mix. A buy call from the median desk therefore carries little
  discriminative information; the *change* (upgrade/downgrade) and the *sell*
  carry the information [1][6].

---

## 4. Forecast & price-target accuracy

**Price targets (12-month):**

- Asquith, Mikhail & Au (2005, *JFE*), All-American analysts 1997–1999: **54.3%**
  of price targets achieved within the 12-month period [14][15].
- Bradshaw, Brown & Huang (2013), US reports 2000–2009: **64%** of targets met
  *sometime* during the 12 months, but only **38%** met *at the end* of the
  12-month period [15][16].
- Gleason, Johnson & Li (2013): among targets achieved, stocks overshoot the
  target by an average of 37% within the year; the remaining ~46% of firms reach
  an average of only 84% of the target [25].
- A 2023 large-cap US study (cited by AnaChart): fewer than half of 12-month
  price targets are reached within the stated timeframe [26]. *(Secondary source
  summarizing a study; consistent with the academic range.)*
- **Discrepancy note:** "hit rates" for targets range 38%→67% across studies
  (e.g., Warsaw WSE sample 66.7% [16]) because definitions differ — met *at
  horizon* vs touched *anytime* — and because bull-market eras mechanically
  inflate achievement. For benchmarking, the strict at-horizon figure (~38–54%)
  is the honest one.

**EPS forecasts:**

- McKinsey (2010), 25-year panel: analysts' expected long-run earnings growth of
  10–12%/yr vs ~6% actual — forecasts on average ~**100% too high**; estimates
  started high and were revised down through nearly every year [17].
- FactSet Earnings Insight, 20-year average (80 quarters): the bottom-up
  quarterly S&P 500 EPS estimate declines **4.3%** during the course of a
  quarter [18].
- Accuracy matters for alpha: analysts in the top EPS-accuracy quintile issue
  recommendations worth +1.27%/month more than the bottom quintile [22].

---

## 5. Horizon decay of call value

- **Days:** the single largest move is the announcement window itself (+3.0% /
  -4.7% for buys/sells) — much of the value is impounded before a client can act
  [1][2].
- **Weeks-to-1-month:** buy-side post-recommendation drift (+2.4%) is exhausted
  within roughly a month [1][2]. The predictive power of revisions is
  concentrated shortly after issuance and around earnings dates [19].
- **Months:** sell-side drift persists much longer (-9.1% over ~6 months) — the
  asymmetric half-life is why shorting downgrades/sells historically out-earned
  buying upgrades [1].
- **Annual:** consensus-level strategies need *daily* rebalancing to capture
  +4.13%/yr gross; weekly/monthly rebalancing materially diminishes returns, and
  transaction costs erase them entirely [3][4].
- **12 months+:** little evidence of durable alpha from recommendation *levels*;
  price-target precision at the 12-month mark is poor (38% exact-hit) [15].
  Value that survives to long horizons is carried by recommendation *changes*
  combined with value/momentum characteristics, not levels [6].

Net: **sell-side value is a short-horizon product.** A benchmark that scores the
Room at 3–12-month horizons on unweighted recommendation levels is grading
humans on their weakest dimension.

---

## 6. Why hit rates are what they are (conflicts & incentives)

- **Investment-banking affiliation bias.** Michaely & Womack (1999, *RFS*):
  lead-underwriter analysts issued **50% more buy recommendations** than
  unaffiliated analysts on the same IPOs; the market only partially discounted
  the bias, and affiliated buys **significantly underperformed** unaffiliated
  buys over the following two years [20][21][27].
- **The distribution itself is the tell.** ~55–60% buys / ~5% sells [11][12] is
  not an honest posterior over outcomes; it reflects desks protecting banking
  relationships, corporate access, and commission flows. Post-2003 Global
  Settlement ($1.4B, ten banks) and Reg FD improved but did not normalize the
  mix [13][21].
- **Career incentives.** Hong & Kubik (2003, *J. Finance*) show analysts'
  career outcomes reward optimism and boldness relative to the consensus, not
  raw accuracy [28]. Optimism is rational for the analyst even when costly for
  the follower.
- **EPS optimism is the mechanism.** Systematically high growth forecasts
  (10–12% expected vs 6% realized [17]) mechanically produce high price targets
  and buy ratings; the quarterly walk-down (avg -4.3% intra-quarter cuts [18])
  is the forecast slowly converging to reality.
- **Counterweights:** Loh & Stulz (2018) find sell-side research is *more*
  valuable in bad times [29], and top-quintile accuracy is persistent and
  rewarded by the market [22] — the skill is real; the *median* output is
  polluted by incentives.

---

## 7. Implications for Room benchmarking

- **Bar to beat — median human team:** a buy call worth roughly +2–4% gross
  annualized alpha with most of it realized in the first month [1][3]; median
  hit rate ≈ 50–55% of ratings profitable over ≤1 year [8][10]. The Room should
  target a **≥55% hit rate vs the S&P 500 at 3 months** to claim parity with a
  competent human desk, **≥65%** to claim elite (TipRanks Top-25) territory [9].
- **Always score against the index, never absolute returns.** Humans issue >50%
  buys [11]; in a bull tape a buy-heavy Room looks brilliant while adding zero
  alpha. Excess return vs S&P 500 (or sector ETF) at fixed horizons is the only
  honest metric — this mirrors TipRanks' own optional benchmark adjustment [8].
- **Weight short horizons, but don't only score them.** Human call value decays
  within weeks [1][19]; score the Room at 1 week / 1 month / 3 months primarily,
  and treat 12-month price-target-style scoring as a stretch goal where even
  humans hit only ~38–54% [14][15].
- **Measure recommendation *changes*, not levels.** The academically robust
  human signal is the upgrade/downgrade [6]. A Room that outputs static
  buy/hold/sell levels should be evaluated on the *delta* between successive
  runs, else it replicates the least informative human output.
- **Exploit the structural gap: sells.** Humans issue ~5% sells because of
  conflicts the Room doesn't have [11][12][20]. Sell/avoid calls are where human
  alpha concentrates (-9.1% drift [1]) — the Room's benchmark sheet should
  include a sell-side precision metric, an axis where it can structurally beat
  the human benchmark rather than merely match it.
- **Track the Room's EPS/fundamental forecast error as a leading indicator.**
  In humans, forecast accuracy predicts recommendation profitability
  (+1.27%/month top-vs-bottom quintile [22]); if the Room's fundamentals agents
  can't beat consensus-naive forecast error, its calls won't beat consensus
  either.

---

## Sources

1. Womack, K. L., "Do Brokerage Analysts' Recommendations Have Investment
   Value?", *Journal of Finance* 51(1), 1996 — abstract and figures as quoted in
   later literature (ResearchGate mirror).
   https://www.researchgate.net/publication/228378575_Analyzing_the_analysts_after_the_Global_Settlement
2. "Do Analysts' Recommendations Have Investment Value?" (summary of Womack
   1996 event-window and drift numbers), CORE working-paper PDF.
   https://core.ac.uk/download/pdf/161689906.pdf
3. Barber, B., Lehavy, R., McNichols, M., Trueman, B., "Can Investors Profit
   from the Prophets? Security Analyst Recommendations and Stock Returns",
   *Journal of Finance* 56(2), April 2001 — abstract (CFA Digest copy).
   https://rpc.cfainstitute.org/sites/default/files/-/media/documents/article/cfa-digest/2001/dig-v31-n4-952-pdf.pdf
4. LeCompte, S., "Can the 'Experts' Help You Beat the Market?" (summary of
   Barber et al. 2001: +4.13% / -4.91% gross, net negative after costs),
   CXO Advisory, Nov 2004.
   https://www.cxoadvisory.com/investing-expertise/can-the-experts-help-you-beat-the-market/
5. Barber, B., Lehavy, R., McNichols, M., Trueman, B., "Reassessing the Returns
   to Analysts' Stock Recommendations", *Financial Analysts Journal* 59(2),
   2003. https://webuser.bus.umich.edu/rlehavy/BLMT2_FAJ.pdf
6. Jegadeesh, N., Kim, J., Krische, S. D., Lee, C. M. C., "Analyzing the
   Analysts: When Do Recommendations Add Value?", *Journal of Finance* 59(3),
   2004 — as summarized in "AlphaRank Top Stocks", Accelerate Shares.
   https://accelerateshares.com/research/alpharank-top-stocks-the-predictive-power-of-changing-expectations/
7. "Security Analysts and Capital Market Anomalies" (discussion of Jegadeesh et
   al. 2004: changes beat levels), PolyU Institutional Research Archive.
   https://ira.lib.polyu.edu.hk/bitstream/10397/90051/1/JFE_Analyst_PolyU.pdf
8. TipRanks, "How Are Experts Ranked" (success rate / average return /
   statistical-significance methodology, default 1-year window).
   https://www.tipranks.com/experts/how-experts-ranked
9. Public.com, "How to make sense of Wall Street analyst ratings" (TipRanks
   Top-25 analysts of 2021: 67.6% success rate — single secondary source).
   https://public.com/learn/how-to-make-sense-of-wall-street-analyst-ratings
10. NBC 6 South Florida / CNBC Make It, "Here are the top 10 U.S. stock
    analysts, according to TipRanks" (Jan 2025: #1 analyst 88% success, 14% avg
    return); plus Futunn news wire embedding live TipRanks per-analyst stats
    (success rates ~39–65%). https://www.nbcmiami.com/news/business/money-report/here-are-the-top-10-u-s-stock-analysts-according-to-tipranks/3519823/
11. FactSet Earnings Insight (current-cycle count: 12,939 S&P 500 ratings;
    59.2% buy / 36.0% hold / 4.8% sell). https://www.factset.com/earningsinsight
12. FactSet Earnings Insight, March 15 2024 edition (5-yr averages: 54.4% buy,
    6.1% sell).
    https://advantage.factset.com/hubfs/Website/Resources%20Section/Research%20Desk/Earnings%20Insight/EarningsInsight_031524.pdf
13. Krantz, M., *Fundamental Analysis For Dummies* (Investars ratings
    distribution table 2000–2008: 73% buy/2% sell in 2000 → 39%/14% in 2008).
    https://procapital.mohdfaiz.com/books/books-image/mainBook/Fundamental%20Analysis%20for%20Dummies.pdf
14. Asquith, P., Mikhail, M., Au, A. (2005, *JFE*) as summarized in "Target
    Price Accuracy: International Evidence", Lancaster EPrints (54.3% of
    All-American analysts' 1997–1999 targets achieved within 12 months).
    https://eprints.lancs.ac.uk/id/eprint/71029/1/Analyst_TP_accuracy_Feb2012.pdf
15. "Target Price Accuracy in Equity Research" (Bradshaw, Brown & Huang 2013:
    64% met sometime during the 12-month period, 38% met at period end),
    ResearchGate.
    https://www.researchgate.net/publication/314905880_Target_Price_Accuracy_in_Equity_Research
16. "Target Price Accuracy and the Information Content of Stock Recommendations
    on the Warsaw Stock Exchange" (cross-study comparison incl. WSE 66.7%,
    Bradshaw et al. 64%, Asquith et al. ~54%), Semantic Scholar PDF.
    https://pdfs.semanticscholar.org/49db/31092e18ffa252c144dc624ef5b9eae70685.pdf
17. Goedhart, M., Raj, R., Saxena, A., "Equity analysts: Still too bullish",
    McKinsey & Company, April 2010 (25-yr expected growth 10–12% vs ~6% actual).
    https://www.mckinsey.com/capabilities/strategy-and-corporate-finance/our-insights/equity-analysts-still-too-bullish
18. FactSet Earnings Insight, Oct 3 2025 edition (20-yr avg intra-quarter
    decline in bottom-up EPS estimate: 4.3%).
    https://advantage.factset.com/hubfs/Website/Resources%20Section/Research%20Desk/Earnings%20Insight/EarningsInsight_100325A.pdf
19. Ivkovic, Z., Jegadeesh, N., "The Timing and the Value of Forecast and
    Recommendation Revisions", *Journal of Financial Economics* 73(3), 2004 —
    abstract, ScienceDirect.
    https://www.sciencedirect.com/science/article/abs/pii/S0304405X04000522
20. Michaely, R., Womack, K. L., "Conflict of Interest and the Credibility of
    Underwriter Analyst Recommendations", *Review of Financial Studies* 12,
    1999 — summarized in "Investment Banks, Scope, and Unavoidable Conflicts of
    Interest", Babson faculty PDF (50% more buys; two-year underperformance).
    https://faculty.babson.edu/wp-content/uploads/2024/01/investment-bank-conflicts.pdf
21. US Senate hearing S. Hrg. 107-948, "Accounting Reform and Investor
    Protection", Vol. II (summary of Michaely & Womack findings; Global
    Settlement context). https://www.govinfo.gov/content/pkg/CHRG-107shrg87708/html/CHRG-107shrg87708-volII.htm
22. Loh, R. K., Mian, G. M., "Do Accurate Earnings Forecasts Facilitate
    Superior Investment Recommendations?", *Journal of Financial Economics*
    80(2), 2006 — abstract (1.27%/month quintile spread), SMU InK.
    https://ink.library.smu.edu.sg/lkcsb_research/2641/
23. "Target Price Accuracy" (ProQuest) — Loh & Mian long-short strategy:
    0.737%/month Carhart 4-factor alpha.
    https://www.proquest.com/scholarly-journals/target-price-accuracy/docview/868431388/se-2
24. Barber, B., Lehavy, R., McNichols, M., Trueman, B., "Buys, Holds, and
    Sells: The Distribution of Investment Banks' Stock Ratings and the
    Implications for the Profitability of Analysts' Recommendations", *Journal
    of Accounting and Economics* 41, 2006.
    https://www.anderson.ucla.edu/documents/areas/fac/accounting/Trueman_BuysHoldsSells.pdf
25. Gleason, C. A., Johnson, W. B., Li, H., "Earnings Forecast Accuracy,
    Valuation Model Use, and Price Target Performance" (overshoot 37%; 46% of
    firms reach avg 84% of target), Notre Dame working paper.
    https://care-mendoza.nd.edu/assets/152422/gleason_6_06.pdf
26. AnaChart, "How Accurate Are Analyst Price Targets? 18 Years of Data"
    (2023 study: fewer than half of 12-month targets reached within timeframe).
    https://anachart.com/how-accurate-are-analyst-price-targets/
27. Choi, S. J., "The Problems with Analysts", *Alabama Law Review* 59
    (Michaely–Womack 50%-more-buys figure in legal-literature context).
    https://www.law.ua.edu/wp-content/uploads/archive/law-review-articles/Volume%2059/Issue%201/Choi.pdf
28. Hong, H., Kubik, J. D., "Analyzing the Analysts: Career Concerns and Biased
    Earnings Forecasts", *Journal of Finance* 58(1), 2003 — citation and
    finding as catalogued in survey literature.
    https://www.siecon.org/sites/default/files/media_wysiwyg/156-acar-becchetti-manfredonia.pdf
29. Loh, R. K., Stulz, R. M., "Is Sell-Side Research More Valuable in Bad
    Times?", *Journal of Finance* 73(3), 2018 — citation as catalogued in
    survey literature (same survey PDF as [28]).

---

### Verification flags

- **[9] 67.6% Top-25 success rate** — single secondary source (Public.com);
  tipranks.com blocks automated access (403), so the primary press release
  could not be fetched. Treat as indicative.
- **Median ~50–55% TipRanks success rate** — inferred from the per-analyst
  samples embedded in press coverage [10], not a published TipRanks aggregate.
- **[13] Investars 2000–2008 table** — secondary (book reproduction of
  Investars data); directionally corroborated by FactSet's current ~55%/~5%
  buy/sell mix [11][12].
- **Price-target hit-rate spread (38% vs 54% vs 64–67%)** is definitional
  (at-horizon vs anytime-in-window) and era-dependent, not a source error —
  noted in Section 4.
