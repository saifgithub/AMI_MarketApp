# Audit run report — 2026-07-30 run-07

ITEM: MOBILE-BATCH1 · ROUND: 1 · VERDICT: COMPLETE
LANE: `lane/MOBILE-BATCH1.coder.mobile` @ `c91ab4b7` · SCOPE: `cr`
AUDITOR: track U (Kimi) · worktree `.claude/worktrees/audit-MOBILE-BATCH1`

## Scope

Six small mobile defects in one lane: DEF164 (friendly_error retry/copy
single-source + honest non-retryable-4xx copy), DEF170 (sector-legend fade
gated on `extentAfter`), DEF174 (roster `Semantics` labels for all four
status states), DEF190 (HomeShell `ref.listen` tab sync; `_JournalPointer`
writes `activeTabIndexProvider` instead of pushing an orphaned route),
DEF194 (settings retro-audit `catch (_)` → couldn't-check snackbar),
DEF198 (`AiCoachCorpus.totalCount = 295` replacing stale '280' literal).

Diff: 28 files, +1035/−205 (incl. formatter churn); 3 new test files
(`home_shell_test.dart`, `settings_screen_retro_audit_test.dart`,
`ai_coach_screen_test.dart`), 3 edited (`friendly_error_test.dart`,
`sector_legend_cap_test.dart`, `room_live_status_test.dart`).

## Measurements (all reproduced by me from the worktree)

| Check | Builder | Auditor | Result |
|---|---|---|---|
| Full flutter suite | 338 passed | 338 passed (00:25) | match |
| `flutter analyze --no-fatal-infos` | exit 0, 5 infos | exit 0, 5 infos (6.1s) | match — same 5 pre-existing |
| Targeted (6 touched test files) | — | 43 passed | green |
| `gen_registers.py verify all` | — | DEF 199 / CR 128 OK | clean |

## Blind mutation (auditor's own)

Removed the `ref.listen<int>(activeTabIndexProvider, …)` block from
`mobile/lib/screens/home_shell.dart` → exactly 1 RED
(`DEF190: the bottom nav survives "Review in Journal" from Portfolio's
History tab`). Reverted byte-identical (`git status --short` empty),
re-green. Builder's own revert-proof covered all six; one independent
mutation per tiered policy.

## File:line verifications beyond the diff read

- `home_shell.dart:29-35` — `_tabs[2]` is `JournalScreen()`; the hard-coded
  index 2 in `_JournalPointer` is correct.
- ARB keys `roomAgentStatusSemantic`, `settingsRetroAuditFailed`,
  `aiCoachEmptyStateHint` present in en; `roomAgentStatusSemantic` present
  in ar/ms; `settingsRetroAuditFailed` carries `retranslate:[ar,ms]` per
  convention.
- Hand-counted `content/ai_coach/*.json` against the new 295 constant —
  matches today.
- DEF194 closes CR101-MOBILE r1 MINOR m1 (the silent `catch (_)` I
  flagged).

## Notes

- Formatter churn inflates the diff stat; no behaviour.
- OUT-OF-SCOPE: DEF198 backend half — no count endpoint; hand-maintained
  client constant will drift. Architect mints.
- MINORs: none. DoD enforcement waived per standing instruction.
