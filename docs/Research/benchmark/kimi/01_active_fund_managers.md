# Active Fund Managers — Human Benchmark Deep Dive

Research date: 2026-08-09. Scope: professional active US equity fund managers as the
primary human benchmark for the AMI Trade "Room" (12-agent AI analyst team).
Every figure carries a citation to the numbered Sources list at the bottom.

---

## Executive summary

- **1-year (2024):** 65% of all active large-cap US equity funds underperformed the
  S&P 500 — slightly worse than the 64% average annual failure rate over the
  scorecard's 24-year history [1][2]. In 2025 this worsened to 79%, the
  fourth-worst year in 25 years of SPIVA data [3].
- **Long horizons are brutal:** over the 15 years ending December 2024, **89.5%** of
  active large-cap funds trailed the S&P 500, and over 20 years **91.99%** did [1][4].
  Across all domestic equity funds vs the S&P Composite 1500, the 20-year failure
  rate was **94.11%** [4].
- **No refuge in any category:** over the 15 years ending December 2024, there was
  **no equity fund category** in which a majority of active managers outperformed [2].
- **Morningstar (investable-passive benchmark, survivorship-adjusted):** only **42%**
  of active funds survived and beat their average passive peer in 2024; over 10
  years to December 2025 just **21%** did — and only **10%** in US large-cap [5][6].
- **Behavior gap (Dalbar QAIB):** the average equity fund investor earned **16.54%**
  in 2024 vs the S&P 500's **25.02%** — an **848 bps** gap, the second-largest of
  the decade [7]. In 2025 the gap narrowed to **72 bps** (17.16% vs 17.88%), the
  third-smallest since 1985 [8].
- **Skill exists but doesn't cover fees:** Fama & French (2010) find that net of
  fees, only funds around the **98th–99th percentile** show statistically
  significant skill — fewer than pure luck would produce [9]. Berk & van Binsbergen
  (2015) find the average fund adds **~$3.2M/year** of gross value, but competition
  drives net alpha to ~zero [10].
- **Outperformance doesn't persist:** of the top-quartile domestic equity funds of
  December 2020, **zero** remained top-quartile four years later; only **2.4%** of
  top-half large-cap funds stayed top-half for five consecutive years vs **6.25%**
  expected by chance [4][11].
- **Fees are the biggest controllable lever:** cheapest-quintile active funds had a
  **31%** 10-year success rate vs **17%** for the priciest quintile (10 years to
  December 2025) [4].

---

## SPIVA US Scorecard results

SPIVA (S&P Indices Versus Active), published semiannually since 2002, fixes the
fund universe at the start of each period (survivorship-bias corrected) and
measures fund returns **net of fees, excluding loads**, against a costless index [4].

### All Large-Cap Funds vs S&P 500 — % underperforming (SPIVA US Year-End 2024, data as of Dec 31, 2024) [1][4]

| Horizon | % underperforming S&P 500 | Implied % beating |
|---|---|---|
| 1 year | 65.24% (reported as "65%") | ~35% |
| 3 years | 84.96% | ~15% |
| 5 years | 76.26% | ~24% |
| 10 years | 84.34% | ~16% |
| 15 years | 89.50% | ~10.5% |
| 20 years | 91.99% | ~8% |

Cross-check: the 1-year figure (65%) is confirmed directly by S&P DJI's own
year-end 2024 article [2]; the 3/5/10/15-year figures come from Barry Ritholtz's
reproduction of the SPIVA report table [1] and are independently corroborated
(85.0 / 76.3 / 84.3 / 89.5) by the Link Plan Management whitepaper citing the same
SPIVA year-end 2024 report [12]. The 20-year figure (91.99%) is cited verbatim
from SPIVA Report 1a by an independent data audit [4]. The 15-year figure (89.5%)
is separately confirmed by Attending Financial [13].

### Other headline SPIVA data points

- **All domestic funds vs S&P Composite 1500:** 79% underperformed in 2024 alone
  [14]; 94.11% underperformed over 20 years ending December 2024 [4].
- **2025 update (Year-End 2025 report):** 79% of large-cap funds underperformed the
  S&P 500 in 2025 — the fourth-worst year in 25 years of scorecards [3].
- **Mid-Year 2025 report:** H1 2025 was unusually kind to active managers — only
  54% of large-cap funds underperformed, 25% of mid-cap, and 22% of small-cap
  (the small-cap figure a record low) [15]. Over 20 years to June 2025: 91.03%
  of large-cap funds underperformed [4].
- **Survivorship:** of the 2,373 domestic equity funds existing at the start of the
  20-year window ending June 2025, only **37.29%** survived; among large-cap funds,
  34.70% of 758 starters survived [4]. Dead funds count as failures in SPIVA.
- **Magnitude of the gap (20 years to June 2025, annualized):** active large-cap
  funds returned **8.77%** equal-weighted / **9.48%** asset-weighted vs **10.73%**
  for the S&P 500 — asset-weighting closes only about a third of the gap [4].
- **Style consistency caveat:** only 47.70% of surviving funds kept the same style
  classification over 20 years [4].
- **2024 was the 15th consecutive year** in which a majority of large-cap funds
  underperformed the S&P 500 [14].

---

## Morningstar Active/Passive Barometer

Methodological difference from SPIVA: the benchmark is a composite of **real,
investable passive funds** (net of their fees), and success = **survived the entire
period AND outperformed** the passive composite. From year-end 2024 the passive
composite is asset-weighted with buy-and-hold weights [6].

| Report | 1-year success rate | 10-year success rate |
|---|---|---|
| Mid-year 2024 (to June 2024) | 51% ("basically a coin flip") | 29% [16] |
| Year-end 2024 (to Dec 2024) | 42% (3,200 active funds analyzed) | "Less than one in four" overall [6] |
| Year-end 2025 (to Dec 2025) | 38% (3,140 active funds) [17] | 21% overall; **10% US large-cap**; 22% mid-cap; 25% small-cap [4] |

Year-end 2024 category detail (1-year): US large-cap 37%, US mid-cap 37%, US
small-cap 43%; foreign stock-pickers 37%; fixed income and real estate aggregates
above 60% [6][18].

Fee effect (10 years to Dec 2024): cheapest-quintile funds succeeded 28% of the
time vs 17% for the priciest quintile [6]. For 10 years to Dec 2025 the cheapest
quintile rose to 31% vs 17% priciest [4].

Asset-weighting: over the 10 years to Dec 2024, the average dollar invested in
active funds beat the average active fund in **16 of 20** categories [6]; the
year-end 2025 edition reports **17 of 20** [4] (minor discrepancy between editions —
both confirm investors gravitate to cheaper/better funds).

Long-run large-growth carnage: of active US large-growth funds existing 20 years
ago, nearly **66% closed** and only **1%** both survived and outperformed their
average indexed peer [4].

Coverage context: the year-end 2024 barometer spans 9,200+ unique funds, ~$23T,
~68% of the US fund market [6]; the year-end 2025 edition covers 9,248 funds, ~$26T,
~67% [4].

---

## Dalbar QAIB — the investor behavior gap

QAIB (Quantitative Analysis of Investor Behavior, annual since 1994) measures the
return the *average investor* actually realizes (dollar-weighted) vs the index.

- **2024 (QAIB 2025, released Mar 31, 2025):** average equity investor **16.54%**
  vs S&P 500 **25.02%** → **848 bps gap**, second-largest of the past decade.
  Equity funds saw outflows in every quarter of 2024, with the largest just before
  a major return surge [7]. (The PR Newswire version prints the S&P 500 return as
  25.05%; Dalbar's own press release says 25.02% — a 3 bp discrepancy between the
  two releases [7][19].)
- **2023 (QAIB 2024, 30th annual report):** the average equity investor earned
  **5.5 percentage points less** than the S&P 500 [20].
- **2025 (QAIB 2026, released Apr 2026):** average equity investor **17.16%** vs
  S&P 500 **17.88%** → gap narrowed to **72 bps**, the third-smallest since 1985
  and lowest since 2012 [8].
- **Long-horizon figures vary by edition** (Dalbar revises windows annually; treat
  as directional): QAIB 2023 reported ~**3.6% annualized** for the average equity
  investor vs ~**10.0%** for the S&P 500 over 30 years [21]; a separate summary of
  the 30 years ending 2022 puts it at **6.81% vs 9.65%** (2.84 pp/year gap) [22].
  Methodology note: Dalbar's long-term investor-return math has attracted academic
  criticism, so the multi-decade point figures should be quoted with their edition
  year; the year-by-year gaps (2023: 5.5 pp; 2024: 8.48 pp; 2025: 0.72 pp) are the
  directly reported, verifiable numbers [7][8][20].

---

## Academic evidence

### Fama & French (2010), "Luck versus Skill in the Cross-Section of Mutual Fund Returns," Journal of Finance 65(5): 1915–1947 [9][23]

- Bootstrap analysis of US equity mutual funds, 1984–2006 (funds with ≥8 months of
  history and ≥$5M AUM in 2006 dollars) [23].
- **Net of fees:** the distribution of true alpha is centered below zero — most
  funds' results are indistinguishable from luck, and only managers around the
  **98th–99th percentiles** show statistically significant skill, *fewer* than
  chance alone would produce [9].
- Estimated distribution of true net alpha: **16%** of funds had true net alpha
  above +1.25%/yr and only **2.3%** above +2.5%/yr [24].
- **Gross of fees:** more funds show positive true alpha (i.e., genuine
  stock-picking skill exists in the right tail), but for the large majority the
  skill is insufficient to cover the fees charged — "few funds produce benchmark-
  adjusted expected returns sufficient to cover their costs" [9][24].

### Berk & van Binsbergen (2015), "Measuring Skill in the Mutual Fund Industry," Journal of Financial Economics 118(1): 1–20 [10][25]

- 6,000+ actively managed equity funds, Jan 1962 – Mar 2011, CRSP
  survivorship-bias-free database [25].
- Skill measured as **dollar value added** = gross abnormal return × AUM. The
  average fund generated **~$3.2 million/year** of value; the industry aggregate
  was **~$19 billion/year** [10][26].
- Cross-sectional differences in skill **persist for as long as ten years**, and
  investors rationally chase it (flows follow skill) [10][27].
- Key reconciliation with Fama-French: **net alpha is set by competition between
  investors, not by manager skill** — skilled managers capture their alpha as fees,
  so gross alpha (skill) is positive while net alpha ≈ 0. One literature review
  reports the average active fund's net alpha at **+36 bps/yr vs comparable index
  mutual funds** (the investable-passive comparison) [25].

### Persistence (S&P Persistence Scorecards)

- **US Persistence Scorecard Year-End 2024:** of top-quartile domestic equity funds
  as of December 2020, **not a single fund in any reported category** remained
  top-quartile four years later [4]. Top-half persistence over five consecutive
  years: **2.4%** of large-cap funds and **0.8%** of mid-cap funds, vs **6.25%**
  expected from a coin flip — i.e., *worse than random* [4]. Of funds that beat
  their benchmark in 2022, a cross-category average of just **8.3%** kept beating
  it in each of the next two years [4]. Bottom-quartile funds are where deaths
  come from: **25%** of fourth-quartile funds were merged or liquidated within five
  years, vs 7% of top-quartile funds [4].
- **US Persistence Scorecard Year-End 2025:** of 334 top-half large-cap funds in
  2021, 58.7% stayed top-half in 2022, only 6.9% through 2023, and **4.5%** through
  all five years to 2025; of 164 top-quartile large-cap funds in 2021, just 20.1%
  held the quartile in 2022 [28].
- Morningstar concurs: "less persistence of outperformance than randomly expected"
  is the consistent finding across SPIVA Persistence Scorecards [9].

---

## Team-managed vs solo-managed funds

Directly relevant to the Room, which is a *team* of specialized agents.

- **Prevalence:** team management is now the dominant structure — **>70%** of US
  domestic equity mutual funds were team-managed in recent years (Patel &
  Sarkissian 2017) [29].
- **Bär, Kempf & Ruenzi (2011), "Is a Team Different from the Sum of Its Parts?",
  Review of Finance 15(2): 359–396:** team-managed funds follow **less extreme
  investment styles**, hold **less risky portfolios**, show **lower industry
  concentration**, and produce **less extreme performance outcomes** than solo
  managers — consistent with a "diversification of opinions" effect, not
  groupthink toward extremes [30][31].
- **Chen et al. (2004):** after controlling for fund size, team-managed funds
  **underperform solo-managed funds by ~48 bps/year** on average, attributed to
  hierarchy/coordination costs [32]. The ResearchGate summary of the literature
  likewise notes Bär et al. (2011) and Chen et al. (2004) find teams deliver
  significantly lower performance on market-adjusted and factor-alpha measures [29].
- **Null results exist too:** Prather & Middleton (2002) and Karagiannidis (2010)
  find **no significant performance difference** between team- and solo-managed
  funds [33].
- **Dass, Nanda & Wang (2013)** (balanced funds): teams show **superior security
  selection** but **worse market timing** than solo managers — specialization helps
  stock-picking, coordination hurts top-down calls [34].

Net read: teams trade raw upside for consistency — fewer blowups, fewer home runs,
slightly lower average alpha, better diversification of judgment. For an education
product benchmark, the team-managed cohort is the fairer human comparison, and its
defining trait is *reduced extremity*, not higher mean return.

---

## Net vs gross of fees

- **SPIVA is net of fees** (excluding loads) against a costless index [4] — the
  index is not directly investable, which slightly overstates the active failure
  rate. Morningstar's barometer removes this objection by benchmarking against real
  passive funds net of their (tiny) fees — and the conclusion barely moves (21%
  10-year success vs SPIVA-implied ~16% at 10 years) [4][6].
- **Gross of fees, managers look meaningfully better.** Berk & van Binsbergen's
  +$3.2M/yr average value added is a *gross* measure [10]; Fama & French find
  genuine skill in the right tail *gross* of fees that evaporates *net* [9][24].
  The industry rule of thumb: the average active US equity fund charges roughly
  0.6–1.0%/yr, so a "typical" manager needs ~0.6–1.0% of gross alpha just to tie
  the index net.
- **Fee level is the strongest predictor of success** found in any of these
  datasets: cheapest-quintile funds beat their passive peers roughly twice as often
  as the priciest quintile (31% vs 17% over 10 years to 2025) [4].
- **Asset-weighting** (what investors actually experienced) softens but doesn't
  reverse the verdict: 9.48% vs 8.77% annualized over 20 years, still 1.25 pp/yr
  behind the S&P 500's 10.73% [4].

---

## Implications for Room benchmarking

- **The bar by horizon (net-of-fees human base rates, large-cap):** beating the
  S&P 500 over 1 year puts the Room ahead of only ~65% of pros — a coin-flip-ish
  achievement. The credible bars are longer: top **~24%** at 5 years, top **~16%**
  at 10 years, top **~10%** at 15 years, top **~8%** at 20 years [1][4]. Any
  claimed "beats the pros" headline must specify the horizon.
- **Gross vs net framing matters for a simulation:** the Room has no expense ratio,
  no fund-flow constraints, and no career risk. Compared to SPIVA's net-of-fee
  funds, the Room effectively competes *gross*. Fama-French and Berk-van Binsbergen
  both show gross skill is more common than net skill [9][10] — so "beat the index
  before fees" is a **softer** bar than the SPIVA headline implies. A fair benchmark
  should either deduct a notional ~0.75% annual fee drag from Room performance or
  compare against funds' gross returns.
- **Persistence is the real test:** one good year proves nothing — even top-half
  funds stay top-half for five straight years only 6.25% of the time *by chance*,
  and actual pros do worse (2.4%) [4]. Room evaluation should require multi-period
  consistency (e.g., rolling 3-year windows) and should be judged against *chance*
  persistence rates, not just against the index once.
- **Survivorship discipline:** 63% of domestic equity funds died within 20 years
  [4]. If the Room's track record is reset or restarted after failures, the
  benchmark comparison silently inherits survivorship bias. Keep a continuous,
  never-reset track record.
- **Team structure sets expectations:** the human team literature says teams
  produce *less extreme* outcomes — lower variance, slightly lower mean alpha
  (~48 bps drag in Chen et al.), better security selection, worse timing [30][32][34].
  A 12-agent Room should be expected to show the same signature; benchmark it on
  risk-adjusted consistency (Sharpe, max drawdown) as well as raw alpha.
- **The behavior gap is the Room's biggest structural edge:** Dalbar shows human
  *investors* forfeit 0.7–8.5 pp/yr to timing behavior (848 bps in 2024) [7][8].
  A rule-following agent team doesn't panic-sell. Relative to the *realized returns
  of human fund investors* — arguably the truest "human benchmark" — the Room's
  hurdle is far lower than beating the S&P 500.

---

## Sources

1. Ritholtz, Barry. "The Data on Active Large Cap Underperformance." The Big
   Picture, May 29, 2025. Reproduces SPIVA US Year-End 2024 Report 1 table (All
   Large-Cap vs S&P 500: 65.24 / 84.96 / 76.26 / 84.34 / 89.50 at 1/3/5/10/15 yrs).
   https://ritholtz.com/2025/05/the-data-on-active-large-cap-underperformance/
2. Ganti, Anu R., Tim Edwards, Nick Didio. "SPIVA® U.S. Year-End 2024." S&P Dow
   Jones Indices, March 2025. (65% large-cap underperformance; no category with
   majority outperformance at 15 years.)
   https://www.spglobal.com/spdji/en/spiva/article/spiva-us-year-end-2024/
3. Ganti, Anu R., Davide Di Gioia, Nick Didio, Liam Flaherty. "SPIVA® U.S.
   Scorecard Year-End 2025." S&P Dow Jones Indices, 2026. (79% large-cap
   underperformance in 2025, fourth-worst year in 25 years.)
   https://www.spglobal.com/spdji/en/documents/spiva/spiva-us-year-end-2025.pdf
4. "What 20 Years of SPIVA Data Show About Active Funds." LedgerTouch, Aug 2, 2026.
   Independent audit citing SPIVA US YE2024 (20-yr: 91.99% large-cap, 94.11% all
   domestic), Mid-Year 2025 (20-yr 91.03%; survivorship 37.29%; 8.77/9.48/10.73
   annualized), Persistence Scorecard YE2024, and Morningstar Barometer YE2025
   (21% / 10% large-cap 10-yr success; 31% vs 17% fee quintiles).
   https://ledgertouch.com/blog/planning-and-costs/spiva-scorecard-active-fund-underperformance
5. (See [4] and [6] — Morningstar 10-year figures.)
6. "Active Funds Trailed Passive Peers in 2024." Morningstar, 2025 (year-end 2024
   Active/Passive Barometer: 42% 1-yr success; <25% 10-yr; 28% vs 17% fee
   quintiles; 16 of 20 asset-weighted; methodology change to asset-weighted
   passive composite).
   https://www.morningstar.com/funds/active-funds-trailed-passive-peers-2024
7. "Investors Missed the Best of 2024's Market Gains, Latest DALBAR Investor
   Behavior Report Finds." DALBAR press release, March 31, 2025. (16.54% vs
   25.02%; 848 bps gap, second-largest of decade.)
   https://www.dalbar.com/press-release/investors-missed-the-best-of-2024s-market-gains-latest-dalbar-investor-behavior-report-finds/
8. "DALBAR's 2026 QAIB Report Shows Narrower Investor Gap Amid a Complex and
   Volatile Market Year." DALBAR / PR Newswire, April 2026. (17.16% vs 17.88%;
   72 bps gap; third-smallest since 1985; 2024 gap restated as 848 bps.)
   https://www.prnewswire.com/news-releases/dalbars-2026-qaib-report-shows-narrower-investor-gap-amid-a-complex-and-volatile-market-year-302745998.html
9. "Should Investors Avoid Active Funds?" Morningstar, Dec 12, 2024. (Fama-French
   2010: only 98th–99th percentile managers show significant skill net of fees,
   fewer than chance; persistence below random.)
   https://www.morningstar.com/funds/should-investors-avoid-active-funds
10. Berk, Jonathan B., and Jules H. van Binsbergen. "Measuring Skill in the Mutual
    Fund Industry." Journal of Financial Economics 118(1), October 2015, pp. 1–20.
    DOI 10.1016/j.jfineco.2015.05.002. (Average value added ~$3.2M/yr; skill
    persists up to 10 years.) Working-paper copy:
    https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2014/04/17.14.VanBinsbergen.pdf
11. "U.S. Persistence Scorecard Year-End 2024." S&P Dow Jones Indices, 2025.
    https://www.spglobal.com/spdji/en/documents/spiva/persistence-scorecard-year-end-2024.pdf
12. Prokop, Brian. "Investment Management Process." Link Plan Management
    whitepaper, May 2025. (SPIVA YE2024 figures: 85.0 / 76.3 / 84.3 / 89.5;
    persistence: 0.39% of 508 top-quartile funds stayed top-quartile over 2 years
    to Dec 2023; zero over five years.)
    https://link-plans.com/wp-content/uploads/2025/05/Whitepaper-2025-LINK-Investment-Management-Process-Update-May-2025.pdf
13. "Does Market Timing Work? What the Evidence Actually Shows." Attending
    Financial, July 2026. (Confirms 65% 1-yr and 89.5% 15-yr YE2024; Persistence
    YE2025: <5% top-quartile over following 5 years.)
    https://attendingfinancial.com/learn/market-timing-evidence
14. "Vectors" newsletter citing SPIVA US YE2024 (79% of domestic funds
    underperformed S&P Composite 1500 in 2024; 15th consecutive majority-failure
    year for large-cap). On Course Financial Planning, May 2025.
    https://www.oncoursefp.com/files/vectors_may_25_final.pdf
15. Ganti, Anu R., Nick Didio. "SPIVA® U.S. Mid-Year 2025." S&P Dow Jones Indices,
    Sept 4, 2025. (H1 2025: 54% large-cap, 25% mid-cap, 22% small-cap
    underperformed.)
    https://www.spglobal.com/spdji/en/spiva/article/spiva-us/
16. "Active Bond Funds Outperformed Passive Peers By a Mile Over the Past Year."
    WealthManagement.com, Sept 11, 2024. (Morningstar mid-2024 barometer: 51% 1-yr,
    29% 10-yr success through June 2024.)
    https://www.wealthmanagement.com/etfs/active-bond-funds-outperformed-passive-peers-mile-past-year
17. "Better Conditions Did Not Yield Better Results for Active Managers in 2025."
    Morningstar, Feb 18, 2026. (38% of 3,140 active funds survived and beat
    average passive peer in 2025.)
    https://www.morningstar.com/funds/better-conditions-did-not-yield-better-results-active-managers-2025
18. "Measuring the Performance of Active Funds Against Their Passive Peers."
    Morningstar, June 25, 2025. (2024 1-yr success: large-cap 37%, mid-cap 37%,
    small-cap 43%.)
    https://www.morningstar.com/funds/measuring-performance-active-funds-against-their-passive-peers
19. PR Newswire version of DALBAR QAIB 2025 release, March 31, 2025. (Prints S&P
    500 2024 return as 25.05% — 3 bp discrepancy vs Dalbar's own 25.02%.)
    https://www.prnewswire.com/news-releases/investors-missed-the-best-of-2024s-market-gains-latest-dalbar-investor-behavior-report-finds-302416023.html
20. "DALBAR Releases 30th Annual QAIB Report." DALBAR, April 11, 2024. (2023:
    average equity investor earned 5.5 pp less than the S&P 500.)
    https://www.dalbar.com/PressReleases/doc/QAIB2024_PR.pdf
21. Oaktree Investment Advisors newsletter, July 2024, citing QAIB 2023 (30-yr:
    investor 3.6% vs S&P 500 10.0% annualized).
    https://oaktreeia.com/wp-content/uploads/2024/08/07.24_OaktreeNews.pdf
22. "Why the average investor massively underperforms." One Day Investor blog,
    July 2026, citing DALBAR QAIB (30 yrs ending 2022: investor 6.81% vs S&P 500
    9.65% — a 2.84 pp/yr gap; also cites ~93% 20-yr SPIVA failure rate).
    https://blog.odinvestor.net/why-trading-is-a-losing-game
23. Fama, Eugene F., and Kenneth R. French. "Luck versus Skill in the
    Cross-Section of Mutual Fund Returns." Journal of Finance 65(5), October 2010,
    pp. 1915–1947. (Sample/period detail per Morningstar India's summary:
    https://www.morningstar.in/posts/24087/past-performance-skilled-managers.aspx)
24. Lima, E. (thesis survey of Fama-French 2010 results), Lume/UFRGS. (16% of
    funds true net alpha > +1.25%/yr; 2.3% > +2.5%/yr.)
    https://lume.ufrgs.br/bitstream/handle/10183/205628/001111752.pdf?sequence=1
25. Jones, R. / Touchstone. "Challenging the Conventional Wisdom on Active
    Management: A Review of the Past 20 Years of Academic Literature." (Berk-van
    Binsbergen: $3.2M/yr average value added; +36 bps net alpha vs comparable
    index funds; net alpha set by investor competition.)
    https://www.westernsouthern.com/-/media/files/touchstone/active-share/ssrn-id3247356.pdf
26. "The value of information flows in the stock market." Springer, 2026. (Cites
    Berk-van Binsbergen: ~$3.2M/fund/yr, ~$19B/yr industry aggregate.)
    https://link.springer.com/article/10.1007/s10436-026-00479-y
27. GLOBE academic newsletter abstract of Berk & van Binsbergen (2015), JFE.
    https://academicnewsletter.sufe.edu.cn/info/356521
28. "Past performance is no guarantee of future results, data confirms." TKer,
    May 7, 2026, covering S&P US Persistence Scorecard YE2025. (334 top-half
    large-cap funds of 2021: 58.7% → 6.9% → 4.5% over 1/3/5 subsequent years;
    164 top-quartile: 20.1% retained after 1 year.)
    https://www.tker.co/p/spiva-persistence-2025-past-performance-no-guarantee
29. "To Group or Not to Group? Evidence from Mutual Fund Databases." ResearchGate,
    2017/2024. (Patel & Sarkissian 2017: >70% of US equity funds team-managed;
    Bär et al. 2011 and Chen et al. 2004 find teams underperform on alpha
    measures.)
    https://www.researchgate.net/publication/320746645_To_Group_or_Not_to_Group_Evidence_from_Mutual_Fund_Databases
30. Bär, Michaela, Alexander Kempf, and Stefan Ruenzi. "Is a Team Different from
    the Sum of Its Parts? Evidence from Mutual Fund Managers." Review of Finance
    15(2), 2011, pp. 359–396. (Teams: less extreme styles, lower risk, lower
    industry concentration, less extreme outcomes; diversification-of-opinions
    supported over group-shift.) Summary:
    https://hub.edubirdie.com/examples/mutual-fund-flow-performance-relationship-managerial-structure-and-manager-turnover-literature-review/
31. "Managerial Incentives in the Mutual Fund Industry" (survey chapter), PKU-HSBC /
    Oxford. (Bär-Kempf-Ruenzi and Dass-Nanda-Wang summaries.)
    https://www.phbs.pku.edu.cn/__local/A/E2/3C/6D8573706DDC4A2388507E25E05_72F2D833_6FE72.pdf
32. Diamond, Wang (ACFR working paper), citing Chen et al. (2004): team-managed
    funds underperform single-managed by ~48 bps/yr after controlling for size.
    https://acfr.aut.ac.nz/__data/assets/pdf_file/0015/57021/Diamond-Wang-Auckland-Uni.pdf
33. "Management team structure and mutual fund performance." Journal of Economics
    and Business (ScienceDirect). (Prather & Middleton 2002 and Karagiannidis 2010
    find no significant team-vs-solo performance difference; Chen et al. 2004 and
    Baer et al. 2005 find weak negative team effects.)
    https://www.sciencedirect.com/science/article/pii/S1042443109000481
34. Dass, Nishant, Vikram Nanda, and Qinghai Wang (2013), summarized in [31]:
    solo managers show cross-asset market timing, teams do not; teams show
    superior security selection.
