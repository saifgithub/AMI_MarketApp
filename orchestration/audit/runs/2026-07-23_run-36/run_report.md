<!--
Auditor run report — run-36 (2026-07-23, session auditor.core/track U). Round-3 audit of CR069-BE
(coder's own doc calls it "round 2" — DEF091's round-counter collision, now fixed). Audited SHA
c2683da on lane/CR069-BE.coder.api. Verdict COMPLETE. Owner: AUDITOR.
-->

# run-36 (round 3) — CR069-BE F2/F3/DEF089/DEF092 fixes → COMPLETE

- **Auditor session:** auditor.core (track U), 2026-07-23. Picked up off the restarted watcher
  (`watcher.sh auditor -i 30 -t 3600`), which returned immediately — the lane was already
  `AWAITING_AUDIT` at `SUBMITTED round 3` when the watcher started.
- **Audited SHA:** `c2683da`, tip of `lane/CR069-BE.coder.api`. Chain: `6b26310` (F2/F3/DEF089
  fixes) → `88776b3` (DEF092 UA fix) → `c2683da` (tests + fixture). Audited in a fresh isolated
  worktree `.claude/worktrees/audit-CR069-BE-r2/`.
- **Why "round 3" not "round 2":** the coder's own hand-off doc calls this "Round 2" (correctly —
  it's their second submission). The auditor lane's round counter reads 3 because my round-2
  self-reopen (no matching architect submission) collided with the coder's later
  `SUBMITTED: round 2`, a genuine state-machine bug the architect diagnosed and fixed same-day as
  DEF091. Not reopening that here — noting it so the round numbering in this file's history makes
  sense against the coder's own doc.
- **The item:** fixes for the two MAJORs from round 2 (F2: staleness dead after process start; F3:
  synchronous fetch blocking the async event loop) plus DEF089 (the iShares parent-index URL
  serving HTML) plus a new defect found mid-fix, DEF092 (SPUS's WAF 403s `python-httpx`/`requests`
  while `curl` passes — both of CR069's two sources turned out to be broken against the client that
  actually ships, discovered only once someone fetched with `httpx` instead of `curl`).
- **depends-on:** none.
- **Verdict:** COMPLETE (round 3) — zero BLOCKER, zero MAJOR. One new MINOR (non-blocking): an
  unguarded check-then-act race on the provider's cache refresh, newly reachable now that F3 routes
  through real thread concurrency. Round 1's resolver correctness reconfirmed untouched, not
  reopened.

---

## What changed since round 2, and how I verified each piece

### F2 — staleness dead after process start

`ShariaUniverseProvider.get()` (`sharia_universe.py:334-356`) now separates two concerns the
round-1 code conflated: staleness is re-derived against a live `now` on **every** call (pure
arithmetic, no network), while the network retry is throttled separately
(`_refetch_due()` / `_REFETCH_INTERVAL_S = 900.0`). Mirrors `news_context.py`'s per-call TTL check,
exactly as the round-2 finding specified.

Reproduced `test_f2_staleness_is_rechecked_after_the_cache_is_warm`,
`test_f2_refetch_is_throttled_while_the_source_is_down`,
`test_f2_refetch_fires_once_the_interval_elapses` — 3/3 passed.

**My own revert-proof**, not a re-read of the coder's: swapped `sharia_universe.py` back to its
exact round-1 content (`git show c1a8706:backend/app/services/sharia_universe.py`), ran the
round-2 `test_f2_*`/`test_f3_*` tests against it — `room_runner.py` (unchanged since round 2 added
the import) fails to resolve `default_halal_universe_async` against the round-1 module →
`ImportError`, all 4 tests error out. Restored the round-2 file, all 4 pass again. Non-vacuous.

### F3 — synchronous fetch blocking the async event loop

New `default_halal_universe_async()` = `await asyncio.to_thread(provider.get)`
(`sharia_universe.py:394-406`), matching the `run_in_executor` precedent at `app/api/sim.py:411`
cited in round 2's own finding. **Read all four call sites at file:line, not from the lane doc's
list**:

- `app/api/sim.py:183` — `preview_trade`. A **fourth** site the round-2 audit didn't know about;
  round 1 found three (`audit_holdings`, `submit_trade`, the Room's `run()`); the coder found this
  one and disclosed it rather than silently fixing three.
- `app/api/sim.py:228` — `submit_trade`.
- `app/api/mandate.py:274` — `audit_holdings`.
- `app/services/room_runner.py:1294` — the Room's `run()` streaming generator.

All four `await default_halal_universe_async()`. Confirmed `sim_engine.py`'s `submit`/`preview`
still carry an `or default_halal_universe()` fallback, but it's dead in production — both routes
now pass `halal_universe=` explicitly (read at the call site, not assumed from the diff).

Reproduced `test_f3_async_accessor_does_not_block_the_event_loop` — passed (>5 ticks of a 10ms
background ticker recorded during a 0.3s blocking fetch offloaded to a thread; a genuinely blocked
loop would freeze the ticker at ~0).

### DEF089 — parent-index URL serves HTML — verified LIVE with the real shipping functions

Not just re-reading the lane doc's pasted output. Ran the actual production functions myself:

```python
with httpx.Client(timeout=15.0, headers={"User-Agent": _USER_AGENT}) as client:
    compliant, as_of = fetch_compliant_universe(client, settings.sharia_spus_holdings_url)
    parent = fetch_parent_index(client, settings.sharia_parent_index_url)
```

Result: `compliant=216, as_of=2026-07-23, parent=503`; `AAPL` → pass (in both); `META`/`JPM` → in
parent, absent from compliant → SCREENED_OUT. Matches the lane doc's own live numbers exactly.

Checked the new `sharia_parent_index_url` config docstring's claim — "the failure direction is
safe, a lagging mirror resolves UNKNOWN, never a false PASS" — against `resolve()`'s actual logic:
PASS is gated purely on membership in the independently-sourced compliant set, which the
parent-index mirror never touches, so a stale/lagging mirror can only turn a real SCREENED_OUT into
UNKNOWN, never fabricate a PASS. Holds.

### DEF092 (SPUS 403s the shipping client) — root cause re-derived, not just accepted

```
$ default httpx UA (no header)  → 403, 146 bytes, nginx block page
$ headers={"User-Agent": _USER_AGENT} (the real constant)  → 200, 216 tickers
```

Confirms the UA really is the gating factor, not a coincidence of some other run-to-run flakiness —
I reproduced both the broken and fixed states myself with the exact client code, not the vendor's
prose about it.

## Suite reproduction

`uv sync --extra dev` first (same known fresh-worktree fallback).

| Check | Command | Result |
|---|---|---|
| Self-test subset | `uv run pytest tests/unit/ -q -k "halal or sharia or mandate or safety_floor or config_compose"` | **102 passed, 870 deselected** (round 1 was 95; +7 matches the new F2/F3/DEF089 tests). Matches. |
| Full backend suite | `uv run pytest tests/unit/ -q` | **972 passed, 2 warnings, 0 failed** (131.17s). Matches both the coder's claim and the architect's independent `873587d` re-verification exactly. |

## Scope discipline

`git show --stat` on all 3 commits: `6b26310` (6 files: `mandate.py`, `sim.py`, `config.py`,
`room_runner.py`, `sharia_universe.py`, `docker-compose.yml`); `88776b3` (1 file: `sharia_universe.py`);
`c2683da` (2 files: new fixture + test file). All backend-only, exactly as claimed. `git diff
c1a8706..c2683da -- schemas/sharia.py agents/safety_floor.py test_def084_halal_flag_copy_guard.py
test_cr069_halal_guard.py` — **EMPTY**. Round 1's resolver correctness genuinely untouched, not
just claimed untouched.

## New finding — MINOR, non-blocking

`ShariaUniverseProvider.get()` has no lock protecting its check-then-act cache-refresh branch
(`grep -n "Lock" sharia_universe.py` → no hits). Before F3 this was safe by construction — the
whole call chain was synchronous inside a single-threaded event loop, so only one coroutine could
ever be mid-`get()` at a time. **F3 changes that**: routing through `asyncio.to_thread` means two
concurrent requests can now genuinely run `get()` on two OS threads simultaneously. If both land
while `_refetch_due()` just became true, both can pass the guard before either writes
`self._cache`/`self._last_attempt` — duplicate concurrent fetches, last-write-wins on the cache.
Not a correctness or safety-floor issue: `HalalUniverse` is immutable, no torn state is observable,
no incorrect verdict ever results — the failure mode is purely redundant network calls in a narrow
timing window, at most once per `_REFETCH_INTERVAL_S` (900s). This is exactly the class of check
DEF088 exists to make routine, and checking it this round surfaced something real, if minor. Not
minting a DEF myself — architect's call whether a lock is worth the complexity for this blast
radius, or an accepted tradeoff.

## Findings

Zero BLOCKER, zero MAJOR. One MINOR (cache-refresh race, above), non-blocking. All four items this
round targeted (F2, F3, DEF089, DEF092) independently verified fixed, including two live
end-to-end runs of the actual shipping fetch code against the real configured URLs.

## Verdict

**VERDICT: COMPLETE (round 3)**
