# The CR214 sweep is blocked on GPU contention, not on our code

**Date:** 2026-09-01 ~02:20 UTC · **Status:** sweep halted at pair 54/700, deliberately

## What happened

The sweep stopped itself. Three consecutive DEF059 fail-safe verdicts tripped
`--max-consecutive-outages 3`, and every layer below it did its job:

```
ABORTED: 3 consecutive LLM-outage fail-safe verdicts — the provider is down…
=== SHARD 1 exit rc=3 · DEF336 outage abort — NOT retrying ===
=== HALT at shard 1 (rc=3) — not advancing ===
```

That is the guard working. It is the opposite of `r70-outcome-1`, which spent a
whole night recording 450 outages as decisions because nothing checked.

## Two separate causes, and only one of them was ours

**Ours (DEF390, fixed):** `_AGENT_LLM_TIMEOUT_S = 90.0` was a hardcoded module
constant, so CR211's model swap never prompted a re-check. Measured from
`llm_audit` over 6h of real convenes: the `portfolio_manager` runs 7,041 input /
277 output tokens at a **42.4s mean**, mode 35-40s, tail to 85s — and **21 of
290 calls piled into the 90-95s bucket**, which is the cap clipping the
distribution, not a mode. ~7% of PM calls were being killed, and because
`pm_self_consistency_samples=5` issues the draws concurrently, a contended host
pushes all five over together (observed: five `room_pm_timeout` lines 4ms apart).
Raised to 180s, made a setting, transport raised 180→360 to keep DEF389's
ordering. **This alone would have been enough at the throughput measured earlier
in the night.**

**Not ours (the actual blocker):** the vLLM host's throughput then collapsed.

| measurement | time | result |
|---|---|---|
| PM-shaped, 3,809 tok prompt | ~01:00 | **14.0s**, 20.7 tok/s |
| 2-token request | ~02:05 | **105.1s** |
| PM-shaped, 3,113 tok prompt | ~02:15 | **277.4s**, 1.3 tok/s |

A ~15x collapse. No timeout we could reasonably set survives a PM call taking
277s, so raising the budget further is not the answer.

## It is co-tenant contention, and the discriminator is the port

`192.168.20.74` runs two vLLM serves of the same model. Measured minutes apart:

| endpoint | 2-token call |
|---|---|
| `:8000` | **114.0s** |
| `:8048` (ours) | **0.4s** |

`:8048`'s own scheduler is idle throughout — `kv_cache_usage_perc` 0.12-0.19,
`num_requests_waiting` 0, `num_preemptions_total` 0. So the bottleneck is not
vLLM's queue, not KV memory, and not our concurrency: it is **GPU time consumed
by the co-resident serve on `:8000`**. When that one is busy, ours crawls, and
the 0.4s reading above is simply a 2-token request slipping through a gap.

Note this also revises the earlier reading of the 8-shard incident. Saturating
`max_num_seqs` was real, but a second serve competing for the same GPUs was
present the whole time and was never in the picture.

## What is needed

**A decision on the box, which is Saiful's.** Options, in rough order of cost:

1. Find out what `:8000` is serving and whether it needs to run concurrently.
   If it is idle-but-loaded by an old workload, stopping it frees the GPU.
2. If both serves must coexist, the sweep should be scheduled around the other
   workload rather than run continuously.
3. `max_num_seqs` on `:8048` remains worth raising — at the 8-shard overload
   everything queued under `reason="capacity"` while KV sat at 0.36 — but that
   is a throughput ceiling, not this.

**Nothing to change on our side.** DEF390 is promoted; `ROOM_AGENT_TIMEOUT_S` is
now an env knob, so the budget can be retuned without a code change if the host's
steady-state throughput turns out to be permanently lower.

## Resume recipe

The batch halted cleanly and is resumable by `(batch, ticker, as_of)` identity.
`r74c-out-s1` holds 4 indexed fail-safes that will be skipped as
`already_indexed`, so resume under a **fresh batch-id** (`r74d-out-s*`) to
re-run those pairs:

```bash
ssh -f melehost 'cd ~/ami_trade && setsid nohup bash backend/scripts/supervisors/run_sequential.sh 1 >/dev/null 2>&1 </dev/null'
```

Before resuming, confirm the host is actually serving: a PM-shaped call
(~3-4k prompt, ~300 completion tokens) against `:8048` should return in **under
20s**. At 200s+ the sweep will only manufacture fail-safes again.
