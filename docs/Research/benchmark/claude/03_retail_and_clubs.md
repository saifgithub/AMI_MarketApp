# 03 — Comparator C3: Retail investors and investment clubs

**The load-bearing comparator.** Not because the data is best — C1 and C2 have
better data — but because this is who AMI Trade's users actually are, and it is the
only comparator the Room could plausibly beat by a margin large enough to measure.

It also contains the single most uncomfortable finding in this entire study, and
the one that most directly interrogates the product's premise.

---

## M1 · Hit rate vs index

**Barber & Odean (2000), *Trading Is Hazardous to Your Wealth*** — 66,465
households at a large discount broker, 1991–1996 **[P-abstract]**:

| Group | Annual return |
|---|---|
| Market index | **17.9%** |
| Average household | **16.4%** |
| **Most active quintile** | **11.4%** |

The average household lagged by ~1.5 points; the most active traders lagged by
**6.5 points a year**. Average annual portfolio turnover was 75%. Barber and Odean
trace the bulk of the shortfall to transaction costs, and the *cause* of the
transaction costs to overconfidence — a behavioural finding, not a skill finding.

The critical decomposition, confirmed directly in the club paper's Figure 1
(M4 below): **individual investors' gross return was 18.7% against the index
fund's 18.0%.** Their selection was fine — better than the index. **The losses came
entirely from trading, not from picking.**

**Barber, Lee, Liu & Odean (2009), *Just How Much Do Individual Investors Lose by
Trading?*** — the complete trading history of every investor in Taiwan
**[P-abstract]**:

| | |
|---|---|
| Individual investors, aggregate annual penalty | **−3.8 percentage points** |
| Institutions, aggregate annual boost | **+1.5 percentage points** |
| Scale of individual losses | **2.2% of Taiwan's GDP** |

Losses trace almost entirely to **aggressive** (marketable) orders; individuals'
passive limit orders were profitable at short horizons. The day-trading subset is
starker still: **~1%** of day traders reliably earned positive abnormal returns net
of fees; about 3% were net-positive at all.

> **Expectation this sets.** This is the bar the Room actually has to clear, and it
> is a *low* bar — but note **where** the gap is. Retail investors don't lose
> because they pick badly; they lose because they trade too much, at bad prices,
> on impulse. **A Room that improves picking by zero and reduces impulse trading by
> a lot would beat this comparator outright.** That is a plausible, measurable, and
> honest product claim, and it does not require the Room to have any stock-picking
> edge whatsoever.

## M2 · Risk-adjusted excess return

Households didn't just underperform — they took more risk doing it. Barber & Odean
find the average household tilted toward **high-beta, small, value** stocks. So the
raw 1.5-point shortfall understates the risk-adjusted one: they were paid less for
carrying more.

**Barber & Odean (2001), *Boys Will Be Boys*** identifies the mechanism as
overconfidence, gendered in expression (men traded 45% more than women and
underperformed correspondingly) but general in kind.

**Barber, Huang, Odean & Schwarz (2022)** extend it to the modern app era:
attention-induced herding among Robinhood users produced concentrated
crowd-buying episodes followed by negative abnormal returns. Same failure mode,
faster interface.

> **Relevant to us with some force.** AMI Trade *is* a modern app interface. The
> attention-herding literature is a warning about our own surface area: if the app
> surfaces "what everyone is convening" prominently, we reproduce the documented
> failure mode. Worth carrying into any social/leaderboard feature design.

## M3 · Forecast accuracy

Retail investors don't publish targets, so there is no direct target-accuracy
series. What exists instead is a rich literature on **systematic errors in
belief-updating**, which is arguably more useful for an education product:

- **Odean (1998), *Are Investors Reluctant to Realize Their Losses?*** — the
  disposition effect. Investors sell winners and hold losers, at direct cost to
  returns.
- **Overconfidence in calibration** — the reliable finding that subjective
  confidence intervals are far too narrow. This is a *forecast-accuracy* failure in
  the strict sense: not the point estimate but the uncertainty around it.

> **Expectation this sets.** Against C3, the Room's measurable M3 edge is
> **calibration**, not point accuracy. A Room that says "60% confident" and is right
> 60% of the time is doing something the comparator population demonstrably cannot
> do. Brier score is the instrument (see `05`).

## M4 · Process quality — **the finding that interrogates our premise**

**Barber & Odean, *Too Many Cooks Spoil the Profits: The Performance of Investment
Clubs*** (Financial Analysts Journal) **[P — read direct]** — 166 investment clubs
at the same discount broker, **February 1991 – January 1997**. Figure 1,
annualised geometric mean:

| Group | Gross | Net |
|---|---|---|
| Index fund (S&P 500) | 18.0% | **17.8%** |
| Average *individual* investor | **18.7%** | **16.4%** |
| **Average investment club** | 17.0% | **14.1%** |

*(A value-weighted NYSE/Amex/Nasdaq index returned **17.9%** over the same period —
that is the "market 17.9%" figure used throughout this study.)*

**60% of clubs underperformed the index**, and the club average came in *below* the
individual average. Clubs turned over 65% of their portfolio annually.

The gross/net split is where the real story is, and it points two different ways:

- **Individual investors' gross selection *beat* the index fund** — 18.7% against
  18.0%. They picked well. They lost all of it, and then some, to costs.
- **Clubs, unlike individuals, genuinely picked badly.** Their own-benchmark gross
  abnormal return is **−0.106 pps/month, significant at the 5% level** (Table 2A) —
  Barber & Odean's reading is that "the stocks clubs choose to buy perform worse
  than the stocks they choose to sell." Net, clubs underperformed their own
  beginning-of-year portfolio by **3.5 pps/year**, with Jensen's alpha at −4.8 pps
  and the Fama-French intercept at −4.4 pps.

**So the group didn't just trade more than the lone individual — it also selected
worse.** Adding people degraded both halves of the job.

Read that again in product terms. **A team of amateurs did worse than a lone
amateur.** The very structure AMI Trade sells — "you now have a team of twelve
analysts" — is a structure that, in the only large-sample study of amateur
investment teams, made outcomes *worse*.

### Why, and why it is survivable

The mechanism is well characterised in the group decision-making literature, and it
is not "teams are bad." It is that **unstructured** teams amplify the individual
failure modes rather than cancelling them:

- **Shared-information bias** (Stasser & Titus): groups spend discussion time on
  what members already hold in common and systematically underweight information
  held by only one member. The distinctive evidence — the thing worth convening for
   — is the thing least likely to be raised.
- **Social conformity**: clubs converge on consensus, which suppresses the dissent
  that would have caught the error.
- **Turnover amplification**: clubs traded more, not less. Meeting monthly and
  needing something to decide manufactures activity — and per M1, activity is the
  documented cause of retail losses.

> **This is the most important finding in the document for product strategy**, and
> it cuts both ways.
>
> **The threat:** "twelve analysts" is not automatically better than one. If the
> Room's twelve agents converge into agreement, we have built an expensive
> investment club and should expect club results — worse than the individual.
>
> **The defence, and it is a real one:** the club failure is a failure of
> *unstructured* consensus. The Room is not unstructured. It runs adversarial roles
> by construction — bull vs bear researchers, three risk debators with opposed
> mandates, a structurally separate PM with a deterministic compliance check.
> That architecture is a direct implementation of the intervention the group
> decision-making literature says fixes exactly this (`05`).
>
> **The consequence for measurement:** *stance diversity is not a nice-to-have
> process metric — it is the test of whether we built a Room or a club.* CR143
> already measures it: stance entropy **1.48 of a possible 1.58 bits**, and **zero
> unanimous convenes** across 18 runs. On the one metric that separates a
> functioning research team from a losing investment club, the Room currently
> measures on the right side. That is the strongest evidence in the repo today, and
> it required no forward prices to obtain.

---

## What C3 tells us about expectations for the Room

1. **This is the comparator to state publicly, and the only one we can beat by a
   measurable margin.** Retail loses by 1.5–6.5 points a year; day traders lose
   ~99% of the time. There is real room above that floor.
2. **The gap is behavioural, not analytical.** Retail's stock selection is roughly
   *better than the index fund* (18.7% vs 18.0% gross); the losses come
   entirely from overtrading, bad order placement, and the
   disposition effect. **The Room's plausible edge is in suppressing action, not in
   improving picks** — and note that a PASS-heavy Room (CR035: 37% APPROVE vs
   Street 63%) is *already* the behaviour this literature rewards.
3. **"You have a team" is not a benefit claim — it is a risk.** Barber & Odean's
   club study says teams underperform individuals. Our claim must be narrower and
   truer: *you have a team that is structurally required to disagree.*
4. **Calibration is the reachable M3 edge**, because the comparator population is
   systematically overconfident and we can measure calibration directly.
5. **Don't build the attention-herding surface.** The Robinhood literature
   documents what happens when an app makes crowd behaviour salient.

---

Next: [`04_student_and_cfa_teams.md`](04_student_and_cfa_teams.md) — the comparator
with no outcome data, and why that turns out to be the interesting part.
