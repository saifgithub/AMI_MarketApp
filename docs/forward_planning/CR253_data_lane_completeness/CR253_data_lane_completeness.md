# CR253 — Data-lane completeness (Phase A)

Give every agent the data its own profile claims. Demand-ranked from 1,151
analyst GAPS lines across the CR251 matrix (aggregate over llm_audit,
2026-10-08). Ships with the CR252 fold-in so the CFA checklist's
SBC/ROIC/WACC instructions are executable on all 30 tickers.

## The four items

1. **Technicals breadth (lane A).** Bollinger bands (20-period SMA ± 2σ,
   population standard deviation, upper/lower/width_pct) and MACD (12/26
   EMAs seeded with the first-window SMA, 9-period EMA signal, histogram)
   computed in `app/trading_math/indicators.py` off the same daily bars
   `compute_technicals` already fetches, carried on `Technicals`, and
   rendered by `_bollinger_line`/`_macd_line` (room_prompts.py) to every
   technicals-lane agent — the Market Analyst first. A moving-average
   crossover SIGNAL remains uncomputed; the old "do NOT claim MACD or
   Bollinger" denials retired with the fields shipping
   (test_cr219_availability_guard.py R7 narrowed to the crossover claim).

2. **Rolling historical baselines (lane B(a)).** `app/services/ratio_baselines.py`
   persists one observation per (ticker, metric, calendar day) on every
   successful live read — put/call volume + open interest
   (`_overlay_put_call`), Reddit sentiment score + mention volume (social
   overlay) — and medians the trailing 90 days EXCLUDING today
   (`_MIN_BASELINE_DAYS = 5` floor). The put/call line gains a
   "trailing-90d baseline X (n daily reads on file)" companion per served
   half; the social detail block gains a `Baselines:` line. No fabrication:
   a young store renders "no baseline on file yet" (CR040). Backed by the
   `ratio_baselines` table (migration `c253a0ratio0base`); inserts are
   IntegrityError-handled upserts (failure_patterns P15).

3. **WACC estimate (lane B(b)).** `app/services/wacc.py`: CAPM cost-of-equity
   proxy — risk-free 4.2% (documented in-code constant standing in for ^TNX)
   + live beta × ERP 4.6% — emitted as `wacc_estimate_pct` beside ROIC in
   the fundamentals lane (`_overlay_wacc` + `wacc_estimate_line`), only when
   the sheet's own beta is live. No debt weighting is applied and the line
   says so. When ROIC is present and WACC is absent, the ROIC line's tail
   states the absence ("no WACC is sourced on this sheet") — never a
   fabricated hurdle. Kill switch: `ROOM_WACC_ENABLED`.

4. **D29 — disclosed SIC-group fallback** (`app/services/peer_basket.py`).
   `_PEER_GROUP_BY_SIC = {"3571": ("3571", "3572")}` pools candidates across
   the computer-hardware sibling SICs ONLY when the strict same-SIC screen
   lands fewer than `_MIN_PEERS` verified peers; every pooled candidate is
   still live-verified against its own submissions JSON; the basket record
   carries `group_sics` and the rendered line names "the disclosed peer
   group (SIC 3571/3572)". A strict success never widens.

## Envelope-presence re-ask guard

A live prose turn that produced no parseable stance envelope gets ONE
regeneration (`_attempt_envelope_repair`, room_runner.py) naming the
omission — same gateway/tier/timeout/constraint as the original call,
audited under its own `room_envelope_repair` flow (the scoring gate counts
base `room`-flow prose calls once per run, so the new flow name is safe).
Turns that already fell back to the scripted template are not re-asked; any
failure keeps the pre-CR253 state exactly. The PM path is untouched (PM
JSON is not envelope-based).

## Acceptance

- GAPS-demand re-run: the addressed lanes leave the top-30.
- D26 gate green; Jev figures-match on a sampled batch rises vs the frozen
  baseline.
- Suite: `test_cr253_*.py` (five new files) plus the touched guards
  (availability R7, prompt-data parity sentinels, fact-sheet census,
  P15 check-then-insert) all green; full `tests/unit` green.
