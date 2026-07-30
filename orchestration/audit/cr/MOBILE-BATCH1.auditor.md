<!-- auditor lane — track U (Kimi). CR052 / orchestration/audit/PROTOCOL.md. -->
# MOBILE-BATCH1 — auditor

VERDICT: COMPLETE (round 1)

Audited `lane/MOBILE-BATCH1.coder.mobile` @ `c91ab4b7` in scratch worktree
`.claude/worktrees/audit-MOBILE-BATCH1` (never `main`, never the builder's
tree). SCOPE: `cr` — full evidence list. Tiered audit policy: targeted +
registers + blind mutation up front, full flutter suite backgrounded during
the file:line read.

---

## Round 1

Six small mobile defects, one lane. Each fix read at file:line, each covered
by a test I ran myself, and my own blind mutation landed exactly where it
should. Nothing to bounce.

### The six, verified

- **DEF164** (`friendly_error.dart`, `revenuecat_purchase_service.dart`):
  `_statusRetryable` is now the single source — `isRetryable()` and the
  `_forStatus` copy both consult it, so a non-retryable 4xx can never again
  ship "retry" copy. New non-retryable copy is honest ("that request wasn't
  accepted"), no status-code leak. The two `e.toString()` leaks in the
  RevenueCat service now route through `friendlyError()` + `debugPrint`.
  The DEF148 guard tests (no call site may bypass, the sweep reaches the
  reported file) still pass — the new call sites are inside the sweep's
  allowance.
- **DEF170** (`portfolio_screen.dart`): the sector-legend fade is now gated
  on `!_controller.hasClients || _controller.position.extentAfter > 0`
  before the `ShaderMask` is applied — "more below" stops signalling at the
  bottom of the scroll, and the `hasClients` short-circuit guards the
  pre-layout frame. The CR118 cap tests (fixed height, 13th sector
  reachable, fade only when cut) still pass.
- **DEF174** (`room_screen.dart`): all four roster states (interrupted /
  thinking / responded / standing-by) fold into one `Semantics` node with
  `excludeSemantics: true`, labelled `roomAgentStatusSemantic(agent,
  statusWord)` — naming the agent AND its state. Scoped to the trailing
  indicator only, so the agent-name Text and headline stay independently
  readable. ARB key present in en/ar/ms. The folding matters: the next new
  state can't reopen the gap by adding another colour-only branch.
- **DEF190** (`home_shell.dart`, `portfolio_screen.dart`): `HomeShell` now
  `ref.listen`s `activeTabIndexProvider` with a `next != _tab` guard (the
  tap handler's own synchronous write is a no-op there, not a second
  rebuild); `_JournalPointer` is a `ConsumerWidget` writing
  `activeTabIndexProvider = 2` instead of pushing an orphaned
  `JournalScreen` over the shell. I verified index 2 against
  `home_shell.dart:29-35` — it IS `JournalScreen()`. The stranded import of
  `journal_screen.dart` in portfolio_screen is gone.
- **DEF194** (`settings_screen.dart`): the post-save retro-audit
  `catch (_)` now surfaces a snackbar (`settingsRetroAuditFailed`), mounted-
  guarded, worded "could not check your holdings…" — the honest third
  state, neither "you are compliant" nor "your save failed" (the save DID
  succeed). En copy carries the `retranslate:[ar,ms]` marker per project
  convention. **This closes my own CR101-MOBILE r1 MINOR m1** — the exact
  silent-bare-catch I flagged there.
- **DEF198** (`ai_coach.dart`, `ai_coach_screen.dart`): the stale '280
  questions' literal is now `AiCoachCorpus.totalCount = 295`, interpolated
  through `aiCoachEmptyStateHint(count)`. I hand-counted
  `content/ai_coach/*.json` against 295 today — it matches. The lane
  discloses the count is hand-maintained and the backend count endpoint is
  NOT done — see OUT-OF-SCOPE.

### Reproduced measurements

- Full flutter suite from the worktree: **338 passed** (builder claims 338,
  baseline 330 — the +8 are the three new test files). Backgrounded during
  the read per the tiered policy.
- `flutter analyze --no-fatal-infos`: exit 0, **5 issues** — the same 5
  pre-existing infos as the CR101-MOBILE baseline.
- Targeted run (the 6 touched test files): **43 passed**.
- `gen_registers.py verify all` from the worktree: DEF 199 / CR 128, OK.
- Blind mutation (mine, not the builder's revert-proof): removed the entire
  `ref.listen(activeTabIndexProvider)` block from `home_shell.dart` →
  exactly **1 RED** (`DEF190: the bottom nav survives "Review in Journal"…`).
  `git checkout --` restored byte-identical (`git status --short` empty),
  re-green. The honest nav-switch is behaviourally pinned, not decorative.

### Observations, not findings

- The diff carries formatter churn (line-length reflow) across
  `room_screen.dart` / `portfolio_screen.dart` beyond the six fixes —
  cosmetic, no behaviour, but it does inflate the +1035/−205 stat. Noted so
  the next reader doesn't mistake it for scope creep.

### OUT-OF-SCOPE (architect mints IDs)

- **DEF198's backend half:** no server endpoint exposes the live corpus
  count; `totalCount = 295` is a hand-maintained client constant that WILL
  drift the next time `content/ai_coach/` grows. The lane disclosed this
  honestly rather than inventing an endpoint — correct call, but the drift
  hole wants a CR (serve the count, or generate the constant at build time).

MINORs: none. DoD enforcement waived per standing instruction.
