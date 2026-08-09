# 06 — Expectation bands

The numbers. For each metric and horizon: what humans achieve, what would count as
par / good / exceptional for the Room, and **how many observations are required
before that cell may be said out loud.**

Every band traces to a derivation in `01`–`05`. Room-side columns are deliberately
empty — nothing here estimates what the Room will score. `07` describes how they
get filled.

Read `00` §5–§7 first or these tables will mislead you.

---

## How to read a band

| Tier | Means |
|---|---|
| **Par** | Indistinguishable from the relevant base rate. **This is the expected result**, and for most cells it is also the honest expectation for a good system. |
| **Good** | Beats the base rate by a margin large enough to detect at feasible n. |
| **Exceptional** | Beats the human comparator population, not just the base rate. |

**Par is not failure.** Per `01`, 84–92% of professional teams fail to clear par
over a decade. A Room that lands solidly at par on outcome metrics while scoring
well above the comparator on process metrics is the *expected good outcome* of this
product, not a disappointment.

---

## M1 · Hit rate vs index

**Denominator: APPROVE/MODIFY verdicts only** (`00` §4). PASS/REJECT are scored
separately as abstention discipline.

### The base rate is not a constant and must not be imported

| Window | % of S&P 500 constituents beating the index | Source |
|---|---|---|
| Q1 2025 | **62%** | SPIVA MY2025 Ex. 5 **[P]** |
| Q2 2025 | **29%** | SPIVA MY2025 Ex. 5 **[P]** |
| Lifetime (vs T-bills, 1926–2016) | **42.6%** | Bessembinder 2018 **[P]** |

Consecutive quarters, 33 points apart. **There is no fixed number to compare a hit
rate against.** The base rate must be measured from the same universe over the same
window — that is what the random-pick control in `07` is for. Any cell below using
50% does so illustratively, for the power arithmetic only.

### Bands

| Horizon | Human comparator | Par | Good | Exceptional | Room |
|---|---|---|---|---|---|
| 1 week | none exists | ≈ measured base rate | — | — | *(empty)* |
| 1 month | none exists | ≈ measured base rate | — | — | *(empty)* |
| 3 months | none exists | ≈ measured base rate | +10 pts | +15 pts | *(empty)* |
| 6 months | none exists | ≈ measured base rate | +10 pts | +15 pts | *(empty)* |
| 12 months | Active funds: **36% beat** (1−64% median underperformance, 2001–2024) **[P]** | ≈ measured base rate | +10 pts | beats sell-side long leg | *(empty)* |
| 3 years | — | ≈ measured base rate | +10 pts | — | *(empty)* |
| 10 years | Active funds: **15.7% beat** **[S]** | — | — | — | *not reachable this decade* |

No "good"/"exceptional" band is offered at 1w and 1m: at those horizons the signal
is dominated by noise and the sell-side comparator publishes nothing.

### Observations required (α=.05, power=.80, illustrative p0=.50)

| Edge | n |
|---|---|
| +3 pts | **2,178** |
| +5 pts | **783** |
| +10 pts | **194** |
| +15 pts | **85** |

**CR035's entire corpus was 150.** At n=150 a measured 37% carries a 95% CI of
**±7.7 points**. Combined with the **~12% run-to-run flip rate**, no M1 edge below
about 12–15 points is measurable at all without repeated convenes per ticker.

> **Expectation: M1 will not produce a defensible claim on any timeline that
> matters to this product.** Track it, never lead with it.

---

## M2 · Risk-adjusted excess return

| Horizon | Human comparator | Room |
|---|---|---|
| all | Sell-side long-short: **+75 bp/month gross**, **not reliably > 0 net** **[P]** | **not computable** |
| all | Active funds, net alpha, aggregate: **negative** (Fama-French 2010) **[P]** | **not computable** |
| all | Retail households: **−1.5 pts/yr** avg, **−6.5 pts/yr** most active **[P]** | **not computable** |
| all | Taiwan individuals, aggregate: **−3.8 pts/yr** **[P]** | **not computable** |

**The Room cannot be scored on M2.** Risk-adjusted alpha requires a portfolio, a
fee load, a risk model, and a multi-year series. The Room emits per-ticker verdicts
and constructs no portfolio (`00` §4, `01` M2). Computing a "Room Sharpe" would
mean inventing a portfolio the Room never built and then attributing its properties
to the Room.

**Substitute, honest but weaker:** the *distribution* of per-verdict excess return
vs SPY over the same window — median, quartiles, and both tails. This is not
risk-adjusted alpha and must never be labelled as such. Per `00` §5 it is reported
**alongside every M1 hit rate**, never instead of one.

---

## M3 · Forecast accuracy — the primary outcome instrument

### 3a. Price targets — the head-to-head

| Measure | Sell-side baseline | Par | Good | Exceptional | Room |
|---|---|---|---|---|---|
| 12-mo target met **at horizon end** | **38%** **[P]** | 33–43% | **≥48%** | ≥53% | *(empty)* |
| 12-mo target met **at any point during** | **64%** **[P]** | 59–69% | **≥74%** | ≥79% | *(empty)* |
| Mean absolute target error | **~45%** **[P]** | 40–50% | ≤35% | ≤25% | *(empty)* |
| Target return vs actual (optimism bias) | **+15%** **[P]** | ±15% | ≤+8% | ≈0 | *(empty)* |

Observations required:

| Test | n |
|---|---|
| Target-at-end, +5 pts (.38→.43) | **749** |
| Target-at-end, **+10 pts (.38→.48)** | **189** |
| Target-at-end, +15 pts (.38→.53) | **84** |
| Target-touched, +10 pts (.64→.74) | **172** |

> **This is the row to aim at.** Like-for-like with a human team, no portfolio
> assumption, no fee model, and **n ≈ 189** — roughly one 150-ticker sweep plus a
> quarter. Nothing else in this document is reachable at that cost.
>
> Why it is soft: Bradshaw, Brown & Huang attribute the sell-side's poor target
> accuracy to incentives — target accuracy is neither scrutinised by the market nor
> tied to analyst pay, so **nobody is optimising it.** A system that optimises it
> deliberately is competing against an unattended metric.

⚠️ **Mandatory partition.** `room_runner` mints absent levels at `entry × 0.94`
(stop) and `entry × 1.13` (target), flagged `ami_default` in `level_provenance`
(`backend/app/schemas/room.py:53-70`). Minted levels are constants, not forecasts.
**Score `pm`- and `trader`-sourced targets separately from `ami_default` ones, and
never report a pooled figure** — a pooled number would partly measure how often a
stock rises 13%.

### 3b. Direction

| Horizon | Baseline | Par | Good | Room |
|---|---|---|---|---|
| Room's own `time_horizon_days` | measured base rate | ≈ base rate | +10 pts (n≈194) | *(empty)* |
| 1w / 1m / 3m fixed | measured base rate | ≈ base rate | +10 pts | *(empty)* |

Score at **both** the Room's stated horizon and the fixed grid. A system evaluated
only on its own chosen horizon can game the metric by choosing horizons.

### 3c. Calibration (Brier score)

| Measure | Human comparator | Par | Good | Exceptional | Room |
|---|---|---|---|---|---|
| Brier score on the PM's implied confidence | Superforecasters ≈ **20–30% below median forecaster** **[S]**; retail systematically **overconfident** **[P]** | any resolved calibration | reliably beats a constant-base-rate forecaster | approaches superforecaster-style calibration | *(empty)* |

Brier is proper, works on single binary forecasts, and decomposes into calibration
and resolution. Per `03`, the retail comparator is systematically overconfident, so
this is a plausibly winnable lane — but the Room must first **emit a numeric
confidence**, which it does not currently do as a structured field.

> **Blocking prerequisite for M3c**, and worth flagging as its own defect: no
> confidence field exists on `Verdict`. Until one does, calibration is unmeasurable
> regardless of sample size.

---

## M4 · Process quality — the instrument available today

The only metric family that (a) has a real primary-sourced human rubric, (b)
requires no market data, and (c) is measurable at n = 18.

### 4a. Report Card composite (rubric in `05` §6, adapted from the CFA Institute form)

| Measure | Human comparator | Par | Good | Room |
|---|---|---|---|---|
| Report Card /100 | CFA Research Challenge grades on a 100-pt form **[P]**; **no public score distribution exists** | establish own baseline first | — | *(empty)* |

Honest limitation: the CFA Institute publishes the rubric but not the score
distribution, so there is **no external "passing score" to import.** The rubric
gives us comparable *dimensions*, not a comparable *number*. First measurement
establishes our own baseline.

### 4b. Components that DO have anchors

| Measure | Anchor | Par | Good | Room (CR143, n=18, 2026-08-07) |
|---|---|---|---|---|
| Unanimous convenes | **0%** — the anti-club test (`03`, `05`) | <10% | **0%** | **0 / 18** ✅ |
| Stance entropy | max 1.58 bits | >1.2 | >1.4 | **1.48** ✅ |
| Number provenance (grounded) | Asquith et al.: justification content carries the information **[S]** | >85% | >95% | **92.6%** ◐ |
| Novel/ungrounded numbers | zero-tolerance class | <5% | <2% | **4.3%** ◐ |
| Role identifiability | — | >75% | >90% | **87.9%** ◐ |
| Disclosure honesty | **no human analogue** | — | — | *(unscored)* |

> **These are the only cells in this document with a Room number in them**, and
> three of six are already at "good." That is not an accident of generosity — it is
> what `00` §7 predicted: process is measurable at n=18, outcome needs n≈189–783.

### 4c. Abstention discipline

| Measure | Human comparator | Par | Good | Room |
|---|---|---|---|---|
| Buy/APPROVE rate | Street **63%** **[S]**; brokers with *fewest* buys produced the most profitable upgrades **[S]** | 25–50% | selectivity that is *informative* | CR035: **37%** |
| Do PASS names underperform APPROVE names? | — | no difference | PASS < APPROVE, detectably | *(empty)* |

**Do not tune the APPROVE rate toward the Street's 63%** (`02`). The Street's
figure is conflict-inflated. The question is not whether the Room buys as often as
the Street, but whether its selectivity carries signal — and CR035's corrected
re-run gives the first significant evidence that it does (20 overlapping APPROVEs
vs 13.3 expected by chance, **p = 0.007**).

---

## Summary — what to expect, in one table

| Metric | Reachable? | When | Expect |
|---|---|---|---|
| **M4 process** | ✅ now | today, n=18 | **This is where the Room already looks good.** Lead here. |
| **M3a targets** | ✅ plausibly | n≈189, ~1 sweep + a quarter | The one honest outcome head-to-head. Aim here. |
| **M3c calibration** | ⚠️ blocked | after a confidence field exists | Winnable lane vs an overconfident comparator. |
| **M1 hit rate** | ⚠️ barely | n≈783 for +5 pts, above a 12% noise floor | Track it. Never lead with it. |
| **M2 risk-adjusted** | ❌ no | never, structurally | Not computable. Don't fake it. |

**The expectation to carry into every conversation about the Room:** we will have a
defensible *process* claim long before — possibly years before — we have a
defensible *returns* claim. That is not a weakness in the Room. It is what the
arithmetic of this domain does to everybody, including the professionals with
better data and more money.

---

Next: [`07_how_we_would_know.md`](07_how_we_would_know.md).
