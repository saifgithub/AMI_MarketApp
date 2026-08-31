# CR164 Phase B — does the Room's approval set carry outcome edge?

Batch `r70-outcome-2`, launched 2026-08-20 06:51 UTC, tag `alpha-2026-08-20-2`.
450 convenes: **18 as-of dates × 25 tickers**, replaying the pinned plan
`pairs_r70-outcome-1.jsonl` byte-for-byte. 140 unique tickers drawn from the
142-name split-free universe (DEF335 mitigation).

**This is the arm that can answer the outcome question.** Phase A held sampling
constant to isolate what the prompt work changed, and its 9 approvals cannot
speak to edge. The pilot's random-pick null was degenerate — 1–2 tickers per
date meant "draw a random name from a pool of one", which is why its p=0.025
was disowned. Twenty-five names per date gives the null a real pool.

## Run record

| | |
|---|---|
| Batch | `r70-outcome-2` |
| Predecessor | `r70-outcome-1` — **VOID**, all 450 verdicts were the DEF059 outage fail-safe. **CORRECTION 2026-08-31 (DEF386):** the outage did NOT begin "in the 11 minutes between batches" as stated below — Phase A (`r70-paired-1`, 15:13→19:54 UTC) is itself **53% outage fail-safes** and is [withdrawn](PHASE_A_PAIRED_2026-08-19.md). The provider was already failing hours earlier; only its total failure in `r70-outcome-1` was obvious enough to notice. **Phase B itself is unaffected — 0 of 450.** |
| Provider | on-prem vLLM `ami-llm`, snapshot `e850c696e6d75f965367e816c16bc7dacd955ffa` — unchanged since the cutoff probe, so the 2025-02-28 window start still holds |
| Window | 2025-02-28 .. 2026-07-16 |
| Prices | `price_history_daily` to 2026-08-18, 161 tickers — every date scoreable at +5d and +20d |
| EDGAR | `edgar_facts` 351,139 rows (206,620 before the Phase 0 Tier-3 re-ingest) |
| Universe | `tickers_142_no_splits.txt` |

## Pre-flight, and why it was needed

`r70-outcome-1` reported "450 completed, 0 failed" for a run in which the
provider was dead throughout: an outage fail-safe **is** a completed run
carrying a PASS verdict, so nothing distinguished a dead batch from a decided
one. DEF336 fixed that at three layers. All three were verified present in the
running container before launch, and a 2-pair smoke batch (`r70-smoke-2`) was
run first:

- RBLX@2025-02-28 → APPROVE, 282 s, `is_llm_outage_verdict=False`, 1101-char reason
- AAPL@2025-07-11 → PASS, 218 s, `is_llm_outage_verdict=False`, 769-char reason

Two different verdicts with substantive rationale — the Room is deciding, not
failing safe.

## Confound to declare before reading any Phase A ↔ Phase B comparison

Phase A ran on `alpha-2026-08-19-2`. Phase B runs on `alpha-2026-08-20-2`.
One prompt-byte change landed between them: **CR197** (`feafbad5`, 2026-08-19
23:18 UTC) added a SIZE channel to the RISK stance envelope and rebuilt all
three debator prompts (`aggressive_debator.md`, `conservative_debator.md`,
`neutral_debator.md`) plus `room_prompts.py` and `room_runner.py`.

So Phase B's Room is **not** Phase A's Room. This costs nothing for Phase B's
own question — APPROVE vs PASS vs random-pick is measured entirely within this
batch — but any cross-phase delta (verdict rates, approval rate, convene
duration) carries CR197 as an unseparated cause. Convene wall-clock is already
visibly up (smoke 218–282 s vs Phase A's 64 s median), consistent with the
debators emitting an extra channel.

The other commit in the gap, DEF336 (`dd72fe90`), renamed the outage sentinel
into a constant and added a recogniser. It changes no prompt byte and no
verdict.

## Run interruption, 08:08–11:02 UTC (DEF345)

The sweep stopped dead after 17 of 450 convenes when another lane recreated
`ami_api_alpha`. `docker compose exec` dies with the container: no traceback,
no non-zero exit, no final log line — the log simply ends after a normal
`→ completed action=PASS`. It sat undetected for 2 h 54 m.

**Nothing in the data was wrong, which is why nothing caught it.** All 17
records are valid and were kept: `overridden_from_llm=false` on every one,
convene durations 160–310 s, inter-run gaps 16–34 s. The batch was wrong only
in what was missing, and absence leaves no record. Detection came from
arithmetic — 17 runs across 4 h 08 m is 877 s each against convene durations
that averaged 245 s, so ~10 min per run was unaccounted for.

Three things changed as a result, all committed under DEF345 (`8832c450`):

1. **A completion sentinel.** `backtest_sweep.py` writes
   `complete_<batch-id>.json` (carrying `planned_pairs`, not just `completed`)
   on the line after the loop ends. A killed process cannot write it.
   `backtest_report.py` refuses a batch without one (exit 5, before it touches
   the DB) and stamps **PARTIAL** on any `--allow-partial` report.
2. **A supervisor.** `backtest_results/_supervise_outcome2.sh` relaunches the
   resumable sweep across container recreates. DEF336's outage abort (exit 3)
   is deliberately not retried.
3. **Staging moved off `/tmp`.** A recreate wipes it — that is how the
   interruption was found, both the pairs file and the ticker universe were
   gone.

The sweep resumed at 11:02 UTC and re-indexed the 17 completed pairs as
`already_indexed` (409, the `uq_backtest_run` gate) rather than re-running
them, so no convene was paid for twice and no verdict was overwritten.

**This does not compromise the batch.** Resume is by (batch, ticker, as_of)
identity, the pair plan is pinned and unchanged, and the interruption is
uncorrelated with anything the Room does — it fell on the 18th pair of the
first as-of date because that is when another lane happened to promote.

## Results

Completed 2026-08-21 10:20 UTC. **450 planned, 446 scored, 18 dates, 140 tickers,
0 LLM-outage fail-safes.** The 4 unscored runs were cancelled mid-convene by the
container recreates at 11:43 and 16:17–16:20 (`client disconnected mid-run`);
one further verdict carries `overridden_from_llm=true` and is a **safety-floor**
override, not an outage — `is_llm_outage_verdict` returns False and the reason is
a real analytical rationale, which is the distinction DEF336's test exists to pin.

Artifacts: `results/report_r70-outcome-2.md`,
`results/trade_pnl_r70-outcome-2.md`, `results/prompt_scan_r70-outcome-2.md`,
`results/complete_r70-outcome-2.json`.

### The headline: no outcome edge is demonstrated

40 APPROVE (9.0%) against 406 PASS.

| bucket | 1w excess vs SPY | 4w excess vs SPY |
|---|---|---|
| APPROVE (n=40) | +0.47% | **+1.40%** |
| PASS (n=406) | +0.94% | **+0.25%** |

The 4-week spread is **+1.15%** in the Room's favour, and it does not survive
either test built to break it:

- **Random-pick null, pooled p = 0.3010.** Per date, only 2 of 18 fall below
  p=0.10 (2025-05-09 at 0.057, 2025-08-08 at 0.095). Under a true null you
  expect ~1.8 of 18 below 0.10. That is precisely what chance predicts.
- **Date-clustered CI on the spread: −2.05% to +4.43%**, straddling zero.
  **Effective n = 18 as-of dates**, not 446 runs.

**This is the first properly-powered version of the question.** The pilot's
null drew one name from a pool of one and its p=0.025 was disowned for exactly
that reason; Phase A's 9 approvals could not speak to outcome at all. Twenty-five
names per date across eighteen dates gives the null a real pool, and the answer
it returns is *no detectable edge*. That is a result, not a failed measurement.

### The trade-level view agrees, and adds a warning

Followed-the-trade on the Room's own stated entry, stop, target and horizon:

| fill policy | realized P&L | win rate | mean/trade |
|---|---|---|---|
| limit | +$4,027 (+4.03%) | 21/38 (55%) | +4.73% |
| market | +$3,447 (+3.45%) | 20/39 (51%) | +3.94% |

**One name is 45% of it.** RSI @2025-05-09 returned +51.4% = $1,543 of the
$3,447 market-fill total. Without it: **+$1,904 (+1.90%) on 19/38 wins (50%)** —
a coin flip with a small positive tail. The pilot had the same shape and so did
Phase A; three sweeps running, the aggregate is carried by one or two names.

**Stops are hit more often than targets.** Target hit 10/40 (25.0%), stop hit
15/40 (37.5%); on first touch, 9 target-first against **13 stop-first**, 18
neither.

> **CORRECTION 2026-08-31 (AT:R74).** This paragraph originally continued: *"The
> Room's level-setting places stops closer to harm than targets to gain. That is
> the one finding here pointing at a specific, fixable mechanism, and it is
> invisible in the return means."* **That reading does not survive arithmetic and
> is withdrawn.** Hit counts cannot show a level is misplaced without normalising
> for how far it sits, and this section never measured the distances — though they
> were recoverable the whole time from `results/trade_pnl_r70-outcome-2.md`, which
> shipped in the same batch. On the realized market-fill exits there, mean stop
> distance is **5.12%** (median 4.65%, n=17) against mean target distance
> **13.17%** (median 9.55%, n=17): the Room sets roughly **2.6 : 1** reward-to-risk
> (2.05 : 1 on medians). For a driftless random walk the near level is touched
> first with probability `target/(stop+target)` — **72.0%** on means, **67.3%** on
> medians. **Observed stop-first is 13/22 = 59.1%** (z = −1.35 and −0.82), i.e.
> *below* the random-walk expectation, not above it, and well inside noise either
> way on 22 first-touches. Two harness conventions push the observed figure up
> rather than down — a same-bar stop+target counts as a STOP because daily bars
> cannot order two intraday touches, and a gap through a level fills at the open —
> so 59.1% is an upper bound. **A 37.5%/25.0% split is what a 2.6:1 R:R produces
> mechanically. There is no mechanism here to fix, and no defect was filed.**
>
> Two caveats on the correction itself. The distances come from the **hit-only**
> subsample (17 stops, 17 targets), which is biased toward close levels on both
> legs; the ratio is more robust than either leg, but it is not the full-40
> geometry, and the stated levels for all 40 live in `room_runs` on melehost
> rather than in this folder. And the target/stop counts above are measured over a
> fixed **20-trading-day** window, while the P&L table walks each trade to its own
> stated horizon (median 90 days) — the two are not the same population, which is
> part of why they were not read against each other in the first place.
>
> **What this leaves as a real gap:** `backtest_report.py`'s target/stop section
> prints raw hit counts with no distance normalisation, so the next sweep can
> reproduce the same misreading. Printing mean/median R:R and the random-walk
> first-touch expectation beside the counts is a code change and needs its own ID.

So Phase B leaves **no** finding pointing at a specific, fixable mechanism in the
Room. The actionable output of this batch is the instrumentation work it forced
(DEF336, DEF345, DEF358) and the quantified noise floor in `RETEST_RECIPE.md`.

**APPROVE underperforms PASS at one week** (+0.47% vs +0.94%) before leading at
four. On 40 trades this is well inside noise, but it is the second sweep to show
it and is worth watching rather than explaining away.

### What did hold

- **DEF255's horizon defect stays fixed.** Stated horizons span 19–365 days,
  median 90, and **0 of 40 exceed a year**. The pilot's four 1,095-day approvals
  — the mandate label restated as a thesis — have not returned.
- **Zero leakage.** See the adjudication below.
- **PIT coverage held up across the full universe:** rev_growth 81.4%,
  price_to_sales 75.6%, profit_margin 75.1%, fcf_yield 72.0%, pe 67.0%,
  net_cash 61.9%, dividend_yield 43.9%, ev_to_ebitda 30.7%.

### Leakage adjudication — 7 hard fails and 592 flags, all resolved

`backtest_prompt_scan.py` exited 1. Both classes were run down rather than
waved through, and **correlation failures were 0**, so every audit row is
correctly attributed to its run.

**The 7 hard fails are one run and one sentence.** All seven are CL@2026-06-12,
run `58149372`, and all seven are the same Bull Researcher output —
*"Upside: **$97.97** (52-week high) by **2027-06-12**"* — propagating into six
downstream agents' prompts. The offending date is **a year past as_of and still
in the future today**; no data exists for it. It is the Room stating a thesis
horizon, which is necessarily post-as_of, not data it was fed.

**The 592 flags are arithmetic coincidence, established by permutation.** They
reduce to only **65 distinct (ticker, as_of, price) triples**, each counted once
per agent prompt it reaches. Matched price dates spread near-uniformly across the
scanner's +3..+28-day window rather than clustering at the near edge, which is
where a leaking query would put them. The decisive test: over 120 sampled runs,
the flagged near-future window (+1..+30 d) matched **19** distinct closes, while
a far-future control window (+200..+230 d) — same ticker, same magnitude, equally
unknowable — matched **12**. Real leakage would leave the control at ~0. The
modest excess is expected, since closes 30 days out sit nearer the as_of price
level than closes 200 days out and so collide more often with computed levels
(SMAs, stops, 52-week bounds). Examples bear this out directly: BAC's flagged
41.90 is *"stop 6.0% below entry 44.57"*, and EOG's 121.83 is *"50-day SMA"* —
both computed from pre-as_of bars.

The structural guard is what makes this safe to conclude: `get_asof_daily_rows`
filters `date <= as_of` and re-asserts post-query, raising `AsOfLeakageError`.
It never fired.

### What this does not answer

Stated horizons have a median of 90 days and reach 365; the scoring horizon is
20 trading days. **The four-week numbers grade name selection, not whether these
theses worked.** Nothing here can be read as "the Room's judgement is/is not
profitable over its own stated horizon" — that needs the oldest cohort to age
past its horizon, which for the 2026 dates is 2027.
