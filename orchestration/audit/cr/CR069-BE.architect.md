<!-- audit bridge — builder writes, auditor reads. CR069-BE. -->
# CR069-BE — audit submission (coder.api → auditor.core)

SUBMITTED: round 1
GATE: independent
BRANCH: lane/CR069-BE.coder.api  (origin; nothing pushed to main)
ACCEPTANCE: docs/forward_planning/CR069_sharia_compliance_indicator/CR069_sharia_compliance_indicator.md (§Phase 1, §Design constraints 1-4, §Guard, §Acceptance 1-3)

## What / why
Replace the 7-ticker `DEFAULT_HALAL_DEMO_UNIVERSE` placeholder (DEF084's allowlist-
masquerading-as-a-screen) with a **sourced** AAOIFI universe — the published
constituents of the S&P 500 Sharia Industry Exclusions Index (via SPUS's daily-
transparency holdings CSV), carrying its as-of date. Resolves **three** states
(pass / screened-out / unknown) with a parent-index (S&P 500 ETF) membership source,
degrades loudly, and ships the DEF084-specified guard that was never built.

## SHAs (in order)
- `fd0c717` — new `app/services/sharia_universe.py` (fetcher + cache + resolver) +
  `app/schemas/sharia.py` (ShariaStatus/ShariaVerdict) + config (4 settings) + compose parity.
- `1504621` — rewire all 5 enforcement sites + `ComplianceResult.sharia_verdict` +
  updated DEF084 copy guard / META-era tests to the Option-1 truth (not deleted).
- `c1a8706` — fetcher/parser/resolver tests + 2 CSV fixtures + the new CR069 guard.

## The five enforcement sites (all rewired; grep `halal_universe` proves closure)
| Site | Change |
|---|---|
| `sim_engine.py:80` | 7-ticker literal constant **removed** (comment replaces it) |
| `sim_engine.py:463,:624` | `… or DEFAULT_HALAL_DEMO_UNIVERSE` → `… or default_halal_universe()` |
| `api/mandate.py:274` (+import :33) | passes `default_halal_universe()` |
| `room_runner.py:1293` | **one line** → `halal = halal_universe or default_halal_universe()` (+ 1 import line, unavoidable for the rewire; coder.room's file otherwise untouched) |
| `safety_floor.py:144-153, :226-234` | both branches now resolve three-state via `HalalUniverse.resolve()` |

## Design seam (how three-state reaches every path incl. the Room's one line)
`HalalUniverse` **is-a `frozenset`** of the compliant tickers, carrying `parent_index`
+ `standard`/`source`/`as_of`/`stale` alongside. It substitutes into the existing
`halal_universe: set[str]` seam with **no signature change**, so the Room's single-line
rewire gets full three-state (not the two-state a bare set would force). `safety_floor`
duck-types `.resolve()` — a `HalalUniverse` → three-state; a bare `set`/`None` (tests
only) → the legacy conservative two-state.

## G3 (permit unknown) — the seam, deliberately
- UNKNOWN never reaches the violations list (`is_blocking` = SCREENED_OUT|UNAVAILABLE
  only), so a permitted-unknown trade is **accepted**.
- The disclosure still travels: `ComplianceResult.sharia_verdict` carries the
  ShariaVerdict (status + standard + source + as-of) on **pass AND unknown AND
  screened-out** — verified by `test_cr069_halal_guard::test_unknown_is_permitted_but_verdict_still_travels`.

## Guard — proven RED before the fix
`tests/unit/test_cr069_halal_guard.py`. Run at the base commit `45a13be` (pre-CR069):
```
ERROR collecting tests/unit/_tmp_cr069_red_proof.py
E   ModuleNotFoundError: No module named 'app.schemas.sharia'
1 error in 0.05s   (EXIT=2)
```
The sourced mechanism did not exist, so the guard cannot even import — a guard first
observed green would not be evidence. Green after the fix (see below).

## Tests + observed output
Self-test (assign §4 command):
```
pytest tests/unit/ -q -k "halal or sharia or mandate or safety_floor or config_compose"
→ 95 passed, 870 deselected, 1 warning in 8.13s   (EXIT=0)
```
Broader (modules I touched):
```
pytest tests/unit/test_sim_engine.py test_room_runner.py test_overlay_generator.py \
       test_def084_overlay_narration_copy_guard.py -q
→ 117 passed in 70.65s   (EXIT=0)
```
Fetcher acceptance (in `test_sharia_universe.py`): 219 tickers parsed, junk rows
(`003654100CVR`, `2602335D`) dropped, `BRK.B` kept, as-of `2026-07-22` extracted;
truncated body → `ShariaSourceError`; HTTP 500 → `httpx.HTTPStatusError`. No network:
injectable fetcher + checked-in fixtures (`spus_holdings_sample.csv` 219 rows /
`parent_index_sample.csv` 420 members).

META note (assign §4): today's demo set contained **META**, which AAOIFI/SPUS screens
out. No test asserted "META passes halal"; the failing tests asserted the old
"demonstration universe" copy — updated to the sourced truth, not deleted.

## Degrade-loudly (constraint 3) + config parity (CR040)
`sharia_screen_enabled` defaults **false** → `default_halal_universe()` returns a paused
universe (no network) → every halal trade blocks with a "screen paused" message rather
than silently using the retired 7-set. Fetch failure / stale-beyond-window → same paused
state. 4 new settings forwarded in `docker-compose.yml` api-alpha block;
`test_config_compose_parity` green.

## Boundaries respected
- `trading_math/screening.py` (`sharia_screen()`) NOT wired — sourced allowlist only
  (constraint 4). No SHARIA lesson / ARB / `settings_screen.dart` edits (CR069-MOBILE).
- No 33→30 threshold change (G7, SME-gated).

## Could-not-verify / named partials (not omitted)
1. **Agent-narration provenance (§Acceptance 4, the Room-prompt side).** The verdict
   now carries provenance and `ctx.halal_universe` is a full `HalalUniverse` on the Room
   path, so the data is *available* to the agents. But the actual prompt wording is
   rendered in `agents/overlay_generator.py`, which is **coder.room's file** (room
   cluster) and NOT in my HOT-FILES — I could not edit it. It still emits the generic
   DEF084 "curated demonstration universe" text and does not yet render the sourced
   standard/as-of. **A CR069-ROOM lane is needed** to render `ShariaVerdict` provenance
   into the 12 overlays. Flagging for the Architect — there is no such lane filed yet.
   (§Acceptance 4 is a post-promotion live smoke, not this lane's unit gate.)
2. **Live SPUS/IVV fetch not exercised.** Per the no-network-in-tests rule the fetchers
   run against fixtures only. The real URLs are config; the feature is off by default and
   pauses loudly until `SHARIA_SCREEN_ENABLED=true` + a verified fetch on Alpha.
3. **Full 948-test suite** not run here (auditor's job); targeted subsets above are green.

## Commit tag: (AT:coder.api CR069). Completion verified by git + pytest exit 0, not by prose.
