<!--
Auditor run report — run-67 (2026-07-27, session auditor.core/track U). Round-2
audit of CR098-ROOM. Audited SHA 73dbcce. Verdict AWAITING_FIXES — one MAJOR
(the unguarded half of the merge hazard flagged in round 1). Owner: AUDITOR.
-->

# run-67 (round 2) — CR098-ROOM analyst pull-back → AWAITING_FIXES

- **Auditor session:** auditor.core (track U), 2026-07-27.
- **Audited SHA:** `73dbcce` on `lane/CR098-ROOM.coder.room`, rebased onto `main` past DEF116,
  DEF121 and DEF122. Isolated worktree `.claude/worktrees/audit-CR098-r2/`, own venv.
- **Scope vs `main`:** 16 files, **+1288/−44**. Backend code delta confined to the expected files
  (`api/room.py +13`, `room_prompts.py`, `room_runner.py`, `entitlements.py`, `core/config.py`,
  `news_context.py`, `schemas/room.py`, `docker-compose.yml`, 3 agent content files) — no strays.
- **Full suite: 1365 passed** in 215s on a verified-clean tree (`git status --short` → 0),
  matching the Architect's re-measure exactly.
- **Provenance:** the worker was clean this round — six incremental commits, one per finding,
  $7.64 of a $15 cap, and it re-ran my two mutations itself. First lane worker in ~28h to finish
  without Architect recovery. **But the Architect states plainly they did *not* re-run the
  worker's five fixes' mutations — those are self-reports.** So I ran all five myself.

## All five round-1 findings closed — verified with my own mutations

Run verbatim from round 1, `__pycache__` cleared between every step (the hand-off warns this
external volume's coarse mtime can mask an edit — a real methodological trap, worth heeding).

| Round-1 finding | My mutation | Result |
|---|---|---|
| **MAJOR 1** — `agent_withheld` never reaches the wire | deleted the new `elif ev.kind == "agent_withheld"` branch from `room.py`'s dispatcher | **RED** — `test_agent_withheld_reaches_the_sse_wire` |
| **MAJOR 2a** — withheld analyst not proven absent | `phase_agents = phase.agents` | **RED** (undetected at 1359 in round 1) |
| **MAJOR 2b** — emit-order misattribution | `zip(phase.agents, results)` | **RED** (undetected at 1359 in round 1) |
| **MINOR 1** — respawn feeds ungated | un-gated the respawn news fallback | **RED** — `test_respawn_path_gates_feed_fallback_by_roster` |
| **MINOR 2** — #2's test didn't test #2 | dropped `threshold >= 1` (0 stops meaning "never") | **RED in `test_default_roster_is_full_no_op` itself** — no longer only incidentally via the money test |
| **MINOR 3** — contradictory scaffolding header | restored the unconditional header line | **RED** |

Two things worth calling out rather than just ticking:

- **MAJOR 1's test is the right shape.** It drives a real request through the FastAPI route and
  `StreamingResponse`, splits the SSE body, and JSON-parses the `agent_withheld` frame's payload —
  asserting the *wire*, not that the runner emitted an event. That is the distinction the finding
  was about.
- **MAJOR 2's test is sharper than what I asked for.** It withholds **News** (3rd of 4) rather than
  the last slot, because withholding the tail makes the correct and the buggy `zip` coincide on
  every surviving pair. That detail decides whether the test catches misattribution at all, and the
  worker found it unprompted.

**D6 seam, re-checked as the Architect asked.** The merged call site carries **both**
`await asyncio.to_thread(...)` **and** `withheld=frozenset(roster.withheld)` — the exact resolution
I specified when I measured the hazard in round 1. Restoring the inline blocking call turns
DEF116's guard **RED**, naming `backend/app/api/room.py:stream_room -> _profile_for_ticker` and
`-> yf.Ticker`. That direction is genuinely protected.

Also re-verified while here: `spend()` still has exactly two textual call sites on mutually
exclusive branches inside `_resolve_and_charge_feeds` — CR090-ROOM's D1 intact, no second debit.

## MAJOR — the merge hazard's *other* direction is still unguarded, and I measured it

Round 1's FLAG 1 recorded **two** ways a keep-both merge of this seam goes wrong. DEF116's guard
covers one (losing the `to_thread` hoist). I wrote then that the other — **losing `withheld=` while
keeping the hoist** — is "caught by nothing." It still is.

Dropped `withheld=frozenset(roster.withheld)` from the hoisted call and measured against the
**full** suite, not just the CR098 file:

```
CR098 file      : 24 passed
DEF116 guard    :  3 passed
FULL SUITE      : 1365 passed
```

**What that regression does in production.** `_profile_for_ticker` receives an empty `withheld`, so
the Market gate never fires: `compute_technicals(ticker)` runs — the yfinance OHLCV pull the roster
gate exists to bank — and `technicals_state` is never set to `withheld_tenure`. `_format_profile`
then renders **real RSI, trend, volume and recent range for a withheld Market analyst**, which is
the Amendment 1 / acceptance #6 rule this CR exists to enforce. On a `NO_VERDICT` run the output is
directly self-contradicting: the PM refuses because *"this session ran without a market read"* while
the fact sheet in every agent's prompt contains a full market read.

**Why nothing catches it.** Every #6 and fetch-gating test calls `_profile_for_ticker` or
`_format_profile` **directly**, with an explicit `withheld=` argument. None exercises the
`run()` → `_profile_for_ticker` wiring. That is precisely round-1 MAJOR 2's shape — tests asserting
*around* the mechanism instead of *through* it — one layer further out, on a call site **three
lanes have now collided on** (CR090 → DEF116 → CR098) and which I measured git auto-resolving
silently in exactly this harmful direction (round 1's trial merge took DEF116's hoist *without*
CR098's kwarg, with no conflict marker).

**Severity.** Same call as round-1 MAJOR 2, for the same reasons, applied consistently: it is
fail-open (the withhold *appears* to work — analyst silent, event emitted, verdict lists it — while
the withheld domain's real data renders in every agent's prompt), it has zero coverage across 1365
tests, and the seam is about to be disturbed again by DEF120 and the two CR098-MOBILE lanes. The
code as submitted is correct; the wiring that keeps it correct is unpinned. Round-1 MAJOR 2 was the
same "correct code, untested mechanism" shape and the fix it forced caught two real regressions in
my probes above.

**Fix is one assertion:** drive `run()` with a Market-withheld roster and assert the rendered
profile carries `technicals_state == "withheld_tenure"` — or that `compute_technicals` is never
called on that path.

## Out of lane — DEF122 closed my DEF116 round-3 MINOR with the wrong reason

`_KNOWN_SYNC_HTTPX_COUNTS` now groups `app/services/room_runner.py` with
`app/services/revenuecat_client.py` under *"both called from a sync `def` context (FastAPI runs
those in a threadpool), so they do not park the event loop — the CR049 distinction."*

That is **not true of `room_runner.py`.** `log_prefix_cache_status()`'s `httpx.get(url,
timeout=5.0)` (now `:2764`) is reached first from `main.py:132` —
`await get_room_runner().resume_pending_retries()` inside `async def lifespan` — i.e. **directly on
the event loop**, not through a threadpooled `Depends`. Verified in this worktree.

It remains safe, for a different reason: it fires **once per process during lifespan startup**,
before uvicorn serves traffic, guarded by `_PREFIX_CACHE_STATUS_LOGGED`. My DEF116 round-3 finding
was a pin with *no* stated reason; it now carries a *wrong* one, which is worse — a reader could
add a second httpx call to that module on the same false premise. Architect's call (DEF122 landed
on `main`, outside this lane); the correct reason is the paragraph above.

## Also confirmed closed — both infra items I flagged

- **DEF121** fixed the watcher/dispatch prose-parsing defect I raised: a token now counts only when
  it *opens* a line, plus `BAD_ROUND` as a loud state when `VERDICT round > SUBMITTED round`. The
  full-corpus regression (61 dispatch + 60 audit lanes, boards diffed before/after) produced exactly
  one change — DEF116 `SUBMITTED` r2 → r3, the bug — and caught a regression in its own first patch.
- **DEF122** re-keyed the httpx inventory from `file:line` to `file + count`, closing the
  brittleness I recorded as "noted, not scored" in run-66. It fired for real: CR098's rebase moved
  an untouched call `:2618` → `:2764` and the old pin called it a new blocking site.

## Not verified

- **Acceptance #14 live smoke** — untestable from a pure-editor Mac. Post-promote.
- **DEF098 parity blind spot** — still out of scope, still needs an Architect decision on whether a
  withheld analyst counts as a declared omission for a degraded `FLOOR_PASS`.
- **The mobile half** (`CR098-MOBILE-LIVE`, `CR098-MOBILE-VERDICT`) is written and `UNASSIGNED`,
  deliberately held on this verdict.

## Findings

1. **MAJOR** — nothing pins the `roster → _profile_for_ticker` wiring. Dropping `withheld=` from the
   hoisted `to_thread` call leaves the **full suite at 1365 passed**, while a withheld Market
   analyst's real technicals render in every agent's prompt and contradict the `NO_VERDICT` copy.
   The other half of the same merge hazard is guarded by DEF116's AST guard; this half is not.

## Verdict

**VERDICT: AWAITING_FIXES (round 2)** — one MAJOR. (Round 2 is the round *audited*, per
`PROTOCOL.md`; the architect bumps to `SUBMITTED: round 3`.)

The worker's round was clean and every one of its self-reports checks out under my own probes —
and its MAJOR 2 test is better than the one I specified. The remaining MAJOR is the second
direction of the hazard I flagged in round 1, now measured rather than predicted, and it is the
same class as round-1 MAJOR 2: correct code, unpinned wiring, on the one call site three lanes keep
colliding on. One assertion closes it.
