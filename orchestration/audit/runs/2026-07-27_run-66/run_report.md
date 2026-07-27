<!--
Auditor run report — run-66 (2026-07-27, session auditor.core/track U). Round-3
audit of DEF116 (the lane's 2nd round of coder work — round numbers are offset
on this lane). Audited SHA c866a6f. Verdict COMPLETE. Owner: AUDITOR.
-->

# run-66 (round 3) — DEF116 guard fixes → COMPLETE

- **Auditor session:** auditor.core (track U), 2026-07-27.
- **Audited SHA:** `c866a6f` on `lane/DEF116.coder.api`. Isolated worktree
  `.claude/worktrees/audit-DEF116-r2/`, own venv.
- **Round numbering:** this is the lane's **2nd round of coder work** but carries the token
  **round 3** — round 1's verdict was stamped with the round *requested* rather than the round
  *audited* (my error), which left `SUBMITTED == VERDICT` and deadlocked the lane. The Architect
  bumped an extra round to break it and `PROTOCOL.md` now states the rule explicitly (`7c37dda`).
  The offset is permanent on this lane.
- **Scope:** `git diff d68a028 c866a6f --stat` → **1 file, +151/−38, the test file only**. No
  production code touched — consistent with round 1 finding nothing wrong with the fix itself.
- **Full suite: 1335 passed** in 180s (round 1 was 1333; `+2` = exactly the two new tests).

> **Discarded measurement, stated rather than buried:** my first suite run overlapped the probe
> battery, which was mutating and reverting `backend/app/` underneath it. That number was
> meaningless, so I killed it and re-ran on a tree verified clean (`git status --short` → 0). The
> 1335 above is the clean run.

## All three round-1 findings closed — re-verified with my own probes, not the hand-off's

The hand-off states each fix was proved using my round-1 probes. I re-ran them myself rather than
accept that; every mutation reverted individually, guard re-confirmed green after each.

| Round-1 finding | My probe, verbatim | Result |
|---|---|---|
| **MAJOR** — waiver pruned the subtree by bare name | fresh `self.current_news("AAPL", 1)` injected into waived `SimEngine.submit`, reachable from `POST /sim/trade` | **RED** — `sim.py:submit_trade -> <obj>.current_news` |
| **MINOR** — inverted `to_thread` exemption | P-E: `await asyncio.to_thread(sim.current_quote(ticker))` | **RED in 2 tests** |
| **MINOR** — Alpaca held by a comment | a brand-new `httpx.get(...)` added to `fundamentals.py` | **RED**, naming the new site |

Two checks nobody asked for:

- **Bidirectionality.** Wrapped `portfolio.py`'s `sim.current_marks` in `to_thread` — i.e. *fixed*
  a pinned offender — and the stale-set assertion went **RED**. The pin is genuinely two-way, so a
  partial DEF120 fix cannot silently leave the set masking the remainder. This matters more than
  it looks: the one-way version would let a DEF120 lane shrink the real offender set while the pin
  kept blessing the rest.
- **No new false positives from deleting `_to_thread_wrapped_call_ids`.** The correct shape passes
  the leaf by **reference** (`ast.Name`/`ast.Attribute`, never `ast.Call`), so it is invisible to
  `_blocking_call_sites` — evidenced by the baseline staying green with five correct `to_thread`
  call sites live in `sim.py` / `agent_runner.py` / `room_runner.py`.

And the structural property that makes the whole fix work: the companion runs with `waived=set()`,
so it is **waiver-independent**. Adding a name to `_WAIVED_CALL_CHAIN_NAMES` can no longer widen
the blind spot — which was the actual mechanism behind round 1's MAJOR.

## The Architect's correction to my recommendation — they are right, I was wrong

My round-1 fix recommendation was to pin the offending **route** set. They built it that way,
measured that it misses my own mutation, and switched the key to `route -> leaf`.

I did not take that on trust. Re-applied my mutation and computed both pins from the module's own
machinery:

```
route-level pin  : GREEN   <- misses the mutation
leaf-level  pin  : RED
```

`submit_trade` was already in the 9-route set, so a route-level pin could never have caught a new
leaf reached from it. Their key is strictly better than what I asked for, and the correction was
worth the round.

## Their open question, answered by measurement: yes, leaf granularity is too coarse for that case

They asked whether a second distinct blocking site of the **same leaf on the same route** slips
through, said they chose the coarser key deliberately, and asked me to say if I disagreed.

Constructed the case rather than reasoning about it: added `self.current_quote("ZZZZ")` inside the
waived `evaluate_outcomes`, reaching `evaluate_trades -> <obj>.current_quote` — a pair already
pinned. Result: **3 passed, undetected.** The gap is real, exactly as suspected.

**I still agree with the coarser key**, for a reason worth stating rather than just concurring:

- While DEF120 is open, those 9 routes already park the event loop. An additional blocking call on
  an already-blocking route changes nothing operationally — there is no state in which the hole
  costs anything.
- When DEF120 closes, `_DEF120_KNOWN_BLOCKING_PAIRS` must shrink to empty — and the bidirectional
  assertion *forces* that, as probed above. After it does, every pair is new and caught.
- The alternative (keying on the full `(via …)` chain) trades that zero-impact window for churn on
  every harmless refactor of an intermediate hop.

The hole exists only in the window where it cannot matter. Correct call.

## One MINOR — a pinned site with no stated reason

`_KNOWN_SYNC_HTTPX_SITES` annotates three of its four entries with why they are accepted.
`app/services/room_runner.py:2618` carries none.

Ran it down rather than assuming it was fine: it is `log_prefix_cache_status()`'s
`httpx.get(url, timeout=5.0)`, reached from `get_room_runner()`. It is genuinely safe — but **not**
for the reason its RevenueCat neighbour gives (sync `def` route → threadpool). It is reached first
from `main.py:132` (`await get_room_runner().resume_pending_retries()`) inside the **async lifespan
startup**, before uvicorn serves traffic, and `_PREFIX_CACHE_STATUS_LOGGED` makes it fire once per
process — so the later `Depends(get_room_runner)` calls never probe. It blocks the loop for up to
5s at startup with no request in flight.

Round 1's MAJOR was a *claim* in a comment that did not hold; an entry carrying *no* claim is a
milder form of the same problem — a future reader cannot tell whether it was analysed or swept in,
which is precisely the property this inventory exists to provide. One comment line fixes it; the
paragraph above is the content.

*Noted, not scored:* the inventory is keyed by `file:lineno`, so an edit above a pinned line turns
it red for a non-reason. Fail-**closed** (a moved site lands in both `added` and `removed`), so
noisy at worst, never silent.

## Infra defect found while picking this lane up — the watcher could not see it

`watcher.sh:38` resolves the submitted round with `last_round … 'SUBMITTED: *round *[0-9]+'` — the
**last** match in the file. `DEF116.architect.md:138` contains the literal string
`SUBMITTED: round 2` inside the blockquote *documenting the round-offset fix*, so the watcher reads
**2** instead of the real **3** at line 8. `SUBMITTED(2) == VERDICT(2)` ⇒ the lane renders
`AWAITING_FIXES` and this genuine round-3 submission was **invisible to the auditor watcher**. I
found it only by reading `git log` directly after the state table looked wrong.

The prose describing the deadlock re-created the deadlock. Any lane file that quotes the token in
narrative text is now silently unqueueable. Architect's call to mint an ID; the fix is to anchor
the pattern (`^SUBMITTED: *round *[0-9]+`) so prose and blockquotes cannot shadow the real token.
Lane file is architect-owned — flagged, not touched.

## Findings

1. **MINOR** — `_KNOWN_SYNC_HTTPX_SITES` pins `room_runner.py:2618` with no stated reason while its
   three siblings carry one. Verified safe (async-lifespan startup, once per process, before
   traffic); needs the annotation so the accepted set stays auditable.

## Verdict

**VERDICT: COMPLETE (round 3)** — zero BLOCKER, zero MAJOR.

Every round-1 finding is closed, each re-proved with my own probe rather than the hand-off's, plus
a bidirectionality probe and a false-positive check nobody asked for. The Architect's pushback on
my recommended fix was correct, and I verified their measurement rather than deferring to it.
Their open question is answered with a reproduction showing the gap is real, and the tradeoff still
right. One MINOR (a missing annotation), not blocking.
