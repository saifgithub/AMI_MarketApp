# Academic Evidence on Human Forecasting Skill — Benchmark Deep Dive

**Purpose.** This is the academic-foundation layer of the human benchmark for AMI
Trade's Room (the 12-agent deliberating analyst team). Sibling docs cover active
fund managers, sell-side analysts, and retail clubs. This doc covers the
forecast-accuracy and expert-vs-model literature: what seventy years of peer-reviewed
measurement says about how good human expert judgment actually is at predicting
economic, political, and market outcomes — and where simple models, crowds, and
machines beat it.

Every headline number carries a citation to the numbered Sources list at the end.
Single-source figures are flagged; discrepancies between sources are reported
inline.

---

## Executive summary

- **Tetlock (2005), 284 experts, ~27,000–82,000 forecasts over ~20 years:** the
  average domain expert's long-horizon political/economic forecasts were barely
  better than chance — "roughly as accurate as a dart-throwing chimpanzee" — and
  were beaten by crude base-rate extrapolation algorithms [1][2][3].
- **Grove et al. (2000) meta-analysis of 136 studies:** mechanical/statistical
  prediction beat human expert ("clinical") judgment in 33–47% of studies, lost in
  only 6–16%, and was ~10% more accurate on average. Meehl's summary: in at most
  ~5% of studies does the expert win outright [4][5][6].
- **Sell-side EPS forecasts (Dreman & Berry 1995; 66,100 consensus estimates,
  1974–1991):** 73.3% of quarterly consensus estimates missed actual EPS by more
  than ±5%; 55.6% missed by more than ±10%; average error exceeded 20% of actual
  EPS — and errors were *increasing* over the sample period [7].
- **Optimism bias (McKinsey 2010):** over 25 years, analysts expected S&P 500
  earnings growth of 10–12% per year versus ~6% realized — forecasts on average
  nearly 2× too high [8].
- **Man vs machine (Cao, Jiang, Wang & Yang 2024, JFE):** an ML "AI analyst" beat
  the median human I/B/E/S analyst in 54.5% of stock-return predictions; even
  machine-*debiased* human forecasts lost to the pure machine (won only 46.5%),
  implying ~22% of the man–machine gap is correctable human bias. The combined
  "Man + Machine" beat the AI-only model in 54.8% of forecasts [9].
- **ML earnings benchmarks (van Binsbergen, Han & Lopez-Lira 2023, RFS):** analyst
  expectations are on average biased *upward*, and the bias **increases with
  forecast horizon**; a statistically optimal ML benchmark is unbiased [10].
- **Wisdom of crowds:** simple equal-weight forecast averages are "hard to beat"
  even by sophisticated combination schemes (Clemen 1989; 50-year review) [11][12];
  prediction markets (Iowa Electronic Markets) beat 964 election polls 74% of the
  time, especially beyond 100 days out [13]. Structured deliberating teams beat
  individuals (Mellers et al. 2014), but only with training, tracking, and
  aggregation — unstructured groups herd [14][15].
- **Horizon dependence:** human forecasting skill decays with horizon across every
  domain measured — Tetlock's experts degraded at longer horizons [1], analyst
  optimism rises with horizon [10], while *markets* themselves show exploitable
  short-horizon structure (momentum ~1%/month at 3–12 months [16]) and long-horizon
  mean reversion (~25 pp loser-winner spread over 36 months [17]).

---

## 1. Tetlock and the limits of expert judgment

**Study.** Philip Tetlock's *Expert Political Judgment* (Princeton, 2005) scored
forecasts from 284 professionals — political scientists, economists, journalists,
intelligence analysts, policy advisors — collected over roughly two decades
(1984–2003) [1][3].

**Sample-size discrepancy (reported, not resolved).** Secondary sources variously
report "28,000 forecasts" [2] and "80,000+ forecasts" [18] for the same research
program. The smaller figure typically refers to the formally scored forecast set in
the 2005 book; the larger (~82,000) to the total elicited across the full program
including the 2017 revised edition's accounting. We treat "284 experts, tens of
thousands of forecasts" as the safe statement and flag both numbers.

**Core findings [1][2][3]:**

- On three-option questions (e.g., GDP growth will rise / stay flat / fall), the
  average expert performed barely above the 33% a random chooser achieves; Tetlock's
  own summary: "the average expert was roughly as accurate as a dart-throwing
  chimpanzee." Tetlock has repeatedly noted the chimp line is a rough paraphrase —
  the precise claim is that expert accuracy was *not reliably distinguishable from
  chance* in aggregate [18][2].
- Experts were beaten by **crude statistical algorithms** that simply extrapolated
  base rates / recent trends, and by informed non-specialists ("dilettantes")
  reading outside their specialty [19].
- **Credentials, experience, and confidence did not predict accuracy.** If anything,
  media prominence correlated *negatively* with accuracy — the most famous experts
  were among the worst [2][18].
- **Cognitive style mattered:** "foxes" (many frameworks, self-critical, updaters)
  consistently beat "hedgehogs" (one big idea, high confidence). The strongest
  predictor of failure was the expert's certainty [2][1].
- Accuracy degraded as the forecast horizon lengthened — the finding is
  specifically about *long-horizon* judgment, not short-run information processing.

**Application to financial forecasting.** Equity selection is exactly the hard case
Tetlock measured: multi-year, noisy, reflexive outcomes with base rates that dominate
case-specific narratives. The direct implication for the Room benchmark: a
credentialled-human "expert bar" for long-horizon stock calls is a *low* bar —
near chance-level directional accuracy with worse-than-base-rate calibration is the
empirically measured human standard [1][2].

**Follow-on program (context for the "trainable" ceiling).** In the IARPA ACE
tournament (2011–2015), Tetlock & Mellers' Good Judgment Project showed forecasting
skill is real but rare and cultivable: the top 2% ("superforecasters") outperformed
professional intelligence analysts — who had classified data — by roughly 30% on
Brier scores, and GJP beat the four rival university teams by 35–72% [15][20].
So the human distribution has a long right tail; the *average* expert sits far
below it.

---

## 2. Simple models vs human experts (Meehl → Grove)

**Meehl (1954).** Paul Meehl's *Clinical vs. Statistical Prediction* reviewed ~20
studies pitting actuarial rules against expert clinical judgment; virtually all
favored the mechanical rule or tied. The result has replicated for 70 years. In
Meehl's own 1996 retrospective on the Grove meta-analysis: "Of 136 research
studies, from a wide variety of predictive domains, not more than 5 percent show
the clinician's informal predictive procedure to be more accurate than a
statistical one" [6]. Dawes, Faust & Meehl (1989, *Science*) extended the count to
~100 studies with the same conclusion [21].

**Grove, Zald, Lebow, Snitz & Nelson (2000), *Psychological Assessment* — the
canonical meta-analysis [4][5][6]:**

- **136 studies** comparing clinical (human-expert) vs mechanical (statistical/
  actuarial) prediction in psychology and medicine, restricted to cases where both
  sides saw the same predictor variables.
- Mechanical prediction **substantially outperformed** clinical prediction in
  **33–47%** of studies (range depends on the analysis subset).
- Clinical prediction substantially outperformed mechanical in only **6–16%** of
  studies; the remainder were ties.
- On average, mechanical techniques were **~10% more accurate** than expert
  judgment.

**Equity-analysis translation.** The finance analogue has a nuance worth stating:
on *short-horizon EPS*, human analysts historically beat naive time-series models —
Fried & Givoly (1982) found analyst forecast errors of 16.4% vs 19.3% for
time-series models on annual EPS [22]. Analysts bring fresh non-numerical
information that stale time-series rules lack. But:

- "Commonly used linear earnings models do not work out-of-sample and are inferior
  to those analysts provide" — yet a *modern ML* benchmark beats the analysts and,
  unlike them, is unbiased [10].
- The verdict of the Grove literature is about *judgment given the same
  information*. Where quant screens and analysts use the same inputs (valuation
  ratios, momentum, quality), the model wins by combining inputs consistently;
  analyst edge is confined to genuinely new, non-quantifiable information [10][9].

**Implication.** A deliberating team of human-style experts is, per the
meta-analytic record, roughly break-even against a simple equal-weighted or
regression rule on the same inputs. The Room must clear the "mechanical baseline"
bar, not just the "average expert" bar, to claim skill.

---

## 3. Analyst forecast accuracy & optimism bias (academic measurement)

*(Cross-references the sell-side sibling doc, which covers the industry structure
and incentives; here we record the measured magnitudes.)*

**Error magnitudes — Dreman & Berry (1995), *Financial Analysts Journal* [7].**
The largest early I/B/E/S-style study: 66,100 quarterly consensus estimates,
~1,200 companies, Q1 1974 – Q1 1991:

- **73.3%** of consensus estimates fell outside a ±5% band around actual EPS;
  **55.6%** outside ±10%; **43.75%** outside ±15% — even though estimates were
  revised as late as two weeks before quarter-end.
- Average absolute surprise exceeded **20% of actual EPS** (SURPE metric; ~41.5%
  of forecast EPS on the SURPF metric).
- Negative surprises outnumbered positive ones, and mean negative surprises
  (−64% to −72% depending on cycle phase) were far larger in magnitude than mean
  positive ones (+23%) — the signature of systematic optimism with occasional large
  misses.
- **Errors were increasing over time** (significant positive trend across all four
  surprise metrics), despite better data and real-time distribution. Earlier
  studies they review: consensus errors of 22.7% (1973), 24.1%/yr (1972–76),
  59.6% in 1974 alone, and a 16.6% composite for 1960–76 — i.e., accuracy did
  **not** improve over three decades.

**Optimism bias — McKinsey (2010) [8].** Over the prior 25 years, analysts'
S&P 500 earnings-growth expectations ran at **10–12% per year** against ~**6%**
realized — on average forecasts were close to double actual growth. Exceptions
(1988, 1994–97, 2003–06) occurred only when strong growth let reality catch up
with earlier predictions.

**The walk-down.** Analysts issue optimistic forecasts early in the fiscal period
and revise down toward a beatable number as earnings approach: early-fiscal-year
optimism is highest and declines monotonically as the horizon shortens [23][24].
Related dividend-forecast evidence: initial optimism of 0.15% of price in Q1 walked
down to 0.01% by Q4 [25]. The ML-benchmark literature confirms the pattern
structurally: conditional bias in analyst EPS expectations is positive on average
and **increases in the forecast horizon** [10]. Malmendier & Shanthikumar and the
"walk-down to beatable forecasts" literature (e.g., Ham et al. 2022, *Review of
Accounting Studies*) tie the late-period pessimism to incentives around equity
issuance and insider trading [26].

**Relative accuracy.** Individual-analyst accuracy is persistent but weakly so;
the *consensus* (simple mean) is the relevant accuracy benchmark, and even it
misses by the Dreman–Berry magnitudes above. Herding compresses the value of the
consensus further (Section 4).

---

## 4. Wisdom of crowds vs team deliberation

**Forecast combination (Clemen 1989 and 50 years of follow-up) [11][12]:**

- Clemen's review (*International Journal of Forecasting*, 1989; 3,500+ citations)
  established that combining forecasts reliably improves accuracy and that the
  **simple arithmetic average is the most robust combination rule** — "practical,
  economical and useful."
- The modern 50-year review (Wang et al. 2023, *IJF*) states the unanimous
  conclusion: "simple combination schemes are hard to beat"; equally weighted
  averages dominate estimated "optimal" weights out of sample (the *forecast
  combination puzzle*), because forecasters share public information and make
  correlated errors [12].
- Mechanism: averaging cancels *independent* error. When errors are strongly
  correlated, the combination premium collapses [12].

**Prediction markets vs polls [13].** Berg, Nelson & Rietz (2008): across 964
national polls in the five US presidential elections 1988–2004, the Iowa
Electronic Markets vote-share price was closer to the actual result **74% of the
time**, and significantly outperformed polls in every election when forecasting
**more than 100 days ahead**. Market aggregation of diverse, incentivized opinions
beats both expert pollsters and (by extension) most individual experts.

**Structured teams — the Good Judgment Project (Mellers et al. 2014,
*Psychological Science*) [14][15]:**

- Randomized interventions in the IARPA tournament showed **training, teaming, and
  tracking** each improved calibration and resolution.
- Team forecasters beat "crowd-belief" forecasters, who beat independent
  individuals — deliberation helped *when* teams shared information, debated
  rationales, and were aggregated afterward. Grouping the top 2% into elite teams
  produced superforecaster teams that were the most accurate condition of all
  [14][20].
- GJP's superforecasters beat rival research teams by **35–72%** and intelligence
  analysts by ~**30%** [20]. (Single-source-adjacent: the 30% figure traces to
  GJP's own track-record page and David Ignatius's Washington Post reporting; treat
  as organization-reported.)

**Where deliberation hurts — herding:**

- **Analyst herding (Hong, Kubik & Solomon 2000, *RAND Journal*):** inexperienced
  analysts are more likely to be terminated for inaccurate forecasts, and —
  controlling for accuracy — for *bold* forecasts. Career risk therefore pushes
  analysts toward the consensus: the observed consensus is herded, not independent,
  which degrades the diversity that averaging needs [27].
- **Institutional herding (Sias 2004, *RFS*):** institutional demand is correlated
  across adjacent quarters; a large component comes from institutions following
  *each other's* trades — correlated action that transmits rather than cancels
  error [28].
- Groupthink mechanics: classic group-decision research (process loss, information
  cascades) predicts that unstructured deliberation amplifies shared bias; the GJP
  result is that deliberation only pays when paired with independence of initial
  estimates, explicit base-rate training, and ex-post aggregation [14][11].

**When does a team beat its best member?** Almost never by deliberation alone in
this literature. The reliable ordering is: best structured aggregation of
independent forecasts ≥ trained/tracked teams > simple average of independent
forecasts > average individual > deliberating unstructured group (risk of cascade)
[14][11][12]. The Room's architecture (independent specialist passes → adversarial
debate → gatekeeper aggregation) maps onto the winning recipe *only if* the
specialist passes are genuinely independent and the aggregation is mechanical
rather than consensus-seeking.

---

## 5. Man vs machine in equity forecasting

**AI analyst vs I/B/E/S analysts — Cao, Jiang, Wang & Yang, "From Man vs. Machine
to Man + Machine," *Journal of Financial Economics* (2024; NBER WP 28800, 2021)
[9][29]:**

- The ML "AI analyst" (ensemble of state-of-the-art models; firm, industry, macro
  variables plus disclosure/news/social text, truncated before each human forecast)
  **outperforms human analysts as a whole: it wins 54.5% of all stock-return
  (target-price-implied) predictions** made by I/B/E/S analysts, 2001–2018.
- **Bias decomposition:** comparing against machine-*debiased* analyst forecasts
  (MDM), humans still lose — MDM beats the AI in only **46.5%** of forecasts —
  implying correctable human biases explain **~22%** of the man–machine gap; the
  rest is raw information-processing advantage [9].
- **Man + Machine:** adding analyst forecasts to the model's information set beats
  the AI-only model in **54.8%** of forecasts — the "centaur" is the best
  configuration [9].
- Humans retain the edge for **illiquid, small, intangible-heavy firms** and in
  **distress** (rare events ML can't learn); the AI's edge is largest when
  information is high-dimensional, transparent, and voluminous — and its edge
  *declined over time* as analysts gained alternative data and in-house AI [29].
- *Version discrepancy:* the working paper reported the AI winning 55.9% of target
  -price predictions and 48.2% against debiased analysts [30]; the published JFE
  figures (54.5% / 46.5%) are canonical.

**ML earnings benchmarks — van Binsbergen, Han & Lopez-Lira, "Man versus Machine
Learning," *Review of Financial Studies* (2023) [10]:**

- A statistically optimal ML benchmark for firm earnings expectations is unbiased;
  analysts' conditional expectations are **biased upward on average, with bias
  increasing in the forecast horizon**.
- The bias measure has cross-sectional return predictability (negative): the most
  optimistically-forecast firms populate the short legs of many anomalies, and
  their managers are more likely to issue equity [10].
- Note the asymmetry vs Section 2: *simple linear* earnings models fail
  out-of-sample and lose to analysts; *modern ML* beats them. The bar is "good
  model," not "any model."

**Machine-readable disclosure (context) — Cao, Jiang, Yang & Zhang, "How to Talk
When a Machine Is Listening," *RFS* (2023) [31]:** firms now actively manage
filing sentiment and even earnings-call audio emotion for machine readers, proxied
by machine downloads of EDGAR filings — evidence that machine consumption of
disclosure is large enough to change corporate behavior. Not a head-to-head
accuracy study, but it establishes that machines are the marginal processor of
exactly the information the Room consumes.

**Older man-vs-model evidence:** Ou & Penman-style financial-statement models
predicted EPS direction up to 36 months out, "direct evidence of the inability of
analysts to forecast earnings with a high degree of accuracy" [7]; Azevedo et al.
(2021) show a cross-sectional model *combined with* analyst forecasts beats raw
analyst forecasts [32].

**Corporate-finance ML benchmark (single-source, flagged):** an AI-enabled
earnings-forecast methodology reported ~**7%** lower mean absolute forecast error
than analyst consensus (Oliver Binz et al.; CFO-press coverage of an academic
study) [33]. Single source; not yet cross-checked against the paper itself.

---

## 6. Horizon dependence of forecasting skill

The evidence converges on a consistent picture: **human forecasting skill decays
fast with horizon; machine/statistical skill decays slower; market prices contain
real but horizon-specific structure.**

- **Expert judgment:** Tetlock's chance-level result is specifically a
  *long-horizon* result; experts were least inaccurate on near-term questions and
  degraded toward (and below) base-rate extrapolation as horizons lengthened [1][2].
- **Analyst EPS:** forecast *optimism* rises with horizon [10][23]; absolute errors
  grow with horizon (e.g., mean per-share optimism of $0.08 at 0–3 months vs $0.33
  at 18+ months in a buy-side forecast study — 8–16% of actual earnings at the long
  end [34]); the walk-down is the temporal signature of horizon-dependent bias
  [24][26].
- **Markets at short horizons have signal:** Jegadeesh & Titman (1993): buying past
  3–12-month winners and selling losers earns **~1% per month** (6-month formation
  produces ~1%/month regardless of holding period) [16]. Analyst-revision momentum
  (Chan, Jegadeesh & Lakonishok 1996) similarly predicts returns at quarterly
  horizons [35].
- **Markets at long horizons mean-revert:** DeBondt & Thaler (1985): portfolios of
  extreme prior losers beat extreme prior winners by roughly **25 percentage points
  cumulatively over 36 months** — long-horizon "predictability" is mostly reversal
  of overreaction, not forecastable growth [17].
- **Deep history:** Cowles (1933, *Econometrica*), the founding study of the entire
  genre — 16 financial advisory services' stock recommendations, 1928–1932 —
  concluded forecasters as a group would have earned **~1.5% per year less than the
  market**, and random predictions could not be statistically distinguished from
  the professionals. His three-word abstract: "It is doubtful" [36].

**Net:** at short horizons (days–quarters), modest but real signal exists and is
contested by both machines and informed humans; at long horizons (years), the
measured human bar collapses toward chance, optimism bias is largest, and the
winning "forecast" is usually a base-rate/mean-reversion rule.

---

## 7. Implications for Room benchmarking

- **The average-human-expert bar is near the floor, not the ceiling.** Tetlock,
  Meehl/Grove, Dreman–Berry, and Cowles all say: unaided expert judgment on
  long-horizon financial outcomes is barely above chance and below base-rate rules.
  The Room clearing "a typical analyst" proves almost nothing; the benchmark must
  include *mechanical baselines* (base-rate growth, equal-weight factor screen,
  consensus EPS itself) [1][4][7][36].
- **The honest human bar is the consensus + mechanical hybrid.** Simple averages of
  independent forecasts are robustly near-optimal [11][12]. The Room should be
  compared against the I/B/E/S-style consensus it could have read off the tape —
  and against a 50/50 blend of consensus and a quant screen [10][32].
- **Deliberation is a liability unless engineered.** Herding/cascade risk is the
  default for groups [27][28]; GJP shows teams pay off only with independence of
  first-pass estimates, base-rate training, tracking, and *mechanical* aggregation
  [14]. Benchmark the Room both ways: full deliberation vs independent-pass
  aggregation. If deliberation doesn't beat its own aggregated independent passes,
  it's groupthink with extra steps.
- **Expect a horizon gradient, and benchmark per horizon.** Bias and error grow
  with horizon [10][34]; momentum/reversal say the attainable signal differs by
  horizon [16][17]. Hit-rate targets should be horizon-indexed: e.g., short-horizon
  calls must beat momentum/base-rate blends; long-horizon calls should be scored
  against chance + base-rate drift, where even ~55% directional accuracy would be
  elite by human standards.
- **The machine bar is the strategic one.** The best published AI analyst beats the
  median human only 54.5% of the time, and the human+machine hybrid beats the
  machine 54.8% [9]. The Room is itself a machine; its real competitive frame is
  other models plus consensus hybrids, not pundits. A Room that merely matches the
  JFE AI-analyst win-rate profile is at the research frontier, not behind it.
- **Optimism control is measurable and mandatory.** The largest, most persistent
  human failure mode is upward bias that grows with horizon [7][8][10]. Room
  forecasts should be audited for sign bias per horizon; a well-calibrated Room
  should show near-zero mean signed error where humans show large positive bias —
  that is a cheap, decisive benchmark win.

---

## Sources

1. Tetlock, P. E., *Expert Political Judgment: How Good Is It? How Can We Know?*,
   Princeton University Press, 2005. Summary page:
   https://www.managementcraft.co/sources/expert-political-judgment
2. Lehrer, J., "Do Political Experts Know What They're Talking About?" (Tetlock
   interview), *Wired*, Aug 2011.
   https://www.wired.com/2011/08/do-political-experts-know-what-theyre-talking-about/
3. "Philip Tetlock: What Good Risk Judgment Actually Looks Like," Control Horizon,
   2026. https://controlhorizon.io/blog/philip-tetlock-superforecasting-risk
4. Grove, W. M., Zald, D. H., Lebow, B. S., Snitz, B. E., & Nelson, C., "Clinical
   Versus Mechanical Prediction: A Meta-Analysis," *Psychological Assessment*,
   12(1), 2000. PubMed abstract: https://pubmed.ncbi.nlm.nih.gov/10752360/ ;
   author PDF: http://zaldlab.psy.vanderbilt.edu/resources/wmg00pa.pdf
5. "Conditions for Intuitive Expertise: A Failure to Disagree" (Kahneman & Klein
   discussion incl. Grove et al. figures), 2025.
   https://www.winwin.university/conditions-for-intuitive-expertise-a-failure-to-disagree/
6. Pollock, R., "Notes on Meehl 1954 Clinical versus Statistical Prediction"
   (incl. Meehl's 1996 preface on Grove et al.: ≤5% of 136 studies favor the
   clinician), 2017.
   https://rufuspollock.com/2017/03/28/notes-on-meehl-1954-clinical-versus-statistical-prediction/
7. Dreman, D. N. & Berry, M. A., "Analyst Forecasting Errors and Their
   Implications for Security Analysis," *Financial Analysts Journal*, 51(3),
   May–Jun 1995, pp. 30–41. Author-hosted PDF:
   https://people.bath.ac.uk/mnsrf/Teaching%202011/IB/Literature/Literature07/dreman-berry.pdf
8. McKinsey & Company, "Equity analysts: Still too bullish," *McKinsey on
   Finance*, Apr 2010.
   https://www.mckinsey.com/capabilities/strategy-and-corporate-finance/our-insights/equity-analysts-still-too-bullish
   (figures cross-checked via Ritholtz, "McKinsey: Equity Analysts Are Still Too
   Bullish," 2010: https://ritholtz.com/2010/06/mckinsey-equity-analysts-are-still-too-bullish/)
9. Cao, S., Jiang, W., Wang, J. L., & Yang, B., "From Man vs. Machine to
   Man + Machine: The Art and AI of Stock Analyses," *Journal of Financial
   Economics*, 160, 2024. ScienceDirect:
   https://www.sciencedirect.com/science/article/pii/S0304405X24001338
10. van Binsbergen, J. H., Han, X., & Lopez-Lira, A., "Man versus Machine
    Learning: The Term Structure of Earnings Expectations and Conditional Biases,"
    *Review of Financial Studies*, 36(6):2361–2396, 2023.
    https://academic.oup.com/rfs/article/36/6/2361/6782974 ; NBER WP 27843 PDF:
    https://www.nber.org/system/files/working_papers/w27843/w27843.pdf
11. Clemen, R. T., "Combining Forecasts: A Review and Annotated Bibliography,"
    *International Journal of Forecasting*, 5(4), 1989. Author PDF:
    https://people.duke.edu/~clemen/bio/Published%20Papers/13.CombiningReview-Clemen-IJOF-89.pdf
12. Wang, X., Hyndman, R. J., Li, F., & Kang, Y., "Forecast Combinations: An Over
    50-Year Review," *International Journal of Forecasting*, 2023.
    https://www.sciencedirect.com/science/article/abs/pii/S0169207022001480 ;
    arXiv: https://arxiv.org/pdf/2205.04216
13. Berg, J. E., Nelson, F. D., & Rietz, T. A., "Prediction Market Accuracy in the
    Long Run," *International Journal of Forecasting*, 24(2), 2008.
    https://www.biz.uiowa.edu/faculty/trietz/papers/long%20run%20accuracy.pdf
14. Mellers, B., Ungar, L., Baron, J., et al. (incl. Tetlock), "Psychological
    Strategies for Winning a Geopolitical Forecasting Tournament," *Psychological
    Science*, 25(5):1106–1115, 2014. PubMed:
    https://pubmed.ncbi.nlm.nih.gov/24659192/ ; PDF:
    http://learnmoore.org/papers/Mellers%20et%20al%202014.pdf
15. Association for Psychological Science, "Predicting Uncertain Events on a
    Global Scale" (Mellers et al. 2014 summary: teams > crowd-belief >
    individuals), 2014.
    https://www.psychologicalscience.org/publications/observer/obsonline/predicting-uncertain-events-on-a-global-scale.html
16. Jegadeesh, N. & Titman, S., "Returns to Buying Winners and Selling Losers:
    Implications for Stock Market Efficiency," *Journal of Finance*, 48(1), 1993.
    PDF: https://www.bauer.uh.edu/rsusmel/phd/jegadeesh-titman93.pdf
17. DeBondt, W. F. M. & Thaler, R., "Does the Stock Market Overreact?" *Journal of
    Finance*, 40(3), 1985. (Long-horizon reversal; loser–winner spread ~25 pp over
    36 months — canonical figure, cited via standard summaries.)
18. "The Folly of Forecasting," InPhroNeSys, 2026 (EPJ summary incl. Tetlock's
    own correction of the chimp soundbite; reports 80,000+ forecast count).
    https://inphronesys.com/2026/04/29/the-folly-of-forecasting/
19. "Expert Problem," Faster Than Normal, 2026 (EPJ summary: experts worse than
    base-rate algorithms; fame negatively correlated with accuracy).
    https://fasterthannormal.co/mental-models/expert-problem
20. Good Judgment Inc., "The Superforecasters' Track Record" (GJP beat rival
    research teams by 35–72%; >30% more accurate than intelligence analysts —
    organization-reported), 2025.
    https://goodjudgment.com/resources/the-superforecasters-track-record/
21. Dawes, R. M., Faust, D., & Meehl, P. E., "Clinical Versus Actuarial Judgment,"
    *Science*, 243, 1989 (cited via SFU thesis summary: ~100 studies, statistical
    prediction consistently ≥ human judgment).
    https://summit.sfu.ca/_flysystem/fedora/2025-04/etd23544.pdf
22. Fried, D. & Givoly, D., "Financial Analysts' Forecasts of Earnings," *Journal
    of Accounting and Economics*, 4(2), 1982 (analyst error 16.4% vs time-series
    19.3%; cited via SciELO review).
    https://www.scielo.br/j/ram/a/h9ykx9zyYMPkRLBmrS8mjSM/?lang=en&format=html
23. "Uncertainty and Financial Analysts' Optimism: A Comparison between High-Tech
    and Low-Tech European Firms," *Sustainability* (MDPI), 15(3), 2023 (optimism
    highest ~11 months pre-release, declining as horizon shortens).
    https://www.mdpi.com/2071-1050/15/3/2270
24. Johnston, R. et al., "Crowdsourcing Forecasts: Competition for Sell-Side
    Analysts?" Rice University working paper, 2013 (walk-down of sell-side
    forecasts).
    https://business.rice.edu/sites/default/files/Crowdsourcing-Forecasts.pdf
25. "Dividend Guidance to Manage Analyst Dividend Expectations," *International
    Review of Economics & Finance*, 2020 (initial dividend-forecast optimism 0.15%
    of price in Q1 → 0.01% by Q4).
    https://www.sciencedirect.com/science/article/pii/S1057521918303892
26. Ham, C. G. et al., "Rationalizing Forecast Inefficiency," *Review of Accounting
    Studies*, 2022 (walk-down to beatable forecasts literature).
    https://link.springer.com/article/10.1007/s11142-021-09622-8
27. Hong, H., Kubik, J. D., & Solomon, A., "Security Analysts' Career Concerns and
    Herding of Earnings Forecasts," *RAND Journal of Economics*, 31(1):121–144,
    2000. PDF: http://www.columbia.edu/~hh2679/rje-analyst.pdf
28. Sias, R. W., "Institutional Herding," *Review of Financial Studies*, 17(1),
    2004 (cited via standard references; institutions following each other's
    trades).
29. EconPapers abstract, NBER WP 28800 (2021 version of [9]: AI edge strongest for
    complex firms / voluminous information; declines as analysts adopt AI).
    https://econpapers.repec.org/RePEc:nbr:nberwo:28800
30. INQUIRE Europe, "From Man vs. Machine to Man + Machine" (working-paper
    figures: AI wins 55.9% of target-price predictions; 48.2% vs debiased
    analysts), 2023.
    https://www.inquire-europe.org/news/in-case-you-missed-it-from-man-vs-machine-to-man-machine-the-art-and-ai-of-stock-analyses/
31. Cao, S., Jiang, W., Yang, B., & Zhang, A. L., "How to Talk When a Machine Is
    Listening: Corporate Disclosure in the Age of AI," *Review of Financial
    Studies*, 36(9):3603–3642, 2023. NBER WP 27950:
    https://www.nber.org/system/files/working_papers/w27950/revisions/w27950.rev0.pdf
32. Azevedo, V. et al., "Earnings Forecasts: The Case for Combining Analysts'
    Estimates with a Cross-Sectional Model," *Review of Quantitative Finance and
    Accounting*, 2021. https://link.springer.com/article/10.1007/s11156-020-00902-z
33. CFO, "Machine learning improves earnings forecast accuracy by 7%" (press
    coverage of Oliver Binz et al. study; single-source, flagged), 2026.
    https://www.cfo.com/news/ai-enabled-methodology-improves-earnings-forecast-accuracy-by-7-Oliver-Binz/808889/
34. "How Important Is Past Analyst Forecast Accuracy?" (buy-side forecasts; mean
    optimism $0.08/sh at 0–3 months vs $0.33/sh at 18+ months; 8–16% of actual
    earnings), ResearchGate.
    https://www.researchgate.net/publication/275900894_How_Important_Is_Past_Analyst_Forecast_Accuracy
35. Chan, L. K. C., Jegadeesh, N., & Lakonishok, J., "Momentum Strategies,"
    *Journal of Finance*, 51(5), 1996 (analyst-revision momentum; cited via
    consensus-anomaly literature).
36. Cowles, A. 3rd, "Can Stock Market Forecasters Forecast?" *Econometrica*, 1(3),
    1933. Cowles Foundation history (three-word abstract "It is doubtful";
    ~1.5%/yr below-market for follower of 16 services):
    https://cowles.yale.edu/sites/default/files/2022-08/history-cowles.pdf

---

*Method note: headline figures for Grove et al. (2000), Berg et al. (2008),
Dreman & Berry (1995), Cao et al. (2024), and Mellers et al. (2014) were
cross-checked against at least two independent sources (primary PDF/abstract plus
secondary academic citation). Tetlock sample-size counts, the GJP 30% figure, and
the ~7% ML-vs-consensus figure [33] are single-source or disputed and are flagged
inline.*
