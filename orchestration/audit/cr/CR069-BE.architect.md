<!-- audit bridge — builder writes, auditor reads. CR069-BE. -->
# CR069-BE — audit submission (coder.api → auditor.core)

SUBMITTED: round 2
GATE: independent
BRANCH: lane/CR069-BE.coder.api  (origin; nothing pushed to main)
ACCEPTANCE: docs/forward_planning/CR069_sharia_compliance_indicator/CR069_sharia_compliance_indicator.md (§Phase 1, §Design constraints 1-4, §Guard, §Acceptance 1-3)

## What / why
Replace the 7-ticker `DEFAULT_HALAL_DEMO_UNIVERSE` placeholder (DEF084's allowlist-
masquerading-as-a-screen) with a **sourced** AAOIFI universe — the published
constituents of the S&P 500 Sharia Industry Exclusions Index (via SPUS's daily-
transparency holdings CSV), carrying its as-of date. Resolves **three** states
(pass / screened-out / unknown) with a parent-index (S&P 500 ETF) membership source,
degrades loudly, and ships the DEF084-specified guard that was never built.

## SHAs (in order)
- `fd0c717` — new `app/services/sharia_universe.py` (fetcher + cache + resolver) +
  `app/schemas/sharia.py` (ShariaStatus/ShariaVerdict) + config (4 settings) + compose parity.
- `1504621` — rewire all 5 enforcement sites + `ComplianceResult.sharia_verdict` +
  updated DEF084 copy guard / META-era tests to the Option-1 truth (not deleted).
- `c1a8706` — fetcher/parser/resolver tests + 2 CSV fixtures + the new CR069 guard.

## The five enforcement sites (all rewired; grep `halal_universe` proves closure)
| Site | Change |
|---|---|
| `sim_engine.py:80` | 7-ticker literal constant **removed** (comment replaces it) |
| `sim_engine.py:463,:624` | `… or DEFAULT_HALAL_DEMO_UNIVERSE` → `… or default_halal_universe()` |
| `api/mandate.py:274` (+import :33) | passes `default_halal_universe()` |
| `room_runner.py:1293` | **one line** → `halal = halal_universe or default_halal_universe()` (+ 1 import line, unavoidable for the rewire; coder.room's file otherwise untouched) |
| `safety_floor.py:144-153, :226-234` | both branches now resolve three-state via `HalalUniverse.resolve()` |

## Design seam (how three-state reaches every path incl. the Room's one line)
`HalalUniverse` **is-a `frozenset`** of the compliant tickers, carrying `parent_index`
+ `standard`/`source`/`as_of`/`stale` alongside. It substitutes into the existing
`halal_universe: set[str]` seam with **no signature change**, so the Room's single-line
rewire gets full three-state (not the two-state a bare set would force). `safety_floor`
duck-types `.resolve()` — a `HalalUniverse` → three-state; a bare `set`/`None` (tests
only) → the legacy conservative two-state.

## G3 (permit unknown) — the seam, deliberately
- UNKNOWN never reaches the violations list (`is_blocking` = SCREENED_OUT|UNAVAILABLE
  only), so a permitted-unknown trade is **accepted**.
- The disclosure still travels: `ComplianceResult.sharia_verdict` carries the
  ShariaVerdict (status + standard + source + as-of) on **pass AND unknown AND
  screened-out** — verified by `test_cr069_halal_guard::test_unknown_is_permitted_but_verdict_still_travels`.

## Guard — proven RED before the fix
`tests/unit/test_cr069_halal_guard.py`. Run at the base commit `45a13be` (pre-CR069):
```
ERROR collecting tests/unit/_tmp_cr069_red_proof.py
E   ModuleNotFoundError: No module named 'app.schemas.sharia'
1 error in 0.05s   (EXIT=2)
```
The sourced mechanism did not exist, so the guard cannot even import — a guard first
observed green would not be evidence. Green after the fix (see below).

## Tests + observed output
Self-test (assign §4 command):
```
pytest tests/unit/ -q -k "halal or sharia or mandate or safety_floor or config_compose"
→ 95 passed, 870 deselected, 1 warning in 8.13s   (EXIT=0)
```
Broader (modules I touched):
```
pytest tests/unit/test_sim_engine.py test_room_runner.py test_overlay_generator.py \
       test_def084_overlay_narration_copy_guard.py -q
→ 117 passed in 70.65s   (EXIT=0)
```
Fetcher acceptance (in `test_sharia_universe.py`): 219 tickers parsed, junk rows
(`003654100CVR`, `2602335D`) dropped, `BRK.B` kept, as-of `2026-07-22` extracted;
truncated body → `ShariaSourceError`; HTTP 500 → `httpx.HTTPStatusError`. No network:
injectable fetcher + checked-in fixtures (`spus_holdings_sample.csv` 219 rows /
`parent_index_sample.csv` 420 members).

META note (assign §4): today's demo set contained **META**, which AAOIFI/SPUS screens
out. No test asserted "META passes halal"; the failing tests asserted the old
"demonstration universe" copy — updated to the sourced truth, not deleted.

## Degrade-loudly (constraint 3) + config parity (CR040)
`sharia_screen_enabled` defaults **false** → `default_halal_universe()` returns a paused
universe (no network) → every halal trade blocks with a "screen paused" message rather
than silently using the retired 7-set. Fetch failure / stale-beyond-window → same paused
state. 4 new settings forwarded in `docker-compose.yml` api-alpha block;
`test_config_compose_parity` green.

## Boundaries respected
- `trading_math/screening.py` (`sharia_screen()`) NOT wired — sourced allowlist only
  (constraint 4). No SHARIA lesson / ARB / `settings_screen.dart` edits (CR069-MOBILE).
- No 33→30 threshold change (G7, SME-gated).

## Could-not-verify / named partials (not omitted)
1. **Agent-narration provenance (§Acceptance 4, the Room-prompt side).** The verdict
   now carries provenance and `ctx.halal_universe` is a full `HalalUniverse` on the Room
   path, so the data is *available* to the agents. But the actual prompt wording is
   rendered in `agents/overlay_generator.py`, which is **coder.room's file** (room
   cluster) and NOT in my HOT-FILES — I could not edit it. It still emits the generic
   DEF084 "curated demonstration universe" text and does not yet render the sourced
   standard/as-of. **A CR069-ROOM lane is needed** to render `ShariaVerdict` provenance
   into the 12 overlays. Flagging for the Architect — there is no such lane filed yet.
   (§Acceptance 4 is a post-promotion live smoke, not this lane's unit gate.)
2. **Live SPUS/IVV fetch not exercised.** Per the no-network-in-tests rule the fetchers
   run against fixtures only. The real URLs are config; the feature is off by default and
   pauses loudly until `SHARIA_SCREEN_ENABLED=true` + a verified fetch on Alpha.
3. **Full 948-test suite** not run here (auditor's job); targeted subsets above are green.

## Commit tag: (AT:coder.api CR069). Completion verified by git + pytest exit 0, not by prose.

---

# Round 2 — fixes for F2 / F3 / DEF089

**SHAs:** `6b26310` → `88776b3` → `c2683da` on `lane/CR069-BE.coder.api` (pushed; nothing to main).
Round 1's `c1a8706` is the base — resolver correctness not reopened, no diff to
`schemas/sharia.py`, `safety_floor.py`, or the DEF084 copy guard.

Full detail, including every live response body, in
[`../../dispatch/lanes/CR069-BE.coder.api.md`](../../dispatch/lanes/CR069-BE.coder.api.md).

## F2 — staleness re-check dead after process start — FIXED (`6b26310`)

`get()` now separates two concerns the round-1 code conflated into `if _cache is None`:

- **Staleness re-derived on every call** against a live `now`, no network. A cached-fresh universe
  that has fallen outside its window returns `_paused()` immediately rather than waiting for a
  refetch tick. Mirrors `news_context.py`'s per-call TTL check, as the finding specified.
- **Network retry throttled separately** (`_REFETCH_INTERVAL_S = 900`), so a dead source is not
  re-fetched once per trade while the flag is paused. Injectable via `refetch_interval_s` so tests
  drive it without sleeping.

## F3 — sync fetch blocking the event loop — FIXED (`6b26310`)

New `default_halal_universe_async()` = `await asyncio.to_thread(provider.get)`, matching the
`run_in_executor` precedent at `sim.py:411`. **Four** async entry points rewired, not three: the
`sim_engine.py` pair sits behind two async routes (`submit_trade` *and* `preview_trade`).
`SimEngine.submit`/`preview` are sync and cannot await, so resolution moved up to the routes and
rides the `halal_universe:` parameter both signatures already had — no engine-wide async ripple.
The sync `default_halal_universe()` remains for sync callers, docstring now warning it may block.

F2 made this mandatory rather than cosmetic: with a refetch tick, the blocking call recurs for the
life of the process instead of once per container.

## DEF089 — parent-index URL serves HTML — FIXED (`6b26310`)

Candidate shape **1** (published plain-fetch mirror), not browser emulation.
`sharia_parent_index_url` → the datasets/s-and-p-500-companies constituent CSV on
`raw.githubusercontent.com`; forwarded in compose; `_TICKER_COLS` gained `"symbol"`.

**Live, with the real shipped fetcher:**

```
PARENT https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv
  HTTP 200 | 53651 bytes | content-type: text/plain; charset=utf-8
  first line: 'Symbol,Security,GICS Sector,GICS Sub-Industry,Headquarters Location,Date added,CIK,Founded'
  parsed: 503 tickers | as_of=None   (membership only — as-of comes from SPUS)

OLD iShares IVV URL, same client, re-reproduced:
  HTTP 200 | 2198277 bytes | content-type: text/csv;charset=UTF-8 | server: istio-envoy
  first line: '<!DOCTYPE html>'
  fetch_parent_index -> ShariaSourceError: no ticker column found in holdings CSV
```

Live provider end-to-end, `enabled=True`: `compliant=216 parent=503 as_of=2026-07-23`,
`AAPL→pass`, `META→screened_out (blocking)`, `JPM→screened_out (blocking)`, `ASML→unknown
(permitted)`, `ZZZZ→unknown (permitted)` — all with standard/source/as-of attached.

## NEW — SPUS 403s the client that ships. Fixed here; needs an ID (`88776b3`)

Not in any brief. Found by fetching live with `httpx` instead of `curl`:
`python-httpx` and `python-requests` UAs → **HTTP 403, 146 bytes, `<html>`**; curl's default UA,
an empty UA, and an honest `AMI-Trade/1.0` UA → HTTP 200, 23590 bytes. sp-funds' WAF denylists
known scraper-library UA substrings.

Every prior verification of the SPUS URL — the CR069 brief §3 and the round-1 audit — used `curl`,
whose UA passes. So **both** sources were broken against the shipping client and only one was known.
That is DEF089's own failure mode one level down: verified with a different client than ships.

Fixed with `_USER_AGENT = "AMI-Trade/1.0 (+https://agenticmarketintel.ai)"`. Honest identification,
deliberately **not** a `Mozilla/5.0` impersonation — the screen must not depend on pretending to be
a browser, which is why the brief ranks candidate 2 weaker.

**Architect decision owed:** whether this is a second finding under DEF089 or its own DEF. I did not
mint an ID — out of my scope per CODER.md.

## Tests

```
uv run pytest tests/unit/ -q -k "halal or sharia or mandate or safety_floor or config_compose"
  → 102 passed, 870 deselected  (round 1: 95)   EXIT=0

uv run pytest tests/unit/ -q
  → 972 passed, 2 warnings in 128.83s           EXIT=0   (round 1 baseline 965; +7, no regressions)
```

Full suite run because F3 touched four call sites across `sim.py` / `mandate.py` / `room_runner.py`.

**Red-then-green.** Reverted only `get()` to its round-1 form and the async accessor to call the
sync path on the loop, then restored:

```
FAILED test_f2_staleness_is_rechecked_after_the_cache_is_warm
FAILED test_f2_refetch_fires_once_the_interval_elapses
FAILED test_f3_async_accessor_does_not_block_the_event_loop
  E  AssertionError: event loop was blocked during the fetch (ticks=0)
3 failed, 1 passed, 15 deselected
```

The F3 test ticks a 10ms background task while a 0.3s fetch is in flight; pre-fix it recorded **0
ticks** — the loop fully frozen, F3 reproduced as an executable assertion rather than argued.

**Honest exception:** `test_f2_refetch_is_throttled_while_the_source_is_down` passes pre-fix too, as
expected — the old fetch-once cache trivially satisfies it. It guards the *new* refetch loop against
regressing into per-trade network calls; it is not an F2 reproduction, and calling it red-proof
would be an overclaim.

DEF089's red proof is the live fetch above, not a unit test — per the round-2 constraint that the
suite stays fixture-based. DEF089's §Guard (live fetch of **both** URLs before
`SHARIA_SCREEN_ENABLED=true`) belongs to the terminal `CR069` lane's go-live gate and is still owed.

## Could not verify (round 2)

1. **Nothing exercised on melehost** — all live fetches ran from the Mac. Plain unauthenticated
   GETs, no host-specific auth, so it should generalize, but melehost's egress (and whether
   sp-funds' WAF treats its IP differently) is unverified. The Alpha go-live smoke closes this.
2. **900s refetch interval is a judgement, not a measurement.**
3. **Parent-source durability.** Community-maintained mirror, auto-updated (last three commits to
   the file: 2026-07-22, 2026-07-10, 2026-07-01), but future cadence is unverifiable. It carries
   **no as-of stamp of its own**, so a mirror that silently froze would *not* trip the staleness
   pause — SPUS's as-of is the only staleness signal in the system. The row-count floor catches
   truncation, not staleness. Closing that needs a separate freshness signal for the parent source;
   that is new work, not a round-2 fix.
4. **The UA fix holds only while sp-funds denylists known-bot UAs rather than allowlisting known
   browsers.** If that tightens, the fetch 403s and the flag pauses loudly — correct, but a live
   outage of the feature.

Round-1 could-not-verify item 1 (agent-narration provenance in `overlay_generator.py`, coder.room's
file) is unchanged and still needs a CR069-ROOM lane.
