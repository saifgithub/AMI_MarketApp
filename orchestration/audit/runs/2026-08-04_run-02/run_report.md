# Audit run 2026-08-04 run-02 — CR136-M01, round 1

Auditor track U. First audit of M01, the root of CR136's dependency graph —
four of its consumers (M02, M05, M06, M09) are already closed, so a finding here
is a finding under them.

Audited at **`c56e2c41`** in detached worktree `.claude/worktrees/audit-m01r1`.

Verdict: **AWAITING_FIXES (round 1)** — zero BLOCKER, **2 MAJOR**, 2 non-gating
MINOR. Findings in `orchestration/audit/cr/CR136-M01.auditor.md`.

## Drift check

Of the declared files, `price_history.py`, its migration, `market_data.py` and
`test_cr136_price_history.py` are **unchanged** between `c56e2c41` and today's
`main`. Only `models.py` (M07's journal index) and
`portfolio_health_constants.py` (DEF213's `GRID_DENSITY_MAX`) moved, both
outside this lane per the seam register. Auditing at the submitted SHA is sound.

## MAJOR A1 — `fetch_failed` answers for one caller in 360

`_FETCH_FRESH_WINDOW_S` is **21600 s = 6 hours**, and the fetch-attempt stamp is
written before the network call. Feed down, successive card opens:

```text
 t (mins)  dates  fetch_failed   caller concludes
        0      0          True   our feed is down     <- correct
        1      0         False   this security is young
      359      0         False   this security is young
      361      0          True   our feed is down     <- window expires
```

Two further paths report `False` on a feed problem: a sibling throttled by an
in-flight attempt (0 dates), and a partially-garbage fetch (200 bars served, 160
NaN → 40 dates). Only "this call produced nothing at all" sets the flag.

Lands at `portfolio_health.py:279`, which picks `FEED_UNAVAILABLE_DROP_REASON`
from `daily.fetch_failed` — so the holding drops as `short_history`. The
constant's own comment names the defect verbatim: *"telling a user 'not enough
price history for this holding' when the truth is 'our feed is down' is the
wrong answer to the question that rule asks."*

MAJOR not BLOCKER: the card renders a degraded state, not a confident wrong
number. The user gets the wrong reason for a correct refusal.

## MAJOR A2 — attack 1 is real; no exception handling on the write path

Mechanism proven deterministically, then end to end through the real function
with the check-then-set window widened by a barrier:

```text
B reads 0 rows -> will INSERT;  A commits 30
B flushes: sqlalchemy.exc.IntegrityError
           UNIQUE constraint failed: price_history_daily.ticker, ...date
price_history.py mentions IntegrityError: False   imports sqlalchemy.exc: False

real get_daily_series, 2 threads, widened window:
  thread 1 -> 200 dates
  thread 0 -> RAISED sqlalchemy.exc.IntegrityError
```

Propagates to the tiles route, whose docstring commits to never 5xx.

**Reachability measured, and narrower than the submission claims.** 60 trials,
two threads off a barrier, cold ticker, no patching: **0/60** both-fetch, 0
exceptions. The window is `_build_series` plus a session commit — milliseconds,
but one thread wins every time at this concurrency. "Both fetch on promote day"
is not what one process does.

It is what two do. `_last_fetch_attempt` is per-process, the Dockerfile runs one
uvicorn with no `--workers`, and CLAUDE.md's Beta stack is **Cloud Run** — where
instances share no dict and the throttle stops protecting the constraint. Every
evaluation fetches SPY.

MAJOR: zero error handling on a concurrent write path, M03 in this same CR
already carries the fix (`portfolio_snapshot.py:192`), and CLAUDE.md's
second-occurrence rule applies (`043995b0` was the first).

## MINOR m1 — attack 4 confirmed exactly as predicted

```text
replace_foreign_rows=source != _MOCK_SOURCE -> == _MOCK_SOURCE   37 passed
argument deleted entirely (defaults True)                        37 passed
```

Unpinned in both directions. `upsert_daily_bars` rewrites `close`, `adj_close`,
`source`, `fetched_at` in place — so an inverted flag in a mock run destroys real
history *and* stamps it `mock-walk`, after which the real-mode read filter makes
it invisible. Destroyed and hidden by two correct mechanisms cooperating. MINOR
because the code is right today and no live path runs mock against real data.

## MINOR m2 — attack 6 measured

```text
robust_daily_sigma = 0.00000000
bound = max(15.0*sigma, 0.10) = 0.1000        <- collapses to the floor
genuine +12% move, 65% next-day retrace -> flagged [100]
```

MAD is exactly 0 whenever >50% of returns are 0 — ordinary for a thin name.
Graded MINOR because the flag is not clearly *wrong* on an illiquid security;
what is wrong is that the volatility-scaled bound degrades to a fixed 10% rule
for exactly the names it was meant to adapt to, and §2.8's calibration (12
liquid large-caps and ETFs) cannot contain a MAD=0 name by construction.

## Attack 7 — confirmed, not a finding

```text
garbage at index 0 -> flagged [1]   (0 in flags? False, 1 in flags? True)
NaN at index 0     -> flagged [1]
```

Caught transitively, holding still drops. His reasoning holds.

## The calibration he cited but did not run — I ran it; it holds

```text
k=10.0  ->  TOTAL FALSE FIRES ON CLEAN REAL DATA: 1   (XLU, COVID window)
k=15.0  ->  TOTAL FALSE FIRES ON CLEAN REAL DATA: 0
```

**Shipped constant verified.** The script's default candidate is k=10 and that
fire is the evidence for rejecting k=10, not a problem with what ships.

Drift note only: the binding XLU move now measures 12.4σ vs the cited 11.0σ
(adjusted closes get reprocessed), so headroom to k=15 is **21%**, not the 36%
the module doc states. Still safe; the documented margin is a third smaller.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| `test_cr136_price_history.py` | 37 | **37 passed, 1.80s** | exact |
| full `tests/unit/` | 2269 | **2269 passed, 280.19s** | exact |
| QA-A…D | 1 failed each | **1 failed each, names checked** | match |

2269 independently corroborated by the M07 round-1 audit of the same tree.

Bookkeeping: §4 names QA-B's kill as
`test_non_positive_and_non_finite_prints_are_flagged`; it is
`test_unusable_provider_closes_are_refused_at_the_door`. Both exist, the guard
is genuinely killed, the label is wrong.

## Round 2 scope

A1 and A2 only. A1 needs a regression test that a *second* caller inside the
throttle window is still told the feed failed — no current fixture makes two
calls. A2 wants the M03 pattern plus a `failure_patterns.md` entry with a guard.

## Probes preserved

`m01_mut.sh`, `m01_concurrency2.py`, `m01_probe3.py`, `m01_calib.txt`,
`m01_calib15.txt`.
