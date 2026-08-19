# CR195 — the Flutter suite is not a gate on anything

**Status:** proposed · **Raised:** 2026-08-19 (AT:R70) · **Origin:** found while running
[DEF331](../../defect/def_list.md) down before a store build.

## The gap

`/promote-to-alpha` step 1 runs, in order: the hold gate, the audit-lane gate, the tree gate, the
**backend** suite (`scripts/promotion/preflight_suite.sh`, enforced with a VERDICT line since
DEF326), and `flutter analyze --no-fatal-infos`.

It never runs `flutter test`.

`scripts/build_testflight.sh`, `scripts/build_playstore.sh` and `scripts/publish_playstore.sh` do
not run it either. So on the path from a commit to a binary on a tester's phone, **nothing executes
the 1,113-test Flutter suite.**

## How it surfaced

DEF331 sat red from `03992d26` (2026-08-17) until 2026-08-19 — across a backend promotion and a
store build. `flutter analyze` returned **0** the whole time, because the failure was a test
assertion, not a static-analysis finding. The two answer different questions and only one of them
was being asked.

It was caught because a human happened to run `flutter test` by hand before a release. That is the
same "caught by accident" this project already filed twice: DEF195 (a release gate that existed and
was never called) and DEF326 (a suite whose failing state was invisible in the line an operator
reads). The pattern is consistent enough to name — *a check nothing invokes is not a check* — and
the fix is the same each time: put it on the path.

## Scope

**In**

1. `flutter test` as a blocking gate, wrapped the way DEF326 wrapped the backend suite: a script
   that reads the result itself and ends in a single `VERDICT:` line plus an exit code, rather than
   printing pytest-style output for an operator to interpret.
2. Wired into the **release scripts**, not into `/promote-to-alpha` — the Flutter suite says nothing
   about a backend rsync, and a gate that fires on work it does not describe is what DEF277 is
   about. The client suite belongs on the client's release path.
3. A decision on where it runs relative to the pubspec bump: **above it**, per DEF279 — a refusal
   must not spend a build number.

**Out**

- Widening `/promote-to-alpha`. Backend promotion does not ship Flutter code (`mobile/` is excluded
  from the rsync), so blocking a backend fix on a client test failure would be a gate firing on
  something it has no relationship to.
- `flutter analyze` changes. It is doing its job; it simply answers a different question.

## Acceptance

1. A red Flutter suite blocks `build_testflight.sh`, `build_playstore.sh` and
   `publish_playstore.sh`, before the pubspec bump.
2. The block is legible from one line, not inferred from a scroll of test output.
3. Proven by running each script against a deliberately-failing test and confirming exit 1 with the
   build number unchanged — the same evidence DEF195's wiring produced.
