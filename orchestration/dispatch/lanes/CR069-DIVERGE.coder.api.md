<!-- dispatch lane file — coder.api-owned. CR052. -->
# CR069-DIVERGE — coder.api

STATUS: READY_FOR_AUDIT (round 1)

**Branch:** `lane/CR069-DIVERGE.coder.api` (base: `main` @ 2d95ee6, includes CR069-BE merge bdc410f)
**SHA:** `658fa2b`

## What and why

New, standalone `backend/app/services/sharia_divergence.py` — fetches the FTSE Shariah USA
Screened Index (via HLAL/Wahed) holdings CSV (same Tidal schema as SPUS) and logs a structured
line when it disagrees with an already-resolved AAOIFI/SPUS `ShariaVerdict` for a ticker. Reuses
`sharia_universe.parse_holdings_csv` and the DEF092 WAF-avoidance User-Agent for the second fetch.

**Dormant by design.** No call site wires this into `safety_floor.py`, `sim_engine.py`,
`room_runner.py`, `mandate.py`, the verdict type, or any API response — `HOT-FILES: none` on the
assign lane holds; the diff touches only the new module + `config.py` + `docker-compose.yml` +
tests/fixtures. Wiring a live call site is explicitly out of scope (assign lane's "Deferred
teaching surface" note) and left for a future lane.

**No union, no intersection.** `log_divergence`/`log_divergences` only ever read from the AAOIFI
`HalalUniverse` (a pure `.resolve()` lookup) and the HLAL observation; neither set is combined into
the other or into any new set that could be mistaken for a verdict.

**Live-fetch bug found in this round (not in the brief):** the Google Sheets `export?format=csv`
URL 307-redirects to a signed googleusercontent URL. A bare `httpx.Client` does not follow
redirects by default, so the fetcher as first written would have silently 307'd to an empty body
forever — the monitor would sit permanently "unavailable" with no error. Fixed with
`follow_redirects=True` on the real client; verified live (below). Same failure class as DEF089:
verified with different client behaviour than what ships.

## Config

`sharia_hlal_holdings_url` (new `Settings` field), forwarded in `docker-compose.yml`'s `api-alpha`
block (CR040 rule; `test_config_compose_parity.py` covers it — see test run below).

## Tests

**Self-test command and observed output:**

```
$ cd backend && .venv/bin/python -m pytest tests/unit/ -q -k "diverge or halal or sharia"
61 passed, 928 deselected in 4.19s          EXIT=0
```

**Full suite** (ran because the fetcher fix touches an httpx.Client construction path):

```
$ .venv/bin/python -m pytest tests/unit/ -q
989 passed, 2 warnings in 115.85s (0:01:55)          EXIT=0
```
(CR069-BE's post-merge baseline was 972; +17 new tests here, no regressions.)

**Live-source evidence** (real shipped `fetch_hlal_universe` + `HlalDivergenceProvider`, fetched
from the Mac, plain unauthenticated GET, generalizes to melehost):

```
without follow_redirects: HTTP 307, 0 bytes, content-type application/binary
with follow_redirects=True (the shipped fetcher): HTTP 200 | 21675 bytes | text/csv
  parsed: 210 tickers | as_of=2026-07-22
```

End-to-end through the real provider + a synthetic AAOIFI universe:

```
AAPL  aaoifi=pass          -> no divergence (agree)
META  aaoifi=screened_out  -> DIVERGENCE (HLAL/FTSE lists it compliant) — logged
JPM   aaoifi=screened_out  -> no divergence (agree)
```

Consistent with §3a's measured disagreement rate (both sources included META/JPM-shaped
disagreements in the 47.9%-of-union figure).

### Hard-boundary tests (the ones that matter most here)

- `test_module_not_imported_by_safety_floor` — AST-parses `safety_floor.py`'s imports (not grep,
  so a reformat can't hide a future import) and asserts `sharia_divergence` is never among them.
- `test_unreachable_second_source_yields_no_observation_not_a_pause` — HLAL fetch failure produces
  `available=False`, never an exception, never anything that could reach the AAOIFI flag's own
  pause state.
- `test_no_comparison_when_aaoifi_has_no_concrete_opinion` — UNKNOWN/UNAVAILABLE AAOIFI verdicts
  are skipped, not compared, since there's no AAOIFI ruling to diverge from.
- `test_halal_universe_resolve_is_read_only_from_divergence_module` — the AAOIFI `HalalUniverse`
  passed in is unchanged after a batch comparison.

## Could not verify — named, not omitted

1. **Not exercised on melehost.** The live fetch above ran from the Mac only, same caveat as
   CR069-BE's round-2 evidence.
2. **Google Sheets export URL's redirect target is not pinned.** If Google changes the export
   redirect shape, the fetch could start failing again; `follow_redirects=True` handles the current
   shape, not any future one. Not something a unit test can pin (the fixture-based tests
   deliberately never touch the network, per the assign lane's Tests section).
3. **No call site exists yet**, so there's nothing to verify about production log volume/rate on
   real holdings — that's true by design (dormant), not an oversight.

## Boundaries respected

- `HOT-FILES: none` — no diff outside the new module, `config.py`, `docker-compose.yml`, and
  tests/fixtures.
- No union, no intersection (checked above).
- `safety_floor.py`, the verdict type (`schemas/sharia.py`), and every enforcement call site are
  byte-for-byte unchanged.
