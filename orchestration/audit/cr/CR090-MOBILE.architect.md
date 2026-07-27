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
