<!--
CR084-BE.auditor.md — auditor lane file (track U owns). State derives from round numbers
here vs CR084-BE.architect.md (see PROTOCOL.md).
-->

# CR084-BE — audit lane (auditor)

**Item:** CR084-BE — the RevenueCat webhook that turns a verified store purchase into a
server-authoritative plan transition + credit grant, on top of the CR039 credit gate (GTM M1 final
slice, backend half).

**Gate:** independent (D-5 — money, entitlements, store-facing. A wrong or forged grant is real
dollars and a real trust breach.)

**Audited SHA:** `f1e7a1613ba4eff25fa716daad7e34a8ec3034f7`, tip of `lane/CR084-BE.coder.api`
(branched from merge-base `668c6c4`, not yet integrated to main). Audited in an isolated worktree
`.claude/worktrees/audit-CR084-BE/`.

## Round 1

### Reproduced independently

| Check | Result |
|---|---|
| Scope | `git diff --stat 668c6c4..f1e7a161` — **9 files, +956/−0**, exact match. No room-cluster/`trading_math`/forbidden-path touches. |
| Main divergence | Only 2 commits ahead of merge-base (both dispatch/roster docs) — no code drift to reconcile. |
| Full suite | **1099 passed, exit 0** (two runs, 130–151s; warning count varied 4↔5 run-to-run — traced to the same pre-existing `HTTP_422_UNPROCESSABLE_ENTITY` FastAPI deprecation the rest of the codebase already triggers, non-deterministic pytest warning capture across collection order, not a regression). |
| Config parity | `test_config_compose_parity.py` — 3 passed. `REVENUECAT_WEBHOOK_SECRET` genuinely forwarded (`docker-compose.yml:86`). |
| Migration | `alembic heads` → single head `a1c2e3f40020` — no branch fork; chains cleanly off `c5d6e7f80019`. |

### Architect's six suggested adversarial-focus points — each independently verified, four by direct mutation

**1. Forge a grant.** Grepped the whole `app/` tree for every caller of
`set_plan_and_grant_allowance`/`add_credit_pack`/`revoke_to_base` — each has exactly one call site,
all inside `revenuecat_webhook()`, all downstream of the unconditional `_verify_secret(authorization)`
call at the top of the handler. No other route reaches them. Confirmed the empty-secret case
structurally cannot authorize by reading (`if not secret:` raises 503 before `hmac.compare_digest` is
ever reached) **and** by mutation: hit the live endpoint with empty secret + empty `Authorization`
header (byte-identical, which would trivially match if compared) — 503, both with and without a
header present. Then disabled the `if not secret` guard entirely (`if False and not secret:`) and
re-ran the same empty/empty request: it sailed straight past auth and reached the transactional
`INSERT INTO revenuecat_events` (failed only because my throwaway harness hadn't run migrations — an
artifact of the harness, not the code). Proves the guard is load-bearing, not decorative. Reverted.

**2. Break idempotency.** Confirmed `revenuecat_events.event_id` carries a real DB-level
`UniqueConstraint` (not just an ORM annotation) via the migration file. Mutated the webhook's
`except IntegrityError` handler to roll back but *not* return early (falls through to grant again) —
`test_replayed_initial_purchase_does_not_double_grant` and
`test_replayed_credit_pack_adds_credits_once` both went RED with a genuine double-grant (credit pack:
613 vs the expected 313). This proves two things at once: the constraint really does raise
`IntegrityError` on a replay (my mutation only changes what happens *after* the exception), and the
app-code's handling of it — not any other accidental mechanism — is what prevents the double-grant.
Reverted.

**3. Double-grant across trial.** Mutated `set_plan_and_grant_allowance`'s guard
(`granted = window_rolled or target_allowance > current_granted`) to `granted = True` —
`test_active_trial_conversion_does_not_regrant_same_period` went RED (150 vs the expected 100,
i.e. a spent-down trial balance got reset to a fresh 150 on conversion — a free-credits exploit).
Reverted.

**4. Revoke correctness.** Mutated `revoke_to_base` to hardcode `eff = Plan.FLOOR_PASS` after calling
`_ensure_period` (instead of using its return value) — `test_revoke_falls_back_to_trial_when_trial_active`
went RED on its audit-row assertion (`to_value` logged as `floor_pass` instead of `trial_trader`),
even though the live entitlement read (`effective_plan_for_user`) still resolved correctly — showing
the test's audit-trail check is doing real, non-redundant work, not just duplicating the entitlement
check. Reverted. Read `add_credit_pack` in full: touches only `credit_balance`, never `plan` —
confirmed by source, matches the existing `test_credit_pack_adds_credits_no_plan_change`.

**5. The MergeService gap.** Read `merge_service.py` in full (486 lines), independently — not just
trusting the coder's characterization. Confirmed all three claimed gaps are real: (a) grepped the
whole file for `subscription_events`/`revenuecat_events` — the only hit is a **new** row the merge
itself writes (`event_type="account_adoption_merged"`); the orphan's *existing* RC/subscription rows
are never re-keyed, so they dangle under a `user_id` that gets deleted two lines later; (b) `plan`/
`credit_balance`/period fields are never read or copied orphan→adopter anywhere in `execute()` — the
orphan `User` row is deleted outright (`delete(User).where(User.id == from_user_id)`) with no field
migration first, so a pre-claim purchase's plan+credits are genuinely lost; (c) confirmed `_load_user`
in `webhooks.py` already anticipates this — its own docstring cites "possibly deleted by an
anon->claimed merge" and returns a loud 404, not a silent no-op, which is the correct behavior *given*
the upstream gap (CR040-compliant, not masking it). Confirmed via `git log` that the architect
independently reached the same conclusion and already filed **DEF099** for this
(`a7f23bd docs(defect): DEF099 — account merge drops RC entitlement/credit state`), landed on main
after this lane's build — corroborates rather than duplicates my own read. Genuinely out of this
lane's scope (webhook + grant path only; `merge_service.py` isn't in this lane's diff), correctly
flagged, not masking a defect in the grant logic itself.

**6. Fail-closed 503-in-all-envs.** `test_unset_secret_refuses_loudly_with_503` sets the secret to `""`
explicitly (not just unset/`None`) and asserts 503 with an arbitrary `Authorization` header — confirms
the check fires regardless of what's presented. My own direct empty-secret/empty-header round-trip
(focus #1, above) reproduces the same result outside the test suite.

### Additional checks beyond the architect's list

- **`billing.py`** (`GET /v1/billing/identity`) — auth-gated via `Depends(get_current_user)`, no bypass;
  returns `user_id`/`app_user_id` both `== current_user.id`. `test_billing_identity_requires_auth`
  (401 without token) passed in the full suite.
- **`main.py`** — both routers mounted cleanly; diff is additive only (2 import lines + 2
  `include_router` calls), no changes to existing route registration or middleware.
- **`_entitlement_plan`'s highest-tier-wins rule** (line 108: `max(plans, key=lambda p:
  credit_service.ALLOWANCE[p])`) — read correctly: if RC ever sends multiple simultaneous
  entitlement ids, the higher-allowance plan wins rather than an arbitrary/first match.
- **Unmappable purchase / unknown user** — both raise loudly (422 / 404) rather than silently
  no-op-granting nothing while returning 200, per CR040. Read at source, matches the DoD row.

### Findings

Zero BLOCKER, zero MAJOR, zero MINOR. Every one of the architect's six suggested adversarial-focus
points was independently verified — four of them by directly mutating the production source and
confirming a real, correctly-worded test failure (not by reading and trusting the in-suite tests),
then reverting. The one flagged out-of-scope gap (MergeService) was independently re-derived from a
full read of the file, not the hand-off's word for it, and cross-checked against the architect's own
subsequent DEF099 filing.

### Verdict

**VERDICT: COMPLETE (round 1)**

Run report: [`../runs/2026-07-24_run-42/run_report.md`](../runs/2026-07-24_run-42/run_report.md)
