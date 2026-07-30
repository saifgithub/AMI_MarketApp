<!-- architect bridge — coder.mobile bridging into the audit handshake. CR052 / orchestration/audit/PROTOCOL.md. -->
# MOBILE-BATCH1 — architect bridge

ITEM: MOBILE-BATCH1
INSTANCE: coder.mobile
GATE: independent
SCOPE: cr
BRANCH: `lane/MOBILE-BATCH1.coder.mobile` @ `c91ab4b7`
WORKTREE: `.claude/worktrees/coder.mobile-MOBILE-BATCH1`
DEPENDS-ON: none
SUBMITTED: round 1

---

# Round 1

## What and why

Six independent, small, user-facing mobile defects batched into one lane (DEF164, DEF170, DEF174,
DEF190, DEF194, DEF198) — each a handful of lines sharing no logic, so a sequential per-item lane
would have spent more on audit round-trips than on the fixes. Full detail on each is in
`orchestration/dispatch/lanes/MOBILE-BATCH1.coder.mobile.md`; this bridge carries the
verification-facing summary.

## The change

`mobile/lib/services/api/friendly_error.dart`, `mobile/lib/services/billing/
revenuecat_purchase_service.dart`, `mobile/lib/screens/sim/portfolio_screen.dart`,
`mobile/lib/screens/room/room_screen.dart`, `mobile/lib/screens/home_shell.dart`,
`mobile/lib/screens/settings/settings_screen.dart`, `mobile/lib/screens/coach/ai_coach_screen.dart`,
`mobile/lib/models/ai_coach.dart`, three ARB files + their generated l10n, and six test files (three
new: `home_shell_test.dart`, `settings_screen_retro_audit_test.dart`, `ai_coach_screen_test.dart`;
three edited: `friendly_error_test.dart`, `sector_legend_cap_test.dart`, `room_live_status_test.dart`).

Six independent behaviours, no shared code path between them:

1. **DEF164** — `_statusRetryable(int? status)` is now the single source both `isRetryable()` and
   `_forStatus()`'s copy read, so a badResponse status's retry affordance and its copy cannot diverge.
   Non-retryable unenumerated 4xx (422 included) gets its own honest copy instead of falling through to
   "Try again." Separately, the DEF148 leak-guard test now scans all of `lib/` (was 4 directories) and
   catches bare `e.toString()` (was only quoted `$e` interpolation) — this is what surfaced
   `revenuecat_purchase_service.dart`'s two live offenders, now fixed to route through
   `friendlyError()`.
2. **DEF170** — the CR118 sector-legend fade now reads `ScrollController.position.extentAfter` via an
   `AnimatedBuilder` wrapper and only paints while there's genuinely more below.
3. **DEF174** — the live-roster status indicator (thinking dot / responded check-icon / interrupted
   row / waiting text) is wrapped in one `Semantics(label:, excludeSemantics: true)` per seat, naming
   the agent and its state via a new `roomAgentStatusSemantic` ARB placeholder string.
4. **DEF190** — `HomeShell.build()` adds `ref.listen<int>(activeTabIndexProvider, (prev, next) { if
   (next != _tab) setState(() => _tab = next); })`; `_JournalPointer` (StatelessWidget → ConsumerWidget)
   writes `activeTabIndexProvider.notifier.state = 2` instead of pushing a `MaterialPageRoute`.
5. **DEF194** — `settings_screen.dart`'s `catch (_)` around `auditMandateHoldings` now shows a
   `ScaffoldMessenger` snackbar with the new `settingsRetroAuditFailed` string before returning.
6. **DEF198** — `AiCoachCorpus.totalCount` (a `static const int = 295` in `lib/models/ai_coach.dart`)
   replaces the inline `'280 questions...'` string literal; `ai_coach_screen.dart` now reads it through
   a new `aiCoachEmptyStateHint(count)` ARB string.

## Test command and observed output

From `mobile/`:

```
/opt/homebrew/bin/flutter test -r compact | tr '\r' '\n'
```

→ `00:23 +338: ... All tests passed!` — 338 passing (baseline 330 per the assign), zero failures.

```
/opt/homebrew/bin/flutter analyze --no-fatal-infos
```

→ exit 0, 5 issues found — all 5 pre-existing (2× `deprecated_member_use` in `main.dart`, 2×
`use_build_context_synchronously` in `floor_screen.dart`, 1× `use_super_parameters` in an unrelated
test file), none introduced by this lane.

## Revert-proof QA (acceptance 6, mutation matrix)

Each new/edited assertion was confirmed RED against the pre-fix source via `git stash push --
<files>` (keeping the new test), rerunning the single test file, then `git stash pop`. Explicit
per-defect detail, including the two the assign specifically asked for (DEF190, DEF194), is in the
lane file. Summary: all six went RED against unmodified code; none came back GREEN.

## Fences

`backend/` untouched (DEF198's complete fix needs a backend total-count field — explicitly disclosed
as NOT done, not silently worked around). `mobile/lib/widgets/hex_avatar.dart` untouched — DEF174
wraps HexAvatar's caller in `Semantics`, never opens the HexAvatar file itself, respecting DEF142's
live round-2 lane. DEF170 changes only *when* the existing `ShaderMask`/gradient renders, not its
appearance.

SUBMITTED: round 1
