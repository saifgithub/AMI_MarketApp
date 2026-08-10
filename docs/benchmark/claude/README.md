# Benchmarking the Room against human analyst teams

**Written:** 2026-08-10 · **Author:** Claude (track R) · **Status:** research +
measurement notes. No code, no behaviour change.

> **Purpose: managing expectations of the Room.** What does a team of humans
> actually achieve at analysing and picking stocks — and therefore what is it
> reasonable to expect of the Room, over what horizons, and how long before we
> could even tell?

Written **without reading** [`../kimi/`](../kimi/), which was being produced in
parallel on the same question. Two independent reads are only worth diffing if
they were produced independently. Same comparator-first file naming, so the two
can be compared cell by cell.

---

## The short version

**1. Nobody is good at this.** 84.3% of active US large-cap funds trailed the S&P
500 over ten years; 89.5% over fifteen. *"The Room beats the market"* is a goal the
entire resourced professional industry fails at. Delete it from the goal set.

**2. A team of amateurs did worse than a lone amateur.** Investment clubs returned
14.1% against the market's 17.9%; **60% underperformed**; the average club came in
below the average *individual* (16.4%). This is the finding that most directly
interrogates our premise — *"you now have a team of twelve analysts"* is not
automatically a benefit.

**3. Structure is what earns a team its keep — and it's why we survive #2.**
Teams running dialectical inquiry and devil's advocacy make measurably better
decisions than consensus teams, *and report lower satisfaction doing it.* That last
part is why voluntary human clubs don't sustain it and why they lose. The Room runs
opposed bull/bear researchers and three conflicting risk debators by construction,
and cannot get tired of it. **Across 18 convenes, zero produced a unanimous verdict**
(CR143). On the one metric separating a research team from a losing investment club,
the Room currently measures on the right side.

**4. We probably cannot prove a returns edge — and that is the realism injection.**
Detecting a 5-point hit-rate edge needs **n ≈ 783**; CR035's whole corpus was 150,
where the 95% CI on a 37% rate is **±7.7 points**. Worse, CR035 measured a **~12%
verdict flip rate between identical re-runs** — the instrument's own noise floor —
and that estimate is itself only 4 flips in 32 paired runs, a 95% CI of
**[1%, 24%]**. We do not currently know whether the Room is nearly deterministic or
flips a quarter of its verdicts. Anyone quoting a Room win rate off 150 convenes is
quoting noise.

**5. So aim at forecast accuracy and process, not returns.** Sell-side analysts hit
**38%** of their 12-month price targets at horizon end and **64%** at some point
during — and the Room emits targets in the same shape. That head-to-head needs
**n ≈ 189**, roughly one sweep plus a quarter. Meanwhile the CFA Institute, grading
university teams on exactly this task, awards **0 of 100 points for being right**
and 100 for process. The profession's own answer to *"how do you judge a research
team you can't wait a decade to evaluate?"* is a weighted process rubric. We should
copy it.

**6. The honest comparator is not Wall Street. It's our users.** Retail investors
lose 1.5 points a year on average, 6.5 for the most active — and they lose it
through **overtrading, not bad picking**. Their gross selection is roughly a wash.
**A Room that improves picking by zero and suppresses impulse trading would beat
this comparator outright.** That is measurable, plausible, and requires no
stock-picking edge at all.

**The one sentence to carry:** *we will have a defensible claim about the Room's
process long before — possibly years before — we have one about its returns.* Not
because the Room is weak, but because that is what the arithmetic of this domain
does to everybody.

---

## What to expect, by metric

| Metric | Reachable? | When | Expect |
|---|---|---|---|
| **Process quality** | ✅ now | today, n=18 | **Where the Room already looks good.** Lead here. |
| **Forecast accuracy — targets** | ✅ plausibly | n≈189 | The one honest outcome head-to-head. Aim here. |
| **Forecast accuracy — calibration** | ⚠️ blocked | needs a confidence field | Winnable vs an overconfident comparator. |
| **Hit rate vs index** | ⚠️ barely | n≈783, above a 12% noise floor | Track it. Never lead with it. |
| **Risk-adjusted excess return** | ❌ never | structurally impossible | The Room builds no portfolio. Don't fake it. |

---

## The files

| | |
|---|---|
| [`00_method_and_limits.md`](00_method_and_limits.md) | **Read first.** The four metrics, the four comparators, and the four structural facts that constrain everything else — including the power arithmetic, shown in full. |
| [`01_active_fund_managers.md`](01_active_fund_managers.md) | The professional ceiling. SPIVA, persistence, Fama-French. |
| [`02_sellside_analysts.md`](02_sellside_analysts.md) | Structurally closest to the Room. **Contains the head-to-head.** |
| [`03_retail_and_clubs.md`](03_retail_and_clubs.md) | Who our users are. The load-bearing comparator, and the club finding. |
| [`04_student_and_cfa_teams.md`](04_student_and_cfa_teams.md) | No outcome data — and why that absence is the interesting part. |
| [`05_process_quality.md`](05_process_quality.md) | Why structured teams win; the proposed Room Report Card rubric. |
| [`06_expectation_bands.md`](06_expectation_bands.md) | **The deliverable.** Per metric × horizon: human baseline, par/good/exceptional, n required. |
| [`07_how_we_would_know.md`](07_how_we_would_know.md) | Measurement notes → input to CR157. Controls, estimators, the power gate, sequencing. |
| [`08_what_we_can_and_cannot_claim.md`](08_what_we_can_and_cannot_claim.md) | 🟢 safe externally / 🟡 teaching-only / 🔴 never. And the claim we *should* make. |
| [`09_rejected_approaches.md`](09_rejected_approaches.md) | **Read before proposing a better benchmark.** Seven approaches evaluated and killed, with the pre-condition that would re-open each. R1 (risk-adjusted return via a portfolio-level Room) is the one most likely to be re-proposed. |
| [`sources.md`](sources.md) | Every figure, with URL, marked **[P]** primary or **[S]** secondary. |

---

## What to do next

From [`07`](07_how_we_would_know.md) §7, cheapest and most informative first. Note
that the top four need **no forward prices and no waiting**, and two need no new
convenes at all — the instinct on reading `06` is to go collect returns, but the
better moves are all upstream of that.

1. **Re-run the consensus ablation** on the corrected Room. CR035's arms B/C ran
   with DEF066/DEF067 live and were never honestly re-run. Answers *"is it
   reasoning or parroting?"* — no forward prices needed.
2. **Score the `05` rubric** over the existing CR143 corpus. No new convenes.
3. **Run the random-pick control** over `tickers_150`. No LLM calls. Establishes
   the real base rate, which makes every later hit-rate number interpretable.
4. **Re-measure the noise floor** — ~100 paired identical convenes. Cheaper than
   one scoring sweep, and every outcome metric is uninterpretable until the
   [1%, 24%] interval narrows.
5. **Add a confidence field to `Verdict`** — verified absent today. Cheapest
   high-value change in the study; unblocks Brier calibration scoring.
6. **Then** target-hit scoring at n≈189.

If the loop gets built, the move is to promote **CR157** `proposed → in_progress`
with [`07`](07_how_we_would_know.md) attached — not to mint a new CR.

---

## Caveats

- **Room-side columns in `06` are deliberately empty.** Nothing here estimates what
  the Room will score. The only Room numbers quoted are CR035's and CR143's
  measured ones.
- Figures marked **[S]** in `sources.md` come from multiple independent secondary
  reports because several S&P PDFs return HTTP 403 to automated fetching.
  **Re-verify any [S] figure by hand before external use.**
- CR035's headline agreement numbers were measured on a Room with two since-fixed
  defects live. The corrected re-run is cited where it exists; the ablation arms
  were never re-run, which is why that is item 1 above.
