# Audit run report — 2026-07-31 run-11

ITEM: R65-BATCH1 · ROUND: 2 · VERDICT: COMPLETE
SHA: `b1c3b17f` (4 source/test files + 2 register rows over af0aeb77;
five round-1-cleared items confirmed untouched)
AUDITOR: track U (Kimi) · worktree `.claude/worktrees/audit-R65-BATCH1`

## M2 — closed, both directions

`except BaseException: release; raise` in `one_on_one.py` (and the
`brief.py` twin — scope judgment: upheld, shared counter, identical
class, 4 disclosed lines). BaseException correct: CancelledError
descends from it and leaks identically mid-spend. New test asserts via
the contract (next request at cap=1 → 200, not 429). Auditor mutation:
removed only the release line → exactly 1 RED (the M2 test), reverted
byte-identical, targeted 21/21 re-green. Known gap disclosed and
recorded: StreamingResponse-never-iterated leaves the generator's
finally unrun; structural fix would weaken the cap — left open
deliberately.

## M1 — closed per the deferral branch of round-2 scope

8 new tests: fixture-driven logic (incl. fail-closed on missing Mandate
schema and on unreachable host), non-vacuous scrape check, and a real
caller on every suite run (`get_openapi(app)` vs scraped client PATCH
keys) — gate logic now in CI via the beta workflow. NOT done (deferral,
Saiful's call, surfaced by the architect): the release-time `--base-url`
call in the 3 build scripts, still dirty under CR084-ALPHA. Nit: mirror
the deferral onto the DEF195 register row, as was done for the janitor
on DEF201.

## MINOR m1

Janitor accepted-not-fixed, recorded on the DEF201 row, wires at next
promotion (mount docker-compose.yml:258 verified committed in round 1).

## Measurements (all reproduced, detached at b1c3b17f)

| Check | Bridge | Auditor | Result |
|---|---|---|---|
| backend full suite | 1869/0 (+9) | 1869/0 (264.33s) | match |
| targeted DEF195+DEF201 | 13+8 | 21/21 | match |
| registers verify | DEF 205 / CR 130 | DEF 205 / CR 130 OK | match |
| mobile | untouched | round-1 results stand | — |

DoD enforcement waived per standing instruction.
