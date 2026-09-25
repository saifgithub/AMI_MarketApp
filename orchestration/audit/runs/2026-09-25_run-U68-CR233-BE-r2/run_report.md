<!--
run_report.md: auditor run report for CR233-BE round 2 (U68), plus the DEF416 post-COMPLETE
glance. It holds the evidence behind orchestration/audit/cr/CR233-BE.auditor.md and the note
appended to DEF416.auditor.md.
-->

# 2026-09-25: CR233-BE round 2 and the DEF416 glance (auditor U68)

**SHA audited:** CR233-BE fix `472905e8` and DEF416 fix `c082e4dd`, both merged at `main` `b065b4ba`.

| Lane | Verdict | Counts |
|---|---|---|
| CR233-BE | `COMPLETE` (round 2) | 0 BLOCKER, 0 MAJOR, 1 MINOR |
| DEF416 | glance only; round 1's `COMPLETE` stands | 1 MINOR, recorded |

**Where the probes ran:** TestClient over the real sim router, sqlite tempfile, in the scratch
worktree at `b065b4ba`. Mock mark 408.14.

## CR233-BE probes

| Probe | Result |
|---|---|
| P1 AMI path, BUY STOP trigger 4.08, $30k at mark | preview refused 300.0% = submit refused 300.0% |
| P2 snapshot path, BUY STOP trigger 4.08, cap 10% | refused 30.0%, identical to MARKET |
| P3 snapshot path, BUY STOP_LIMIT 412.22/816.28 | sized at 816.28, refused 17.8% |
| Sell-to-open stop-limits, `long_only` OFF (P4–P6) | cap sized at the limit; preview then refuses every sell-to-open ("not enough held"); AMI `/submit` rests it at the limit basis |
| Marketable STOP_LIMIT through its limit, AMI `/submit` | BUY limit 387.73 filled 408.14; SELL limit 428.55 filled 408.14 (pre-existing, recorded) |
| Mutation: marketable STOP sized at its trigger | 5 failed |
| Mutation: resting STOP_LIMIT sized at its trigger | 4 failed |
| Lane files + `test_sim_engine` + `test_def419` + `test_safety_floor` | 104 passed, EXIT=0 |

## DEF416 glance

| Check | Result |
|---|---|
| `test_def416_oidc_unique_race.py` | 8 passed |
| Mutation: remove the lost-race re-key and adoption block, both providers | 8 passed (unpinned, MINOR) |

## Full suite

Full unit suite at `b065b4ba`, run as 3 melehost shards plus the 5 git-dependent files on the Mac.

- **Totals:** 6929 passed, 9 skipped, 3 failed.
- **2 are the DEF417 blocking-I/O guard.** They are deterministic.
- **1 is `test_cr077_phase_parallelism`.** It is a timing flake and passes when run alone.

FOREIGN: not run.
