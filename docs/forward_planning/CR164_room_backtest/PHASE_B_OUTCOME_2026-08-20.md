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

## Results

_Pending — sweep in flight._
