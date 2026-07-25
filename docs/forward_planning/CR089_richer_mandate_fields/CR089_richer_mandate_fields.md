# CR089 — Richer Mandate fields (cooldowns, position/trade-count limits, sector caps)

**Status:** proposed · **Not MVP.** · **Session:** AT:daily-checkin · **Date:** 2026-07-25
**Source:** spun off from [DEF102](../../defect/DEF102_lessons_teach_phantom_mandate_fields/)'s
class-B SCOPE fork.

## What

DEF102 found 30 lessons teaching a Mandate vocabulary the product doesn't have. Most of
it was a naming mismatch (class A — the lesson names the wrong field for a real
mechanism, e.g. `max_position_pct` instead of `risk_score`). A smaller set — the
emotional-discipline and risk-budgeting lessons (`017`, `047`, `050`, `051`, `109`,
`204`, `205`) — assumed a genuinely richer Mandate that was never built:

- `cooldown_after_stop_minutes` — a self-imposed no-new-entries window after a stop-out
- `max_open_positions` — a position-count ceiling
- `max_trades_per_week` — a trade-count ceiling
- `max_sector_exposure_pct` — a per-sector risk ceiling
- `total_open_risk_pct` — a portfolio-level open-risk ceiling
- `max_single_name_notional_pct` — a dollar-weight concentration ceiling (distinct
  from the existing risk-based `risk_tier_cap`)
- `max_single_factor_exposure_pct` — a correlated-cluster exposure ceiling

None of these exist in `backend/app/schemas/mandate.py`, and none are enforced by
`safety_floor.py`. Today the safety floor only mechanically enforces: `risk_score`
(→ derived single-name position cap), `max_drawdown_pct`, the compliance booleans
(`halal`/`esg_lite`/`no_fossil_fuels`/`no_tobacco_alcohol_gambling`), `long_only`,
`liquid_only`, and `ticker_allowlist`/`ticker_blocklist`.

**2026-07-25 decision (Saiful, daily check-in `AskUserQuestion`):** rewrite the seven
lessons to match the current schema now (done same session — they reframe these
concepts as self-imposed, journal-tracked discipline rather than app-enforced rules),
**and** file this CR to track the build path. **Explicitly not MVP** — no lane, no
build commitment; revisit after MVP ships.

## Why

The seven lessons' underlying pedagogy (revenge-trading cooldowns, boredom-trading
trade caps, sector/factor concentration risk) is genuinely good content — the gap is
that AMI's safety floor doesn't yet give the user a mechanical backstop for any of it
beyond position size and drawdown. Building these fields would let the safety floor
enforce what the curriculum already teaches, closing that gap structurally instead of
relying on the user's own discipline (which the rewritten lessons are honest about
being the *current* mechanism).

## Scope (draft — needs real design work before this is buildable)

**In (candidate):**
- Extend `Mandate`/`Compliance` schema with the fields above (naming needs proper
  design, not a literal port of the lesson vocabulary).
- Extend `safety_floor.py::check_mandate_compliance()` to enforce cooldown, position/
  trade-count, sector, total-open-risk, and notional-concentration ceilings.
- Settings UI to set each ceiling; Room/1-on-1 prompt surfaces to narrate them
  (mirroring the existing per-ticker size-cap narration).
- Cooldown specifically needs a stateful "reject an order for N minutes after a
  stop-out" mechanism — new territory, not just a static check like the others.

**Out / needs a decision before scoping further:**
- Sector taxonomy source (yfinance `sector` field, a curated mapping, GICS licensing —
  unresolved, same class of question CR069 hit for Sharia sector screens).
- Whether cooldown blocks order *submission* (hard reject) or only *narrates* a
  warning (soft, PM-flagged) — a real UX/trust decision, not just a technical one.
- Interaction with existing `risk_tier_cap` (is `max_single_name_notional_pct` a
  second, independent cap, or does it replace/complement the risk-based one?).

## Acceptance

Not defined — this CR is a placeholder marking the SCOPE fork's build path as tracked
and deliberately deferred. A future session that picks this up should re-scope it
properly (probably split into per-field sub-CRs, similar to CR069's decomposition)
rather than build it as written here.
