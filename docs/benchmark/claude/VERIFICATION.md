# Verification status — what was actually read

**Audited 2026-08-10**, in response to a direct challenge: *"we had 'the seven
findings that set expectations' — did we prove them all?"*

Answer: **no.** Two were proved outright, four are now verified against primary
documents after this audit, and one rests on secondary sources with its primary
paywalled. One citation was **wrong** and has been corrected.

This file exists because "verified" was being used loosely. A WebSearch that
returns text *from* an abstract is not the same as having read the abstract, and
`sources.md` originally labelled several of those `[P]`. That was an overstatement
and is fixed.

---

## The seven findings

| # | Finding | Status |
|---|---|---|
| 1 | Nobody is good at this (SPIVA) | ◐ **Partly.** Annual series + base rates read from primary. **The 10y/15y/20y headline numbers are secondary only.** |
| 2 | A team of amateurs did worse than a lone amateur | ✅ **Verified from primary** — and the finding got *stronger*. See correction C2. |
| 3 | Structured dissent beats consensus | ◐ Secondary. Direction consistently reported; paper not read. |
| 4 | Skew means "right more often" ≠ "made money" | ✅ **Verified from primary.** Improved with better figures. |
| 5 | The one clean head-to-head (38%/64% targets) | ⚠️ **Secondary only — and my citation was wrong.** See correction C1. |
| 6 | We probably cannot prove an edge | ✅ **Proved.** My own computation, re-derived and cross-checked. |
| 7 | The Room is structurally not a fund | ✅ **Proved.** Direct code inspection. |

## Documents I actually opened and read

| Document | What it confirmed |
|---|---|
| **SPIVA U.S. Scorecard Mid-Year 2025** (PDF, pp. 1–8) | Exhibit 1 full annual series 2001–2024 + H1 2025 (range 45%–87%); H1 2025 54%; 2024 65%; mid-cap 25%, small-cap 22% H1 2025. **Exhibit 5: 62% of S&P 500 stocks beat the index in Q1 2025, 29% in Q2** — the load-bearing base-rate instability figure. |
| **CFA Institute Research Challenge — Written Report Guidelines + Evaluation Form** (PDF, pp. 1–2) | The full 100-point rubric, verbatim. Zero points for outcome. Required header includes recommendation + target price. |
| **Barber & Odean, *Too Many Cooks Spoil the Profits*** (FAJ, PDF pp. 1–2, 4–6) | 166 clubs, Feb 1991–Jan 1997; "60 percent of the clubs underperformed the index"; **Figure 1 gross/net returns**; clubs turned over 65% of portfolio annually; Table 2 abnormal-return panels. |
| **Bessembinder, *Do Stocks Outperform Treasury Bills?*** (PDF, pp. 1–2) | Abstract + intro: majority of CRSP stocks below one-month Treasuries lifetime; **best-performing 4% explain the entire net gain**; **only 47.8% of monthly CRSP returns beat the one-month T-bill rate**; "poorly diversified active strategies most often underperform market averages." |
| **Bradshaw & Brown (2005 working paper)** (PDF, pp. 1–2) | **"On average, 24-45 percent of analysts' target prices are met."** ⚠️ This is *not* the 38%/64% I cited — see C1. |
| **Own computation** (Python, re-derived) | All power/CI arithmetic: n=2178/783/194/85; target-hit n=749/189/84; touched-during n=172; CI ±7.7pts at n=150; noise-floor CI [1.0%, 24.0%]; Sharpe years 3.8/15.4/42.7/96.0. |
| **The codebase** (grep + read) | `VerdictAction` has no SELL; no `confidence` field on `Verdict`; `level_provenance` + minted `entry×0.94`/`entry×1.13`; `room_benchmark_report.py --forward` exists at line 329. CR035's flip rate 4/32, APPROVE 24%→37%, p=0.007, κ=0.14. |

## Still secondary-only

Verified across multiple independent reports, primary not obtained. **Re-verify by
hand before external use.**

- **SPIVA 10-year 84.3% / 15-year 89.5% / 20-year ~92% / full-year 2025 79%** — S&P's
  year-end PDFs return HTTP 403 to automated fetching. These are the README's
  headline numbers and they are the least-verified figures in the study.
- **Bradshaw, Brown & Huang (2013): 38% / 64% / 45% / 15%** — Springer auth-gated. See C1.
- Barber, Lehavy, McNichols & Trueman (2001): 18.8% / 5.78% / 75 bp per month.
- Loh & Stulz (2011): only 12% of recommendation changes influential.
- Schweiger, Sandberg & Ragan (1986): dialectical inquiry / devil's advocacy > consensus.
- Good Judgment Project Brier figures (goodjudgment.com PDF 403s).
- Barber & Odean (2000) household returns — **partly cross-verified**: the 16.4%
  net individual-investor figure appears independently in *Too Many Cooks* Figure 1.
- Taiwan day traders: <1% reliably profitable.

---

## Corrections made as a result

### C1 — Bradshaw target-price citation was wrong ⚠️

**What was wrong.** `sources.md` cited `assets.csom.umn.edu/assets/37727.pdf` as
the source for "38% of targets met at horizon end, 64% during." I fetched that PDF.
It is the **2005 preliminary working paper by Bradshaw & Brown — two authors, not
three** — and its abstract says something different:

> "On average, **24-45 percent** of analysts' target prices are met, and analysts do
> not exhibit persistent differential abilities to forecast target prices."

The linked document does not contain the figure attributed to it.

**Resolution.** The 38%/64% figures belong to the **published 2013 version**
(Bradshaw, Brown & Huang, *Review of Accounting Studies* 18(4)), whose sample is
**2000–2009** — a fact I did not previously have. Those figures are consistently
reported across independent secondary sources, and 38% sits inside the working
paper's 24–45% range, so they are not contradictory — but I have **not** read the
published paper, and Springer is auth-gated.

**Why this matters more than the other gaps:** 38%/64% is the benchmark `06`
recommends aiming at. It is the single most consequential number in the study and
it is secondary-sourced. `02` and `06` now say so explicitly, and carry the
2000–2009 sample period.

### C2 — the investment-club finding was understated

`03` claimed retail's "gross stock selection is roughly a wash." The primary
document is more specific, and more interesting. *Too Many Cooks* Figure 1,
annualized geometric mean, Feb 1991 – Jan 1997:

| | Gross | Net |
|---|---|---|
| Index fund (S&P 500) | 18.0% | 17.8% |
| **Individuals** | **18.7%** | **16.4%** |
| **Clubs** | **17.0%** | **14.1%** |

*(A value-weighted NYSE/Amex/Nasdaq index returned 17.9% over the same period —
that is the "market 17.9%" figure quoted throughout this study.)*

Two refinements:

1. **Individual investors' gross selection *beat* the index fund** — 18.7% vs 18.0%.
   Not "a wash": they picked well and lost it entirely to costs. That strengthens
   the C3 argument in `00` §3 rather than weakening it.
2. **Clubs, unlike individuals, genuinely did pick badly.** Table 2's own-benchmark
   gross abnormal return is **−0.106 pps/month, significant at 5%** — Barber &
   Odean's reading is that "the stocks clubs choose to buy perform worse than the
   stocks they choose to sell." Net of costs, clubs underperformed their own
   beginning-of-year portfolio by 3.5 pps/year, with Jensen's alpha at −4.8 pps and
   the Fama-French intercept at −4.4 pps.

So the group didn't merely trade more than the individual — **it also selected
worse.** The "too many cooks" result is a stronger warning to a
twelve-agent product than originally written, and `03` has been updated.

### C3 — Bessembinder figures upgraded

The abstract says the best-performing **4%** of listed companies explain the entire
net gain (I had cited 4.3%, which is the body's 1,092/25,967 count). Added from the
introduction: **only 47.8% of all monthly CRSP common stock returns from 1926–2016
exceed the one-month Treasury rate**, and fewer than half are even positive.

Also worth recording: Bessembinder himself draws the conclusion `00` §5 presents —
"the results help to explain why poorly diversified active strategies most often
underperform market averages." That is no longer my inference; it is his.

---

## What this changes about the study's conclusions

**Nothing in the direction of the findings.** Every correction moved a number to a
firmer footing or made a finding stronger. The one wrong citation pointed at a
paper reporting 24–45% where I claimed 38% — a range that contains it.

**But the confidence labels were wrong**, and on a document whose central argument
is *"report your n and your interval, don't quote noise as fact,"* mislabelling
source quality is the failure mode the document itself warns about. Hence this file.

---

Back to [`README.md`](README.md) · sources in [`sources.md`](sources.md).
