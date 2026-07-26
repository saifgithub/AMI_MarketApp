<!--
Auditor run report — run-50 (2026-07-26, session auditor.core/track U). Round-1 audit of
DEF099. Audited SHA 0433165 on lane/DEF099.coder.api. Verdict COMPLETE. Owner: AUDITOR.
-->

# run-50 (round 1) — DEF099 account-merge billing carry → COMPLETE

- **Auditor session:** auditor.core (track U), 2026-07-26.
- **Audited SHA:** `0433165`, tip of `lane/DEF099.coder.api`. Audited in a fresh isolated worktree
  `.claude/worktrees/audit-DEF099/`.
- **The item:** an anon→claimed account merge was silently dropping RevenueCat entitlement +
  credit state — a pre-claim anonymous purchase did not survive account claim, violating the
  locked anonymous-first decision. This is the exact gap I flagged during my own CR084-BE audit
  earlier this session, now returning as the fix under audit.
- **Gate:** independent — money + entitlements, D-5, plus an explicit architect instruction to
  verify against a real merge path rather than trust the fixtures (the DEF089/DEF092/DEF094
  lesson: verifying the component ≠ verifying the contract).
- **Verdict:** COMPLETE (round 1) — zero findings.

## Verification

### Reproduced independently

8 files, 1212 tests passed, compose parity green. Confirmed `plan_rank` reuses the pre-existing
entitlement ranking (not a new parallel one that could disagree with `effective_plan()`), the RC
alias transfer genuinely runs after the DB transaction commits (verified by indentation, not
inferred), and the orphan's `User` row is fetched for the billing carry well before it's deleted.

### Two independent live scripts, written from scratch — the bulk of this audit's effort

1. My own single-merge scenario, deliberately using different numbers than the shipped test
   fixtures, run through the real `AuthService`/`MergeService`/`credit_service` with no mocks:
   confirmed the higher-plan-wins + credits-sum carry, the re-keying, and — critically — that a
   post-merge `balance_for()` read does not silently wipe the carried sum back down mid-month.
2. A 2-hop chain-merge scenario (A merged into B, then B later merged into C) that has **zero**
   coverage in the shipped test suite. Sent a live webhook for A's twice-orphaned original id
   through the real endpoint and confirmed it resolves — 200, not 404 — with the grant correctly
   landing on C, the final surviving account. This independently proves the bounded 5-hop
   chain-follow safety net (with cycle protection) genuinely works for the exact scenario it was
   written to handle, which the coder's own 11 tests never exercise.

### Three mutation-tested claims

The conflict-rule direction (hardcoded always-take-the-orphan's-plan) and the mid-month period
re-stamp (removed entirely) were each disabled in turn — both caught cleanly by name, then
reverted. Suite re-confirmed clean afterward.

### `revenuecat_client.py`

Read in full; confirmed it never raises and degrades loudly on an unset key — live-observed
identically in both of my own scripts.

## Findings

None.

## Verdict

**VERDICT: COMPLETE (round 1)**
