<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR090-ROOM — assign

KIND: code
INSTANCE: coder.room
GATE: independent    <!-- D-5: money. This lane is the only thing that decides how many credits a user is actually debited. Same risk class as CR084 (RevenueCat) and CR047 (winzip), both of which took independent audit. -->
ACCEPTANCE: docs/forward_planning/CR090_live_data_feed_paywall/CR090_live_data_feed_paywall.md
DEPENDS-ON: none — CR090-BE integrated at `847d09c`; CR077-ROOM at `ea16a9d`; CR026-BE at `dbfc127`. All three are on `main` and their lanes are closed. Branch from `main` @ `25d07b4` or later.
HOT-FILES: `backend/app/services/room_runner.py`, `backend/app/services/room_prompts.py` — **currently free**, but both were rewritten twice in the last 24h (CR026 sector cap, CR077-ROOM analyst parallelism). Rebase before you hand off if anything lands under you, and re-run BOTH features' test files after any rebase — a keep-both merge resolution is exactly where one feature gets silently half-dropped.

## Why this lane exists

CR090-BE shipped a complete, tested surcharge contract on 2026-07-27 and **nothing consumes it**.
No user is charged for live data, and the "paid feature withheld" disclosure renders nowhere. That
is a shipped-but-dark feature — the exact class that cost this project DEF038 and DEF063, each dark
for months for want of one wiring line. Your lane closes it on the Room surface.

## The contract you build against (already on `main`, do not re-derive)

```python
from app.services.news_context import LiveDataState, live_data_state, resolve_news_feed, NewsFeed
from app.services.social_context import resolve_social_feed, SocialFeed
from app.services.credit_service import live_data_surcharge, LIVE_DATA_SURCHARGE, room_cost_for_plan, spend
from app.services.entitlements import effective_plan_for_user
```

- `LiveDataState` — `.LIVE` / `.WITHHELD_PAID` / `.UNAVAILABLE`. Only `LIVE` carries a payload.
- `resolve_news_feed(ticker, entitled=<bool>) -> NewsFeed` (`.state`, `.headlines`)
- `resolve_social_feed(ticker, entitled=<bool>) -> SocialFeed` (`.state`, `.sentiment`)
- `live_data_surcharge(n) == n * LIVE_DATA_SURCHARGE == n * 2`, where `n` = number of feeds
  whose `.state is LiveDataState.LIVE`.
- `live_data_state(available=..., entitled=...)` — the classifier, if you need to compose a state
  without a fetch.

## Architect decisions — these are settled, do not re-open them

**D1 — ONE atomic charge, before the run. Never a second mid-run `spend()`.**
`spend()` has exactly one call site in the whole backend: `room_runner.py:1464`, inside `convene()`,
past both dedup tiers, immediately before any work is committed to. The surcharge goes **into that
same call**: `spend(user_id, base + surcharge, reason=...)` instead of today's
`spend(user_id, None, reason=...)` (`amount=None` means "look up the plan's Room price"; you now
pass an explicit int, which is what `spend`'s own docstring anticipates). A second `spend()` later in
the run could raise `InsufficientCredits` **after** the user already paid the base and the Room is
half-streamed — a money bug and a horrible UX. Not negotiable.

**D2 — Entitlement is the credit balance, NOT a plan tier.** The CR's decision #2 is explicit:
*"Meter through credits, not a flat tier lock."* So there is no plan check. The sequence in
`convene()`, in this order:

1. Probe availability for both feeds (cache-first).
2. `n_available` = how many feeds have real data right now.
3. `cost_full = room_cost_for_plan(effective_plan) + live_data_surcharge(n_available)`.
4. If balance ≥ `cost_full` → **entitled = True**. Charge `cost_full`. Both available feeds
   resolve `LIVE`.
5. Else if balance ≥ base → **entitled = False**. Charge the base **only**. Available feeds resolve
   `WITHHELD_PAID`; the loud disclosure fires. The run proceeds on the honest synthetic fallback.
6. Else → the existing `InsufficientCredits` → 402 path, unchanged.

**All-or-nothing on the live bundle** (you buy both live feeds or neither). Partial "buy as many as
you can afford, cheapest first" was considered and rejected: it makes the price depend on an
arbitrary tie-break the user can't predict. If Saiful later wants partial, it is a one-branch change
at step 4 — say so in your hand-off, don't build it.

**D3 — The user-facing disclosure MUST be structural, not a prompt instruction.** This is the
load-bearing rule of the lane. `room_prompts.py::_format_profile` already carries a data-source
disclosure header, and its own docstring records why: the synthetic macro/Fed fields were *removed at
source* rather than kept behind "a disclosure the agents ignored 70% of the time" (CR038). If you
implement "render the loud paid-feature-withheld disclosure" as a line in an agent's prompt, it will
be dropped ~70% of the time and the user will silently believe the synthetic block is just how the
agent behaves — which is **precisely** the DEF059 shape (LLM path produced a confident wrong answer
because nothing structural stopped it).

So:
- **Emit it from the runner**, with the model completely out of the loop. `RoomEvent`
  (`room_runner.py:961`) currently has kinds `started|phase|agent_token|agent_done|verdict|error`.
  Add what you need (a new kind, or fields on `started` — your call, justify it) carrying at minimum:
  each feed's `LiveDataState`, and the surcharge actually charged. The client renders this;
  CR090-MOBILE consumes it next.
- **Also** add the third state to `_format_profile`'s header so the agent doesn't fabricate around
  the gap — but that is the anti-fabrication measure, **not** the user guarantee.
- Your test must prove the notice reaches the event stream **with the LLM stubbed out entirely**.
  If the test can only observe the disclosure through generated text, you built the wrong thing.

**D4 — The charge must match what was rendered.** If you charge for 2 LIVE feeds, the profile that
reaches the agents must actually carry 2 LIVE feeds. Thread the feeds you resolved in `convene()`
down into `run()`; do **not** re-fetch inside the profile build (`room_runner.py:383`,
`fetch_live_news`) — a second fetch can return a different answer than the one you priced, and then
you have billed for data you did not deliver. Write the test that pins this: charged `n_live` ==
number of feeds marked live in the profile handed to the agents. This is the single most valuable
test in the lane.

**D5 — `WITHHELD_PAID` and `UNAVAILABLE` are charged NOTHING**, and `UNAVAILABLE` keeps its existing
honest synthetic-illustrative fallback (CR023/CR024) byte-for-byte. Only `LIVE` costs credits.

## Scope

- `backend/app/services/room_runner.py` — feed resolution hoisted into `convene()` ahead of `spend()`;
  the atomic charge; the structural notice event; the resolved feeds threaded into `run()`/the
  profile build.
- `backend/app/services/room_prompts.py` — third disclosure state in `_format_profile`.
- `backend/app/api/room.py` — only if the new event needs SSE translation.
- `docs/initial_specs/06_monetization/paywall_axes.md` — add **axis #25** recording this decision
  (an explicit acceptance item in the CR).
- Tests. New file `backend/tests/unit/test_cr090_room_live_data_surcharge.py`.

## Out of scope

- **1-on-1 (`agent_runner.py`) — carved out deliberately.** The CR names Room *and* 1-on-1, but
  1-on-1 has no `spend()` call anywhere in the backend today, so there is no charging spine to attach
  a surcharge to. Architect is filing that separately. Do not build 1-on-1 billing here.
- Changing `ROOM_COST_BASIC`/`ROOM_COST_PREMIUM` or the `LIVE_DATA_SURCHARGE` value.
- Mobile rendering (CR090-MOBILE).
- Providers, LunarCrush, free-tier sanctity items.

## FLAGS — raise these in your hand-off, do not silently resolve them

1. **Acceptance criterion 2 is reinterpreted by D2.** The CR says *"Adanos's 250-call/month quota is
   protected by the gate — free-tier traffic can no longer exhaust it unpriced."* Under a
   credits-only meter with no tier lock, free-tier traffic **can** still reach Adanos — it is now
   *priced* (credits), not *blocked*. And step 1 above probes availability before pricing, which is
   inherent: you cannot distinguish `WITHHELD_PAID` from `UNAVAILABLE` without knowing whether data
   exists. State plainly in your hand-off which reading you built and what the residual quota
   exposure is, with the 24h-cache behaviour measured, not assumed. Do not quietly claim the
   criterion is met.
2. Whether adding a new `RoomEvent` kind breaks the **existing** Flutter SSE parser. Check
   `mobile/`'s room stream handling for unknown-kind tolerance and report what you find — a backend
   that emits an event the shipped client crashes on is worse than dark.

## Acceptance (yours, on top of the CR doc's)

- Full unit suite from the **repo root**, absolute venv path:
  `./backend/.venv/bin/python -m pytest backend/tests/unit/ -q` — green, ≥ 1320, exit 0 reported.
- Both prior features re-verified intact on your tip: `test_cr026_sector_allocation.py` and
  `test_cr077_phase_parallelism.py`.
- A user with exactly `base` credits gets the Room, gets `WITHHELD_PAID`, gets the notice event, and
  is debited exactly `base` — asserted on the balance, not on a mock.
- A user with `base + 4` gets both feeds LIVE and is debited exactly `base + 4`.
- Charged-vs-rendered consistency test (D4).
- Notice-reaches-the-stream test with the LLM stubbed (D3).

ASSIGNED: coder.room round 1
DISPATCH: OPEN
