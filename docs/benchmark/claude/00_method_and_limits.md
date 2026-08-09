# 00 — Method, and the limits on what any of this can tell us

**Written:** 2026-08-10 · **Author:** Claude (track R) · **Status:** research, no code

Read this first. It defines the four metrics, names the four comparator
populations, and — more importantly — establishes four structural facts that
constrain every number in files `01`–`08`. Skipping it produces confident
misreadings of the rest.

---

## 1. The question

> The Room will always be compared to a team of humans. What does a team of humans
> actually achieve — and therefore what should we expect of the Room?

Note what this is *not*. It is not "can the Room beat the market." That framing
imports an assumption — that beating the market is the standard a research team is
held to — which the evidence in `01` flatly contradicts. The professionals mostly
don't beat it, and the ones who do mostly can't repeat it.

The useful question is narrower and answerable: **for each thing a research team
produces, how good are humans at producing it, and how would we tell if the Room
were better or worse?**

---

## 2. The four metrics

A research team produces four separable things. They are measured by different
literatures, they fail in different ways, and they have wildly different sample
requirements. Conflating them is the commonest error in this space.

| # | Metric | The question it answers | Unit of observation |
|---|---|---|---|
| M1 | **Hit rate vs index** | How often does a pick beat the benchmark over horizon H? | one pick, one horizon |
| M2 | **Risk-adjusted excess return** | Was the money made worth the risk taken? | a portfolio, over time |
| M3 | **Forecast accuracy** | Did the *stated numbers* — target, stop, direction, confidence — verify? | one forecast |
| M4 | **Process quality** | Was the reasoning sound, evidenced, and free of the known failure modes? | one report / transcript |

M1 is intuitive and misleading (§4). M2 is the honest professional measure and is
**not computable for the Room at all** (§3). M3 is the only clean head-to-head we
can actually run. M4 is measurable at small n and is where the Room's defensible
claim lives.

## 3. The four comparators

| # | Population | Why it's here | Outcome data |
|---|---|---|---|
| C1 | **Active fund managers** | The professional ceiling. If they can't, nobody can. | Excellent (SPIVA, CRSP) |
| C2 | **Sell-side research teams** | Structurally closest to the Room: a team, one ticker, a rating + a target. | Excellent (I/B/E/S) |
| C3 | **Retail investors & investment clubs** | Who our users actually are. The load-bearing comparator. | Good (Barber & Odean) |
| C4 | **Student / CFA competition teams** | Who our users are *becoming*. | Almost none — process only |

Each of `01`–`04` takes one population and works all four metrics through it.

---

## 4. Structural fact #1 — the Room is not a fund, so most benchmarks don't transfer

`VerdictAction` (`backend/app/schemas/room.py:13-22`) is
`APPROVE | REJECT | MODIFY | PASS | NO_VERDICT`. Per CR035's mapping,
APPROVE/MODIFY → Buy and PASS → Hold. **There is no SELL.** The Room is buy-side
only, evaluates one ticker at a time, on a ticker the *user* chose, builds no
portfolio, sizes nothing across names, and never rebalances.

Three consequences that bind the whole study:

1. **Long-short results are not replicable.** Barber, Lehavy, McNichols & Trueman
   (2001) got 75 bp/month from buying the most-recommended and shorting the
   least-recommended. We can only ever run the long leg. Half of their measured
   effect is unavailable to us by construction.
2. **SPIVA-style fund comparison is an analogy, not a measurement.** SPIVA measures
   *portfolios, net of fees, against a benchmark, with survivorship correction*.
   The Room has no portfolio and no fees. Quoting "84% of funds underperform" next
   to a Room hit rate is a category error, and `08` forbids it in external copy.
3. **Every hit rate must be conditional on acting.** The denominator is
   APPROVE/MODIFY verdicts, not all convenes. A Room that PASSes on everything has
   no hit rate — it has an *abstention rate*, which must be reported separately or
   the headline number is trivially gameable.

**Ticker selection is not ours.** Users choose what to convene. So the Room's
"picks" are a filter applied to a user-chosen sample, not a selection from the
universe. Against any comparator who chose their own coverage, that is a different
task. The honest control is not "the market" but *"what would have happened to
this same ticker without the Room"* — see `07`.

## 5. Structural fact #2 — skew makes "right more often" ≠ "made money"

Bessembinder (2018), 25,967 US stocks, 1926–2016:

- **57.4%** of stocks had a lifetime buy-and-hold return **below one-month T-bills**.
- The **median** stock's lifetime return was about **−3.7%**.
- **4.3%** of stocks (1,092 of them) account for the **entire** net wealth creation
  of the US market over 90 years; the other 95.7% collectively matched T-bills.

Two things follow. First, a stock-picker can be right more often than not and still
lose badly, because the losses are ordinary and the wins are extreme and rare.
Second — and this is the one that catches people — **a concentrated portfolio has a
median outcome below the index even with zero skill difference**, purely from
skew. The index captures the 4.3%; a 10-name portfolio probably doesn't.

**Rule adopted for this study: no hit rate is ever reported without its return
distribution.** A 60% hit rate with a −40% tail is a worse result than a 45% hit
rate with a +300% tail, and a bare percentage hides which one you have.

## 6. Structural fact #3 — the base rate moves under your feet

S&P's own measurement, SPIVA Mid-Year 2025 (Exhibit 5, data to 2025-06-30):

| Quarter | % of S&P 500 stocks that beat the index |
|---|---|
| Q1 2025 | **62%** |
| Q2 2025 | **29%** |

Same index, same year, consecutive quarters — the base rate for "a randomly chosen
constituent beats the benchmark" moved by 33 points. S&P also note the return
distribution was positively skewed in both quarters (mean above median), which is
§5 showing up in-period.

The same instability appears in the professional series. SPIVA Exhibit 1, share of
active large-cap funds underperforming the S&P 500, by year:

```
2001 65   2002 68   2003 75   2004 69   2005 49   2006 68
2007 45   2008 56   2009 48   2010 66   2011 82   2012 63
2013 55   2014 87   2015 65   2016 66   2017 63   2018 65
2019 71   2020 60   2021 85   2022 51   2023 60   2024 65
H1 2025 54
```

Range: **45% to 87%**. In 2007 most active large-cap managers beat the index; in
2014 almost none did. Any single-year read on skill is mostly a read on the year.

**Rule adopted: no metric is reported at a single horizon, and no cross-period
comparison is made without the same-window control.** A Room scored only in a
quarter like Q1 2025 would look like a genius; the same Room in Q2 2025 would look
broken. Both readings would be artifacts.

## 7. Structural fact #4 — the arithmetic of proof (the binding constraint)

This is the part that determines the roadmap, so it is shown in full rather than
asserted.

For a one-sample, two-sided test that a hit rate `p1` differs from a base rate
`p0`, at significance α and power 1−β:

```
n  =  [ z(1−α/2)·√(p0(1−p0))  +  z(1−β)·√(p1(1−p1)) ]²  /  (p1 − p0)²

with α = 0.05  →  z = 1.95996
     β = 0.20  →  z = 0.84162     (i.e. 80% power)
```

Worked, against a 50% base rate:

| Edge to detect | p0 → p1 | n required |
|---|---|---|
| +3 points | .50 → .53 | **2,178** |
| +5 points | .50 → .55 | **783** |
| +10 points | .50 → .60 | **194** |
| +15 points | .50 → .65 | **85** |

And against the sell-side price-target base rate of 38% (Bradshaw, Brown & Huang
2013 — see `02`), which is the one comparison we can run like-for-like:

| Edge to detect | p0 → p1 | n required |
|---|---|---|
| +10 points | .38 → .48 | **189** |

Now the two facts that make this bite:

**(a) Our largest corpus to date is 150 convenes.** CR035 ran 150 tickers. At
n = 150 the 95% confidence interval on a measured 37% rate is

```
1.96 · √(0.37 · 0.63 / 150)  =  ±7.7 percentage points
```

so a measured 37% means "somewhere between 29% and 45%." That interval is wider
than most of the effects we would care about.

**(b) The instrument has its own noise floor.** CR035 measured a **~12% verdict
flip rate between two identical re-runs** — same ticker, same inputs, different
answer. An edge smaller than the instrument's own irreproducibility cannot be
measured at all without convening each ticker repeatedly and scoring the modal
verdict, which multiplies the cost per data point.

⚠️ And the noise floor is itself barely measured: it comes from **4 flips out of
32** paired runs (`CR035_room_benchmark.md:133`), whose 95% CI is **[1.0%, 24.0%]**.
So the honest statement is "the instrument's irreproducibility is somewhere between
negligible and a quarter of all verdicts, and we don't know which." Re-measuring it
on the current prompt generation is cheap and is the precondition for interpreting
any outcome metric — see `07` §3.

**Conclusion, and it is the single most important sentence in this document: we
will be able to make a defensible claim about the Room's *process* long before we
can make one about its *returns*.** Not because the Room is weak, but because
outcome claims in this domain need four-figure sample sizes and the instrument is
noisy. Anyone — us included — quoting a Room win rate off 150 convenes is quoting
noise.

---

## 8. What makes a comparison invalid

Applied throughout `01`–`06`; violations are called out where the literature
commits them.

- **Pooling across mandate regimes.** Different single-name caps produce different
  APPROVE rates for reasons unrelated to judgement. (The CR153/CR156 lesson.)
- **Pooling across prompt versions.** A rate spanning two prompt generations
  measures the mix, not the model. Partition by `llm_audit.prompt_version` (CR158).
- **Survivorship.** Funds that die are dropped from naive averages; SPIVA corrects
  for this, most casual comparisons don't.
- **Gross vs net.** The sell-side long-short edge is real gross and vanishes net of
  costs. Always state which.
- **Selection of the window.** §6. Pick your quarter and you can prove anything.
- **Agreement mistaken for accuracy.** CR035 measured agreement with *analyst
  consensus*. Consensus is an opinion, not an outcome. High agreement with the
  Street means the Room is Street-like, which is a finding about style, not skill.

## 9. Scope and honesty commitments

- Every figure traces to a primary source in [`sources.md`](sources.md), marked
  **[P]** where I read the primary document and **[S]** where I could only verify
  via multiple independent secondary reports (S&P's own PDFs 403 to automated
  fetching for some editions).
- **Room-side columns in `06` are deliberately empty.** The only Room numbers in
  this study are CR035's measured ones. Nothing here estimates what the Room will
  score.
- Where a comparator has no outcome data, that is stated rather than filled with a
  plausible number. `04` is mostly this.
- This document was written **without reading** `docs/benchmark/kimi/`, which was
  being produced in parallel on the same question. Two independent reads are only
  worth diffing if they were produced independently.

---

Next: [`01_active_fund_managers.md`](01_active_fund_managers.md) — the professional
ceiling.
