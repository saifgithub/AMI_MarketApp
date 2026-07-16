# DEF061 — 4 of 8 mandate compliance toggles are prompt-only; sim trades never check them

**Filed:** 2026-07-16 (AT:R59), source: prompt (CR036 deep-trace audit, sim/journal/mandate flows)
**Category:** compliance
**Severity:** high — a user-facing safety/values promise silently doesn't hold

---

## What's broken

Settings presents 8 mandate compliance toggles as hard per-trade filters
(`mobile/lib/screens/settings/settings_screen.dart:365-386`), e.g.:

- "No tobacco / alcohol / gambling" — *"Filters out tickers whose primary revenue comes from
  tobacco, alcohol, or gambling operations."*
- "No fossil fuels" — *"Filters out oil, gas, and coal producers..."*

The deterministic, uncoachable compliance check (`backend/app/agents/safety_floor.py::check_mandate_compliance`,
lines 90-169) — the function every sim trade and Room convene actually gates on — only
evaluates: `ticker_allowlist`, `ticker_blocklist`, `halal` (and only when a `halal_universe`
set is supplied), `locale_allowed_universe`, single-name position-size cap, and drawdown. It
**never reads** `mandate.compliance.esg_lite`, `no_tobacco_alcohol_gambling`,
`no_fossil_fuels`, or `custom_constraints`.

Those four fields are consumed in exactly one place: `overlay_generator.py:70-93`, which turns
them into LLM prompt text for Room agents to *narrate around*. Since `sim.submit()` /
`sim.preview()` never call an LLM — they go straight to the deterministic check — toggling "No
fossil fuels" on has **zero effect** on whether a sim trade in an oil major is accepted. A user
can enable the toggle, buy XOM in the simulator, and it fills without a single violation
flagged.

Confirmed enforcement order is otherwise correct (compliance check runs before persistence,
`sim_engine.py:452-471`) — this is specifically about which fields the check evaluates, not a
sequencing bug.

## Why this matters

This sits directly on the "safety floor is sacred" commitment
(`docs/initial_specs/10_delivery/project_plan.md` cross-cutting commitment #1) — the PM's
deterministic compliance check is supposed to be the uncoachable enforcement layer. Four of the
eight advertised constraints currently only exist as LLM narration, which is exactly the kind of
soft, coachable enforcement the safety floor exists to not be. For the halal-conscious AR/MS
launch markets specifically (`vision_and_positioning.md` — halal screening is called a
first-class differentiator), a Muslim user relying on "No tobacco/alcohol/gambling" as a hard
filter is not actually protected by it in the simulator today.

## Fix direction (not yet implemented)

Extend `check_mandate_compliance()` to evaluate `esg_lite`, `no_tobacco_alcohol_gambling`,
`no_fossil_fuels`, and `custom_constraints` the same way `halal` is checked — against a
supplied classification set/universe (mirroring the existing `halal_universe` parameter
pattern), since these are static per-ticker sector/industry classifications, not something to
compute from real-time data. Needs a source for the classification data (could reuse whatever
backs `DEFAULT_HALAL_UNIVERSE` in `sim_engine.py`, or a small per-ticker sector tag table) —
scoping that data source is the actual sizing question, not the check logic itself.

## Status

`open` — audit only this session, not fixed. Estimate: ~1 session once the classification-data
source is decided (a product/data question, not purely an engineering one).
