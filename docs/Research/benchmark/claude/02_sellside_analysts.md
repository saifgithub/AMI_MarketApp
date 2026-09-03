# 02 — Comparator C2: Sell-side research teams

**The structurally closest comparator, and the one place a genuine head-to-head is
available.**

A sell-side equity research team is a senior analyst plus associates covering a
sector. For each name they publish a rating (buy/hold/sell), a 12-month price
target, an earnings model, and a thesis. That output shape is almost exactly the
Room's: a `VerdictAction`, an `entry`/`target`/`stop`, a `time_horizon_days`, and a
`reason` (`backend/app/schemas/room.py:33-70`).

Same task, same deliverable, same horizon. This is where we should aim.

---

## M1 · Hit rate vs index

**Barber, Lehavy, McNichols & Trueman (2001), *Can Investors Profit from the
Prophets?*** — **1986–1996**, consensus built from **Zacks Investment Research**
(~360k observations, ~3,600 companies, 4,300+ analysts) **[P — CFA Digest summary
read direct]**:

> ⚠️ Corrected 2026-08-10. This entry previously read "1985–1996, the full I/B/E/S
> consensus." Both were wrong: the sample is 1986–1996 and the data is Zacks, not
> I/B/E/S — I had conflated it with Loh & Stulz, who do use I/B/E/S. Verified from
> the CFA Digest summary of the paper.

| Portfolio | Annualised geometric mean return |
|---|---|
| Most highly recommended | **18.8%** |
| Least favourably recommended | **5.78%** |

Controlling for size, book-to-market and momentum, the long-short strategy returned
**75 basis points per month** — about 9%/year gross. That is a large, real,
statistically robust edge, and it is the strongest pro-analyst result in the
literature.

**And it does not survive contact with reality.** From the same paper: capturing
it requires daily rebalancing and immediate response to rating changes, and

> "abnormal net returns for these strategies are not reliably greater than zero."

The edge exists gross and is entirely eaten by transaction costs.

Two further deflations:

- **Barber et al. (2003)** re-examined 2000–2001: the *least*-favoured stocks
  outperformed the most-favoured. The effect is regime-dependent, not a constant.
- Per `00` §4, **we can only run the long leg** — the Room has no SELL. Roughly
  half the measured 75 bp/month came from shorting the dogs. That half is
  structurally unavailable to us.

> **Expectation this sets.** The best-documented human-team stock-picking edge in
> the literature is ~9%/year *gross*, ~0% *net*, only half of it reachable by a
> buy-side-only tool, and it inverted for two years running. Expect the Room's
> honest M1 ceiling to be "indistinguishable from the base rate, measured over
> anything less than four figures of convenes."

## M2 · Risk-adjusted excess return

Same paper, same answer: after size/BM/momentum adjustment the alpha is the 75
bp/month gross figure, and net of trading costs it is not reliably positive.

**Loh & Stulz (2011)** add the sharpest deflation of all. Across I/B/E/S 1993–2006,
only **12%** of recommendation changes are *influential* — i.e. visibly move the
stock at all **[S, NBER digest]**. The other 88% are published, read, and
economically inert. Influence concentrates in star analysts, changes away from
consensus, and changes accompanied by an earnings forecast revision.

> **Expectation this sets.** Even for well-resourced professionals doing exactly
> this job, **~7 in 8 published calls are noise.** A Room whose verdicts are mostly
> unremarkable is behaving like the comparator, not failing.
>
> The corollary is a design insight worth more than the benchmark: what made a call
> influential was **being away from consensus and carrying a specific numeric
> forecast**. Both are things we can measure in a Room transcript without waiting
> for prices — see `05` and `07`.

## M3 · Forecast accuracy — **the head-to-head**

This is the section that justifies the whole document.

### Price targets

**Bradshaw, Brown & Huang (2013), *Do sell-side analysts exhibit differential
target price forecasting ability?*** (Review of Accounting Studies 18(4)), sample
**2000–2009** — **[S]**, see the caveat below:

| Measure | Sell-side result |
|---|---|
| 12-month targets met **at the end** of the horizon | **38%** |
| 12-month targets met **at some point during** the horizon | **64%** |
| Mean absolute target price forecast error | **~45%** |
| Implied target return vs actual return | targets exceed actuals by **~15%** on average |

⚠️ **Source caveat — this is the study's most consequential number and its
least-verified one.** The published paper is auth-gated; these figures are
consistently reported across independent secondary sources but I have not read it.
The **2005 preliminary working paper** (Bradshaw & Brown, two authors) *is* readable
and reports something different for its own sample: *"On average, **24-45 percent**
of analysts' target prices are met."* 38% sits inside that range, so the two are
not in conflict — but do not cite the working paper as the source of 38%/64%.
Full detail in [`VERIFICATION.md`](VERIFICATION.md) §C1. **Re-verify against the
published paper before any external use.**

Their explanation is incentive-structural and worth carrying: earnings-forecast
accuracy is tracked by the market and feeds analyst compensation; **target price
accuracy is neither scrutinised nor compensated.** So nobody optimises it.

**Why this is our benchmark.** The Room emits `target`, `stop`, `entry` and
`time_horizon_days` on every APPROVE. The Bradshaw-Brown-Huang scoring rule —
*did price touch the target at any point in the window / was it above target at
window end* — applies to a Room verdict unchanged, with no portfolio assumption, no
fee model, and no need to construct anything the Room didn't produce.

It also has the rare property of being **statistically reachable**. Detecting a
10-point improvement on a 38% base rate needs **n ≈ 189** (`00` §7) — roughly one
150-ticker sweep plus a bit, versus the 783 a 5-point M1 edge would need.

⚠️ One honest caveat before anyone gets excited. `room_runner` **mints** missing
levels: an absent stop becomes `entry × 0.94` and an absent target `entry × 1.13`,
recorded in `level_provenance` as `ami_default` (`room.py:53-70`). A minted
+13% target is not a forecast — it's a constant. **Scoring must partition by
`level_provenance` and report `pm`/`trader`-sourced targets separately.** Pooling
them would produce a "forecast accuracy" number that is partly just measuring how
often a stock rises 13%.

### Earnings forecasts

Consensus EPS beats a naive random-walk model, which is the floor. But the bias is
systematic and directional: analysts are **optimistic at long horizons and walk
estimates down** as the reporting date approaches, until the number is beatable.
The well-known consequence is that most companies "beat" consensus — an artifact of
the incentive structure, not evidence of forecasting skill.

> Relevant to us because the Room ingests analyst consensus. CR035's
> `SUPPRESS_ANALYST_CONSENSUS` ablation exists precisely to test whether the Room
> is reasoning or parroting. Its result — 41% agreement with consensus hidden vs
> 50% visible, with 35% of verdicts flipping — was flagged in CR035 as a strong
> hypothesis rather than a verdict, and was never re-run on the post-DEF066/DEF067
> corrected Room. **That re-run is the highest-value single experiment available to
> us**, and it needs no forward prices at all.

### Rating distribution — the skew we should *not* copy

Analyst ratings are heavily long-biased: roughly **~50% buy / ~45% hold / ~5%
sell** in the modern era **[S]**, a distribution shaped by banking relationships,
management access, and NASD Rule 2711 disclosure pressure rather than by the
distribution of investment merit.

Against this, CR035's measured Room numbers read differently than they first
appear:

| | APPROVE / Buy rate |
|---|---|
| Street | **63%** |
| Room (corrected, `baseline150fix`, 2026-07-20) | **37%** |
| Room (pre-fix, buggy) | 24% |

The 26-point gap was logged in CR035 as an open question. Read against the
distribution literature it is much more likely a **feature**: the Street's 63% is
inflated by conflicts the Room does not have. Barber et al. (2006), *Buys, holds,
and sells*, found that brokers with the *smallest* proportion of buy ratings
produced the *most* profitable upgrades — i.e. selectivity correlated with signal.

> **Expectation this sets.** Do not treat convergence toward the Street's 63% as
> progress. A lower APPROVE rate is what an unconflicted analyst should produce.
> What must be tested is whether the Room's selectivity is *informative* — the
> corrected re-run showed a stable buy-core (20 overlapping APPROVEs vs 13.3
> expected by chance, **p = 0.007**), which is the first CR035 result to clear
> significance and the best existing evidence that the Room has a thesis at all.

## M4 · Process quality

No public rubric-scored corpus of sell-side reports exists. The nearest thing is
**Asquith, Mikhail & Au (2005)**, which content-codes analyst reports and asks what
moves prices: the *justification* content — the specific evidence and the earnings
model — carries information beyond the headline rating.

> Directly applicable. The Room produces a full transcript. If justification
> content is what carries information for humans, then measuring the Room's
> justification content (grounding, provenance, specificity) is measuring the thing
> that matters — and CR143 already does exactly this: 92.6% of numbers grounded,
> 4.3% novel/hallucinated, stance entropy 1.48 of a possible 1.58 bits.

---

## What C2 tells us about expectations for the Room

1. **Aim at 38% / 64%.** The Bradshaw-Brown-Huang target-hit rates are the one
   benchmark that is like-for-like, needs no portfolio, and is reachable at
   n ≈ 189. Everything else in this document is context; this is the target.
2. **Expect most verdicts to be inert.** 88% of professional recommendation changes
   move nothing. That is the norm, not a failure.
3. **The Room's low APPROVE rate is probably a feature.** The Street's 63% is
   conflicted. Do not tune toward it.
4. **Beating the Street on *targets* is plausible; beating them on *returns* is
   not.** Targets are unscrutinised and uncompensated in the sell-side incentive
   structure — literally nobody is optimising them. That is an unusually soft
   target for a system that can be made to optimise them deliberately.
5. **The cheapest high-value experiment we have is the consensus ablation re-run**,
   because it needs no forward prices and answers "is it reasoning or parroting."

---

Next: [`03_retail_and_clubs.md`](03_retail_and_clubs.md) — the comparator our users
actually are.
