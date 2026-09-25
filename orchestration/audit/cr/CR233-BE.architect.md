<!--
CR233-BE.architect.md — audit lane. State derives from round numbers here vs CR233-BE.auditor.md.
GATE: independent (CR005 protocol, same routing CR233's own mobile lane used). Safety-floor sizing inputs on a preview path — Tier A.
-->

# CR233-BE — audit lane (backend closure of the round-1 preview price-basis gap)

**SCOPE:** chunk (the backend half of CR233's known gap; the mobile half — forwarding `stop`/`target` on the two ticket preview call sites — is bundled in the same commit since it is small and the two halves cannot be tested independently: a mobile field with nothing reading it server-side is unverifiable, and a backend param nothing sends is dead code).

**TIER: A.** This changes the price basis and bracket-validity check `check_mandate_compliance` sizes a preview against — the same class of input CR233's own architect doc and DEF419-BE's audit lane were both routed to independent review for.

**SHA:** `0167e999` on branch `worktree-agent-a8a36bf01d79ddbf9`, based on `main`'s `c61acd98` (CR233 mobile round 1 + DEF419 round 2 merge). Review with `git diff c61acd98..0167e999`. Not yet merged to `main`, not pushed, no build bump.

**depends-on:** CR233 (round 1, `in_progress`, mobile-only — its own architect doc named this exact gap and flagged it to the Architect for a follow-up; this lane is that follow-up, same CR number per the dispatch brief's instruction, not a new ID). DEF419 round 2 (`fixed` — `preview()`'s `stop`/`proposed_stop`/`unmeasured_rules` plumbing this lane builds on top of, untouched here). **Promoted:** no.

## What and why

CR233's own round-1 architect doc (`orchestration/audit/cr/CR233.architect.md`, "Known gap" §) disclosed rather than fixed: `preview_trade`'s handler (`backend/app/api/sim.py`) forwarded `limit_price` to `SimEngine.preview()` but that method had **no `trigger_price` parameter at all** — a STOP/STOP_LIMIT Alpaca-leg preview sized cash-sufficiency and concentration at the live mark, not the order's own trigger price, and `preview()` ran no bracket-validity check whatsoever (only `submit()`'s path did, via `_execute_fill`'s DEF312/DEF377 refusal). A ticket could preview a STOP order as "accepted" against a price it would never actually be sized at, and preview a wrong-side bracket as "accepted" when `/submit` (or Alpaca's own order call) would then refuse it a moment later — a dry-run that answers a question other than the one being asked.

**The fix:**

- `SimEngine.preview()` (`backend/app/services/sim_engine.py:2428`) gains `trigger_price: float | None = None` and `target: float | None = None` parameters. Where it used to unconditionally set `fill_price = mark` (a deliberate CR170 §3 choice for MARKET orders, but never revisited for STOP/STOP_LIMIT once resting orders existed), it now computes `named = named_price_for(order_type, trigger_price=trigger_price, limit_price=limit_price)` and sets `fill_price = named if named is not None else mark`. `named_price_for` is the SAME function `commitment_for()` (`sim_resting_orders.py`) already calls to price a resting order's committed cash at portfolio-read time — this is not a new pricing rule, it is the existing one reaching a caller that had been left out.
- The same `named` value — not the raw `limit_price` parameter — is passed as `ProposedTrade.limit_price` when building the `proposed` object handed to `check_mandate_compliance`. That function's `unit_price = proposed.limit_price or quotes.get(t) or 0.0` (`safety_floor.py:398`) is the ONE chokepoint every sizing/concentration rule (single-name cap, sector cap, and — via `proposed_stop`/`proposed_contribution` — the open-risk cap) reads its per-share price from (DEF153's "one renderer of one rule" fix). Passing `named` here is what makes a STOP order's `trigger_price` reach that chokepoint too, on both the AMI path and the DEF419 account-snapshot path (same function, different denominator, unchanged by this lane).
- `preview()` now runs a bracket-validity check mirroring `_execute_fill`'s DEF312/DEF377 refusal: for a BUY, or a SELL that opens a short (`held <= 1e-9`), `bracket_is_wrong_side(is_short=..., entry=fill_price, stop=stop, target=target)` is called, and a non-`None` result rejects the preview with that reason, `blocked_by=None` (matching `_execute_fill`'s own convention — this is a mechanical price-relationship refusal, not a mandate-compliance block). **Scoped to `account_snapshot is None`** — the AMI path only, matching `_execute_fill`'s own `kind == "training"` gate. The Alpaca-snapshot path has no AMI short-position concept to decide "does this SELL open a short" from (`sizing_shorts` is already `None` there, per DEF419's own "unknown, don't invent it" convention), and Alpaca's own bracket validation already runs client-side in `validateAlpacaOrder` (CR233 round-1 mobile). Duplicating an unreliable short-detection heuristic against a foreign account would be worse than the gap it claims to close.
- `backend/app/api/sim.py::preview_trade` forwards `trigger_price=req.trigger_price` and `target=req.target` to `sim.preview()` — both were previously read off `SubmitTradeRequest` (which already carries them, and already validates STOP/STOP_LIMIT requires a `trigger_price > 0` at the schema level via `_prices_match_the_order_type`) but dropped on the floor before this fix, never reaching `sim.preview()`'s call.
- Mobile: `ApiClient.simPreview` (`mobile/lib/services/api/api_client.dart:1090`) gains `stop`/`target` parameters, sent on the wire when non-null. `SimNotifier.preview()` (`mobile/lib/state/sim_providers.dart:214`) forwards them. Both trade-ticket preview call sites — `_submitAlpacaOnly` (~line 761) and the BOTH-destination Alpaca leg inside `_legAlpaca` (~line 952) in `mobile/lib/screens/sim/trade_ticket_sheet.dart` — now pass `stop: double.tryParse(_stop.text.trim())` / `target: double.tryParse(_target.text.trim())`, the exact pattern already used at both `/submit` call sites (lines 661-662, 899-900) in the same file.

Design note: `docs/forward_planning/CR233_alpaca_order_types/CR233_alpaca_order_types.md` — "Known gap" section rewritten from "not fixed by this CR" to "CLOSED round 2", with the fix detail; Acceptance section gained a "Round 2 (backend gap closure)" block; Status updated.

## Tests (Architect ran on this worktree, bare)

**Backend**, `cd backend && .venv/bin/python -m pytest tests/unit/test_cr233_preview_price_basis.py tests/unit/test_sim_engine.py tests/unit/test_def419_per_account_mandate_check.py tests/unit/test_safety_floor.py tests/unit/test_wire_contract_parity.py tests/unit/test_config_compose_parity.py -q` → `88 passed, 1 skipped` (exit 0). Broader sweep, `-k "sim or preview or def419 or cr233 or order_pricing or bracket or safety_floor"` over the full `tests/unit/` tree → `332 passed, 6456 deselected` (exit 0).

New file `backend/tests/unit/test_cr233_preview_price_basis.py` (6 tests, wire-level via `TestClient` against `/v1/sim/preview`):
- STOP preview sizes at `trigger_price`, not mark, on the AMI path (and the inverse: a trigger that IS affordable is accepted even though the mark alone would breach cash — proves the basis is genuinely the trigger, not a max/min of the two).
- STOP_LIMIT preview sizes at `trigger_price` on the DEF419 Alpaca-snapshot path.
- A wrong-side bracket (`stop` above entry on a BUY) is refused at preview, and the positive twin (right-side bracket accepted).
- A MARKET preview still sizes at the live mark — unaffected by this lane.

New tests appended to `backend/tests/unit/test_sim_engine.py` (6 tests, direct `SimEngine.preview()` calls with a `_ConstProvider` fixed-price provider, mirroring `test_cr026_sector_allocation.py`'s existing pattern): the same STOP/STOP_LIMIT trigger-price-sizing and bracket-refusal claims, pinned at the engine layer rather than over HTTP — the two layers together prove both "the arithmetic is right" and "the route actually forwards the fields".

**Mobile**, `cd mobile && flutter analyze` → 11 issues, all pre-existing info-level (deprecated_member_use, use_build_context_synchronously, use_super_parameters, unnecessary_import), 0 errors — same baseline as before this lane. Before this lane's fix to the four `SimNotifier.preview()` overrides in `test/screens/sim/{cr227_destination_routing,cr230_alpaca_order_log,cr233_ticket_order_types,def419_per_account}_test.dart`, adding `stop`/`target` to the base class signature produced 4 `invalid_override` errors — each override needed the same two optional named parameters added (Dart requires an override to accept at least the parameters the base declares); confirmed those 4 errors, fixed, re-confirmed clean.

`cd mobile && flutter test` → `1589 tests passed` (exit 0), full suite (1575 baseline + 14 new: 4 backend-adjacent aren't mobile — the +14 here is 4 new tests in `cr233_ticket_order_types_test.dart` (2 in the Alpaca-only group: stop/target forwarded, and empty-fields-send-null; 1 in the BOTH group: same for `_legAlpaca`) plus incidental count drift from the same file's existing tests unaffected — see that file's diff for the exact 3 new `testWidgets` blocks).

**Mutation checks** (backend + mobile, both verified then reverted, `git status`/`git diff` confirmed clean after each revert):

1. **Backend, price basis.** Reverted `fill_price = named if named is not None else mark` / `limit_price=named` back to `fill_price = mark` / `limit_price=limit_price` (the round-1 shape). `test_sim_engine.py` + `test_cr233_preview_price_basis.py` together: **6 failures** (`test_preview_stop_buy_sizes_cash_at_trigger_not_mark`, `test_preview_stop_buy_passes_at_trigger_even_though_mark_would_breach`, `test_preview_stop_limit_sizes_at_trigger_price`, `test_stop_preview_sizes_at_trigger_price_not_mark_ami_path`, `test_stop_preview_accepted_when_trigger_affordable_even_if_mark_is_not`, `test_stop_limit_preview_sizes_at_trigger_on_alpaca_snapshot_path`). Reverted; 30/30 green again.
2. **Backend, bracket check.** Replaced the new `if accepted and account_snapshot is None: ...` block with `if False: pass`. **2 failures** (`test_preview_refuses_wrong_side_bracket_on_a_buy`, `test_preview_refuses_wrong_side_bracket_ami_path`). Reverted; green again.
3. **Mobile, stop/target forwarding.** Removed `stop:`/`target:` from `_submitAlpacaOnly`'s `preview(...)` call. `flutter test test/screens/sim/cr233_ticket_order_types_test.dart` → the new "sends stop/target" test failed with an explicit assertion mismatch; the file's own summary line read `+7 -1` at that point (one test failed, the mutation caught). Reverted (`diff` against the pre-mutation file confirmed byte-identical); 13/13 green again.

## Measurement

None live yet — unpromoted. `docs/forward_planning/CR233_alpaca_order_types/CR233_alpaca_order_types.md`'s own Status still reads `in_progress` for the overall CR (round-1 mobile mid-review, round-2 backend submitted here); this lane closes the specific gap round 1 disclosed, not the whole CR.

## Attack surface (please probe)

1. **Preview/submit price-basis divergence.** Confirm `preview()`'s new `fill_price`/`unit_price` basis (`named_price_for(...) or mark`) genuinely matches what `submit()` would book a MARKETABLE order at (CR170 §3's "marketable at submit time fills at mark, not the named price" rule) versus what it would REST at (`named`, then Rule 2's worse-of on eventual fill). `preview()` reports `named` for a non-marketable order and cannot know Rule 2's eventual worse-of fill in advance — judge whether reporting `named` (the conservative, committed-cash anchor `commitment_for()` already uses) rather than attempting to predict Rule 2's outcome is the right disclosure, or whether it understates/overstates notional for a resting order that will eventually fill at a WORSE price than its own named one.
2. **Bracket validation parity.** Confirm the AMI-path-only scoping (`account_snapshot is None`) is genuinely inert on the snapshot path rather than silently permitting a wrong-side bracket there — re-derive `sizing_shorts is None` on that path independently rather than taking this doc's word that "opens a short" is undecidable for an Alpaca snapshot. Consider whether disclosing this scoping to the user (an unmeasured-rule-style note) belongs on this lane or is out of scope.
3. **`stop` omitted → behaviour.** Confirm a preview with no `stop`/`target` at all is byte-identical to pre-this-lane behaviour on every path (the bracket check's `stop is None and target is None` case must fall through `bracket_is_wrong_side` as `None`/no-op — verify this holds for BOTH the long and the opens-short branches, not just the long one the new tests emphasize).
4. **Snapshot-path open-risk, with and without `stop`.** This lane does not touch DEF419's `proposed_stop`/`unmeasured_rules` wiring, but it does change what `fill_price`/`notional` the response reports for a STOP order on the snapshot path. Confirm `test_stop_limit_preview_sizes_at_trigger_on_alpaca_snapshot_path` in `test_cr233_preview_price_basis.py` genuinely exercises the snapshot branch's `sizing_portfolio_value`/`sizing_cash` (Alpaca equity/cash) rather than accidentally falling through to the AMI branch — re-run it with a print/breakpoint on `account_snapshot` if the account JSON's shape is suspect.
5. **`ProposedTrade.limit_price=named` reuse.** This is the same field DEF153 already made the single sizing chokepoint; confirm this lane's substitution (`named` in place of the raw `limit_price` parameter) does not change behaviour for a plain LIMIT order (`named` IS `limit_price` for LIMIT — `named_price_for` returns `limit_price` unchanged in that branch) or for MARKET (`named` is `None`, falls through to `mark` via the `quotes.get(t)` branch inside `safety_floor.py`, unchanged). Only STOP/STOP_LIMIT's answer should differ from round 1.
6. **Mobile override-signature drift.** Four test-double subclasses of `SimNotifier` needed `stop`/`target` added to stay valid overrides. Confirm no FIFTH override exists elsewhere in the mobile test tree that this lane's `flutter analyze` sweep might have missed (the analyzer surfaced all four as compile errors, which is a strong signal, but grep independently: `grep -rn "Future<SimPreviewResult?> preview(" mobile/`).

SUBMITTED: round 1

## Round 2 — fix for MAJOR-1

**SHA:** `c082e4dd` on branch `worktree-agent-a3d411df720d206a1`, based on `main`'s
`b5de455c`. Fix commit is `472905e8` ("fix: preview() and submit() size STOP/STOP_LIMIT
orders identically (AT:R85 CR233)"); `c082e4dd` is a separate, unrelated DEF416 commit
made in the same session — review CR233-BE with `git diff b5de455c..472905e8` or
`git show 472905e8`.

### The fix

**One shared helper, used everywhere a non-market order's compliance-sizing price is
needed.** `committed_price_for()` (`backend/app/trading_math/order_pricing.py`, new
function, ~85 lines with docstring) takes `(side, order_type, mark, trigger_price,
limit_price)` and returns:

- **MARKET** — always `mark`.
- **Already triggered** (`is_triggered(...)` true at the current mark) — always `mark`,
  no matter the order type. This is the auditor's exact P1/P2 finding: `submit()` books
  a marketable order (any type) at `mark` unconditionally (CR170 §3 acceptance 1,
  `sim_engine.py`'s `fill_price = mark` set BEFORE the rest-vs-fill branch even runs),
  so the compliance check must size at that same price, not the order's stale named
  price.
- **Resting STOP or LIMIT** — the order's own named price (`trigger_price` /
  `limit_price`), the same conservative anchor `commitment_for()`
  (`sim_resting_orders.py`) already uses for a resting order's committed cash at read
  time.
- **Resting STOP_LIMIT** — the order's own **LIMIT**, never the trigger alone (the
  auditor's P3: once resting, a stop-limit can fill anywhere up to its limit —
  `stop_limit_becomes_limit`'s "the trigger converts it into a resting LIMIT, then
  Rule 1/2 re-apply against `limit_price`" is the exact mechanism).

**Three call sites now use it, not two — the auditor's fix note said "preview and
submit"; a third instance of the identical bug class was found and fixed in the same
pass:**

1. `SimEngine.preview()` (`sim_engine.py:2551-2565`, was `named_price_for(...) or
   mark`) — `fill_price = committed_price_for(...)`, passed as `ProposedTrade.limit_price`
   into `check_mandate_compliance` exactly as round 1 already did with the wrong value.
2. `SimEngine.submit()` (`sim_engine.py:1452-1481`) — a NEW `committed_price` local,
   computed the same way, passed as `ProposedTrade.limit_price` for the compliance
   check ONLY. `fill_price` (what the order actually books at if it fills now) stays
   `mark` unconditionally, unchanged — the two are different questions and round 2 had
   conflated them by never touching `submit()`'s `ProposedTrade` construction at all
   (it passed the raw `limit_price` parameter, `None` for a plain STOP, silently
   falling back to `quotes.get(ticker)` — the live mark — inside `safety_floor.py`'s
   `unit_price` chokepoint). This was a second, previously-unmeasured instance of the
   SAME bug class MAJOR-1 named, on `submit()`'s own resting-order compliance check —
   found by an agent I dispatched to verify whether `submit()` had this gap too before
   writing the parity test; confirmed via direct call (`app/services/sim_engine.py:1453`,
   `app/agents/safety_floor.py:451`) before fixing it.
3. `SimEngine.fill_resting_order()` (`sim_engine.py:1992-2015`) — the fill-time re-run
   of `check_mandate_compliance` (CR170's no-time-delayed-bypass guarantee) had the
   identical shape: `ProposedTrade(limit_price=order.limit_price)`, `None` for a plain
   STOP. Fixed by computing `resting_fill_price` (Rule 2's worse-of, `fill_price_for`)
   BEFORE the compliance check runs instead of after, and passing it as
   `ProposedTrade.limit_price` — the re-check now sizes against the exact price the
   order is about to book at, not a stale value.

### Tests (Architect ran on this worktree, bare)

```
cd backend && .venv/bin/python -m pytest \
  tests/unit/test_sim_engine.py \
  tests/unit/test_cr233_preview_price_basis.py \
  tests/unit/test_cr233be_preview_submit_price_parity.py \
  tests/unit/test_def419_per_account_mandate_check.py \
  tests/unit/test_safety_floor.py \
  tests/unit/test_wire_contract_parity.py \
  tests/unit/test_config_compose_parity.py \
  -q -p no:cacheprovider
117 passed, 1 skipped     EXIT=0
```

Full targeted list from the dispatch brief (adds DEF416's files, registers, ratchet):
`test_sim_engine.py`, `test_cr233_preview_price_basis.py`,
`test_cr233be_preview_submit_price_parity.py`, `test_def419_per_account_mandate_check.py`,
`test_safety_floor.py`, `test_wire_contract_parity.py`, `test_def416_oidc_unique_race.py`,
`test_auth_service.py`, `test_auth_google.py`, `test_p15_check_then_insert_guard.py`,
`test_def200_ratchet.py`, `test_config_compose_parity.py`, `test_registers_no_drift.py`,
`test_p30_registers_name_things_that_exist.py` — 179 passed, 1 skipped, EXIT=0.

**Existing round-1 tests updated, not just added to.** Two round-1 tests in
`test_sim_engine.py` and one in `test_cr233_preview_price_basis.py` pinned the OLD
(wrong) basis and had to be corrected to the new one — each rewritten as a marketable
vs. resting PAIR rather than dropped, so the old claim ("sizes at trigger") is still
checked, now scoped to the case where it is actually true (still resting):

- `test_preview_stop_buy_passes_at_trigger_even_though_mark_would_breach` — round 1's
  version put the trigger UNDER the mark (already triggered), which the docstring
  itself said was testing "a trigger under the mark" while the numbers described a
  marketable order (flagged by the auditor as not pinning what it claimed to). Fixed to
  a genuinely-resting shape (trigger above mark); a new sibling test,
  `test_preview_stop_buy_marketable_sizes_at_mark_not_trigger`, pins the
  now-correctly-refused marketable case with the ORIGINAL numbers.
- `test_preview_stop_limit_sizes_at_trigger_price` → split into
  `test_preview_stop_limit_resting_sizes_at_limit_not_trigger` (resting, sizes at the
  limit) and `test_preview_stop_limit_marketable_sizes_at_mark_not_trigger_or_limit`
  (marketable, sizes at mark).
- `test_stop_limit_preview_sizes_at_trigger_on_alpaca_snapshot_path` (wire-level) →
  `test_stop_limit_preview_resting_sizes_at_limit_on_alpaca_snapshot_path` (resting) +
  `test_stop_marketable_preview_sizes_at_mark_on_alpaca_snapshot_path` (marketable,
  matching the auditor's own measured P2 numbers: 1% trigger, 10% cap, ~$408 mock mark).

**New file**, `backend/tests/unit/test_cr233be_preview_submit_price_parity.py` (26
tests):

1. `test_committed_price_for_table` — 14-row parametrized table pinning the helper's
   own arithmetic directly (every order type x side x triggered/untriggered
   combination named in the fix brief).
2. `test_preview_submit_agree_buy_ami_path` / `..._alpaca_snapshot_path` — call
   `preview()` and `submit()` with IDENTICAL order parameters and assert they refuse at
   the exact same `position_pct` (parsed out of the single-name-cap violation string,
   not just "both refused" — a weaker accepted==accepted check can pass by coincidence
   when two different wrong prices both happen to breach the same cap; extracting the
   number closes that hole). Cash-sufficiency was deliberately NOT used as the shared
   probe for a resting order: `_rest_order()` never reserves cash (documented, §6 of its
   own docstring), so `submit()` returning `accepted=True` for a resting order means
   "parked", not "affordable" — comparing it against `preview()`'s bespoke cash check
   would compare two different questions. The single-name cap runs on every path
   (marketable fill, resting placement, preview) and reads the exact `unit_price`
   chokepoint this fix targets.
3. `test_preview_submit_agree_sell_stop_marketable_ami_path` — the SELL side, mirroring
   the BUY-side parity from the other side of the book.
4. `test_fill_resting_order_sizes_cap_check_at_actual_fill_price` — the third call
   site: places a resting STOP_LIMIT, gaps the mark past both trigger and limit, and
   confirms `fill_resting_order()`'s re-run compliance check sizes at the ACTUAL Rule-2
   fill price, not the stale stored limit (isolated from the cash-sufficiency check by
   keeping both prices well under available cash, so only the cap check's own number is
   being probed).

### Mutation evidence (each reverted via `Edit`, `git diff` confirmed byte-identical after)

| Mutation | Result |
|---|---|
| `preview()`'s `committed_price_for(...)` call reverted to round 2's `named_price_for(...) or mark` | 11 failed across `test_cr233be_preview_submit_price_parity.py`, `test_sim_engine.py`, `test_cr233_preview_price_basis.py` |
| `submit()`'s new `committed_price` passed to `ProposedTrade` reverted to the raw `limit_price` parameter | 3 failed in the parity suite (the resting-order cases, where the two values differ) |
| `fill_resting_order()`'s `resting_fill_price` (computed early) reverted to `order.limit_price` in the `ProposedTrade` | the dedicated fill-time parity test failed (accepted `True` where it must refuse) |

One dead end worth recording: my FIRST attempt at the `submit()` mutation used
cash-sufficiency as the probe and found NOTHING (0 failures) — `_rest_order()` never
checks cash, so a resting order's `submit()` call returns `accepted=True` regardless of
price. Rewrote the probe around the single-name cap (which DOES run on every path)
before re-attempting the mutation, which is when it correctly killed. Recorded because
it is the same class of false-negative the auditor's own P1 finding warns about:
picking the wrong invariant to probe looks like a passing test and proves nothing.

### Attack surface — my own answers to round 1's numbered items

1. **Preview/submit price-basis divergence** — closed. `committed_price_for()` is now
   the single source both call, and `test_committed_price_for_table` pins its answer
   for every combination named in the fix brief.
2. **Bracket validation parity (AMI-path-only scoping)** — untouched by this round;
   round 1's `account_snapshot is None` scoping is orthogonal to the price-basis fix.
3. **`stop`/`target` omitted** — untouched; still falls through to `bracket_is_wrong_side`
   as a no-op, unaffected by the price-basis change.
4. **Snapshot-path open-risk with/without `stop`** — `test_stop_marketable_preview_sizes_at_mark_on_alpaca_snapshot_path`
   and the resting sibling both exercise `account_snapshot`'s branch explicitly (a
   non-`None` `AccountSnapshotIn`), not the AMI fallback.
5. **`ProposedTrade.limit_price=named` reuse** — extended, not changed in kind:
   `preview()` still passes ONE value into that chokepoint; it is now
   `committed_price_for(...)`'s answer rather than round 2's `named_price_for(...) or
   mark`. LIMIT/MARKET's answer is unchanged for the resting case (LIMIT's committed
   price is still its own `limit_price` when resting) and now ALSO correctly matches
   `mark` for a marketable LIMIT (round 2 left this gap open too — a marketable buy
   limit was sized at its limit rather than the mark it actually fills at, which this
   round's `committed_price_for` closes as a side effect of the general fix, pinned by
   `test_committed_price_for_table`'s LIMIT rows).
6. **Mobile override-signature drift** — out of scope for this round (backend-only fix).

SUBMITTED: round 2
