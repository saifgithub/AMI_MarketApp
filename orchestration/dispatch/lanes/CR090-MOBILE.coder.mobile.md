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
