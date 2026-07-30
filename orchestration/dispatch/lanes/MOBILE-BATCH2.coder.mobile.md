<!-- hand-off — coder.mobile. CR052. -->
# MOBILE-BATCH2 — coder.mobile hand-off

STATUS: READY_FOR_AUDIT (round 1)
BRANCH: lane/MOBILE-BATCH2.coder.mobile
WORKTREE: .claude/worktrees/coder.mobile-MOBILE-BATCH2
COMMITS: c16f1893 (code+tests), 8fb62472 (registers)

## Scope delivered

**DEF173 — fixed.** `JournalNotifier.refresh()` no longer takes `plan` as a
parameter at all (was `{String plan = 'trial_trader'}`). It reads
`_ref.read(mandateNotifierProvider).mandate?.plan` every call and, if the
mandate hasn't loaded yet, makes **no network call** rather than guessing —
a wrong plan is worse than a stale read. `MandateNotifier.refresh()` now
also re-triggers the Journal refresh on success (mirroring the existing
`patch()` re-trigger), so the Journal self-heals once the real mandate
lands, matching every real call site (none of which ever passed `plan`).
`ApiClient.listJournal`'s `plan` param lost its default too — it's
`required` now, so a future caller that skips deriving it fails to
compile instead of silently landing on `trial_trader`.

**Chose "derive from the authenticated user," not "delete the default and
keep it client-supplied."** The mandate (`GET /v1/mandate/{id}`) is
already the server-authoritative plan source the rest of the app trusts
(see `purchase_providers.dart`'s comment on `_refreshEntitlementFromBackend`)
— reusing it is the closest a mobile-only lane can get to "derive
server-side" without touching `backend/`.

**Residual, disclosed not fixed:** the backend's `GET /v1/journal/{user_id}`
still accepts `plan` as a client-supplied query param with its own default
(`backend/app/api/journal.py:55`). A raw HTTP client bypassing the app
could still lie about its plan. That's a `backend/` change and this lane
is fenced off from `backend/` — flagging it as a likely follow-up Defect,
not silently absorbing it into "fixed."

**DEF162 — fixed.** `RoomBoardMeta` deleted from `room_board.dart`
(dead since CR111 — zero `.meta` consumers anywhere, confirmed by grep),
its population removed from both mappers in `room_board_mappers.dart`,
and the two assertions in `room_board_parity_test.dart` that were the only
thing still exercising it. Checked before removing: the snapshot fields
`RoomBoardMeta` wrapped (`payload['model_tier']`, `entry.mandateVersion`)
are read directly off `JournalEntry`/its payload elsewhere — `RoomBoardMeta`
depended on the snapshot, not the other way round, so nothing in the
snapshot depends on the `meta` key.

**DEF167 — code residues (a)/(b)/(c) cleared, row stays `open`** (docs
half is the Architect's, per the assign).
- (a) `cta_shape_test.dart` gets a `FlatTopHexagonBarClipper` case at a
  300×44 (~6.8:1) bar — deliberately far from the regular hexagon's fixed
  2:√3 (~1.1547:1). Proves the shape mechanically: the octagon keeps a
  vertical edge down each side (`(w, c)` to `(w, h-c)`); the hex-bar's two
  end-diagonals converge to a single point at the vertical middle instead,
  so a point just off that vertical edge is inside the octagon and outside
  the hex-bar at the same envelope and corner size.
- (b) `AmiRadii.hexCornerMobile`/`hexCornerDesktop` deleted — zero
  consumers, confirmed by grep before deleting.
- (c) `hex_clipper.dart:4-6` no longer lists `HexButton` as a
  `CutCornerOctagonClipper` consumer — CR113 already removed that clip
  (`cta_shape_test.dart`'s own first test proves `HexButton` renders no
  `ClipPath` at all); the only remaining reference in `hex_button.dart` is
  a doc comment describing what CR113 removed, not live usage.

**DEF171 — code residue cleared, row stays `open`** (docs half is the
Architect's). Swept the dead `DailyBriefing` client model from
`mandate.dart`: the class itself, the `dailyBriefing` field + required
constructor param on `UserMandate`, and its population in
`UserMandate.fromJson`. It was populated but never read outside
`mandate.dart` — confirmed independently by grep before deleting, per the
row's instruction. Fixed the three test files that constructed it:
`risk_limits_section_test.dart`, `settings_screen_retro_audit_test.dart`,
`settings_screen_risk_limits_test.dart`.
`grep -rn "DailyBriefing\|dailyBriefing\|daily_briefing" mobile/lib mobile/test`
→ zero hits.

## Verification

- `flutter test -r compact` (piped through `tr '\r' '\n'`): **341 passed**,
  0 failures. Baseline 338 + 3 new tests (2 in
  `journal_plan_trust_boundary_test.dart`, 1 in `cta_shape_test.dart`).
- `flutter analyze --no-fatal-infos`: exit 0, **5** known infos (matches
  the expected count — none of them touch files this lane edited).
- **Mutation testing (acceptance #5):**
  - DEF173: `git stash`'d only `journal_providers.dart` back to its
    pre-fix version (old `refresh({String plan = 'trial_trader'})`, no
    mandate read). Both new tests in `journal_plan_trust_boundary_test.dart`
    went **RED** — `Set:['trial_trader']` instead of `{'floor_pass'}`, and
    a non-empty network-call list where the "no mandate loaded" case
    expects empty. Restored → both **GREEN** again.
  - DEF162: `git stash`'d only `room_board_parity_test.dart`'s edit,
    restoring the two old `fromJournal.meta.*` assertions against the
    **new** (fixed) `room_board.dart`. Compile error — `The getter 'meta'
    isn't defined for the type 'RoomBoardData'` — **RED**, proving
    `RoomBoardMeta` is genuinely gone from the type surface, not just
    unreferenced. Restored → **GREEN** again.
  - Nothing came back green that should have gone red.
- DEF167(b)/(c) and DEF171 are pure deletions per the assign's exception —
  proof is the grep output above plus the green suite, not a new failing
  test.

## Fences respected

Did not touch `backend/` (see DEF173's disclosed residual above). Did not
touch `mobile/lib/widgets/hex_avatar.dart` or the `HexAvatar` label path
(DEF142's lane). No visual restyle — every change is either dead-code
removal, a trust-boundary fix with no rendering change, or a doc-comment
correction. Did not touch `docs/` for DEF167/DEF171's spec halves or the
vacated-name guard — those are the Architect's, per the assign.

## Registers

DEF162, DEF173 → `fixed`. DEF167, DEF171 stay `open` with a note on which
residues this lane cleared. `docs/defect/def_list.md` regenerated via
`scripts/registers/gen_registers.py gen def`, row files + regenerated
table committed together (commit `8fb62472`), explicit pathspec.

## Next

Ready for integration on your own verification (sprint mode, no
`.architect.md` submit file per the assign). Branch is on
`lane/MOBILE-BATCH2.coder.mobile`; pushing to origin now.
