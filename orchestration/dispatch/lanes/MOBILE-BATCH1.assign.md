<!-- lane assign — Architect-owned. CR052. -->
# MOBILE-BATCH1 — six small mobile defects, one lane

KIND: code
INSTANCE: coder.mobile
GATE: independent    <!-- Two of the six are user-reported against a shipped build, and DEF194 is a silent-failure class this project keeps re-committing. -->
BUDGET: $20
DEPENDS-ON: none

## What and why

Six independent, small, user-facing mobile defects. Batched because each is a handful of lines and
they share no logic — sequential lanes would spend more on audit round-trips than on the fixes.
**Read each row file; it carries the measured diagnosis and the intended fix.**

```
docs/defect/_registry/DEF164.row.md   friendly_error.dart tells the user to retry a 422 while isRetryable() says it is not retryable
docs/defect/_registry/DEF170.row.md   CR118's sector-legend fade renders at maximum scroll extent — "more below" keeps signalling with nothing below
docs/defect/_registry/DEF174.row.md   live-convene per-agent status is colour + motion only; a screen reader is told nothing
docs/defect/_registry/DEF190.row.md   the bottom nav bar disappears when Journal is opened via "Review in Journal" from Portfolio → History
docs/defect/_registry/DEF194.row.md   a failed retro-tightening breach check is swallowed by a bare `catch (_)` — "no warning" and "we could not check" look identical
docs/defect/_registry/DEF198.row.md   AI Coach empty-state copy still says "280 questions"; the corpus is 295
```

**DEF190 and DEF198 are tester-reported** against `0.1.0+60` by Platinum Anchor (`8f1e288a`). They
are the cheapest user-visible wins in the whole backlog.

**DEF194 is the one to take seriously despite its size.** A bare `catch (_)` that makes "we checked
and you are fine" indistinguishable from "we could not check" is the CR040 degrade-loudly violation
in miniature, and this project has shipped that exact shape enough times that it has its own entry
in `docs/initial_specs/08_tech/failure_patterns.md`. The fix is not to log it — it is to make the
user-visible state honest.

**DEF198 is not just a string.** Do not hardcode 295. The count went stale because it was written
by hand; if you replace one literal with another, someone files this defect again at 310. Derive it
from the corpus or from whatever the backend already returns, and if neither is available, say so in
your hand-off and hardcode it with a comment naming what would have to exist to stop doing that.

## Fences

- **Do NOT touch `backend/`.** `CR129-BE` and `SEC-BATCH1` are both building in parallel worktrees.
- **Do NOT touch `mobile/lib/widgets/hex_avatar.dart` or anything in the `HexAvatar` label path** —
  `DEF142` is a live lane at round 2 and owns it.
- **Do not restyle anything.** DEF170 is a *when-to-render* fix, not a redesign of the fade.
- ARB edits require `flutter gen-l10n` afterwards.

## Acceptance

1. **Each of the six is proven by a widget or unit test that FAILS against current code.** DEF190
   in particular: a navigation test that asserts the nav bar survives that specific entry path, not
   a manual claim.
2. **DEF194: the three states are distinguishable** — checked-and-clear, checked-and-breaching,
   could-not-check. The third must be visible to the user, not merely logged.
3. **DEF174: the status stream is exposed to the accessibility tree** with a semantic label that
   names the agent and its state. Verify with a semantics test, not by reading the code.
4. **DEF164: `friendly_error.dart`'s copy and `isRetryable()` agree for every status code they both
   handle.** A table-driven test over the codes, so the next divergence fails the build — this is
   the file whose own docstring claims to prevent exactly this.
5. **DEF198: the number is not a hand-maintained literal**, or you have said in the hand-off why it
   had to be and what would fix that.
6. **Mutations:** revert your DEF190 and DEF194 fixes and show the tests go RED. Report honestly,
   **including any that come back GREEN**.
7. `flutter test -r compact` from `mobile/` — pipe through `tr '\r' '\n'`. Baseline **330**, must
   finish `>= 330` with zero failures. `flutter analyze --no-fatal-infos` → exit 0
   (**5** known infos are expected; do not "fix" them).
8. Flutter binary is `/opt/homebrew/bin/flutter`.

## Registers

Flip each row you actually closed to `fixed` in its own `docs/defect/_registry/DEF###.row.md`, then
`python3 scripts/registers/gen_registers.py gen def`, and commit the row files and the regenerated
table **in the same commit** (DEF159). Leave any you did not close `open`, and say why.

## Hand-off delivery

Write `orchestration/dispatch/lanes/MOBILE-BATCH1.coder.mobile.md` with
`STATUS: READY_FOR_AUDIT (round 1)`; write `orchestration/audit/cr/MOBILE-BATCH1.architect.md` with
an explicit `SUBMITTED: round 1` line; get BOTH onto `main` AND push your lane branch to origin
(**DEF175**).

**If you can measure that an instruction here is wrong, stop and disclose with the measurement.**
The CR101-MOBILE builder did exactly that — my field table was wrong and it refused to render it.
That was the right call and it is the standard here.

ASSIGNED: coder.mobile round 1
DISPATCH: OPEN
