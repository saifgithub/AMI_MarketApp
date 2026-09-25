<!--
run_report.md: auditor run report for DEF417 round 2 (U68). It holds the evidence behind
orchestration/audit/cr/DEF417.auditor.md.
-->

# 2026-09-25: DEF417 round 2 (auditor U68)

**SHA audited:** the worker's merge `26481d44`, plus the Architect's follow-up `937d75f8`. The
lane files are identical at `b065b4ba`, where the full suite ran. **Verdict:** `AWAITING_FIXES`,
with 0 BLOCKER, 1 MAJOR and 1 MINOR.

**How it ran:**
- **Stack:** a throwaway melehost stack (`audit_u68_q_*`: API on the HEAD tree, its own Postgres
  and Redis) with `CLASSIFICATION_SCREEN_ENABLED=true` and a stored snapshot.
- **Yahoo:** live lookups ran from a throwaway container.
- **Live DB:** read with SELECTs only (`ticker_reference`, `room_runs`).
- **Cleanup:** everything was removed at the end.

| Probe | Result |
|---|---|
| GNS, real `/v1/sim/preview` + `/submit`, `liquid_only` ON | refused: "$30M market cap is below AMI's $500M microcap floor" |
| SNDL, same | refused: "$345M market cap …" |
| MSFT, same | accepted, `liquidity=permitted` |
| 40 non-S&P tradables from `ticker_reference`, real lookup with a price | microcaps refused, mid and large caps permitted; residue: warrants and `$`-preferreds UNKNOWN (3 of 40), 2 LOOKUP_FAILED per run |
| CCXIW (warrant), real preview | accepted, `liquidity=unknown`, `advisories=[]` (MINOR-1) |
| Cold-lookup latency | 0.75–3.72s against the 4.0s bound |
| Mutation: live-PM site `room_runner.py:5944`, universe → None | 1 failed |
| Mutation: `fill_resting_order` `sim_engine.py:1983` ignores the universe | 1 failed |
| `test_def417_liquid_only_enforcement.py` | 39 passed, EXIT=0 |
| Full unit suite at `b065b4ba` (3 melehost shards + 5 git-dependent files on the Mac) | 6929 passed, 9 skipped, 3 failed |
| `test_no_blocking_io_in_async_routes.py`, both tests | deterministic failures (they still fail when the file runs alone): `stream_room` / `start_backtest_room_run` → `resolve_liquidity_with_lookup` → `yf.Ticker` (MAJOR-3) |
| `test_cr077_phase_parallelism` | timing flake; passes when run alone |
| Live Room durations, last 14 days (read-only) | median 313s, p90 347s; 52 of 72 runs over the 5-minute cache on a failed lookup |

FOREIGN: not run.
