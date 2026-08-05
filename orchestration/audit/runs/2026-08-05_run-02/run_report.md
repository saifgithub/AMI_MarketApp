# Audit run 2026-08-05 run-02 — CR136-M01, round 2

Auditor track U. Round 1 returned 2 MAJOR; scope for this round was A1 and A2
only. Both fixed.

Audited at **`64d1e1a1`** in detached worktree `.claude/worktrees/audit-m01r2`.

Verdict: **COMPLETE (round 2)** — zero BLOCKER, zero MAJOR, 2 non-gating MINOR.
**Lane closed.** Findings in `orchestration/audit/cr/CR136-M01.auditor.md`.

## A1 — re-measured on the round-1 table, not on the new tests

```text
 t (mins)  dates  fetch_failed        round 1
        0      0          True   ->   True
        1      0          True   ->   False
       30      0          True   ->   False
      120      0          True   ->   False
      359      0          True   ->   False
      361      0          True   ->   True
```

The counter-case holds — a clean 20-bar IPO stays `fetch_failed=False` at
t=0/1/200, so the distinction A1 is about survives its own fix. Partial garbage
(200 served, 160 NaN) reads True; recovery clears the flag; no cross-ticker leak.

## A2 — including the case the patch shape could have missed

```text
(a) IntegrityError raised at the upsert call site   returned normally
(b) two real threads past the throttle              200/200 dates, 0 escaping
(c) `with get_session()` is INSIDE the try          True
```

(c) matters: the raise can come from the session's **commit** in `__exit__`, not
from the call. A patch wrapping only the call would look identical and catch
nothing on Postgres.

## Mutations — his 5 re-performed, 3 added

```text
MUT-1  2 failed (reported 2)     AUD-M1 sticky read ungated   46 passed SURVIVED
MUT-2  2 failed (reported 1)     AUD-M2 pessimistic pre-set    1 failed
MUT-3  1 failed (reported 1)     AUD-M3 ticker_reference       1 failed
MUT-4  2 failed (reported 1)
MUT-5  1 failed (reported 1)
```

5/5 killed. MUT-2 and MUT-4 each kill two, not one — guards stronger than
reported. MUT-4's second kill is the new P15 guard firing on `price_history.py`;
AUD-M3 fires it on `ticker_reference.py`. The guard genuinely guards.

## MINOR m3 — P15 enforces a naming convention, not the pattern

```text
AUD-M4  check-then-SELECT-then-add under a unique constraint,
        no handler, not named upsert_*        3 passed  (guard blind)
```

Docstring says "every check-then-INSERT under a unique constraint"; the AST
filter is `func.id.startswith("upsert_")`, parametrizing over two files.
`journal_store.append_unique` is the same shape and invisible to the scan — it
happens to be handled at `:157`, so nothing is broken today. MINOR because P15 is
now the durable `failure_patterns.md` entry and the sentence is what gets trusted.

## MINOR m4 — a smaller `min_days` caller clears the sticky flag

```text
A min_days=126 t=0    (fetch)      fetch_failed=True
B min_days=20  t=400  (fetch)      fetch_failed=False, flag cleared
A min_days=126 t=401  (throttled)  fetch_failed=False   <- A1, reopened
```

Latent: `get_daily_series` has one origin call site
(`portfolio_health.py:773`, `min_days=T_MIN + 1`). Live the day a second
consumer asks for a shorter window.

## Measured and not graded

A1's inverse exists in the rule — a short security with one unusable close reads
as a feed failure (125 days + 1 NaN → `fetch_failed=True`). Trigger rate on the
provider that actually serves this system:

```text
17 tickers x 2y live Yahoo, 8,534 bars — unusable closes: 0, tickers with >=1: 0/17
```

So `rejected` is inert against this provider, which also means attack 3 is the
theoretical path while paths 1 and 2 are the live ones.

AUD-M1 survived; traced rather than assumed — `fetch_failed` has exactly one
consumer (`portfolio_health.py:780`), reaching a dropped holding's reason and
`bench_feed_failed`, so an over-set flag on a full series reaches nothing.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| module + P15 suites | — | **46 passed, 2.15s** | — |
| full `tests/unit/` | 2313 | **2313 passed, 285.07s** | exact |

## Probes preserved

`m01r2_a1.py`, `m01r2_a2.py`, `m01r2_a2b.py`, `m01r2_mut.sh`.
