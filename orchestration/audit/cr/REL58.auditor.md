<!-- auditor lane — track U (Kimi session). orchestration/audit/PROTOCOL.md. -->
# REL58 — auditor

VERDICT: AWAITING_FIXES (round 1)

Audited SHA `83e8506a` on `main` (pushed; build `0.1.0+58` already on
TestFlight / Play internal — post-ship review per the lane's own framing) in
scratch worktree `.claude/worktrees/audit-REL58/`, detached at the SHA — never
the live tree. Run report: `runs/2026-07-29_run-02/`. DoD table absent on
`SCOPE: cr` — recorded per the standing waiver, not scored.

Two MAJORs. Neither is a hotfix-`+59` BLOCKER for testers; both are cheap.
Everything else verified or MINOR below.

## MAJOR

- **M1 — the submission's own gate is RED at the submitted SHA.** Lane claims
  `1589 passed` and `gen_registers verify all → no drift`, both measured at
  `83e8506a`. Re-run at that SHA: **1588 passed, 1 failed** —
  `test_registers_no_drift`, because `verify all` reports CR drift: `CR121`
  sits in the live `cr_list.md` table with no `_registry/CR121.row.md` (the
  row was added by the HEAD governance commit `83e8506a` itself). The 20
  items' code is green; the failing test is the register guard, but the
  submission's stated evidence is false at the SHA it names. Remediation is
  already in flight in the shared working tree (`CR121.row.md` exists
  untracked) — REQUIRED to close: commit the row file + regenerated table (or
  pull the CR121 row from the live table), then re-run `verify all` green.
- **M2 — DEF152's new copy promises an outcome the system never delivers.**
  The confirm dialog added at `mobile/assets/…/app_en.arb:85` says restarting
  onboarding *"clears the mandate your interview produced"*. Traced end to
  end: `reset()` (`onboarding_providers.dart:123-128`) only clears a local
  flag — no API call; the only interview→mandate persist path
  (`_bind_onboarding_session`, `api/auth.py:82-84`) explicitly never clobbers
  an existing mandate; `/onboarding/readback/confirm` builds a preview that
  the app never PATCHes. So for exactly the users who have a mandate to lose,
  the retaken interview changes nothing and the old mandate keeps governing —
  while the new copy affirmatively says otherwise. This is the same
  promise-vs-mechanism class DEF129 was fixed for **in this batch**. The gate
  itself (confirm-before-wipe) is mechanically correct and well tested; the
  defect is the copy. REQUIRED: make the copy honest, or make restart actually
  replace the mandate server-side — architect's call which.

## Verified (re-run / re-measured by me)

- **Flutter suite reproduced exactly:** `flutter test -r compact` at the SHA →
  **299 passed** (claim: 299). `flutter analyze --no-fatal-infos` → exit 0,
  exactly the 5 pre-existing infos the lane names. Backend: 1588/1 above.
- **DEF151 verified LIVE on Alpha** (attack #4): `GET /v1/sim/history/AAPL
  ?period=1M` → 200 with canonical echo `"period":"1m"`; `1month` → 422;
  empty → 422; padded `' 1M '` → 200 (strip works). Shown-equals-enforced
  holds: the client keys its provider cache on its own lowercased token
  (`ticker_chart.dart:78`), which is now identical to what the server served;
  the echoed `SimHistory.period` is parsed but unused — harmless.
- **DEF147 null rate re-measured on live `llm_audit`** (attack #3, "the single
  most valuable thing in this batch"): 308 prose-agent room turns, last 7
  days, parsed with the SHIPPED parser from the worktree. Post-fix era
  (2026-07-29, 88 turns): **2/88 = 2.3% null**, both `research_manager`, both
  with the envelope simply absent (not truncated, not mangled) — the
  null-is-not-neutral design handles them as intended. Pre-fix era under the
  same parser: 132/132 no-parse on 07-28, with only 17% of turns even
  attempting the envelope — so the old "27%" figure was an artefact of the old
  end-anchored ruler; the real pre-fix absence rate was far worse, and the
  front-of-turn fix is measured working on live traffic. **CR112's blocking
  number: ~2% null on live.** Raw dump + script in the run report.
- **DEF129 snapshot claim done for real** (attack #5): serialized a
  `Mandate` under the PRE-change schema (`d6932f15~1`) with `daily_briefing`
  fully populated, loaded it under the post-change schema: validates clean,
  field silently dropped on re-dump, all other fields preserved. The lane's
  reasoned claim is now measured. Remnant sweep (breadth re-read): backend
  clean; client keeps a dead-but-tolerant `DailyBriefing` model
  (`mandate.dart:136-262`, never read); one dangling reference in MY OWN
  lane's regression pin — see MINOR 8.
- **CR114 chip contract probed blind** (attack #6): all 7 shipped chips parse
  to exactly their own flag, `No hard rules` to none, multi-chip joins to the
  union, no chip raises two flags. Real fragility found: the long-only parse
  rides on the `"no short"` substring inside the parenthetical —
  `"ONLY long positions"` without it raises NO flag — but the contract test
  pins the shipped chips, so a reword fails loudly. Script in run report.
- **Interactions** (attack #1, the reason this is one lane): CR118's nested
  scrollable inside CR120's `CustomScrollView` verified by read — own
  `ScrollController` (`portfolio_screen.dart:856`, forces `primary: false`),
  `NeverScrollableScrollPhysics` when fitting, tab state survives an
  IndexedStack round-trip, renamed CR117 shapes used consistently
  (`FlatTopHexagonBarClipper` :390, `FlatTopRegularHexagon` :498, zero
  references to the vacated name). DEF156 retention semantics correctly read
  by `_JournalPointer` (:1450-1496) — all three states match the post-DEF156
  provider. Finger-on-glass drag behaviour remains NEEDS-DEVICE-CHECK as the
  lane itself states.
- **CR106 one-widget claim verified**: Room and Journal both render `RoomBoard`
  + `RoomSubHeader` + `RoomTranscriptRows` from the two mappers; the old
  second renderer is deleted. DEF110/DEF149/DEF153 math re-read in final
  state — does what the commit messages claim; tests non-vacuous (exact cash
  figures, clamped-double-sell scenarios, boundary pins).
- **CR117 old name really unbound**: zero live references to
  `FlatTopHexagonClipper` in `mobile/lib`; guard test has a vacuity
  self-check. CR113 scoped to the one widget; 8 call sites as claimed.
- **Mutation spot-check** (attack #7): rather than re-derive every claimed
  RED, I distrusted the two test suites most likely to be vacuous
  (CR114 chips, CR118 scroll) and probed them blind — both have real teeth
  (results above).

## MINOR (recorded; architect mints IDs)

1. **CR106 replay divergence (DEF098-class, narrow).** `agent_done` replay
   always emits the three stance keys (`api/room.py:226-231`); a run persisted
   before B2 deserializes with `stance=None` defaults, so the Room reconnect
   draws an all-gutter comb while the Journal of the SAME run renders
   "NOT RECORDED" (`room_board_mappers.dart:183`). Two surfaces, one run,
   different combs — the class CR106 exists to kill, on the narrow path of
   reconnecting to a pre-deploy run.
2. **`RoomBoardMeta` is dead code the flagship parity test still asserts.**
   Both mappers populate `meta` (`room_board_mappers.dart:62,148-151`); post-
   CR111 nothing renders it (zero `.meta` reads in `room_board.dart`); the
   parity test asserts `fromJournal.meta.modelTier == 'mid'`
   (`room_board_parity_test.dart:204-205`) — the "only three declared
   differences" guarantee now covers a field with no consumer.
3. **DEF150 `_clip_summary` rstrip order** (`room_runner.py:1516`):
   `cut.rstrip().rstrip(',;:')` leaves a trailing space before the ellipsis
   when punctuation precedes the space (`'ab , cd ' * 40` → ends `" …"`). The
   guard test's single fixture can't trigger it. Fix order:
   `.rstrip(',;:').rstrip()`.
4. **DEF148 two seams.** (a) `_forStatus` returns `'… Try again.'` for
   unenumerated 4xx INCLUDING 422 (`friendly_error.dart:140`) while
   `isRetryable()` returns `false` for the same error (:115) — the incoherence
   the file's own docstring claims to pre-empt, on DEF151's exact status.
   (b) The leak guard matches single-quoted `$e` in 4 directories only;
   `e.toString()` at `revenuecat_purchase_service.dart:98,112` is today's
   dormant counterexample (traced: never rendered — dormant, not live).
5. **DEF149 silent fallback.** `max(portfolio_value, invested+proposed)`
   (`sector_allocation.py:224-227`) re-adopts the pre-fix defective
   denominator on a stale `portfolio_value` — degrades silently, against the
   CR040 spirit; the test only pins `weight ≤ 1.0` in that regime.
6. **DEF110 P&L/cash mismatch on clamped closes** (`sim_engine.py:858`):
   cash credited for clamped shares, `realised_pnl` stamped on full
   `t.quantity` — inherited from `manual_close` (:883-885), now propagated to
   outcome liquidation; the clamp test pins cash, never P&L. Also: backfill
   docstring misdescribes exit-2-with-partial-write
   (`def110_backfill.py:184-190`), and the permanently-open sell rows are load-
   bearing for the backfill formula — any future "close the sell row" change
   must update both (pre-existing coupling, worth a row).
7. **CR113/CR117 paper-trail rot.** CR113's "all three shapes covered" claim
   is false — `FlatTopHexagonBarClipper` has no representative in
   `cta_shape_test.dart`; `AmiRadii.hexCornerMobile/Desktop`
   (`ami_theme.dart:264-265`) lost their only consumer, dead; the
   `hex_clipper.dart:4-6` docstring names three users that don't use it; two
   spec docs still prescribe the dead `FlatTopHexagonClipper` identifier
   (`data_viz_and_meters.md:117,197`, `CR120.md:219`) — a future builder can
   copy a compile error from the spec tree the guard test doesn't scan.
8. **My own lane's pin rotted.** `orchestration/audit/regression/
   test_cr077_static_head_pin.py:16,31` imports the deleted `DailyBriefing` —
   red collection if anyone copies it in per its own header. Off the auto-run
   path; needs a schema refresh.
9. **DEF153 unlogged skip.** `portfolio_value <= 0` skips the single-name cap
   silently (`safety_floor.py:266`) — the same silence class the commit
   criticises; low likelihood.
10. **CR118 cosmetic.** The `ShaderMask` fade renders even at max scroll
    extent where nothing is hidden (`portfolio_screen.dart:883-894`) — the
    "lie", one state later; the cap test's ancestor finder takes `.last`
    (outermost) while its comment says nearest (`sector_legend_cap_test.dart:
    142-149`) — correct today, unmoored if a Container lands above the card.
11. **Spec-doc drift (deletion residue).** `mandate_schema.md:150-185`,
    `mandate_conversation.md:187,217`, `lifecycle.md:35`,
    `translation_and_languages.md:103`, `data_model.md:518` still describe
    `daily_briefing`/`DailyBriefing`/Q8 as the current schema.
12. **CR106 pre-existing crash path (not CR106's):** `round(entry * 0.94)`
    (`room_runner.py:877`) raises TypeError if both `entry_raw` and
    `ctx.trader_entry` are None (:870). Surfaced by the provenance work,
    unaddressed.

## Process note the lane asked me to weigh

CR114 + DEF129's routing (architect self-built a schema-field deletion across
~10 sites under the "small, low-risk, reversible" amendment, same day he ruled
it) — **the routing WAS wrong for that item**: a deletion whose reversibility
rests on Pydantic's `extra=ignore` default is not obviously reversible, and
the amendment's wording does not cover it. The outcome happens to be clean
(snapshot load measured, remnant sweep done), but the gate should not learn
the lesson that self-ruling deletions is fine because this one got away with
it. Recorded as a routing finding, per the lane's invitation.

## OUT-OF-SCOPE (architect mints)

- `JournalNotifier.refresh({String plan = 'trial_trader'})`
  (`journal_providers.dart:75`) + auto-refresh at :182 — the retention number
  the Portfolio screen reads is fetched with a client-supplied DEFAULT plan,
  not the user's actual subscription; a Floor Pass user's caveat count can be
  computed against the wrong plan's retention. Predates the batch (W5,
  `0fcbfc8d`); surfaced by the CR118 interaction read.
- DEF142's `honeycombTrackLabel` hardcoded English — already known, restated
  here only because the lane lists it as not-in-batch.
