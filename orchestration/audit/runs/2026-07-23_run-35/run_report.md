<!--
Auditor run report — run-35 (2026-07-23, session auditor.core/track U). Round-2 SELF-REOPEN of
CR069-BE, prompted by Saiful questioning round-1's pace given the CR's structural weight. No new
architect submission — same SHA c1a8706, re-examined for runtime/lifecycle behavior round 1 didn't
cover. Verdict AWAITING_FIXES. Owner: AUDITOR.
-->

# run-35 (round 2) — CR069-BE, self-reopened → AWAITING_FIXES

- **Auditor session:** auditor.core (track U), 2026-07-23, same day as run-34.
- **Why this round exists:** Saiful, after reading run-34's COMPLETE verdict: *"that was quick. these
  are pretty structural changes."* Fair challenge — round 1 verified the resolver's *logic*
  (three-state correctness, G3, provenance) and the fetcher's *parsing* thoroughly, including a live
  adversarial pass that found a real external-URL problem. It never examined the provider as a
  **long-lived object inside a running server process** — cache lifecycle and the sync/async
  boundary. That's a real gap in coverage, not a defensive re-check that came up empty.
- **Audited SHA:** `c1a8706` — unchanged, same as run-34. No architect resubmission; `SUBMITTED` is
  still round 1. Advancing the auditor round on my own initiative is protocol-legal — PROTOCOL.md's
  own gap-fill note says detect state by the `VERDICT:` keyword, never by round-number equality
  alone.
- **Verdict:** AWAITING_FIXES (round 2) — two new MAJOR findings (F2, F3) against the provider's
  runtime behavior. Round 1's findings on resolver correctness and the external-URL problem stand
  unchanged; this round doesn't reopen either.

---

## F2 — MAJOR: staleness is checked once per process lifetime, never again

`ShariaUniverseProvider.get()` (`sharia_universe.py:286-289`):

```python
def get(self, *, refresh: bool = False, now: date | None = None) -> HalalUniverse:
    if self._cache is None or refresh:
        self._cache = self._build(now=now)
    return self._cache
```

`_is_stale()` — the mechanism behind constraint 3's "degrades loudly if stale beyond its window" —
only runs inside `_build()`, which only fires when `self._cache is None` (the first call in the
process) or on an explicit `refresh=True`. Grepped the whole tree: `refresh=True` has **zero call
sites** in `app/`; `reset_sharia_universe_provider` (the only other cache-buster) is **only called
from tests**. melehost runs `ami_api_alpha` as a single long-running container — confirmed via
`Dockerfile:34` (`CMD ["uvicorn", "app.main:app", ..., "--reload"]`, no worker-cycling flag) — so in
real deployment: container starts → first halal-flagged request fetches once and caches whatever
`HalalUniverse` (or paused state) results → **every subsequent request for that container's entire
uptime gets the identical cached object**, `stale` flag included, never re-derived against a fresh
`now`.

`sharia_staleness_days: int = 7` (`config.py:177`) is real, correctly-forwarded config that is
practically dead: it can only fire in the narrow window right after a container restart. A universe
fresh at boot silently serves increasingly-stale PASS/SCREENED_OUT verdicts — no pause, no
`UNAVAILABLE` — for the container's entire remaining uptime. For a religious-observance flag, "loud
at boot, silent forever after" is the exact failure constraint 3 exists to prevent, just delayed
instead of immediate.

**Established counter-pattern in the same codebase** (so this isn't a novel Python opinion being
applied for the first time): `news_context.py`'s `_AlphaVantageSource`
(`_ALPHA_VANTAGE_CACHE_TTL`, `:47,95-130`) checks `time.time()` against a **per-call** expiry on
every read. `sharia_universe.py`'s provider doesn't follow it.

## F3 — MAJOR: the first fetch is a blocking synchronous call inside async route handlers

`_default_fetcher()` (`sharia_universe.py:248-252`) uses `httpx.Client` (sync), doing up to two real
HTTP round-trips at `timeout=15.0` each. All three callers of `default_halal_universe()` invoke it
with no `await` and no offload, directly inside `async def` handlers:

- `app/api/mandate.py:274`, inside `async def audit_holdings` (`:265`).
- `app/api/sim.py:210` (`sim.submit(...)` → `sim_engine.py:464`/`:625`), inside
  `async def submit_trade` (`app/api/sim.py:197`).
- `app/services/room_runner.py:1294`, inside `async def run(...)` (`:1236`) — the Room's own
  streaming Convene generator, the highest-traffic path this flag touches.

`docker-compose.yml` + `Dockerfile:34` run a single `uvicorn` process, **no `--workers` flag**
(confirmed, not assumed — default is one process, one event loop). A synchronous blocking call
inside any of these three handlers stalls the **entire event loop** — every concurrent user on the
whole API, not just the triggering request — for the duration of the live network call(s). Because
of F2 this is a one-time hit per container lifetime (bounded), but it lands unpredictably on
whichever of the three entry points a real user hits first after `SHARIA_SCREEN_ENABLED=true` is set
or the container restarts, freezing the service for everyone else connected at that moment —
including an unrelated in-progress Room stream.

**Established counter-pattern in the same codebase:** `app/api/sim.py:411` already offloads a
blocking `sim.current_quote` call via `loop.run_in_executor(pool, ...)` for exactly this class of
problem. CR069-BE's three call sites don't follow the project's own existing precedent.

## Why round 1 missed both

Round 1's rigor was real — exhaustive on resolver logic and fetcher parsing, plus a live adversarial
pass that surfaced a genuine external-source defect nobody had found before. It simply never asked
how the singleton behaves as a long-lived object across many requests over the container's uptime.
That's a dimension, not a depth failure on the dimensions it did cover — worth naming precisely so
future rounds check "runtime lifecycle + sync/async boundary" as a standing item on any provider/
cache-shaped chunk, not just this one.

## Findings

- **F2 — MAJOR.** Staleness re-check dead after process start; contradicts constraint 3 for any
  long-running deployment. Fix shape: check elapsed time against `as_of`/staleness window on every
  `get()` call (mirror `news_context.py`'s per-call TTL), or add an explicit periodic refresh path.
- **F3 — MAJOR.** Synchronous network fetch blocks the async event loop on first use, at all three
  call sites, on a confirmed single-worker deployment. Fix shape: `asyncio.to_thread(self._build, ...)`
  or `run_in_executor` (matching `sim.py:411`'s existing pattern).

Neither reopens round 1's resolver-correctness verification or the carried live-parent-index-URL
finding — both stand as reported in run-34.

## Verdict

**VERDICT: AWAITING_FIXES (round 2)**
