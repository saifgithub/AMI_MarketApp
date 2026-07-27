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
