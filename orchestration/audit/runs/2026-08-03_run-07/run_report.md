# Audit run 2026-08-03 run-07 — CR136-M09, round 2

Auditor track U. Answers round 1's `AWAITING_FIXES` (1 MAJOR, 2 MINOR — run-05).
Audited at **`8179f659`** in `.claude/worktrees/audit-CR136-m09-r2`, detached and
clean at checkout.

Verdict: **COMPLETE** — zero BLOCKER, zero MAJOR. One non-gating MINOR.
Findings in `orchestration/audit/cr/CR136-M09.auditor.md`.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| module suites (5 files) | 85 passed | **85 passed** | match |
| full `flutter test` | 495 passed | **495 passed, ~20 s** | match |
| `flutter analyze --no-fatal-infos` | 6 issues, 6 infos, 0 errors, 0 warnings | **same, 4.9 s** | match |
| new parity guard | — | **3 passed, 0.61 s** | — |
| full backend `tests/unit/` | — | **2269 passed, 13 warnings, 319.92s** | no regressions |

Run from `mobile/` after `flutter pub get`, Flutter 3.41.9 stable — the Dart/Flutter
bindings row I added in round 1, used for the first time as the pinned suite.

## The guard, attacked five ways

```
baseline                                                          3 passed
MUT-A  one Dart unit flipped fraction → ratio                      1 failed, 2 passed
MUT-B  one Dart key dropped ('mcr')                                1 failed, 2 passed
MUT-C  a backend refusal code renamed                              1 failed, 2 passed
MUT-D  the Dart map literal genuinely renamed                      2 failed, 1 passed
MUT-E  trailing comma removed from the last map entry              1 failed, 2 passed
restored                                                          3 passed
```

A–C are the three drift directions M1 named. D and E are mine, aimed at whether the
non-vacuity leg makes the other assertions compare anything at all — a fair question
of a regex-over-source guard, and it answers correctly: a partial parse is as red as
an empty one, because the comparison is whole-map equality.

Recording a correction of my own: MUT-D's first form (`kMetricValueUnit` →
`kMetricValueUnitX`) left all 3 green, because `source.index(...)` is a prefix match
and found the same literal. A real rename fails 2 of 3. The leg works; a suffix-only
rename is the single edit that slips past it, and it is not a drift shape anyone
produces by accident.

## m1, m2

m1 closed by removing the fallback rather than narrowing it — `fromJson` reads
`metrics` only, and an envelope without it is stamped `unrecognised_envelope`, which
reaches `health_card.dart:121`'s unknown-status branch. Traced by hand: every earlier
branch in `_body` keys on an exact status string, so nothing intercepts it. Both
vacuity guards on the replacement test are the right two.

m2 closed — QA-C restated with a mutation that compiles (85 → 84/1), corrected in
place. That is the right handling; a revert-proof section whose numbers came from a
load failure is worse than no section.

## MINOR m3 — the inverse gap

Contract 2 iterates a hard-coded tuple of three constants, so it catches a **renamed**
code and not an **added** one. Three today, correct today. A fourth backend refusal
code is invisible to the guard and drops the user into the generic panel — the exact
failure contract 2 exists to prevent, by the one route it does not watch. Same
argument the submission made for the units map ("addition is covered, drift is not"),
inverted. Not gating; fix by reflection over `*_CODE` names, or document it as
manually maintained.

## Still owed, and not by this lane

`NEEDS-DEVICE-CHECK` (no build shipped, melehost off-LAN all session), §5.5's CR120
scroll re-pin (Saiful's call), §5.7's loading state. This verdict covers logic and
wire contracts, not pixels.
