<!-- lane hand-off — coder.mobile. CR052. -->
# MOBILE-DEF189 — hand-off

STATUS: IN_PROGRESS (round 1)

Branch: `lane/MOBILE-DEF189.coder.mobile`, worktree
`.claude/worktrees/coder.mobile-MOBILE-DEF189`.

## What's done

- `mobile/lib/widgets/room/room_transcript_rows.dart`:
  - Added `firstSentence(content)` — verbatim up to first `.`/`!`/`?`, else the
    whole content (row's `maxLines: 1` + ellipsis absorbs the rest).
  - Added `collapsedLabel(l, voice)` — the single place that decides the
    collapsed-row text: `NOT HEARD` withheld, else `gistFor` result, else
    `NO RESPONSE` for truly empty content, else `firstSentence(content)`.
  - `TranscriptRow.build` now calls `collapsedLabel` instead of the
    copy-paste ternary (`voice.content.isEmpty ? l.roomRowNoResponse :
    l.roomRowNoResponse`) that always rendered `NO RESPONSE`.
  - Left `gistFor`'s null branch UNCHANGED — did not extend it to parse
    verdict prose. Reasoning is in a doc-comment on `gistFor`: its three
    patterns (headline / bold span / level triple) are quotable-source
    ranks specific to analyst commentary; the PM's prose fallback is a
    presentation choice (first sentence), not another rank, so it lives at
    the call site (`collapsedLabel`) rather than inside `gistFor`.
  - Expanded content: when `voice.agentId == 'portfolio_manager'`, wraps
    `MarkdownBody` in a `Container` matching `_ReasonBlock`'s treatment
    (`room_board.dart:1141-1147` — `slate900` bg, `AmiRadii.card`,
    `AmiSpacing.s` padding) with an uppercased `agent.displayName` label
    above it in `agent.color`. Other rows unchanged (bare `MarkdownBody`,
    matching the fence against restyling the rest of the transcript).
    Used `agent.displayName` (already in `agent.dart`) rather than a new
    ARB string — avoids an i18n/retranslation flag for UI chrome that's
    just an existing display name.

## Next

- Writing the widget test (`test/widgets/room_transcript_rows_test.dart`)
  now — copy-paste-bug regression, NO RESPONSE-stays-correct, PM card +
  attribution.
- Then: mutation testing (revert each fix, confirm RED), full suite run,
  `flutter analyze`, register flip + regen, commit + push.

Will update this file to `STATUS: READY_FOR_AUDIT (round 1)` once all of the
above is done and pushed.
