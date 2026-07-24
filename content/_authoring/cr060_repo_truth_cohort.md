# CR060 — repo-truth cohort: lessons teaching a Mandate vocabulary the product doesn't have

Produced by the deterministic repo-truth auditor (`content/_authoring/repo_truth_check.py`,
CR060 Phase 6). Ground truth is `backend/app/schemas/mandate.py` + a grep of `backend/app/`.

**Finding.** 30 lessons instruct the user to set, or narrate the PM checking, a Mandate field
that does not exist in the schema. `max_position_pct` alone appears 39 times. The densest cluster
is the Level-12 "how AMI works" module (269–279) — the lessons whose entire job is describing the
product correctly. A user who follows a "Try it" task here (*"Open the Mandate editor and set
`max_risk_per_trade_pct` to 1"*) cannot find the field. This is a CR040 degrade-loudly failure in
the curriculum: confident instructions to configure things that silently aren't there.

**Why the LLM sweep missed some of it.** This class is *mechanically decidable* — a field name
either is in the schema or isn't. The verification agents didn't hold the schema, so they scored
several of these lessons VERIFIED. The deterministic scan caught **4 lessons the sweep marked
clean** (`014`, `050`, `076`, `109`) that would otherwise have been stamped `verified:` carrying a
false product claim, and it promotes **5 lessons from P2a → P1** (`017`, `019`, `049`, `242`,
`253`) whose phantom field is a repo-truth defect, not genericizable prose. This is the DEF083
lesson restated: *for a mechanically-decidable class, a deterministic scan beats an LLM.*

## The real schema (what a user can actually set)

`Mandate`: `risk_score` (1–5), `max_drawdown_pct` (Literal 10/20/30/50/100), `long_only`,
`liquid_only`, and `compliance` booleans (`halal`, `esg_lite`, `no_fossil_fuels`,
`no_tobacco_alcohol_gambling`), plus `ticker_blocklist` / `ticker_allowlist` /
`custom_constraints`. The single-name **cap is derived, not set**: `risk_tier_cap(risk_score)` =
`{1:1.5, 2:1.5, 3:3.0, 4:4.5, 5:4.5}`% (`trading_math/sizing.py`), computed internally by
`_max_position_pct(risk_score)` in `overlay_generator.py`. By design (CR046) the user sets the
*risk score*, and the cap falls out of it — so exposing `max_position_pct` as a settable field
contradicts the architecture, it isn't just a missing feature.

## Two sub-classes

### A — DESIGN: contradicts the existing architecture → clear content fix

The real construct already exists; the lesson just names it wrong. Fix by aligning:

| phantom | real construct |
|---|---|
| `max_position_pct`, `max_single_name_notional_pct` | `risk_score` (cap derives via `risk_tier_cap`) |
| `max_risk_per_trade_pct`, `max_per_trade_risk_pct` | `risk_score` (1–5) |
| `pause_at_drawdown_pct` | `max_drawdown_pct` |
| `region_allowlist` | `ticker_allowlist`/`ticker_blocklist` + locale |

### B — SCOPE: a coherent "richer mandate" the lessons assume but the product lacks → **decision**

`cooldown_after_stop_minutes`, `max_open_positions`, `max_trades_per_week`,
`max_sector_exposure_pct`, `total_open_risk_pct`, `max_single_factor_exposure_pct`. These aren't
architecture mistakes — they're a plausible richer Mandate (cooldowns, position-count limits,
sector caps) the emotional-discipline + risk-budgeting lessons (`047`, `050`, `051`, `109`, `204`,
`205`, `017`) teach as if it shipped. **Fork — Saiful's call:** either the Mandate *gains* these
fields (a CR to build them, and the lessons become correct) or the lessons stop teaching them (a
content fix). I can't resolve this by genericizing — it's product scope, not accuracy. Filed as a
CR candidate; the accuracy-preserving default until decided is to align these lessons to the
current schema.

## The 30 lessons

| lesson | class bucket | sub | phantom tokens |
|---|---|---|---|
| 012_why_most_traders_fail | P1 | A | max_position_pct |
| 014_position_sizing_basics | **swept-clean → P1** | A | max_risk_per_trade_pct |
| 017_portfolio_exposure_and_correlation | **P2a → P1** | B | max_single_factor_exposure_pct |
| 018_drawdown_management | P1 | A | pause_at_drawdown_pct |
| 019_survival_mindset | **P2a → P1** | A | max_risk_per_trade_pct, pause_at_drawdown_pct |
| 047_revenge_trading | P1 | B | cooldown_after_stop_minutes |
| 049_overconfidence | **P2a → P1** | A | max_per_trade_risk_pct |
| 050_boredom_trading | **swept-clean → P1** | B | max_trades_per_week |
| 051_discipline_vs_excitement | P1 | A+B | cooldown_after_stop_minutes, max_open_positions, max_per_trade_risk_pct, max_trades_per_week |
| 072_what_ami_can_do_for_you | P1 | A | max_position_pct |
| 074_ai_hallucinations_and_amis_safety_floor | P1 | A | max_position_pct |
| 075_the_risk_of_overreliance | P1 | A | max_position_pct |
| 076_human_oversight_is_the_product | **swept-clean → P1** | A | max_position_pct |
| 109_risk_budgeting_across_positions | **swept-clean → P1** | A+B | max_sector_exposure_pct, max_single_name_notional_pct, total_open_risk_pct |
| 110_tail_risk_and_fat_tails | P1 | A | max_single_name_notional_pct |
| 111_gamblers_ruin_and_the_one_percent_rule | P1 | A | max_risk_per_trade_pct |
| 204_sixty_minute_rule | P2b | B | cooldown_after_stop_minutes |
| 205_sector_switching_revenge | P1 | B | cooldown_after_stop_minutes |
| 242_late_bull_warning_signs | **P2a → P1** | A | max_position_pct |
| 248_vix_term_structure | P1 | A | max_position_pct |
| 253_mandate_adjustments_by_regime | **P2a → P1** | A | max_position_pct |
| 269_analysts_gather_researchers_debate | P1 | A | max_position_pct |
| 270_why_the_pm_is_structurally_separate | P1 | A | max_position_pct |
| 271_inside_the_deterministic_compliance_check | P1 | A | max_position_pct, region_allowlist |
| 272_the_mandate_is_your_contract | P1 | A | max_position_pct, region_allowlist |
| 273_uncoachable_means_no_prompt | P1 | A | max_position_pct |
| 274_the_safety_floors_audit_trail | P1 | A | max_position_pct |
| 277_pass_is_not_buy | P1 | A | max_position_pct |
| 279_you_are_the_ceo | P1 | A | max_position_pct, region_allowlist |
| 355_how_amis_halal_flag_maps_to_real_screening | REPO_TRUTH (DEF097) | — | DEFAULT_HALAL_DEMO_UNIVERSE |

Filed as **DEF098**. The guard (`repo_truth_check.py`) becomes a corpus pytest once this cohort is
cleared — guard lands with the fix, per `docs/initial_specs/08_tech/failure_patterns.md`.
