<!-- lane hand-off — coder.mobile. CR052. -->
# MOBILE-DEF189 — hand-off

STATUS: READY_FOR_AUDIT (round 1)

Branch: `lane/MOBILE-DEF189.coder.mobile`, pushed to origin at `0d5e7c36`.
Worktree: `.claude/worktrees/coder.mobile-MOBILE-DEF189`.

## What shipped

`mobile/lib/widgets/room/room_transcript_rows.dart`:

- **Bug (1), the copy-paste ternary** — added `collapsedLabel(l, voice)`, the
  single function that now decides the collapsed-row text:
  `NOT HEARD` (withheld) → `gistFor`'s ranked extraction → `NO RESPONSE`
  **only** when `voice.content` is genuinely empty → else
  `firstSentence(voice.content)`. Replaces the
  `voice.content.isEmpty ? l.roomRowNoResponse : l.roomRowNoResponse`
  ternary (both branches identical) that rendered `NO RESPONSE`
  unconditionally.
- Added `firstSentence(content)` — verbatim up to and including the first
  `.`/`!`/`?`, else the full content (the row's `maxLines: 1` + ellipsis
  absorbs any overflow, so no separate length cap needed).
- **`gistFor` left unchanged, on purpose.** It still returns null for
  verdict prose. Documented in its own doc-comment: its three patterns
  (headline / `**bold**` span / entry-stop-target triple) are ranked
  quotable-sources specific to analyst commentary; the PM's prose fallback
  is a presentation choice (first sentence), not another rank, so it lives
  at the call site (`collapsedLabel`) instead of blurring `gistFor`'s
  contract.
- **Bug (3), no card/attribution** — when `voice.agentId ==
  'portfolio_manager'` and the row is expanded, `MarkdownBody` is now
  wrapped in a `Container` (`key: pmVerdictCard`) matching
  `_ReasonBlock`'s treatment at `room_board.dart:1141-1147` — `slate900`
  background, `AmiRadii.card` radius, `AmiSpacing.s` padding — with
  `agent.displayName.toUpperCase()` labelled above the content in the
  agent's colour. **No new ARB string** — reused the existing
  `agent.displayName` from `agent.dart`, so no i18n/retranslation flag
  needed for this. Every other agent's row is untouched (bare
  `MarkdownBody`, no card) — did not restyle the rest of the transcript.
- `RoomTranscriptRows`' membership is untouched — the PM row stays, per
  Saiful's ruling in the assign. Did not touch `backend/`.

`mobile/test/widgets/room_transcript_rows_test.dart` (new, 8 tests):

1. A PM voice with prose content (no headline/bold/triple) does not
   render `NO RESPONSE` — **this is the regression test for the actual
   bug the tester saw.**
2. `gistFor` still returns null for that same prose (documents that the
   fallback is intentionally NOT inside `gistFor`).
3. `collapsedLabel` derives from content when `gistFor` is null.
4. A genuinely empty PM voice still reads `NO RESPONSE` — the other
   direction, confirming this isn't a new false positive.
5. A withheld voice reads `NOT HEARD`, never `NO RESPONSE`.
6. A headline still wins over the first-sentence fallback.
7. The expanded PM row is carded (`pmVerdictCard`, `slate900`) and named
   (`PORTFOLIO MANAGER` text found).
8. A non-PM row (Trader) gets no card and no "TRADER" attribution text —
   confirms the fence against restyling the rest of the transcript.

## Mutation testing (acceptance #5)

Reverted each fix in turn against the fixed source, re-ran the new test
file:

- **Mutation A** — reverted `collapsedLabel` to the old always-`NO
  RESPONSE`-when-ungistable behaviour (dropped the `firstSentence`
  fallback): **2 tests went RED** — test #1 (the regression test) and
  test #3 (`collapsedLabel derives from content`). Tests #2, #4, #5, #6
  stayed green, correctly (they don't exercise the fallback path).
- **Mutation B** — reverted the expanded-PM-card branch back to a bare
  `MarkdownBody` for all agents: **1 test went RED** — test #7 (card +
  attribution). Test #8 stayed green (nothing to find either way on the
  Trader row).
- No mutation came back GREEN. Restored the fixed source after each
  mutation; final state committed matches what's on the pushed branch.

## Verification run

- `flutter test test/widgets/room_transcript_rows_test.dart -r compact`:
  **8/8 pass** on the fixed source.
- `flutter test -r compact | tr '\r' '\n'`: **393 passed, 0 failed**
  (baseline 385 + 8 new = 393; matches).
- `flutter analyze --no-fatal-infos`: **5 issues**, all pre-existing
  (`main.dart:69` x2 deprecated `copyWith`, `floor_screen.dart:74,327`
  `use_build_context_synchronously`, `sign_in_email_disclosure_test.dart:27`
  `use_super_parameters`) — none in `room_transcript_rows.dart` or the new
  test file. Exit 0.

## Registers

`DEF189` flipped to `fixed` in `docs/defect/_registry/DEF189.row.md`
(status cell is the bare token; the fix note is in the DESCRIPTION column
per DEF203) and `docs/defect/def_list.md` regenerated via
`python3 scripts/registers/gen_registers.py gen def`. Row file + generated
table committed together with the code in the same commit
(`0d5e7c36`) — no separate registers-only commit.

## Commit

`fix(bug:f23f7891): PM transcript row derives its label from content and
cards its expanded verdict (AT:R65 DEF189)` — `0d5e7c36` on
`lane/MOBILE-DEF189.coder.mobile`, pushed to origin.

Nothing left fenced or disclosed as out-of-scope. Ready for audit.
