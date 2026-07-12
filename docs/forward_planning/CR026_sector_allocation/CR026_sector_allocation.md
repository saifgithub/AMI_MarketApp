# CR026 — Sector concentration enforcement + Portfolio-screen allocation chart

**Status:** proposed · **Session:** AT:R55 · **Date:** 2026-07-12
**Source:** migrated from `Silent_Scout/13_sector_allocation/` as part of closing and
deprecating Silent_Scout.

## What

A mandate compliance rule — sector concentration > 40% (default) — is locked in the
onboarding lifecycle spec but has **zero backend enforcement** and no Portfolio-screen
visualization. `safety_floor.py` (the deterministic PM safety floor) only checks
single-name concentration; there is no sector-level check anywhere in the codebase.
Confirmed still true as of 2026-07-12.

## Why

This is a real, unenforced compliance gap, not a nice-to-have — the mandate promises a
rule the backend doesn't check. More urgent under GTM (real users hitting real
mandate edges) than it was during initial research.

**Correction from the original Silent_Scout design:** the source docs (README +
`01_constraints/from_production.md`) cited a "Risk Analyst" / "Risk Agent" as the
consumer of sector-weight data, quoting `overlay_generator.py:198`. **That citation is
fabricated** — there is no Risk Analyst agent in the 13-agent roster
(`backend/app/schemas/agents.py:10-24`) and no `_risk_block()` function anywhere in
`overlay_generator.py`. This design corrects that: sector-weight data feeds the
**Portfolio Manager** (which already reasons about `risk_score`/drawdown in its
existing prompt injection) and the deterministic **`safety_floor.py`** compliance
check, not a nonexistent agent.

## Design (ported + corrected)

### Data source
`yfinance ticker.info.get('sector')` — GICS-style ~11 sectors, ~95% coverage on major
US exchanges, ~60% on OTC/micro-caps. `None`/missing → "Other" bucket, logged, never
errors. Cache indefinitely per ticker (sectors essentially never change) — same
never-raises pattern as `fundamentals.py`.

### Aggregation
```
allocate_by_sector(holdings, quotes) -> Dict[str, float]  # sector -> weight (0.0-1.0)
```
Sum `quantity × current_price` per sector, normalize by total portfolio value. Empty
portfolio → `{}`. No `SimHolding` schema change — fully computable from existing
holdings + a per-ticker sector lookup.

### Backend endpoint
`GET /v1/portfolio/sector-allocation` → `{allocation: {sector: weight}, total_value,
compliance: {max_sector, max_allowed, compliant}}`. `max_allowed` reads the mandate's
concentration tolerance (default 40%, per `lifecycle.md:120`).

### Compliance enforcement (the actual gap this CR closes)
Wire the same `allocate_by_sector()` computation into `safety_floor.py`'s deterministic
check, alongside the existing single-name concentration block — reject/flag a proposed
trade that would push any sector over the mandate's cap, the same way single-name
concentration is enforced today.

### Portfolio Manager data feed
Inject the computed sector-weight dict into the Portfolio Manager's prompt context
(not a Risk Agent — see correction above), so its verdict reasoning can reference real
sector exposure instead of guessing.

### Portfolio-screen chart
Donut/pie chart (`fl_chart`), 280px height, full width minus 48px margin, positioned
below the summary card (value/P&L/drawdown) and above the holdings list. Legend below
(color swatch + sector name + weight%). Sector→color mapping already spec'd (11 GICS
sectors + "Other"). Empty state: "No portfolio yet. Add a trade to see sector
allocation." Tap-to-filter deferred (nice-to-have, not blocking).

**Chart type note:** original design compared pie vs. horizontal stacked bar and
recommended pie for simplicity/familiarity, deferring bar to a later tier if sector
count grows past ~6. That recommendation still holds.

### Mandate-breach UI
When a sector exceeds the mandate cap, overlay a warning on the chart ("⚠️ Technology
(35%) exceeds your 25% mandate limit") — this is the UI-visible half of the
enforcement in `safety_floor.py`.

## Scope

**In:** aggregation function + endpoint, `safety_floor.py` sector-cap enforcement,
Portfolio Manager prompt injection, Portfolio-screen chart + legend + breach warning.
**Out:** tap-to-filter holdings by sector (future polish); per-security sub-industry
breakdown (GICS goes deeper than sector; not needed for the mandate rule as written).

## Acceptance

- `GET /v1/portfolio/sector-allocation` returns correct weights for a representative
  multi-sector test portfolio, `{}` for an empty one.
- `safety_floor.py` actually blocks/flags a trade that would breach the mandate's
  sector cap — this is the compliance gap being closed; needs a regression test that
  fails without the fix (mirroring the DEF039/DEF049 adversarial-test pattern already
  used in this codebase).
- Portfolio Manager prompt context contains real sector weights, not silence.
- Portfolio screen renders the chart + legend + breach warning when applicable;
  correct empty state; dark-mode-safe (all `AmiColors.*` tokens).
