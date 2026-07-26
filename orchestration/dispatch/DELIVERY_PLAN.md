<!--
DELIVERY_PLAN.md — Architect-owned active delivery plan (CR052). The current wave plan for
the work Saiful greenlit. Durable across /compact — RESTORE reads this to resume. Supersede
in place when the wave set changes; archive prior versions in git history, not here.
-->

# Delivery plan — 2026-07-26 daily-review greenlights (9 items)

**Origin:** daily CR/Def review 2026-07-26 (ledger `4113d08`). Saiful greenlit 9 items,
directed: *"Plan the delivery of all 9 based on your best guess of logical sequencing.
Prioritize not-Blocked items. Prepare to use /sm-checkpoint in between."*

**Sequencing principles:** (1) not-blocked first; (2) `coder.api` is the bottleneck (6 of 9
want it, WIP cap 2) so its work serializes — spread everything else onto idle instances
(`coder.math`, `coder.mobile`) to parallelize; (3) hot-file serialization: `safety_floor.py`
(CR026) and `sim.py` (CR028, currently held by DEF094 @ READY_FOR_AUDIT) gate their lanes;
(4) cross-domain items split BE + mobile sub-lanes joined by `DEPENDS-ON` (BE lands first,
mobile re-verifies `fromJson` vs live JSON before audit). Auditor gate: `auditor.core` (do
NOT spawn — Saiful's self-respawning track-U). Global audit cap ≤3.

## Wave 1 — not-blocked, parallel (LAUNCH NOW)

| Item | Owner(s) | Dep | Why now |
|---|---|---|---|
| **DEF099** | `coder.api` | none | Unblocks anon-purchase M1. Account-merge must carry RC entitlement/credit. Top priority. |
| **CR029** | `coder.math` (+`coder.mobile` UI, DEPENDS-ON math) | none | FIFO realised P&L in `trading_math`. `coder.math` is idle — free parallelism. |
| **CR030** | `coder.api` (BE) + `coder.mobile` (pill, DEPENDS-ON BE) | none | Small: `ex_dividend_date`+`dividend_rate` onto the shipped earnings endpoint/pill. |
| **CR006** | architect / research (no fleet slot) | none | Non-code Beta infra cost-research doc. Runs alongside; consumes no coder WIP. |

Wave-1 WIP: `coder.api` = 2 (DEF099, CR030-BE) at cap · `coder.math` = 1 · `coder.mobile` = 2 (CR029-UI, CR030-pill) at cap. Fits.
**→ /sm-checkpoint after Wave 1 is laned + coders spawned (or after first integrations).**

## Wave 2 — dependency-cleared + moderate (after Wave 1 frees api/mobile slots)

| Item | Owner(s) | Dep / gate |
|---|---|---|
| **CR026** | `coder.api` (safety_floor extend) + `coder.mobile` (allocation donut) | DEF061 dep CLEARED (BE shipped). Reuses live DEF061 sector snapshot. Serialize on `safety_floor.py` — hold if CR069-MY / DEF061-ROOM still touching it. |
| **CR063** | `coder.mobile` | none — self-contained rules/league info screen. |
| **CR090** | `coder.api` | Soft-serialize after DEF099 settles the entitlement surface. Meter live news/social feeds, fail loud (CR040). |

**→ /sm-checkpoint after Wave 2.**

## Wave 3 — serialized behind in-flight hot files

| Item | Owner(s) | Dep / gate |
|---|---|---|
| **CR028** | `coder.api` (sim.py order type) + `coder.mobile` (UI) | Behind **DEF094** (holds `sim.py`, @ READY_FOR_AUDIT → integrate first). Trailing stop. |
| **CR065** | `coder.api` (streaks/reputation BE) + `coder.mobile` | Needs a recon pass first (spec vs code drift) — investigate, then lane the reconcile. |

**→ /sm-checkpoint after Wave 3 / on completion.**

## Not in these 9 but adjacent (do not lose)
- **DEF061-ROOM** + **DEF061-MOBILE** tails still open (MOBILE earns store build +56). CR031 reframed → evaluate onboarding TTS audio-reminder. CR002 needs Saiful re-decide next review.
- **Blocked-on-Saiful:** DEF100 (RevenueCat keys — nag), DEF104 (rotate live cred when convenient), CR027 (APNs/FCM certs).

## Status ledger (update as waves execute)
- [ ] Wave 1 laned
- [ ] Wave 1 integrated
- [ ] Wave 2 laned
- [ ] Wave 2 integrated
- [ ] Wave 3 laned
- [ ] Wave 3 integrated
