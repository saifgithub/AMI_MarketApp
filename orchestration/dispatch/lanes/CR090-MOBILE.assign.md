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
DISPATCH: OPEN
