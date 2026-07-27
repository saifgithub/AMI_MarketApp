# CR090-MOBILE — closed lane archive (AT:R65, 2026-07-27)

Audited **COMPLETE round 1** by an Architect-spawned premium auditor. Merged to `main`; `flutter test` 97/97 exit 0 re-verified post-merge. Worktree + branch reaped.

---

## assign

<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR090-MOBILE — assign

KIND: code
INSTANCE: coder.mobile
GATE: spawned    <!-- Not a money lane: this renders a disclosure, it decides no debit. But it is the honesty half of a money feature, and the DEF059 inversion class lives here (see D3), so it does not ship ungated. Architect-spawned auditor at premium, same treatment as CR100. -->
ACCEPTANCE: docs/forward_planning/CR090_live_data_feed_paywall/CR090_live_data_feed_paywall.md
DEPENDS-ON: CR090-ROOM (`lane/CR090-ROOM.coder.room` @ `e06ed4b`) is **IN_AUDIT with track U, not yet on `main`**. You do NOT need it merged — this lane touches **zero backend files**. Branch from `main` @ `998c854` or later. See "If CR090-ROOM's audit moves the shape" below.
HOT-FILES: `mobile/lib/services/api/api_client.dart`, `mobile/lib/state/room_providers.dart`, `mobile/lib/screens/room/room_screen.dart`, `mobile/lib/l10n/app_en.arb` — **currently free.** CR100 rewrote `portfolio_screen.dart` / `ticker_detail_screen.dart` and `sim.dart`, none of which you touch.

## Why this lane exists

CR090-BE shipped the surcharge contract (`847d09c`). CR090-ROOM makes the Room actually **charge** it
and emit the disclosure. Neither one puts a single word in front of a user.

The CR's first acceptance criterion is:

> A Floor Pass user with insufficient credits triggering a live-data News/Social Analyst turn sees an
> explicit "this needs credits / upgrade" message — **never a silent synthetic substitution presented
> as business-as-usual.**

**Only this lane can satisfy that.** Verified this session by reading the shipped client, not by
assuming:

- `mobile/lib/services/api/api_client.dart:655` — `switch (eventType)` over the seven known Room event
  kinds, **no `default:`**. An unknown kind falls through silently; `jsonDecode` is never even reached.
- `mobile/lib/state/room_providers.dart:111` — `switch (ev['kind'])`, **also no `default:`**.

Two stacked silent-drop switches. That answers CR090-ROOM's open FLAG 2 — the backend **cannot** crash
the shipped client by emitting `live_data_notice` — and it establishes the thing that matters more:

> **Today, CR090-ROOM shipped alone would debit a surcharge that no user is ever told about.**

The disclosure has exactly one delivery channel, the transient SSE event, and it is **not persisted**:
`RoomRun` (`backend/app/schemas/room.py:44-68`) and `RoomRunRow` (`backend/app/db/models.py:383-410`)
carry `credit_cost` but **no live-data field at all**, so reopening a past run cannot show it either.
Charge the user more, tell them nothing, anywhere, ever. That is the DEF038 / DEF063 shipped-but-dark
class with a price tag attached.

**Promotion coupling (Architect ruling): CR090-ROOM must not reach Alpha ahead of this lane.** They
promote together. Do not treat this as ordinary backlog.

## The contract you build against

The backend emits exactly this frame (transcribed from `backend/app/api/room.py:225-232` on
`lane/CR090-ROOM.coder.room` @ `e06ed4b` — **read it there yourself, do not trust this paste**):

```
event: live_data_notice
data: {"news": "withheld_paid", "social": "unavailable", "surcharge_charged": 0}
```

- `news`, `social` — each independently one of `"live"` / `"withheld_paid"` / `"unavailable"`
  (`LiveDataState` values, lowercase, via `.value`).
- `surcharge_charged` — `int`, the surcharge **actually debited** for this run
  (`max(0, credit_cost - room_cost_for_plan(plan))`, `room_runner.py:1769`). `2` per LIVE feed.
- The event fires **once per run**, after `started`, before the analyst phases.

## Architect decisions — settled, do not re-open

**D1 — Extend BOTH switches. One is not enough.**
`api_client.dart` must yield a typed `{'kind': 'live_data_notice', ...}` map, and
`room_providers.dart` must handle that kind onto `RoomState`. Wiring only the first leaves the feature
exactly as dark as it is today, and every test you write against the parser would still pass. Add a
field to `RoomState` + `copyWith` (follow the existing `paywall` / `serverError` precedent, which are
the same shape of "one-shot signal that drives a card").

**D2 — Do NOT add a throwing `default:` to either switch.**
The silent tolerance is load-bearing forward-compatibility: a client that throws on an unknown kind
turns every future backend event into a crash for users who haven't updated. Keep the fall-through.
You **may** add a `default:` that *logs* the unknown kind on the room stream — that is the CR040
"degrade loudly" shape, and it is the one thing that would have surfaced this class earlier. Log only;
never throw, never surface to the user.

**D3 — Three states, three distinct renderings. `withheld_paid` must never look like `unavailable`.**
This is the entire point of the CR and it is the DEF059 inversion trap:

| state | means | render |
|---|---|---|
| `live` | real feed, user paid the surcharge | confirm it's live + what it cost |
| `withheld_paid` | the data **exists**, the user did not pay for it | explicit "needs credits" + upgrade CTA |
| `unavailable` | **nobody** has this data right now | say so plainly. **No CTA. No upsell.** |

Upselling on `unavailable` sells a user something we cannot deliver. Rendering `withheld_paid` as
"unavailable" hides a real, honest upsell and re-creates the silent substitution the CR exists to kill.
Getting these two backwards is a BLOCKER, not a MINOR.

**D4 — An absent notice is absence, not zero.**
If no `live_data_notice` arrives (older backend, dropped frame, CR090-ROOM not yet promoted), render
**nothing**. Do not render "surcharge: 0", do not render "live data unavailable", do not default the
states. This is CR100's rule restated: *nullable fields render as absent, never as zero.* A default
here would show every user of the current backend a disclosure about a charge that never happened.

**D5 — Render what was sent; never re-derive the price client-side.**
Display `surcharge_charged` as received. Do not compute it from a local credit table, do not multiply
a local constant by a feed count. Client and server disagreeing about what a user was charged is the
exact defect class CR100 just closed on the portfolio surface.

## Scope

Per the CR: *"surface the 'upgrade to unlock live data' message wherever the marker fires — copy only,
no new screens."*

- `mobile/lib/services/api/api_client.dart` — parse the event.
- `mobile/lib/state/room_providers.dart` — carry it on `RoomState`.
- `mobile/lib/screens/room/room_screen.dart` — render it. Inline in the Room console, AMI hex design
  language, consistent with the existing paywall / server-error cards.
- `mobile/lib/l10n/app_en.arb` — new keys with context comments.

**Out of scope:**

- **The 1-on-1 chat half.** The CR names it, but 1-on-1 has **no `spend()` call site at all** — filed
  as **DEF113**, blocked on Saiful's ship-now-or-Beta call. There is no marker to surface there yet.
  Do not build it; do not "prepare" for it.
- Any file under `backend/`. Zero. If you find yourself editing one, stop and flag.
- New screens, new nav, pricing-table changes.

## Copy rules

- **"AMI", never "the AI"** — user-visible copy names AMI (CLAUDE.md, behaviour-critical).
- Brand voice: analyst-to-analyst, numbers over adjectives, no marketing puffery. "Live news + social
  cost 4 credits this run" beats "Unlock powerful real-time insights!"
- EN only. **AR and MS take the gen-l10n English fallback — do not invent translations** (CR100
  precedent; translation is arranged externally and is not blocking). `app_ar.arb` / `app_ms.arb` hold
  452 keys against EN's 893, so the fallback path is already well-trodden here.

## Acceptance — how the auditor will check you

1. **A contract test that parses a real SSE frame transcribed from the backend source**, not a frame
   hand-written from your mental model. CR100's audit turned on exactly this: a fixture mirrored off
   the model reproduces the defect instead of catching it. Transcribe from
   `room.py:225-232` on `lane/CR090-ROOM.coder.room` and say in a comment where you got it.
2. **Each of the three states renders distinctly**, with `withheld_paid` vs `unavailable` pinned by
   its own test (D3). Assert the CTA is present on `withheld_paid` and **absent** on `unavailable`.
3. **No notice ⇒ nothing rendered** (D4). Test it.
4. **The unknown-kind tolerance still holds** — a garbage event kind must not throw. Pin the property
   this lane depends on so a later `default:` can't silently break it.
5. `flutter test` green — currently **88/88** on `main`; your additions on top.
6. `flutter analyze` **clean on files you touched.** It is not globally clean: 5 pre-existing issues
   remain, none in your files. Do not "fix" unrelated ones — that inflates the diff and the audit.
7. Scope: **zero files under `backend/`**.

Flutter is at `/opt/homebrew/bin/flutter`. Run from `mobile/`.

## If CR090-ROOM's audit moves the shape

It is at round 1 with track U and could come back `AWAITING_FIXES`. The payload keys are unlikely to
move (FLAG 1 is about *when* feeds are probed, not what the event carries), but if they do, rebase the
fixture and re-run — that is why acceptance #1 demands the fixture be transcribed from source rather
than invented. Do not block on the verdict; do not merge ahead of it either.

## Working rules — read these, three lane workers have died in 24h

- **Commit incrementally.** Two of the three deaths were budget caps, and CR090-ROOM's worker died
  with the **entire lane uncommitted** — zero commits on the branch, the only copy dirty files in a
  worktree. The Architect recovered it by hand. Commit every meaningful step so a cap costs you the
  last step, not the lane.
- **Never background a command and then emit your final message** (CR057 / failure_patterns P7). If
  you start a test run, wait for it in the foreground and report its real exit code.
- **Pathspec-commit only** — `git commit -m "…" -- <your files>`. Never `git add -A`, never `-am`,
  never bare. The checkout is shared.
- Report what you measured, not what you expect. If something is unverified, say so in the hand-off —
  the auditor is told to weight self-reports sceptically, and an honest gap costs you far less than a
  claim that doesn't reproduce.

## FLAGS to raise rather than decide

1. **Where the notice belongs in the Room console.** Inline above the transcript, a dismissible
   banner, or attached to the News/Social analyst rows specifically? The analyst-row placement is the
   most honest (it marks *which* analyst is degraded) but the most fiddly. Pick what fits the existing
   screen, and flag your choice for Saiful rather than treating it as settled.
2. **Whether `live` deserves any UI at all.** Disclosing "you paid 4 extra credits and got real data"
   is honest and matches the numbers-over-adjectives voice, but it also puts a cost reminder on the
   happy path every single run. Product call, not yours — build it, flag it, let Saiful cut it.

---

ASSIGNED: coder.mobile round 1
DISPATCH: ACCEPTED (round 1)

---

## coder.mobile hand-off

<!-- dispatch lane hand-off — coder.mobile, CR090-MOBILE, round 1 -->
# CR090-MOBILE — hand-off

STATUS: READY_FOR_AUDIT (round 1)
BRANCH: lane/CR090-MOBILE.coder.mobile (off main @ 998c854, 4 commits on top)

## What I built

1. **`api_client.dart`** — extracted the SSE-event switch out of `streamRoom`'s
   loop into a new top-level `@visibleForTesting Map<String,dynamic>? parseRoomSseEvent(String eventType, String data)`
   function (behavior-preserving refactor, separate commit). Added a
   `live_data_notice` case yielding `{'kind','news','social','surcharge_charged'}`,
   and a `default:` that `debugPrint`s the unknown kind and returns `null` —
   never throws (D2). `streamRoom` now calls this function and only returns
   the generator on `done`/`error` kinds, same as before.
   - *Why the refactor*: acceptance #1 demands a contract test parsing a real
     transcribed frame. `ApiClient` builds its own `http.Client()` inline with
     no injection point, so the only way to unit-test the actual parsing logic
     (not just the post-parse map) was to pull it into a pure function.
2. **`room_providers.dart`** — new `RoomLiveDataNotice` (news/social/surchargeCharged),
   a `liveDataNotice` field on `RoomState` + `copyWith`, a `case 'live_data_notice'`
   in `RoomNotifier.start()`'s switch, and a `default:` that logs and never throws
   (D2, second switch per D1). `start()` resets to `const RoomState(streaming: true)`
   on every convene, so the notice is one-shot per run, same as `paywall`.
3. **`room_screen.dart`** — new `_LiveDataNoticeCard`, mounted inline in the
   console alongside the paywall/server-error cards (only when
   `state.liveDataNotice != null` — D4). Three distinct renderings (D3):
   `live` → confirmation line + surcharge (rendered exactly as received, D5,
   no CTA); `withheld_paid` → "needs credits" line + an amber upgrade CTA
   (`showUpgradeSheet`, the existing Settings/402-wall entry point, reusing
   `mandateNotifierProvider.creditsResetAt` for the reset-date label — no new
   screen); `unavailable` → plain statement, no CTA, no upsell. When news and
   social disagree (e.g. one withheld, one unavailable) the card shows both
   lines and the CTA fires if *either* is `withheld_paid`.
4. **`app_en.arb`** — 6 new keys (`roomLiveDataNoticeTitle`,
   `roomLiveDataFeedLive/Withheld/Unavailable`, `roomLiveDataSurchargeCharged`,
   `roomLiveDataUpgradeCta`), each with a context comment naming the D-rule it
   serves. Ran `flutter gen-l10n` — AR/MS report 20 untranslated messages each
   (expected fallback-to-EN, CR100 precedent, not invented).

## What I measured (not expected)

- `flutter analyze` on all 4 touched source files + both new test files:
  **0 issues**, run individually right after each edit.
- `flutter test` (full suite, from `mobile/`): **97/97 green** — the pre-existing
  88 plus my 9 new tests (5 contract tests in
  `test/services/api_client_room_stream_test.dart`, 4 widget-render tests in
  `test/widgets/room_live_data_notice_test.dart`). Ran in the foreground,
  watched exit to completion, not backgrounded.
- Contract fixture in the test file is transcribed from
  `backend/app/api/room.py:225-232` and `backend/app/services/room_runner.py:1769-1777`
  on `lane/CR090-ROOM.coder.room` @ `e06ed4b` — read directly from that branch/commit,
  not from this lane's own model, and the test file cites both paths + the commit.
- `git diff --stat` confirms **zero files under `backend/`** touched this lane.
- The unknown-kind-doesn't-throw property (acceptance #4) is pinned for
  `parseRoomSseEvent` (api_client.dart) with an explicit `returnsNormally` test.

## What I did NOT verify

- **The `room_providers.dart` switch's `default:` branch has no direct test.**
  I verified by inspection that it mirrors the api_client one (log, return,
  no computation that could throw), and the widget test's "no notice" case
  exercises `RoomState()` with no `liveDataNotice` at all, but I did not wire
  a fake `ApiClient`/`streamRoom` stream through `RoomNotifier.start()` to
  prove an in-band garbage `'kind'` value is dropped end-to-end at that layer.
  `RoomNotifier.start()` also awaits `DeviceUser.getOrCreate()` first, which
  looked like it could pull in plugin-channel mocking I didn't want to risk
  getting wrong under this lane's file-scope limits — flagging instead of
  guessing.
- Did not test on a real device or simulator — no `flutter run`, this was
  `flutter test` + `flutter analyze` only. Static/widget-test verification
  only, not an eyeballed screen.
- Did not verify AR/MS fallback rendering visually (relying on `gen-l10n`'s
  untranslated-message report + CR100 precedent that this path is well-trodden).
- Have not rebased against CR090-ROOM's audit outcome — it was still IN_AUDIT
  with track U at branch time; the fixture is transcribed from its current
  commit (`e06ed4b`) per the assign's instruction, not from a merged `main`.

## FLAGS (raising per the assign, not deciding)

1. **Notice placement.** I put `_LiveDataNoticeCard` inline in the console,
   stacked with `paywall`/`serverError` above the transcript — cheapest fit
   with the existing screen, but it's a fixed card, not attached to the
   individual News/Social analyst rows. The row-level placement the assign
   flags as "most honest" would need each `_AgentLine` to know its own
   feed's live-data state, which the current one-shot `RoomLiveDataNotice`
   doesn't carry per-agent. Saiful's call.
2. **Whether `live` deserves any UI.** Built it (confirmation line + the
   surcharge, muted color, no CTA) per D3's table, but it puts a cost line on
   the happy path every run. Easy to cut — delete the `if (_anyLive)` block
   and the `roomLiveDataSurchargeCharged` key becomes unused.

## Scope confirmation

Touched: `mobile/lib/services/api/api_client.dart`,
`mobile/lib/state/room_providers.dart`, `mobile/lib/screens/room/room_screen.dart`,
`mobile/lib/l10n/app_en.arb`, generated `mobile/lib/generated/l10n/*.dart`,
2 new test files under `mobile/test/`. Zero files under `backend/`.

---

## architect bridge

<!--
CR090-MOBILE.architect.md — architect/coder submission lane (track R owns the audit lane).
State derives from round numbers here vs CR090-MOBILE.auditor.md (see PROTOCOL.md).
Built by the coder.mobile lane agent; Architect verified before submitting.
-->

# CR090-MOBILE — audit lane (coder.mobile submission)

SUBMITTED: round 1

**Item:** CR090-MOBILE — render the live-data disclosure in the Room console. This is the half that
makes CR090's **first acceptance criterion** true: *"a Floor Pass user with insufficient credits …
sees an explicit 'this needs credits / upgrade' message — never a silent synthetic substitution."*

Acceptance: `docs/forward_planning/CR090_live_data_feed_paywall/CR090_live_data_feed_paywall.md`
Assign (carries Architect decisions **D1–D5** — audit against those, not against what the code
happens to do): `orchestration/dispatch/lanes/CR090-MOBILE.assign.md`
Lane hand-off: `orchestration/dispatch/lanes/CR090-MOBILE.coder.mobile.md`

**Code branch:** `lane/CR090-MOBILE.coder.mobile` @ **`299a6f8`** (off `main` @ `998c854`, 4 commits).
Scope **11 files, +645/−40, zero under `backend/`**.

**GATE: spawned** — Architect-spawned audit. Not a money lane (it debits nothing), but it is the
honesty half of a money feature and the DEF059 inversion class lives in D3.

## Why this lane matters more than "render a banner"

Verified this session by reading the shipped client: `api_client.dart:655` and
`room_providers.dart:111` were **both** `switch` statements with no `default:`, so the backend's
`live_data_notice` was dropped twice over. The disclosure is also **not persisted** — `RoomRun`
(`backend/app/schemas/room.py:44-68`) and `RoomRunRow` (`backend/app/db/models.py:383-410`) carry
`credit_cost` but no live-data field. Without this lane, CR090-ROOM charges a surcharge that no user
is ever told about, anywhere, ever. **Architect ruling: CR090-ROOM does not reach Alpha ahead of this
lane.**

## Audit this hardest — a refactor of shipped, previously-untested streaming code

The coder extracted the SSE-event switch out of `streamRoom`'s loop into a new top-level
`parseRoomSseEvent(String eventType, String data)` and had `streamRoom` call it. It states the reason
plainly: `ApiClient` builds its own `http.Client()` inline with no injection point, so the parsing
logic was **not unit-testable before** — which means the pre-existing 88 tests plausibly **did not
cover the code this refactor restructured.** A green 97/97 therefore does **not** by itself prove the
refactor was behaviour-preserving.

Please go at this directly rather than reading the diff for plausibility:

1. **`agent_token` unescaping.** The original did
   `.replaceAll(r'\n', '\n').replaceAll(r'\\', r'\')` — order-dependent. Confirm it survived
   byte-for-byte and in the same order. Getting this wrong corrupts every analyst's streamed text.
2. **`done` and `error` terminate the stream; the others don't.** In the original these were `return`
   inside the generator, not `break`. The hand-off says `streamRoom` "only returns the generator on
   `done`/`error` kinds." Confirm a `done` still ends the stream and that no other kind now does —
   an early return would truncate a Room run; a missing one would hang it.
3. **Multi-line `data:` joining** (`dataLines.join('\n')`) and the `eventType == null` skip.
4. **`verdict`** still constructs `RoomVerdict.fromJson` and the malformed-event `try/catch` still
   swallows exactly what it did before.

Mutation is the right tool here: break each of the above in turn and confirm a test goes red. If a
mutation stays green, that's a real coverage gap in the *shipped* path, and worth saying so.

## Then the D-rules

- **D3 (BLOCKER class if inverted)** — `withheld_paid` (data exists, user didn't pay) must render an
  upgrade CTA; `unavailable` (nobody has the data) must render **no CTA and no upsell**. Upselling on
  `unavailable` sells what we cannot deliver. The coder also decided that when news and social
  **disagree**, both lines render and the CTA fires if *either* is `withheld_paid` — that decision is
  the coder's, not the assign's. Judge it.
- **D4** — no notice ⇒ **nothing rendered**, never a zero surcharge or a defaulted state. Confirm the
  one-shot reset (`start()` resets `RoomState`) actually holds across a second convene.
- **D5** — `surcharge_charged` rendered **as received**, never recomputed client-side.
- **D2** — the new `default:` branches must **log, never throw**. A throwing default would turn every
  future backend event into a crash on old clients. Confirm both, and confirm the tolerance property
  is pinned by a test.
- **Fixture provenance** — the contract fixture must be **transcribed from the backend source**
  (`room.py:225-232`, `room_runner.py:1769-1777` on `lane/CR090-ROOM.coder.room` @ `e06ed4b`), not
  written from the model. A model-mirrored fixture reproduces the defect instead of catching it; this
  is exactly what CR100's audit turned on. The coder says it cites both paths + the commit — check
  the literals actually match the backend.

## Reproduce (Architect measured these, foreground, on the lane branch)

```bash
cd mobile && /opt/homebrew/bin/flutter test          # 97/97, exit 0
/opt/homebrew/bin/flutter analyze                    # exit 1 — see below
git diff --stat main...lane/CR090-MOBILE.coder.mobile
```

**`flutter analyze` exits 1, and that is expected:** exactly **5 pre-existing** issues remain
(`lib/main.dart:69` ×2 deprecated `copyWith`, `lib/screens/floor/floor_screen.dart:73,313`
`use_build_context_synchronously`, `test/widgets/sign_in_email_disclosure_test.dart:27`
`use_super_parameters`). **None is in a CR090-MOBILE file** — the coder's "clean on touched" claim
reproduces. It is clean-on-touched, not globally clean; do not read the exit code alone as a failure.

## Claims NOT verified by the Architect — do not treat as checked

- **No end-to-end run.** Nothing exercised a real SSE stream from a real backend; the backend half
  (CR090-ROOM) is itself still at audit and not merged. All 9 new tests are unit/widget-level.
- **No device or simulator render.** The three states were verified by widget test, not by eye. The
  card's placement and legibility in the live console is unconfirmed — and is FLAG 1.
- **The refactor's behaviour-preservation was NOT independently mutation-tested by the Architect.**
  That is the single most important thing above and it is yours.
- **The `room_providers.dart` `default:` branch has no direct test** — the coder disclosed this
  itself rather than hiding it, and gave its reason (would require faking `DeviceUser`/`ApiClient`
  plumbing). Judge whether that gap is acceptable; the sibling `parseRoomSseEvent` default *is*
  pinned with a `returnsNormally` test.
- **AR/MS** report 20 untranslated messages each — the intended gen-l10n English fallback (CR100
  precedent), not invented translations. Confirm nothing was invented.

## FLAGS — for Saiful, not audit findings

1. **Where the notice sits** in the Room console — the coder mounted it inline alongside the
   paywall/server-error cards. Attaching it to the specific News/Social analyst rows would be more
   honest about *which* analyst is degraded, but fiddlier. Product call.
2. **Whether `live` deserves any UI at all.** Confirming "you paid N extra credits and got real data"
   is honest and on-voice, but puts a cost reminder on the happy path every single run. Saiful may
   want it cut.

---

## auditor verdict

<!--
CR090-MOBILE.auditor.md — auditor verdict lane (track U owns this file).
State derives from round numbers here vs CR090-MOBILE.architect.md (see PROTOCOL.md).
-->

# CR090-MOBILE — audit verdict (auditor.mobile)

VERDICT: COMPLETE (round 1)

**Branch audited:** `lane/CR090-MOBILE.coder.mobile` @ `299a6f8` (off `main` @ `998c854`).
Audited in an isolated worktree; `main`'s working tree untouched. Reverted every mutation;
worktree confirmed clean at `299a6f8` before writing this.

---

## Bottom line

The refactor is **behaviour-preserving** and D1–D5 are **correctly implemented**. The two things
this audit was spun up to protect both hold under execution:

- **D3 inversion trap (the BLOCKER class):** correctly rendered AND mutation-proven. Inverting the
  CTA condition turns a widget test red.
- **Fixture provenance (the CR100 class):** the contract fixture is transcribed from the real backend
  source at `e06ed4b`, not model-mirrored. I diffed the literals against source; they match.

Findings are all **MINOR / informational** — chiefly the `agent_token` unescape test gap the Architect
flagged. None blocks promotion: the untested paths are **byte-identical to the already-shipped `main`
baseline**, so the refactor introduces no regression in them; it simply didn't add tests for
pre-existing untested code. Blocking a behaviour-preserving refactor for not back-filling tests on
shipped code it left unchanged would be scope creep beyond this CR's acceptance.

---

## Verified by EXECUTION (ran it)

- `cd mobile && flutter test` → **exit 0, 97/97 "All tests passed!"** (ran twice, foreground, watched
  to completion). Matches the Architect's measurement.
- `flutter analyze` → **exit 1**, exactly **5 issues, all pre-existing, none in a CR090-MOBILE file**:
  `lib/main.dart:69:22` + `:69:44` (deprecated `copyWith`), `lib/screens/floor/floor_screen.dart:73:7`
  + `:313:9` (`use_build_context_synchronously`), `test/widgets/sign_in_email_disclosure_test.dart:27:3`
  (`use_super_parameters`). I verified this list myself rather than taking it — it reproduces exactly.
  Clean-on-touched confirmed.
- **Scope:** `git diff --name-only main...299a6f8` → **11 files, ZERO under `backend/`.** Confirmed by
  execution (`grep -c '^backend/'` → 0).
- **Mutation testing** (each: mutate → run → observe red/green → `git checkout` revert):

  | # | Mutation | Location | Result | What it means |
  |---|---|---|---|---|
  | M1 | swap `agent_token` unescape order (`\\` before `\n`) | `parseRoomSseEvent` | **SURVIVED (green)** | `agent_token` path has NO test — real coverage gap (see F1) |
  | M2 | `done` no longer terminates the generator | `streamRoom` | **SURVIVED (green)** | generator-termination untested; `streamRoom` is not unit-testable (builds its own `http.Client`) — pre-existing gap (F2) |
  | M3 | invert D3 CTA so it fires on `unavailable` | `room_screen` | **CAUGHT (red, +3 −1)** | the BLOCKER inversion class is protected |
  | M4 | drop the `social` payload key (return `null`) | `parseRoomSseEvent` | **CAUGHT (red, +3 −2)** | the anti-CR100 contract property holds |
  | M5 | provider `default:` throws | `room_providers` | **SURVIVED (green)** | provider default untested (coder disclosed); defensively unreachable today (F3) |
  | M6 | parser `default:` throws | `parseRoomSseEvent` | **SURVIVED (green)** | throw is swallowed by the outer `try/catch`; no-throw still holds structurally (F4) |

## Verified by READING (source comparison / inspection, not by test)

- **Behaviour-preservation of the extracted switch.** Diffed every moved case body in
  `parseRoomSseEvent` (`299a6f8`) against the original inline switch in `streamRoom` on `main`
  (`git show main:.../api_client.dart`). `started` / `phase` / `agent_token` / `agent_done` /
  `verdict` / `done` / `error` case bodies are **byte-identical** (yield→return is the only shape
  change; equivalent). The `agent_token` unescape is `.replaceAll(r'\n','\n').replaceAll(r'\\',r'\')`
  in the same order — survived byte-for-byte. `dataLines.join('\n')` and `if (eventType == null)
  continue;` remain in `streamRoom` **unchanged from `main`**. The `done`/`error` termination is
  now `if (parsed['kind'] == 'done' || parsed['kind'] == 'error') return;` after the yield —
  behaviourally equivalent to the original in-switch `return`s: `done` and `error` both still end the
  stream, and no other kind does.
- **The only behavioural deltas vs `main`** are the two intended additions: the `live_data_notice`
  case and the logging `default:` (D2). Everything else is preserved.
- **Fixture provenance** (diffed literals against `e06ed4b`):
  - `backend/app/services/room_runner.py:1769-1777` builds `{"news": news_feed.state.value,
    "social": social_feed.state.value, "surcharge_charged": surcharge_charged}` — keys match the
    fixture exactly.
  - `backend/app/services/news_context.py:51` `class LiveDataState(Enum)`: `LIVE="live"`,
    `WITHHELD_PAID="withheld_paid"`, `UNAVAILABLE="unavailable"` — exact lowercase literals used in
    the fixture (`withheld_paid`, `unavailable`, `live`).
  - `backend/app/api/room.py:225-232` emits `event: live_data_notice\ndata: {json}\n\n` — matches the
    frame shape the parser consumes.
  - `credit_service.py:90` `LIVE_DATA_SURCHARGE = 2`; both-live → 4, none → 0 — the fixture's `4`
    (both live) and `0` (withheld/unavailable) are correct, and `surcharge_charged: 0` with
    `news: withheld_paid, social: unavailable` is internally consistent (neither is LIVE).
- **D4 one-shot reset:** `RoomNotifier.start()` does `state = const RoomState(streaming: true)`
  (room_providers.dart:129), which nulls `liveDataNotice` (its default). A second convene starts
  fresh — the notice cannot leak across runs. Absence renders nothing: the card is mounted only
  `if (state.liveDataNotice != null)` and defaults to `null`.
- **D5:** surcharge rendered as received — provider stores `ev['surcharge_charged'] as int` verbatim;
  screen passes `notice.surchargeCharged` straight to the l10n string. No client-side recompute.

---

## D-rule judgments

- **D1 — both switches extended.** ✓ `parseRoomSseEvent` yields the typed `live_data_notice` map;
  `room_providers` handles `case 'live_data_notice'` onto a new `RoomLiveDataNotice` on `RoomState`
  (+`copyWith`), following the `paywall`/`serverError` one-shot precedent.
- **D2 — defaults log, never throw.** ✓ Both defaults `debugPrint` and never throw. Parser default is
  additionally inside the swallowing `try/catch`. See F4 for the nuance.
- **D3 — three distinct renderings; `withheld_paid` ≠ `unavailable`.** ✓ `_stateLine` maps each state
  to distinct copy; CTA gated on `_anyWithheld` only. `withheld_paid` → "needs credits" + amber
  `UPGRADE FOR LIVE DATA` CTA; `unavailable` → plain "unavailable right now", **no CTA, no upsell**.
  Mutation-proven (M3).
- **D4 — absent notice ⇒ render nothing.** ✓ Verified above; widget test `const RoomState()` renders
  nothing.
- **D5 — render as received.** ✓ Verified above.

**Coder's own decision (disagreement case), judged:** when `news` and `social` disagree, both lines
render and the CTA fires if *either* is `withheld_paid` (`_anyWithheld = _newsWithheld ||
_socialWithheld`). **Sound and on-spec.** A `withheld_paid` feed is a genuine, honest upsell (the data
exists, the user didn't pay), so showing the CTA is correct; the `unavailable` feed still renders its
own plain "unavailable" line and is never upsold. This does not re-create the DEF059 inversion — the
CTA is never driven by an `unavailable` feed. Approved.

---

## Findings (all MINOR / informational — none blocking)

- **F1 (MINOR, recommend follow-up test) — `agent_token` unescaping is untested (M1 survived).**
  The Architect's #1-flagged corruption risk. The refactor's stated purpose was to make parsing
  unit-testable, and it succeeded — `parseRoomSseEvent` is now a pure function — but the single
  highest-risk case (order-dependent unescaping that touches every analyst's streamed text) got no
  test. It is byte-identical to the shipped `main` code, so **no regression is introduced**; the gap
  is that a *future* edit to that line wouldn't be caught. Now that the function is pure, one
  `expect(parseRoomSseEvent('agent_token', '{"text":"a\\\\nb"}')['text'], 'a\nb')`-style test would
  close it cheaply. Non-blocking; recommend as a small follow-up on this or a subsequent lane.
- **F2 (INFORMATIONAL) — `streamRoom` generator-termination / multi-line join / null-skip untested
  (M2 survived).** `streamRoom` builds its own `http.Client()` with no injection point, so it is not
  unit-testable without a DI refactor that is out of this lane's scope. These lines are unchanged from
  `main`. No action this lane.
- **F3 (INFORMATIONAL) — `room_providers` `default:` untested (M5 survived).** Disclosed by the coder.
  It is defensively **unreachable via the real stream today**: `parseRoomSseEvent` drops any unknown
  `eventType` to `null` (→ `continue`) *before* it could reach the provider switch, and every `kind`
  the parser can yield has a non-default provider case. Purely defensive; acceptable.
- **F4 (INFORMATIONAL, not a defect) — parser default's no-throw is enforced by the outer `try/catch`,
  not the branch itself (M6 survived).** The `returnsNormally` test pins the whole function's
  no-throw, not the default branch's log-don't-throw specifically. D2's actual requirement — the
  client never crashes on an unknown kind — is met structurally. No change needed.

## Claims I did NOT independently establish (consistent with the Architect's non-verified list)

- No end-to-end SSE run against a live backend (CR090-ROOM not merged; all new tests are
  unit/widget-level). Not required for this verdict.
- No device/simulator render — placement/legibility of the card in the live console is unconfirmed
  (Architect FLAG 1). Product/eyeball check, not an audit gate.
- AR/MS untranslated-message fallback confirmed by design (gen-l10n EN fallback, CR100 precedent) —
  I did not visually confirm rendering; nothing appears invented in `app_en.arb` (EN-only keys with
  context comments).

FLAGS 1 (card placement) and 2 (whether `live` deserves UI) are product calls for Saiful, not audit
findings — passing them through unchanged.
