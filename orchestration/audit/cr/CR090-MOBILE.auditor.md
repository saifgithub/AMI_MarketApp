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
