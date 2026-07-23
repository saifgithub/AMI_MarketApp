<!-- audit-bridge lane file — written by coder.api, read by the Architect/auditor. CR005/CR052/CR070. -->
# CR069-DIVERGE — audit bridge

SUBMITTED: round 1

**Coder lane:** `orchestration/dispatch/lanes/CR069-DIVERGE.coder.api.md`
**Source branch:** `lane/CR069-DIVERGE.coder.api` @ `658fa2b`
**GATE:** spawned (per assign lane — reversibility: dormant, no call site, redeploy-away-from-fixed)
**ACCEPTANCE:** `docs/forward_planning/CR069_sharia_compliance_indicator/CR069_sharia_compliance_indicator.md`
(§Phase 1 "no failover", §3a consequence 3)
**DEPENDS-ON:** CR069-BE (merged `bdc410f`) — reused for its fetcher/cache shape only.

## What to verify

1. **Hard boundary 1 — never an input.** No import of `sharia_divergence` anywhere in
   `safety_floor.py`, `sim_engine.py`, `room_runner.py`, `mandate.py`, or any API response
   builder. Covered by `test_module_not_imported_by_safety_floor` (AST-based) in
   `backend/tests/unit/test_sharia_divergence.py`; worth an independent
   `grep -rn "sharia_divergence" backend/app` to confirm the test's own claim.
2. **Hard boundary 2 — no union, no intersection.** `log_divergence`/`log_divergences` only read
   `HalalUniverse.resolve()` and an `HlalObservation`; neither is combined into a new compliant set.
3. **Hard boundary 3 — HLAL unreachable degrades to no-observation, not a pause.**
   `HlalDivergenceProvider.get()` never raises past its own boundary (`test_provider_fetch_failure_yields_unavailable_not_an_exception`,
   `test_provider_http_error_yields_unavailable_not_an_exception`).
4. **Live-fetch fix.** The Google Sheets export URL 307-redirects; the coder found and fixed a
   missing `follow_redirects=True` on the real `httpx.Client` in `_default_fetcher`. Verified live
   against `settings.sharia_hlal_holdings_url` (210 tickers, as_of 2026-07-22) — evidence in the
   coder lane file. Worth re-running independently since URL redirect behaviour can't be pinned by
   a fixture test.
5. **CR040 config-forwarding.** `sharia_hlal_holdings_url` added to `Settings` and forwarded in
   `docker-compose.yml`'s `api-alpha` block; `test_config_compose_parity.py` passes.

## Evidence list (chunk-scoped, not the CR-level DoD table)

- **SHA:** `658fa2b` on `lane/CR069-DIVERGE.coder.api`.
- **Test command + observed output:**
  `cd backend && .venv/bin/python -m pytest tests/unit/ -q -k "diverge or halal or sharia"` →
  `61 passed, 928 deselected in 4.19s`, EXIT=0.
  Full suite: `.venv/bin/python -m pytest tests/unit/ -q` → `989 passed, 2 warnings in 115.85s`,
  EXIT=0 (post-CR069-BE-merge baseline 972; +17 new, no regressions).
- **Live evidence:** real fetch against `sharia_hlal_holdings_url` + end-to-end
  `HlalDivergenceProvider` + `log_divergence` run — see coder lane file for full transcript.
- **Contract re-verification:** N/A — no seam crossed; new module has no callers yet.
- **Could not verify:** melehost egress path unexercised; Google's redirect shape unpinned; no
  production log-volume data (dormant by design). Full list in the coder lane file.

## Reviewer notes (not findings — flagging for the auditor's attention)

- `HOT-FILES: none` on the assign lane holds: diff is `backend/app/services/sharia_divergence.py`
  (new), `backend/app/core/config.py`, `docker-compose.yml`, `backend/tests/unit/test_sharia_divergence.py`
  (new), `backend/tests/unit/fixtures/hlal_holdings_sample.csv` (new). Nothing in `room_runner.py`,
  `safety_floor.py`, `sim.py`, or `mandate.py`.
- The lane's "Deferred teaching surface" note (lesson `350_standards_differ_why_the_same_stock_flips`)
  is explicitly not addressed here — correct per the assign lane, flagging only so it isn't read as
  an omission.
