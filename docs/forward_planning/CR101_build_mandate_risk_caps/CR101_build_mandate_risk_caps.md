# CR101 — Build the Mandate risk caps the curriculum already teaches

**Filed:** 2026-07-27 · **Status:** proposed · **Decision:** Saiful, 2026-07-27 — *"create a CR for the caps. It will be build."*

## Why

The CR060 content sweeps found that a slice of the curriculum teaches Mandate constraints the product does
not actually have — the "phantom mandate" class:

- **DEF102** — ~6 lessons teach fields absent from `backend/app/schemas/mandate.py`
  (`cooldown_after_stop_minutes`, `max_open_positions`, `max_trades_per_week`, `max_sector_exposure_pct`,
  `total_open_risk_pct`, `max_single_factor_exposure_pct`).
- **DEF117** — ~26 of 193 daily challenges assume the same caps (21 position-size, 6 sector, 1 concentration,
  1 app-enforced cooldown, 3 max-trades). Whole "spot the violation" challenges hinge on them.

Rather than strip the content down to the product, **build the product up to the content.** These are genuine
risk-management features a training simulator should have; the curriculum was authored to the intended design.

## Scope (build team + audit lane — NOT the education lane)

1. **Schema** — add the fields to `Mandate` (`backend/app/schemas/mandate.py`) with sane bounds/enums, matching
   the existing style (e.g. `max_drawdown_pct` is a `Literal`). Decide each field's type and default.
2. **Enforcement** — deterministic checks in the PM compliance step, as a **hard floor** (the CR038 rule:
   prompt instructions are not controls — make it structural, like the halal floor). A trade breaching a cap is
   blocked with a named reason, same as `is_blocking` in the halal path.
3. **Derived → explicit** — reconcile the currently-DERIVED single-name cap (`risk_tier_cap(risk_score)` in
   `backend/app/trading_math/sizing.py`) with an explicit user-settable concentration cap; keep the risk-tier
   default as the floor.
4. **Overlay** — thread the new caps through `backend/app/agents/overlay_generator.py`.
5. **UI** — surface the caps in the Mandate screen (Settings → Mandate).
6. **Config parity** — anything env-gated forwards in `docker-compose.yml` (CR040 / `test_config_compose_parity`).

## Consequences for content (coordinate)

- **HALT the lesson-strip** of the DEF102 cohort (another lane began stripping 017/047/050/051). Once these
  fields exist, the original lesson content is correct — stripping would now be the regression. Reconcile any
  already-stripped lessons back to the built design.
- Once shipped, DEF102 + the DEF117 phantom-cluster flip from "wrong vs product" to "correct" — re-verify the
  cohort against the built schema and close.
- The `dc_2026_07_22` cooldown challenge specifically claims an *app-enforced* cooldown; lesson 047 teaches a
  *self-imposed* one. The build decides which is true — align both to whatever ships (enforced hard floor vs.
  journal-logged nudge).

## Acceptance

- New Mandate fields exist, validated, defaulted, and config-parity-clean.
- PM compliance blocks a breaching trade deterministically with a named reason; unit-tested.
- Overlay + Mandate UI expose the caps.
- DEF102 + DEF117 phantom cohorts re-verified green against the shipped schema.
