<!-- lane assign — Architect-owned. CR052. -->
# MOBILE-BATCH2 — two mobile defects plus the code half of two paper-trail residues

KIND: code
INSTANCE: coder.mobile
GATE: none    <!-- Sprint mode (Saiful, 2026-07-30): lanes integrate on my verification; track U audits the whole sprint as one item at the end. -->
BUDGET: $10
DEPENDS-ON: none

## What and why

Four pieces of work. **Read each row file — it carries the measured diagnosis and the intended fix.**

```
docs/defect/_registry/DEF173.row.md   journal retention cap is fetched with a hardcoded default plan, not the user's actual subscription
docs/defect/_registry/DEF162.row.md   RoomBoardMeta is dead code, and the flagship Room/Journal parity test still asserts it
docs/defect/_registry/DEF167.row.md   CR117 rename residues — the CODE half only (items a, b, c below)
docs/defect/_registry/DEF171.row.md   CR114/DEF129 deletion residue — the CODE half only (the dead DailyBriefing client model)
```

**The docs half of DEF167 and DEF171 is already done** (commit `3e33b17a` — the seven spec docs are
corrected). Both rows remain `open` for the code residues listed below. Do not re-edit the specs.

**DEF173 is the one that matters.** `JournalNotifier.refresh({String plan = 'trial_trader'})`
(`journal_providers.dart:75`) takes the plan as a **client-supplied argument with a default**, and
the auto-refresh at :182 takes that default — so the retention window, the "older entries" count and
the retention caveat are computed from `trial_trader` regardless of who is signed in. This is the
deeper half of DEF156: DEF156 made the number *update correctly*, so the wrong number now moves
convincingly. A Floor Pass user can be shown a retention caveat belonging to a different plan, on a
surface whose entire job is telling them what their plan costs them. **A client-supplied plan on an
entitlement-bearing read is the wrong trust boundary independent of the display bug** — that is the
part to fix, not just the default value.

**DEF162 is not ordinary dead code.** `room_board_parity_test.dart` is the structural guard that
keeps Room and Journal from diverging (the DEF098 class), and its authority comes from enumerating
exactly which fields may differ. An assertion spent on `meta.modelTier`, which nothing renders,
inflates the apparent coverage of that guarantee — someone checking whether parity is well-tested
counts a test that proves nothing about anything on screen.

### DEF167 — code residues only (a, b, c)

- **(a)** `cta_shape_test.dart` has no `FlatTopHexagonBarClipper` case, so CR113's "all three shapes
  covered" claim is **false** — and the untested one is the shape whose whole point is arbitrary
  aspect ratio. Add the missing third leg.
- **(b)** `AmiRadii.hexCornerMobile` / `hexCornerDesktop` (`ami_theme.dart:264-265`) lost their only
  consumer. Delete them.
- **(c)** `hex_clipper.dart:4-6` docstring names three users that do not use it. Correct it.

The three real shape names after CR117 are `CutCornerOctagonClipper` (8 sides, the default control
shape), `FlatTopHexagonBarClipper` (6 sides, angled ends, any aspect ratio), and
`FlatTopRegularHexagon` (6 sides, 2:√3). `FlatTopHexagonClipper` was **deliberately vacated** so
stale references fail to compile — do not reintroduce that name anywhere.

### DEF171 — code residue only

Sweep the dead-but-tolerant `DailyBriefing` client model (`mobile/lib/models/mandate.dart:136-262`).
The auditor confirmed it is never read. **Verify that independently before deleting** — a grep for
`DailyBriefing` and `daily_briefing` across `mobile/lib` and `mobile/test`.

## Fences

- **Do NOT touch `backend/`.** Four backend lanes are live in parallel worktrees.
- **Do NOT touch `mobile/lib/widgets/hex_avatar.dart` or anything in the `HexAvatar` label path** —
  `DEF142` is a separate live lane and owns it.
- **Do not restyle anything.** No visual redesign in this lane.
- ARB edits require `flutter gen-l10n` afterwards.
- **Do not extend the vacated-name guard to `docs/`** — the DEF167 row suggests it and I am doing
  that half myself; it scans the spec tree, not Dart.

## Acceptance

1. **Each item is proven by a widget or unit test that FAILS against current code**, except the pure
   deletions (DEF167 b/c, DEF171) where the proof is that the suite stays green and a grep shows
   zero remaining references — **show me the grep output** in the hand-off.
2. **DEF173: the plan is not client-supplied with a default.** Derive it from the authenticated
   user. If the client genuinely must pass it, **delete the default** so a missing plan is a compile
   error rather than a silent `trial_trader` — and say in the hand-off which of the two you chose
   and why. A test must prove a Floor Pass user gets Floor Pass retention, not `trial_trader`'s.
3. **DEF162: verify no journal-replay snapshot depends on the `meta` key** before removing it from
   the mappers. The row asks for this specifically. Show what you checked.
4. **DEF167 (a): the new `FlatTopHexagonBarClipper` case exercises a non-2:√3 aspect ratio** — a
   square-ish case proves nothing about the shape whose purpose is arbitrary aspect ratio.
5. **Mutations:** revert your DEF173 and DEF162 fixes and show the tests go RED. Report honestly,
   **including any that come back GREEN**.
6. `flutter test -r compact` from `mobile/` — **pipe through `tr '\r' '\n'`**. Baseline **338**;
   must finish `>= 338` with zero failures. `flutter analyze --no-fatal-infos` → exit 0
   (**5** known infos are expected; do not "fix" them).
7. Flutter binary is `/opt/homebrew/bin/flutter`.

## Registers

DEF162 and DEF173 flip to `fixed` if closed. **DEF167 and DEF171 stay `open`** — I am closing them
myself once the docs-tree guard lands; add a line to each row body naming which residues you cleared
so the remaining scope is unambiguous. Then `python3 scripts/registers/gen_registers.py gen def`,
and commit row files and the regenerated table **in the same commit** (DEF159).
**Explicit pathspec — never `git add -A`, never bare commit.**

## Hand-off delivery

**Write your hand-off file EARLY and keep updating it** — a budget cap that kills you mid-lane with
the hand-off unwritten is the worst place to stop, and it has already happened twice here.

Write `orchestration/dispatch/lanes/MOBILE-BATCH2.coder.mobile.md` with
`STATUS: READY_FOR_AUDIT (round 1)`; get it onto `main` AND push your lane branch to origin
(**DEF175**).

**No `.architect.md` submit file** — sprint mode, I integrate on my own verification and track U
audits the sprint as one batch afterwards.

**If you can measure that an instruction here is wrong, stop and disclose with the measurement.**
The CR101-MOBILE builder did exactly that — my field table was wrong and it refused to render it.
That was the right call and it is the standard here.

ASSIGNED: coder.mobile round 1
DISPATCH: ACCEPTED
