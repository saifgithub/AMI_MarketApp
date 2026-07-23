<!--
CR069-DIVERGE.auditor.md — auditor lane file (track U owns). State derives from round numbers
here vs CR069-DIVERGE.architect.md (see PROTOCOL.md).
-->

# CR069-DIVERGE — audit lane (auditor)

**Item:** CR069-DIVERGE — HLAL/FTSE Shariah divergence monitor: fetch a second observation and
log where it disagrees with the AAOIFI/SPUS verdict on a name, log-only, never an enforcement
input. Chunk under the CR069 decomposition (chunk evidence list, not the CR-level DoD).

**Audited SHA:** `658fa2b`, tip of `lane/CR069-DIVERGE.coder.api` (not on main). Audited in an
isolated worktree `.claude/worktrees/audit-CR069-DIVERGE/`.

## Round 1

### Reproduced independently

| Check | Command | Result |
|---|---|---|
| Self-test subset | `uv run pytest tests/unit/ -q -k "diverge or halal or sharia"` | **61 passed, 928 deselected** (`uv sync --extra dev` first). Matches. |
| Full backend suite | `uv run pytest tests/unit/ -q` | **989 passed, 2 warnings** (131.44s). Matches exactly (CR069-BE/ROOM baseline 972/1036 depending on branch ancestry; this branch based off `2d95ee6` pre-ROOM, +17 new = 989). |

### Hard boundary 1 — never an input — verified with my own grep, not the AST test's word for it

`grep -rln "sharia_divergence" app/` → only `app/core/config.py` (the settings field) and the
module itself. Zero hits in `safety_floor.py`, `sim_engine.py`, `room_runner.py`, `mandate.py`, or
`app/api/`. The lane's own `test_module_not_imported_by_safety_floor` AST-parses only
`safety_floor.py`'s imports — my grep is broader (whole `app/` tree), so it isn't just trusting
that one file's guard to speak for the other three named surfaces.

**Mutation-tested the guard itself**, not just read it: inserted
`from app.services.sharia_divergence import HlalObservation` into `safety_floor.py`, reran
`test_module_not_imported_by_safety_floor` → **failed** with the expected assertion message.
Reverted (`git diff --stat` on `safety_floor.py` afterward: clean, no residue). The guard bites.

### Hard boundary 2 — no union, no intersection

Read `log_divergence`/`log_divergences` (`sharia_divergence.py:159-206`) directly: both only call
`aaoifi.resolve(ticker)` (a pure lookup on the existing `HalalUniverse`) and read
`hlal.compliant`/`hlal.available` off the separately-typed `HlalObservation` — no set arithmetic
combines the two anywhere in the module. `test_halal_universe_resolve_is_read_only_from_divergence_module`
confirms the AAOIFI universe is byte-identical before/after a batch comparison.

### Hard boundary 3 — HLAL unreachable degrades to no-observation, not a pause

`HlalDivergenceProvider.get()` (`:118-127`) catches `(httpx.HTTPError, ShariaSourceError)` and
returns `HlalObservation(available=False)` rather than propagating. Read
`test_provider_fetch_failure_yields_unavailable_not_an_exception` and
`test_provider_http_error_yields_unavailable_not_an_exception` bodies directly — both inject a
raising fetcher and assert `get()` returns cleanly with `available=False`. Non-vacuous: the
`try/except` is real, not a no-op catch of an exception type nothing raises.

### Live-fetch redirect fix — reproduced myself against the real URL, not the pasted transcript

```
no follow_redirects:      307, 0 bytes, content-type application/binary
follow_redirects=True:    200, 21675 bytes, text/csv; charset=utf-8
```
Ran the actual shipped `_default_fetcher()` (not a hand-rolled equivalent): **210 tickers,
as_of=2026-07-22**, `AAPL`/`META` present, `JPM` absent — matches the lane doc's numbers exactly.

**End-to-end, with a live AAOIFI fetch too** (`SHARIA_SCREEN_ENABLED=true` — off by default in this
worktree, same as every prior CR069 lane's local config): ran `default_halal_universe_async()` +
`HlalDivergenceProvider(...).get()` + `log_divergence()` together, live, for AAPL/META/JPM:

```
AAPL  aaoifi=pass          -> agree/no-opinion
META  aaoifi=screened_out  -> DIVERGENCE (log line emitted: ftse_compliant=True)
JPM   aaoifi=screened_out  -> agree/no-opinion
```

Byte-for-byte the same pattern the lane doc reports. Consistent with §3a's measured 47.9%
disagreement rate — META is exactly the kind of name that flips between standards.

### Config parity (CR040)

`backend/app/core/config.py:194` — `sharia_hlal_holdings_url` field present.
`docker-compose.yml:152` — `SHARIA_HLAL_HOLDINGS_URL: ${SHARIA_HLAL_HOLDINGS_URL:-<default>}`
forwarded into `api-alpha`. Present in the full-suite run's `test_config_compose_parity.py` pass.

### Scope discipline

`git diff --stat 2d95ee6..658fa2b` (the lane's single commit) → exactly 5 files: the new module,
`config.py`, `docker-compose.yml`, the new test file, the new CSV fixture. `HOT-FILES: none`
holds — no touch to `safety_floor.py`, `sim_engine.py`, `room_runner.py`, `mandate.py`, or the
verdict type (`schemas/sharia.py`).

### Findings

Zero BLOCKER, zero MAJOR, zero MINOR against this lane's own acceptance.

**Observation, not a finding against this lane (informational, forward-looking).**
`HlalDivergenceProvider.get()` caches on first success and never re-fetches unless a future caller
passes `refresh=True` — nothing in this module ever does, since it has no call site yet. That is
the exact shape of CR069-BE's own round-2 F2 (staleness never re-derived after process start),
minus the safety consequence: this monitor never gates a trade, so a stale FTSE snapshot at worst
produces a stale-but-harmless log line, not a wrong verdict. Zero live impact today (confirmed:
zero call sites anywhere in `app/`). Flagging for whoever picks up the deferred "wire a call site"
follow-on lane — they should give this provider the same per-call staleness re-derivation
`ShariaUniverseProvider.get()` now has, rather than reproducing F2 a second time in a new module.
Not minting a DEF — the module is dormant, so there is nothing failing yet, and the follow-on
lane's own assign is the natural place to carry this forward.

### Verdict

Every claim in the architect's hand-off independently reproduced: test counts (61/61, 989/989),
all three hard boundaries (boundary 1 mutation-tested, not just read), the live redirect-fix
(reproduced the raw 307→200 behavior AND the shipped fetcher's parse), the end-to-end divergence
detection on the same three tickers the lane doc cites, config parity, and scope (exactly the 5
files claimed, `HOT-FILES: none` holds).

**VERDICT: COMPLETE (round 1)**

Run report: [`../runs/2026-07-23_run-39/run_report.md`](../runs/2026-07-23_run-39/run_report.md)
