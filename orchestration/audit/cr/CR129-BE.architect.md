<!-- architect bridge — track R (bridged by coder.api per CR052 §6). CR052 / orchestration/audit/PROTOCOL.md. -->
# CR129-BE — architect bridge

ITEM: CR129-BE
INSTANCE: coder.api round 1
GATE: independent
SCOPE: chunk
BRANCH: `lane/CR129-BE.coder.api` @ `344e2b30` (from `main` @ `ee21def6`)
WORKTREE: `.claude/worktrees/coder.api-CR129-BE`
SUBMITTED: round 1

---

# Round 1

## The situation this bridge inherits

A prior `coder.api` instance built the full CR129 implementation (`502e96cf`, committed to this
branch) and was killed by its budget cap before writing either hand-off file or finishing
verification. I picked this branch up cold: merged `main` forward, read the assign and the CR129
README end to end, read `502e96cf` in full, then measured what was actually missing rather than
trusting the task briefing's own diagnosis of what was missing — one of its claims turned out to be
wrong (below).

## What was already correct in `502e96cf` (I did not touch or re-derive any of this)

- Five preset tables + `resolved_*` functions in `trading_math/risk_limits.py`, following BE1's
  established coalesce-at-read pattern.
- DEF187 closed: `safety_floor.single_name_cap_pct` reads `resolved_single_name_cap_pct` instead of
  the flat 50% backstop.
- `services/day_trader_preset.py`: explicit permissive overrides, no bypass flag, `risk_score`
  untouched.
- `services/risk_limit_backfill.py`: the CR040 disclosure-line builder for the structural backfill.
- `api/mandate.py`'s per-field journal diff loop extended to cover `sector_cap_pct`/
  `single_name_cap_pct` (closing DEF197) alongside the five CR129 fields.
- ~30 existing test files updated for the DEF187 tightening's expected fallout (e.g.
  `test_sim_engine.py` pinning `single_name_cap_pct=100.0` on tests that aren't about concentration).

## What I found missing, and built

**Acceptance 5 (Day Trader compliance/halal boundary) had zero test references** —
`day_trader_preset.py` existed, `DAY_TRADER_PRESET_OVERRIDES`/`is_day_trader_preset` existed, nothing
exercised them. Wrote 8 tests in the new `test_cr129_risk_limits_from_risk_tolerance.py`: every
override value asserted against the preset dict; a 95%-of-book buy passes under the preset (proves
the permissive side actually is permissive, so the compliance-still-blocks claim means something);
a halal-screened-out ticker still blocks with `blocked_by == "compliance"` and carries a
`ShariaVerdict`; blocklist, locale, and allowlist each independently still block; `risk_score` stays
in [1,5] and there is no `skip_floor` attribute anywhere on the mandate.

One iteration needed: my first `_day_trader_mandate` helper defaulted `halal=True` on every test,
which meant the locale/blocklist/allowlist tests all tripped the halal-universe-unavailable pause
(`blocked_by == "compliance"`) before their own check ever ran — `blocked_by` reports the FIRST
violation found, and halal is evaluated before locale in `check_mandate_compliance`'s ordering.
Fixed by defaulting `halal=False` and only enabling it (with a real `HalalUniverse`) in the one test
that's actually about halal. Caught this by running the new file before claiming it green, not by
inspection.

**Acceptance 3 (diversification-floor guard) had zero coverage.** `DIVERSIFICATION_FLOOR = 30` is
defined and never asserted. Built `_names_reachable(risk_score, max_drawdown_pct)` = `min(
max_open_positions, floor(open_risk_cap_pct / (single_name_cap_pct * assumed_stop_pct / 100)))`,
using the codebase's own standard 10%-below-entry stop-distance convention (the same one
`test_cr101_be2_new_risk_limits.py::test_total_open_risk_cap_sums_size_x_stop_distance` already
uses to turn a risk-budget cap into a position count). This reproduces the README's own "names
reachable" column EXACTLY for `base_mandate`'s `max_drawdown_pct=30`: 50/60/35/30/30, all >= 30.

I initially over-reached and added a second test asserting the guard holds across a RANGE of
`max_drawdown_pct` values (10/15/30/50/100), which failed at `max_drawdown_pct=10` (reachable drops
to 11 at risk_score=5). On inspection this isn't a bug — the invariant the assign and README state
is "for every risk_score", pinned against the documented table (which assumes the base 30%
drawdown ceiling); it says nothing about arbitrary user-chosen drawdown ceilings, and a user who
sets a genuinely tight 10% drawdown ceiling legitimately can't afford 30 fully-sized positions
without exceeding THEIR OWN stated risk budget — that's the ceiling working as intended, not a
diversification failure. Removed the invented test rather than either weaken the invariant or
misreport a false RED as a real defect.

**Acceptance 2 (full migration proof) was single-name-cap-only.** The existing
`test_migration_every_risk_score_now_enforces_the_new_single_name_value` (BE1's file, extended by
`502e96cf`) proves it for one of five fields. Added
`test_every_risk_score_resolves_all_five_limits_to_the_documented_table`, parametrized across all 5
risk scores, asserting all five CR129 fields resolve to the table's documented value — both with
the fields explicitly `None` and with them entirely absent from the stored dict (the real shape of
every one of the 13 live alpha mandates).

**Acceptance 7 (backfill journalling) had zero test references.** Added 3 tests against the live
PATCH endpoint + journal store: a CR129-field PATCH's summary names both the prior value (or
"following your risk profile" if unset) and the new one; the Day Trader preset PATCH gets its own
distinct summary ("Day Trader preset applied...") rather than falling into the generic diff line;
a second sequential PATCH's summary carries the PRIOR explicit value, proving this is a real diff
and not merely "something changed."

## The sim_reputation diagnosis — disclosing a correction to the task briefing

I was told these two failed in the full suite, passed in isolation (4/4), implying order-dependent
state, and told explicitly not to dismiss it as CPU contention or re-run to green. I ran them in
isolation FIRST, before any other change: **both FAILED alone**, with
`"position size 4.4% exceeds single-name cap 3.0%"` / `4.1%` respectively. This is not order-dependent
state — it's a real, direct DEF187-unification regression: the test builds its user via
`ensure_anonymous` (a default risk_score=3 mandate, no PATCH), then submits `quantity=1 AAPL market
order` against a $10k default sim portfolio. Pre-CR129 the floor's fallback was the flat 50%
backstop (always passed); post-CR129 it resolves to the ~3% risk-tier preset, and 1 share of AAPL is
~3-4% of the book. `502e96cf` already fixed this exact shape across 7 call sites in
`test_sim_engine.py` (pinning `single_name_cap_pct=100.0` on tests that aren't about concentration)
— `test_sim_reputation.py` simply wasn't in that sweep, because it builds its mandate through the
API/store default path rather than `hydrate_coach_mandate`. Fixed identically:
`get_mandate_store().patch(user_id, {"single_name_cap_pct": 100.0})` before each submit. Verified
green alone and in the full suite.

I'm flagging the correction explicitly rather than silently fixing it, because the task's own
framing ("don't dismiss as CPU contention, find the actual pollution source") assumed a shape of
bug this wasn't, and a future reader trusting that framing would look for cross-test pollution that
doesn't exist here.

## Mutation matrix — two mutations, both reverted after measurement, neither left mutated

| Mutation | Result |
|---|---|
| CLEAN | 1675 passed |
| M1 — `safety_floor.single_name_cap_pct` reverted to the pre-CR129 flat `SINGLE_NAME_ABSOLUTE_CAP_PCT` (50.0) fallback (undoing DEF187's closure) | **RED — 26**: `test_safety_floor.py::test_single_name_cap_falls_back_to_the_risk_tier_preset` + all 25 combos of `test_cr101_be1_settable_risk_caps.py::test_migration_every_risk_score_now_enforces_the_new_single_name_value` |
| M2 — `DEFAULT_MAX_OPEN_POSITIONS[5]` changed 30 → 99 (one preset value broken) | **RED — 3**: the new acceptance-2 parametrized test at risk_score=5, `test_preset_tables_carry_exactly_the_documented_five_scores`, `test_diversification_floor_guard_names_reachable[5-30]` |

Both mutations applied via `Edit`, measured with a scoped `pytest` run (not the full suite, to keep
iteration fast), then reverted; `git diff --stat` on the touched files confirmed empty before the
next step. No mutation returned a false green.

## Measured

| Check | Result |
|---|---|
| Full suite, repo root, foreground: `"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest backend/tests/unit/ -q` | **1675 passed, 0 failed**, 249.00s (baseline 1651 pre-merge/pre-fix per the assign; +21 new CR129 tests, +3 from the `main` merge — a lesson fix and a docs sweep didn't add backend tests, so the delta is CR129's own) |
| `git status --short` before every measurement | clean of anything but this lane's own tracked changes |
| `git merge main` | clean, no conflicts, 18 files (docs + config + the two files SEC-BATCH1/lesson-fix touched, none of them fenced for this lane) |

## What I have NOT established

- No manual/device check — backend-only, nothing promoted to Alpha.
- No live-LLM read of `DAY_TRADER_DISCLOSURE` through a real vLLM completion — asserted at the
  string/field level only, same limitation BE1's bridge disclosed for its own overlay lines.
- The Day Trader preset's outcome-instrumentation half (Barber-Odean/Taiwan baseline comparison) is
  explicitly out of scope — the README calls it out as a separate follow-up CR (CR131) needing
  trade-history aggregation and a comparison surface. Not built, not tested, correctly excluded.

## Found, NOT fixed

- Nothing new. The one correction (sim_reputation) was fixed within this lane's own fence
  (`backend/tests/unit/`), not a new defect requiring a mint.

## Fences honoured

- Did not touch `mobile/`.
- Did not touch `backend/app/api/llm.py`, `backend/app/api/auth.py`, `backend/app/middleware/`,
  `backend/app/services/oidc_verifier.py`, or `docker-compose.yml` (SEC-BATCH1's live files) —
  confirmed via `git diff --stat` against `main` before every commit.
- Did not widen `risk_score` — `test_day_trader_preset_is_not_risk_score_6_and_does_not_bypass_the_
  floor` asserts this directly rather than by inspection.
- Did not make compliance/locale/halal/allow-blocklist relaxable by the Day Trader preset — 4
  dedicated boundary tests, one per family member, not a single combined assertion that could pass
  on a coincidence.

## Definition of Done

| Row | Disposition |
|---|---|
| **Scope** | Round 1 (`502e96cf`, prior worker): 26 files, +766/-225 — the full feature. This round (`344e2b30`): 1 new test file (21 tests), 1 fixed test file (2 tests), 2 row files resolved, 2 generated tables rebuilt, this bridge + the lane hand-off. No new `backend/app/` source this round. |
| **Tests** | **1675 passed, 0 failed**, repo root, foreground. Two-mutation matrix, both RED, neither left mutated. |
| **Manual verification** | None available — backend-only, Mac is a pure editor. |
| **Docs** | This bridge, the lane hand-off (`CR129-BE.coder.api.md`), `DEF187.row.md`/`DEF197.row.md` → resolved, `CR129.row.md` → in_progress (CR129-MOBILE still open on DEF193), both `.md` tables regenerated via `gen_registers.py gen all` in the same commit as the row edits (DEF159). |
| **Commit tag** | `344e2b30` `(AT:R65 CR129 DEF187 DEF197)` on `lane/CR129-BE.coder.api`, pushed to origin. |
| **Register** | Row files + regenerated tables committed together; no hand-edit of either `.md` table. |
| **Scope discipline** | No deviation from the assign's own scope. One disclosed correction to the task briefing's diagnosis of the sim_reputation failures (real regression, not order-dependent pollution) — measured before asserting, not assumed. |
