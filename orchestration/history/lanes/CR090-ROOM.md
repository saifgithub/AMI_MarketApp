# CR090-ROOM — closed lane archive (AT:R65, 2026-07-27)

Audited **COMPLETE round 1, ZERO findings** by track U (independent). Merged to `main`; full suite **1332 passed** re-verified post-merge from the repo root. Worktree + branch reaped.

**PROMOTION HOLD:** this lane's charging code must NOT reach Alpha until a mobile build carrying CR090-MOBILE is in testers' hands. Affirmed independently by the auditor, not just the Architect.

---

## assign

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
DISPATCH: ACCEPTED (round 1)

---

## coder.room hand-off

<!-- coder.room lane file — CR090-ROOM. Shared coordination state, committed to the shared branch (main). -->
# CR090-ROOM — coder.room lane

STATUS: READY_FOR_AUDIT (round 1)

## ⚠️ Provenance — read this before auditing

**The `coder.room` worker died on its $10 premium budget cap with everything UNCOMMITTED.** It
ignored the assign's explicit commit-incrementally instruction, so `lane/CR090-ROOM.coder.room`
carried zero commits and the only copy of the work was dirty files in
`.claude/worktrees/coder.room-CR090-ROOM/`.

The **Architect** recovered it rather than discarding a substantially-complete money lane, and
committed it at `e06ed4b`. Treat authorship accordingly: the design and the great majority of the
code are the worker's; the Architect verified it, made **one** production fix (below), and wrote
this hand-off. `GATE: independent` is unchanged and the external track-U auditor is still the gate —
that independence is intact, which is why recovery was judged acceptable over a $10 relaunch.

**Architect's one production change**, on top of the worker's tree:

`_profile_for_ticker`'s social fallback branch resolved through
`resolve_social_feed(ticker, entitled=True)`, while the *news* branch beside it kept calling the raw
module-level `fetch_live_news`. That asymmetry moved the seam every existing caller and test patches
(`room_runner.fetch_live_sentiment`) into `social_context`, **silently voiding those patches** — it
turned `test_room_runner.py::test_profile_overlays_live_sentiment_when_enabled` red with
`KeyError: 'social_source'`. Restored symmetry with the news branch (raw fetcher + explicit
`SocialFeed` construction). Behaviourally identical; the seam is what changed. Worth an auditor's
eye precisely because "the test was stale" is the easy wrong conclusion here.

## What was built

Branch `lane/CR090-ROOM.coder.room` @ **`e06ed4b`**, based on `main` @ `6d45741`. Pushed to origin.
Scope **5 files, +658/−34**:

| File | What |
|---|---|
| `backend/app/services/room_runner.py` | +262 — feed resolution + pricing hoisted into `convene()` ahead of the single `spend()`; feeds threaded into `run()`/`_profile_for_ticker`; new `live_data_notice` `RoomEvent` kind; 3-state marker recorded on the profile |
| `backend/app/services/room_prompts.py` | +29 — third disclosure state in `_format_profile` |
| `backend/app/api/room.py` | +11 — SSE translation of the new event |
| `backend/tests/unit/test_cr090_room_live_data_surcharge.py` | +365, new — 12 tests |
| `docs/initial_specs/06_monetization/paywall_axes.md` | axis #25 (a CR acceptance item) |

### Against the assign's D1–D5

- **D1 — one atomic spend.** The surcharge folds into the single pre-existing `spend()` at the
  `convene()` charge point. There is still exactly one `spend()` in the whole run, so a second
  mid-run debit can never 402 after the base is paid and the Room is half-streamed.
- **D2 — entitlement is the balance, not a plan tier.** Probe both feeds → `n_available` →
  `entitled = n_available > 0 and balance >= base + surcharge`. All-or-nothing on the live bundle,
  as specified. **Detail the worker got right and worth preserving:** the non-entitled path keeps
  the byte-for-byte `spend(user_id, None, …)` call, which is what preserves the CR047 winzip
  soft-wall and the CR039 402 — both live inside `spend` keyed on `amount is None`. A naive
  `spend(user_id, base, …)` would have silently deleted the winzip funnel.
- **D3 — structural disclosure.** `live_data_notice` `RoomEvent` carrying
  `{news, social, surcharge_charged}`, emitted by the runner with the model out of the loop. The
  `_format_profile` third state is present too and is correctly *commented in the source* as the
  anti-fabrication measure only, not the user guarantee.
- **D4 — charged == rendered.** Feeds resolved once in `convene()` and threaded down; the profile
  build does not re-fetch on the production path. Pinned by
  `test_charged_surcharge_equals_rendered_live_feeds`, parametrized 4 ways.
- **D5 — `WITHHELD_PAID` / `UNAVAILABLE` charge nothing** and keep the honest synthetic fallback.

### Tests (12, all Architect-run in the foreground)

```
test_entitled_user_buys_both_live_feeds_debited_base_plus_surcharge
test_user_with_exactly_base_gets_withheld_paid_and_pays_only_base
test_entitlement_is_balance_not_plan_tier
test_charged_surcharge_equals_rendered_live_feeds  [4 params]
test_notice_reaches_the_stream_with_the_llm_stubbed
test_format_profile_renders_withheld_paid_anti_fabrication_header
test_no_live_data_available_charges_base_only
test_failed_run_refunds_the_full_charge_including_surcharge
test_genuinely_broke_user_still_hits_the_402
```

## Evidence — what the Architect verified personally

- **Full backend suite from the repo root, foreground: `1332 passed, exit 0`**
  (`./backend/.venv/bin/python -m pytest backend/tests/unit/ -q`, 169s). Before the seam fix it was
  `1 failed, 1331 passed` — that regression is closed, not suppressed.
- **Mutation test on D3:** deleted the `live_data_notice` emission entirely → **9 of 12 tests went
  red**, including both `test_notice_reaches_the_stream_with_the_llm_stubbed` and all four D4
  params. Restored → 12/12 green. The notice is load-bearing, not decorative. *Caveat, stated
  rather than glossed:* the blast radius is broad because the notice is the observation channel for
  most of the file, so this proves the event is real but does **not** prove each test is
  independently discriminating. A finer per-test mutation pass is the auditor's to run.
- Scope + base SHA reproduced by `git diff --stat main...HEAD` and `git merge-base`.

## Claims explicitly NOT verified

- **No live measurement.** Nothing was exercised against real Alpha Vantage or Adanos, or against
  a real credit balance in Postgres. All 12 tests are unit-level with the providers stubbed.
- **No end-to-end SSE check.** `room.py`'s translation of the new event is covered by a unit
  assertion, not by a real client consuming a real stream.
- **The refund path** (`test_failed_run_refunds_the_full_charge_including_surcharge`) was not
  mutation-tested by the Architect.
- **D4's no-re-fetch guarantee** was read in the source and is pinned by a test, but the Architect
  did not mutate the threading to confirm the test catches a re-fetch.

## FLAGS from the assign — answered

1. **Acceptance criterion 2 (the Adanos 250-call/month quota) is reinterpreted, not met as
   written.** The CR text says free-tier traffic "can no longer exhaust it unpriced". Under D2's
   credits-only meter there is no tier lock, so free-tier traffic still *reaches* Adanos — it is now
   **priced**, not blocked. Worse for the quota specifically: pricing requires knowing availability,
   so `convene()` probes **both feeds before deciding entitlement**, meaning a non-entitled turn
   still costs a probe. The 24h cache bounds this to ~1 call per ticker per day, but that bound was
   **read from CR024's design, not measured here**. If protecting the 250-call budget matters more
   than the loud disclosure, the fix is to suppress the social probe for a user whose balance can't
   cover the surcharge and compose `WITHHELD_PAID` via `live_data_state(available=…, entitled=False)`
   — at the cost of no longer being able to tell `WITHHELD_PAID` from `UNAVAILABLE`. **This is a
   product call for Saiful, not an auditor finding.**
2. **New `RoomEvent` kind vs the shipped Flutter parser.** The worker recorded in a source comment
   that the shipped parser tolerates unknown SSE event kinds. **The Architect did not independently
   confirm this**, and it matters — a backend emitting an event the shipped client crashes on is
   worse than dark. Auditor should verify it against `mobile/`'s room stream handling directly.

## BLOCKED / follow-on

- **CR090-MOBILE** is now unblocked: the event shape is `event: live_data_notice`, payload
  `{"news": <state>, "social": <state>, "surcharge_charged": <int>}` with state ∈
  `live | withheld_paid | unavailable`.
- **1-on-1 remains uncovered** and is out of scope by design — it has no `spend()` call site at all.
  Filed as **DEF113**; CR090's 1-on-1 half cannot be built until that lands.

Hand-off: `orchestration/audit/cr/CR090-ROOM.architect.md`, `SUBMITTED: round 1`.

---

## architect bridge

<!--
CR090-ROOM.architect.md — architect/coder submission lane (track R owns the audit lane).
State derives from round numbers here vs CR090-ROOM.auditor.md (see PROTOCOL.md).
Built by the coder.room lane agent in .claude/worktrees/coder.room-CR090-ROOM/;
recovered and committed by the Architect after that worker died on its budget cap.
-->

# CR090-ROOM — audit lane (coder.room submission, Architect-recovered)

SUBMITTED: round 1

**Item:** CR090-ROOM — wire the live-data credit surcharge and the 3-state "paid feature withheld"
disclosure into the Room. CR090-BE integrated its surcharge contract at `847d09c` on 2026-07-27 and
**nothing consumed it**: no user was charged and no disclosure rendered. This lane closes that
shipped-but-dark gap on the Room surface.

Acceptance: `docs/forward_planning/CR090_live_data_feed_paywall/CR090_live_data_feed_paywall.md`
Assign: `orchestration/dispatch/lanes/CR090-ROOM.assign.md` (carries Architect decisions **D1–D5**;
audit against those, not against what the code happens to do)
Lane hand-off: `orchestration/dispatch/lanes/CR090-ROOM.coder.room.md`

**Code branch:** `lane/CR090-ROOM.coder.room` @ **`e06ed4b`** (based on `main` @ `6d45741`), pushed
to origin. Scope **5 files, +658/−34**.

**GATE: independent** — D-5, money. This lane is the only thing deciding how many credits a user is
actually debited. Same risk class as CR084 (RevenueCat) and CR047 (winzip).

## ⚠️ Provenance you need before you start

The `coder.room` worker **exceeded its $10 budget cap with the entire lane uncommitted** — it
ignored the commit-incrementally instruction, so the branch carried zero commits and the only copy
was dirty files in the worktree. Third worker death in 24h, second on a budget cap.

The **Architect recovered and committed it** rather than discard a substantially-complete money
lane. Design and the great majority of the code are the worker's. The Architect verified it, made
**one** production change, and wrote the hand-off. Your independence is unaffected — that is exactly
why recovery was preferred to a $10 relaunch — but **you should weight the usual "the coder
self-reported this" scepticism onto the Architect instead of onto an absent worker.**

## Please independently re-verify (commands that reproduce)

1. **The full suite, from the repo root** — the Architect measured `1332 passed, exit 0`:
   ```bash
   ./backend/.venv/bin/python -m pytest backend/tests/unit/ -q
   ```
   Before the Architect's fix this was `1 failed, 1331 passed`. Confirm the regression is **closed,
   not suppressed**.

2. **The Architect's one production change — scrutinise this hardest.**
   `_profile_for_ticker`'s social fallback branch had gone through
   `resolve_social_feed(ticker, entitled=True)` while the news branch beside it kept the raw
   module-level `fetch_live_news`. That asymmetry moved the seam every existing caller and test
   patches (`room_runner.fetch_live_sentiment`) into `social_context`, silently voiding those
   patches, and turned `test_room_runner.py::test_profile_overlays_live_sentiment_when_enabled`
   red with `KeyError: 'social_source'`. The Architect restored symmetry with the news branch.
   **"The test was just stale" is the easy wrong conclusion here** — decide for yourself whether
   the fix restores the original behaviour or papers over a real change, and whether the fallback
   branch should be granting `entitled=True` live data outside the charging path at all.

3. **D1 — exactly one `spend()` in the whole run.**
   ```bash
   grep -rn "spend(" backend/app --include="*.py" | grep -v "def spend"
   ```
   Must remain a single call site. A second debit anywhere is a BLOCKER: it can raise
   `InsufficientCredits` after the base is paid and the Room is half-streamed.

4. **D2 — the winzip path.** The non-entitled branch deliberately keeps the byte-for-byte
   `spend(user_id, None, …)` call, because the CR047 winzip soft-wall and the CR039 402 both live
   inside `spend` keyed on `amount is None`. Confirm a naive refactor has not deleted the funnel —
   `test_genuinely_broke_user_still_hits_the_402` should pin it; mutate to check.

5. **D3 — the disclosure is structural, not a prompt string.** The Architect mutation-tested this by
   deleting the `live_data_notice` emission: **9 of 12 tests went red**, including
   `test_notice_reaches_the_stream_with_the_llm_stubbed` and all four D4 params; restored → 12/12.
   **Stated caveat:** that blast radius is broad because the notice is the observation channel for
   most of the file, so it proves the event is load-bearing but **not** that each test is
   independently discriminating. **A finer per-test mutation pass is yours to run.**

6. **D4 — charged == rendered.** Feeds are resolved once in `convene()` and threaded down; the
   profile build must not re-fetch on the production path. **The Architect did NOT mutate the
   threading to confirm the test catches a re-fetch** — please do. Charging for 2 LIVE feeds and
   rendering fewer is the money bug this lane most needs to not have.

7. **Scope + base:**
   ```bash
   git diff --stat main...lane/CR090-ROOM.coder.room
   git merge-base --is-ancestor 6d45741 lane/CR090-ROOM.coder.room
   ```

## Claims NOT verified by the Architect — do not treat as checked

- **No live measurement.** Nothing exercised against real Alpha Vantage or Adanos, or against a real
  credit balance in Postgres. All 12 tests are unit-level with providers stubbed.
- **No end-to-end SSE check** — `room.py`'s translation of the new event has a unit assertion, not a
  real client consuming a real stream.
- **The refund path** was not mutation-tested.
- **FLAG 2 is open:** the worker's source comment claims the shipped Flutter parser tolerates unknown
  SSE event kinds. **Nobody has confirmed that.** A backend emitting an event the shipped client
  crashes on is worse than dark — please verify against `mobile/`'s room stream handling directly.

## ADDENDUM (Architect, same round — FLAG 2 is now CLOSED, and it opens something bigger)

**FLAG 2 is answered — verified by reading the shipped client, not assumed.** The worker's source
comment was correct:

- `mobile/lib/services/api/api_client.dart:655` — `switch (eventType)` over the seven known Room event
  kinds, **no `default:`**. An unknown kind falls through silently and `jsonDecode` is never reached.
- `mobile/lib/state/room_providers.dart:111` — `switch (ev['kind'])`, **also no `default:`**.

So this lane **cannot crash the shipped client**. That claim is now checked; treat FLAG 2 as closed
and don't spend audit budget re-deriving it.

**What that fact actually means, which nobody had stated:**

> Shipped alone, this lane debits a surcharge that **no user is ever told about.**

The disclosure has exactly one delivery channel — the transient `live_data_notice` SSE event — and
both client switches drop it on the floor. It is also **not persisted**: `RoomRun`
(`backend/app/schemas/room.py:44-68`) and `RoomRunRow` (`backend/app/db/models.py:383-410`) carry
`credit_cost` but **no live-data field**, so reopening a past run can't surface it retroactively
either. There is no third channel — `_format_profile`'s third state is prompt-side and is correctly
documented in-source as anti-fabrication only, not a user guarantee.

Net: charge goes up, disclosure renders nowhere, nothing is logged. That is the CR's **first
acceptance criterion inverted** — "never a silent synthetic substitution presented as
business-as-usual" — with a price attached.

**This is not a finding against your lane's code.** D3 is implemented exactly as the assign specified;
the event is emitted, structurally, with the model out of the loop. It is a **promotion coupling**, and
the Architect ruling is recorded here so it can't be lost:

> **CR090-ROOM must not reach Alpha ahead of CR090-MOBILE. They promote together.**

`CR090-MOBILE` is laned as of this addendum
(`orchestration/dispatch/lanes/CR090-MOBILE.assign.md`, `coder.mobile`, `GATE: spawned`) and builds
against the frame at `room.py:225-232` on this branch. It touches zero backend files, so it does not
contend with you and does not need this lane merged first.

**Nothing above changes what you are auditing.** Verdict this lane on its own merits; the coupling is
the Architect's to enforce at promotion time.

## FLAG 1 — a product call, not an audit finding

Acceptance criterion 2 (*"Adanos's 250-call/month quota is protected by the gate — free-tier traffic
can no longer exhaust it unpriced"*) is **reinterpreted, not met as written**, and the lane says so
rather than quietly claiming it. Under D2's credits-only meter there is no tier lock, so free-tier
traffic still reaches Adanos — **priced**, not blocked. And pricing requires knowing availability, so
`convene()` probes both feeds *before* deciding entitlement: a non-entitled turn still costs a probe.
The 24h cache bounds this to roughly one call per ticker per day, but **that bound was read from
CR024's design, not measured**. Please don't fail the lane on this criterion — flag your view and let
Saiful decide; the alternative (suppress the probe for a user who can't afford the surcharge) costs
the ability to tell `WITHHELD_PAID` from `UNAVAILABLE`, which is the disclosure this CR exists for.

---

## auditor verdict

<!--
CR090-ROOM.auditor.md — auditor lane file (track U owns). State derives from
round numbers here vs CR090-ROOM.architect.md (see PROTOCOL.md).
-->

# CR090-ROOM — audit lane (auditor)

**Item:** wire CR090-BE's live-data credit surcharge and the 3-state "paid feature withheld"
disclosure into the Room. CR090-BE shipped the contract; nothing consumed it — no user was
charged, no disclosure rendered. This lane closes that shipped-but-dark gap.

**Gate:** independent — D-5, money. This lane decides how many credits a user is actually
debited on every Room run.

**Audited SHA:** `e06ed4b`, tip of `lane/CR090-ROOM.coder.room` (base `main` @ `6d45741`).
**Provenance:** the coder.room worker exceeded its budget cap with the lane entirely
uncommitted — the Architect recovered and committed it, making one production change of their
own. Weighted the usual coder-self-report scepticism onto the Architect's own claims instead,
per their explicit ask. Audited in an isolated worktree `.claude/worktrees/audit-CR090-ROOM/`,
own venv.

## Round 1

### Reproduced independently

| Check | Result |
|---|---|
| Scope | `git diff 6d45741 e06ed4b --stat` — 5 files, **+658/−34**, exact match. |
| Full suite | `.venv/bin/pytest tests/unit/ -q` — **1332 passed**, 5 warnings, exit 0 (168–194s across two runs). Matches the Architect's post-fix claim exactly; confirmed from a clean isolated worktree the pre-fix `1 failed, 1331 passed` regression is genuinely closed, not suppressed. |
| D1 | Grepped `app/` for `spend(` — two textual call sites in `room_runner.py`, on mutually exclusive `if entitled: / else:` branches. Only one executes per run. No other file calls `spend`. |
| Architect's one production change | Read `_profile_for_ticker`'s news/social fallback branches in full and traced the production call chain (`room.py::stream_room` → `start_run()` → `_resolve_and_charge_feeds()` → `_pump()` threads the SAME feed objects into `run(news_feed=, social_feed=, credit_cost=)` → `_profile_for_ticker` renders exactly what was billed). The restored-symmetry fallback (entitled=True) is reachable only by direct/test callers that bypass `start_run` entirely — confirmed by reading the call sites myself, not the comment. The fix is correct: legacy behaviour preserved on a genuinely production-unreachable branch, not a billing bypass. |

### Mutation-tested every gap the Architect explicitly left open, plus one more

1. **D2 — winzip/402 keying** (Architect: "mutate to check"). `spend(user_id, None, ...)` →
   `spend(user_id, 0, ...)` (explicit 0 defeats the `amount is None` key both CR047 winzip and
   CR039 402 branch on) → `test_genuinely_broke_user_still_hits_the_402` failed. Confirms the
   test pins the keying mechanism, not just the surface outcome.
2. **D3 — finer per-test mutation pass** (Architect's own probe was presence-only: deleting the
   whole notice caught 9/12 tests but didn't prove per-test discrimination). Hardcoded the
   notice's `news`/`social` fields to always report `"live"` regardless of actual state → 4
   tests failed on the WRONG VALUE — a content-correctness check, distinct from the
   presence-only mutation. Confirms individual tests check what the notice says, not just that
   one fired.
3. **D4 — the money bug itself** (Architect explicitly did not mutate this — "please do").
   Dropped `news_feed=`/`social_feed=` threading from `_pump()`'s call into `run()` → the
   WITHHELD_PAID test case failed with `'live' == 'withheld_paid'`: a non-entitled user charged
   base-only would have the disclosure falsely claim their feed was live. This is the exact
   money bug D4 exists to prevent, and it's genuinely caught.
4. **The refund path** (Architect: "was not mutation-tested"). Dropped
   `credit_cost=charged_total` from the same call → `test_failed_run_refunds_the_full_charge_including_surcharge`
   failed. The refund-on-failure amount genuinely depends on this threading.

All four reverted individually; suite re-confirmed clean before the next probe. Final full
suite re-confirmed **1332/1332 clean**.

### FLAG 2 — independently re-confirmed, not relayed

Read `mobile/lib/services/api/api_client.dart:655` and `mobile/lib/state/room_providers.dart:111`
myself: both `switch` statements match on plain `String` values (no Dart-enum exhaustiveness
requirement) and neither has a `default:` case in the file. An unrecognised `live_data_notice`
kind genuinely falls through silently — no crash, no effect. Matches the Architect's claim
exactly.

Also independently confirmed the "no third channel" claim: `RoomRun` (`app/schemas/room.py:44-68`)
and `RoomRunRow` (`app/db/models.py:383-410`) both carry `credit_cost` but no live-data field —
a reopened past run cannot surface the disclosure retroactively either.

**This affirms the Architect's promotion-coupling ruling on my own independent verification,
not their say-so: the disclosure has no delivery channel to a real user today. Not a defect in
this lane's code** — D3 is implemented exactly as specified, structurally, model out of the
loop — **but a promotion-sequencing constraint I'm recording alongside my verdict:
CR090-ROOM must not reach Alpha ahead of CR090-MOBILE.**

### FLAG 1 — product call, recorded not resolved

Confirmed the mechanics: under D2's credits-only meter, free-tier traffic still reaches Adanos
(priced, not blocked), and `convene()` probes both feeds before pricing, so a can't-afford turn
still costs one probe. The 24h cache bounds this to ~1 call/ticker/day (from CR024's design,
not independently re-measured against a live Adanos quota by either of us). Agree this is a
reasonable, disclosed tradeoff — suppressing the probe would break the
WITHHELD_PAID/UNAVAILABLE distinction the CR exists for. Recording for Saiful's call per the
Architect's own request, not treating as a code defect.

### Findings

None against the delivered code — zero BLOCKER/MAJOR/MINOR. One promotion-sequencing
constraint affirmed (CR090-ROOM must not ship ahead of CR090-MOBILE) and one product-policy
flag recorded for Saiful (Adanos quota criterion reinterpretation, FLAG 1).

### Verdict

**VERDICT: COMPLETE (round 1)** — scope and full suite reproduced exactly, every gap the
Architect explicitly left open (D2 keying, D3 content-discrimination, D4 the money bug itself,
the refund path) closed via independent mutation testing on production code, the Architect's
own production change traced and confirmed sound, and the promotion-blocking claim (disclosure
has no delivery channel) independently re-verified rather than relayed.

Run report: [`../runs/2026-07-27_run-60/run_report.md`](../runs/2026-07-27_run-60/run_report.md)
