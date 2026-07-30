<!-- dispatch lane hand-off. CR052. -->
# CR129-BE — hand-off

STATUS: READY_FOR_AUDIT (round 1)

BRANCH: `lane/CR129-BE.coder.api` @ `344e2b30` (feature commit `502e96cf` by a prior worker,
merged `main` forward, then this finishing commit) — from `main` @ `ee21def6`
WORKTREE: `.claude/worktrees/coder.api-CR129-BE`

## Context — a prior worker was killed by its budget cap mid-verification

`502e96cf` (26 files, +766/-225) is the full CR129 implementation — five preset tables + resolvers
in `trading_math/risk_limits.py`, the DEF187 single-name-cap unification in `safety_floor.py`, the
Day Trader preset (`services/day_trader_preset.py`), backfill disclosure (`services/
risk_limit_backfill.py`), and the DEF197 journal-loop fix in `api/mandate.py`. It was already
committed and correct; this round finished what round 1 measured as missing and never got to write
up. I did not rebuild any of it.

## What I added this round

1. `git merge main` — picked up a lesson-code fix and a docs sweep that landed on `main` after this
   branch was cut. Clean merge, no conflicts.
2. `backend/tests/unit/test_cr129_risk_limits_from_risk_tolerance.py` (21 tests) — the four
   acceptance criteria that had zero or partial coverage. See the table below.
3. Fixed `test_sim_reputation.py`'s two failures — a real regression, not order-dependent state
   (see "the sim_reputation diagnosis" below).
4. Updated `DEF187.row.md` / `DEF197.row.md` to `resolved`, `CR129.row.md` to `in_progress` (BE done,
   MOBILE still open on DEF193), regenerated both `.md` tables.

## Acceptance, one line each

| # | Criterion | Result |
|---|---|---|
| 1 | Each of the five resolves from `risk_score` per the table; `None` follows the profile | ✅ pre-existing (`risk_limits.py` resolvers) + `test_every_risk_score_resolves_all_five_limits_to_the_documented_table` (new, parametrized 1-5, both explicit-None and field-absent-from-dict shapes) + `test_preset_tables_carry_exactly_the_documented_five_scores` (new, pins the raw dicts) |
| 2 | The inverted migration proof — every risk_score 1-5, every limit changes to the documented value | ✅ **was single-name-cap-only** (`test_migration_every_risk_score_now_enforces_the_new_single_name_value`, pre-existing) — extended this round to the other five fields, above |
| 3 | The "nobody is forced to concentrate" guard — reachable names >= 30, expected 50/60/35/30/30 | ✅ **had zero coverage.** `test_diversification_floor_guard_names_reachable` (new): reachable = min(max_open_positions, floor(open_risk_cap / (single_name_cap * 10%-assumed-stop))) — the codebase's standard stop-distance convention (same one `test_cr101_be2_new_risk_limits.py`'s own open-risk tests use). Exact match to the README's own "names reachable" column for `base_mandate`'s max_drawdown_pct=30: 50/60/35/30/30, every one >= `DIVERSIFICATION_FLOOR` (30). |
| 4 | DEF187 closed: one resolver, both paths | ✅ pre-existing (`safety_floor.single_name_cap_pct` → `resolved_single_name_cap_pct`), `test_single_name_cap_falls_back_to_the_risk_tier_preset` (pre-existing) |
| 5 | Day Trader preset: all seven permissive, compliance/halal still blocks | ✅ **had zero test references anywhere** — `day_trader_preset.py` existed, untested. 8 new tests: every override value asserted; a 95%-of-book buy passes (every user limit off/permissive, sanity check before the boundary claim means anything); a halal-screened-out ticker still blocks with `blocked_by == "compliance"`; blocklist/locale/allowlist each independently still block; `risk_score` untouched and no `skip_floor` attribute exists. |
| 6 | "Off" stays expressible | ✅ pre-existing (unchanged by this round — `Compliance`/field defaults already accept explicit 0/100/high-count overrides) |
| 7 | Backfill journalling: entry names the change | ✅ **had zero test references** — 3 new tests: a CR129-field PATCH names both old and new value (not "Mandate updated."); the Day Trader preset PATCH gets its own distinct summary naming the compliance carve-out; a second PATCH's summary carries BOTH the prior explicit value and the new one (not merely "changed"). |
| 8 | Mutations, including any that come back GREEN | ✅ both RED, honestly reported below — see "Mutation matrix" |
| 9 | Full backend suite green, repo root | ✅ **1675 passed, 0 failed** (baseline 1651 pre-merge/pre-fix; +21 new CR129 tests + 3 from the `main` merge) |

## The sim_reputation diagnosis — the task briefing's guess was wrong, and I'm saying so

I was told these two failed in the full suite but passed in isolation (4/4), implying order-dependent
state. I ran them in isolation FIRST, before touching anything else, and **both failed alone**:

```
FAILED test_sim_reputation.py::test_disciplined_buy_awards_points_once
       position size 4.4% exceeds single-name cap 3.0%
FAILED test_sim_reputation.py::test_buy_without_stop_or_target_awards_nothing
       position size 4.1% exceeds single-name cap 3.0%
```

This is a real, direct regression from the DEF187 unification, not pollution: `test_sim_reputation.py`
submits `quantity=1 AAPL market order` against a **default anonymous mandate** (risk_score=3, no
mandate PATCH at all) on a $10k default sim portfolio. Pre-CR129 the floor's fallback was the flat
50% backstop, so this always passed; post-CR129 the same mandate's single-name cap resolves to the
~3% risk-tier preset, and 1 share of AAPL is ~3-4% of the book — now correctly rejected on
concentration, which is not what either test is about.

This is exactly the shape `502e96cf` already fixed across `test_sim_engine.py` (7 call sites got
`"single_name_cap_pct": 100.0` added to their `hydrate_coach_mandate` calls) — `test_sim_reputation.py`
simply wasn't in that sweep because it builds its mandate through `ensure_anonymous` + the store
default, not `hydrate_coach_mandate`. Fixed the same way: `get_mandate_store().patch(user_id,
{"single_name_cap_pct": 100.0})` before each submit. Both tests pass alone and in the full suite now.

## Mutation matrix — two mutations, both reverted after measurement, neither left mutated

| Mutation | Result |
|---|---|
| CLEAN | 1675 passed |
| M1 — `safety_floor.single_name_cap_pct` reverted to the pre-CR129 flat `SINGLE_NAME_ABSOLUTE_CAP_PCT` (50.0) fallback, closing DEF187 back up | **RED — 26**: `test_safety_floor.py::test_single_name_cap_falls_back_to_the_risk_tier_preset` + all 25 combos of `test_cr101_be1_settable_risk_caps.py::test_migration_every_risk_score_now_enforces_the_new_single_name_value` (5 risk_score × 5 concentration_tolerance) |
| M2 — one preset value changed: `DEFAULT_MAX_OPEN_POSITIONS[5]` 30 → 99 | **RED — 3**: `test_every_risk_score_resolves_all_five_limits_to_the_documented_table[5-...]`, `test_preset_tables_carry_exactly_the_documented_five_scores`, `test_diversification_floor_guard_names_reachable[5-30]` |

No mutation returned green — every acceptance-2/3/4 test that should have caught its matching
mutation did.

## Measured

| Check | Result |
|---|---|
| Full suite, repo root, foreground, `"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest backend/tests/unit/ -q` (worktree has no own `.venv`; resolved from the main checkout) | **1675 passed, 0 failed**, 249.00s |
| `git status --short` before every measurement run | clean of anything but this lane's own tracked changes |
| `git diff --stat` after each mutation revert | empty — confirmed no mutation left in the tree before the next measurement |

## What I have NOT established

- No manual/device check — backend-only, nothing promoted to Alpha.
- No live-LLM read of the Day Trader disclosure copy (`DAY_TRADER_DISCLOSURE` in
  `day_trader_preset.py`) through a real vLLM completion — asserted at the string/field level only.
- The instrumentation half of the Day Trader preset (outcome vs. the Barber-Odean/Taiwan baselines)
  is explicitly out of scope per the README ("a separate follow-up CR" — CR131) — not built, not
  tested here, correctly.

## Fences honoured

- Did not touch `mobile/`.
- Did not touch `backend/app/api/llm.py`, `backend/app/api/auth.py`, `backend/app/middleware/`,
  `backend/app/services/oidc_verifier.py`, `docker-compose.yml` (SEC-BATCH1's files).
- Did not widen `risk_score` — Day Trader preset writes explicit overrides only, confirmed by
  `test_day_trader_preset_is_not_risk_score_6_and_does_not_bypass_the_floor`.
- Did not make compliance/locale/halal/allow-blocklist relaxable by any preset — proven by 4
  dedicated boundary tests, not merely asserted.

## Definition of Done

| Row | Disposition |
|---|---|
| **Scope** | This round: 1 new test file (21 tests), 1 fixed test file (2 tests), 5 doc/registry files (2 row files resolved, 2 generated tables regenerated, this hand-off pair). No `backend/app/` source touched this round — round 1's `502e96cf` is the source diff. |
| **Tests** | **1675 passed, 0 failed**, repo root, foreground. |
| **Manual verification** | None available — backend-only, Mac is a pure editor. |
| **Docs** | This hand-off, the architect bridge (`CR129-BE.architect.md`), `DEF187.row.md` / `DEF197.row.md` marked resolved, `CR129.row.md` marked in_progress (MOBILE still open), both generated tables rebuilt via `gen_registers.py gen all`. |
| **Commit** | `344e2b30` `(AT:R65 CR129 DEF187 DEF197)` on `lane/CR129-BE.coder.api`, pushed to origin. |
| **Register** | Row files + regenerated tables in the same commit (DEF159). |
| **Scope discipline** | No deviation from the assign. One correction to the task briefing's own diagnosis (sim_reputation), disclosed above with the measurement. |
