# CR112 round 1 — audit run report (track U, 2026-07-29)

Lane: `orchestration/audit/cr/CR112.architect.md` (`SUBMITTED: round 1`, bridge from
`coder.mobile`). Audited SHA `bd3589ab` (lane tip, one commit off `dd71c7e8`) in scratch
worktree `.claude/worktrees/audit-CR112/` (detached; removed after the run).
Verdict: **COMPLETE (round 1)**. Scope: `room_screen.dart` (+150/−172 vs main), 3 ARBs,
2 test files, lane md. `room_providers.dart` and `room_transcript_rows.dart` zero-diff
(claim verified).

## Suites at bd3589ab

| Command | Lane claim | Measured | Verdict |
|---|---|---|---|
| `flutter test -r compact` (worktree `mobile/`) | 309 passed | **309 passed** (17s) | match |
| `flutter analyze --no-fatal-infos` | 5 infos | exit 0, same 5 infos (4.3s) | match |

## Auditor mutation probes (independent of the builder's three claimed REDs)

Probe 1 — transcript fallback in the headline-PRESENT branch
(`Text(state.transcript[agent.id] ?? headline, …)` in `_headline`'s else branch):
**GREEN, 9/9 pass.** No fixture pairs a non-null headline with transcript text, so the
branch's rendered content is unpinned. Dismissed as a finding (dead-code-shaped
regression direction; the branch requires `headline != null` to render at all) —
recorded as an observation in the verdict.

Probe 2 — the same fallback in the NOT STATED branch
(`Text(state.transcript[agent.id] ?? l.roomCombNotStated, …)`):
**exactly 1 RED of 9** — `acceptance #2 — a mixed roster shows all three, correctly
attributed`, which seeds a responded agent with transcript text `'full text that must
never appear on screen'` and asserts its absence. The prose-leak dimension the CR
exists for is genuinely guarded.

Post-probe hygiene: `git checkout -- room_screen.dart` after each probe; final
`git diff --stat main...HEAD -- room_screen.dart` = the committed CR112 diff only
(150+/172−), no mutation residue.

## State-machine trace (the PM-interrupted question)

Concern: `interrupted = !responded && !thinking && started && !streaming &&
!reconnecting`, and the PM never gets a stance key on the prose-envelope path. Could a
HEALTHY run strand the roster with the PM reading INTERRUPTED?

- `room_providers.dart:290-296` — the `done` SSE event sets `streaming:false` and
  `done:true` in one `copyWith`; no intermediate frame exists with streaming stopped
  and done unset on the normal path.
- `room_screen.dart:94` — `settled = state.done || state.verdict != null`, so once
  `done` lands the roster is replaced by `RoomTranscriptRows`; a no-verdict run still
  settles.
- `room_providers.dart:300-305` — the `error` event sets `streaming:false` WITHOUT
  `done`; that is the only path (plus reconnect timeout, :399-403) where the roster
  survives a stopped stream, and there INTERRUPTED is the truth.
- Live `agent_done` emits the three stance keys unconditionally
  (`api/room.py:263-268`), so every completed turn — PM included — marks `responded`.
- Roster membership: `kAllAgents.sublist(0, 12)` = the 12 room agents, PM last,
  concierge excluded (`agent.dart:45-160`).

## Edited-in-place withheld tests

`room_agent_withheld_test.dart` diff read in full: the reorder test is renamed to state
the new invariant and asserts MORE than before (prose absent + fixed-seat ordering);
the countdown test's finder narrowed to the full sentence because the fixed roster now
also renders a plain row for the same agent. Tightening, not vacuity-laundering.
