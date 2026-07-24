<!--
Auditor run report — run-44 (2026-07-24, session auditor.core/track U). Round-1 audit of
CR087-MOBILE. Audited SHA 89e4528 on lane/CR087-MOBILE.coder.mobile. Verdict COMPLETE. Owner: AUDITOR.
-->

# run-44 (round 1) — CR087-MOBILE lesson locale threading + RTL → COMPLETE

- **Auditor session:** auditor.core (track U), 2026-07-24. Picked off the run queue right after
  GTM M1 (CR084-BE/MOBILE) fully cleared.
- **Audited SHA:** `89e4528`, tip of `lane/CR087-MOBILE.coder.mobile` (branched from merge-base
  `c8eae6e`, zero divergence from current main). Audited in a fresh isolated worktree
  `.claude/worktrees/audit-CR087-MOBILE/`.
- **The item:** thread the active content locale into both the lesson catalogue fetch and the
  lesson-detail fetch, and fix 4 hard-coded-LTR spots so the AR lesson body + quiz render RTL.
  Makes CR083's 312 AR-translated lesson bodies reachable end-to-end.
- **Gate:** independent (D-5 — store-facing, ships to public TestFlight/Play per a CEO-approved
  timing deviation from the "AR + MS at v1.0" decision log).
- **Verdict:** COMPLETE (round 1) — zero BLOCKER, zero MAJOR, zero MINOR.

## An unusual dependency situation, checked first

`DEPENDS-ON: CR087-BE`, but `git branch -a` shows **no `lane/CR087-BE.coder.api` branch exists
anywhere** — the backend half hasn't started building. This lane is legitimately verifiable
standalone (CR087-BE only changes string *values* + adds a query param, not the response shape),
but it means the coder's own "contract re-verify against real backend JSON" could only have been a
static schema comparison. I redid that comparison independently rather than accept it as stated.

## Verification

### Reproduced independently

| Check | Result |
|---|---|
| Scope | 5 files, +352/−9, all under `mobile/`. Zero main divergence. |
| Analyze | 4 pre-existing infos, none touched. |
| Test suite | 76 passed, exit 0. |

### Focus #1 — locale reaches both wires — the one mutation test this audit ran

Confirmed at source: both the catalogue refresh and the reader load read the identical
`contentLocaleProvider`; both API client methods put `locale` in the actual query string. Then
reproduced the **exact bug the coder says the spec had wrong** by reverting the catalogue call to
drop its locale argument — the `catalogue fetch carries the active locale` test went RED
immediately (`['en','en']` instead of containing `'ar'`), cascading into 4 more failures. This is
the single failure mode the architect named as most dangerous (list-in-EN / detail-in-AR split),
and it's now proven caught by the suite, not merely claimed fixed. Reverted.

### Focus #2, #3, #4

`null` → `'en'` derivation read at source, matches its own doc comment and passing test. All 4 RTL
diff hunks are faithful directional conversions; grepped the whole lessons screens tree for
survivors — none; the RTL test asserts real `Directionality.of(ctx)`, not string presence.
Independently verified the coder's one disclosed out-of-scope item (a catalogue list-tile padding,
not the reader) is accurately characterized and genuinely outside this lane's spec-scoped
acceptance. Redid the `fromJson` ↔ `schemas/lessons.py` field-by-field comparison myself — every
consumed field maps 1:1; the one backend field the client never reads (`locale_versions`) is
completely absent from the mobile model, not defaulted around; no fabricated-translation pattern
anywhere in the diff.

## Findings

None.

## Verdict

**VERDICT: COMPLETE (round 1)**
