# Outage census — every CR164 batch, run backwards through DEF336's recogniser

**2026-08-31 (AT:R74, DEF386).** DEF336's `is_llm_outage_verdict` was written on 2026-08-20,
*after* several of these batches were measured and written up, and nothing had ever re-run the
older ones through it. This is that pass. It is the general form of the DEF386 lesson: **a
detector built in response to an incident must be run backwards over the data that predates
it** — the incident is evidence the failure was already happening.

| batch | n | outage | % | window (UTC) | |
|:--|--:|--:|--:|:--|:--|
| `r70-outcome-2` | 450 | 0 | 0% | 2026-08-20 06:55 .. 08-21 10:20 | clean |
| `r70-outcome-1` | 450 | 450 | **100%** | 2026-08-19 20:06 .. 08-20 04:57 | **VOID** (known) |
| `pit-pilot-2` | 130 | 0 | 0% | 2026-08-10 22:22 .. 08-11 04:52 | clean |
| `r70-paired-1` | 126 | 67 | **53%** | 2026-08-19 15:13 .. 19:54 | **WITHDRAWN** (DEF386, new) |
| `r68-def230-n40` | 40 | 0 | 0% | 2026-08-12 13:39 .. 16:07 | clean |
| `pit-pilot-1` | 30 | 0 | 0% | 2026-08-10 20:52 .. 22:18 | clean |
| `r68-postfix` | 26 | 0 | 0% | 2026-08-11 22:32 .. 08-12 00:07 | clean |
| `r68-postbatch9` | 26 | 0 | 0% | 2026-08-11 15:41 .. 17:18 | clean |
| `pit-pilot-2-repeat` | 20 | 0 | 0% | 2026-08-11 04:54 .. 05:51 | clean |
| `r74-flipbase2-cr214` | 5 | 0 | 0% | 2026-08-31 11:22 .. | clean, in flight |
| `r74-flipbase-cr214` | 5 | 0 | 0% | 2026-08-31 11:04 .. 11:22 | clean, superseded |
| `r70-smoke-2` | 2 | 0 | 0% | 2026-08-20 06:44 .. 06:48 | clean |
| `pit-smoke-1` | 1 | 0 | 0% | 2026-08-10 20:48 | clean |

## What it establishes

**Exactly two batches are affected, and they are adjacent in time.** The outage is bounded to
**2026-08-19 ~15:13 → 2026-08-20 ~04:57**: it begins partway into `r70-paired-1`, runs at 53%
through the rest of that batch, and is total across `r70-outcome-1`. `r70-smoke-2` at 06:44 the
next morning is already clean, which is consistent with `PHASE_B_OUTCOME`'s pre-flight smoke
test being run precisely to establish that.

**Nothing else in the corpus is touched.** In particular:

- **`r70-outcome-2` is 0 of 450.** The batch carrying the 13-week horizon finding
  ([FINDING_2026-08-31_horizon.md](../CR214_room_edge_test/FINDING_2026-08-31_horizon.md)) is
  clean, and that result does not depend on any withdrawn data.
- **`pit-pilot-2` is 0 of 130.** The pilot stands.
- The CR143/CR179/CR197/CR199 ablation batches are not in `backtest_run_index` (they are live
  runs, not as-of runs) and are outside this census. They ran 2026-08-07..14, i.e. well before
  the outage window, but that is an inference from timestamps rather than a measurement here.

## The gap that let a 53% outage run to completion

`backtest_sweep.py`'s DEF336 abort fires on **three CONSECUTIVE** outage verdicts (exit 3). A
53% intermittent outage evades that indefinitely — the probability of three in a row is high per
attempt, but the sweep only needs one non-outage run to reset the counter, and at 53% it got
plenty. `r70-outcome-1` tripped the guard only because it was 100%.

**A rate-based abort is the missing control**, and it is the one worth adding: the failure mode
that hurt here was not the total outage (which was obvious and was caught) but the partial one,
which produced a plausible-looking mixture and was written up as a result.
