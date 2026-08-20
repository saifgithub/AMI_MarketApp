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
| Predecessor | `r70-outcome-1` — **VOID**, all 450 verdicts were the DEF059 outage fail-safe |
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

_Pending — sweep in flight._
