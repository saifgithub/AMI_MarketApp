<!--
CR069-BE.auditor.md — auditor lane file (track U owns). State derives from round numbers
here vs CR069-BE.architect.md (see PROTOCOL.md). CR069-BE is a chunk under the CR069
decomposition (CR069_decomposition.md) — carries the chunk evidence list, NOT the CR-level
Definition of Done; that belongs to the terminal `CR069` lane (not yet dispatched).
-->

# CR069-BE — audit lane (auditor)

**Item:** CR069-BE — sourced AAOIFI Sharia universe (fetcher + three-state resolver) replacing
`DEFAULT_HALAL_DEMO_UNIVERSE`, rewired into all 5 `halal` enforcement sites.

**Audited SHA:** `c1a8706` (tip of `lane/CR069-BE.coder.api`, on origin, not yet merged to main —
per CODER.md delivery is to the lane branch, not the shared branch). Chain: `fd0c717` (fetcher +
resolver + config) → `1504621` (5-site rewire + copy guard evolution) → `c1a8706` (tests + fixtures
+ the DEF084-specified guard). Audited in an isolated worktree
`.claude/worktrees/audit-CR069-BE/` (`git worktree add --detach c1a8706`).

**DoD note:** this is a chunk under the CR069 decomposition (6 lanes + a terminal `CR069` CR-level
audit, per `CR069_decomposition.md`). Per `AUDITOR_LOOP_PROMPT.md` §4, a chunk carries the shorter
chunk evidence list and is not bounced for a missing Definition-of-Done table — confirmed the lane
file carries exactly the CODER.md-specified list (SHA(s), what/why, tests + observed output,
contract note, named could-not-verify items). Full DoD is the terminal `CR069` lane's job.

## Round 1

### Reproduced independently

| Check | Command | Result |
|---|---|---|
| Self-test subset | `uv run pytest tests/unit/ -q -k "halal or sharia or mandate or safety_floor or config_compose"` | **95 passed, 870 deselected** (after `uv sync --extra dev` in the fresh worktree). Matches. |
| Broader touched-module subset | `uv run pytest tests/unit/test_sim_engine.py tests/unit/test_room_runner.py tests/unit/test_overlay_generator.py tests/unit/test_def084_overlay_narration_copy_guard.py -q` | **117 passed**. Matches (architect named `test_def084_overlay_narration_copy_guard.py`; the actual file is `test_def084_halal_flag_copy_guard.py` — harmless filename slip in the lane doc, file exists and is exactly the one touched by `1504621`). |
| Fetcher/parser/resolver | `uv run pytest tests/unit/test_sharia_universe.py -q -v` | **12 passed**. |
| Full backend suite (auditor's job, not the chunk's) | `uv run pytest tests/unit/ -q` | **965 passed, 2 warnings, 0 failed** (129.77s). No regression anywhere in the tree. |
| Guard revert-proof | Reverted worktree to base `45a13be`, copied `test_cr069_halal_guard.py` in, ran it | **5 failed** (module/attribute errors — `app.schemas.sharia` / `HalalUniverse` don't exist pre-fix). Non-vacuous, independently reproduced (architect's own repro used a slightly different scratch-file path and reported a single collection error; same root cause, same conclusion: red at base). |

### Source re-read (file:line)

- `app/services/sharia_universe.py` — `HalalUniverse(frozenset)` with `resolve()`:
  `stale → UNAVAILABLE`, `in self → PASS`, `in parent_index (not self) → SCREENED_OUT`,
  else `→ UNKNOWN` (:113-130). `_build()` (:258-284): disabled → `_paused()`; fetch raises
  `httpx.HTTPError`/`ShariaSourceError` → `_paused()`; stale-beyond-window → `_paused()`;
  only a genuinely fresh, successful fetch produces a live `HalalUniverse`. `_paused()`
  (:254-256) always sets `stale=True`, which `resolve()` maps to `UNAVAILABLE` for every
  ticker — no code path returns a stale/partial universe as if it were current.
- `app/schemas/sharia.py` — `ShariaVerdict.is_blocking` (:60-67): `SCREENED_OUT` and
  `UNAVAILABLE` only; `PASS`/`UNKNOWN` never block. Matches G3 exactly, and the property's
  own docstring states the invariant it exists to protect.
- `app/agents/safety_floor.py:144-166` (`check_mandate_compliance`) and `:246-257`
  (`check_holdings_against_mandate`) — both call `resolve(t)` unconditionally whenever
  `c.halal` and a `HalalUniverse` is present (`getattr(halal_universe, "resolve", None)`
  duck-type), so `sharia_verdict`/`hv` is populated on **every** outcome (PASS, SCREENED_OUT,
  UNKNOWN, UNAVAILABLE) — the disclosure genuinely travels on a permitted-unknown trade, not
  only on a rejection, confirmed by reading the branch structure, not just the docstring
  claiming it.
- Five enforcement sites — read each file:line directly, not the lane summary:
  `sim_engine.py:459` and `:625` (`halal_universe or default_halal_universe()`), `api/mandate.py:274`
  (`halal_universe=default_halal_universe()`), `room_runner.py:1293`
  (`halal = halal_universe or default_halal_universe()`) — all four call the same
  `default_halal_universe()` singleton accessor; `sim_engine.py:75-81` carries only a comment
  where the old 7-ticker constant used to be (`grep DEFAULT_HALAL_DEMO_UNIVERSE app/` → zero
  hits, confirms it's genuinely gone, not re-pointed).
- Config parity — `app/core/config.py:167-177` (4 settings, `sharia_screen_enabled` defaults
  `False`) and `docker-compose.yml:144-147` (`SHARIA_SCREEN_ENABLED`/`SHARIA_SPUS_HOLDINGS_URL`/
  `SHARIA_PARENT_INDEX_URL`/`SHARIA_STALENESS_DAYS` all forwarded). `test_config_compose_parity`
  passed in the self-test subset above.
- Boundary respected — `grep -rn "sharia_screen\b" app/` → every hit is either a docstring/
  comment reference or the function's own definition in `trading_math/screening.py`; zero call
  sites from `safety_floor.py`/`sim_engine.py`/`room_runner.py`/`api/mandate.py`. Constraint 4
  genuinely honored, not just disclaimed.
- Scope discipline — `git show --stat` on all 3 commits: `fd0c717` (4 files, all new:
  `config.py`, `schemas/sharia.py`, `services/sharia_universe.py`, `docker-compose.yml`);
  `1504621` (9 files, all backend enforcement/tests); `c1a8706` (4 files, all backend
  tests/fixtures). No mobile, no `overlay_generator.py` (correctly named as "coder.room's
  file, could not touch" in the lane doc — confirmed by its absence from every diff), no
  drive-by changes.
- DEF084 copy guard — `git show 1504621 -- tests/unit/test_def084_halal_flag_copy_guard.py`:
  genuinely evolved (renamed assertions, new `_COMPUTED_SCREEN_PHRASES` list, new
  standard/as-of assertions), not deleted or weakened — old test asserted the literal-set
  shape and "demonstration universe" copy; new test asserts the sourced shape and
  standard+as-of copy, still forbidding a claimed *computation*. `test_sim_engine.py`'s
  `test_halal_screens_out_in_index_but_permits_unknown` replaces a single-assertion rejection
  test with one that exercises **both** SCREENED_OUT and UNKNOWN at the `SimEngine.submit`
  boundary — a genuine upgrade, not a narrowed regression.

### Live-source adversarial check (the item's own named open item, exercised for real)

The lane's "Could-not-verify" list names this directly: *"Live SPUS/IVV fetch not exercised…
needs a verified fetch on Alpha."* Reproduced both, live, from the Mac (has internet; this isn't
melehost, but the fetch is a plain unauthenticated `httpx.Client().get()` with no host-specific
auth, so the result generalizes):

- **SPUS (compliant-set) URL — works.** `curl https://www.sp-funds.com/wp-content/uploads/data/TidalFG_Holdings_SPUS.csv`
  → HTTP 200, 23,590 bytes, 220 rows / 219 header+data, `StockTicker`+`Date` columns exactly as
  the fetcher expects. Ran the **real** `parse_holdings_csv()` against this live body:
  **216 tickers, as_of=2026-07-23**, `AAPL` in / `META` and `JPM` out — matches the standard's
  known exclusions.
- **Parent-index (S&P 500 / IVV) URL — does NOT work.** The exact configured
  `sharia_parent_index_url` (`config.py:171-173`, same value in `docker-compose.yml:146`):
  `curl` returns **HTTP 200** but the body is the iShares **product webpage** (`<!DOCTYPE html>…`),
  not a CSV — reproduced **3 times consecutively**, and again with a full browser
  `User-Agent`/`Accept` header (no difference). Response headers are actively misleading:
  `content-type: text/csv;charset=UTF-8` and `content-disposition: attachment;
  filename=IVV_holdings.csv` are both present on the HTML response — consistent with an
  upstream bot-mitigation layer (`server: istio-envoy`) intercepting the request and returning a
  challenge/interstitial page while leaving the origin's file-download headers in place. Ran the
  **real** `parse_holdings_csv()` against this live body: it correctly **raises
  `ShariaSourceError("no ticker column found in holdings CSV")`** — confirmed by direct
  invocation, not inferred. `_build()` catches exactly that exception type and returns
  `_paused()`.

**Consequence, and why this is not a defect in this chunk.** As configured, flipping
`SHARIA_SCREEN_ENABLED=true` on melehost will make `default_halal_universe()` permanently return
a paused (`UNAVAILABLE`, blocking) universe — **every** `halal`-flagged trade will be rejected
with the honest "screen paused" message (`sharia.py:86-89`), indefinitely, not intermittently.
That is exactly constraint 3's degrade-loudly contract working as designed — a real fetch failure
correctly fails safe and visible, never silently. The code is not at fault; **the configured
parent-index URL itself does not serve what CR069 assumed it would** when fetched by a plain
server-side client. Worth noting: the CR069 brief's own §3 "verified live" research only curl'd
the SPUS URL — the parent-index fetch was never live-tested at any point in this CR's history
until this audit round, chunk or brief. This is new, confirmed information, not a restatement of
the lane's own disclosed gap.

**Recommendation (not a bounce on CR069-BE):** flag this prominently before anyone flips
`SHARIA_SCREEN_ENABLED=true` — Acceptance §4's "live smoke after promotion" would catch it
immediately but only after a wasted promotion cycle. Needs either a different parent-index
source (e.g. a Google-Sheets-published mirror the way HLAL is fetched, per the CR069 doc's own
§3 pattern) or browser-emulation/session handling for the iShares endpoint. The architect should
mint a DEF or fold this into the terminal `CR069` lane's go-live gate — I don't mint IDs.

### Findings

No BLOCKER, no MAJOR, no MINOR against CR069-BE's own code or claims — every claim in the lane
file reproduced exactly, the riskiest design property (UNKNOWN never blocking) verified from
source and from a red/green guard, and the one thing the item named as unverified was exercised
live this round with a real (if unwelcome) result, documented above rather than silently
absorbed into "COMPLETE."

**OUT-OF-SCOPE / carried finding (informational, does not bounce this chunk):** the configured
`sharia_parent_index_url` does not serve CSV via a plain HTTP client — see above. Not
CR069-BE's defect (the code's response to this exact failure is correct); a precondition for the
feature ever functioning once enabled.

### Verdict

Zero BLOCKER, zero MAJOR, zero MINOR. Chunk evidence list complete and accurate (SHA(s), what/why,
tests + observed output all reproduced, could-not-verify items honestly named — one of which I
exercised live and it is worse than "unverified," it is currently broken, but that does not
implicate this chunk's own correctness).

**VERDICT: COMPLETE (round 1)**

Run report: [`../runs/2026-07-23_run-34/run_report.md`](../runs/2026-07-23_run-34/run_report.md)

## Round 2 — self-reopened, no architect resubmission

Saiful pushed back on round 1's pace given the CR's structural weight ("that was quick, these are
pretty structural changes") — fair, and re-examining turned up two real gaps round 1 didn't cover:
provider lifecycle (does staleness ever get re-checked?) and the async/sync boundary (does the
first fetch block the event loop?). Neither is about whether the *values* CR069-BE computes are
correct — round 1's source read of the resolver logic stands — both are about the **provider's
runtime behavior in a long-lived process**, a dimension round 1 didn't probe at all. Re-audited the
same SHA `c1a8706`, no new architect submission (architect `SUBMITTED` is still round 1) — I'm
advancing the round on my own initiative per protocol's "detect by the VERDICT keyword, not round
number" note. No source changed; this corrects round 1's coverage, not CR069-BE's code.

### F2 — MAJOR: staleness is checked once per process lifetime, never again

`ShariaUniverseProvider.get()` (`sharia_universe.py:286-289`):
```python
def get(self, *, refresh: bool = False, now: date | None = None) -> HalalUniverse:
    if self._cache is None or refresh:
        self._cache = self._build(now=now)
    return self._cache
```
`_is_stale()` — the entire mechanism behind constraint 3's "degrades loudly... if stale beyond its
window" — is evaluated **only inside `_build()`**, which only runs when `self._cache is None` (the
very first call in the process) or when a caller explicitly passes `refresh=True`. Grepped the
whole tree: `refresh=True` has **zero call sites** in `app/`, and `reset_sharia_universe_provider`
(the only other cache-buster) is **only called from tests**. So in melehost's actual deployment —
a single long-running `ami_api_alpha` container, not restarted per request — the sequence is:
container starts → first halal-flagged request fetches once, caches whatever `HalalUniverse` (or
paused state) results → **every request for the rest of that container's uptime gets the exact
same cached object**, `stale` flag and all, never re-derived against a fresh `now`.

`sharia_staleness_days: int = 7` (`config.py:177`) is real config, forwarded correctly, and
genuinely dead in practice: it can only fire in the narrow window right after a restart, never
during normal long-running operation. A universe that was fresh at container start silently
serves increasingly-stale verdicts — `resolve()` reports `PASS`/`SCREENED_OUT` with full
confidence, no `UNAVAILABLE`, no pause — for as long as the container runs, contradicting
constraint 3 in exactly the way it was written to prevent (a silent stale read, just delayed
rather than immediate). This is a **religious-observance-relevant** flag; "correct at container
boot, silently frozen after" is not what "degrades loudly" was meant to buy.

Cross-checked against this codebase's own precedent for the same problem: `news_context.py`'s
`_AlphaVantageSource` (`_ALPHA_VANTAGE_CACHE_TTL`, `news_context.py:47,95-130`) checks
`time.time()` against a **per-call** expiry on every read, not just the first — a real
self-expiring cache. `sharia_universe.py`'s provider does not follow that established pattern.

### F3 — MAJOR: the first fetch is a blocking synchronous call inside async route handlers

`_default_fetcher()` (`sharia_universe.py:248-252`) uses `httpx.Client` (sync), not
`httpx.AsyncClient`, doing up to two real HTTP round-trips with `timeout=15.0` each. All three
callers of `default_halal_universe()` are invoked with no `await`, no `run_in_executor`, directly
inside `async def` FastAPI route handlers / async generators:
- `app/api/mandate.py:274`, inside `async def audit_holdings` (`:265`).
- `app/api/sim.py:210` (`sim.submit(...)` → `sim_engine.py:464`/`:625`), inside
  `async def submit_trade` (`app/api/sim.py:197`).
- `app/services/room_runner.py:1294`, inside `async def run(...)` (`:1236`) — the Room's own
  SSE/streaming Convene generator, the single highest-traffic path this flag touches.

`docker-compose.yml`/`Dockerfile:34` run a single `uvicorn` process with **no `--workers`
flag** (default: one process, one event loop) — confirmed, not assumed. A synchronous blocking
call inside any of these three async handlers stalls **the entire event loop**, i.e. every
concurrent user on the whole API, not just the triggering request, for the duration of the live
network call(s). Because of F2, this only happens once per container lifetime (bounded blast
radius) — but it happens unpredictably, on whichever of the three entry points a real user hits
first after `SHARIA_SCREEN_ENABLED=true` is set or the container restarts, and freezes the whole
service for everyone else connected at that moment (including an in-progress Room stream on an
unrelated ticker).

This is not a hypothetical Python subtlety being applied for the first time to this codebase: this
project already has an established fix for exactly this shape of problem —
`app/api/sim.py:411` offloads a blocking `sim.current_quote` call via
`loop.run_in_executor(pool, ...)`. CR069-BE's three call sites don't follow that precedent.

### Why round 1 missed both

Round 1 verified the resolver's *logic* exhaustively (three-state correctness, G3, provenance
propagation) and the fetcher's *parsing* correctness (including the live URL adversarial pass) —
both genuinely thorough. It never asked how the `ShariaUniverseProvider` singleton behaves *as a
long-lived object inside a running server process* — cache lifecycle and the sync/async boundary.
That's a real gap in round-1 coverage, not a false alarm on re-check: both F2 and F3 reproduce from
reading the actual shipped code, no speculation.

### Findings (round 2 additions)

- **F2 — MAJOR.** Staleness re-check dead after process start; contradicts constraint 3 for any
  long-running deployment. Fix shape: check elapsed time against `as_of`/staleness window on every
  `get()`, not only when `_cache is None` (mirror `news_context.py`'s per-call TTL check), or add an
  explicit periodic refresh caller.
- **F3 — MAJOR.** Synchronous network fetch blocks the async event loop on first use, at all three
  call sites, on a single-worker deployment. Fix shape: `asyncio.to_thread(self._build, ...)` (or
  `run_in_executor`, matching `sim.py:411`'s existing pattern) so the first fetch doesn't stall
  other requests.

Neither finding touches the resolver's correctness (PASS/SCREENED_OUT/UNKNOWN/UNAVAILABLE
semantics stand, round 1's verification of those is unchanged) or reopens the live parent-index-URL
finding already carried from round 1 (still separately tracked, still not this chunk's defect).
Both are the provider's own runtime shape and are this chunk's to fix.

### Verdict (round 2)

Zero BLOCKER. Two MAJOR (F2, F3) against code this chunk shipped — not process-completeness, not
an external data source, genuine behavioral gaps in the provider. Bounces.

**VERDICT: AWAITING_FIXES (round 2)**

Run report: [`../runs/2026-07-23_run-35/run_report.md`](../runs/2026-07-23_run-35/run_report.md)

## Round 3 (architect's board reads this as round 3; coder's own doc calls it "round 2" — see
DEF091, the round-counter collision my self-reopen caused, now fixed)

**Audited SHA:** `c2683da`, tip of `lane/CR069-BE.coder.api` (`6b26310` → `88776b3` → `c2683da`).
Confirmed `git diff c1a8706..c2683da -- schemas/sharia.py agents/safety_floor.py
test_def084_halal_flag_copy_guard.py test_cr069_halal_guard.py` EMPTY — round 1's resolver
correctness genuinely not reopened, not just claimed.

### F2 — FIXED, independently verified

Source read: `get()` now separates staleness (re-derived every call, pure arithmetic against a
live `now`) from network retry (throttled by `_refetch_due()` / `_REFETCH_INTERVAL_S`). Reproduced
`test_f2_*` (3 tests) green. **Revert-proof, my own**: swapped `sharia_universe.py` back to its
round-1 form (`git show c1a8706:...`), ran the round-2 tests — `room_runner.py`'s existing import
of `default_halal_universe_async` (unchanged since round 2 added it) fails to resolve against the
round-1 module → `ImportError`, all 4 round-2 tests error. Restored, all 4 pass again. Non-vacuous.

### F3 — FIXED, independently verified

All four call sites confirmed at file:line, not from the lane doc's list: `api/sim.py:183`
(`preview_trade`), `:228` (`submit_trade`) — a fourth site the round-1 audit didn't know about,
found by the coder, correctly disclosed — `api/mandate.py:274` (`audit_holdings`),
`room_runner.py:1294` (the Room's `run()`). All four `await default_halal_universe_async()`.
Confirmed `sim_engine.py`'s `submit`/`preview` still carry the `or default_halal_universe()`
fallback but it's dead in production — both routes now pass `halal_universe=` explicitly, verified
by reading the call sites, not assumed. `test_f3_async_accessor_does_not_block_the_event_loop`
reproduced green (>5 ticks of a 10ms ticker during a 0.3s blocking fetch offloaded via
`asyncio.to_thread`).

### DEF089 — FIXED, verified LIVE with the real shipping fetcher functions

Not just re-reading the lane doc's pasted output — ran `fetch_compliant_universe` +
`fetch_parent_index` myself, live, against `settings.sharia_spus_holdings_url` /
`sharia_parent_index_url` exactly as `_default_fetcher()` calls them:

```
compliant: 216  as_of: 2026-07-23
parent: 503
AAPL in compliant: True  | AAPL in parent: True
META in compliant: False | META in parent: True   → SCREENED_OUT
JPM  in compliant: False | JPM  in parent: True    → SCREENED_OUT
```

Matches the lane doc's own live numbers. The new `sharia_parent_index_url` config docstring's
"failure direction is safe" claim (a lagging mirror can only misclassify a real SCREENED_OUT as
UNKNOWN, never fabricate a false PASS) checked against `resolve()`'s logic — PASS is gated purely
on membership in the independently-sourced compliant set, which the parent-index mirror cannot
influence — holds.

### DEF092 (SPUS 403s the shipping client) — FIXED, verified LIVE, diagnosis re-derived not just accepted

Reproduced the ROOT CAUSE myself, not just the fix: plain `httpx.Client(timeout=15.0)` with no
custom header against the SPUS URL → **403, 146 bytes, nginx block page**. Same client with
`headers={"User-Agent": _USER_AGENT}` (the actual constant from source) → **200, 216 tickers**.
Confirms the UA really is what's gating this, not a coincidence of some other run-to-run
flakiness.

### New finding — MINOR, non-blocking: unguarded check-then-act race on cache refresh

`ShariaUniverseProvider.get()` has no lock (`grep -n "Lock" sharia_universe.py` → none). Before F3,
this was safe by construction — the whole call chain was synchronous inside a single-threaded
event loop, so only one coroutine could ever be mid-`get()` at a time. **F3 changes that**: routing
through `asyncio.to_thread` means, for the first time, two concurrent requests can genuinely run
`get()` on two OS threads at once. If both land while `_refetch_due()` just became true, both can
pass the `if` guard before either writes `self._cache`/`self._last_attempt` — duplicate concurrent
fetches, last-write-wins on the cache. Not a correctness or safety-floor issue (no torn state,
`HalalUniverse` is immutable, `resolve()` never sees inconsistent data, no incorrect verdict ever
results) — the failure mode is purely redundant network calls in a narrow timing window, at most
once per `_REFETCH_INTERVAL_S`. Exactly the class of thing DEF088 exists to make routine to check,
and checking it this round turned up something real, if minor. Not filing a DEF myself — worth the
architect's judgement on whether a `threading.Lock` around the refresh branch is worth the
complexity for this blast radius, or whether it's an accepted tradeoff.

### Findings

Zero BLOCKER, zero MAJOR. One MINOR (the refresh race, above), non-blocking. All four items this
round set out to fix (F2, F3, DEF089, DEF092) independently verified fixed — including two live,
end-to-end runs of the actual shipping fetch code against the real URLs, not just re-reading pasted
output. Full suite reproduced: **972 passed, 2 pre-existing warnings, 0 failed** — matches both the
coder's claim and the architect's independent 873587d re-verification exactly. Scope discipline
clean (`git show --stat` on all 3 commits — backend-only, exactly the claimed files).

### Verdict

**VERDICT: COMPLETE (round 3)**

Run report: [`../runs/2026-07-23_run-36/run_report.md`](../runs/2026-07-23_run-36/run_report.md)
