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

**Two lanes launch in parallel with zero coder.api/models.py contention:**

| Item | Owner(s) | Dep | Why now |
|---|---|---|---|
| **DEF099** | `coder.api` | none | Unblocks anon-purchase M1. Account-merge must carry RC entitlement/credit. Service-only, **no schema** → no models.py collision. Top priority. **LANED + spawned.** |
| **CR029-MATH** | `coder.math` | none | Pure FIFO realised-P&L engine in `trading_math`. `coder.math` idle, zero backend dep. **LANED + spawned.** |

**Queued behind a coder.api slot (activate as DEF099 frees it — they touch schema/fundamentals so serialize):**
- **CR030** (`coder.api` BE: `ex_dividend_date`+`dividend_rate` on the earnings endpoint) → **CR030-MOBILE** (pill, DEPENDS-ON BE). Existing stub `CR030.assign.md` (OPEN).
- **CR029-BE** (`coder.api` schema owner: `lots` table + migration + wire FIFO into sim sell path, DEPENDS-ON CR029-MATH) → **CR029-MOBILE** (DEPENDS-ON CR029-BE).
- **CR006** (research doc, no fleet slot) — architect-led; can run anytime.

**→ /sm-checkpoint now** (before spawning/driving the rest) — the spawn+monitor+integrate phase is the context-heavy one; checkpoint keeps it inside budget.

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
- [x] Wave 1 laned — DEF099 (coder.api) + CR029-MATH (coder.math) dispatched, ASSIGNED round 1
- [x] **Wave 1 DONE** — **CR029-MATH** integrated (ACCEPTED, `bd2b68e`). **DEF099** audited **COMPLETE r1** (track-U run-50, zero findings) → integrated to main `c445c68` (AT:architect DEF099), full suite **1222 green**, DISPATCH: ACCEPTED, row open→resolved. coder.api WIP slot freed. (DEF099's live RC-alias hop still gated on DEF100 — Saiful's RC secret key.)
- [~] **Wave 1b IN PROGRESS** — **CR030-BE built** (dividend fields on `/v1/sim/earnings`; `EarningsInfo` +2 defaulted fields, `_dividend_fields_from_info` null-handling, yfinance provider populates from `Ticker.info`; small/reversible → architect-built + verified inline). **CR029-BE scope CORRECTED** (see below). Then their mobile halves + CR006 research doc.
  - **CR029-BE scope correction (2026-07-26):** the CR029 acceptance doc explicitly says **"no schema change"** — all inputs already exist in `sim_trades` (`side/quantity/entry_price/opened_at/closed_price/realised_pnl`). CR029 is a **pure read-time FIFO-lot reconstruction + per-lot display**, NOT a lots table / migration / sell-path change. So CR029-BE = a pure reconstruction service (`compute_lots_fifo` over `SimTradeRow`, consuming the shipped `trading_math.cost_basis.fifo_sell`) + one authenticated read endpoint + tests. **Reversible, no models.py, no sell-path change → GATE inline** (NOT independent; the underlying FIFO primitive was already audited via CR029-MATH). Owner `coder.api`. Must test the acceptance case (buy 100@150 + buy 50@155 + sell 60@160 → lot-1 partial close, correct realised-P&L split).
- [ ] Wave 2 laned
- [ ] Wave 2 integrated
- [ ] Wave 3 laned
- [ ] Wave 3 integrated
