# 05 — Process quality: why a structured team wins, and how to score one

`03` produced the finding that most threatens the product: investment clubs
returned **14.1%** against the market's 17.9%, **60% underperformed**, and the
average club did worse than the average lone individual. Adding people made
outcomes worse.

`04` produced the finding that most helps: the CFA Institute, grading exactly this
task, allocates **0 of 100 points to being right** and 100 to process.

This file reconciles them. The reconciliation is the Room's actual thesis, and it
is empirically supported rather than aspirational.

---

## 1. Why unstructured teams lose

Three well-replicated mechanisms, each of which the investment-club result exhibits:

- **Shared-information bias** (Stasser & Titus). Groups discuss what members
  already share and systematically fail to surface information held by only one
  member. The distinctive evidence — the entire reason to convene a team — is the
  least likely thing to reach the table.
- **Conformity and premature consensus.** Groups converge fast; the dissent that
  would have caught the error is socially expensive to voice.
- **Manufactured activity.** A club that meets monthly needs something to decide.
  Per `03`, trading volume is the documented cause of retail underperformance, and
  meeting cadence manufactures volume.

## 2. Why *structured* teams win

**Schweiger, Sandberg & Ragan (1986), *Group Approaches for Improving Strategic
Decision Making*** (Academy of Management Journal) — a longitudinal study of
fast-advancing middle managers doing strategic planning, comparing three protocols
**[P-abstract]**:

| Protocol | Decision quality | Assumption quality | Member satisfaction |
|---|---|---|---|
| **Dialectical inquiry** — two opposed full positions, argued | **higher** | **highest** | lower |
| **Devil's advocacy** — one assigned attacker | **higher** | higher | lower |
| **Consensus** — converge on agreement | baseline | baseline | **highest** |

Both structured-conflict protocols produced significantly higher-quality decisions
and surfaced significantly better assumptions than consensus. Dialectical inquiry
beat devil's advocacy specifically on *assumption* quality. And in both cases
members reported **more re-evaluation of their own positions but lower acceptance
of the group's decision, and less desire to keep working together.**

That last column is the crux, and it explains the club result. Consensus feels
best and performs worst. Left to themselves, human teams optimise the thing they
can feel — agreement — and pay for it in decision quality. **A voluntary human club
cannot sustain dialectical inquiry, because the protocol makes members unhappy.**

**This is the Room's structural advantage, stated precisely:** it can run the
protocol that works and is indifferent to the protocol's cost. Agents do not
resent being assigned the bear case. There is no meeting to survive. The Room can
hold dialectical inquiry indefinitely at zero social cost — which is the one thing
the human comparator in `03` demonstrably could not do.

The Room's architecture is a literal implementation:

| Room stage | Protocol element |
|---|---|
| `bull_researcher` vs `bear_researcher`, in parallel | dialectical inquiry — two opposed full positions |
| `aggressive` / `conservative` / `neutral` risk debators | multi-lens devil's advocacy |
| `portfolio_manager`, structurally separate + deterministic compliance check | the synthesis authority that cannot be argued out of the mandate |

## 3. Calibration: the Good Judgment Project apparatus

The forecasting-tournament literature supplies the missing measurement instrument.

Key results **[S]** — the primary Good Judgment PDF 403s to automated fetching, so
these are verified across multiple independent secondary reports and should be
re-verified against the primary before external use:

- Superforecasters achieved Brier scores roughly **20–30% lower than the median
  forecaster**, and ~40% lower than naive baselines.
- **Teams outperformed individuals** working alone — sharing information, debating,
  and refining beat solo forecasting.
- **Aggregation helped ordinary forecasters most** and top performers least: the
  crowd-combination algorithm produced its largest gains on unfiltered forecasters,
  while superforecasters were already good enough that aggregation added little.
- Elite teams realised Brier reductions of roughly **0.05–0.10** versus the
  unfiltered crowd.

Two things transfer directly:

1. **Brier score is the right M3 instrument for confidence.** It is proper (it
   cannot be gamed by hedging), it works on single binary forecasts, and it
   decomposes into *calibration* (are your 60%s right 60% of the time?) and
   *resolution* (do you discriminate at all?). Per `03`, the retail comparator is
   systematically overconfident, so calibration is a lane where a measurable edge
   is plausible.
2. **The aggregation result predicts what the Room is for.** Aggregation helps
   *ordinary* forecasters most. AMI Trade's users are ordinary forecasters. The
   expected benefit of the Room is therefore largest exactly where our users sit —
   and would be smallest for an expert, which is consistent with the product being
   an education tool rather than a professional one.

## 4. What Asquith, Mikhail & Au add

Their content-coding of sell-side reports found that the **justification** content —
the specific evidence and the earnings model — carries information beyond the
headline rating. What makes a research product informative is not the verdict but
the evidenced reasoning under it.

Combined with Loh & Stulz (`02`: only 12% of recommendation changes are
influential, and influence concentrates in *off-consensus* calls carrying a
*specific numeric forecast*), this gives two process properties that are known to
correlate with informativeness and are measurable on a transcript **today**:

- **grounded specificity** — are the numbers real and sourced?
- **off-consensus willingness** — does the team ever depart from the crowd?

## 5. What we already measure

CR143 (`docs/forward_planning/CR143_agent_prompt_audit/PHASE3B_quality.md`), n = 18
convenes / 198 turns, epoch 2026-08-07:

| Metric | Measured | Reads as |
|---|---|---|
| Role identifiability | **87.9%** (9.7× lift over baseline) | agents are playing distinct roles, not one voice |
| Number provenance | **92.6% grounded**, 4.3% novel | grounded specificity — the Asquith property |
| Stance entropy | **1.48 / 1.58 bits** | near-maximal disagreement |
| Unanimous convenes | **0 of 18** | **the anti-club metric** |
| M4 (as defined in CR143) | unmeasurable → DEF235 | open |

**Stance entropy and the zero-unanimity count are the most important numbers in the
repository right now.** They are the direct test of whether we built a dialectical
team or an expensive investment club — the distinction that separates
Schweiger et al.'s winning protocol from Barber & Odean's losing one. On that test
the Room currently measures on the right side, at n = 18, with no forward prices
required.

Caveat, stated plainly: 18 convenes is a small corpus, the numbers are epoch-bound,
and stance entropy measures *whether* agents disagree, not whether the disagreement
is *substantive*. An agent that reliably contradicts on trivia scores identically
to one that raises a real objection. That is the gap the rubric below closes.

## 6. Proposed rubric — the AMI Room Report Card

Adapted from the CFA Institute Research Challenge Written Report Evaluation Form
(`04`), reweighted for the Room's roster, ESG dropped (no counterpart agent), and
two dimensions added that the CFA form has no need for because human analysts don't
hallucinate numbers or silently drop agents.

| Dimension | Pts | Scored from | CFA origin |
|---|---|---|---|
| Business & industry grounding | 10 | analyst turns | Business Desc. 5 + Industry 10 |
| Financial analysis | 20 | `fundamentals_analyst` | Financial Analysis 20 |
| Valuation & levels | 20 | trader/PM `entry`/`target`/`stop` | Valuation 20 |
| Investment risks | 15 | three risk debators | Investment Risks 15 |
| **Dialectical integrity** | **15** | bull/bear + stance entropy | *new* |
| **Number provenance** | **10** | grounded vs novel numbers | *new* |
| **Disclosure honesty** | **10** | `opinions_not_included`, `level_provenance`, violations | *new* |
| **Total** | **100** | | |

The three new dimensions are where the Room can be *better than a human team*, not
merely comparable:

- **Dialectical integrity** operationalises Schweiger et al. A human team cannot
  sustain this; the Room structurally must.
- **Number provenance** operationalises Asquith et al. and catches the failure mode
  humans don't have. CR143 measures it already.
- **Disclosure honesty** has no human analogue at all. `opinions_not_included`
  (CR098) and `level_provenance` (CR106) mean the Room can state which of its own
  inputs were missing and which of its own numbers it invented. No sell-side report
  discloses "we minted this target from a constant." That is a genuine structural
  advantage and it should be scored.

Scoring is per-convene from the transcript, needs no market data, and is available
immediately after a run.

---

## What this file establishes

1. **The club result is survivable, and we know why.** Unstructured consensus
   loses; structured dissent wins; the Room is structurally incapable of the
   consensus failure mode and structurally indifferent to the social cost that
   stops humans from running the winning protocol.
2. **Process is the primary instrument, not the consolation prize.** The CFA
   Institute's own grading says so.
3. **The evidence we already have points the right way** — 0/18 unanimous, 1.48
   bits of stance entropy, 92.6% grounded numbers — and it cost no forward prices.
4. **Brier score is the M3 instrument** and calibration is a plausibly winnable
   lane against a demonstrably overconfident comparator.
5. **Three rubric dimensions have no human counterpart.** That is where "better
   than a human team" is not marketing.

---

Next: [`06_expectation_bands.md`](06_expectation_bands.md) — the numbers.
