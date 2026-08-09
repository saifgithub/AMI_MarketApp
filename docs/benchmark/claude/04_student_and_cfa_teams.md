# 04 — Comparator C4: Student and CFA competition teams

**The comparator with almost no outcome data — and the one that changes how the
other three should be read.**

This is the population AMI Trade's users most resemble in *role*: a small team,
learning, analysing a single company, producing a recommendation and a target
price, being judged. It is the closest analogue to what a Room session is
pretending to be.

The honest finding is that **nobody scores these teams on whether they were right.**
That is not a data gap to apologise for. It is the profession telling us what it
believes is measurable.

---

## M1 · Hit rate vs index — no usable series

The CFA Institute Research Challenge does not track whether team recommendations
subsequently made money. Reports are graded and the competition ends.

Student-managed investment funds (SMIFs) do run real money against real benchmarks
and some publish, but the literature is thin, fragmented and structurally
unreliable for our purposes:

- Individual fund disclosures exist (e.g. Purdue SMIF benchmarks quarterly against
  the S&P 500), but they are **self-published by the winner-selected subset that
  chooses to publish** — the survivorship problem in its purest form.
- Academic treatment is sparse; the *Journal of Economics and Finance Education*
  study of a Florida SMIF is representative — it concludes active management "can
  add value" on one fund's data **[S]**, which is an n of one.
- Mandates are heavily constrained (usually long-only, large-cap, low turnover,
  faculty-supervised), so a SMIF is closer to a constrained index tracker than to a
  stock-picking team.

**I am not going to synthesise a hit rate from this.** Any number I produced would
be a survivorship-biased average of self-reported results across incomparable
mandates. Per `00` §9, the honest answer is: no baseline available.

## M2 · Risk-adjusted excess return — no usable series

Same reasons, worse. SMIF disclosures rarely include risk-adjusted figures and
never include a survivorship-corrected cross-sectional series. There is no student
equivalent of SPIVA.

## M3 · Forecast accuracy — not scored, though the forecast is required

Here is the interesting part.

The CFA Institute Research Challenge **requires** each team to publish exactly the
forecast we would score. From the official written report guidelines **[P]**, every
report must state:

> Company name · Exchange · Ticker symbol · Sector · Industry ·
> **Recommendation (buy/sell/hold)** · Current price (as of \_\_date) ·
> **Target price (% increase/decrease)**

A rating and a target price, on a single ticker, from a team — the same tuple the
Room emits and the same tuple Bradshaw, Brown & Huang scored for the sell-side
(`02`).

**And the rubric allocates zero points to whether it turns out to be correct.**

## M4 · Process quality — the one lane with a real, primary-sourced baseline

The Research Challenge Written Report Evaluation Form, in full **[P]**:

| Section | Max points |
|---|---|
| Business Description | 5 |
| Industry Overview & Competitive Positioning | 10 |
| Investment Summary | 15 |
| **Valuation** | **20** |
| **Financial Analysis** | **20** |
| Investment Risks | 15 |
| Environmental, Social, Governance | 15 |
| **Total** | **100** |

Overall competition scoring is weighted 50% written report / 50% oral presentation.

Three things to extract:

1. **Outcome is worth 0 of 100 points.** The global professional body that
   certifies equity analysts, when training and grading the next generation on
   exactly this task, scores **process only**. Not because outcome doesn't matter —
   because over one report and one year, outcome is mostly noise, and they know it.
   This is `00` §7 expressed as institutional policy.
2. **The weighting is a usable rubric.** Valuation (20) and Financial Analysis (20)
   dominate at 40% combined; Risks (15) is weighted equal to ESG (15) and above
   Industry Overview (10). This maps with unusual directness onto the Room's roster
   — `fundamentals_analyst` → Financial Analysis/Valuation, the three risk debators
   → Investment Risks, `market_analyst`/`news_analyst` → Industry Overview.
3. **Risk gets 15 points as a first-class section.** Not an appendix. A report that
   nails the valuation and ignores the risks loses 15% before the judges consider
   anything else.

> **Expectation this sets, and it reframes the whole study.** The profession's own
> answer to *"how do you judge a research team you cannot wait ten years to
> evaluate?"* is **a weighted process rubric**. We have been treating process
> metrics as the consolation prize for not being able to measure returns. The CFA
> Institute treats them as the primary instrument. So should we.

### The gap in the analogy

Two caveats before adopting the rubric wholesale:

- **Judged on the report, not the reasoning.** The rubric scores a polished
  10-page artifact. The Room produces a live transcript. Some categories transfer
  cleanly (was the valuation done, were risks covered); others measure writing
  quality, which is not what we want to know.
- **ESG at 15 points** reflects CFA Institute curriculum priorities and has no
  counterpart in the Room's roster. Not a gap to fill — a reminder that the rubric
  encodes one institution's priorities, not a law of nature.

---

## What C4 tells us about expectations for the Room

1. **Adopt a weighted process rubric as the primary instrument**, with the CFA
   Research Challenge form as the starting template, adjusted for the Room's roster
   and dropping ESG. Detail in `05`; the score itself is `06`'s M4 band.
2. **Every rubric dimension is scorable on a transcript we already have.** No
   forward prices, no waiting, no four-figure sample. CR143's corpus of 18 convenes
   / 198 turns is already enough to score a rubric — it is nowhere near enough to
   measure a hit rate.
3. **This is the comparator to use in-app.** For a learner, "your Room scored 78 on
   the same rubric the CFA Institute uses to grade university teams" is concrete,
   immediately available after a single convene, pedagogically honest, and carries
   none of the regulatory exposure of a returns claim (`08`).
4. **State the absence plainly.** There is no student outcome baseline. `06` leaves
   those cells empty rather than manufacturing one.

---

Next: [`05_process_quality.md`](05_process_quality.md) — the theory of why a
structured team beats an unstructured one, and how to score it.
