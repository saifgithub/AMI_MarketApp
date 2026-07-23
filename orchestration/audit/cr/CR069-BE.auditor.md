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
