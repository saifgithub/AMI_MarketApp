<!-- lane hand-off — coder.api. CR052. -->
# BE-DEF113 — hand-off (coder.api, round 1)

STATUS: READY_FOR_AUDIT (round 1)
BRANCH: lane/BE-DEF113 (worktree `../AMI_MarketApp_worktrees/BE-DEF113`, branched from main @ 6bc6f8ff)

## What shipped

1-on-1 chat now has the same charging spine as Room, priced 0 in Alpha via a
declared, config-check-visible setting.

- **`backend/app/core/config.py`** — `Settings.one_on_one_credit_cost: int = 0`,
  validated `>= 0` (fails boot on a negative value, same shape as the CR098
  pull-back validator).
- **`docker-compose.yml`** — `ONE_ON_ONE_CREDIT_COST: ${ONE_ON_ONE_CREDIT_COST:-0}`
  forwarded in the `api-alpha` env block (required or
  `test_config_compose_parity.py` fails the build).
- **`backend/app/services/credit_service.py`** — `one_on_one_cost()` accessor
  (mirrors `room_cost_for_plan`, but flat — 1-on-1 has one price, not a
  plan-keyed table). `room_runner.py` untouched.
- **`backend/app/api/one_on_one.py`** — `send_message` now calls
  `spend(user_id, one_on_one_cost(), reason=f"one_on_one:{agent_id}")`
  **before** `StreamingResponse` is constructed (same reasoning as
  `room.py`: once the SSE status line is on the wire, a refusal can only be
  an in-band error event, which the client renders as a crash, not a wall).
  `InsufficientCredits` → 402 with the same `detail` shape Room uses
  (`code`/`balance`/`cost`/`plan`/`resets_at`). On an LLM failure *after* the
  spend (caught inside `event_stream()`), the turn is refunded before the
  journal write — charged-then-failed must not silently eat a turn even at
  price 0, because the ledger row persists regardless of the price.
  `mobile/` and the deprecated `/v1/coach/*` shim are untouched — the shim
  routes to `brief.py`, not `one_on_one.py`, so nothing there inherits this.
- **`backend/app/api/admin.py` + `backend/app/schemas/admin.py`** —
  `GET /v1/admin/config-check` now returns `one_on_one_credit_cost` (int,
  top-level field, not a `FeatureGate` — those are booleans; this is a price).
  Cheap, so added it rather than reporting it as a gap.
- **`backend/tests/unit/test_def113_one_on_one_credit_gate.py`** — 9 tests,
  new file.

## Acceptance walkthrough

1. **Test that fails against current code:** the whole file fails to even
   *collect* against pre-fix `main` — `ImportError: cannot import name
   'one_on_one_cost'` — because the spend call didn't exist anywhere in
   `one_on_one.py`. Verified live: `git stash` in the worktree (reverting all
   my changes except the test file) → collection error. `git stash pop` →
   green. This is stronger red than a normal assertion failure: the spine
   was structurally absent, not just mis-priced.
2. **402 at a non-zero price:** `test_insufficient_credits_returns_402_at_a_non_zero_price`
   + `test_402_does_not_stream_or_journal_the_turn` monkeypatch
   `settings.one_on_one_credit_cost = 3`, drain the balance to 2, and prove
   the 402 body + that no journal entry / no debit happens on refusal.
3. **Alpha's 0 is a genuine charge-of-zero:**
   `test_zero_price_turn_still_writes_a_ledger_row_and_returns_200` asserts,
   at the real Alpha-default price (no monkeypatch), that a `credits_spent`
   ledger row is written with `from_value == to_value` (a charge of zero
   recorded, not skipped) and the response is 200.
4. **Idempotency / charged-then-failed:** implemented (see above) — a
   `stream_one_on_one_message` failure now refunds via `credit_service.refund`
   at whatever the configured price is, before the journal write. Test:
   `test_llm_failure_after_spend_refunds_at_a_non_zero_price` (run at price 3
   so the refund is observable — at price 0 it would be indistinguishable
   from doing nothing, which is exactly why the test uses a non-zero price).
   **Why refund and not "let it ride" (as CR090-Room does for its surcharge,
   which is deliberately all-or-nothing but only ever charged once the run is
   committed):** 1-on-1's spend happens *before* the LLM call even starts
   (unlike Room, which resolves feeds/roster first), so a failure after the
   charge is *closer* to Room's "failed run refunds" case
   (`room_runner.py`'s `on_complete` refund path) than to a mid-run partial
   success. I did not find a case where a *partial* reply (some tokens
   streamed, then a failure) should keep the charge — credits.md's own
   pre-flight-check section says "If an operation fails partway... credits
   are refunded automatically," which is unambiguous and matches what I
   built.
5. **"5 free 1-on-1s" — reporting only, not implemented, per the fence:**
   `credits.md:40` ("13 = 5 1-on-1s + 1 Room") reads as the *same* pool doing
   double duty — the 13-credit Floor Pass allowance divided against two
   prices. But `credits.md:118-134` ("Free 1-on-1 / Free Room mechanics")
   reads as a **genuinely separate mechanic**:
     - explicitly "tracked **separately** from the regular credit balance"
     - resets on the user's **monthly anniversary**, not the calendar month
       `credit_service._ensure_period`/`ALLOWANCE` actually use
     - the mock UI shows *both* "Free 1-on-1s remaining: 2 of 5" *and*
       "Credit balance: 0" as two distinct numbers in the same modal — if
       they were the same pool there'd be nothing to show twice
   **My belief:** the spec as written describes a second, independent
   free-turn counter, not just the allowance re-labelled — but the two
   sections of `credits.md` contradict each other on this, and reconciling
   them (and deciding whether to build the second counter or fix the spec
   prose) is exactly the call this lane was told to leave to Saiful. Not
   implemented; DEF113's row leaves this open explicitly.
6. **Mutation check:** reverted the `spend()` call in `send_message` (kept
   `one_on_one_cost()` call so `cost` stays defined) — 5 of the 9 new tests
   went RED (`test_message_debits_through_spend_at_a_non_zero_price`,
   `test_insufficient_credits_returns_402_at_a_non_zero_price`,
   `test_402_does_not_stream_or_journal_the_turn`,
   `test_zero_price_turn_still_writes_a_ledger_row_and_returns_200`,
   `test_llm_failure_after_spend_refunds_at_a_non_zero_price`). Re-applied the
   real edit, all 9 green again. Reported honestly — this is the real
   before/after, not a claim.
7. **Full suite** from repo root (this worktree), venv python from the main
   checkout (`backend/.venv` doesn't exist per-worktree):
   `"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest backend/tests/unit/ -q`
   → **1815 passed, 0 failed** (baseline ≥1812, zero failures — met; the one
   named exception, `test_cr084_revenuecat_webhook.py::test_test_store_expiration_revokes_to_floor_pass`,
   is another track's *uncommitted* main-checkout change and this worktree was
   branched from committed `main` @ 6bc6f8ff, so that file is untouched here
   and simply passed along with everything else). Did not touch `webhooks.py`
   or `scripts/`.

## Registers

`docs/defect/_registry/DEF113.row.md` flipped to `fixed` (note text in the
description column per DEF203, status cell stays a bare token); regenerated
`docs/defect/def_list.md` via `python3 scripts/registers/gen_registers.py gen def`.
Row notes CR090's 1-on-1 half is now unblocked, and names the residual "5
free 1-on-1s" question as Saiful's open call, not a gap in this lane.

## Fences respected

- Did not touch `room_runner.py`.
- Did not touch `mobile/`.
- Did not touch the `/v1/coach/*` shim (it routes to `brief.py`, not
  `one_on_one.py` — nothing to inherit).
- Did not implement the "5 free 1-on-1s" mechanic — reported only (§5 above).

## Commit / push

Commits land on `lane/BE-DEF113`, pushed to origin. GATE: none — sprint mode,
Saiful integrates on his own verification; track U audits the sprint as one
batch.
