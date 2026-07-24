<!--
Auditor run report — run-42 (2026-07-24, session auditor.core/track U). Round-1 audit of
CR084-BE. Audited SHA f1e7a161 on lane/CR084-BE.coder.api. Verdict COMPLETE. Owner: AUDITOR.
-->

# run-42 (round 1) — CR084-BE RevenueCat webhook (money/entitlements) → COMPLETE

- **Auditor session:** auditor.core (track U), 2026-07-24. Picked off the run queue.
- **Audited SHA:** `f1e7a1613ba4eff25fa716daad7e34a8ec3034f7`, tip of `lane/CR084-BE.coder.api`
  (branched from merge-base `668c6c4`; not yet integrated to main). Audited in a fresh isolated
  worktree `.claude/worktrees/audit-CR084-BE/`.
- **The item:** the RevenueCat webhook (`POST /v1/webhooks/revenuecat`) that turns a verified store
  purchase into a server-authoritative plan transition + credit grant, plus `GET /v1/billing/identity`
  (the RC `app_user_id` linkage contract CR084-MOBILE depends on). GTM Milestone M1's final slice,
  backend half.
- **Gate:** independent (D-5 — money, entitlements, store-facing; a wrong or forged grant is real
  dollars and a real trust breach). The highest-stakes item audited this session.
- **Verdict:** COMPLETE (round 1) — zero BLOCKER, zero MAJOR, zero MINOR.

## Verification

### Reproduced independently

| Check | Result |
|---|---|
| Scope | 9 files, +956/−0 — exact match, no forbidden-path touches. |
| Full suite | 1099 passed, exit 0 (two runs). |
| Config parity | 3 passed; `REVENUECAT_WEBHOOK_SECRET` genuinely forwarded in `docker-compose.yml`. |
| Migration | Single alembic head, clean chain off `c5d6e7f80019`. |

### Six adversarial-focus points from the architect's hand-off — four verified by direct mutation

1. **Forge a grant** — every grant-function call site traced; all gated behind one unconditional
   secret check. Removed the `if not secret` guard entirely and confirmed an empty-secret/empty-header
   request sails past auth to the DB insert. Reverted.
2. **Break idempotency** — confirmed a real DB `UniqueConstraint` on `event_id` (not ORM-only).
   Mutated the exception handler to roll back without returning early → both replay tests went RED
   with a genuine double-grant (613 vs 313 credits). Reverted.
3. **Trial double-grant** — mutated the regrant guard to always-true → the trial-conversion test went
   RED with a real 150-credit over-grant (should have stayed at the spent-down 100). Reverted.
4. **Revoke correctness** — mutated `revoke_to_base` to ignore the trial-aware effective plan →
   the audit-row assertion caught the mismatch even though the live entitlement read still resolved
   correctly, proving the test does real work. Reverted. Credit-pack-never-touches-plan confirmed by
   reading `add_credit_pack` in full.
5. **The MergeService gap** — read `merge_service.py` in full (486 lines) independently; confirmed all
   three claimed gaps are real (RC/subscription rows not re-keyed, plan/credit_balance not carried,
   orphan deleted outright). Confirmed genuinely out of this lane's scope and not masking a grant-path
   defect — the webhook's own 404-on-unknown-user handling is itself correct given the gap. Cross-
   checked against `git log`: the architect independently reached the same conclusion and already
   filed **DEF099** for it.
6. **Fail-closed in all envs** — the in-suite test explicitly sets secret to `""` (not just unset) and
   asserts 503 with an arbitrary header; reproduced independently via direct TestClient calls.

### Additional checks beyond the hand-off's list

`billing.py`'s identity endpoint is properly auth-gated with no bypass; `main.py`'s router mounting is
purely additive; the highest-tier-wins entitlement resolution and the loud-422/404 unmappable-purchase
paths were read at source and match the DoD.

## Findings

None. This is the highest-stakes item audited this session (D-5, real money/entitlements) and
received the most adversarial verification: four separate production-source mutations, each proven
to flip a specific test red for the expected reason, then reverted, rather than reading and trusting
the in-suite guard-on-the-guard claims. The one disclosed out-of-scope gap (MergeService) was
independently re-derived from a full source read and corroborated by the architect's own subsequent
DEF099 filing.

## Verdict

**VERDICT: COMPLETE (round 1)**
