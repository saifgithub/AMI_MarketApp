# 01 — Where the divergence actually comes from

## The two runs

Two real IBM Room convenes exist in the live `room_runs` table, both from
2026-09-25, ~78 seconds apart, triggered by two different users:

| | Run A | Run B |
|---|---|---|
| `room_run_id` | `7fd1a30c-20d0-44ba-b647-aca5d77b12de` | `1707ad92-0afd-42f1-a6f7-d81a70da6619` |
| `user_id` | `8f1e288a-b288-4b9e-942f-2003b88ba555` | `d00000f5-c311-4f4e-b94f-cc1b56cdedbc` |
| triggered | 17:02:18Z | 17:03:36Z |
| `model_tier` | premium | mid |
| mandate version | 5 | 1 |
| verdict | PASS, 0/5 approve votes | PASS, 0/5 approve votes |
| reference price | $225.78 | $225.77 |

The verdict itself agreed (PASS, 0/5 votes both). What differed was the reasoning
text and which numbers each agent's response led with.

## Pulling the real prompts

`backend/scripts/ibm_room_divergence_probe.py` reads the `llm_audit` table
(`system_prompt`, `messages`, `response_text` — every LLM gateway call is captured
here, per `LLMAuditRow`, [backend/app/db/models.py](../../../backend/app/db/models.py))
for both users' calls in the trigger window, and diffs each agent's prompt A-vs-B.
Full output: [`out/01_original_two_runs_diff.json`](out/01_original_two_runs_diff.json).

## What the diff actually shows

**The market-data fact sheet is effectively identical between the two runs.**
Price differs by 1¢ ($225.79 vs $225.77 — live-quote jitter across the 78-second
gap, not a caching bug), one volume figure differs by ~5k shares, everything else —
P/E, margins, FCF, the 20-day and 200-day SMAs, analyst targets, catalysts — is
byte-for-byte the same. `backend/app/services/market_data.py`'s `CachingProvider`
serves quotes from a shared in-process cache (60s TTL), consistent with two calls
78 seconds apart mostly hitting the same cached values.

**What genuinely differs is per-user context**, injected into every agent's prompt
unconditionally (CR055):

- **Mandate**: max drawdown 50% vs 30%, single-name cap 100% vs 3%, sector cap 100%
  vs 40%, post-loss cooldown off vs 1h, trading pace 10/50 vs 4/12 per day/week, total
  open-risk cap 60% vs 10.5%.
- **Portfolio**: Run A's user holds APA/GGG/NFLX/NVDA plus a linked Alpaca paper
  account; Run B's user has an empty $10,000 simulated account.

This is the expected, by-design behavior of `_build_sim_holdings_block`,
`_build_room_sector_context`, `_build_room_risk_limit_context`
([backend/app/services/room_runner.py](../../../backend/app/services/room_runner.py))
— two different users are never supposed to see the same prompt.

## The part that is not explained by per-user context

Replaying **Run A's exact captured `fundamentals_analyst` prompt** — same system
prompt, same single user turn, sent to the same vLLM endpoint a second time — came
back with a different stance:

| | Run A original | Replay of Run A's exact prompt |
|---|---|---|
| STANCE | for | neutral |
| CONVICTION | medium | low |
| HEADLINE | "6.2% FCF yield vs 17% op margin" | "1% growth, 16% net margin" |

Same prompt, same model, sent twice, different conclusion — on demand, the same day.
This is the phenomenon [CR214](../../forward_planning/CR214_room_edge_test/) already
measured in aggregate (a ~12–20% verdict-flip rate across repeated identical
convenes, per that CR's own writeup and a separate, earlier measurement in
[CR035](../../forward_planning/CR035_room_benchmark/)); this is that same effect
reproduced concretely, on this one real case, with the raw before/after text
sitting next to it.

## Why: no sampling control is set anywhere

`backend/app/services/llm_gateway.py`'s `OpenAICompatibleProvider.stream_chat`
builds the vLLM request body from `model`, `messages`, `max_tokens`, `stream` —
grepping the whole file for `temperature` returns zero hits. No `seed` either.
vLLM's own server-side default sampling temperature applies to every Room call in
production, unpinned. `pm_self_consistency_samples=5`
([backend/app/core/config.py](../../../backend/app/core/config.py)) exists
specifically to vote this noise down at the final PM verdict step — and in both
original runs, it worked (both landed on PASS despite the underlying instability one
level down, at the individual analyst-agent layer).

## What this rules in and out

- **Not a market-data bug.** The fact sheet is stable across the 78-second gap.
- **Not (primarily) a per-user personalization bug.** Mandate and portfolio
  differences are real, intended, and account for most of the observable
  difference between Run A and Run B specifically.
- **Is a real, reproducible sampling-noise effect**, on the individual analyst-agent
  layer, that the PM's 5-sample vote absorbs at the very top of the pipeline but
  does nothing to fix underneath — every other agent's single-shot output (the ones
  earlier agents in the pipeline read as "prior context") is exactly as unstable as
  the replay above shows.

The rest of this research digs into how big that instability actually is, across
temperature and across two independent model providers.
