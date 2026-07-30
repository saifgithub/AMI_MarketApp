<!-- lane return — coder.mobile owns this file. CR052. -->
# MOBILE-BATCH1 — coder.mobile progress

All six closed. `mobile` test count 338 (baseline 330, +8 new), zero failures. `flutter analyze
--no-fatal-infos` exit 0, the same 5 pre-existing infos, nothing new.

- **DEF164** — `friendly_error.dart` derived a `_statusRetryable(status)` helper shared by
  `isRetryable()` and `_forStatus()` so the copy and the retry affordance for a 4xx (422 among them)
  can't disagree by construction; a non-retryable 4xx now reads "wasn't accepted... before trying
  again" instead of an unconditional "Try again." The dormant leak-guard half: widened
  `friendly_error_test.dart`'s scan from four hand-picked directories to the whole of `lib/`
  (excluding `lib/generated/`), and added a check for bare `e.toString()` alongside the existing `$e`
  interpolation pattern — this actually caught the two live offenders in
  `revenuecat_purchase_service.dart:98,112`, which now route through `friendlyError()`. Table-driven
  test over 9 status codes proves copy/retryability agreement.
- **DEF170** — the CR118 sector-legend `ShaderMask` now wraps in an `AnimatedBuilder` on the legend's
  own `ScrollController` and only renders while `!hasClients || position.extentAfter > 0`, so the fade
  stops once nothing remains hidden below. Also fixed the `sector_legend_cap_test.dart` ancestor finder
  (`.last` → `.first`) to match its own "nearest" comment — was correct by accident of the current tree.
- **DEF174** — `_AgentStatusRow`'s trailing status indicator (the colour-changing dot for `thinking`,
  the bare check icon for `responded`) is now wrapped in `Semantics(label: ..., excludeSemantics:
  true)` naming the agent and its state, scoped narrowly to just that indicator so the agent-name Text
  and the headline stay independently readable rather than folding the whole seat into one opaque
  node. Wires the previously-orphaned `roomAgentThinking` ARB string; added `roomAgentResponded` +
  `roomAgentStatusSemantic`. Verified with `find.bySemanticsLabel`, not by reading the code.
- **DEF190** — `HomeShell` now `ref.listen<int>(activeTabIndexProvider, ...)` and switches its own
  `_tab` on an external write it didn't already know about (guarded `next != _tab` so the shell's own
  tap handler, which sets `_tab` directly before the provider write, doesn't cause a redundant
  rebuild). `_JournalPointer` (now a `ConsumerWidget`) writes the provider to index 2 instead of
  `Navigator.push`ing a second, orphaned `JournalScreen`. Test pumps the REAL `HomeShell`, taps through
  Portfolio → History → "Review in Journal", and checks `Navigator.canPop() == false` + exactly one
  `JournalScreen` in the tree — a plain `find.byType(HexBottomNav)` check alone would have passed on
  the buggy build too, since a pushed route still leaves the covered widget in the tree.
- **DEF194** — the `catch (_)` in `settings_screen.dart`'s retro-tightening audit read stays a swallow
  (a failed audit GET must never make a genuinely-succeeded PATCH look failed) but now shows a
  `settingsRetroAuditFailed` snackbar — "Couldn't check your holdings against the new limit — open
  Portfolio to verify." — on the catch path. Test reuses the `settings_screen_risk_limits_test.dart`
  harness with a fake `ApiClient` whose `auditMandateHoldings` throws; confirms BOTH the save-succeeded
  snackbar AND the disclosure snackbar appear (had to pump past the first SnackBar's ~4s default
  duration for the queued second one to surface — Flutter shows one at a time).
- **DEF198** — `AiCoachCorpus.totalCount` (295) replaces the inline `'280 questions...'` literal;
  the copy is now routed through the ARB pipeline for the first time (`aiCoachEmptyStateHint`,
  localizable). **Disclosure, not a full fix**: no `/v1/ai_coach/*` response carries a total-entry
  count today, and adding one is a `backend/` change outside this batch's fence — documented in
  `AiCoachCorpus`'s doc comment in `lib/models/ai_coach.dart`. Guarded by a test that sums
  `content/ai_coach/*.json` on disk and asserts it equals the constant, so a future corpus change
  fails the build instead of shipping stale silently (the "refiled at 310" scenario the assign warned
  against).

## Mutation matrix (acceptance 6)

Reverted DEF190 (`home_shell.dart` + `portfolio_screen.dart`) and DEF194
(`settings_screen.dart` + the three ARBs/generated l10n) via `git stash`, kept the new tests, re-ran:

- DEF190 (`home_shell_test.dart`): RED — `Navigator.of(...).canPop()` is `true` and a second
  `JournalScreen` renders, against the pre-fix code.
- DEF194 (`settings_screen_retro_audit_test.dart`): RED at runtime (`settingsRetroAuditFailed` never
  renders) when only `settings_screen.dart` is reverted; a full ARB+source revert instead fails to
  *compile* (missing getter) — both are legitimate RED, the second just fires earlier.

The other four (DEF164/170/174/198) were also confirmed RED against unmodified source the same way,
though the assign only required it for DEF190/DEF194 — reported here for completeness, all four came
back RED, none came back GREEN.

## Registers

All six row files flipped to `fixed` with `(AT:R65 DEF###)` in `docs/defect/_registry/`, regenerated
`docs/defect/def_list.md` via `gen_registers.py gen def`, row files + regenerated table committed
together (DEF159).

## Fences respected

Never touched `backend/` (DEF198's real fix needs it — disclosed above and in the row file, not
worked around). Never touched `mobile/lib/widgets/hex_avatar.dart` or the HexAvatar label path —
DEF174 wraps HexAvatar's *caller* (`room_screen.dart`) in `Semantics`, doesn't modify HexAvatar itself.
DEF170 is a when-to-render fix only — no restyling, same `ShaderMask`/gradient as before, now
conditional.

Committed `c91ab4b7` on `lane/MOBILE-BATCH1.coder.mobile`, pushed to origin. Audit bridge filed at
`orchestration/audit/cr/MOBILE-BATCH1.architect.md` (`SUBMITTED: round 1`).

STATUS: READY_FOR_AUDIT (round 1)
