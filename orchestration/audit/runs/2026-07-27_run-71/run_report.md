<!--
Auditor run report — run-71 (2026-07-27, session auditor.core/track U). Round-1
audit of DEF120. Audited SHA cec80c9. Verdict AWAITING_FIXES — one MAJOR
(reproduced). Owner: AUDITOR.
-->

# run-71 (round 1) — DEF120 portfolio/trade blocking I/O → AWAITING_FIXES

- **Auditor session:** auditor.core (track U), 2026-07-27.

**Item:** the portfolio/trade half of the MVP blocking-I/O show-stopper. `SimEngine`'s valuation and
trade-execution methods call `self.current_quote` synchronously and internally, so the blocking call
never appears at the route — which is why DEF116's re-derived call-site table missed the class
entirely. Nine handlers park the one event loop.

**Gate:** independent — touches trade execution and portfolio valuation, and the fix moves
DB-writing code onto a worker thread.

**Audited SHA:** `cec80c9`, off `main` @ `dd57fef`. Isolated worktree
`.claude/worktrees/audit-DEF120/`, own venv.

**Placement note:** this lane was also submitted to `orchestration/audit/def/` and was invisible for
the same reason DEF114 was — both were moved into `cr/` (`2bad8a3`, `ac39e06`) after I raised it on
DEF114. My finding recovered two lanes, not one.

## Round 1

### Reproduced independently

| Check | Result |
|---|---|
| Scope | 10 files, **+390/−83**, exact match |
| Full suite | **1370 passed** in 216s, clean tree, `__pycache__` cleared, run to completion before any mutation. Baseline 1366 + 4 new — matches |
| **D2** — no asyncio in the engine fetch path | `asyncio` appears in `sim_engine.py` only as **two docstring mentions explaining why not**; no import, no call |
| **D7** — Room files untouched | **0** files matching `room_runner`/`room_prompts` |
| **D5** — waiver emptied | 9 names → **1** (`_build_room_sector_context`); `_DEF120_KNOWN_BLOCKING_PAIRS` empty |
| New leaf coverage | the diff adds 3 engine methods; the 2 that reach the network (`portfolio_marks_snapshot`, `valuation_snapshot`) are both in the leaf set, and `_aggregate_source_from_quotes` is a static helper over already-fetched quotes — correctly absent |

**The empty pin set is genuinely correct — measured, not assumed.** Ran the walk with
`waived=set()`: **0 offender pairs**. So the lane's claim that the walker cannot see the
`_build_room_sector_context` pair *even with zero waivers* holds, and the empty set is not hiding a
visible pair. I verified the remainder is nonetheless real: `_build_room_sector_context(user_id)` is
still called synchronously at `room_runner.py:1912` from inside async `run()`. **DEF120 does not
close the show-stopper on its own** — exactly as the lane states, and I confirm it rather than take
it on trust.

**Acceptance 8 — the thread hop is safe, verified structurally, not just by the ASGI test.**
`submit()` opens and closes its own session internally (`with get_session() as s:`), and what crosses
the thread boundary is `SubmitResult`/`SimTrade` — plain types defined in `sim_engine.py`, not the
ORM `SimTradeRow` in `models.py`. Nothing detached can be touched on the loop thread after the worker
returns.

**The fan-out is correct.** `_marks_with_quotes` uses a plain `ThreadPoolExecutor` bounded at
`min(len(unique), 10)`, deduped and context-managed. The D2 reasoning is verifiable, not
hand-waving: `run_in_executor` requires a running loop and a `to_thread` worker has none, so copying
`quotes_batch`'s pattern really would have exploded under D1.

### Acceptance 6(a) re-proved with my own variant

Un-`to_thread`'d a **different** route from the Architect's (`portfolio.py::sector_allocation`'s
`portfolio_marks_snapshot`) → **2 failed**. The realistic regression shape is caught.

### A probe I ran, and why it is NOT a finding — recording the retraction

I re-ran my own DEF116 round-1 MAJOR mutation (a fresh `self.current_news("AAPL", 1)` inside
`SimEngine.submit`), expecting the guard to catch it now that `submit` is unwaived. It stayed
**green** — and that is **correct**, not a blind spot. I checked every engine entry point:
`sim.preview` (`sim.py:210`), `sim.submit` (`:263`), `sim.evaluate_outcomes` (`:383`),
`sim.manual_close` (`:438`) are **all** now `await asyncio.to_thread(...)`. A blocking call added
inside an already-offloaded method runs on the worker thread and does not park the event loop, so it
is not this defect's class at all. My initial read was wrong; recording it so a later round does not
rediscover it as a finding.

### MAJOR — the fix converted the engine surface from a walk into a name allowlist

The guard now catches *"a route calls the engine synchronously"* (proved above). It does **not**
catch *"a new engine method reaches the network and is called synchronously from a route."*

Reproduced, with an explicit vacuity check that the mutation really landed:

```python
# sim_engine.py:439  — a new engine method, network-bound via the fan-out
def audit_probe_snapshot(self, user_id):
    return self._marks_with_quotes(["AAPL"])

# portfolio.py:63    — called DIRECTLY from the async sector_allocation route, no to_thread
sim.audit_probe_snapshot(user_id)
```

→ guard **7 passed, green**. That is a genuine, un-offloaded, network-bound call on the event loop
from a live route — the exact MVP show-stopper class — reported clean.

**Why the chain breaks:** `_marks_with_quotes` hands `current_quote` to `pool.map` **by reference**,
so the walker cannot see the leaf through it (the same by-reference invisibility that makes the
*correct* `to_thread(leaf, arg)` shape invisible). Neither `_marks_with_quotes` nor the new method is
in `_BLOCKING_LEAF_METHOD_NAMES`, so every hop is blind.

**This already happened once, inside this lane.** The worker's own disclosure is the evidence:
acceptance 6(a) did not go red the first time, because the fix introduced `portfolio_marks_snapshot`
and `valuation_snapshot` — new leaf names the guard did not know — and *the fix silently widened the
guard's blind spot*. The worker found it, added the two names, re-proved red, and reported it. That
was the right response to the symptom, but the remedy was to extend the allowlist, so the mechanism
survives intact and the next engine method reopens it.

**Recommended fix, cheap and local.** The exposed surface is one class in one file, so this needs no
cross-module type resolution: walk `sim_engine.py` alone and assert every public `SimEngine` method
that transitively reaches `_marks_with_quotes` / `current_quote` is either in
`_BLOCKING_LEAF_METHOD_NAMES` or on an explicit, justified exclusion list. Deny-by-default — a new
engine method must argue its way out, rather than being silently unprotected.

I am scoring this MAJOR on the same basis I used for DEF116 round 1 and CR104: it is fail-open on the
exact class the item exists to close, it is reproduced rather than reasoned, a cheap structural fix
exists, and — unlike those two — it has *already recurred once within this lane*, which is the
strongest available evidence that it will recur again.

### Also recorded, not scored

- **Thread budget under load.** Each `_marks_with_quotes` call creates a pool of up to 10 threads,
  and it is called from inside a `to_thread` worker. A burst of concurrent portfolio requests
  multiplies (to_thread pool) × (10 per call). Strictly better than parking the loop, and the 60s
  cache collapses most of it — but it is a real characteristic for the post-promote smoke, which the
  lane correctly lists as unmeasured.
- The Architect's contrived lambda-indirection probe that did not fire is **correctly** not a defect
  — passing a leaf by reference through a helper is invisible by construction, the same way the
  correct shape is. I did not re-run it; recording that I agree with the negative result.

### Not verified — as the lane discloses

- **Concurrency under real load** — nothing exercised against a running server; Mac is a pure editor
  and `main` is under a promotion hold. The latency evidence is a stubbed-provider unit measurement.
- **The 60s cache assumption in production** — read from `market_data.py`, not measured against live
  traffic.
- **Two simultaneous writers through the thread hop** — acceptance 8 proves one request round-trips.
  I confirmed the session/return-type shape makes it structurally sound, but neither of us has run
  concurrent writers.

### Findings

1. **MAJOR** — a new `SimEngine` method that reaches the network via `_marks_with_quotes` and is
   called directly from an async route is invisible to the guard (reproduced: `audit_probe_snapshot`
   called from `sector_allocation` → 7 passed). The by-reference `pool.map` breaks the walk, and the
   remedy applied to the same problem during this lane was to extend the leaf allowlist by two names,
   leaving the mechanism intact. Fix: a single-file deny-by-default assertion over `SimEngine`.

### Verdict

**VERDICT: AWAITING_FIXES (round 1)** — one MAJOR. (Round 1 is the round *audited*.)

The fix itself is good work and I could not fault it: the fan-out is the right primitive for the
right reason, the thread hop is structurally safe, the four N-ticker passes collapse to one snapshot,
D2/D5/D7 all hold, and the empty pin set is genuinely empty rather than quietly waived — which is the
property DEF116's round-3 fix was built to guarantee, now paying off. The lane's disclosure is also
the best of the day: it says plainly that an empty pin set is a blind spot rather than a clean bill,
and that DEF120 does not close the show-stopper on its own.

The MAJOR is that the fix's own shape severed the walker's reach into the engine, and the response
was to name the two methods that broke rather than to close the mechanism. One file, one assertion.

