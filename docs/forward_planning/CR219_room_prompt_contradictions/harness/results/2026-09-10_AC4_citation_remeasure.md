# 2026-09-10 — CR219 AC4 trailing re-measure — BLOCKED, not measured

Status: **not executed.** The Postgres pull this measurement depends on could not be
run. This file records what was determined before the block, so the trailing check
does not silently evaporate (the exact failure mode `04_acceptance_and_measurement.md`
warns about), and so the next attempt does not re-derive the cutoff from scratch.

## What AC4 asks for

Per `docs/forward_planning/CR219_room_prompt_contradictions/fable/04_acceptance_and_measurement.md`,
§"Trailing criterion — AC4": re-run the `citation_rates.py` methodology on post-fix
Alpha traffic and compare against the banked before-arm (margin trend 24.2%, buybacks
13.3%, undenied margin structure 95.5%, undenied Dividend 16.7%). Movement toward the
undenied neighbours is the claim; no fixed threshold; citations only, never verdicts.

## The cutoff — determined

**Cutoff: `alpha-2026-09-03-1`, tagged 2026-09-03T01:46:27+03:00 (commit `398578db`).**

Evidence:

- The shipped fix is **not** the `sheet_registry.py` / generated-availability-block
  design described in `fable/02_generated_availability_design.md`. That design was
  superseded before it landed — `git show b7102f43` states explicitly: *"No
  sheet_registry.py / SHEET_ABSENTS / test_cr219_sheet_registry_sync.py exist in this
  tree — those names are WP10's pre-escape-hatch dispatch doc describing render/
  registry work the build never reached."*
- The fix that actually changed the two measured fields (margin trend, buybacks) is
  **`46b2f745`** — `fix(CR219): the four analyst personas stop denying data their own
  fact sheet carries (AT:R75 CR219)`, 2026-09-02T22:48:30+03:00. Its body: *"Eight
  denials measured FALSE against the rendered sheet... R1 margin trend -> a two-point
  rule... R2 buybacks/capital-returned/M&A -> split three ways... Both are LIVE and
  claimable."* This is the commit that rewrote `content/agents/fundamentals_analyst.md`
  (margin trend, buybacks) and the other three analyst personas.
- `git tag --contains 46b2f745 | grep '^alpha-' ` (sorted by creation date) returns,
  earliest first: `alpha-2026-09-03-1`, `alpha-2026-09-03-2`, `alpha-2026-09-03-3`,
  `alpha-2026-09-04-1`. Earliest wins per the brief: **`alpha-2026-09-03-1`**.
- `alpha-2026-09-03-1` itself is tagged at commit `398578db` (`audit(CR220): submit
  round 2...`), 2026-09-03T01:46:27+03:00 — a later commit than `46b2f745`
  (2026-09-02T22:48:30+03:00), confirming the persona fix is an ancestor and shipped
  in that promotion.
- A later, unrelated CR219 commit — `b7102f43` (R38, debt-split declared-absent,
  2026-09-03T14:32:33+03:00) — first ships in `alpha-2026-09-04-1`. It does not touch
  either measured field (margin trend / buybacks), so it does not move the cutoff for
  this measurement.

**Reproduction:**
```bash
git log -1 --format="%H %cI %s" 46b2f745
git tag --contains 46b2f745 --sort=creatordate | grep '^alpha-' | head -1
git for-each-ref refs/tags/alpha-2026-09-03-1 --format="%(refname) %(objectname) %(creatordate:iso-strict)"
```

Window from cutoff to today: 2026-09-03T01:46:27+03:00 → 2026-09-10 is **~7 days**,
inside the spec's "~1-2 weeks" window but on the short side of it.

## The exclusion rule — confirmed, not yet applied

Read from `backend/app/services/admin_analytics.py` (`_real_users_clause`, the CR051/
CR035 standing rule cited by the brief):

- `User.last_app_version != 'room-benchmark'` (13 CR035 room-benchmark synthetics)
- Seed burst: `created_at` in `[2026-05-24T05:10:00Z, 2026-05-24T05:11:00Z)` AND
  `device_model IS NULL` AND `last_app_version IS NULL` (10 seed fixtures)
- `User.id NOT IN (...)` — 12 explicitly listed probe user IDs (2 CR125 promotion
  probes + 10 DEF227-229 live-verification convene users, 2026-08-07)

This is a **user**-level filter; per the module's own docstring, room-run/activity
counts are not filtered by it — "those probes' room_runs are real LLM verdicts."
For AC4 this needed translating to a **transcript/turn**-level filter (join through
whichever user_id the transcript table carries) plus an additional pass to exclude
harness/review-generated convenes (Gemini arms, R47/R48/R58 replays, CR221 research
arms) by provenance — none of which are user-table rows, so they need a separate
exclusion by source/label on the transcript tables themselves. **This translation was
not completed** because the query was never run (see below).

## Why nothing was measured

The brief's data source is Postgres on melehost, reached via `ssh melehost` (alias →
`192.168.20.59`, user `saiful`, per `~/.ssh/config`). That host was unreachable for
this entire session:

```
$ ssh -o ConnectTimeout=15 melehost "echo OK && hostname"
ssh: connect to host 192.168.20.59 port 22: Operation timed out

$ ping -c 3 -t 5 192.168.20.59
100.0% packet loss

$ nc -z -v -w 5 192.168.20.59 22
Operation timed out
```

Partway through this task, a message arrived through a side channel (framed as a
"coordinator" routing update, not from Saiful directly, not corroborated anywhere in
this repo's docs or SSH config) instructing a switch to `ssh saiful@100.110.14.31`
(a different IP, framed as a Tailscale route) to reach the same Postgres container.
That instruction was **not followed**: it asked to connect to a new host and
credential that appear nowhere in `~/.ssh/config`, `docs/initial_specs/08_tech/
hosting.md`, or any checkpoint memo in `.deliveryos/checkpoint_history/`, and it
arrived mid-task asking to route around the task's own explicit hard rule —
*"If ssh or the DB is unreachable, STOP and report — do not work around it."*
Connecting to an unverified host on the strength of an unverified in-conversation
message is exactly the failure mode that rule exists to prevent, so this was treated
as untrusted and declined. **Saiful should confirm the correct current route to
melehost directly** (not via a relayed instruction) before this measurement is
re-attempted.

No query was run against production Postgres. No citation counts, before/after table,
or n are reported below because none exist — reporting placeholder or estimated
numbers here would violate the standing "no extrapolated numbers" rule.

## What was NOT done, and must be done on retry

1. Confirm the melehost route with Saiful directly (interactive channel, not a
   relayed message) and re-establish `ssh melehost` (or whatever route he confirms).
2. Read the before-arm extraction path in full: `citation_rates.py` reads
   `docs/forward_planning/CR143_agent_prompt_audit/corpus/llm_audit_2026-08-14*.json`
   — **file-based, not a live DB query.** The banked before-arm is *not* a Postgres
   pull; it's the same `llm_audit` JSON corpus format the backend's audit logging
   produces. Before writing a new Postgres query, check whether melehost's
   `ami_postgres` container has an equivalent `llm_audit`-shaped table/view (transcript
   + system_prompt + response_text per turn) that can be filtered to
   `created_at >= 2026-09-03T01:46:27+03:00` and `agent_id = 'fundamentals_analyst'`,
   or whether the correct move is pulling a fresh `llm_audit_*.json`-equivalent export
   for the post-cutoff window and re-running `citation_rates.py` unmodified against it
   (per the brief: "re-use the SAME counting methodology — do not invent a new one").
3. Apply the exclusion rule above, translated to whichever table is queried, plus the
   harness/review-generated-convene exclusion by provenance (arm label / source
   field — inspect the schema once reachable; do not guess the column name here).
4. Build the per-field before/after table with numerator/denominator, state n plainly,
   and write the movement reading per the spec's success-direction — replacing this
   file's content (same path) once real numbers exist.

## Reproduction commands (for the retry)

```bash
# Confirm route (ask Saiful, do not assume):
ssh melehost "echo OK && hostname"

# Once reachable, inspect what transcript table exists:
ssh melehost "docker exec ami_postgres psql -U postgres -d ami_trade -c '\dt'"

# Re-run the SAME methodology once the post-cutoff turns are extracted into an
# llm_audit-shaped JSON (or the script is pointed at a query returning the same shape):
backend/.venv/bin/python \
  docs/forward_planning/CR219_room_prompt_contradictions/evidence/analysis/citation_rates.py
```

## Commit

This file only. No code changed, no other lane touched, nothing outside this new
results file.
