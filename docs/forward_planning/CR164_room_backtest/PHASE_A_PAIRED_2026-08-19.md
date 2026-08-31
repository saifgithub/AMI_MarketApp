# CR164 Phase A — the rebuilt Room against the pilot, same 126 pairs

> ## ⛔ WITHDRAWN 2026-08-31 — this batch is 53% LLM-outage fail-safes (DEF386)
>
> **Every measured claim below is withdrawn.** Re-running `r70-paired-1` through DEF336's
> `is_llm_outage_verdict` recogniser finds **67 of its 126 verdicts (53%)** carrying the DEF059
> sentinel reason verbatim — the provider was dead and no agent ruled. `backtest_report.py`
> now refuses the batch outright (exit 4). The recogniser returns **0%** on `pit-pilot-2`
> (n=130) and **0%** on `r70-outcome-2` (n=450), and it is an exact match against a
> module-level constant, so this is not over-matching.
>
> **The timeline recorded in §"Phase B is VOID" below is wrong.** It says the provider *"went
> down at 20:05 UTC and stayed down"*, and `PHASE_B_OUTCOME_2026-08-20.md:19` says the vLLM
> *"died in the 11 minutes between batches"*. Measured `finished_at` says Phase A ran
> **15:13:53 → 19:54:41 UTC** and was already half-dead inside that window. **The outage began
> during THIS batch, at least four hours before 20:05.** It was diagnosed from its effect on
> `r70-outcome-1` — 450 of 450, impossible to miss — and the batch it was already corrupting at
> 53% was never re-examined, because a partial outage produces a plausible mixture rather than
> an absurd one.
>
> **Why the numbers cannot be salvaged by simply noting the caveat.** The damage is not
> uniform. The 67 outage rows all land in the PASS bucket, so the PASS leg stops being a
> *rejection* set and becomes approximately a random-name average — which silently converts
> `APPROVE − PASS` from "approved vs rejected" into "approved vs roughly the market", and
> flatters it. And the verdict-stability comparison against the pilot (112/126, 88.9%) — **the
> entire reason this batch exists** — was matching up to half its pairs against runs with no
> model in them.
>
> Specifically withdrawn: APPROVE 9/126 (7.1%) · 4w excess APPROVE **+6.13%** vs PASS +0.71% ·
> spread **+5.43%**, CI −1.48…+13.69 · P&L **+4.44%**, win rate 5/9 · stability **88.9%** ·
> and the conclusion *"the rebuilt Room is better on every measure taken"*, which the data does
> not support.
>
> **The 59 clean runs are not a smaller Phase A.** The outage did not fall randomly across the
> pair plan, and a 59-run subset of a 126-pair *paired* design is no longer paired. Treat this
> batch as withdrawn, not as a reduced version of itself.
>
> **`pit-pilot-2` (0% outage) and `r70-outcome-2` (0% outage) are unaffected** and remain valid
> for the model they measured — see [DEF385](../../defect/_registry/DEF385.row.md) on which
> model that was.
>
> **The lesson worth keeping:** DEF336's recogniser was written on 2026-08-20, the day *after*
> this batch was measured and written up, and nothing re-ran the older batches through it. **A
> detector built in response to an incident must be run backwards over the data that predates
> it** — the incident is evidence the failure was already happening, and the batch nearest in
> time is the likeliest other victim.


Batch `r70-paired-1`, 2026-08-19, tag `alpha-2026-08-19-2`. Replays every pair
`pit-pilot-2` completed, so sampling is held constant and nothing here turns on
which names were drawn. **126/126 completed, zero failures.**

## Read this before the numbers

**Two things changed at once, and this comparison cannot separate them.**
Between the pilot and today, ten batches of prompt work landed (29 commits, 8
promotions) — and separately, Phase 0 of this re-run took the historical fact
sheet from 14 emitted fields to 45. The rebuilt Room is both better instructed
*and* better informed. Any improvement below is the pair of them together. A
clean attribution would need a third arm holding the fact sheet at 14 fields,
which was not run and is not planned: the 14-field sheet was a defect, not a
condition worth preserving for science.

**Leakage: clean.** 1,514 audit rows across 126 runs, **0 hard fails, 0
correlation failures**. The 278 price flags are the known coincidence class —
a 2-decimal close that recurs days later — and they rose from the pilot's 156
only because the sheet now carries three times as many numbers.

## What is settled, and needs no statistics

**The horizon defect is gone.** The pilot's approvals carried horizons of 19,
26, 47, 90, 90, 145, 201, **730, 900, 1095, 1095, 1095, 1095** days — six of
thirteen over a year, four at exactly three years, which DEF255 showed was the
mandate's "3–10 years" label restated as a trade horizon. The rebuilt Room's
nine approvals: **33, 47, 90, 90, 90, 120, 120, 180, 180**. Nothing over 180
days. Zero approvals reached the >365-day coherence check, so the check never
had to fire — the contract sentence alone moved the behaviour, and the
deterministic control remains as the backstop for when it does not.

**Every approval carries PM-stated levels.** 9 of 9 with entry, stop and target
all provenance `pm`; no minted `ami_default` anywhere.

**The Room's decisions are stable.** 112 of 126 verdicts unchanged (88.9%);
14 flipped (11.1%) — indistinguishable from the ~12% same-config noise floor
CR035 measured. Ten batches of prompt surgery did not scramble the Room.

## What moved, but is not significant

| | pilot | rebuilt |
|---|---|---|
| APPROVE rate | 13/126 (10.3%) | 9/126 (7.1%) |
| 4w excess vs SPY, APPROVE | +4.83% | **+6.13%** |
| 4w excess vs SPY, PASS | +0.72% | +0.71% |
| APPROVE − PASS spread (4w excess) | +4.11% | **+5.43%** |
| date-clustered 95% CI on the spread | −5.05% … +14.63% | **−1.48% … +13.69%** |
| followed-the-trade P&L | +1.48% of book | **+4.44%** |
| trade win rate | 4/12 (33%) | **5/9 (56%)** |
| first touch: target vs stop | 2 vs 5 | **3 vs 3** |

McNemar on the paired APPROVE flips (9 lost, 5 gained): **p = 0.424**. The
random-pick null: **p = 0.625** — and on this batch that null is degenerate
anyway, since replaying the pilot's pairs preserves its 1–2 tickers per date.
Fixing that is the whole point of Phase B.

**The spread's interval still crosses zero**, though by much less than the
pilot's (−1.5 points versus −5.1). That is progress in precision, not a result.

**One name still carries the P&L.** KSS returned +106% and contributed $3,185
of the $4,436. Strip it and the book is +$1,251 (+1.25%) on eight trades —
which is the honest headline. It is, however, a real improvement in *shape*:
the pilot's book without its best trade was **−$622**. The rebuilt Room is
positive without its outlier; the pilot was not.

**The stop geometry stopped fighting the horizon.** Pilot first-touch was 2
targets to 5 stops with 6 neither; rebuilt is 3 to 3 with 3 neither. Consistent
with DEF255's diagnosis — shorter, evidenced horizons and the same stop
distances no longer guarantee the stop arrives first. On n=9 this is a
direction, not a measurement.

## Honest summary

The rebuilt Room is better on every measure taken, and **not one of those
measures clears significance at n=9 approvals**. What genuinely improved is
structural and needs no p-value: horizons are now evidence-sized, levels are
all PM-stated, the fact sheet carries 45 fields instead of 14, and the
decision set is stable under a large prompt rewrite. Whether the approvals
carry outcome edge is a question 126 pairs and 9 approvals cannot answer, and
is what `r70-outcome-1` — 450 convenes over 18 dates, 25 tickers each — is
running to address.

Artifacts: `results/runs_r70-paired-1.jsonl`, `report_r70-paired-1.md`,
`trade_pnl_r70-paired-1.md`, `scored_r70-paired-1.jsonl`,
`prompt_scan_r70-paired-1.md`.

---

## Phase B (`r70-outcome-1`) is VOID — do not score it

Ran 2026-08-19 20:05 → 2026-08-20 04:57 UTC. **All 450 verdicts are the DEF059
LLM-outage fail-safe**, not decisions: the on-prem vLLM died in the eleven
minutes between the paired batch finishing (19:54 UTC) and this one starting
(20:05 UTC), and stayed down. The host `192.168.20.74` is currently unreachable
— 100% packet loss, port 8000 closed.

The batch reported "450 completed, 0 failed" because an outage fail-safe IS a
completed run carrying a PASS verdict. That blind spot is now closed at three
layers (**DEF336**): the sentinel is a named constant with a recogniser, the
sweep aborts after 3 consecutive outage verdicts, and the report refuses any
batch more than 5% outage.

Two cheap tells that would have caught it sooner, worth keeping in mind for
any future sweep: 0 approvals of 450 against the paired batch's 7.1% is a
~1e-15 event, and 450 runs in 8.9 h is 71 s each against a measured 155 s —
a failing convene fails fast.

**The outcome question remains unanswered.** Re-run the same 450-pair plan
(`pairs_r70-outcome-1.jsonl`, unchanged and still valid) under a fresh
batch-id once the provider is healthy.
