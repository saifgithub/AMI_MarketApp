# 01 — Comparator C1: Active fund managers

**The professional ceiling.** Teams with Bloomberg terminals, management access,
PhD quants, and a direct financial incentive to be right. If a structured human
team can beat the market, this is where it happens.

It mostly doesn't.

---

## M1 · Hit rate vs index

SPIVA (S&P Indices Versus Active) is the reference series — survivorship-corrected,
25 years long, published by the index provider itself.

### The headline everyone quotes

Share of active US large-cap equity funds underperforming the S&P 500:

| Horizon | Underperformed | As of |
|---|---|---|
| 10 years | **84.3%** | year-end 2024 **[S]** |
| 15 years | **89.5%** | year-end 2024 **[S]** |
| 20 years | **~92%** (all domestic funds) | year-end 2025 **[S]** |

Roughly **1 in 10** professional large-cap teams beats a passive index over 15
years. Over 20, closer to 1 in 12.

### The part nobody quotes, which matters more

The annual series is wildly unstable. SPIVA Exhibit 1 **[P]**, share of large-cap
funds underperforming, each year:

| | | | | | |
|---|---|---|---|---|---|
| 2001 **65** | 2002 **68** | 2003 **75** | 2004 **69** | 2005 **49** | 2006 **68** |
| 2007 **45** | 2008 **56** | 2009 **48** | 2010 **66** | 2011 **82** | 2012 **63** |
| 2013 **55** | 2014 **87** | 2015 **65** | 2016 **66** | 2017 **63** | 2018 **65** |
| 2019 **71** | 2020 **60** | 2021 **85** | 2022 **51** | 2023 **60** | 2024 **65** |
| H1 2025 **54** | | | | | |

In 2007 and 2009, **most** active large-cap managers beat the index. In 2014, 87%
failed. Same profession, same skills, nine years apart.

And it is not uniform across the market. In H1 2025 only **25%** of mid-cap and
**22%** of small-cap funds underperformed — i.e. three-quarters of them *won* — and
2024's 30% small-cap underperformance rate was the lowest in more than two decades
of SPIVA **[P]**. Difficulty is a property of the segment and the regime, not just
the manager.

> **Expectation this sets.** A one-year result — for a fund or for the Room —
> carries almost no information about skill. The 10-and-15-year numbers are damning
> precisely because they are long. We will not have a 10-year Room track record for
> a decade, so **M1 will not settle anything for us in any timeframe that matters
> to this product.**

### The base rate underneath it

The reason the long-horizon numbers are so bad is arithmetic, not incompetence.
From SPIVA Exhibit 5 **[P]**, the share of S&P 500 constituents that beat the index
itself: **62% in Q1 2025, 29% in Q2 2025**. Combined with Bessembinder's lifetime
figures (57.4% of stocks below T-bills; median lifetime return −3.7%; 4.3% of
stocks producing all net wealth creation **[P]**), the picture is that a
concentrated portfolio's *median* outcome sits below the index even at zero skill
differential. Active managers are fighting skew, and fees, before they fight each
other.

## M2 · Risk-adjusted excess return

The honest professional measure, and the one where the evidence is strongest.

**Fama & French (2010), *Luck versus Skill*** **[P-abstract]** bootstrap the whole
cross-section of US mutual fund returns, preserving the correlation structure. Two
findings:

- On **net** returns, few funds produce benchmark-adjusted expected returns
  sufficient to cover their costs. Aggregate net alpha is negative.
- On **gross** returns — adding expense ratios back — there *is* evidence of real
  non-zero α in the extreme tails, both superior and inferior.

The synthesis is the important bit: **skill exists, and it is almost exactly
consumed by cost.** Fama and French's own summary is that a portfolio of low-cost
index funds performs about as well as a portfolio of the top ~3% of active funds,
and better than everything else.

**Berk & Green (2004)** supply the mechanism: skill is real, but flows chase it,
assets grow, and the manager's edge is diluted until net alpha to the investor
approaches zero. Skill accrues to the *manager*, not the *investor*.

**Carhart (1997)** removes most of what looks like persistent skill by adding a
momentum factor — apparent hot hands were largely factor exposure, not selection.

> **Expectation this sets.** M2 is where the profession's real answer lives, and
> **the Room cannot be scored on it.** M2 requires a portfolio, a fee load, a risk
> model and a multi-year series. The Room produces per-ticker verdicts. Any attempt
> to compute a "Room Sharpe" would be manufacturing a portfolio that the Room never
> constructed and then attributing its properties to the Room. See `07` for what we
> compute instead (per-verdict excess return distributions, which are honest but
> are *not* risk-adjusted alpha).

## M3 · Forecast accuracy

Funds are the wrong comparator here. They don't publish per-name forecasts,
targets, or confidence levels — they publish holdings, quarterly and lagged. There
is no per-forecast accuracy series for this population.

The one transferable result is **persistence**, which is forecast accuracy of a
sort — "will last year's winners win again?" S&P's Persistence Scorecard finds it
close to absent: among top-quartile domestic equity funds as of December 2020,
**not a single one** remained top-quartile over the next four years; earlier
editions found **zero** large-, mid- or multi-cap funds holding top-quartile status
across five years **[S]**.

> ⚠️ **Corrected 2026-08-10 — this passage previously claimed the result was "worse
> than chance would predict." That was a statistical error.** Random reshuffling
> leaves 0.25⁴ ≈ **0.39%** of funds top-quartile four years running — about **one
> fund in a cohort of 250**. Observing zero is therefore *consistent with* chance,
> not below it. P(zero survivors) under pure chance is **0.38 at N=250** and **0.14
> at N=500**; a cohort would need to exceed **766** funds before zero was surprising
> at p<.05. The cohort size is not stated in the source, so the comparison cannot be
> made at all.
>
> **The defensible claim** is the weaker and more useful one: *past quartile rank
> carries no detectable information about future quartile rank.* Do not say
> "worse than chance."

### The strongest counter-argument — and it is serious

**Berk & van Binsbergen (2015), *Measuring Skill in the Mutual Fund Industry***,
JFE 118(1) **[P — abstract + intro read direct]**, argue the whole net-alpha framing
measures the wrong quantity. Per Berk-Green, net alpha is set in equilibrium by
*competition between investors* chasing a good manager, not by the manager's
ability — so net alpha near zero is what you expect **whether or not skill exists**.

Measuring instead the dollars a fund extracts from markets, they find the average
fund adds about **$3.2M/year**, and that cross-sectional differences in value added
**persist for as long as 10 years**. Their words: they "find it hard to reconcile
[the] findings with anything other than the existence of money management skill."

**This does not contradict SPIVA — it answers a different question.** SPIVA asks
*did the investor beat the index after fees* (overwhelmingly no). Berk & van
Binsbergen ask *did the manager extract value from the market* (often yes,
persistently). Held together they say something sharper than either alone:
**skill is real and is captured by the manager and the fund rather than delivered
to the client** — which is exactly the Fama-French/Berk-Green synthesis two
paragraphs above, now with a persistence result attached.

**Consequence for this study:** the persistence finding above is narrower than it
first reads. *Net-return quartile rank* does not persist. *Dollar value added*, on
this evidence, does. Any claim we make about "persistence is absent in this
population" must specify which measure.

> **Expectation this sets.** *"Was good last period"* has close to zero predictive
> value for *"will be good next period"* in this population. Applied to us: a good
> Room quarter is not evidence of a good Room. Report rolling windows, never a
> best-window highlight.

## M4 · Process quality

Not measured for this population in any public series. Funds disclose holdings, not
reasoning. There is no rubric-scored corpus of fund investment committee
transcripts.

This is itself worth noting: **the most-measured population in finance is measured
exclusively on outcome, and the only population measured on process is students
(`04`).** The professional world has no accepted process metric. That is an
opportunity for us — `05` — but it also means M4 has no C1 baseline to beat.

---

## What C1 tells us about expectations for the Room

1. **Delete "the Room beats the market" from the goal set.** It is a goal that
   84–92% of resourced professional teams fail over a decade. Holding it internally
   guarantees a false negative on a Room that is actually doing its job; implying
   it externally is the claim `08` most explicitly forbids.
2. **The Room's structural advantage over this population is real but boring:
   it has no fees.** Fama-French's finding is that pre-cost skill is roughly
   cancelled by cost. A tool that removes the cost layer inherits whatever pre-cost
   edge exists. That is a legitimate thing to say and it is *not* a performance claim.
3. **Persistence is the metric to fear, not the level.** Zero-persistence is the
   professional norm. If Room quality is stable across quarters, that alone
   distinguishes it from the comparator — and it is measurable at far smaller n
   than a return edge, because it is a within-instrument comparison.
4. **The single-year number is noise for them and will be noise for us.** 45%–87%
   across 24 years, same profession.

---

Next: [`02_sellside_analysts.md`](02_sellside_analysts.md) — the structurally
closest comparator, and the one clean head-to-head.
