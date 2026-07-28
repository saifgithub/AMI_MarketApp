STATUS: READY_FOR_AUDIT (round 1)

<!-- coder-owned lane file for CR098-MOBILE-LIVE, written by the Architect on the coder.mobile build's
behalf. State machine driven by the STATUS line above (byte-exact). -->

# CR098-MOBILE-LIVE — coder.mobile lane (in-run locked-chair surface)

**Item:** CR098 scope item 8, part 1 of 2 — the streaming-run surface for the analyst tenure roster
pull-back: `agent_withheld` (locked chair + roster countdown) and `live_data_notice`'s new
`withheld_tenure` value. `GATE: independent` (paywall-adjacent disclosure, DEF059-inversion risk).

**Spec:** `docs/forward_planning/CR098_room_analyst_pullback/CR098_room_analyst_pullback.md`
(Amendment 1, Amendment 2, scope item 8) + this lane's own assign
(`orchestration/dispatch/lanes/CR098-MOBILE-LIVE.assign.md`), which carries the wire contract lifted
verbatim from `CR098-ROOM.coder.room.md`.

**Built on:** `lane/CR098-MOBILE-LIVE.coder.mobile`, merge-base `ce6d55e` (the dispatch commit) —
`git diff ce6d55e..HEAD` is the full, isolated diff (10 files, +588/−12, all under `mobile/`).

## Acceptance-#2: current behaviour recorded first (verified before any fix)

Read, did not assume. `parseRoomSseEvent`'s switch in `api_client.dart` had no `agent_withheld` case
— it hit the `default:` branch (`api_client.dart:184` pre-fix), which logs and returns `null`. Because
`streamRoom`'s consumer loop does `if (parsed == null) continue;` (`api_client.dart:744` pre-fix), the
event never reaches `room_providers.dart`'s own switch at all — its own `default:` (also missing the
case) is never even exercised. **Confirmed: today the event is dropped silently, twice over, before
the first switch's own fallback is reached.** This matches D2/D3 in the assign exactly.

## What shipped

1. **`api_client.dart`** — added the `agent_withheld` case to `parseRoomSseEvent`, returning
   `{kind, agent_id, reason, next_step_agent, next_step_days}` verbatim from the wire payload.
2. **`room_providers.dart`** —
   - New `WithheldAgentInfo` (agentId, reason, nextStepAgentId?, nextStepDays?) and
     `RoomState.withheldAgents: Map<String, WithheldAgentInfo>`.
   - New `agent_withheld` case in `RoomNotifier.start()`'s switch: records the info AND mirrors the
     agentId into `RoomState.order` (never into `transcript`) so the console renders the chair inline,
     in the analyst's real seat, at the point the event arrived — which the contract guarantees is
     before any ANALYSTS-phase agent speaks (D4).
3. **`room_screen.dart`** —
   - `_WithheldAgentChair`: renders a dimmed avatar + lock icon + `{agent} — off your roster on this
     plan`, plus a countdown line ONLY when `nextStepAgentId`/`nextStepDays` are both non-null — and
     that countdown names the roster's NEXT agent, never the withheld chair's own agent (acceptance
     #5/#6). The render loop (`state.order` for-loop) now checks `state.withheldAgents[agentId]` first
     and renders the chair instead of `_AgentLine` when present.
   - `_LiveDataNoticeCard` extended for `withheld_tenure`: distinct copy (`roomLiveDataFeedTenure`),
     distinct accent (`hexPurple`, not the `hexAmber` used for `withheld_paid`), and its own CTA
     (`roomLiveDataTenureUpgradeCta` = "UPGRADE YOUR PLAN") — never the credits CTA
     ("UPGRADE FOR LIVE DATA"). Both CTAs can open the same underlying `showUpgradeSheet` (it already
     bundles plan tiers + credit packs — there is no separate plan-only screen to route to), but the
     disclosure copy and button label are never shared, which is what D1 requires ("own copy and its
     own CTA").
4. **l10n:** 4 new EN strings in `app_en.arb` (`roomLiveDataFeedTenure`, `roomLiveDataTenureUpgradeCta`,
   `roomAgentWithheldChairLabel`, `roomAgentWithheldRosterNote` — the last is ICU-plural on `days`).
   `flutter pub get` regenerated `lib/generated/l10n/`. **`ar`/`ms` fall back to EN** —
   `retranslate:[ar,ms]` for these 4 keys, per project convention (translation is a separate lane, not
   blocking).

## CR104's new REQUIRED scope (thin fundamentals/technicals) — investigated, no wire contract exists

Read `room_prompts.py:_format_profile` and `room_runner.py:_profile_for_ticker` (`field_state` per-field
provenance, CR104) and `api/room.py`'s SSE serialiser end to end. Finding, stated plainly:

- **Fundamentals/technicals genuine-absence has NO client-visible signal.** `field_state` (live /
  withheld_paid / withheld_tenure / unavailable, per numeric field) governs ONLY the text baked into
  agent prompts — it is never serialised onto the wire. The client's only structured, client-facing
  signals remain `agent_withheld` (whole-chair roster pull-back) and `live_data_notice.live_data.
  {news,social}` (feed-level, news/social only — never extended to fundamentals/technicals).
- **Structurally, this means the DEF059 inversion the auditors flagged cannot currently occur for
  fundamentals/technicals from the client's side**, because nothing client-side keys a CTA off prose
  content. `agent_withheld` only fires when the backend has actually decided to withhold Market's
  *entire chair* (roster pull-back, tenure-gated) — never when yfinance merely had a bad day for a
  present, running analyst. A genuinely-thin session (Market analyst present, technicals
  `field_state=unavailable` from a real provider gap) renders exactly like any other transcript line
  in `_AgentLine` — plain markdown text, no banner, no CTA, no error, no paywall. That already
  satisfies the assign's fallback instruction ("render absent fields in a visibly non-alarming way...
  do not ship a screen that shows a thin Room as an error or as a paywall") **by construction**, with
  zero code change, because no existing code path treats agent prose as anything other than prose.
- **Recommendation: this is a separate, small lane, not scope creep onto this one.** If Saiful wants an
  explicit "this session's data was thin" in-transcript affordance (e.g., a small badge distinct from
  both the locked-chair and live-data-notice mechanisms), it needs a NEW wire signal first — today
  there is nothing to build the client half against. Flagging this rather than inventing a client-side
  heuristic that would have to guess at prose content (fragile, and exactly the kind of "prompt
  instructions are not controls" trap CR038/CR040 warn against).
- **Not independently verified against a live thin-data run** (no melehost access from this session;
  static code read only) — noted as an honest gap, not claimed as tested.

## Acceptance checklist

| # | Item | Status |
|---|---|---|
| 1 | `flutter test` green; `flutter analyze` on touched files clean | done — 86/86 passed on `test/services/ test/widgets/`; `flutter analyze --no-fatal-infos` on the 5 touched non-generated files: 0 issues. Did NOT run the full untouched-file analyze (assign notes 5 pre-existing unrelated issues elsewhere) |
| 2 | Current behaviour recorded first | done — see above, both switches' `default:` branches confirmed, first one short-circuits the second |
| 3 | `agent_withheld` parses in both switches; test proves it reaches state | done — `test/services/api_client_room_stream_test.dart` (parse contract, incl. next_step-both-null) + `test/widgets/room_agent_withheld_test.dart`'s first group drives the REAL `RoomNotifier.start()` via a scripted `ApiClient` (not a fixture-seeded state) and asserts on the resulting `RoomState` |
| 4 | Locked chair renders in seat from start of ANALYSTS phase | done — mirrored into `order` at event-arrival time (contract guarantees pre-speech emission); widget test proves the chair sits ahead of a real agent line in the same `order` list |
| 5 | Countdown is roster-level, not per-agent; asserted on rendered string | done — test asserts the countdown names the OTHER (next-step) agent, e.g. a Market-analyst chair's countdown names "Social Media Analyst", never "Market Analyst" |
| 6 | next_step both null ⇒ chair renders, countdown omitted, no "null days" | done — dedicated test; `showCountdown` guards on both non-null |
| 7 | `withheld_tenure` renders distinctly with its own CTA; mutation-checked | done — distinct copy/accent/CTA; **mutation physically applied** (collapsed the tenure branch onto the credits CTA in `room_screen.dart`), test confirmed to go RED, then reverted (`git diff` against the prior commit is empty — clean revert) |
| 8 | No agent voice sells | done by construction — no agent prompt files touched; all new copy lives in app-chrome widgets (`_LiveDataNoticeCard`, `_WithheldAgentChair`), never in `_AgentLine`'s markdown-rendered agent text |

## Out of scope respected

- Did not touch the verdict surface (`_VerdictCard`, `opinions_not_included`) — that's
  `CR098-MOBILE-VERDICT`'s lane, sequenced after this one per the assign's HOT-FILES note.
- Did not read the CR098 doc's backend-only sections (scope items 1–7, 9; rollout; governance) —
  budget-conscious per the assign's instruction to read only Amendment 1/2 + item 8.
- No backend, `orchestration/`, or docs edits beyond this hand-off + the row file below.
- Nothing backgrounded; all commands (`flutter pub get`, `flutter analyze`, `flutter test`) ran to
  completion in the foreground before this hand-off was written.

## Not independently verified

- No live-device / melehost smoke test (this session has no backend access) — static analysis + unit
  tests only, as the verification split specifies.
- `ar`/`ms` translations for the 4 new strings — flagged above, translation is a separate, non-blocking
  lane per project convention.
- The CR104 thin-fundamentals/technicals finding is a code-read conclusion (traced `field_state`
  through `room_prompts.py`/`room_runner.py`/`api/room.py`), not confirmed against a live run showing
  a genuinely-thin fundamentals block end to end.

---

STATUS: READY_FOR_AUDIT (round 2)

Round-2 fixes made by the **Architect directly**, not by this instance — the coder lane was closed
when the round-1 verdict landed, and both findings were small, prototyped by the auditor, and
verifiable inline (Flutter runs on the Mac). Lane branch `lane/CR098-MOBILE-LIVE.coder.mobile` is now
at `44dcc0f`.

- **MAJOR** — re-seat withheld chairs when `_recoverViaPolling` rebuilds `order`.
- **MINOR** — shape-check the `agent_withheld` payload instead of hard-casting it.

Measured foreground in the lane worktree: full `flutter test` **122 → 128**, `flutter analyze` clean
on both touched files, and both fixes mutation-proved (removing the re-seat → exactly the 2 new
recovery tests RED; restoring the hard casts → exactly the 4 new malformed-payload tests RED; tree
restored, 128 green). Detail in `orchestration/audit/cr/CR098-MOBILE-LIVE.architect.md` round 2.

---

DISPATCH: ACCEPTED

Auditor `VERDICT: COMPLETE (round 2)` delivered at `b8a90e0`, audited SHA `44dcc0f`, reproduced
independently in a fresh detached worktree (128/128, both fixes mutation-proved RED at exactly the
expected tests). The round-2 missing-DoD-table MAJOR was downgraded to recorded-not-scored by the
stakeholder waiver (`AMI_TRADE_BINDINGS.md` gap-fill 7). Merged to `main` by the Architect.

**Still open, and carried OUT of this lane deliberately:**

- **`ar`/`ms` for the 4 new strings** — `roomLiveDataFeedTenure`, `roomLiveDataTenureUpgradeCta`,
  `roomAgentWithheldChairLabel`, `roomAgentWithheldRosterNote`. The last takes an `int` and needs
  **plural forms per locale**, not a string swap. Generated files currently carry EN in all three.
- **No device / melehost verification.** `main` is under an active promotion hold and nobody has seen
  this render on a phone.
- **The thin-session wire signal** — a genuinely thin session (analyst present, `field_state=
  unavailable`) still has no wire signal at all. Needs a **backend** signal before any client work.
