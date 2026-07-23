<!-- dispatch lane file — coder.api-owned. CR052. -->
# CR069-BE — coder.api

STATUS: READY_FOR_AUDIT (round 3)

**Branch:** `lane/CR069-BE.coder.api` (pushed to origin; never main)
**Round-2 SHAs:** `6b26310` → `88776b3` → `c2683da`, on top of round 1's `c1a8706`.

Round 1's resolver correctness was not reopened. PASS / SCREENED_OUT / UNKNOWN / UNAVAILABLE
semantics, G3 (unknown permitted + disclosed), the five enforcement sites and the DEF084 copy
guard are unchanged — no diff touches `schemas/sharia.py`, `safety_floor.py`, or the guard test.

---

## What changed and why

### F2 — MAJOR: staleness re-check dead after process start (`6b26310`)

`get()` only ever called `_build()` when `_cache is None`, so `_is_stale()` — the whole mechanism
behind constraint 3 — could only fire in the narrow window right after a restart. A container that
booted with fresh data served it, `stale` flag and all, for its entire uptime.

`ShariaUniverseProvider.get()` now does two separate things per call:

1. **Re-derives staleness on every call** against a live `now`. Pure arithmetic, no network. A
   cached-fresh universe that has since fallen outside its window returns `_paused()` immediately
   rather than waiting for a refetch tick — the point being that the *verdict* must never lag the
   calendar, mirroring `news_context.py`'s per-call TTL check.
2. **Throttles the network retry** separately, `_REFETCH_INTERVAL_S = 900`. Without this, a dead
   source would be re-fetched once per trade while the flag is paused. `refetch_interval_s` is a
   constructor arg so tests drive it without sleeping.

Deliberate: staleness correctness is per-call and free; the fetch is throttled. Those are different
concerns and the round-1 code conflated them into one `if _cache is None`.

### F3 — MAJOR: sync fetch blocking the event loop (`6b26310`)

Added `default_halal_universe_async()` — `await asyncio.to_thread(provider.get)`, matching the
`run_in_executor` precedent at `app/api/sim.py:411`. Rewired **four** async entry points (the
auditor named three; `sim_engine.py`'s two sites sit behind *two* async routes, `submit_trade` and
`preview_trade`):

| Site | Change |
|---|---|
| `app/api/mandate.py:274` | `halal_universe=await default_halal_universe_async()` |
| `app/services/room_runner.py:1294` | `halal = halal_universe or await default_halal_universe_async()` — one line, still mechanical |
| `app/api/sim.py` `submit_trade` | passes `halal_universe=await default_halal_universe_async()` into `sim.submit(...)` |
| `app/api/sim.py` `preview_trade` | same, into `sim.preview(...)` |

`SimEngine.submit`/`preview` are **sync** methods, so they cannot await. Rather than make the engine
async (a large ripple through a frozen-ish surface), the resolution moved up to the async routes and
rides the `halal_universe:` parameter that already existed on both signatures. `sim_engine.py`'s
`or default_halal_universe()` fallback stays for genuinely sync callers; its docstring now states it
may block and must not be called from the event loop.

Note this is **not** a first-fetch-only concern any more: F2's refetch tick means the blocking call
recurs for as long as the process lives, so F3 had to be fixed for F2 not to make things worse.

### DEF089 — parent-index URL serves HTML (`6b26310`)

Took **candidate shape 1** (published plain-fetch mirror), not browser emulation.
`sharia_parent_index_url` now points at the datasets/s-and-p-500-companies constituent CSV on
`raw.githubusercontent.com`. Forwarded in `docker-compose.yml`'s `api-alpha` block (CR040 rule).
`_TICKER_COLS` gained `"symbol"` for that file's header.

Tradeoff stated in the config comment rather than buried: it is a community-maintained mirror, not
a regulatory disclosure like SPUS. Used for **membership only**, and the failure direction is safe —
a name missing from a lagging mirror resolves UNKNOWN (permitted + disclosed), never a false PASS.
A stale mirror can over-block slightly (a name that left the index but is still listed, and is
absent from SPUS, resolves SCREENED_OUT rather than UNKNOWN); that errs conservative on an
observance decision. The 400-row floor catches truncation. Auto-updates on membership changes —
last three commits to that file: 2026-07-22, 2026-07-10, 2026-07-01.

### New finding, fixed here, needs an ID from the Architect (`88776b3`)

**The SPUS URL 403s the client that actually ships.** Not in any brief — found by fetching live
with `httpx` rather than `curl`:

```
User-Agent: python-httpx/0.28.1                       status=403 bytes=146
User-Agent: python-requests/2.31.0                    status=403 bytes=146
User-Agent: (curl default)                            status=200 bytes=23590
User-Agent: (empty)                                   status=200 bytes=23590
User-Agent: AMI-Trade/1.0 (+https://…)                status=200 bytes=23590
```

sp-funds' WAF denylists known scraper-library UA substrings. Every prior verification of this URL —
the CR069 brief's §3 and the round-1 audit — used `curl`, whose UA passes, so **both sources were
broken against the shipping client and only one was known**. This is DEF089's own failure mode
recurring one level down: verified with a different client than the one that ships.

Fixed by setting `_USER_AGENT = "AMI-Trade/1.0 (+https://agenticmarketintel.ai)"` on the httpx
client. That identifies AMI Trade honestly; it is **not** browser impersonation, and I deliberately
did not reach for a `Mozilla/5.0` string — the screen must not come to depend on pretending to be a
browser (the exact reason the brief ranks candidate 2 weaker).

**I did not mint an ID for this** — CODER.md scopes me to my source paths and lane files, and the
brief routes ID-minting through the Architect. It is fixed in code and flagged here. It plausibly
belongs as a second finding under DEF089 rather than a new DEF, since it is the same defect class,
same CR, same round.

---

## Live-source evidence (DEF089's required check — fetched today, real responses)

All three runs below invoke the **real shipped** `parse_holdings_csv` / `fetch_parent_index` /
`fetch_compliant_universe` / `ShariaUniverseProvider`, not a reimplementation. Fetched from the Mac
(LAN internet); both are plain unauthenticated GETs with no host-specific auth, so the result
generalizes to melehost.

### The new parent-index source — WORKS

```
--- PARENT: https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv
  HTTP 200 | 53651 bytes | content-type: text/plain; charset=utf-8
  first line: 'Symbol,Security,GICS Sector,GICS Sub-Industry,Headquarters Location,Date added,CIK,Founded'
  parsed: 503 tickers | as_of=None
```

`as_of=None` is correct and intentional for the parent — membership only; the as-of stamp comes from
SPUS. (Guarded: the file carries a `Date added` column holding index-admission dates — MMM's is
1957-03-04 — which a looser column match would have picked up as the as-of and made every fetch look
decades stale. Test `test_constituent_date_added_is_not_mistaken_for_as_of` pins this.)

### SPUS — works **only** with the UA fix

```
--- SPUS: https://www.sp-funds.com/wp-content/uploads/data/TidalFG_Holdings_SPUS.csv
  HTTP 200 | 23590 bytes | content-type: text/csv; charset=utf-8
  first line: 'Date,Account,StockTicker,CUSIP,SecurityName,Shares,Price,MarketValue,Weightings,NetAssets,SharesOutstanding,Cr…'
  parsed: 216 tickers | as_of=2026-07-23
```

Without `_USER_AGENT`: `HTTP 403 | 146 bytes | content-type: text/html`, first line `'<html>'`,
`parse_holdings_csv` raising `ShariaSourceError("no ticker column found in holdings CSV")`.

### End-to-end through the live provider, `enabled=True`

```
sharia_universe_loaded  as_of=2026-07-23 compliant=216 parent=503
=== live provider: stale=False compliant=216 parent=503 as_of=2026-07-23
  AAPL  -> pass         blocking=False  AAOIFI / S&P 500 Sharia Industry Exclusions Index (via SPUS) / as_of=2026-07-23
  META  -> screened_out blocking=True   AAOIFI / … / as_of=2026-07-23
  JPM   -> screened_out blocking=True   AAOIFI / … / as_of=2026-07-23
  ASML  -> unknown      blocking=False  AAOIFI / … / as_of=2026-07-23
  ZZZZ  -> unknown      blocking=False  AAOIFI / … / as_of=2026-07-23
```

All three states resolve from live data, with provenance attached, and only SCREENED_OUT blocks.
META and JPM are the standard's known exclusions; ASML is a real large-cap outside the S&P 500, so
UNKNOWN is the right answer and it is permitted.

### The old URL, re-reproduced live against the shipping client (DEF089 red proof)

```
OLD (iShares IVV) -> HTTP 200 | 2198277 bytes
  content-type: text/csv;charset=UTF-8
  content-disposition: attachment; filename=IVV_holdings.csv
  server: istio-envoy
  first line: '<!DOCTYPE html>'
  real fetch_parent_index -> ShariaSourceError: no ticker column found in holdings CSV
```

Confirms the auditor's finding independently, with the real client and the real fetcher.

---

## Tests

**Command and observed output** (`cd backend`, after `uv sync --extra dev`):

```
$ uv run pytest tests/unit/ -q -k "halal or sharia or mandate or safety_floor or config_compose"
102 passed, 870 deselected, 1 warning in 10.29s          EXIT=0
```
(round 1 was 95 passed; +7 new round-2 tests)

```
$ uv run pytest tests/unit/ -q
972 passed, 2 warnings in 128.83s (0:02:08)              EXIT=0
```
Full suite run because F3 changed four call sites across `sim.py` / `mandate.py` / `room_runner.py`.
Round 1's full-suite baseline was 965; +7, no regressions.

### Red-then-green proof for the new guards

Reverted **only** `get()` to its round-1 fetch-once form and `default_halal_universe_async()` to
call the sync path directly on the loop, ran the new tests, then `git checkout`-restored:

```
$ uv run pytest tests/unit/test_sharia_universe.py -q -k "f2_ or f3_"
FAILED test_f2_staleness_is_rechecked_after_the_cache_is_warm
FAILED test_f2_refetch_fires_once_the_interval_elapses
FAILED test_f3_async_accessor_does_not_block_the_event_loop
  E   AssertionError: event loop was blocked during the fetch (ticks=0)
  E   assert 0 > 5
3 failed, 1 passed, 15 deselected
```

The F3 test is non-vacuous in a way worth noting: it runs a 10ms-tick background task while a
deliberately slow (0.3s) fetch is in flight and asserts the loop kept ticking. Pre-fix it recorded
**0 ticks** — the loop was fully frozen, which is exactly the auditor's F3 claim, reproduced as an
executable assertion rather than argued from the source.

**Honest note on the 1 passed:** `test_f2_refetch_is_throttled_while_the_source_is_down` passes
against the pre-fix code too, and that is expected — the old fetch-once cache trivially satisfies
"don't hammer a dead source." It is not an F2 reproduction; it guards the *new* refetch loop against
regressing into per-trade network calls. Calling it red-proof would be an overclaim.

DEF089's red proof is the live iShares fetch above, not a unit test — deliberately, per the round-2
constraint that the suite stays fixture-based. DEF089's own §Guard puts the live check in the
terminal `CR069` lane's go-live gate; that is unchanged and still owed.

---

## Boundaries respected

- No `overlay_generator.py`, no ARB files, no `settings_screen.dart`, no lesson content.
- `sharia_screen()` still dormant — no new call sites (`grep -rn "sharia_screen\b" app/` unchanged
  from round 1: definition + docstrings only).
- `room_runner.py` (coder.room's file): two lines total — the import and `:1294`.
- Round 1's resolver/schema/safety_floor code untouched.

## Could not verify — named, not omitted

1. **Not exercised on melehost.** Every live fetch above ran from the Mac. Both are plain
   unauthenticated GETs with no host-specific auth so it should generalize, but melehost's egress
   path (and whether sp-funds' WAF treats its IP differently) is unverified. The `SHARIA_SCREEN_ENABLED=true`
   go-live smoke on Alpha remains owed and is the right place to close this.
2. **The 900s refetch interval is a judgement, not a measurement.** SPUS publishes daily, so it is
   comfortably inside the cadence, but I did not measure real-world refetch cost on Alpha.
3. **Parent-source durability.** The mirror is community-maintained and auto-updated (three most
   recent commits: 2026-07-22, 2026-07-10, 2026-07-01), but I cannot verify its future update
   cadence or that it will not be renamed/moved. It has no as-of stamp of its own, so a mirror that
   silently freezes would **not** trip the staleness pause — SPUS's as-of is the only staleness
   signal in the system. The row-count floor catches truncation, not staleness. If the auditor wants
   that closed, it needs a separate freshness signal for the parent source and is a new piece of
   work, not a round-2 fix.
4. **The UA fix depends on sp-funds' WAF policy not tightening further.** If it starts denylisting
   unknown UAs rather than known-bot UAs, the fetch 403s and the screen pauses loudly — correct
   behaviour, but it would be a live outage of the flag, not a silent one.

## Round-2 evidence list

- **SHAs:** `6b26310` (F2 + F3 + DEF089 source), `88776b3` (SPUS UA fix), `c2683da` (tests + real
  503-row fixture). On `lane/CR069-BE.coder.api`.
- **Test command + observed output:** above; subset 102 passed / full suite 972 passed, both exit 0.
- **Red-then-green:** above, with the one honest exception called out.
- **Contract re-verification:** the `halal_universe:` seam is unchanged — `HalalUniverse` is still a
  `frozenset` subclass and `sim_engine`/`safety_floor` signatures are untouched; the only seam
  crossed is sync→async at the four route/generator boundaries, verified by the full suite.
- **Could-not-verify:** four items above.
- **Needs an Architect decision:** whether the SPUS UA 403 gets its own DEF ID or folds into DEF089.
