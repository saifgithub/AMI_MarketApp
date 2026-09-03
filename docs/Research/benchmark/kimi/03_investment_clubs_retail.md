# Investment Clubs & Retail Teams — Human Benchmark Deep Dive

Research date: 2026-08-09. Scope: amateur human teams (investment clubs, retail
groups) as the closest human comparator to AMI Trade's Room users. Every number
carries a citation to the Sources list; single-source figures are flagged.

---

## Executive summary — headline numbers

- **Investment clubs (US, 1991–1997, 166 clubs):** average net annual return
  **14.1% vs S&P 500 at 18.0%** — a 3.7pp/yr shortfall against a passive index
  fund. **60% of clubs (100 of 166) underperformed the market index** [1].
- **Clubs underperform even individual retail investors by ~2pp/yr net** — the
  "team of amateurs" does worse than the lone amateur [1].
- **Retail households (US, 66,465 households, 1991–1996):** average net return
  **16.4% vs market 17.9%**; the **highest-turnover quintile earned 11.4% net
  vs 18.5%** for the lowest-turnover quintile [2].
- **Taiwan (1995–1999, 3.9M individual investors):** active trading cost
  individuals **3.8pp of portfolio return per year**; aggregate losses ≈
  **2.2% of Taiwan's GDP**; institutions earned +1.5pp/yr on the other side [4].
- **Taiwan day traders (1992–2006):** only **~20% earn positive net abnormal
  returns in a given year**, and **fewer than 1% (~4,000 of ~450,000/yr) are
  predictably profitable net of fees** year over year [5].
- **Brazil (2013–2015 cohort of 19,646 new futures day traders):** of the
  1,551 who persisted beyond 300 sessions, **97% lost money**; only **1.1%
  earned more than minimum wage** [6][7][8].
- **BetterInvesting/NAIC collapse:** from ~37,000 affiliated clubs in 1998
  (~11% of US adults in some investment club) to 9,500 member clubs by 2007
  and ~3,000 clubs / 34,000 members by end-2018 [1][10][11].
- **WallStreetBets-era evidence:** WSB "due diligence" buy reports had
  predictive value before the GameStop event, but advice **quality
  deteriorated sharply after the 2021 influx**; a naive WSB-following
  long/short strategy earns **no risk-adjusted alpha** at any horizon from
  1 day to 1 year [13][14][15].

---

## 1. The Barber–Odean investment club study ("Too Many Cooks Spoil the Profits", 2000)

**Citation:** Barber, B.M. & Odean, T. (2000), *Financial Analysts Journal*,
Jan/Feb 2000 [1]. Cross-checked against CBS News secondary summary [9].

**Sample & method.** 166 investment clubs randomly drawn from account data of a
large US discount brokerage (the same 78,000-household dataset as [2]),
**February 1991 – January 1997** (72 months). Returns computed from month-end
position statements + CRSP; net returns deduct actual commissions and estimated
bid–ask spread per trade. Performance benchmarks: own-benchmark (beginning-of-
year buy-and-hold portfolio), market-adjusted, CAPM Jensen's alpha, and
Fama–French three-factor alpha [1].

**Headline returns** [1]:

| Measure | Clubs | Individuals (same broker) | Market |
|---|---|---|---|
| Net annual return | **14.1%** | 16.4% [2] | S&P 500: **18.0%**; VW NYSE/Amex/Nasdaq: **17.9%** |
| Shortfall vs passive index fund (net) | **−3.7 pp/yr** | ~−1.5 pp/yr [2] | — |
| Shortfall vs individuals (net) | **~−2 pp/yr (~16 bps/month)** | — | — |

**Risk-adjusted net alphas (per year)** [1]:

| Benchmark | Net underperformance |
|---|---|
| Market-adjusted | ~3 pp (not statistically significant) |
| Own-benchmark (buy-and-hold counterfactual) | **3.5 pp** |
| Jensen's alpha (CAPM) | 4.8 pp |
| Fama–French 3-factor alpha | **4.4 pp** |

**Other exact figures** [1]:
- **60% of clubs (100 of 166) underperformed** the broad market index — directly
  inverting the NAIC survey claim that "60% of clubs beat the market." Gross
  (pre-cost), the median club actually beat the market by 0.075 pp/month and
  54.8% of clubs beat the market; costs flip the result.
- Clubs held on average **7.5 stocks worth $37,416** (individuals: 4.3 stocks,
  $47,334); club portfolios were **~30% less volatile** (monthly SD 6.0% vs
  8.7% for individuals).
- Annual turnover **65%** (avg holding period ~18 months) vs ~75–76% for
  individuals and 78% for mutual funds.
- Transaction costs: average round trip ~**1% bid–ask spread + ~7% commissions**
  for clubs vs ~5% commissions for individuals — clubs trade smaller, so
  proportional costs are higher (~5 bps/month worse).
- Clubs tilted to **small-cap, high-beta growth stocks** (per NAIC's own advice
  to "buy growth stocks"); the growth tilt cost them ~11 bps/month vs
  individuals.
- **Security selection was perverse:** stocks clubs *bought* underperformed
  stocks they *sold* by **0.35–0.41 pp/month (4.2–4.9 pp/yr)** — the same
  pattern Odean (1999) found for individuals.

**Why clubs lose to individuals (~2 pp/yr):** (1) smaller trades → higher
proportional commissions (~5 bps/month); (2) stronger growth tilt (~11 bps/month)
[1].

**The Beardstown Ladies cautionary tale** (from the paper's framing and [12]):
the famous club promoted a 23.4% annual return (1983–1994; the FAJ paper's
epigraph quotes 23.6% for 1983–1992 per the *Chicago Tribune* — minor
discrepancy across press sources); a Price Waterhouse audit found the real
return was **9.1%/yr vs 14.9% for the S&P 500** over the same period. NAIC's own
survey-based claims ("60% of clubs beat the market"; "42.9% equaled or exceeded
the S&P 500" on the NAIC website in Oct 1998) suffer selection, survivorship,
and self-calculation biases; the brokerage-data study shows the opposite [1][12].

---

## 2. Retail household performance — "Trading Is Hazardous to Your Wealth" (2000)

**Citation:** Barber, B.M. & Odean, T. (2000), *Journal of Finance* 55(2),
773–806 [2].

**Sample:** 66,465 households with common-stock positions at a large US discount
broker, **1991–1996** (returns Feb 1991 – Jan 1997) [2].

**Exact figures** [2]:

| Group | Gross annual return | Net annual return |
|---|---|---|
| Market (VW NYSE/Amex/Nasdaq) | 17.9% | (Vanguard 500 fund ≈ index) |
| Aggregate household portfolio | 18.2% | 16.7% |
| **Average household** | **18.7%** | **16.4%** |
| Lowest-turnover quintile | ~market-like | **18.5%** |
| **Highest-turnover quintile** | ~market-like | **11.4%** |

- Average household turnover: **>75%/yr**; the top quintile turned over
  **>250%/yr** [2].
- Round-trip trading cost: ~3% commissions + ~1% spread on trades > $1,000 [2].
- Gross returns are ~market-matching: essentially **all** of the 1.5pp/yr
  average shortfall (and the 7.1pp gap between turnover quintiles) is trading
  costs + perverse trade timing, not portfolio selection. The own-benchmark
  test shows buy-and-hold would have beaten actual trading [2].
- Gender slice (same dataset, QJE 2001): **men trade 45% more than women**;
  excess trading cuts net returns by **2.65 pp/yr for men vs 1.72 pp/yr for
  women** [3].

---

## 3. Day-trader survival / success rates

| Study | Market & period | Sample | Profitable in a typical period | Persistently profitable |
|---|---|---|---|---|
| Barber, Lee, Liu & Odean, *JFM* 2014 [5] | Taiwan stocks, 1992–2006 | ~450,000 day traders/yr; 277,000 "heavy" (>$20k US/yr); full exchange data | **~20%** (17–20% by definition) earn positive **net** abnormal returns in a given year | **<1% (~4,000)** predictably profitable net of fees; top 500 earn +61.3 bps/day gross (+37.9 net) in year y+1; bottom-ranked lose −11.5/−28.9 bps/day [5] |
| Barber, Lee, Liu & Odean 2004 working paper (via [16]) | Taiwan stocks, 1995–1999 | Full exchange data | — | **>80% of day traders lose money over a six-month horizon** (secondary-source figure [16]) |
| Barber, Lee, Liu & Odean, *RFS* 2009 [4] | Taiwan stocks, 1995–1999 | 3.9M individuals, complete market data | Aggregate individuals lose **3.8 pp/yr**; ≈ NT$935bn ≈ **2.2% of GDP**, 2.8% of personal income; turnover ~300%/yr | Institutions earn +1.5 pp/yr — retail losses fund institutional gains [4] |
| Chague, De-Losso & Giovannetti 2020 [6][7][8] | Brazil, mini-Ibovespa equity futures; cohort starting 2013–2015, tracked to 2019 | 19,646 individuals | — | Of **1,551** who persisted >300 sessions: **97% lost money**; **1.1%** earned > minimum wage; **0.5%** > a bank teller's salary; best performer averaged US$310/day with US$2,560 std dev [7][8] |

Notes on consistency:
- The Taiwan <1% and Brazil 97%-lose figures are consistent in shape: a thin,
  real, *persistent* skill elite exists, but it is far too small to be a
  reachable bar for the median user. The 2014 Taiwan paper also documents
  **performance persistence** — past winners keep winning, past losers keep
  losing — which is what makes year-over-year profitability the right test [5].
- Chague et al.'s literature review notes that both Barber et al. (2014) and
  Barber et al. (2019, "Learning, Fast or Slow") find **<3% of frequent day
  traders consistently profitable** [8].
- The 1,551 persistent-trader count is single-source via secondary summary [7];
  the 19,646 cohort and 97%/1.1% figures appear in two independent secondary
  sources [7][8]. The underlying working paper is [6].

---

## 4. BetterInvesting / NAIC club data

- **Peak:** the NAIC reported **>35,000 affiliated clubs in May 1998** [1];
  sociological sources put the 1998 high-water mark at **just over 37,000
  clubs**, with an estimated **~11% of the US adult population** belonging to
  some investment club (not all NAIC-affiliated) [10]. Minor discrepancy
  between sources (>35,000 vs ~37,000) — both cited.
- **Decline:** **9,500 member clubs by 2007** [10]; **~3,000 clubs and ~34,000
  individual members at end-2018** [11]. That is a >90% decline in affiliated
  clubs over two decades. (Press reports a modest post-2020 club-formation
  uptick, but from a small base — single-source, not relied on here.)
- **Performance stats published by the organization itself are survey-based and
  unreliable:** the "60% of clubs beat the market" claim inverted under audit
  [1]; the Beardstown Ladies' self-calculated 23.4%/yr was actually 9.1%/yr
  vs 14.9% for the S&P 500 [1][12]. The organization's "BetterInvesting 100"
  most-held-stocks list reportedly outpaced the S&P 500 Equal Weight index
  18.88% vs 16.37% (5-yr CAGR to Oct 2021) — but that is an index of popular
  holdings, **not measured club portfolio returns** (single-source press
  report; treat as marketing, not performance data) [9-adjacent; see Sources 10–12 for context].
- **Survival bias warning:** Barber & Odean explicitly note that if poor
  performance causes clubs to disband, any survey of surviving clubs overstates
  club performance [1]. Club survival-rate statistics are not reliably
  published; the membership collapse above is the best available proxy.

---

## 5. Group dynamics — do amateur teams help or hurt?

The evidence says **hurt, modestly but reliably**:

- **Direct comparison:** in identical market conditions with an identical
  broker, clubs underperformed individual investors by ~2 pp/yr net [1]. The
  amateur *team* is a worse investor than the amateur *individual*.
- **Mechanism 1 — costs:** teams trade smaller per position (pooling across
  members), so proportional commissions are higher (~5 bps/month drag) [1].
  (Mostly a 1990s artifact; near-zero commissions today shrink this channel.)
- **Mechanism 2 — style convergence on bad advice:** clubs systematically
  followed NAIC's growth-stock tilt, which cost ~11 bps/month in the sample;
  group membership homogenized style toward an underperforming template [1].
- **Mechanism 3 — consensus does not debias timing:** clubs, like individuals,
  bought stocks that went on to underperform the stocks they sold by 4.2–4.9
  pp/yr [1]. Deliberation and voting did not correct the perverse
  attention/momentum-driven trade timing documented for individuals.
- **Attention-driven buying:** individuals (and by extension amateur groups)
  are net buyers of attention-grabbing stocks — high volume, extreme returns,
  in the news — because attention solves the search problem but not the
  valuation problem (Barber & Odean, "All That Glitters," *RFS* 2008; reviewed
  in their 2011 handbook chapter [17]).
- **Sociological evidence:** ethnographic work on investment clubs (Brooke
  Harrington, *Pop Finance*, 2008; summary in [10]) documents that clubs
  function primarily as social groups; cohesion and consensus-seeking shape
  decisions as much as analysis does — consistent with the observed
  groupthink-style convergence rather than "wisdom of crowds."
- **The one thing groups did better:** diversification. Clubs held ~2× as many
  stocks as individuals and ran ~30% lower volatility [1]. Teams reduced risk
  but did not add return.

Net: **an amateur team is a diversification device and a social device, not an
alpha device.**

---

## 6. Recent (2015+) social-trading / community evidence

- **WallStreetBets advice quality (RFS 2024):** Bradley, Hanousek, Jame & Xiao,
  "Place Your Bets? The Value of Investment Research on Reddit's Wallstreetbets,"
  *Review of Financial Studies* 37(5):1409 [13]. WSB "due diligence" buy reports
  had genuine short-horizon predictive value **before** the GameStop event;
  after the 2021 user influx, the quality/usefulness of advice **deteriorated
  materially, adversely affecting smaller investors** [13][14]. Scaling the
  crowd destroyed the crowd's edge.
- **Naive WSB-following earns nothing:** Chacon, Morillon & Wang (*Review of
  Behavioral Finance*, 2023) — a daily long-buy-recs / short-sell-recs WSB
  portfolio produces **no risk-adjusted alpha at horizons from 1 day to
  1 year**, despite WSB submissions predicting abnormal volume [15].
- **eToro copy-trading:** rigorous peer-reviewed performance data on copier
  outcomes remains thin. A quantitative study of the 30 most-recommended eToro
  investors found they **underperformed the S&P 500**, with a **negative
  correlation between copier count and abnormal return** (popularity predicts
  *worse*, not better, subsequent performance) — **single-source, bachelor-thesis
  quality; treat as suggestive** [18]. Regulatory disclosures across CFD/social
  platforms (typically ~70–80% of retail accounts lose money) are consistent
  but platform-specific and marketing-adjacent; not cited as a number here.
- **Aggregate retail flows:** Barber et al. (2009) note stocks heavily bought by
  retail positively predict short-term returns at market level [4-adjacent],
  but this flow effect does not translate into retail *portfolio*
  outperformance after costs.

---

## 7. Implications for Room benchmarking

- **The right human bar for "amateur team" is ~−3.7 pp/yr vs index, and −2
  pp/yr vs the lone retail investor** [1]. Beating an investment club is a low
  bar — almost any disciplined process clears it. It is a sanity floor, not a
  target.
- **The meaningful bars, in ascending order:** (a) the average club (14.1% net
  in-sample [1]); (b) the average individual household (16.4% net [2]); (c)
  buy-and-hold / the index (17.9–18.0% [1][2]). Only (c) is a real claim to
  add value; (a) and (b) are "does the Room at least not replicate known
  amateur failure modes."
- **Simulation has no real transaction costs** — and costs are *the* mechanism
  that separates gross from net in every study here (clubs flip from
  market-beating gross to 3.7pp-losing net [1]; households' entire 1.5pp
  shortfall is costs + timing [2]). Benchmark runs must apply realistic
  synthetic costs, or the Room's edge over humans is partly an artifact.
- **Log the diagnostic metrics the literature uses, not just returns:**
  turnover (clubs 65%/yr, households 75%/yr, day traders 250%+ [1][2][5]);
  the **bought-minus-sold subsequent return spread** (amateurs: −4.2 to −4.9
  pp/yr [1]) — a direct test of whether the Room's trade *timing* beats amateur
  teams even if headline returns are noisy.
- **Persistence is the test that matters.** ~20% of day traders are profitable
  in any single year by chance; <1% are *predictably* profitable year over
  year [5]. Any benchmark claim for the Room needs multi-period evaluation;
  one good run proves nothing.
- **Frame it for the product's actual goal:** the Room teaches *these* users —
  people who, left alone, lose 1.5–3.8 pp/yr to their own trading [2][4].
  "Beats the user's counterfactual self" (own-benchmark abnormal return, the
  same construct Barber & Odean use [1][2]) may be a more honest and more
  pedagogically relevant bar than "beats the S&P 500."
- **Beware the club trap in the Room's design:** amateur teams failed through
  style convergence and consensus, not lack of effort [1][10]. The Room's
  12-agent diversity (bull/bear/risk debators) is architecturally the right
  antidote — the benchmark should verify the debate actually changes outcomes
  (e.g., ablation runs), not just that it exists.

---

## Sources

1. Barber, B.M. & Odean, T. (2000). "Too Many Cooks Spoil the Profits:
   Investment Club Performance." *Financial Analysts Journal*, Jan/Feb 2000.
   https://faculty.haas.berkeley.edu/odean/Papers%20current%20versions/FAJ%20JF00%20Barber%20and%20Odean.pdf
2. Barber, B.M. & Odean, T. (2000). "Trading Is Hazardous to Your Wealth: The
   Common Stock Investment Performance of Individual Investors." *Journal of
   Finance* 55(2), 773–806.
   https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/individual_investor_performance_final.pdf
3. Barber, B.M. & Odean, T. (2001). "Boys Will Be Boys: Gender, Overconfidence,
   and Common Stock Investment." *Quarterly Journal of Economics* 116(1),
   261–292. https://academic.oup.com/qje/article-abstract/116/1/261/1939000
   (PDF: https://econweb.ucsd.edu/~jandreon/Econ264/papers/Barber%20Odean%20QJE%202001.pdf)
4. Barber, B.M., Lee, Y.-T., Liu, Y.-J. & Odean, T. (2009). "Just How Much Do
   Individual Investors Lose by Trading?" *Review of Financial Studies* 22(2),
   609–632.
   https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/justhowmuchdoindividualinvestorslose_rfs_2009.pdf
5. Barber, B.M., Lee, Y.-T., Liu, Y.-J. & Odean, T. (2014). "The Cross-Section
   of Speculator Skill: Evidence from Day Trading." *Journal of Financial
   Markets* 18, 1–24.
   https://faculty.haas.berkeley.edu/odean/papers/day%20traders/The%20Cross-Section%20of%20Speculator%20Skill.pdf
6. Chague, F., De-Losso, R. & Giovannetti, B. (2020). "Day Trading for a
   Living?" USP Working Paper 2019_47 / FGV EESP TD 525.
   https://ideas.repec.org/p/spa/wpaper/2019wpecon47.html
7. Gorak, R. (2026). "Quitting Your Job to Day Trade? 97% of Persistent
   Traders Still Lose Money" (secondary summary of [6]). tradicted.com.
   https://www.tradicted.com/research/chagu-day-2020/
8. One Day Investor (2026). "I Lost $3,000 Trading Crypto. The Research Says
   I'm Not Alone" (secondary summary of [6]; also corroborates [5]).
   https://blog.odinvestor.net/why-trading-is-a-losing-game
9. CBS News (2010). "Bad Investors: Single Men and Investing Clubs" (secondary
   corroboration of [1]: 166 clubs, 14.1% vs 17.9%, −4.4pp FF alpha, 65%
   turnover, −3.5pp own-benchmark).
   https://www.cbsnews.com/news/bad-investors-single-men-and-investing-clubs/
10. The Society Pages / Contexts (2009). "Things that Come in Threes: Queries
    and Speculations About Investment Clubs" (club participation history:
    ~37,000 clubs 1998, 11% of US adults, 9,500 clubs 2007; sociology of
    clubs, cf. Harrington, *Pop Finance*, Princeton UP, 2008).
    https://thesocietypages.org/eye/2009/01/29/things-that-come-in-threes-queries-and-speculations-about-investment-clubs/
11. Investopedia. "National Association of Investors Corp (BetterInvesting)
    Overview" (~3,000 member clubs, ~34,000 individual members at end-2018).
    https://www.investopedia.com/terms/n/naic.asp
12. Rockstar Finance. "The History of F.I.R.E" (Beardstown Ladies: 23.4%
    claimed vs 9.1% audited vs 14.9% S&P 500).
    https://rockstarfinance.com/history-of-financial-independence-early-retirement-movement
13. Bradley, D., Hanousek, J., Jame, R. & Xiao, Z. (2024). "Place Your Bets?
    The Value of Investment Research on Reddit's Wallstreetbets." *Review of
    Financial Studies* 37(5), 1409.
    https://www.ebsco.com/articles/business-and-management/cf6a3620-b1a9-5907-94b9-b492bd0db320/place-your-bets-the-value-of-investment-research-on-reddit-s-wallstreetbets
14. SuchScience (2024). "New study finds WallStreetBets tips have declined in
    predictive value since 2021" (secondary summary of [13]).
    https://suchscience.net/wallstreetbets-tips-declined-in-value-after-gamestop/
15. Chacon, R.G., Morillon, T. & Wang, R. (2023). "Will the Reddit Rebellion
    Take You to the Moon? Evidence from WallStreetBets." *Review of Behavioral
    Finance* (Springer).
    https://link.springer.com/content/pdf/10.1007/s11408-022-00415-w.pdf
16. Asia-Pacific Journal of Financial Studies (apjfs.org) — literature-review
    corroboration of Barber, Lee, Liu & Odean (2004), "Do Individual Day
    Traders Make Money? Evidence from Taiwan" (>80% lose over six months).
    https://apjfs.org/file/download/6408?view=1
17. Barber, B.M. & Odean, T. (2011). "The Behavior of Individual Investors"
    (handbook chapter reviewing "All That Glitters," RFS 2008, attention-driven
    buying).
    https://www.umass.edu/preferen/You%20Must%20Read%20This/Barber-Odean%202011.pdf
18. Universitat Rovira i Virgili TFG repository (2020). Quantitative analysis of
    eToro's 30 most-recommended investors (underperformance vs S&P 500;
    negative copier-count/abnormal-return correlation). **Single-source,
    student thesis — suggestive only.**
    https://repositori.urv.cat/repositori/getDocument/TFG:4849?ds=Memòria&mime=application/pdf
