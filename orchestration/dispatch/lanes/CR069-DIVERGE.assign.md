<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR069-DIVERGE — assign (HLAL/FTSE divergence monitor — log-only, never an input)

KIND: code
INSTANCE: coder.api
ACCEPTANCE: docs/forward_planning/CR069_sharia_compliance_indicator/CR069_sharia_compliance_indicator.md (§Phase 1 "no failover", §3a consequence 3)
DEPENDS-ON: CR069-BE — reuses its fetcher/cache shape for a second source.
GATE: spawned    <!-- recorded upfront at decomposition. Log-only, no user-visible output, no input to any verdict; a mistake is a redeploy away from fixed. Reversibility says spawned. If the diff comes back touching safety_floor.py or any render path, that is a different lane and this gate is void — escalate rather than proceed. -->
HOT-FILES: none expected — see the gate note above

**What:** Fetch HLAL (Wahed, FTSE Shariah USA) as a **second observation** and log where it disagrees
with the AAOIFI/SPUS verdict on a name a user holds or convenes. Nothing else.

**Why this is deliberately small.** §3a measured the two free sources disagreeing on **47.9% of
their union** (SPUS 216, HLAL 210, agree 146). That number is why a failover must never be built: it
would flip a user's observance verdict with no signal. This lane exists to make the disagreement
*visible* without letting it near the answer.

## Hard boundaries

1. **Never an input.** The HLAL set must not reach `safety_floor.py`, the verdict type, or any API
   response. If you find yourself passing it into an enforcement path, stop — that is the failover
   §3a forbids, arriving by accident.
2. **No union, no intersection.** Union is AMI's own invented standard (DEF084 with extra steps).
   Intersection is defensible as conservative but is likewise no published standard and would
   wrongly exclude 134 names some scholar body cleared. One named primary standard, full stop.
3. **Its failure is not the flag's failure.** If HLAL is unreachable, log that and carry on. The
   halal flag depends on SPUS only. A monitor that can take down the thing it monitors is worse
   than no monitor.

## Build

- Source: `https://docs.google.com/spreadsheets/d/1UC1Bk67bGuYsos_i8y_HQpNoHpVHAvqf71MbgrafJOQ/export?format=csv&gid=0`
  — HTTP 200, ~21.7 KB, 213 rows, identical Tidal schema to SPUS, same as-of date (measured
  2026-07-22). URL is config, not a literal; if it becomes a setting, forward it in
  `docker-compose.yml`'s `api-alpha` block or `test_config_compose_parity.py` fails the build.
- **Trap (measured):** `yfinance.funds_data.top_holdings` returns only **10 rows** for SPUS and HLAL.
  It is not a substitute for the CSV.
- Emit a structured log line on divergence: ticker, AAOIFI verdict, FTSE verdict, both as-of dates.

## Tests

Fixture-based, no network. Assert the monitor is **not** wired into enforcement — a test that fails
if the HLAL set is reachable from the verdict path is worth more here than any assertion about the
log format.

**Self-test:** `cd backend && .venv/bin/python -m pytest tests/unit/ -q -k "diverge or halal or sharia"`

## Delivery

Push to `lane/CR069-DIVERGE.coder.api`, never `main`. Hand-off:
`orchestration/dispatch/lanes/CR069-DIVERGE.coder.api.md` (`STATUS: READY_FOR_AUDIT (round 1)`) +
`orchestration/audit/cr/CR069-DIVERGE.architect.md` (`SUBMITTED: round 1`). Chunk evidence list, not
the DoD. Commit tag `(AT:coder.api CR069)`.

**Commit both hand-off files to the SHARED branch, not your lane branch** (DEF090) — source goes
to the lane branch; the lane files are shared coordination state and every board reads them on the
shared branch. A hand-off committed only to a lane branch is invisible to both boards and has
already stranded a finished round; an uncommitted one now renders `UNCOMMITTED` (DEF087).

**Deferred teaching surface.** The CR frames divergence as the "standards differ" teaching moment
(lesson `350_standards_differ_why_the_same_stock_flips`). Surfacing it to users is **not** in this
lane — that is user-facing content, it would change this lane's gate, and lesson content is G7/SME
territory. Log first; decide whether to teach from it later.

<!-- CR069-BE merged at bdc410f after VERDICT: COMPLETE (round 3). Dependency satisfied; assigned. -->
DISPATCH: ACCEPTED (round 1)

ASSIGNED: coder.api round 1
