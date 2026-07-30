# Run report — REL61 round 1 (2026-07-30, run-05)

Auditor: track U (Kimi). SCOPE release-bundle; audited merged `main` @
`06e12ba1` in `.claude/worktrees/audit-REL61` (detached, removed after).
Per the bridge: no full-suite re-runs (architect reproduced 1645/330); the
round went to seams. Tiered mechanics: targeted tests + probes + one mutation
re-check + one live measurement.

## Verdict

**COMPLETE** — zero BLOCKER, zero MAJOR. Seven-field × five-layer trace holds
for set users everywhere; the only unset-user divergences are DEF187/DEF193,
already minted and re-measured here with concrete numbers.

## Evidence

1. **Trace probe** (`/tmp/rel61_trace.py`, real resolvers + real overlay):
   SET user — floor `17.0`/`0.33`, overlay narrates `17.0%`/`33.0%`/`48.0h`/
   `7`/`3 / 9`/`2.5%`; all seven fields agree at UI/PATCH/store/floor/
   overlay. UNSET user — sector consistent (0.4 = 40.0%); single-name floor
   50.0% vs overlay 3.0% (~16.7x) = DEF187 (minted); BE2 five off/"not set"
   consistently.
2. **Sibling stability probe**: one-field PATCH moved zero siblings; explicit
   `null` and `0` survive `_deep_merge`; full-schema re-validation on persist.
3. **Consumer census** (attack 3): beyond floor + overlay —
   `room_prompts.py:420` (PM clamp, DEF187 participant),
   `sector_allocation.py:151-156`, `sizing.py` tables. None unaccounted.
4. **Mutation re-check (my BE2 M4)**: kwargs dropped at the live-PM
   `enforce_safety_floor` site on merged main → exactly **1 RED** (the
   tightened "active until"/"did not supply"-absent assertions). M4 closed
   for real. Reverted, tree clean.
5. **Targeted on merged main**: 52 backend (BE1+BE2 files) + 21 mobile
   (risk-limits files) — all pass; merges preserved lane behaviour.
6. **Live Alpha**: caught mid-restart (502 → "Up 3 minutes (healthy)"),
   then my own OpenAPI read confirmed all seven fields LIVE in the `Mandate`
   schema.
7. **0-vs-null chain**: no falsy coercion at any layer (Dart null-safe
   parse, dio explicit nulls, `"key" in updates`, merge preserves, floor
   `is not None`, overlay `is None`).

## Findings

- 3 MINORs: r1 unset BE2 overlay lines attach the mechanism suffix to
  "not set" (self-contradictory to an LLM reader — every unset user, the
  majority); r2 mandate-edit journal doesn't narrate the two BE1 caps
  (bare "Mandate updated."); r3 `0` = block-everything on six fields but a
  no-op on cooldown (doc note).
- Architect's invited opinion (client-shipped/backend-behind has no gate;
  `extra='ignore'` fails silently): **agreed, real hole, mint it** — the
  near-miss already happened on this very bundle (`0.1.0+61` uploading while
  Alpha lacked all seven). Suggested shape: mechanical OpenAPI-vs-client-keys
  check in the release path, not a procedural note.
- All four builder disclosures re-weighed and upheld (BE1 50% fallback,
  BE2 UTC basis + per-row pricing, MOBILE post-save audit + no-number
  rendering).

## Housekeeping

- Verdict lane, run report, trail row — committed by name, pushed,
  `origin/main` containment confirmed. Worktree removed; watcher relaunched.
