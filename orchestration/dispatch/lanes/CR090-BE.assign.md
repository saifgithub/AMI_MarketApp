<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR090-BE — assign (meter live News/Social feeds via credit surcharge — coder.api core)

KIND: code
INSTANCE: coder.api
ACCEPTANCE: docs/forward_planning/CR090_live_data_feed_paywall/CR090_live_data_feed_paywall.md
DEPENDS-ON: — (CR039 credit infra + CR084-BE billing both LANDED; `credit_service.py` is FREE on main)
GATE: independent    <!-- D-5: real credit-spend / entitlement logic, cross-surface — same risk class as CR084 (money/entitlements). Verify adversarially: the surcharge only fires on ACTUAL live data; an entitled-but-broke user gets the LOUD "paid feature withheld" marker, never a silent synthetic substitution presented as business-as-usual (the DEF059 inversion trap). -->
HOT-FILES: `backend/app/services/credit_service.py` (coder.api owns — **FREE now**: CR084-BE landed f6f4cfd, its worktree is stale not live). · `backend/app/services/news_context.py` + `backend/app/services/social_context.py` (coder.api owns — the degrade path; add the 3-state marker). NOT `room_runner.py` / `room_prompts.py` / `agent_runner.py` (coder.room — the ROOM sub-lane consumes your contract). New test file under `backend/tests/unit/`.

## Design decided (Saiful 2026-07-26): SURCHARGE model — not per-agent rework

Room/1-on-1 keep their flat price; a live-data News/Social Analyst turn adds an **additive
surcharge, only when it actually fires with real data**. This lane builds the **coder.api core
+ the marker contract** the ROOM lane consumes. Do NOT change Room's flat base price.

## Scope — fixed by the Architect (load-bearing; not open)

**coder.api core ONLY.** The Room/1-on-1 wiring (charge the surcharge in `room_runner`, render the
disclosure header's third state) is **`coder.room` → CR090-ROOM (deferred, DEPENDS-ON this contract)**.
The "upgrade to unlock live data" mobile copy is **`coder.mobile` → CR090-MOBILE (deferred, copy only)**.
Do NOT touch the room cluster or Flutter here.

### 1. The surcharge cost (in `credit_service.py`)
Add a named constant + accessor beside `ROOM_COST_BASIC`/`room_cost_for_plan`:
```
LIVE_DATA_SURCHARGE = 2          # per live-data analyst turn (News, Social) — credits.md, tunable
def live_data_surcharge(n_live_analysts: int) -> int: ...   # e.g. both live -> 4
```
Documented default **+2 per live-data analyst** (Saiful-approved illustration: Basic Room 8 + News 2 +
Social 2 = 12). Keep it a constant so the figure is trivially adjustable; do NOT hard-code it inline at
call sites. Do NOT alter `ALLOWANCE`, `ROOM_COST_BASIC/PREMIUM`, or `_ROOM_COST_BY_PLAN`.

### 2. The 3-state marker (in `news_context.py` + `social_context.py`)
The degrade path today is BINARY (live vs synthetic-illustrative). CR023/CR024 already disclose the
synthetic block honestly, but that never distinguishes **"no data exists"** from **"data exists, you're
not entitled / short on credits."** Return an explicit enum/marker with **three** states:
- `LIVE` — real feed fired (this is what the surcharge is charged for).
- `WITHHELD_PAID` — live data *is available* but gated (entitlement/credits) → the loud "this agent's
  live feed is a paid feature" signal. **This is the new state.** Must be structurally distinct, not a
  prompt string (CR038 lesson: prompt instructions are not controls).
- `UNAVAILABLE` — genuinely no data (uncached ticker, provider down, quota exhausted) → the existing
  honest illustrative fallback.
Expose the marker on the context object each function already returns, so `room_runner`/`agent_runner`
(the ROOM lane) can branch on it. Keep the existing return shape backward-compatible (additive field).

### 3. Do NOT charge here
The actual `spend()` of the surcharge happens where the Room turn is priced — `room_runner.py`
(coder.room, the ROOM sub-lane). This lane only **exposes** `live_data_surcharge()` and the marker.
Provide a clean, documented contract in the hand-off so CR090-ROOM can wire it without guessing.

## Tests (new `backend/tests/unit/test_cr090_live_data_surcharge.py`)
- `live_data_surcharge(0)==0`, `(1)==2`, `(2)==4`; the constant is the single source of the figure.
- `ALLOWANCE` / `ROOM_COST_BASIC` / `_ROOM_COST_BY_PLAN` are **byte-unchanged** (assert values) — the
  surcharge is additive, it does not disturb existing pricing (a CR090 acceptance item).
- `news_context` / `social_context`: a real-feed path → `LIVE`; a gated path → **`WITHHELD_PAID`**
  (assert it is NOT `UNAVAILABLE` and NOT a silent synthetic — the DEF059 inversion guard); a
  no-data path → `UNAVAILABLE`. The existing binary callers still get a valid context (back-compat).
- Full backend unit suite green (`cd backend && uv sync --frozen --extra dev`, then
  `.venv/bin/pytest tests/unit/ -q`).

## Delivery
Push to `lane/CR090-BE.coder.api`, **never `main`**. Hand-off:
`orchestration/dispatch/lanes/CR090-BE.coder.api.md` (`STATUS: READY_FOR_AUDIT (round 1)`, and **spell
out the marker + surcharge contract** for CR090-ROOM) + `orchestration/audit/cr/CR090-BE.architect.md`
(`SUBMITTED: round 1`, adversarial notes: surcharge fires ONLY on real live data; `WITHHELD_PAID` is a
structural state not a prompt string; existing pricing byte-unchanged; back-compat preserved). Commit
tag `(AT:coder.api CR090)`.

ASSIGNED: coder.api round 1

DISPATCH: ACCEPTED

## Integrated (AT:R65, 2026-07-27)

Track-U VERDICT: COMPLETE (round 1), zero findings. Merged `cd292d3` to `main` @ `847d09c`,
re-verified independently post-merge (1260/1260, exit 0). CR090-ROOM + CR090-MOBILE remain
deferred, consuming this contract.
