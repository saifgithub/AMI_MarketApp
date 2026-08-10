# CR164 — Room backtesting harness (as-of mode on production infrastructure)

Filed 2026-08-10 (AT:R67). Status: in_progress. Plan approved by Saiful in-session 2026-08-10.

## What

A backtesting capability for the Room: run the real 12-agent Room "as of" a historical
date, on the app's own infrastructure, and score its verdicts against realized forward
returns. Primary metric: **outcome edge** — 1w/4w forward returns of the APPROVE set vs
the PASS set vs a per-date random-pick bootstrap null vs SPY.

## Why

CR035 measured cross-sectional *agreement* with the Street (κ=0.14 — essentially none)
and its own doc ruled full backtesting impractical at the time. Nothing yet measures
whether the Room's conclusions are *right*. The benchmark research lanes
(`docs/benchmark/claude/`, `docs/benchmark/kimi/`) did the power math (detecting +5pt
hit-rate edge needs n≈783 scored picks) and established the validity constraint: an LLM
backtest over dates before the model's training cutoff is invalid on its face. This CR
builds the harness that makes a *valid, limited* backtest possible — and, because it
runs on the production infrastructure, doubles as a standing regression instrument:
any prompt/agent/data-layer change is re-testable by re-running a pinned batch.

## Binding design rule (Saiful, plan review 2026-08-10)

**Same infrastructure as the main app.** No forked data layer, no parallel Room path.
As-of capability lands inside the production services as a first-class mode; the only
backtest-specific code is harness bookkeeping (sweep driver, run index, scoring report).

## Scope (locked decisions)

- **Staged:** ~130-convene pilot (gates below) → ~800–1000 full sweep.
- **News:** ablated in v1 via `field_state = UNAVAILABLE`; `news_archive` table reserved
  for a later historical-news arm (Alpha Vantage `time_from`/`time_to`, GDELT).
- **Social:** ablated (Adanos has no historical endpoint; CR035 arm-C precedent) — but
  per-run, never by env flip.
- **Fundamentals:** SEC EDGAR companyfacts point-in-time (filed-date-keyed) **in v1**.
  Reconstructable: trailing P/E, rev growth, margins, net cash, P/S, FCF yield, 52wk
  range, base price. Not reconstructable → UNAVAILABLE: forward P/E, PEG, analyst
  target/rating, next earnings.
- **Window:** post-model-cutoff only. A probe script finds the vLLM model's knowledge
  collapse month; `window_start = collapse + 8 weeks`; sweep and report refuse earlier
  as-of dates. No override flag.
- **Survivorship:** `tickers_150.txt` reused with a written membership audit
  (`backtest_universe_membership`); exclusion counts published verbatim.

## Architecture

See the approved plan (kept in Saiful's plan archive) — summary:

1. `AsOfContext` (`as_of`, `batch_id`, `arm`) in a ContextVar, set by
   `RoomRunner.start_run(..., backtest=...)` for the run's lifetime. Request-scoped;
   live Alpha untouched while a sweep runs.
2. `price_history_daily` (CR136) extended with OHLCV columns + `as_of` reads —
   the single price store for the Room, Portfolio Health, backfill, and scoring.
   As-of reads that find no real rows return None loudly → UNAVAILABLE, never mock.
3. `market_data.get_market_data_provider()` returns a store-backed adapter when an
   as-of context is active — `compute_technicals` becomes as-of-correct unchanged.
4. `fundamentals.fetch_fundamentals(ticker, as_of=None)` — one module, two modes,
   one output shape. EDGAR resolvers in `edgar_pit.py`, tag preferences in
   `edgar_tags.py`, ingest via `scripts/ingest_edgar_facts.py` (SEC fair-use throttle,
   required `--user-agent` flag; no new env vars).
5. Admin-only `POST /v1/admin/backtest/room-run`; dedup bypassed under backtest
   (idempotency via `UNIQUE(batch_id, ticker, as_of)` on `backtest_run_index`).
6. Sweep driver `scripts/backtest_sweep.py` (factored from `room_benchmark.py`),
   run inside the alpha container, resumable. Weekly-Friday as-of dates; entry =
   Friday adj_close; forward = +5/+20 trading days.
7. Scoring `scripts/backtest_report.py` — reads `backtest_run_index ⋈ room_runs`
   + the candle store only (byte-reproducible). Date-clustered block bootstrap;
   effective n ≈ #dates. Target/stop-hit gated on `level_provenance`, `ami_default`
   levels excluded.

## Leakage guards (structural — CR038: prompt instructions are not controls)

- (a) store-level `WHERE date <= :as_of` + post-query assertion → `AsOfLeakageError`;
- (b) post-run `llm_audit` prompt scan: any parseable date > as_of hard-fails; matches
  of actual post-as_of closes flagged. 100% of pilot prompts, 10% + flags on full;
- (c) model-cutoff probe fixes the window start; refusal is code, not convention;
- (d) all ablations ride `field_state` provenance gating, never prompt text.

## Acceptance

1. Unit tests: leakage raise on seeded post-as_of rows; UNAVAILABLE rendering of
   ablated fields; `run_date` renders the as-of date; live path behavior unchanged
   when no context is active (regression). All green under
   `pytest backend/tests/unit/ -q` on the sqlite fixture.
2. Pilot gate: zero `AsOfLeakageError`; 100% prompt-scan clean; completion ≥95%;
   verdict mix non-degenerate; EDGAR field coverage ≥~70%.
3. Full sweep completes with tranche-wise prompt scans; report re-run is byte-stable.
4. Report ships with the limitations register (no Sharpe; ~12% noise floor with an
   in-sweep repeat-run re-measurement; tested-Room ≠ live-Room ablation list;
   effective-n honesty; survivorship audit counts).
5. A pinned regression batch spec is committed and documented as the post-infra-CR
   re-test recipe.

## Explicitly out of scope

- Any Sharpe/portfolio/alpha claim (no SELL action, no portfolio — `docs/benchmark/claude/09` R1/R3).
- Pre-cutoff outcome claims, under any framing.
- Changing agent behaviour based on results (a later CR, evidence-gated).
- CR157's weekly retrospective of live user runs (separate CR, stays proposed).

## Results

Land under `results/` in this folder: batch JSONLs, cutoff-probe report, universe
audit, pilot gate report, final scored report.
