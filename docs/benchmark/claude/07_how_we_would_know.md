# 07 — How we would ever know

**Input to CR157** (`Weekly retrospective loop: score convened Rooms against
reality`, filed 2026-08-08, status `proposed`). Not a new CR, not a harness design.
Its job is to say what has to be true for the bands in `06` to get filled honestly,
and to carry the gates that stop us from filling them dishonestly.

CR157 already specifies the capture table, the weekend batch and the post-mortem.
This file supplies the four things it was missing: **the targets to score against**
(`06`), **the controls**, **the estimators**, and **the power gate**.

---

## 1. Capture — three additions to CR157's `room_run_conclusions`

CR157 proposes recording reference price, trader levels, and per-agent stance. Add:

| Field | Why |
|---|---|
| `prompt_version` (CR158) | A rate spanning two prompt generations measures the mix, not the model. Partition by this, **never by date** — CR157's own reconstruction note flags this and it is the error that put a wrong 18.4% into CR143. |
| `mandate_regime` | Different single-name caps produce different APPROVE rates for reasons unrelated to judgement. The CR153/CR156 lesson. |
| `level_provenance` (already on `Verdict`) | Minted levels are constants, not forecasts (`06` M3a). Without this the target-hit rate is uninterpretable. |

## 2. Reuse — build almost nothing

| Need | Already exists |
|---|---|
| Forward returns from a spot snapshot | `backend/scripts/room_benchmark_report.py` — `--forward` / `forward_section()` (line 329). Written for CR035, **never run as a product loop.** |
| Street consensus arm | `backend/scripts/room_consensus.py` |
| Price history | `market_data.py` → `CachingProvider`. No new provider (CR157's own constraint). |
| Benchmark universe | `docs/forward_planning/CR035_room_benchmark/tickers_150.txt` (CR041) |
| Process metrics | `backend/scripts/prompt_quality_sweep.py` (CR143) — already computes stance entropy, provenance, role identifiability |

The genuinely new work is the **rubric scorer** for `05` §6 and the **controls**
below.

## 3. Controls — the part that decides whether any of it means anything

Three arms must run alongside every scored batch. Without them a hit rate is
uninterpretable (`00` §6 — the base rate moved 33 points between consecutive
quarters of 2025).

1. **Same-window SPY.** The benchmark return over the identical window.
2. **Random-pick control.** N tickers drawn from the same 150-ticker universe over
   the identical window. **This measures the base rate on our universe in our
   window** rather than importing a constant. It is the single most important
   control here and the cheapest to run — no LLM calls at all.
3. **Street consensus arm.** Already available via `room_consensus.py`.

A fourth is not optional so much as overdue: **the same ticker convened twice**, to
re-measure the flip rate on the current prompt generation. CR035's ~12% rests on
**4 flips in 32 paired runs**, a 95% CI of **[1.0%, 24.0%]** — wide enough that we
do not currently know whether the instrument is nearly deterministic or flips a
quarter of its verdicts. Every outcome metric is uninterpretable until that
interval narrows, and 100 paired runs would cost less than one scoring sweep.

## 4. Estimators

Per horizon **1w / 1m / 3m / 6m / 12m**, plus the Room's own `time_horizon_days`:

| Metric | Estimator | Notes |
|---|---|---|
| M1 hit rate | share of APPROVE/MODIFY names beating SPY | denominator = acted verdicts only |
| M1 companion | **full excess-return distribution** — median, quartiles, both tails | mandatory; `00` §5 forbids a bare hit rate |
| M3a target | met-at-end **and** touched-during, per Bradshaw-Brown-Huang | **partition by `level_provenance`** |
| M3a error | mean absolute target error; target-implied vs actual return | comparable to the 45% / +15% baselines |
| M3b direction | vs reference price at convene | both fixed grid and stated horizon |
| M3c Brier | on the PM's stated confidence | **blocked — see §6** |
| M4 rubric | `05` §6 Report Card, per convene | no market data needed |
| Abstention | forward return of PASS names vs APPROVE names | the selectivity test |

## 5. The power gate — non-negotiable

Adopt as a rule, not a guideline:

> **No cell is reported without its n and its 95% confidence interval.**
> **No cell is described as an edge unless the interval excludes the base rate.**
> **No claim leaves the building below the n in `06`.**

At n = 150 the interval on a 37% rate is ±7.7 points. Most effects we care about
are narrower than that. Reporting a point estimate without the interval is how a
noisy instrument becomes a confident false claim — the exact failure class
`CLAUDE.md` calls *degrade loudly*, applied to measurement.

**Log what was dropped.** If a batch scores only tickers with clean price history,
say how many were dropped and why. Silent truncation reads as full coverage.

## 6. Two blockers worth filing

1. **No confidence field on `Verdict`.** Verified: no `confidence` anywhere in
   `backend/app/schemas/room.py`. M3c calibration is unmeasurable at any sample
   size until the PM emits a structured numeric confidence. This is the cheapest
   high-value addition in the whole study — it unlocks Brier scoring, which is the
   lane where the comparator (`03`: systematically overconfident retail) is
   weakest.
2. **DEF235** — CR143's M4 was unmeasurable. Already filed; the `05` §6 rubric is
   a candidate replacement instrument.

## 7. Sequencing — cheapest and most informative first

| # | Experiment | Cost | Answers |
|---|---|---|---|
| 1 | **Consensus-ablation re-run** on the corrected Room | ~150 convenes, **no forward prices** | Is the Room reasoning or parroting? CR035's arms B/C ran on a Room with DEF066/DEF067 live and were never honestly re-run. |
| 2 | **Rubric scorer** over the existing CR143 corpus | no new convenes at all | Fills `06` M4 today |
| 3 | **Random-pick control** over `tickers_150` | no LLM calls | Establishes the real base rate; makes every later M1 number interpretable |
| 4 | **Noise-floor re-measurement** — ~100 paired identical convenes | < one scoring sweep, **no forward prices** | Narrows the [1%, 24%] interval. Every outcome metric is uninterpretable until it does. |
| 5 | **Confidence field** + Brier scoring | small backend change | Unblocks M3c |
| 6 | **Target-hit scoring** at n≈189 | one sweep + a quarter's wait | The head-to-head in `06` M3a |
| 7 | M1 hit rate | n≈783 | Probably never decisive |

Note that **experiments 1–4 need no forward prices and no waiting**, and two of
them need no new convenes at all. The instinct on reading `06` is to go start
collecting returns; the cheaper and more informative moves are all upstream of
that.

---

Next: [`08_what_we_can_and_cannot_claim.md`](08_what_we_can_and_cannot_claim.md).
