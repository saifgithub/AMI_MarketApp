# Sweep supervisors

The host-side half of the DEF387 guard.

`backtest_sweep.py` refuses to run unless `AMI_SWEEP_SUPERVISOR` is set
(`_require_supervisor()`), because a bare launch dies with its ssh channel or
its exec pipe and leaves no traceback, no non-zero exit and no final log line —
DEF345 and DEF387, 2h54m and 2h49m of undetected idle GPU three weeks apart.
These scripts are what sets it, so **the guard and its enabling half must ship
together.**

They live here rather than in `backtest_results/` for exactly that reason.
`backtest_results/` is a `rw` bind mount and is excluded from the promotion
rsync as host-generated runtime data (DEF276), so anything kept there is on one
disk, unversioned, and invisible to review. A guard whose enabling half can
vanish with a disk is not a guard.

| script | what it does |
|---|---|
| `supervise_shard.sh N` | one shard: relaunches the resumable sweep across exec death, up to 200 attempts. Exit 0 = shard complete, 3 = DEF336 outage abort (**never retried**) |
| `run_sequential.sh [first]` | runs shards `first..8` **one at a time**, halting rather than advancing on any non-zero shard exit |
| `supervise_cr214.sh`, `supervise_outcome2.sh` | single-batch equivalents for earlier CR164/CR214 batches |

## Running one

Always detached, always under `setsid` — a backgrounded ssh command dies with
the channel, which is the mistake DEF387 records:

```bash
ssh -f melehost 'cd ~/ami_trade && setsid nohup bash backend/scripts/supervisors/run_sequential.sh 1 >/dev/null 2>&1 </dev/null'
```

## Watching one

**Silence is not success.** A monitor filtered on progress lines stays quiet
through a crash, a hang and a clean death alike, and that silence reads as
"running" — it did, for three hours, across three status reports. Watch for the
failure states: supervisor absent, log staleness against a ~250-300s convene,
`ABORTED`, `REFUSING`, and any `LLM OUTAGE FAIL-SAFE`.

## Sequential vs parallel

`run_sequential.sh` exists because an 8-way fan-out saturated the vLLM host on
2026-08-31: every request queued under `reason="capacity"` while
`kv_cache_usage_perc` sat at 0.36, i.e. the ceiling was `max_num_seqs`, not
memory. The shard split is still the right *coverage* design — each shard is a
stride-8 sample of the window's Fridays, so a completed shard is 6-7 dates
spread evenly across the whole window rather than a contiguous block, and
partial progress stays unbiased in time. What changed is that exactly one
supervisor runs at a time. `backtest_sweep.py` is itself strictly serial, so
one supervisor is one convene in flight.
