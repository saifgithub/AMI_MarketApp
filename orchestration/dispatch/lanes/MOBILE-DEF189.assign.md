<!-- lane assign — Architect-owned. CR052. -->
# MOBILE-DEF189 — the PM's transcript row says "NO RESPONSE" when the PM did respond

KIND: code
INSTANCE: coder.mobile
GATE: none    <!-- Sprint mode (Saiful, 2026-07-30): lanes integrate on my verification; track U audits the sprint as one batch. -->
BUDGET: $8
DEPENDS-ON: none

## What and why

`docs/defect/_registry/DEF189.row.md` — **read it in full.** Two tester reports from Platinum Anchor
on `0.1.0+60`, two minutes apart, one root cause:

> *"PM agent showing 'No response' is incorrect. you can just put the short PM verdict"* (`f23f7891`)
> *"the PM NARRATIVE is just floating there. it should be in a card and clearly indicated that this came from the PM AGENT"* (`d7a0740d`)

**RULED by Saiful 2026-07-30: keep the PM row, fix both bugs.** The alternative — excluding
`portfolio_manager` from `RoomTranscriptRows` the way the 11-hex comb already does — was considered
and rejected. Do not remove the row.

Two bugs in `room_transcript_rows.dart`:

**(1) The collapsed label is a copy-paste bug.** At `:253-257` the ternary reads
`voice.content.isEmpty ? l.roomRowNoResponse : l.roomRowNoResponse` — **both branches are
identical**, so the row says `NO RESPONSE` regardless of whether `voice.content` holds the PM's full
verdict text. It does; it is simply never surfaced.

**(2) `gistFor` returns null for PM prose.** At `:69-75` it extracts a headline, a `**bold**` span,
or an entry/stop/target numeric triple — three patterns written for *analyst-style commentary*, not
a verdict narrative. The PM's reasoning matches none of them, which is why the null branch is hit
every time.

**(3) The expanded content has no card.** Tapping the row renders `voice.content` through a bare
`MarkdownBody` at `:284-293` with only left padding — no `Container`, no border, no attribution.
The Board already does this correctly: `_ReasonBlock` (`room_board.dart:1126-1177`) wraps the PM's
reason in a `slate900` card. **Match that treatment rather than inventing a new one** — the whole
point of the second tester report is that the same content looks authored in one place and orphaned
in the other.

## Fences

- **Do NOT touch `backend/`.** Backend lanes may be live in parallel worktrees.
- **Do NOT change `RoomTranscriptRows`' membership** — the PM row stays, per the ruling above.
- **Do not restyle the Board.** `_ReasonBlock` is the reference, not the subject.
- Do not invent a PM headline on the backend. This is a client-side presentation fix; if you
  conclude the honest fix needs a backend field, **stop and disclose it** rather than reaching into
  `backend/`.
- ARB edits require `flutter gen-l10n` afterwards.

## Acceptance

1. **A widget test that FAILS against current code**, asserting a PM voice with non-empty content
   does **not** render `NO RESPONSE`. Write it first, watch it go red. This is the copy-paste bug and
   it is the one the tester actually saw.
2. **The collapsed label derives from `voice.content`** when `gistFor` returns null — first sentence,
   or an existing `headline` if the backend ever sets one. **`NO RESPONSE` must remain reachable and
   correct for a genuinely empty voice** — a test for that direction too, or you have replaced a
   false negative with a false positive.
3. **The expanded PM content is carded and attributed**, matching `_ReasonBlock`'s treatment. A test
   asserts the container exists and that the PM is named — not merely that the text renders.
4. **`gistFor`'s null branch is understood, not just routed around.** Say in your hand-off whether
   you extended `gistFor` to handle verdict prose or left it null and handled the fallback at the
   call site, and why. Both are defensible; leaving it undocumented is not.
5. **Mutations:** revert each fix in turn and show the corresponding test goes RED. Report honestly,
   **including any that come back GREEN**.
6. `flutter test -r compact` from `mobile/` — **pipe through `tr '\r' '\n'`**. Baseline **385**; must
   finish `>= 385` with zero failures. `flutter analyze --no-fatal-infos` → exit 0 (**5** known infos
   are expected; do not "fix" them).
7. Flutter binary is `/opt/homebrew/bin/flutter`.

## Registers

Flip `DEF189` to `fixed` if closed. **Put the note in the DESCRIPTION column — the status cell must
stay a bare token** (DEF203). Then `python3 scripts/registers/gen_registers.py gen def` and commit
row file and regenerated table **in the same commit** (DEF159). **Explicit pathspec — never
`git add -A`, never bare commit.**

`DEF189` is a **user-reported** defect (`bug:f23f7891`), so the commit subject follows that form:
`fix(bug:f23f7891): … (AT:R65 DEF189)`.

## Hand-off delivery

**Write your hand-off file EARLY and keep updating it.** Write
`orchestration/dispatch/lanes/MOBILE-DEF189.coder.mobile.md` with `STATUS: READY_FOR_AUDIT (round 1)`;
get it onto `main` AND push your lane branch to origin (**DEF175**).

**If you can measure that an instruction here is wrong, stop and disclose with the measurement.**

ASSIGNED: coder.mobile round 1
DISPATCH: ACCEPTED
